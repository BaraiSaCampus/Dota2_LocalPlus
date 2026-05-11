from __future__ import annotations

import json
import queue
import threading
import time
import urllib.request
import ctypes
import ctypes.wintypes
import sys
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from PySide6.QtCore import QPoint, QRect, QTimer, Qt
from PySide6.QtGui import QColor, QFont, QKeySequence, QLinearGradient, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QKeySequenceEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


HOST = "127.0.0.1"
PORT = 3007
HISTORY_SECONDS = 60
BASE_WIDTH = 240
BASE_HEIGHT = 178
ITEM_SOURCE_URL = "https://raw.githubusercontent.com/odota/dotaconstants/master/build/items.json"
DEFAULT_SETTINGS = {
    "visibility_hotkey": "Ctrl+Alt+E",
    "click_through_hotkey": "Ctrl+Alt+T",
}
IN_MATCH_STATES = {
    "DOTA_GAMERULES_STATE_PRE_GAME",
    "DOTA_GAMERULES_STATE_GAME_IN_PROGRESS",
}


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def bundled_dir() -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent


ITEM_CACHE = app_dir() / "item_prices.json"
SETTINGS_FILE = app_dir() / "overlay_settings.json"


def load_settings() -> dict[str, str]:
    if SETTINGS_FILE.exists():
        try:
            loaded = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            return {**DEFAULT_SETTINGS, **{k: str(v) for k, v in loaded.items()}}
        except (OSError, json.JSONDecodeError):
            pass
    return dict(DEFAULT_SETTINGS)


def save_settings(settings: dict[str, str]) -> None:
    SETTINGS_FILE.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def format_clock(seconds: int) -> str:
    sign = "-" if seconds < 0 else ""
    seconds = abs(seconds)
    return f"{sign}{seconds // 60:02d}:{seconds % 60:02d}"


def clean_hero_name(name: str) -> str:
    name = name.replace("npc_dota_hero_", "")
    if not name:
        return "英雄"
    return " ".join(part.capitalize() for part in name.split("_"))


def normalize_item_name(name: str) -> str:
    name = name.strip()
    if name.startswith("item_"):
        name = name[5:]
    return name


def load_item_prices() -> dict[str, int]:
    for item_file in [ITEM_CACHE, bundled_dir() / "item_prices.json"]:
        if not item_file.exists():
            continue
        try:
            cached = json.loads(item_file.read_text(encoding="utf-8"))
            return {str(name): as_int(cost) for name, cost in cached.items()}
        except (OSError, json.JSONDecodeError):
            pass

    try:
        with urllib.request.urlopen(ITEM_SOURCE_URL, timeout=8) as response:
            data = json.loads(response.read().decode("utf-8"))
        prices = {
            normalize_item_name(name): as_int(details.get("cost"))
            for name, details in data.items()
            if isinstance(details, dict) and as_int(details.get("cost")) > 0
        }
        ITEM_CACHE.write_text(json.dumps(prices, ensure_ascii=False, indent=2), encoding="utf-8")
        return prices
    except Exception:
        return {}


def extract_item_names(value: Any) -> list[str]:
    names: list[str] = []

    if isinstance(value, dict):
        item_name = value.get("name")
        if isinstance(item_name, str) and item_name and item_name != "empty":
            names.append(normalize_item_name(item_name))

        for child in value.values():
            names.extend(extract_item_names(child))
    elif isinstance(value, list):
        for child in value:
            names.extend(extract_item_names(child))

    return names


VK_CODES = {
    **{chr(code): code for code in range(ord("A"), ord("Z") + 1)},
    **{str(number): ord(str(number)) for number in range(10)},
    **{f"F{number}": 0x70 + number - 1 for number in range(1, 25)},
    "SPACE": 0x20,
    "TAB": 0x09,
    "ESC": 0x1B,
    "ESCAPE": 0x1B,
    "INSERT": 0x2D,
    "DELETE": 0x2E,
    "HOME": 0x24,
    "END": 0x23,
    "PAGEUP": 0x21,
    "PAGEDOWN": 0x22,
}
MODIFIERS = {
    "ALT": 0x0001,
    "CTRL": 0x0002,
    "CONTROL": 0x0002,
    "SHIFT": 0x0004,
    "WIN": 0x0008,
    "META": 0x0008,
}


