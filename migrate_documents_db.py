import sqlite3
import os


def migrate_documents_db():
    os.makedirs("data", exist_ok=True)

    db_path = "data/documents.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                content TEXT NOT NULL,
                tokens_count INTEGER DEFAULT 0,
                hit_count INTEGER DEFAULT 0
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                embeddings TEXT,
                strategy TEXT,
                tokens_count INTEGER DEFAULT 0,
                hit_count INTEGER DEFAULT 0,                
                FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_chunks_document_id
            ON chunks(document_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_strategy
            ON chunks(strategy)
        """)

        # Commit changes
        conn.commit()

        print(f" Database created/migrated successfully at: {db_path}")

    except Exception as e:
        conn.rollback()
        print(f" Error during migration: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_documents_db()
