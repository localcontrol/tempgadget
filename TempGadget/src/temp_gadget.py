import ctypes
import glob
import json
import math
import os
import subprocess
import sys
import threading
from collections import deque
from pathlib import Path

import clr
from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (QAction, QActionGroup, QColor, QFont, QIcon,
                           QBrush, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap)
from PySide6.QtWidgets import (QApplication, QCheckBox, QDialog, QDialogButtonBox, QLabel,
                               QMenu, QMessageBox, QSystemTrayIcon, QVBoxLayout, QWidget)

BASE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
LIBS = os.path.join(BASE, "libs")
sys.path.append(LIBS)
clr.AddReference(os.path.join(LIBS, "LibreHardwareMonitorLib.dll"))

from LibreHardwareMonitor.Hardware import Computer, HardwareType, SensorType

CPU_PREF = ("CPU Package", "Core (Tctl/Tdie)", "Core (Tdie)", "CPU Total")
GPU_PREF = ("GPU Core",)
GPU_TYPES = {HardwareType.GpuNvidia, HardwareType.GpuAmd, HardwareType.GpuIntel}
CFG_FILE = Path(os.getenv("APPDATA", ".")) / "TempGadget" / "config.json"
METRICS = {  # key: label, kind (temp = degrees C, load = percent)
    "CPU": dict(label="CPU", kind="temp", title="CPU: температура"),
    "GPU": dict(label="GPU", kind="temp", title="GPU: температура"),
    "LOAD": dict(label="CPU %", kind="load", title="CPU: загрузка"),
    "GPUL": dict(label="GPU %", kind="load", title="GPU: загрузка"),
    "RAM": dict(label="ОЗУ", kind="load", title="ОЗУ: занято"),
}
DEFAULT_SHOW = ["CPU", "LOAD", "RAM"]
T_MIN, T_MAX = 20, 100
HISTORY = 60
SCALE_MIN, SCALE_MAX = 0.2, 1.0

THEMES = {
    "Glass": dict(
        font="Segoe UI", glow=False,
        bg=(20, 22, 30, 210), border=(255, 255, 255, 35),
        text=(245, 246, 250), dim=(140, 146, 165), track=(255, 255, 255, 26),
        stops=[(30, (56, 189, 248)), (55, (74, 222, 128)),
               (70, (250, 204, 21)), (85, (248, 113, 113))]),
    "Neon": dict(
        font="Segoe UI", glow=True,
        bg=(10, 8, 24, 230), border=(255, 0, 200, 120),
        text=(240, 240, 255), dim=(130, 120, 180), track=(255, 255, 255, 20),
        stops=[(30, (0, 229, 255)), (60, (180, 80, 255)),
               (80, (255, 0, 200)), (95, (255, 60, 90))]),
    "Minimal": dict(
        font="Segoe UI", glow=False,
        bg=(250, 250, 252, 235), border=(0, 0, 0, 25),
        text=(28, 28, 34), dim=(120, 120, 135), track=(0, 0, 0, 15),
        stops=[(30, (59, 130, 246)), (55, (34, 197, 94)),
               (70, (245, 158, 11)), (85, (239, 68, 68))]),
    "Retro": dict(
        font="Consolas", glow=True,
        bg=(14, 10, 4, 235), border=(255, 176, 0, 90),
        text=(255, 190, 40), dim=(160, 110, 20), track=(255, 176, 0, 30),
        stops=[(30, (255, 176, 0)), (70, (255, 140, 0)), (85, (255, 80, 0))]),
    "Aurora": dict(
        font="Segoe UI", glow=False,
        bg=(15, 23, 42, 215), border=(255, 255, 255, 30),
        text=(241, 245, 249), dim=(148, 163, 184), track=(255, 255, 255, 22),
        stops=[(30, (45, 212, 191)), (60, (96, 165, 250)),
               (80, (167, 139, 250)), (95, (244, 114, 182))]),
    "Matrix": dict(
        font="Consolas", glow=False,
        bg=(0, 8, 0, 235), border=(0, 255, 70, 90),
        text=(0, 255, 70), dim=(0, 140, 40), track=(0, 255, 70, 25),
        stops=[(30, (0, 255, 70)), (70, (180, 255, 0)),
               (85, (255, 200, 0)), (95, (255, 60, 40))]),
    "Cyberpunk": dict(
        font="Consolas", glow=True,
        bg=(13, 2, 33, 235), border=(255, 230, 0, 150),
        text=(0, 240, 255), dim=(190, 120, 255), track=(255, 230, 0, 28),
        stops=[(30, (0, 240, 255)), (60, (255, 230, 0)),
               (80, (255, 0, 128)), (95, (255, 40, 40))]),
    "Sunset": dict(
        font="Segoe UI", glow=False,
        bg=(38, 16, 40, 220), border=(255, 160, 120, 70),
        text=(255, 240, 235), dim=(200, 150, 165), track=(255, 255, 255, 24),
        stops=[(30, (253, 224, 71)), (55, (251, 146, 60)),
               (75, (244, 63, 94)), (95, (190, 24, 93))]),
    "Ocean": dict(
        font="Segoe UI", glow=False,
        bg=(6, 30, 48, 220), border=(125, 211, 252, 70),
        text=(224, 242, 254), dim=(125, 160, 190), track=(255, 255, 255, 22),
        stops=[(30, (34, 211, 238)), (60, (56, 189, 248)),
               (80, (129, 140, 248)), (95, (251, 113, 133))]),
    "Sakura": dict(
        font="Segoe UI", glow=False,
        bg=(255, 241, 245, 235), border=(244, 114, 182, 80),
        text=(80, 30, 55), dim=(170, 110, 140), track=(244, 114, 182, 38),
        stops=[(30, (244, 114, 182)), (60, (232, 121, 249)),
               (80, (251, 146, 60)), (95, (239, 68, 68))]),
    "OLED": dict(
        font="Segoe UI", glow=False,
        bg=(0, 0, 0, 245), border=(255, 255, 255, 55),
        text=(255, 255, 255), dim=(115, 115, 115), track=(255, 255, 255, 20),
        stops=[(30, (255, 255, 255)), (60, (190, 190, 190)),
               (80, (255, 170, 60)), (95, (255, 70, 70))]),
    "Frost": dict(
        font="Segoe UI", glow=False,
        bg=(226, 240, 255, 205), border=(255, 255, 255, 170),
        text=(15, 40, 70), dim=(90, 115, 150), track=(15, 40, 70, 22),
        stops=[(30, (14, 165, 233)), (55, (20, 184, 166)),
               (75, (245, 158, 11)), (95, (239, 68, 68))]),
    "Inferno": dict(
        font="Segoe UI", glow=True,
        bg=(20, 4, 2, 235), border=(255, 90, 20, 140),
        text=(255, 238, 220), dim=(190, 110, 80), track=(255, 120, 40, 28),
        stops=[(30, (255, 214, 10)), (55, (255, 150, 0)),
               (75, (255, 70, 0)), (95, (255, 20, 40))]),
    "Vapor": dict(
        font="Segoe UI", glow=True,
        bg=(28, 10, 60, 230), border=(255, 113, 206, 140),
        text=(255, 240, 255), dim=(185, 150, 230), track=(255, 255, 255, 24),
        stops=[(30, (1, 205, 254)), (55, (5, 255, 161)), (75, (255, 251, 150)),
               (90, (255, 113, 206)), (100, (255, 60, 120))]),
}
# second colour of the diagonal background gradient
BG2 = {
    "Glass": (38, 42, 64, 215), "Neon": (36, 6, 60, 235), "Aurora": (40, 30, 90, 220),
    "Cyberpunk": (45, 4, 70, 238), "Sunset": (78, 24, 62, 225), "Ocean": (4, 66, 98, 225),
    "Matrix": (0, 28, 6, 238), "Retro": (40, 22, 2, 238), "Sakura": (255, 222, 236, 238),
    "Frost": (190, 215, 245, 210), "Inferno": (80, 8, 4, 238), "Vapor": (80, 15, 100, 232),
}
LAYOUTS = {  # name: (draw style, base size for two cells)
    "Компакт": ("compact", (168, 104)),
    "Спидометр": ("gauge", (340, 190)),
    "Спидометр + t°": ("dial", (300, 150)),
    "Жидкость": ("liquid", (300, 150)),
    "Строка": ("line", (300, 50)),
    "Кольца": ("rings", (300, 160)),
    "Дуги": ("arc", (320, 150)),
    "Полосы": ("bars", (280, 120)),
    "Цифры": ("numbers", (240, 100)),
    "График": ("spark", (300, 130)),
}
DIAL_SMALL = 0.7  # size of the 2nd, 3rd... dial relative to the first
STACKED = ("bars", "spark")  # cell is a full-width row (default orientation: vertical)
# px, or fraction of height if < 1, or "cut" for chamfered corners
SHAPES = {"Квадрат": 4, "Мягкая": 20, "Круглая": 0.32, "Таблетка": 0.5, "Скос": "cut"}
SCALES = (20, 30, 40, 50, 60, 70, 80, 90, 100)
OPACITIES = (100, 85, 70)
PRESETS = {  # one-click combos
    "Реактор": dict(theme="Cyberpunk", layout="Спидометр", shape="Скос"),
    "Аквариум": dict(theme="Ocean", layout="Жидкость", shape="Круглая"),
    "Инферно": dict(theme="Inferno", layout="Спидометр", shape="Мягкая"),
    "Vaporwave": dict(theme="Vapor", layout="Жидкость", shape="Мягкая"),
    "Стелс": dict(theme="OLED", layout="Строка", shape="Таблетка"),
    "Сакура": dict(theme="Sakura", layout="Дуги", shape="Мягкая"),
    "Спидометры (как 8GadgetPack)": dict(theme="Glass", layout="Спидометр + t°", shape="Мягкая",
                                         show=["CPU", "LOAD", "RAM"]),
    "Компакт (как 8GadgetPack)": dict(theme="Glass", layout="Компакт", shape="Мягкая",
                                      show=["CPU", "LOAD", "GPU", "GPUL", "RAM"]),
}
DEFAULTS = dict(theme="Glass", layout="Спидометр + t°", shape="Мягкая", scale=1.0, opacity=100, ontop=True,
                show=DEFAULT_SHOW)