def parse_hotkey(sequence: str) -> tuple[int, int] | None:
    parts = [part.strip().upper() for part in sequence.replace(" ", "").split("+") if part.strip()]
    if not parts:
        return None

    modifiers = 0
    key = 0
    for part in parts:
        if part in MODIFIERS:
            modifiers |= MODIFIERS[part]
        elif part in VK_CODES:
            key = VK_CODES[part]
        else:
            return None

    return (modifiers, key) if key else None


class HotkeyManager:
    WM_HOTKEY = 0x0312
    WM_QUIT = 0x0012

    def __init__(self, action_queue: "queue.Queue[str]") -> None:
        self.action_queue = action_queue
        self.thread: threading.Thread | None = None
        self.thread_id = 0
        self.stop_event = threading.Event()

    def start(self, settings: dict[str, str]) -> None:
        self.stop()
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, args=(dict(settings),), daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread_id:
            ctypes.windll.user32.PostThreadMessageW(self.thread_id, self.WM_QUIT, 0, 0)
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1)
        self.thread = None
        self.thread_id = 0

    def _run(self, settings: dict[str, str]) -> None:
        user32 = ctypes.windll.user32
        self.thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        registered: list[int] = []
        hotkeys = [
            (1, settings.get("visibility_hotkey", ""), "toggle_visibility"),
            (2, settings.get("click_through_hotkey", ""), "toggle_click_through"),
        ]

        for hotkey_id, sequence, _action in hotkeys:
            parsed = parse_hotkey(sequence)
            if parsed is None:
                continue
            modifiers, key = parsed
            if user32.RegisterHotKey(None, hotkey_id, modifiers, key):
                registered.append(hotkey_id)

        msg = ctypes.wintypes.MSG()
        try:
            while not self.stop_event.is_set() and user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
                if msg.message == self.WM_HOTKEY:
                    for hotkey_id, _sequence, action in hotkeys:
                        if msg.wParam == hotkey_id:
                            self.action_queue.put(action)
                            break
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        finally:
            for hotkey_id in registered:
                user32.UnregisterHotKey(None, hotkey_id)


class SettingsDialog(QDialog):
    def __init__(self, settings: dict[str, str], parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("覆盖层设置")
        self.setModal(True)
        self.resize(360, 150)

        self.visibility_edit = QKeySequenceEdit(QKeySequence(settings["visibility_hotkey"]))
        self.click_through_edit = QKeySequenceEdit(QKeySequence(settings["click_through_hotkey"]))

        form = QFormLayout()
        form.addRow("强制隐藏/出现", self.visibility_edit)
        form.addRow("鼠标穿透", self.click_through_edit)

        reset_button = QPushButton("恢复自动显示")
        reset_button.clicked.connect(parent.clear_visibility_override)  # type: ignore[attr-defined]

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("快捷键全局生效。鼠标穿透开启后，需要用快捷键关闭穿透。"))
        layout.addLayout(form)
        layout.addWidget(reset_button)
        layout.addWidget(buttons)

    def values(self) -> dict[str, str]:
        return {
            "visibility_hotkey": self.visibility_edit.keySequence().toString(QKeySequence.NativeText),
            "click_through_hotkey": self.click_through_edit.keySequence().toString(QKeySequence.NativeText),
        }


