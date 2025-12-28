import sys
import time
import uuid
import hashlib
import requests
import mss
import keyboard
import queue

from PySide6.QtWidgets import QApplication, QWidget, QTextEdit
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont

# -------------------------------------------------
# MACHINE UNIQUE ID
# -------------------------------------------------
def get_machine_id():
    raw = str(uuid.getnode())
    return hashlib.sha256(raw.encode()).hexdigest()

MACHINE_ID = get_machine_id()
print("DEVICE ID:", MACHINE_ID)

# -------------------------------------------------
# BACKEND URLS
# -------------------------------------------------
VERIFY_URL = "http://127.0.0.1:8000/verify"
AI_URL = "http://127.0.0.1:8000/analyze"

def verify_machine():
    r = requests.post(VERIFY_URL, json={"machine_id": MACHINE_ID}, timeout=5)
    return r.json().get("allowed", False)

if not verify_machine():
    sys.exit("Machine not authorized")

# -------------------------------------------------
# HOTKEYS
# -------------------------------------------------
SCREENSHOT_KEY = "ctrl+shift+z"
TOGGLE_KEY = "m"

# -------------------------------------------------
# SCREENSHOT
# -------------------------------------------------
def take_screenshot():
    with mss.mss() as sct:
        name = f"snap_{int(time.time())}.png"
        sct.shot(output=name)
        return name

# -------------------------------------------------
# SEND TO AI
# -------------------------------------------------
def send_to_ai(image_path):
    with open(image_path, "rb") as img:
        r = requests.post(
            AI_URL,
            files={"image": img},
            data={"machine_id": MACHINE_ID},
            timeout=30
        )
    return r.json().get("answer", "")

# -------------------------------------------------
# THREAD-SAFE QUEUE
# -------------------------------------------------
ui_queue = queue.Queue()

# -------------------------------------------------
# POPUP UI
# -------------------------------------------------
class AnswerOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.resize(300, 180)

        screen = QApplication.primaryScreen().availableGeometry()
        x = (screen.width() - self.width()) // 2
        y = screen.height() - self.height() - 80
        self.move(x, y)

        self.setStyleSheet("""
            QWidget { background-color: rgba(0,0,0,220); border-radius: 8px; }
        """)

        self.text = QTextEdit(self)
        self.text.setGeometry(10, 10, 280, 160)
        self.text.setReadOnly(True)
        self.text.setFont(QFont("Segoe UI", 10))
        self.text.setStyleSheet("color:white; background:transparent;")

# -------------------------------------------------
# QT APP START
# -------------------------------------------------
app = QApplication(sys.argv)

overlay = AnswerOverlay()
overlay.hide()

visible = False
last_answer = ""

# -------------------------------------------------
# QUEUE PROCESSOR (QT THREAD)
# -------------------------------------------------
def process_ui_queue():
    global visible
    while not ui_queue.empty():
        action = ui_queue.get()
        if action == "TOGGLE":
            if visible:
                overlay.hide()
            else:
                overlay.text.setText(last_answer or "No answer yet")
                overlay.show()
                overlay.raise_()
                overlay.activateWindow()
            visible = not visible

# -------------------------------------------------
# HOTKEY CALLBACKS (NON-UI THREAD)
# -------------------------------------------------
def on_screenshot():
    global last_answer
    img = take_screenshot()
    last_answer = send_to_ai(img)

def on_toggle():
    ui_queue.put("TOGGLE")

keyboard.add_hotkey(SCREENSHOT_KEY, on_screenshot)
keyboard.add_hotkey(TOGGLE_KEY, on_toggle)

# -------------------------------------------------
# TIMER TO PROCESS QUEUE
# -------------------------------------------------
timer = QTimer()
timer.timeout.connect(process_ui_queue)
timer.start(100)

sys.exit(app.exec())