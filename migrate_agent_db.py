import sqlite3
import os

DB_PATH = "data/agent.db"

def migrate():
    """
    Create agent_threads and agent_turns tables if they don't exist.
    Only runs if data/agent.db doesn't exist yet.
    """

    # Check if database already exists
    if os.path.exists(DB_PATH):
        print(f"Database {DB_PATH} already exists. Skipping migration.")
        return

    print(f"Creating database {DB_PATH}...")

    # Ensure data directory exists
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    # Create connection and tables
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Create agent_threads table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_threads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id TEXT NOT NULL,
                user_id INTEGER NOT NULL
            )
        """)

        # Create indexes for agent_threads
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_agent_threads_thread_id
            ON agent_threads(thread_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_agent_threads_user_id
            ON agent_threads(user_id)
        """)

        # Create agent_turns table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_turns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                input TEXT,
                output TEXT,
                raw_items TEXT,
                metadata TEXT
            )
        """)

        # Create indexes for agent_turns
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_agent_turns_thread_id
            ON agent_turns(thread_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_agent_turns_user_id
            ON agent_turns(user_id)
        """)

        conn.commit()
        print("Migration completed successfully!")
        print("Created tables:")
        print("  - agent_threads (with indexes on thread_id, user_id)")
        print("  - agent_turns (with indexes on thread_id, user_id)")

    except Exception as e:
        conn.rollback()
        print(f"Error during migration: {e}")
        raise

    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
