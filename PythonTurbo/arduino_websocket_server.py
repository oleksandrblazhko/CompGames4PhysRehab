import asyncio
import json
import websockets
import serial_asyncio
import serial.tools.list_ports
import threading
import tkinter as tk
import time
from datetime import datetime
import sqlite3
from db_manager import init_db, insert_sensor_data, insert_calibration, DB_NAME

# --- Глобальні змінні ---
CONNECTED_CLIENTS = set()
SENSOR_DATA = {"gyro_x": 0, "gyro_y": 0, "gyro_z": 0}
SESSION_ID = datetime.now().strftime("session_%Y%m%d_%H%M%S")
CALIB_X, CALIB_Y = 512, 512
ARDUINO_CONNECTED = False
arduino_transport = None
arduino_protocol = None

# --- Завантаження останнього калібрування ---
def load_last_calibration():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT calib_x, calib_y FROM calibration ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    if row:
        return row[0], row[1]
    return 512, 512

# --- Пошук Arduino ---
def find_arduino_port():
    ports = serial.tools.list_ports.comports()
    for port in ports:
        if "Arduino" in port.description or "CH340" in port.description:
            return port.device
    return None

# --- Arduino Protocol ---
class ArduinoProtocol(asyncio.Protocol):
    def __init__(self):
        self.high_byte = -1
        self.last_db_write = time.time()

    def connection_made(self, transport):
        global ARDUINO_CONNECTED
        self.transport = transport
        ARDUINO_CONNECTED = True
        print("Arduino під'єднано")

    def data_received(self, data):
        global SENSOR_DATA
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

                if time.time() - self.last_db_write >= 0.05:
                    asyncio.get_event_loop().call_soon_threadsafe(
                        insert_sensor_data, SESSION_ID,
                        SENSOR_DATA["gyro_x"], SENSOR_DATA["gyro_y"], SENSOR_DATA["gyro_z"]
                    )
                    self.last_db_write = time.time()

                self.high_byte = -1

    def connection_lost(self, exc):
        global ARDUINO_CONNECTED
        ARDUINO_CONNECTED = False
        print("Arduino від'єднано")

# --- Запуск asyncio loop для Arduino ---
def run_async_loop(port):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(serial_asyncio.create_serial_connection(
            loop, ArduinoProtocol, port, baudrate=38400
        ))
    except Exception as e:
        print(f"Помилка з'єднання Arduino: {e}")
    loop.run_forever()

# --- WebSocket ---
async def register_client(ws):
    CONNECTED_CLIENTS.add(ws)
    try:
        await ws.wait_closed()
    finally:
        CONNECTED_CLIENTS.remove(ws)

async def broadcast():
    while True:
        if CONNECTED_CLIENTS:
            msg = json.dumps(SENSOR_DATA)
            await asyncio.wait([c.send(msg) for c in CONNECTED_CLIENTS])
        await asyncio.sleep(0.05)

async def start_websocket_server():
    server = await websockets.serve(register_client, "localhost", 8767)
    print("WebSocket сервер запущено")
    await broadcast()  # постійне надсилання даних

def run_websocket_server():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_websocket_server())

# --- GUI ---
def create_hover_button(parent, text, font, bg, fg, hover_bg, active_bg, active_fg, width, height, command):
    btn = tk.Button(parent, text=text, font=font, bg=bg, fg=fg,
                    activebackground=active_bg, activeforeground=active_fg,
                    width=width, height=height, command=command, relief="raised", bd=3)
    btn.pack(pady=15)

    def on_enter(e):
        btn['bg'] = hover_bg
    def on_leave(e):
        btn['bg'] = bg

    btn.bind("<Enter>", on_enter)
    btn.bind("<Leave>", on_leave)
    return btn

