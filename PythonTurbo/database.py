import sqlite3

DB_NAME = "sensors.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS sensor_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        x REAL NOT NULL,
        y REAL NOT NULL,
        z REAL NOT NULL,
        time TIMESTAMP NOT NULL
    )
    ''')

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("The database and table have been created.")