pc = Computer()
pc.IsCpuEnabled = True
pc.IsGpuEnabled = True
pc.IsStorageEnabled = True
pc.Open()

# every drive with a temperature sensor becomes its own optional metric
for _hw in pc.Hardware:
    if _hw.HardwareType == HardwareType.Storage:
        _hw.Update()
        if any(s.SensorType == SensorType.Temperature for s in _hw.Sensors):
            _name = str(_hw.Name)
            METRICS["DSK:" + _name] = dict(label=_name.split()[0][:7].upper(), kind="temp",
                                           title="Диск: " + _name)


def pick(hw, prefs):
    temps = [s for s in hw.Sensors
             if s.SensorType == SensorType.Temperature and s.Value is not None]
    for name in prefs:
        for s in temps:
            if s.Name == name and s.Value > 0:
                return float(s.Value)
    vals = [float(s.Value) for s in temps if s.Value > 0]
    return max(vals, default=None)


class MEMSTATUS(ctypes.Structure):
    _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


def ram_percent():
    try:
        m = MEMSTATUS()
        m.dwLength = ctypes.sizeof(m)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return float(m.dwMemoryLoad)
    except Exception:
        return None


def ram_gb():
    """(used, total) physical memory in GB, or None."""
    try:
        m = MEMSTATUS()
        m.dwLength = ctypes.sizeof(m)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return (m.ullTotalPhys - m.ullAvailPhys) / 2 ** 30, m.ullTotalPhys / 2 ** 30
    except Exception:
        return None


def load(hw, name):
    for s in hw.Sensors:
        if s.SensorType == SensorType.Load and s.Name == name and s.Value is not None:
            return float(s.Value)
    return None


def read():
    out = {"RAM": ram_percent()}
    for hw in pc.Hardware:
        hw.Update()
        ht = hw.HardwareType
        if ht == HardwareType.Cpu:
            out["CPU"] = pick(hw, CPU_PREF)
            out["LOAD"] = load(hw, "CPU Total")
        elif ht in GPU_TYPES and out.get("GPU") is None:
            out["GPU"] = pick(hw, GPU_PREF)
            out["GPUL"] = load(hw, "GPU Core")
        elif ht == HardwareType.Storage:
            out["DSK:" + str(hw.Name)] = pick(hw, ("Temperature",))
    return out


def heat(t, stops):
    if t <= stops[0][0]:
        return QColor(*stops[0][1])
    for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
        if t <= t1:
            k = (t - t0) / (t1 - t0)
            return QColor(*(round(a + (b - a) * k) for a, b in zip(c0, c1)))
    return QColor(*stops[-1][1])


def load_cfg():
    try:
        return json.loads(CFG_FILE.read_text())
    except Exception:
        return {}


