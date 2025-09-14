import asyncio
import json
import websockets
import serial_asyncio
import serial.tools.list_ports
import sqlite3
from datetime import datetime

# --- Database ---
DB_NAME = "sensors.db"


def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS sensor_data
                   (
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


def insert_sensor_data(session_id, x, y, z, t):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
                   INSERT INTO sensor_data (session_id, x, y, z, time)
                   VALUES (?, ?, ?, ?, ?)
                   ''', (session_id, x, y, z, t))
    conn.commit()
    conn.close()


# --- Global State ---
CONNECTED_CLIENTS = set()
SENSOR_DATA = {
    "gyro_x": 0,
    "gyro_y": 0,
    "gyro_z": 0
}
SESSION_ID = datetime.now().strftime("session_%Y%m%d_%H%M%S")  # unique ID for the session


def find_arduino_port():
    ports = serial.tools.list_ports.comports()
    for port in ports:
        if "Arduino" in port.description or "CH340" in port.description:
            return port.device
    return None


class ArduinoProtocol(asyncio.Protocol):
    high_byte = -1

    def connection_made(self, transport):
        self.transport = transport
        print("Arduino connection established.")

    def data_received(self, data):
        for current_byte in data:
            if current_byte & 0b10000000:
                self.high_byte = current_byte
            elif self.high_byte != -1:
                low_byte = current_byte
                sensor_id = (self.high_byte >> 3) & 0x0F
                value = ((self.high_byte & 0x07) << 7) | low_byte

                if sensor_id == 0:
                    SENSOR_DATA["gyro_x"] = value
                elif sensor_id == 1:
                    SENSOR_DATA["gyro_y"] = value
                elif sensor_id == 2:
                    SENSOR_DATA["gyro_z"] = value

                # --- Save to DB ---
                insert_sensor_data(
                    SESSION_ID,
                    SENSOR_DATA["gyro_x"],
                    SENSOR_DATA["gyro_y"],
                    SENSOR_DATA["gyro_z"],
                    datetime.now().isoformat()
                )

                self.high_byte = -1

    def connection_lost(self, exc):
        print("Arduino connection lost.")
        asyncio.get_event_loop().stop()


async def register_client(websocket):
    CONNECTED_CLIENTS.add(websocket)
    print(f"New client connected. Total clients: {len(CONNECTED_CLIENTS)}")
    try:
        await websocket.wait_closed()
    finally:
        CONNECTED_CLIENTS.remove(websocket)
        print(f"Client disconnected. Total clients: {len(CONNECTED_CLIENTS)}")


async def broadcast_sensor_data():
    while True:
        if CONNECTED_CLIENTS:
            message = json.dumps(SENSOR_DATA)
            await asyncio.wait([client.send(message) for client in CONNECTED_CLIENTS])
        await asyncio.sleep(0.05)


async def main(arduino_port):
    transport, protocol = await serial_asyncio.create_serial_connection(
        asyncio.get_event_loop(),
        ArduinoProtocol,
        arduino_port,
        baudrate=38400
    )

    server = await websockets.serve(register_client, "localhost", 8767)
    broadcaster = asyncio.create_task(broadcast_sensor_data())

    print("WebSocket server started on ws://localhost:8767")
    await server.wait_closed()
    broadcaster.cancel()


if __name__ == "__main__":
    init_db()  # database initialization
    print("Searching for Arduino port...")
    port = find_arduino_port()

    if port:
        print(f"Arduino found on port {port}.")
        try:
            asyncio.run(main(port))
        except KeyboardInterrupt:
            print("\nProgram stopped by user.")
    else:
        print("Error: Could not find an Arduino. Please check the connection.")
