from flask import Flask
from config import Config
from extensions import db, mail, login_manager
from routes import app_routes
from sqlalchemy import text

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    mail.init_app(app)
    login_manager.init_app(app)
    app.register_blueprint(app_routes)

    with app.app_context():
        from models import User, Chat, Message, Attachment
        db.create_all()

        engine = db.engine  # ✅ fixed deprecation
        with engine.connect() as conn:
            try:
                res = conn.execute(text("PRAGMA table_info('attachment')")).fetchall()
                cols = [row[1] for row in res]
                if "message_id" not in cols:
                    print("⚠️ 'message_id' missing in 'attachment'. Adding column...")
                    conn.execute(text("ALTER TABLE attachment ADD COLUMN message_id INTEGER"))
                    print("✅ Column added.")
            except Exception as e:
                print(f"⚠️ Schema check failed: {e}")

    return app

# ✅ create app at import time for gunicorn
app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