def save_cfg(cfg):
    CFG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CFG_FILE.write_text(json.dumps(cfg))


NO_WINDOW = 0x08000000  # CREATE_NO_WINDOW


def wipe_dir(path):
    """Delete everything inside path that isn't locked. Returns bytes freed."""
    freed = 0
    if not os.path.isdir(path):
        return 0
    keep = os.path.normcase(os.path.abspath(BASE))  # our own PyInstaller unpack dir
    for root, dirs, files in os.walk(path, topdown=False):
        if os.path.normcase(os.path.abspath(root)).startswith(keep):
            continue
        for f in files:
            fp = os.path.join(root, f)
            try:
                size = os.path.getsize(fp)
                os.remove(fp)
                freed += size
            except OSError:
                pass
        for d in dirs:
            try:
                os.rmdir(os.path.join(root, d))
            except OSError:
                pass
    return freed


def service_running(name):
    try:
        out = subprocess.run(["sc", "query", name], capture_output=True, text=True,
                             creationflags=NO_WINDOW).stdout
        return "RUNNING" in out
    except Exception:
        return False


def service(action, name):
    try:
        subprocess.run(["net", action, name], capture_output=True,
                       creationflags=NO_WINDOW, timeout=60)
    except Exception:
        pass


def wipe_files(pattern):
    """Delete files matching a glob pattern. Returns bytes freed."""
    freed = 0
    for fp in glob.glob(pattern):
        try:
            size = os.path.getsize(fp)
            os.remove(fp)
            freed += size
        except OSError:
            pass
    return freed


CLEAN_ITEMS = [
    ("temp", "Временные файлы (Windows\\Temp, %TEMP%)"),
    ("wu", "Кэш Центра обновления и Delivery Optimization"),
    ("browser", "Кэш браузеров: Chrome, Edge, Firefox, Brave (без паролей и cookies)"),
    ("shader", "Кэш шейдеров: DirectX, NVIDIA, AMD"),
    ("thumbs", "Миниатюры и кэш значков"),
    ("dumps", "Дампы сбоев и отчёты об ошибках"),
    ("bin", "Корзина"),
    ("dns", "DNS-кэш"),
]


def clean_temp(sel):
    env = os.environ.get
    win = env("windir", r"C:\Windows")
    local = env("LOCALAPPDATA", "")
    pdata = env("ProgramData", r"C:\ProgramData")
    freed = 0
    seen = set()

    def wipe_many(paths):
        nonlocal freed
        for path in paths:
            key = os.path.normcase(os.path.abspath(path)) if path else ""
            if path and key not in seen:
                seen.add(key)
                freed += wipe_dir(path)

    if "temp" in sel:
        wipe_many([os.path.join(win, "Temp"), env("TEMP", "")])
    if "shader" in sel:
        wipe_many([os.path.join(local, "D3DSCache"),
                   os.path.join(local, "NVIDIA", "DXCache"),
                   os.path.join(local, "NVIDIA", "GLCache"),
                   os.path.join(local, "AMD", "DxCache")])
    if "dumps" in sel:
        wipe_many([os.path.join(win, "Minidump"), os.path.join(local, "CrashDumps"),
                   os.path.join(pdata, "Microsoft", "Windows", "WER", "ReportQueue"),
                   os.path.join(pdata, "Microsoft", "Windows", "WER", "ReportArchive"),
                   os.path.join(local, "Microsoft", "Windows", "WER")])
        freed += wipe_files(os.path.join(win, "MEMORY.DMP"))
    if "browser" in sel:  # caches only, never cookies, passwords or history
        dirs = []
        for pat in (r"Google\Chrome\User Data\*\Cache", r"Google\Chrome\User Data\*\Code Cache",
                    r"Google\Chrome\User Data\*\GPUCache", r"Microsoft\Edge\User Data\*\Cache",
                    r"Microsoft\Edge\User Data\*\Code Cache", r"Microsoft\Edge\User Data\*\GPUCache",
                    r"Mozilla\Firefox\Profiles\*\cache2",
                    r"BraveSoftware\Brave-Browser\User Data\*\Cache",
                    r"BraveSoftware\Brave-Browser\User Data\*\Code Cache"):
            dirs += glob.glob(os.path.join(local, pat))
        wipe_many(dirs)
    if "thumbs" in sel:
        explorer = os.path.join(local, "Microsoft", "Windows", "Explorer")
        for pat in ("thumbcache_*.db", "iconcache_*.db"):
            freed += wipe_files(os.path.join(explorer, pat))
    if "wu" in sel:  # stop services, wipe, restart only those that were running
        svcs = [s for s in ("wuauserv", "bits") if service_running(s)]
        for s in svcs:
            service("stop", s)
        wipe_many([os.path.join(win, "SoftwareDistribution", "Download"),
                   os.path.join(win, "ServiceProfiles", "NetworkService", "AppData", "Local",
                                "Microsoft", "Windows", "DeliveryOptimization", "Cache")])
        for s in reversed(svcs):
            service("start", s)
    if "bin" in sel:  # size is not reported by Windows
        try:
            ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 0x7)
        except Exception:
            pass
    if "dns" in sel:
        try:
            subprocess.run(["ipconfig", "/flushdns"], capture_output=True,
                           creationflags=NO_WINDOW, timeout=30)
        except Exception:
            pass
    return freed


class Tip(QLabel):
    """Big, always-readable hover hint (independent of the gadget scale)."""

    def __init__(self):
        super().__init__(None, Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setTextFormat(Qt.RichText)
        self._bg = self._bd = QColor(0, 0, 0, 240)

    def style_for(self, t):
        r, g, b, a = t["bg"]
        br, bg_, bb, ba = t["border"]
        self._bg = QColor(r, g, b, max(a, 240))
        self._bd = QColor(br, bg_, bb, max(ba, 110))
        f = QFont(t["font"])
        f.setPixelSize(15)
        self.setFont(f)
        self.setStyleSheet(f"QLabel {{ background: transparent; padding: 8px 14px;"
                           f" color: rgb{tuple(t['text'])}; }}")

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(self._bd, 1))
        p.setBrush(self._bg)
        p.drawRoundedRect(QRectF(self.rect()).adjusted(.5, .5, -.5, -.5), 9, 9)
        p.end()
        super().paintEvent(e)