@dataclass
class EconomyState:
    connected: bool = False
    updated_at: float = 0.0
    hero_name: str = "等待 Dota2 数据"
    game_time: int = 0
    map_state: str = "unknown"
    gold: int = 0
    reliable_gold: int = 0
    unreliable_gold: int = 0
    item_value: int = 0
    net_worth: int = 0
    unknown_items: list[str] = field(default_factory=list)
    gpm: int = 0
    xpm: int = 0
    last_hits: int = 0
    denies: int = 0
    kills: int = 0
    deaths: int = 0
    assists: int = 0
    level: int = 0
    net_worth_history: list[tuple[float, int]] = field(default_factory=list)

    def update_from_payload(self, payload: dict[str, Any], item_prices: dict[str, int]) -> None:
        now = time.time()
        player = payload.get("player") or {}
        hero = payload.get("hero") or {}
        map_data = payload.get("map") or {}

        self.connected = True
        self.updated_at = now
        self.hero_name = clean_hero_name(str(hero.get("name") or player.get("name") or "英雄"))
        self.game_time = as_int(map_data.get("clock_time"), self.game_time)
        self.map_state = str(map_data.get("game_state") or self.map_state)

        self.gold = as_int(player.get("gold"), self.gold)
        self.reliable_gold = as_int(player.get("gold_reliable"), self.reliable_gold)
        self.unreliable_gold = as_int(player.get("gold_unreliable"), self.unreliable_gold)
        self.gpm = as_int(player.get("gpm"), self.gpm)
        self.xpm = as_int(player.get("xpm"), self.xpm)
        self.last_hits = as_int(player.get("last_hits"), self.last_hits)
        self.denies = as_int(player.get("denies"), self.denies)
        self.kills = as_int(player.get("kills"), self.kills)
        self.deaths = as_int(player.get("deaths"), self.deaths)
        self.assists = as_int(player.get("assists"), self.assists)
        self.level = as_int(hero.get("level"), self.level)

        item_names = extract_item_names(payload.get("items") or {})
        self.item_value = sum(item_prices.get(name, 0) for name in item_names)
        self.unknown_items = sorted({name for name in item_names if name not in item_prices})
        self.net_worth = self.gold + self.item_value

        self.net_worth_history.append((now, self.net_worth))
        cutoff = now - HISTORY_SECONDS
        self.net_worth_history = [(ts, worth) for ts, worth in self.net_worth_history if ts >= cutoff]

    @property
    def recent_net_worth_delta(self) -> int:
        if len(self.net_worth_history) < 2:
            return 0
        return self.net_worth_history[-1][1] - self.net_worth_history[0][1]


class GSIHandler(BaseHTTPRequestHandler):
    data_queue: "queue.Queue[dict[str, Any]]"

    def do_POST(self) -> None:
        length = as_int(self.headers.get("Content-Length"))
        raw_body = self.rfile.read(length)

        try:
            payload = json.loads(raw_body.decode("utf-8"))
            self.data_queue.put(payload)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Invalid JSON")

    def log_message(self, _format: str, *_args: Any) -> None:
        return


