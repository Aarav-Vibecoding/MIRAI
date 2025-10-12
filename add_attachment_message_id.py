# scripts/add_attachment_message_id.py
from app import create_app
from extensions import db
from sqlalchemy import text

def main():
    app = create_app()
    with app.app_context():
        engine = db.get_engine()  # get SQLAlchemy engine

        # Check existing columns using SQLite PRAGMA
        with engine.connect() as conn:
            res = conn.execute(text("PRAGMA table_info('attachment')")).fetchall()
            cols = [row[1] for row in res]  # row: (cid, name, type, notnull, dflt_value, pk)
            if 'message_id' in cols:
                print("✅ Column 'message_id' already exists in table 'attachment'. Nothing to do.")
                return

        # Add the column
        print("Adding column 'message_id' to 'attachment' table...")
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE attachment ADD COLUMN message_id INTEGER"))
        print("✅ Done. 'message_id' column added successfully. Restart your Flask app now.")

if __name__ == "__main__":
    main()
