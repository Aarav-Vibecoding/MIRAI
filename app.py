from flask import Flask
from config import Config
from extensions import db, mail, login_manager
from routes import app_routes
from sqlalchemy import text


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize extensions
    db.init_app(app)
    mail.init_app(app)
    login_manager.init_app(app)

    # Register routes
    app.register_blueprint(app_routes)

    # Database initialization and schema patch
    with app.app_context():
        from models import User, Chat, Message, Attachment
        db.create_all()

        # --- Auto schema check & fix (Render safe) ---
        engine = db.engine  # ✅ updated: .get_engine() is deprecated
        with engine.connect() as conn:
            try:
                res = conn.execute(text("PRAGMA table_info('attachment')")).fetchall()
                cols = [row[1] for row in res]
                if "message_id" not in cols:
                    print("⚠️  'message_id' missing in 'attachment'. Adding column automatically...")
                    conn.execute(text("ALTER TABLE attachment ADD COLUMN message_id INTEGER"))
                    print("✅  Column 'message_id' added.")
            except Exception as e:
                print(f"⚠️  Schema check failed: {e}")

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)
