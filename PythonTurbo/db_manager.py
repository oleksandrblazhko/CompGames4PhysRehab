import sqlite3
from datetime import datetime

DB_NAME = "sensors.db"

def init_db():
    """Створює бази даних і таблиці, якщо їх нема"""
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
                       calib_x REAL NOT NULL,
                       calib_y REAL NOT NULL,
                       time TIMESTAMP NOT NULL)''')
    conn.commit()
    conn.close()

def insert_sensor_data(session_id, x, y, z):
    """Вставляє дані з Arduino в таблицю sensor_data"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO sensor_data (session_id, x, y, z, time) VALUES (?,?,?,?,?)',
                   (session_id, x, y, z, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def insert_calibration(calib_x, calib_y):
    """Зберігає значення калібровки в таблицю calibration"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO calibration (calib_x, calib_y, time) VALUES (?,?,?)',
                   (calib_x, calib_y, datetime.now().isoformat()))
    conn.commit()
    conn.close()
