import asyncio
import json
import websockets
import serial_asyncio
import serial.tools.list_ports

# --- Global State ---
# A set to store all connected WebSocket clients
CONNECTED_CLIENTS = set()
# A dictionary to store the latest sensor data
SENSOR_DATA = {
    "gyro_x": 0,
    "gyro_y": 0,
    "gyro_z": 0
}

def find_arduino_port():
    """Scans for serial ports and returns the device name of the first one
    that looks like an Arduino.
    """
    ports = serial.tools.list_ports.comports()
    for port in ports:
        if "Arduino" in port.description or "CH340" in port.description:
            return port.device
    return None

class ArduinoProtocol(asyncio.Protocol):
    """A protocol class to handle reading data from the Arduino.
    This runs in its own asyncio task.
    """
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
                
                # Update the global state with the angle data we care about
                if sensor_id == 0:
                    SENSOR_DATA["gyro_x"] = value
                elif sensor_id == 1:
                    SENSOR_DATA["gyro_y"] = value
                elif sensor_id == 2:
                    SENSOR_DATA["gyro_z"] = value
                
                self.high_byte = -1

    def connection_lost(self, exc):
        print("Arduino connection lost.")
        # Cause the main event loop to stop
        asyncio.get_event_loop().stop()

async def register_client(websocket):
    """Registers a new client and keeps the connection open.
    This runs for each client that connects.
    """
    CONNECTED_CLIENTS.add(websocket)
    print(f"New client connected. Total clients: {len(CONNECTED_CLIENTS)}")
    try:
        # Keep the connection open until the client disconnects
        await websocket.wait_closed()
    finally:
        CONNECTED_CLIENTS.remove(websocket)
        print(f"Client disconnected. Total clients: {len(CONNECTED_CLIENTS)}")

async def broadcast_sensor_data():
    """Broadcasts the latest sensor data to all connected clients.
    This runs in its own asyncio task.
    """
    while True:
        if CONNECTED_CLIENTS:
            # Package the data into JSON format (e.g., {"gyro_x": 512, "gyro_y": 508}).
            # JSON is a standard, structured format that is easy for web clients (JavaScript) to parse.
            message = json.dumps(SENSOR_DATA)
            # Send the message to all clients concurrently
            await asyncio.wait([client.send(message) for client in CONNECTED_CLIENTS])
        # Wait for a short period before sending the next update
        await asyncio.sleep(0.05) # ~20 updates per second

async def main(arduino_port):
    """Main function to set up and run all tasks.
    """
    # Create and start the Arduino connection task
    transport, protocol = await serial_asyncio.create_serial_connection(
        asyncio.get_event_loop(), 
        ArduinoProtocol, 
        arduino_port, 
        baudrate=38400
    )

    # Create and start the WebSocket server and data broadcasting tasks
    server = await websockets.serve(register_client, "localhost", 8767)
    broadcaster = asyncio.create_task(broadcast_sensor_data())

    print("WebSocket server started on ws://localhost:8767")
    await server.wait_closed()
    broadcaster.cancel()

if __name__ == "__main__":
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