class Gadget(QWidget):
    cleaned = Signal(int)

    def __init__(self):
        super().__init__()
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.tip = Tip()
        self._hover = None
        self._tip_at = QPoint()
        self._cleaning = False
        self.cleaned.connect(self._clean_done)

        self.cfg = {**DEFAULTS, **load_cfg()}
        self.cfg["ontop"] = bool(self.cfg["ontop"])
        flags = Qt.FramelessWindowHint | Qt.Tool
        if self.cfg["ontop"]:
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        for key, options in (("theme", THEMES), ("layout", LAYOUTS), ("shape", SHAPES)):
            if self.cfg[key] not in options:
                self.cfg[key] = DEFAULTS[key]
        if self.cfg.get("orient") not in ("h", "v"):
            self.cfg["orient"] = "v" if LAYOUTS[self.cfg["layout"]][0] in STACKED else "h"
        self.cfg["scale"] = min(max(float(self.cfg["scale"]), SCALE_MIN), SCALE_MAX)
        self.setWindowOpacity(self.cfg["opacity"] / 100)

        shown = [k for k in self.cfg.get("show", []) if k in METRICS]
        self.cfg["show"] = shown or list(DEFAULT_SHOW)
        self.target = dict.fromkeys(METRICS)
        self.shown = dict.fromkeys(METRICS)
        self.hist = {k: deque(maxlen=HISTORY) for k in METRICS}
        self._off = None
        self.phase = 0.0
        self._apply(persist=False)
        self._place()
        self._tray_setup()

        self._poll()
        QTimer(self, timeout=self._poll, interval=1000).start()
        QTimer(self, timeout=self._animate, interval=16).start()

    # ---------- state ----------
    def _apply(self, persist=True):
        self.t = THEMES[self.cfg["theme"]]
        self.style, (bw, bh) = LAYOUTS[self.cfg["layout"]]
        self.active = [k for k in METRICS if k in self.cfg["show"]]
        self.groups = self._groups()
        n = len(self.groups)
        if self.style in STACKED:  # one cell = one full-width row
            self.cw, self.ch = bw, bh / 2
        else:  # one cell = half of the two-cell base size
            self.cw, self.ch = bw / 2, bh
        vert = self.cfg["orient"] == "v"
        if self.style == "dial":  # 8GadgetPack look: first dial big, the rest smaller and overlapping
            self.rects, pos, W, H = [], 0.0, 0.0, 0.0
            for i in range(n):
                s = 1.0 if i == 0 else DIAL_SMALL
                w, h = self.cw * s, self.ch * s
                if vert:  # small ones right-aligned under the big one
                    x, y = self.cw - w, pos
                    pos = y + h - 8
                else:  # small ones top-aligned, tucked over the previous dial's edge
                    x, y = pos, 0.0
                    pos = x + w - (30 if i == 0 else 12)
                self.rects.append((x, y, s))
                W, H = max(W, x + w), max(H, y + h)
            self.bw, self.bh = W, H
        elif vert:  # cells grow downwards
            self.rects = [(0, i * self.ch, 1.0) for i in range(n)]
            self.bw, self.bh = self.cw, self.ch * n
        else:  # cells grow to the right
            self.rects = [(i * self.cw, 0, 1.0) for i in range(n)]
            self.bw, self.bh = self.cw * n, self.ch
        self.k = self.cfg["scale"]
        self.setFixedSize(round(self.bw * self.k), round(self.bh * self.k))
        if persist:
            self._persist()
        self.update()

    def _set(self, **kw):
        self.cfg.update(kw)
        self._apply()

    def _toggle_metric(self, key, on):
        show = [k for k in METRICS if k in self.cfg["show"]]
        if on and key not in show:
            show.append(key)
        elif not on and key in show and len(show) > 1:  # keep at least one
            show.remove(key)
        self._set(show=[k for k in METRICS if k in show])

    def _set_top(self, on):
        pos = self.pos()
        self.cfg["ontop"] = bool(on)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, bool(on))
        self.move(pos)
        self.show()
        self._persist()

    # ---------- tray ----------
    def _toggle(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()

    def _tray_setup(self):
        self.tray = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(self)
        self._tray_menu = QMenu()
        self._tray_menu.addAction("Показать / скрыть гаджет", self._toggle)
        self._tray_menu.addAction("Очистить систему от мусора", self._clean_ask)
        self._tray_menu.addSeparator()
        self._tray_menu.addAction("Выход", QApplication.quit)
        self.tray.setContextMenu(self._tray_menu)
        self.tray.activated.connect(
            lambda r: self._toggle() if r in (QSystemTrayIcon.Trigger,
                                              QSystemTrayIcon.DoubleClick) else None)
        self._tray_update()
        self.tray.show()

    def _tray_update(self):
        if self.tray is None:
            return
        keys = self.active[:2]
        pm = QPixmap(64, 64)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(18, 20, 28, 235))
        p.drawRoundedRect(QRectF(0, 0, 64, 64), 12, 12)
        h = 64 / len(keys)
        for i, k in enumerate(keys):
            v = self.target[k]
            f = QFont("Segoe UI")
            f.setPixelSize(30 if len(keys) == 2 else 40)
            f.setBold(True)
            p.setFont(f)
            p.setPen(self._col(k, v))
            p.drawText(QRectF(0, i * h, 64, h), int(Qt.AlignCenter),
                       "--" if v is None else f"{v:.0f}")
        p.end()
        self.tray.setIcon(QIcon(pm))
        self.tray.setToolTip("\n".join(
            f"{METRICS[k]['label']}: " + self._long(k, self.target[k]) for k in self.active))

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton and self.tray is not None:
            self.hide()

    def _clean_ask(self):
        if self._cleaning:
            return
        saved = self.cfg.get("clean")
        chosen = set(saved) if isinstance(saved, list) else {k for k, _ in CLEAN_ITEMS}
        dlg = QDialog(self)
        dlg.setWindowTitle("Очистка системы")
        dlg.setWindowFlag(Qt.WindowStaysOnTopHint)
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel("Что очистить:"))
        boxes = {}
        for key, title in CLEAN_ITEMS:
            cb = QCheckBox(title)
            cb.setChecked(key in chosen)
            boxes[key] = cb
            lay.addWidget(cb)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText("Очистить")
        btns.button(QDialogButtonBox.Cancel).setText("Отмена")
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addWidget(btns)
        if dlg.exec() != QDialog.Accepted:
            return
        sel = {k for k, cb in boxes.items() if cb.isChecked()}
        self.cfg["clean"] = [k for k, _ in CLEAN_ITEMS if k in sel]
        self._persist()
        if not sel:
            return
        self._cleaning = True
        threading.Thread(target=lambda: self.cleaned.emit(clean_temp(sel)),
                         daemon=True).start()

    def _clean_done(self, freed):
        self._cleaning = False
        b = QMessageBox(self)
        b.setWindowTitle("Очистка")
        b.setText(f"Готово. Освобождено: {freed / 1048576:.1f} МБ")
        b.setWindowFlag(Qt.WindowStaysOnTopHint)
        b.exec()

    def _place(self):
        x, y = self.cfg.get("x"), self.cfg.get("y")
        if x is not None and QApplication.screenAt(QPoint(x + 10, y + 10)):
            self.move(x, y)
        else:
            g = QApplication.primaryScreen().availableGeometry()
            self.move(g.right() - self.width() - 24, g.top() + 24)

    def _persist(self):
        self.cfg.update(x=self.x(), y=self.y(),
                        opacity=round(self.windowOpacity() * 100))
        save_cfg(self.cfg)

    def _poll(self):
        got = read()
        self.target = {k: got.get(k) for k in METRICS}
        for k, v in self.target.items():
            if v is not None:
                self.hist[k].append(v)
        self._tray_update()
        self._tip_show()

    def _animate(self):
        for k in METRICS:
            t, s = self.target[k], self.shown[k]
            self.shown[k] = None if t is None else t if s is None else s + (t - s) * 0.12
        self.phase += 0.03
        self.update()

    # ---------- helpers ----------
    @staticmethod
    def _frac(k, v):
        if v is None:
            return 0.0
        lo, hi = (0, 100) if METRICS[k]["kind"] == "load" else (T_MIN, T_MAX)
        return min(max((v - lo) / (hi - lo), 0.0), 1.0)

    def _col(self, k, v):
        if v is None:
            return QColor(*self.t["dim"])
        if METRICS[k]["kind"] == "load":  # 0..100 % -> same colour ramp as 20..100 C
            v = 20 + 0.8 * v
        return heat(v, self.t["stops"])

    @staticmethod
    def _num(k, v):  # 54deg / 7%
        if v is None:
            return "--"
        return f"{v:.0f}" + ("%" if METRICS[k]["kind"] == "load" else "°")

    @staticmethod
    def _long(k, v, compact=False):  # "54 C" / "7 %"
        if v is None:
            return "--"
        unit = "%" if METRICS[k]["kind"] == "load" else "°C"
        return f"{v:.0f}{unit}" if compact else f"{v:.0f} {unit}"

    @staticmethod
    def _sub(k):  # caption under a dial
        m = METRICS[k]
        return m["label"] + (" °C" if m["kind"] == "temp" else "")

    def _text(self, p, rect, s, px, color, bold=False, align=Qt.AlignCenter):
        f = QFont(self.t["font"])
        f.setPixelSize(px)
        f.setBold(bold)
        p.setFont(f)
        col = QColor(*color) if isinstance(color, tuple) else QColor(color)
        if self.t["glow"] and bold and px >= 20:  # soft neon halo
            halo = QColor(col)
            halo.setAlpha(45)
            p.setPen(halo)
            for dx, dy in ((-1.5, 0), (1.5, 0), (0, -1.5), (0, 1.5)):
                p.drawText(rect.translated(dx, dy), int(align), s)
        p.setPen(col)
        p.drawText(rect, int(align), s)

    def _ring(self, p, cx, cy, r, frac, col, w=9, start=90, sweep=360):
        rect = QRectF(cx - r, cy - r, 2 * r, 2 * r)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(*self.t["track"]), w, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(rect, start * 16, -sweep * 16)
        if frac <= 0:
            return
        span = -int(sweep * frac * 16)
        if self.t["glow"]:
            for gw, a in ((w + 10, 28), (w + 5, 50)):
                g = QColor(col)
                g.setAlpha(a)
                p.setPen(QPen(g, gw, Qt.SolidLine, Qt.RoundCap))
                p.drawArc(rect, start * 16, span)
        p.setPen(QPen(col, w, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(rect, start * 16, span)

    # ---------- layouts ----------
    def _groups(self):
        """Compact/dial layouts merge CPU/GPU load with its temperature into one cell."""
        act = self.active
        if self.style not in ("compact", "dial"):
            return [(k, None) for k in act]
        pairs = {"LOAD": "CPU", "GPUL": "GPU"}
        merged = {t for ld, t in pairs.items() if ld in act and t in act}
        out = []
        for k in act:
            if k in merged:
                continue
            out.append((k, pairs[k] if k in pairs and pairs[k] in act else None))
        return out

    def _draw_compact(self, p):
        k, k2 = self._cur
        w = self.cw
        cx, cy = w / 2, 38
        v = self.shown[k]
        c = self._col(k, v)
        self._ring(p, cx, cy, 31, self._frac(k, v), c, w=5)
        if k2:
            v2 = self.shown[k2]
            c2 = self._col(k2, v2)
            self._ring(p, cx, cy, 22, self._frac(k2, v2), c2, w=4)
            self._text(p, QRectF(cx - 21, cy - 10, 42, 20), self._num(k, v), 13,
                       self.t["text"], True)
            self._text(p, QRectF(cx - w / 2, 72, w, 16), self._long(k2, v2, compact=True),
                       13, c2, True)
            self._text(p, QRectF(cx - w / 2, 88, w, 14), METRICS[k2]["label"], 10,
                       self.t["dim"], True)
        else:
            self._text(p, QRectF(cx - 26, cy - 10, 52, 20), self._num(k, v), 15,
                       self.t["text"], True)
            self._text(p, QRectF(cx - w / 2, 74, w, 16), METRICS[k]["label"], 11,
                       self.t["dim"], True)

    def _cells(self):
        """(key, shown value, centre x, cell width) of the cell being drawn."""
        k = self._cur[0]
        return [(k, self.shown[k], self.cw / 2, self.cw)]

    def _draw_gauge(self, p):
        r, n = 58, 25
        for k, v, cx, _ in self._cells():
            cy = 92
            c, frac = self._col(k, v), self._frac(k, v)
            self._ring(p, cx, cy, r, frac, c, w=8, start=210, sweep=240)
            off = QColor(*self.t["dim"])
            off.setAlpha(90)
            for j in range(n):  # tick marks that light up with the value
                a = math.radians(210 - 240 * j / (n - 1))
                on = v is not None and j / (n - 1) <= frac
                major = j % 4 == 0
                r0, r1 = r + 9, r + (16 if major else 12)
                p.setPen(QPen(c if on else off, 2.2 if major else 1.3,
                              Qt.SolidLine, Qt.RoundCap))
                p.drawLine(QPointF(cx + r0 * math.cos(a), cy - r0 * math.sin(a)),
                           QPointF(cx + r1 * math.cos(a), cy - r1 * math.sin(a)))
            a = math.radians(210 - 240 * frac)
            tip = QPointF(cx + (r - 12) * math.cos(a), cy - (r - 12) * math.sin(a))
            if self.t["glow"]:
                g = QColor(c)
                g.setAlpha(60)
                p.setPen(QPen(g, 7, Qt.SolidLine, Qt.RoundCap))
                p.drawLine(QPointF(cx, cy), tip)
            p.setPen(QPen(QColor(*self.t["text"]), 2.5, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(cx, cy), tip)
            p.setPen(Qt.NoPen)
            p.setBrush(c)
            p.drawEllipse(QPointF(cx, cy), 6, 6)
            p.setBrush(QColor(*self.t["bg"]))
            p.drawEllipse(QPointF(cx, cy), 2.5, 2.5)
            self._text(p, QRectF(cx - 50, cy + 12, 100, 36), self._num(k, v), 28,
                       self.t["text"], True)
            self._text(p, QRectF(cx - 50, cy + 48, 100, 18), self._sub(k), 11,
                       self.t["dim"], True)

    def _draw_dial(self, p):
        """8GadgetPack-style speedometer: arc + needle = load, hub = temperature."""
        k, k2 = self._cur
        cx, cy, r, n, hub = self.cw / 2, 74, 50, 25, 23
        v = self.shown[k]
        c, frac = self._col(k, v), self._frac(k, v)
        if self._small:
            p.setPen(QPen(QColor(*self.t["border"]), 1.2))
            p.setBrush(QColor(*self.t["bg"][:3], 240))
            p.drawEllipse(QPointF(cx, cy), r + 17, r + 17)
        self._ring(p, cx, cy, r, frac, c, w=7, start=210, sweep=240)
        off = QColor(*self.t["dim"])
        off.setAlpha(90)
        for j in range(n):
            a = math.radians(210 - 240 * j / (n - 1))
            on = v is not None and j / (n - 1) <= frac
            major = j % 4 == 0
            r0, r1 = r + 8, r + (14 if major else 11)
            p.setPen(QPen(c if on else off, 2.2 if major else 1.3, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(cx + r0 * math.cos(a), cy - r0 * math.sin(a)),
                       QPointF(cx + r1 * math.cos(a), cy - r1 * math.sin(a)))
        a = math.radians(210 - 240 * frac)
        p0 = QPointF(cx + hub * math.cos(a), cy - hub * math.sin(a))
        tip = QPointF(cx + (r - 6) * math.cos(a), cy - (r - 6) * math.sin(a))
        if self.t["glow"]:
            g = QColor(c)
            g.setAlpha(60)
            p.setPen(QPen(g, 7, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(p0, tip)
        p.setPen(QPen(c, 3, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(p0, tip)
        # hub: temperature of the paired sensor (or the value/label when there is none)
        if k2:
            t2 = self.shown[k2]
            hc, htxt, hpx = self._col(k2, t2), self._num(k2, t2), 16
            main, sub_ = self._num(k, v), METRICS[k2]["label"]
        elif METRICS[k]["kind"] == "load":
            hc, htxt, hpx = c, METRICS[k]["label"], 11
            main, sub_ = self._num(k, v), ""
        else:
            hc, htxt, hpx = c, self._num(k, v), 16
            main, sub_ = METRICS[k]["label"], ""
        p.setBrush(QColor(*self.t["bg"][:3]))
        if self.t["glow"]:
            g = QColor(hc)
            g.setAlpha(45)
            p.setPen(QPen(g, 7))
            p.drawEllipse(QPointF(cx, cy), hub, hub)
        p.setPen(QPen(hc, 2.5))
        p.drawEllipse(QPointF(cx, cy), hub, hub)
        self._text(p, QRectF(cx - hub, cy - 11, 2 * hub, 22), htxt, hpx, self.t["text"], True)
        self._text(p, QRectF(cx - self.cw / 2, 102, self.cw, 24), main, 20,
                   c if k2 or METRICS[k]["kind"] == "load" else self.t["text"], True)
        if sub_:
            self._text(p, QRectF(cx - self.cw / 2, 126, self.cw, 16), sub_, 11,
                       self.t["dim"], True)

    def _draw_liquid(self, p):
        r = 52
        for k, v, cx, _ in self._cells():
            cy = 66
            c, frac = self._col(k, v), self._frac(k, v)
            circ = QPainterPath()
            circ.addEllipse(QPointF(cx, cy), r, r)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(*self.t["track"]))
            p.drawPath(circ)
            if v is not None:
                level = cy + r - 2 * r * (0.06 + 0.88 * frac)
                p.save()
                p.setClipPath(circ)
                for amp, spd, alpha, dy in ((4.0, 1.0, 120, 0), (3.0, -1.4, 215, 2)):
                    path = QPainterPath(QPointF(cx - r, cy + r))
                    x = cx - r
                    while x <= cx + r + 4:
                        path.lineTo(x, level + dy + amp * math.sin(x * 0.09 + self.phase * spd * 3))
                        x += 4
                    path.lineTo(cx + r + 4, cy + r)
                    path.closeSubpath()
                    col = QColor(c)
                    col.setAlpha(alpha)
                    p.setBrush(col)
                    p.drawPath(path)
                p.restore()
            p.setBrush(Qt.NoBrush)
            if self.t["glow"]:
                g = QColor(c)
                g.setAlpha(40)
                p.setPen(QPen(g, 8))
                p.drawEllipse(QPointF(cx, cy), r, r)
            ring = QColor(c)
            ring.setAlpha(170)
            p.setPen(QPen(ring, 2.5))
            p.drawEllipse(QPointF(cx, cy), r, r)
            p.setPen(QPen(QColor(255, 255, 255, 80), 3, Qt.SolidLine, Qt.RoundCap))
            p.drawArc(QRectF(cx - r + 8, cy - r + 8, 2 * r - 16, 2 * r - 16), 110 * 16, 50 * 16)
            self._text(p, QRectF(cx - 45, cy - 20, 90, 40), self._num(k, v), 28,
                       self.t["text"], True)
            self._text(p, QRectF(cx - 45, 124, 90, 20), METRICS[k]["label"], 12,
                       self.t["dim"], True)

    def _draw_line(self, p):
        for k, v, cx, w in self._cells():
            x = cx - w / 2
            c = self._col(k, v)
            p.setPen(Qt.NoPen)
            p.setBrush(c)
            p.drawEllipse(QPointF(x + 18, self.ch / 2), 4.5, 4.5)
            self._text(p, QRectF(x + 28, 0, 48, self.ch), METRICS[k]["label"], 11,
                       self.t["dim"], True, Qt.AlignLeft | Qt.AlignVCenter)
            self._text(p, QRectF(x + 76, 0, w - 80, self.ch), self._num(k, v), 20, c, True,
                       Qt.AlignLeft | Qt.AlignVCenter)

    def _draw_rings(self, p):
        for k, v, cx, _ in self._cells():
            cy = 70
            c = self._col(k, v)
            self._ring(p, cx, cy, 46, self._frac(k, v), c)
            self._text(p, QRectF(cx - 40, cy - 18, 80, 36), self._num(k, v), 24,
                       self.t["text"], True)
            self._text(p, QRectF(cx - 45, 126, 90, 20), METRICS[k]["label"], 12,
                       self.t["dim"], True)

    def _draw_arc(self, p):
        for k, v, cx, _ in self._cells():
            cy = 72
            c = self._col(k, v)
            self._ring(p, cx, cy, 48, self._frac(k, v), c, w=10, start=210, sweep=240)
            self._text(p, QRectF(cx - 48, cy - 22, 96, 40), self._num(k, v), 28, c, True)
            self._text(p, QRectF(cx - 48, cy + 26, 96, 18), self._sub(k), 11,
                       self.t["dim"], True)

    def _draw_bars(self, p):
        x0, x1 = 18, self.cw - 18
        rh = self.ch
        for i, k in enumerate(self._cur[:1]):
            v = self.shown[k]
            y = i * rh + (rh - 36) / 2
            c = self._col(k, v)
            self._text(p, QRectF(x0, y, 90, 22), METRICS[k]["label"], 13, self.t["dim"], True,
                       Qt.AlignLeft | Qt.AlignVCenter)
            self._text(p, QRectF(x1 - 110, y - 2, 110, 26), self._long(k, v), 19,
                       self.t["text"], True, Qt.AlignRight | Qt.AlignVCenter)
            track = QRectF(x0, y + 28, x1 - x0, 8)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(*self.t["track"]))
            p.drawRoundedRect(track, 4, 4)
            w = track.width() * self._frac(k, v)
            if w < 1:
                continue
            fill = QRectF(track.x(), track.y(), w, track.height())
            if self.t["glow"]:
                g = QColor(c)
                g.setAlpha(45)
                p.setBrush(g)
                p.drawRoundedRect(fill.adjusted(-3, -3, 3, 3), 7, 7)
            grad = QLinearGradient(fill.left(), 0, max(fill.right(), fill.left() + 1), 0)
            grad.setColorAt(0, QColor(*self.t["stops"][0][1]))
            grad.setColorAt(1, c)
            p.setBrush(grad)
            p.drawRoundedRect(fill, 4, 4)

    def _draw_numbers(self, p):
        for k, v, cx, _ in self._cells():
            c = self._col(k, v)
            p.setPen(Qt.NoPen)
            p.setBrush(c)
            p.drawEllipse(QPointF(cx - 28, 22), 4, 4)
            self._text(p, QRectF(cx - 22, 12, 80, 20), METRICS[k]["label"], 12, self.t["dim"],
                       True, Qt.AlignLeft | Qt.AlignVCenter)
            self._text(p, QRectF(cx - 60, 34, 120, 54), self._num(k, v), 42, c, True)

    def _draw_spark(self, p):
        rh = self.ch
        for i, k in enumerate(self._cur[:1]):
            v = self.shown[k]
            y = i * rh + (rh - 48) / 2
            c = self._col(k, v)
            self._text(p, QRectF(14, y, 80, 16), "> " + METRICS[k]["label"], 12, self.t["dim"],
                       True, Qt.AlignLeft | Qt.AlignVCenter)
            self._text(p, QRectF(14, y + 18, 84, 30), self._long(k, v, compact=True), 22, c,
                       True, Qt.AlignLeft | Qt.AlignVCenter)
            area = QRectF(104, y + 2, self.cw - 118, 44)
            p.setPen(QPen(QColor(*self.t["track"]), 1))
            p.drawLine(QPointF(area.left(), area.bottom()), QPointF(area.right(), area.bottom()))
            hist = list(self.hist[k])
            if len(hist) < 2:
                continue
            lo, hi = min(hist), max(hist)
            span = max(hi - lo, 10.0)
            lo -= (span - (hi - lo)) / 2
            pts = [QPointF(area.left() + area.width() * j / (HISTORY - 1),
                           area.bottom() - area.height() * (t - lo) / span)
                   for j, t in enumerate(hist, start=HISTORY - len(hist))]
            line = QPainterPath(pts[0])
            for pt in pts[1:]:
                line.lineTo(pt)
            fill = QPainterPath(line)
            fill.lineTo(pts[-1].x(), area.bottom())
            fill.lineTo(pts[0].x(), area.bottom())
            fill.closeSubpath()
            a = QColor(c)
            a.setAlpha(35)
            p.setPen(Qt.NoPen)
            p.setBrush(a)
            p.drawPath(fill)
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(c, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawPath(line)

    # ---------- hover hint ----------
    def _cell_at(self, pos):
        """Index of the cell under a widget-local point (topmost first), or None."""
        for i in reversed(range(len(self.groups))):
            x, y, s = self.rects[i]
            r = QRectF(x * self.k, y * self.k, self.cw * s * self.k, self.ch * s * self.k)
            if r.contains(pos):
                return i
        return None

    def _tip_html(self, i):
        t, rows = self.t, []
        dim = "#%02x%02x%02x" % tuple(t["dim"])
        for k in [m for m in self.groups[i] if m]:
            v = self.target[k]
            val = self._long(k, v)
            if k == "RAM" and v is not None and ram_gb():
                used, total = ram_gb()
                val += f"  ({used:.1f} / {total:.1f} ГБ)"
            rows.append(f'<span style="color:{dim}">{METRICS[k]["title"]}</span>'
                        f'&nbsp;&nbsp;<b style="color:{self._col(k, v).name()}">{val}</b>')
        return "<br>".join(rows)

    def _tip_show(self, gpos=None):
        i = self._hover
        if i is None or i >= len(self.groups):
            self.tip.hide()
            return
        if gpos is not None:
            self._tip_at = gpos
        self.tip.style_for(self.t)
        self.tip.setText(self._tip_html(i))
        self.tip.adjustSize()
        scr = QApplication.screenAt(self._tip_at) or QApplication.primaryScreen()
        g = scr.availableGeometry()
        x = min(self._tip_at.x() + 16, g.right() - self.tip.width())
        y = self._tip_at.y() + 22
        if y + self.tip.height() > g.bottom():
            y = self._tip_at.y() - self.tip.height() - 12
        self.tip.move(max(x, g.left()), max(y, g.top()))
        if not self.tip.isVisible():
            self.tip.show()

    def _tip_hide(self):
        self._hover = None
        self.tip.hide()

    def leaveEvent(self, _):
        self._tip_hide()

    def hideEvent(self, _):
        self._tip_hide()

    # ---------- events ----------
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)
        p.scale(self.k, self.k)
        r = SHAPES[self.cfg["shape"]]
        rect = QRectF(.75, .75, self.bw - 1.5, self.bh - 1.5)
        if r == "cut":
            c = min(14, self.bh / 3)
            path = QPainterPath(QPointF(rect.left() + c, rect.top()))
            path.lineTo(rect.right(), rect.top())
            path.lineTo(rect.right(), rect.bottom() - c)
            path.lineTo(rect.right() - c, rect.bottom())
            path.lineTo(rect.left(), rect.bottom())
            path.lineTo(rect.left(), rect.top() + c)
            path.closeSubpath()
        else:
            r = r * self.bh if r < 1 else r
            path = QPainterPath()
            path.addRoundedRect(rect, r, r)
        # diagonal gradient body
        bg = QLinearGradient(0, 0, self.bw * .6, self.bh)
        bg.setColorAt(0, QColor(*self.t["bg"]))
        bg.setColorAt(1, QColor(*BG2.get(self.cfg["theme"], self.t["bg"])))
        p.setPen(Qt.NoPen)
        p.setBrush(bg)
        p.drawPath(path)
        # glossy highlight along the top
        p.save()
        p.setClipPath(path)
        gloss = QLinearGradient(0, 0, 0, self.bh * .55)
        gloss.setColorAt(0, QColor(255, 255, 255, 32))
        gloss.setColorAt(1, QColor(255, 255, 255, 0))
        p.setBrush(gloss)
        p.drawRect(QRectF(0, 0, self.bw, self.bh * .55))
        p.restore()
        # light edge: bright top-left, fading bottom-right; pulses red when hot
        bc = QColor(*self.t["border"])
        vals = [self.shown[k] for k in self.active
                if METRICS[k]["kind"] == "temp" and self.shown[k] is not None]
        if vals and max(vals) >= 85:
            bc = QColor(255, 50, 50, int(150 + 90 * math.sin(self.phase * 6)))
        hi, lo = QColor(bc), QColor(bc)
        hi.setAlpha(min(255, bc.alpha() * 2))
        lo.setAlpha(bc.alpha() // 3)
        edge = QLinearGradient(0, 0, self.bw, self.bh)
        edge.setColorAt(0, hi)
        edge.setColorAt(1, lo)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QBrush(edge), 1.5))
        p.drawPath(path)
        for g, (x, y, sc) in zip(self.groups, self.rects):
            p.save()
            p.translate(x, y)
            p.scale(sc, sc)
            self._cur, self._small = g, sc < 1
            getattr(self, f"_draw_{self.style}")(p)
            p.restore()

    def wheelEvent(self, e):
        if e.modifiers() & Qt.ControlModifier:
            step = 0.05 if e.angleDelta().y() > 0 else -0.05
            self._set(scale=round(min(max(self.k + step, SCALE_MIN), SCALE_MAX), 2))

    def mousePressEvent(self, e):
        self._tip_hide()
        if e.button() == Qt.LeftButton:
            self._off = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._off is not None and e.buttons() & Qt.LeftButton:
            self._tip_hide()
            self.move(e.globalPosition().toPoint() - self._off)
        elif self._off is None:
            self._hover = self._cell_at(e.position())
            self._tip_show(e.globalPosition().toPoint())

    def mouseReleaseEvent(self, _):
        if self._off is not None:
            self._off = None
            self._persist()

    def _radio(self, menu, title, options, current, setter):
        sub = menu.addMenu(title)
        group = QActionGroup(sub)
        for label, value in options:
            a = QAction(label, group, checkable=True, checked=value == current)
            a.triggered.connect(lambda _=False, v=value: setter(v))
            sub.addAction(a)

    def contextMenuEvent(self, e):
        self._tip_hide()
        c = self.cfg
        menu = QMenu(self)
        presets = menu.addMenu("✨ Пресеты")
        for name, kw in PRESETS.items():
            act = presets.addAction(name)
            act.triggered.connect(lambda _=False, kw=kw: self._set(**kw))
        shown = menu.addMenu("Показывать")
        for key, m in METRICS.items():
            act = shown.addAction(m["title"])
            act.setCheckable(True)
            act.setChecked(key in self.active)
            act.toggled.connect(lambda on, key=key: self._toggle_metric(key, on))
        self._radio(menu, "Тема", [(n, n) for n in THEMES], c["theme"],
                    lambda v: self._set(theme=v))
        self._radio(menu, "Вид", [(n, n) for n in LAYOUTS], c["layout"],
                    lambda v: self._set(layout=v))
        self._radio(menu, "Форма", [(n, n) for n in SHAPES], c["shape"],
                    lambda v: self._set(shape=v))
        self._radio(menu, "Ориентация", [("Горизонтально", "h"), ("Вертикально", "v")],
                    c["orient"], lambda v: self._set(orient=v))
        self._radio(menu, "Размер (Ctrl+колесо)", [(f"{s}%", s) for s in SCALES],
                    round(self.k * 100), lambda v: self._set(scale=v / 100))
        self._radio(menu, "Прозрачность", [(f"{o}%" , o) for o in OPACITIES],
                    round(self.windowOpacity() * 100),
                    lambda v: (self.setWindowOpacity(v / 100), self._persist()))
        if self.tray is not None:
            menu.addAction("Свернуть в трей (двойной клик)", self.hide)
        top = menu.addAction("Поверх всех окон")
        top.setCheckable(True)
        top.setChecked(c["ontop"])
        top.toggled.connect(self._set_top)
        menu.addSeparator()
        clean = menu.addAction("Очищается..." if self._cleaning else "Очистить систему от мусора")
        clean.setEnabled(not self._cleaning)
        clean.triggered.connect(self._clean_ask)
        menu.addSeparator()
        menu.addAction("Выход", QApplication.quit)
        menu.exec(e.globalPos())


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.aboutToQuit.connect(pc.Close)
    gadget = Gadget()
    gadget.show()
    sys.exit(app.exec())