class EconomyOverlay(QWidget):
    def __init__(self, data_queue: "queue.Queue[dict[str, Any]]", item_prices: dict[str, int]) -> None:
        super().__init__()
        self.data_queue = data_queue
        self.action_queue: "queue.Queue[str]" = queue.Queue()
        self.item_prices = item_prices
        self.settings = load_settings()
        self.hotkeys = HotkeyManager(self.action_queue)
        self.state_data = EconomyState()
        self.drag_origin: QPoint | None = None
        self.resize_origin: QPoint | None = None
        self.resize_start_geometry: QRect | None = None
        self.visibility_override = "auto"
        self.click_through = False
        self.settings_button = QRect(78, 11, 22, 22)

        self.setWindowTitle("Dota2 Economy Overlay")
        self.setGeometry(80, 80, BASE_WIDTH, BASE_HEIGHT)
        self.setMinimumSize(224, 166)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._schedule_update)
        self.timer.start(250)
        self.hotkeys.start(self.settings)

    def paintEvent(self, _event: Any) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        rect = self.rect()
        scale = max(0.75, min(rect.width() / BASE_WIDTH, rect.height() / BASE_HEIGHT))
        gradient = QLinearGradient(0, 0, rect.width(), 0)
        gradient.setColorAt(0.0, QColor(24, 26, 29, 178))
        gradient.setColorAt(0.62, QColor(66, 70, 76, 108))
        gradient.setColorAt(1.0, QColor(66, 70, 76, 0))
        painter.fillRect(rect, gradient)

        painter.setPen(QColor("#d7dee9"))
        painter.setFont(QFont("Microsoft YaHei UI", max(7, round(9 * scale)), QFont.Bold))
        painter.drawText(round(16 * scale), round(27 * scale), "\u603b\u8d44\u4ea7")

        painter.setPen(QColor(215, 222, 233, 180))
        painter.setBrush(QColor(255, 255, 255, 26))
        self.settings_button = QRect(round(78 * scale), round(11 * scale), round(22 * scale), round(22 * scale))
        painter.drawRoundedRect(self.settings_button, 5, 5)
        painter.setPen(QColor("#f8fafc"))
        painter.setFont(QFont("Segoe UI Symbol", max(8, round(11 * scale))))
        painter.drawText(self.settings_button, Qt.AlignCenter, "\u2699")

        if not self.click_through:
            handle = self.resize_handle_rect()
            painter.setPen(QColor(255, 255, 255, 150))
            painter.drawLine(handle.right() - 3, handle.bottom() - 14, handle.right() - 3, handle.bottom() - 3)
            painter.drawLine(handle.right() - 14, handle.bottom() - 3, handle.right() - 3, handle.bottom() - 3)
            painter.drawLine(handle.right() - 9, handle.bottom() - 7, handle.right() - 3, handle.bottom() - 7)

        painter.setPen(QColor("#facc15"))
        painter.setFont(QFont("Segoe UI", max(20, round(30 * scale)), QFont.Bold))
        painter.drawText(round(16 * scale), round(68 * scale), f"{self.state_data.net_worth:,}")

        painter.setPen(QColor("#e2e8f0"))
        painter.setFont(QFont("Segoe UI", max(8, round(12 * scale))))
        painter.drawText(
            round(166 * scale),
            round(49 * scale),
            round(58 * scale),
            round(24 * scale),
            Qt.AlignRight,
            format_clock(self.state_data.game_time),
        )

        painter.setFont(QFont("Microsoft YaHei UI", max(7, round(9 * scale))))
        label_color = QColor("#d1d8e3")
        value_color = QColor("#ffffff")
        rows = [
            ("\u53ef\u9760\u91d1\u94b1", f"{self.state_data.reliable_gold:,}"),
            ("\u4e0d\u53ef\u9760\u91d1\u94b1", f"{self.state_data.unreliable_gold:,}"),
            ("GPM", str(self.state_data.gpm)),
            ("XPM", str(self.state_data.xpm)),
        ]
        for index, (label, value) in enumerate(rows):
            y = round((102 + index * 21) * scale)
            painter.setPen(label_color)
            painter.drawText(round(16 * scale), y, label)
            painter.setPen(value_color)
            painter.setFont(QFont("Segoe UI", max(8, round(11 * scale)), QFont.Bold))
            painter.drawText(
                round(118 * scale),
                y - round(15 * scale),
                round(106 * scale),
                round(22 * scale),
                Qt.AlignRight,
                value,
            )
            painter.setFont(QFont("Microsoft YaHei UI", max(7, round(9 * scale))))

    def mousePressEvent(self, event: Any) -> None:
        if self.click_through:
            return
        if event.button() == Qt.LeftButton:
            if self.resize_handle_rect().contains(event.position().toPoint()):
                self.resize_origin = event.globalPosition().toPoint()
                self.resize_start_geometry = self.geometry()
                return
            if self.settings_button.contains(event.position().toPoint()):
                self.open_settings()
                return
            self.drag_origin = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event: Any) -> None:
        if self.click_through:
            return
        if self.resize_origin is not None and self.resize_start_geometry is not None and event.buttons() & Qt.LeftButton:
            delta = event.globalPosition().toPoint() - self.resize_origin
            start = self.resize_start_geometry
            min_width = self.minimumWidth()
            min_height = self.minimumHeight()
            raw_width = max(min_width, start.width() + delta.x())
            raw_height = max(min_height, start.height() + delta.y())
            scale = max(raw_width / BASE_WIDTH, raw_height / BASE_HEIGHT)
            scale = max(scale, min_width / BASE_WIDTH, min_height / BASE_HEIGHT)
            self.resize(round(BASE_WIDTH * scale), round(BASE_HEIGHT * scale))
            return
        if self.drag_origin is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_origin)
            return
        self.setCursor(Qt.SizeBDiagCursor if self.resize_handle_rect().contains(event.position().toPoint()) else Qt.ArrowCursor)

    def mouseReleaseEvent(self, _event: Any) -> None:
        self.drag_origin = None
        self.resize_origin = None
        self.resize_start_geometry = None
        self.setCursor(Qt.ArrowCursor)

    def mouseDoubleClickEvent(self, event: Any) -> None:
        if event.button() == Qt.LeftButton:
            self.close()

    def keyPressEvent(self, event: Any) -> None:
        if event.key() == Qt.Key_Escape:
            self.close()

    def resize_handle_rect(self) -> QRect:
        scale = max(0.75, min(self.width() / BASE_WIDTH, self.height() / BASE_HEIGHT))
        size = max(18, round(22 * scale))
        return QRect(max(0, self.width() - size), max(0, self.height() - size), size, size)

    def _schedule_update(self) -> None:
        while True:
            try:
                payload = self.data_queue.get_nowait()
            except queue.Empty:
                break
            self.state_data.update_from_payload(payload, self.item_prices)

        while True:
            try:
                action = self.action_queue.get_nowait()
            except queue.Empty:
                break
            if action == "toggle_visibility":
                self.toggle_visibility_override()
            elif action == "toggle_click_through":
                self.set_click_through(not self.click_through)

        self.apply_visibility()
        self.update()

    def is_in_match(self) -> bool:
        if not self.state_data.connected:
            return False
        if time.time() - self.state_data.updated_at > 5:
            return False
        return self.state_data.map_state in IN_MATCH_STATES

    def apply_visibility(self) -> None:
        should_show = self.is_in_match()
        if self.visibility_override == "hidden":
            should_show = False
        elif self.visibility_override == "shown":
            should_show = True

        if should_show and not self.isVisible():
            self.show()
            self.raise_()
        elif not should_show and self.isVisible():
            self.hide()

    def toggle_visibility_override(self) -> None:
        if self.isVisible():
            self.visibility_override = "hidden"
            self.hide()
        else:
            self.visibility_override = "shown"
            self.show()
            self.raise_()

    def clear_visibility_override(self) -> None:
        self.visibility_override = "auto"
        self.apply_visibility()

    def set_click_through(self, enabled: bool) -> None:
        self.click_through = enabled
        self.setWindowFlag(Qt.WindowTransparentForInput, enabled)
        if self.visibility_override == "hidden":
            return
        self.show()
        self.raise_()

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec() != QDialog.Accepted:
            return
        self.settings = {**self.settings, **dialog.values()}
        save_settings(self.settings)
        self.hotkeys.start(self.settings)

    def closeEvent(self, event: Any) -> None:
        self.hotkeys.stop()
        super().closeEvent(event)


def start_server(data_queue: "queue.Queue[dict[str, Any]]") -> ThreadingHTTPServer:
    GSIHandler.data_queue = data_queue
    server = ThreadingHTTPServer((HOST, PORT), GSIHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def main() -> None:
    data_queue: "queue.Queue[dict[str, Any]]" = queue.Queue()
    item_prices = load_item_prices()
    server = start_server(data_queue)
    try:
        qt_app = QApplication([])
        overlay = EconomyOverlay(data_queue, item_prices)
        overlay.show()
        qt_app.exec()
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
