# routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session, current_app, send_from_directory
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db, login_manager
from models import User, Chat, Message, Attachment
from forms import RegisterForm, LoginForm, UsernameForm
from utils import (
    send_verification_email,
    hash_password,
    verify_password,
    generate_chat_title,
    generate_response,
    read_file_content,
    read_stored_file_content,  # <- added
)
from itsdangerous import URLSafeTimedSerializer
from sqlalchemy.exc import IntegrityError
import json, os, uuid
from werkzeug.utils import secure_filename

app_routes = Blueprint("app_routes", __name__)

# ---------------- USER LOADER ----------------
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ---------------- HOME ----------------
@app_routes.route("/")
def index():
    return render_template("index.html")


# ---------------- REGISTER ----------------
@app_routes.route("/register", methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data

        existing = User.query.filter_by(email=email).first()
        if existing:
            flash("⚠️ Email already registered.", "danger")
            return redirect(url_for("app_routes.register"))

        new_user = User(email=email, is_confirmed=False)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        send_verification_email(new_user)

        flash("✅ Registration successful! Please check your Gmail to confirm before login.", "info")
        return redirect(url_for("app_routes.login"))

    return render_template("register.html", form=form)


# ---------------- CONFIRM EMAIL ----------------
@app_routes.route("/confirm/<token>")
def confirm_email(token):
    serializer = URLSafeTimedSerializer(current_app.config.get("SECRET_KEY"))
    try:
        email = serializer.loads(token, salt="email-confirm", max_age=3600)
    except Exception:
        flash("⚠️ Confirmation link invalid or expired.", "danger")
        return redirect(url_for("app_routes.login"))

    user = User.query.filter_by(email=email).first_or_404()
    if not user.is_confirmed:
        user.is_confirmed = True
        db.session.commit()
        login_user(user)  # Auto-login
        flash("✅ Email confirmed! Please set your username.", "success")
        return redirect(url_for("app_routes.set_username"))
    else:
        flash("ℹ️ Account already confirmed. Please login.", "info")
        return redirect(url_for("app_routes.login"))


# ---------------- LOGIN ----------------
@app_routes.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data

        user = User.query.filter_by(email=email).first()

        if not user:
            flash("⚠️ No account with this email.", "danger")
            return redirect(url_for("app_routes.login"))

        if not user.is_confirmed:
            flash("⚠️ Please confirm your email before logging in.", "warning")
            return redirect(url_for("app_routes.login"))

        if not user.check_password(password):
            flash("❌ Incorrect password.", "danger")
            return redirect(url_for("app_routes.login"))

        login_user(user)
        flash(f"✅ Welcome back, {user.username or user.email}!", "success")

        if not user.username:
            return redirect(url_for("app_routes.set_username"))

        return redirect(url_for("app_routes.jarvis"))

    return render_template("login.html", form=form)


# ---------------- SET USERNAME ----------------
@app_routes.route("/set-username", methods=["GET", "POST"])
@login_required
def set_username():
    form = UsernameForm()
    if form.validate_on_submit():
        username = form.username.data
        if User.query.filter_by(username=username).first():
            flash("⚠️ Username already taken.", "danger")
            return redirect(url_for("app_routes.set_username"))

        current_user.username = username
        db.session.commit()

        flash("✅ Username set successfully!", "success")
        return redirect(url_for("app_routes.jarvis"))

    return render_template("set_username.html", form=form)


# ---------------- LOGOUT ----------------
@app_routes.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You've been logged out.", "info")
    return redirect(url_for("app_routes.login"))


# ---------------- MAIN CHAT PAGE ----------------
@app_routes.route("/jarvis")
@login_required
def jarvis():
    if not current_user.username:
        return redirect(url_for("app_routes.set_username"))

    user_chats = Chat.query.filter_by(user_id=current_user.id).order_by(Chat.created_at.desc()).all()

    # Ensure at least one chat exists
    if not user_chats:
        new_chat = Chat(name="New Chat", user_id=current_user.id, memory=json.dumps([]))
        db.session.add(new_chat)
        db.session.commit()
        user_chats.append(new_chat)

    active_chat_id = request.args.get("chat_id")
    active_chat = None
    if active_chat_id:
        try:
            active_chat = Chat.query.filter_by(id=active_chat_id, user_id=current_user.id).first()
        except Exception:
            active_chat = None

    if not active_chat:
        active_chat = user_chats[0]

    # safe: ensure messages is always a list
    messages = Message.query.filter_by(chat_id=active_chat.id).order_by(Message.timestamp).all() if active_chat else []

    return render_template("jarvis.html",
                           user=current_user,
                           chats=user_chats,
                           active_chat=active_chat,
                           active_chat_id=getattr(active_chat, "id", None),
                           messages=messages)


# ---------------- helper: upload folder ----------------
def ensure_upload_folder():
    upload_dir = os.path.join(current_app.instance_path, 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    return upload_dir


# ---------------- SEND MESSAGE (updated to handle attachments list) ----------------
@app_routes.route("/send_message/<int:chat_id>", methods=["POST"])
@login_required
def send_message(chat_id):
    chat = Chat.query.get_or_404(chat_id)
    user_msg = ""
    uploaded_content = ""
    attachments_ids = []

    # If multipart form (direct file + prompt form submit)
    if request.content_type and request.content_type.startswith("multipart/form-data"):
        # Keep old behavior for direct uploads in form submit
        user_msg = request.form.get("prompt", "") or ""
        for f in request.files.getlist("file"):
            if f and f.filename:
                text = read_file_content(f)
                uploaded_content += f"\n\n[Uploaded: {f.filename}]\n{text}"
        attachments_ids = []
    else:
        # JSON path (used by the frontend)
        data = request.get_json(silent=True) or {}
        user_msg = data.get("message", "") or ""
        attachments_ids = [a.get("id") for a in (data.get("attachments") or []) if a.get("id")]

    # Build initial prompt (user text + any inline uploaded content)
    final_prompt = (user_msg + uploaded_content).strip()

    # If no text but attachments exist, we'll still build prompt from attachments.
    if not final_prompt and not attachments_ids:
        return jsonify({"reply": ""})

    # Build attachments text (extract/describe)
    attachments_text_parts = []
    if attachments_ids:
        for aid in attachments_ids:
            try:
                aid_int = int(aid)
            except Exception:
                continue
            att = Attachment.query.get(aid_int)
            if not att:
                continue
            # only process attachments owned by the current user
            if att.user_id != current_user.id:
                continue

            # read/ocr stored file (utils handles OCR fallback)
            try:
                snippet = read_stored_file_content(att, max_chars=4000)
                if snippet:
                    attachments_text_parts.append(snippet)
            except Exception as e:
                current_app.logger.exception("Failed to read stored attachment %s: %s", aid_int, e)
                # fallback: include a filename/link
                try:
                    url = url_for('app_routes.serve_file', file_id=att.id, _external=True)
                except Exception:
                    url = f"[file://{getattr(att, 'path', getattr(att, 'stored_name', 'unknown'))}]"
                attachments_text_parts.append(f"[Attachment: {att.filename}] Accessible at: {url}")

    # Append attachments block to prompt (delimited)
    if attachments_text_parts:
        attachments_block = "\n\n--- Attachments ---\n" + "\n\n".join(attachments_text_parts) + "\n--- End attachments ---\n"
        final_prompt = (final_prompt + "\n\n" + attachments_block).strip()

    # Save user message (content includes any attachments text)
    user_message = Message(content=final_prompt or user_msg, sender="user", chat_id=chat.id)
    db.session.add(user_message)
    db.session.flush()  # assign id to user_message so we can link attachments

    # Link attachments (if any) to this message & chat (only if the uploader is the owner)
    if attachments_ids:
        for aid in attachments_ids:
            try:
                aid_int = int(aid)
            except Exception:
                continue
            att = Attachment.query.get(aid_int)
            if not att:
                continue
            if att.user_id != current_user.id:
                continue
            att.chat_id = chat.id
            # ensure Attachment model has message_id column (migration/auto-add earlier)
            try:
                att.message_id = user_message.id
            except Exception:
                # if attribute doesn't exist (older DB), ignore silently
                pass
            db.session.add(att)

    # Load chat memory
    memory = json.loads(chat.memory or "[]")
    memory.append({"role": "user", "content": final_prompt})

    # Get AI response (the prompt now includes attachments text/captions)
    ai_reply = generate_response(final_prompt, current_user.username or "User", memory)

    ai_message = Message(content=ai_reply, sender="assistant", chat_id=chat.id)
    db.session.add(ai_message)

    # Update memory
    memory.append({"role": "assistant", "content": ai_reply})
    chat.memory = json.dumps(memory[-20:])  # keep last 20 turns

    # Auto-title
    if chat.name == "New Chat" and user_msg:
        chat.name = generate_chat_title(user_msg, current_user.username or "User")

    db.session.commit()
    return jsonify({"reply": ai_reply})


# ---------------- RENAME CHAT (XHR-friendly) ----------------
@app_routes.route("/rename_chat/<int:chat_id>", methods=["POST"])
@login_required
def rename_chat(chat_id):
    chat = Chat.query.get_or_404(chat_id)
    new_name = ""
    if request.is_json:
        new_name = (request.get_json(silent=True) or {}).get("name") or ""
    else:
        new_name = request.form.get("new_name") or (request.json.get("name") if request.json else "")

    if new_name:
        chat.name = new_name.strip()
        db.session.commit()

    wants_json = request.is_json or ('application/json' in (request.headers.get('Accept') or ''))
    if wants_json:
        return jsonify({"success": True, "name": chat.name})
    return redirect(url_for("app_routes.jarvis", chat_id=chat.id))


# ---------------- UPLOAD FILE (XHR) ----------------
@app_routes.route("/upload_file/<int:chat_id>", methods=["POST"])
@login_required
def upload_file(chat_id):
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file part'}), 400

    f = request.files['file']
    if not f or f.filename == '':
        return jsonify({'success': False, 'error': 'No selected file'}), 400

    filename = secure_filename(f.filename)
    ext = os.path.splitext(filename)[1] or ''
    uniq = uuid.uuid4().hex
    stored_name = f"{uniq}{ext}"
    upload_dir = ensure_upload_folder()
    save_path = os.path.join(upload_dir, stored_name)

    try:
        f.save(save_path)
    except Exception as e:
        current_app.logger.exception("Failed to save upload")
        return jsonify({'success': False, 'error': 'Could not save file'}), 500

    att = Attachment(
        filename=filename,
        path=stored_name,
        content_type=f.mimetype,
        user_id=current_user.id,
        chat_id=chat_id if chat_id else None
    )
    db.session.add(att)
    db.session.commit()

    file_url = url_for('app_routes.serve_file', file_id=att.id, _external=False)
    return jsonify({'success': True, 'file': {
        'id': att.id,
        'filename': att.filename,
        'url': file_url,
        'content_type': att.content_type
    }}), 201


# ---------------- SERVE FILE ----------------
@app_routes.route("/files/<int:file_id>")
@login_required
def serve_file(file_id):
    att = Attachment.query.get_or_404(file_id)
    if att.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Forbidden'}), 403

    upload_dir = os.path.join(current_app.instance_path, 'uploads')
    disk_name = att.path
    return send_from_directory(upload_dir, disk_name, as_attachment=False, download_name=att.filename)


# ---------------- NEW CHAT ----------------
@app_routes.route("/new_chat", methods=["POST"])
@login_required
def new_chat():
    new_chat = Chat(name="New Chat", user_id=current_user.id, memory=json.dumps([]))
    db.session.add(new_chat)
    db.session.commit()
    return redirect(url_for("app_routes.jarvis", chat_id=new_chat.id))


# ---------------- DELETE CHAT ----------------
@app_routes.route("/delete_chat/<int:chat_id>", methods=["POST"])
@login_required
def delete_chat(chat_id):
    chat = Chat.query.get_or_404(chat_id)
    if chat.user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403

    db.session.delete(chat)
    db.session.commit()

    remaining = Chat.query.filter_by(user_id=current_user.id).all()
    if not remaining:
        new_chat = Chat(name="New Chat", user_id=current_user.id, memory=json.dumps([]))
        db.session.add(new_chat)
        db.session.commit()
        return jsonify({"redirect": url_for("app_routes.jarvis", chat_id=new_chat.id)})

    return jsonify({"redirect": url_for("app_routes.jarvis")})


# ---------------- UPLOAD CHAT FILE ----------------
@app_routes.route("/upload_chat", methods=["POST"])
@login_required
def upload_chat():
    file = request.files.get("file")
    prompt = request.form.get("prompt", "")

    if not file:
        flash("⚠️ Please select a file to upload.", "danger")
        return redirect(url_for("app_routes.jarvis"))

    file_content = read_file_content(file)
    combined_input = f"{prompt.strip()}\n\n{file_content}".strip() if prompt else file_content

    short_title = generate_chat_title(combined_input[:500], current_user.username)

    new_chat = Chat(user_id=current_user.id, name=short_title, memory=json.dumps([]))
    db.session.add(new_chat)
    db.session.commit()

    user_msg = Message(chat_id=new_chat.id, sender="user", content=combined_input)
    db.session.add(user_msg)

    reply = generate_response(combined_input, current_user.username, memory=[])
    bot_msg = Message(chat_id=new_chat.id, sender="assistant", content=reply)
    db.session.add(bot_msg)

    db.session.commit()

    return redirect(url_for("app_routes.jarvis", chat_id=new_chat.id))


# ---------------- VERIFY EMAIL (alt) ----------------
@app_routes.route("/verify/<token>")
def verify_email(token):
    user = User.verify_token(token)
    if not user:
        flash("❌ Invalid or expired verification link.", "danger")
        return redirect(url_for("app_routes.login"))

    user.is_confirmed = True
    db.session.commit()

    flash("✅ Email verified! Now set your username.", "success")
    return redirect(url_for("app_routes.set_username"))