class BalanceApp:
    def __init__(self, root):
        global CALIB_X, CALIB_Y
        self.root = root
        self.root.title("Rehab Balance")
        self.root.state('zoomed')
        self.root.configure(bg="#f0f2f5")

        self.player_speed_factor = 0.2
        self.enemy_speed_factor = 0.15
        self.enemy_speed_min = 0.05
        self.last_catch_time = time.time()
        self.optimal_wait = 5
        self.server_thread = None
        self.websocket_running = False  # статус серверу

        self.title_font = ("Segoe UI", 20, "bold")
        self.button_font = ("Segoe UI", 16)
        self.label_font = ("Segoe UI", 14)

        # --- Панель ---
        control_frame = tk.Frame(root, bg="#e6e6e6", padx=100, pady=50)
        control_frame.pack(expand=True)

        self.server_status_label = tk.Label(control_frame, text="Server: не запущено", font=self.title_font,
                                            bg="#e6e6e6", fg="#333333")
        self.server_status_label.pack(pady=(0,10))

        self.status_label = tk.Label(control_frame, text="Arduino не під'єднано", font=self.label_font,
                                     bg="#e6e6e6", fg="#555555")
        self.status_label.pack(pady=(0,10))

        self.port_label = tk.Label(control_frame, text="Порт: N/A", font=self.label_font,
                                   bg="#e6e6e6", fg="#555555")
        self.port_label.pack(pady=(0,25))

        # --- Кнопки ---
        create_hover_button(control_frame, "⚡ Запустити/Перезапустити сервер", self.button_font,
                            "#4caf50", "white", "#45a049", "#388e3c", "white", 30, 2, self.start_server)
        create_hover_button(control_frame, "⚙ Калібрування", self.button_font,
                            "#2196f3", "white", "#1976d2", "#1565c0", "white", 30, 2, self.calibration_window)
        create_hover_button(control_frame, "🎮 Гра: Баланс", self.button_font,
                            "#ff5722", "white", "#e64a19", "#d84315", "white", 30, 2, self.start_game)

        # --- Рух ---
        self.target_x = 0
        self.target_y = 0
        self.player_vel_x = 0
        self.player_vel_y = 0
        self.smoothing_factor = 0.3

        self.root.after(500, self.update_status_labels)  # постійне оновлення статусів
        self.monitor_arduino()  # Запуск моніторингу одразу

    def monitor_arduino(self):
        global ARDUINO_CONNECTED
        port = find_arduino_port()

        if port:
            if not ARDUINO_CONNECTED:
                print(f"[Моніторинг] Arduino знайдено на {port}, під'єднання...")
                threading.Thread(target=run_async_loop, args=(port,), daemon=True).start()
                ARDUINO_CONNECTED = True
                self.status_label.config(text=f"Arduino під'єднано")
                self.port_label.config(text=f"Порт: {port}")
        else:
            if ARDUINO_CONNECTED:
                print("[Моніторинг] Arduino від'єднано")
                ARDUINO_CONNECTED = False
                self.status_label.config(text="Arduino від'єднано")
                self.port_label.config(text="Порт: N/A")

        # Перевіряти кожну секунду
        self.root.after(1000, self.monitor_arduino)

    def start_server(self):
        port = find_arduino_port()
        if not port:
            self.status_label.config(text="Arduino не під'єднано")
            self.port_label.config(text="Порт: N/A")
            print("Arduino не знайдено")
            return
        if self.server_thread and self.server_thread.is_alive():
            print("Перезапуск сервера...")
        self.server_thread = threading.Thread(target=self.run_servers, args=(port,), daemon=True)
        self.server_thread.start()

    def run_servers(self, port):
        global ARDUINO_CONNECTED, WEBSOCKET_RUNNING
        # Запуск Arduino loop
        threading.Thread(target=run_async_loop, args=(port,), daemon=True).start()
        ARDUINO_CONNECTED = True
        # Запуск WebSocket
        WEBSOCKET_RUNNING = True
        self.websocket_running = True
        run_websocket_server()  # виклик, який блокує

    def update_status_labels(self):
        # Оновлення статусу Arduino
        port = find_arduino_port()
        if port and ARDUINO_CONNECTED:
            self.status_label.config(text=f"Arduino під'єднано")
            self.port_label.config(text=f"Порт: {port}")
        else:
            self.status_label.config(text="Arduino не під'єднано")
            self.port_label.config(text="Порт: N/A")

        # Оновлення статусу сервера
        server_text = "Server: запущено" if self.websocket_running else "Server: не запущено"
        self.server_status_label.config(text=server_text)

        self.root.after(500, self.update_status_labels)

    def calibration_window(self):
        global CALIB_X, CALIB_Y, SESSION_ID
        win = tk.Toplevel(self.root)
        win.title("Калібрування")
        win.geometry("400x200")
        tk.Label(win, text="Тримайте дошку декілька секунд \n горизонтально у нерухомому стані",
                 font=("Arial", 12)).pack(pady=20)
        countdown = tk.Label(win, text="", font=("Arial", 24))
        countdown.pack(pady=20)

        def run_count():
            for i in range(3, 0, -1):
                countdown.config(text=str(i))
                win.update()
                threading.Event().wait(1)
            # Оновлюємо глобальні змінні
            CALIB_X = SENSOR_DATA["gyro_x"]
            CALIB_Y = SENSOR_DATA["gyro_y"]
            # Зберігаємо в БД з session_id
            insert_calibration(CALIB_X, CALIB_Y, SESSION_ID)
            print(f"[Калібрування] X={CALIB_X}, Y={CALIB_Y}, Session={SESSION_ID}")
            win.destroy()

        threading.Thread(target=run_count, daemon=True).start()

    def start_game(self):
        global CALIB_X, CALIB_Y, SESSION_ID
        # Завантажуємо останнє калібрування
        CALIB_X, CALIB_Y = load_last_calibration()
        # Скидання швидкості ворога до базової
        self.enemy_speed_factor = 0.15
        self.game_win = tk.Toplevel(self.root)
        self.game_win.title("Гра: Баланс")
        self.game_win.state('zoomed')
        self.canvas = tk.Canvas(self.game_win, bg="white")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.player = self.canvas.create_oval(100, 200, 140, 240, fill="blue")
        self.enemy = self.canvas.create_oval(400, 200, 440, 240, fill="red")
        self.speed_label = tk.Label(self.game_win, text="", font=("Arial", 14))
        self.speed_label.pack()
        self.opt_label = tk.Label(self.game_win, text="", font=("Arial", 14))
        self.opt_label.pack()
        # Гра може стартувати одразу після калібрування
        self.game_started = True
        self.game_loop()

    def game_loop(self):
        px1, py1, px2, py2 = self.canvas.coords(self.player)
        ex1, ey1, ex2, ey2 = self.canvas.coords(self.enemy)

        if ARDUINO_CONNECTED:
            self.target_x = (SENSOR_DATA["gyro_y"] - CALIB_Y) * self.player_speed_factor
            self.target_y = (SENSOR_DATA["gyro_x"] - CALIB_X) * self.player_speed_factor
        else:
            self.target_x = 0
            self.target_y = 0

        self.player_vel_x += (self.target_x - self.player_vel_x) * self.smoothing_factor
        self.player_vel_y += (self.target_y - self.player_vel_y) * self.smoothing_factor

        new_px1 = max(0, min(px1 + self.player_vel_x, self.canvas.winfo_width() - (px2 - px1)))
        new_py1 = max(0, min(py1 + self.player_vel_y, self.canvas.winfo_height() - (py2 - py1)))
        self.canvas.coords(self.player, new_px1, new_py1, new_px1 + (px2 - px1), new_py1 + (py2 - py1))

        new_ex1 = max(0, min(ex1 + (new_px1 - ex1) * self.enemy_speed_factor,
                             self.canvas.winfo_width() - (ex2 - ex1)))
        new_ey1 = max(0, min(ey1 + (new_py1 - ey1) * self.enemy_speed_factor,
                             self.canvas.winfo_height() - (ey2 - ey1)))
        self.canvas.coords(self.enemy, new_ex1, new_ey1, new_ex1 + (ex2 - ex1), new_ey1 + (ey2 - ey1))

        # Логіка «піймав гравця» лише після старту
        if hasattr(self, 'game_started'):
            caught = abs(new_px1 - new_ex1) < 40 and abs(new_py1 - new_ey1) < 40
            if caught:
                self.canvas.coords(self.player, 100, self.canvas.winfo_height() // 2, 140,
                                   self.canvas.winfo_height() // 2 + 40)
                self.canvas.coords(self.enemy, self.canvas.winfo_width() - 140, self.canvas.winfo_height() // 2,
                                   self.canvas.winfo_width() - 100, self.canvas.winfo_height() // 2 + 40)
                self.enemy_speed_factor = max(self.enemy_speed_min, self.enemy_speed_factor * 0.9)
                self.last_catch_time = time.time()
        else:
            # Позначаємо, що гра вже стартувала і перші координати пройшли
            self.game_started = True

        self.speed_label.config(text=f"Швидкість ворога: {self.enemy_speed_factor:.2f}")
        if time.time() - self.last_catch_time >= self.optimal_wait:
            self.opt_label.config(text="Швидкість оптимальна")
        else:
            self.opt_label.config(text="")

        self.game_win.after(20, self.game_loop)

# --- Точка входу ---
if __name__ == "__main__":
    init_db()
    root = tk.Tk()
    app = BalanceApp(root)
    # Запуск WebSocket серверу в окремому потоці
    threading.Thread(target=run_websocket_server, daemon=True).start()
    root.mainloop()
