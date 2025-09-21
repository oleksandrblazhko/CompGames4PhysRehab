import sqlite3
from datetime import datetime

DB_NAME = "sensors.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS sensor_data
                      (id INTEGER PRIMARY KEY AUTOINCREMENT,
                       session_id TEXT NOT NULL,
                       x REAL NOT NULL,
                       y REAL NOT NULL,
                       z REAL NOT NULL,
                       time TIMESTAMP NOT NULL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS calibration
                      (id INTEGER PRIMARY KEY AUTOINCREMENT,
                       session_id TEXT NOT NULL,
                       calib_x REAL NOT NULL,
                       calib_y REAL NOT NULL,
                       time TIMESTAMP NOT NULL)''')
    conn.commit()
    conn.close()

def insert_sensor_data(session_id, x, y, z):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO sensor_data (session_id, x, y, z, time) VALUES (?,?,?,?,?)',
                   (session_id, x, y, z, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def insert_calibration(calib_x, calib_y, session_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO calibration (session_id, calib_x, calib_y, time) VALUES (?,?,?,?)',
                   (session_id, calib_x, calib_y, datetime.now().isoformat()))
    conn.commit()
    conn.close()
