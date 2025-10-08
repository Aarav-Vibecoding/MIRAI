# app.py
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

    # Register Blueprints
    app.register_blueprint(app_routes)

    with app.app_context():
        from models import User, Chat, Message, Attachment
        db.create_all()

        # --- Auto schema check & fix ---
        engine = db.engine  # ✅ updated to new API (no DeprecationWarning)
        with engine.connect() as conn:
            res = conn.execute(text("PRAGMA table_info('attachment')")).fetchall()
            cols = [row[1] for row in res]  # row[1] is the column name
            if "message_id" not in cols:
                print("⚠️ 'message_id' missing in 'attachment'. Adding column automatically...")
                conn.execute(text("ALTER TABLE attachment ADD COLUMN message_id INTEGER"))
                print("✅ Column 'message_id' added.")

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
