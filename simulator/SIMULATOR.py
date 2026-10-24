import requests
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext
import numpy as np
import pandas as pd
import joblib
import random
from collections import deque
import math
from collections import defaultdict
from matplotlib.colors import to_rgb
from mpl_toolkits.mplot3d.art3d import Poly3DCollection, Line3DCollection
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import warnings
warnings.filterwarnings("ignore")

# ==========================================
# CONFIGURATION & MODEL LOADING
# ==========================================
MODEL_PATH = "2v.joblib"
THRESHOLD = 8.0
SETPOINT = 4.0
HISTORY_SIZE = 144

# Django API endpoint
DJANGO_API_URL = "http://127.0.0.1:8000/monitoring/api/readings/"

# ---- Realistic physics tuning ----
COOLING_BASE      = 0.40
COOLING_GAIN      = 0.04
COOLING_MAX       = 1.50
HEAT_LEAK_COEF    = 0.005
DOOR_HEAT_COEF    = 0.20
DEFROST_HEAT_RATE = 0.30
THERMOSTAT_ON     = 5.0
THERMOSTAT_OFF    = 4.0


def send_to_django(payload):
    """POST a reading to the Django backend (silently ignores errors)."""
    try:
        requests.post(DJANGO_API_URL, json=payload, timeout=0.5)
    except requests.exceptions.RequestException:
        pass  # Django not running? Silently skip — simulator continues fine


try:
    model = joblib.load(MODEL_PATH)
    USE_REAL_MODEL = True
    print(f"✅ Model loaded successfully from {MODEL_PATH}")
except Exception as e:
    USE_REAL_MODEL = False
    print(f"⚠️ Could not load model. Using mock model. Error: {e}")

# Color Palette
BG_MAIN = "#0f172a"
BG_PANEL = "#1e293b"
FG_TEXT = "#f8fafc"
ACCENT = "#38bdf8"
DANGER = "#ef4444"
WARN = "#f59e0b"
SUCCESS = "#10b981"


class DigitalTwinApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ColdPulse - AI Digital Twin Control Center")
        self.root.geometry("1400x800")
        self.root.configure(bg=BG_MAIN)

        self.internal_temp = 4.0
        self.ambient_temp = 30.0
        self.door_open = 0
        self.power_status = 1
        self.compressor_status = 1
        self.defrost_cycle = 0
        self.sensor_fault = 0
        self.load_change = 0.0

        self.step_count = 0
        self.door_open_step = -999
        self.door_closed_step = 0
        self.power_cut_step = -999
        self.compressor_start_step = 0

        self.history = deque(maxlen=HISTORY_SIZE)
        self.latest_prediction = 4.0

        self.setup_ui()
        self.update_simulation()

    def setup_ui(self):
        header_frame = tk.Frame(self.root, bg=BG_PANEL, height=60)
        header_frame.pack(side="top", fill="x")
        header_frame.pack_propagate(False)

        tk.Label(header_frame, text="COLDPULSE AI", bg=BG_PANEL, fg=ACCENT,
                 font=("Segoe UI", 20, "bold")).pack(side="left", padx=20)
        tk.Label(header_frame, text="| Digital Twin Control Center",
                 bg=BG_PANEL, fg="#94a3b8", font=("Segoe UI", 14)).pack(side="left")

        self.lbl_header_status = tk.Label(header_frame, text="SYSTEM NORMAL",
                                          bg=BG_PANEL, fg=SUCCESS,
                                          font=("Segoe UI", 14, "bold"))
        self.lbl_header_status.pack(side="right", padx=20)

        main_frame = tk.Frame(self.root, bg=BG_MAIN)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        left_frame = tk.Frame(main_frame, bg=BG_PANEL, bd=2, relief="groove")
        left_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))

        self.fig = plt.Figure(figsize=(8, 6), dpi=100)
        self.fig.patch.set_facecolor(BG_MAIN)
        self.ax = self.fig.add_subplot(111, projection='3d')
        self.ax.set_axis_off()

        self.canvas = FigureCanvasTkAgg(self.fig, master=left_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        right_frame = tk.Frame(main_frame, bg=BG_MAIN, width=450)
        right_frame.pack(side="right", fill="y")
        right_frame.pack_propagate(False)

        ctrl_frame = tk.LabelFrame(right_frame, text=" OPERATOR CONTROLS ",
                                   bg=BG_PANEL, fg=ACCENT,
                                   font=("Segoe UI", 11, "bold"), bd=2, relief="groove")
        ctrl_frame.pack(fill="x", pady=(0, 10), ipady=5)

        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Action.TButton", font=("Segoe UI", 10, "bold"),
                        padding=8, background=BG_PANEL, foreground="black")

        self.btn_power = ttk.Button(ctrl_frame, text="⚡ POWER: ON",
                                    command=self.toggle_power, style="Action.TButton")
        self.btn_power.pack(fill="x", padx=10, pady=5)

        self.btn_door = ttk.Button(ctrl_frame, text="🚪 DOOR: CLOSED",
                                   command=self.toggle_door, style="Action.TButton")
        self.btn_door.pack(fill="x", padx=10, pady=5)

        self.btn_defrost = ttk.Button(ctrl_frame, text="❄️ DEFROST: OFF",
                                      command=self.toggle_defrost, style="Action.TButton")
        self.btn_defrost.pack(fill="x", padx=10, pady=5)

        self.btn_load = ttk.Button(ctrl_frame, text="📦 ADD WARM STOCK (+20kg)",
                                   command=self.trigger_load, style="Action.TButton")
        self.btn_load.pack(fill="x", padx=10, pady=5)

        self.btn_fault = ttk.Button(ctrl_frame, text="⚠️ SENSOR FAULT: NO",
                                    command=self.toggle_fault, style="Action.TButton")
        self.btn_fault.pack(fill="x", padx=10, pady=5)

        ai_frame = tk.LabelFrame(right_frame, text=" AI PREDICTIVE WARNING ",
                                 bg=BG_PANEL, fg=DANGER,
                                 font=("Segoe UI", 11, "bold"), bd=2, relief="groove")
        ai_frame.pack(fill="x", pady=(0, 10), ipady=10)

        self.lbl_ai_temp = tk.Label(ai_frame, text="Current: 4.0 °C",
                                    bg=BG_PANEL, fg=FG_TEXT, font=("Segoe UI", 12))
        self.lbl_ai_temp.pack()

        self.lbl_ai_pred = tk.Label(ai_frame, text="Predicted (30m): -- °C",
                                    bg=BG_PANEL, fg=ACCENT, font=("Segoe UI", 16, "bold"))
        self.lbl_ai_pred.pack(pady=5)

        self.lbl_ai_risk = tk.Label(ai_frame, text="RISK: SAFE",
                                    bg=BG_PANEL, fg=SUCCESS, font=("Segoe UI", 20, "bold"))
        self.lbl_ai_risk.pack()

        log_frame = tk.LabelFrame(right_frame, text=" LIVE TELEMETRY & AI LOG ",
                                  bg=BG_PANEL, fg="#94a3b8",
                                  font=("Segoe UI", 11, "bold"), bd=2, relief="groove")
        log_frame.pack(fill="both", expand=True)

        self.log_box = scrolledtext.ScrolledText(log_frame, bg="#020617", fg="#38bdf8",
                                                 font=("Consolas", 10), state="disabled", wrap="word")
        self.log_box.pack(fill="both", expand=True, padx=5, pady=5)

    def log_msg(self, msg, color_tag="info"):
        self.log_box.config(state="normal")
        self.log_box.insert(tk.END, msg + "\n", color_tag)
        self.log_box.see(tk.END)
        self.log_box.config(state="disabled")
        self.log_box.tag_config("info", foreground="#38bdf8")
        self.log_box.tag_config("safe", foreground="#10b981")
        self.log_box.tag_config("warn", foreground="#f59e0b")
        self.log_box.tag_config("danger", foreground="#ef4444")

    # ==================================================================
    #  3D COLD-CHAMBER MODEL
    # ==================================================================
    _LIGHT = np.array([0.35, -0.55, 0.75]) / np.linalg.norm([0.35, -0.55, 0.75])
    _LEVEL_COLORS = [SUCCESS, WARN, DANGER]
    _SENSORS = [
        ("T1 Door",   (8.4, 1.0, 3.3), "stem"),
        ("T2 Center", (5.0, 3.0, 2.9), "stem"),
        ("T3 Rack A", (3.8, 5.1, 2.7), "shelf"),
        ("T4 Rack B", (7.4, 5.1, 3.6), "shelf"),
    ]
    _G = dict(x0=-7.6, x1=-4.2, xn=-5.2, z0=3.0, h=2.1, y=0.30)

    def _shade(self, color, normal):
        s = 0.45 + 0.55 * max(0.0, float(np.dot(normal, self._LIGHT)))
        return tuple(np.clip(np.array(to_rgb(color)) * s, 0, 1))

    def _prism(self, o, ex, ey, ez, color, alpha=1.0, edge='#0f172a'):
        o, ex, ey, ez = (np.array(v, float) for v in (o, ex, ey, ez))
        c = [o + i * ex + j * ey + k * ez for k in (0, 1) for j in (0, 1) for i in (0, 1)]
        center = o + (ex + ey + ez) / 2
        ecol = to_rgb(edge) + (min(1.0, alpha + 0.3),)
        for f in ((0, 1, 3, 2), (4, 5, 7, 6), (0, 1, 5, 4), (2, 3, 7, 6), (0, 2, 6, 4), (1, 3, 7, 5)):
            pts = [c[i] for i in f]
            n = np.cross(pts[1] - pts[0], pts[3] - pts[0])
            ln = np.linalg.norm(n)
            if ln < 1e-9: continue
            n = n / ln
            if np.dot(n, np.mean(pts, axis=0) - center) < 0: n = -n
            if n[2] < -0.9: continue
            self._layers[self._layer].append(([tuple(p) for p in pts], self._shade(color, n) + (alpha,), ecol))

    def _box(self, x0, y0, z0, x1, y1, z1, color, alpha=1.0, edge='#0f172a'):
        self._prism((x0, y0, z0), (x1 - x0, 0, 0), (0, y1 - y0, 0), (0, 0, z1 - z0), color, alpha, edge)

    def _disk(self, cx, cy, z, r, color, edge='#0f172a', n=20):
        pts = [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n), z) for i in range(n)]
        self._layers[self._layer].append((pts, self._shade(color, np.array([0, 0, 1.0])) + (1.0,), to_rgb(edge) + (1.0,)))

    def _disk_v(self, cx, y, cz, r, color, edge='#0f172a', n=20):
        pts = [(cx + r * math.cos(2 * math.pi * i / n), y, cz + r * math.sin(2 * math.pi * i / n)) for i in range(n)]
        self._layers[self._layer].append((pts, self._shade(color, np.array([0, -1.0, 0])) + (1.0,), to_rgb(edge) + (1.0,)))

    def _cyl(self, cx, cy, z0, z1, r, color, n=18):
        for i in range(n):
            a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
            am = (a0 + a1) / 2
            pts = [(cx + r * math.cos(a0), cy + r * math.sin(a0), z0), (cx + r * math.cos(a1), cy + r * math.sin(a1), z0),
                   (cx + r * math.cos(a1), cy + r * math.sin(a1), z1), (cx + r * math.cos(a0), cy + r * math.sin(a0), z1)]
            self._layers[self._layer].append((pts, self._shade(color, np.array([math.cos(am), math.sin(am), 0.0])) + (1.0,), to_rgb(color) + (1.0,)))
        self._disk(cx, cy, z1, r, color, edge=color, n=n)

    def _line(self, pts, color, lw=1.0, ls='-'):
        for a, b in zip(pts[:-1], pts[1:]):
            self._lines[(color, lw, ls)].append([tuple(a), tuple(b)])

    def _text(self, x, y, z, s, color='white', size=6, weight='normal', ha='center', bbox=False):
        self._texts.append(dict(x=x, y=y, z=z, s=s, color=color, size=size, weight=weight, ha=ha, bbox=bbox))

    def _arrow(self, p, q, color, lw=1.5):
        p, q = np.array(p, float), np.array(q, float)
        d = q - p
        ln = np.linalg.norm(d)
        if ln < 1e-6: return
        d /= ln
        u = np.cross(d, [0, 0, 1.0])
        if np.linalg.norm(u) < 1e-3: u = np.cross(d, [1.0, 0, 0])
        u /= np.linalg.norm(u)
        self._line([p, q], color, lw)
        for sg in (1, -1):
            self._line([q, q - 0.28 * d + sg * 0.14 * u], color, lw)

    def _fan_v(self, cx, y, cz, r, running):
        a0 = self.step_count * 0.8 if running else 0.0
        for k in range(4):
            a = a0 + k * math.pi / 2
            self._line([(cx, y - 0.02, cz), (cx + 0.9 * r * math.cos(a), y - 0.02, cz + 0.9 * r * math.sin(a))], '#e2e8f0', 1.6)

    def _fan_h(self, cx, cy, z, r, running):
        a0 = self.step_count * 0.8 if running else 0.0
        for k in range(4):
            a = a0 + k * math.pi / 2
            self._line([(cx, cy, z + 0.02), (cx + 0.9 * r * math.cos(a), cy + 0.9 * r * math.sin(a), z + 0.02)], '#e2e8f0', 1.8)

    def _rack(self, xa, ya, rng, skip=()):
        for px in (xa, xa + 3.5):
            for py in (ya, ya + 2.7):
                self._box(px, py, 0.4, px + 0.1, py + 0.1, 4.1, '#64748b', edge='#334155')
        for zs in (0.9, 1.8, 2.7, 3.6):
            for i in range(3):
                for j in range(2):
                    tx, ty = xa + i * 1.2, ya + j * 1.4
                    self._box(tx, ty, zs - 0.05, tx + 1.2, ty + 1.4, zs, '#475569', edge='#1e293b')
                    if (zs, i, j) in skip: continue
                    h = 0.42 + 0.12 * rng.random()
                    col = '#38bdf8' if rng.random() < 0.18 else rng.choice(['#f8fafc', '#e0f2fe', '#fef3c7'])
                    self._box(tx + 0.1, ty + 0.15, zs, tx + 1.1, ty + 1.25, zs + h, col, edge='#94a3b8')
                    if j == 0:
                        lab = rng.choice(['#3b82f6', '#ef4444', '#10b981', '#f59e0b'])
                        self._box(tx + 0.25, ty + 0.13, zs + 0.1, tx + 0.95, ty + 0.15, zs + h - 0.08, lab, edge=lab)

    def _build_static_scene(self):
        rng = random.Random(7)
        G = self._G
        self._layer = 0
        for i in range(-9, 15):
            self._line([(i, -4.5, -0.29), (i, 9.0, -0.29)], '#1e293b', 0.5)
        for j in range(-4, 10):
            self._line([(-9, j, -0.29), (14.5, j, -0.29)], '#1e293b', 0.5)
        self._box(-9, -4.5, -0.3, 14.5, 9.0, -0.28, '#0f172a', edge='#1e293b')
        self._text(2.5, -4.55, -0.15, "COLDPULSE  |  AI-POWERED COLD CHAIN MONITORING", '#94a3b8', 6, 'bold')
        self._layer = 1
        self._box(0, 0, 0, 10, 8, 0.4, '#cbd5e1', edge='#64748b')
        self._layer = 2
        for k in range(8):
            xa = 0.4 + k * 1.15
            self._box(xa, 7.6, 0.4, xa + 1.15, 8.0, 6.0, '#f1f5f9', edge='#94a3b8')
            ya = k * 0.95
            self._box(0.0, ya, 0.4, 0.4, ya + 0.95, 6.0, '#e2e8f0', edge='#94a3b8')
        self._box(9.6, 0.0, 0.4, 10.0, 0.4, 6.0, '#94a3b8', edge='#475569')
        self._box(9.6, 7.6, 0.4, 10.0, 8.0, 6.0, '#94a3b8', edge='#475569')
        self._box(0.4, 0.0, 0.4, 6.0, 0.4, 0.6, '#94a3b8')
        self._box(5.9, 0.0, 0.6, 6.0, 0.4, 5.0, '#94a3b8')
        for b in ((6.0, 0, 0.4, 9.6, 0.15, 0.5), (6.0, 0, 4.9, 9.6, 0.15, 5.0),
                  (6.0, 0, 0.5, 6.12, 0.15, 4.9), (9.48, 0, 0.5, 9.6, 0.15, 4.9)):
            self._box(*b, '#0f172a', edge='#000000')
        self._box(0.7, -0.12, 5.15, 5.6, 0.0, 5.85, '#0284c7', edge='#38bdf8')
        self._text(3.15, -0.2, 5.58, "COLDPULSE", 'white', 11, 'bold')
        self._text(3.15, -0.2, 5.29, "AI Cold Chain Monitoring", '#bae6fd', 5.5)
        self._rack(0.8, 4.4, rng, skip={(2.7, 2, 0)})
        self._rack(5.6, 4.4, rng, skip={(3.6, 1, 0)})
        self._box(2.3, 4.2, 4.2, 7.7, 4.4, 4.3, '#64748b')
        for fx in (3.2, 5.0, 6.8):
            self._box(fx - 0.9, 4.4, 4.8, fx + 0.9, 7.3, 5.6, '#94a3b8', edge='#475569')
            self._box(fx - 0.9, 4.4, 4.3, fx + 0.9, 7.3, 4.8, '#0ea5e9', edge='#0284c7')
            self._disk_v(fx, 4.33, 5.2, 0.38, '#0f172a')
            self._disk_v(fx, 4.30, 5.2, 0.09, '#94a3b8')
        for k in range(5):
            z = 4.38 + k * 0.08
            self._line([(2.35, 4.36, z), (7.65, 4.36, z)], '#f59e0b', 1.4)
        for i in range(27):
            x = 2.4 + i * 0.2
            self._line([(x, 4.36, 4.33), (x, 4.36, 4.75)], '#e0f2fe', 0.5)
        for name, (sx, sy, sz), mount in self._SENSORS:
            if mount == "stem":
                self._box(sx - 0.02, sy - 0.02, sz + 0.3, sx + 0.02, sy + 0.02, 5.6, '#64748b')
            self._box(sx - 0.13, sy - 0.09, sz, sx + 0.13, sy + 0.09, sz + 0.3, '#1e293b', edge='#0f172a')
        self._box(0.4, 2.4, 3.0, 0.7, 2.7, 3.3, '#475569')
        self._box(0.7, 2.45, 3.05, 0.76, 2.65, 3.25, '#0ea5e9', edge='#38bdf8')
        self._box(0.4, 0.9, 3.7, 1.0, 1.9, 4.5, '#0f172a', edge='#38bdf8')
        self._line([(0.7, 1.4, 4.5), (0.7, 1.4, 5.3)], '#cbd5e1', 2.0)
        self._text(1.0, 2.55, 3.62, "RH 60%", '#e0f2fe', 5, bbox=True)
        self._text(1.2, 1.4, 4.85, "IoT UNIT", '#bae6fd', 5, bbox=True)
        for i, (name, (sx, sy, sz), mount) in enumerate(self._SENSORS):
            yw, zr = 1.6 + 0.4 * i, 5.45 - 0.1 * i
            self._line([(sx, sy, sz + 0.32), (sx, yw, sz + 0.32), (sx, yw, zr), (0.7, yw, zr), (0.7, 1.4, 4.5)], '#38bdf8', 0.9, '--')
        self._line([(0.7, 2.4, 3.15), (0.7, 1.9, 3.15), (0.7, 1.9, 3.7)], '#38bdf8', 0.9, '--')
        self._box(11.3, 2.1, 0.0, 13.9, 4.7, 0.25, '#1e293b')
        self._cyl(13.2, 3.4, 0.25, 1.4, 0.45, '#64748b')
        self._text(12.6, 3.4, 2.1, "COMPRESSOR", '#fca5a5', 5, bbox=True)
        for lx in (11.5, 13.7):
            for ly in (5.1, 7.7):
                self._box(lx - 0.1, ly - 0.1, 0.0, lx + 0.1, ly + 0.1, 0.6, '#334155')
        self._box(11.4, 5.0, 0.6, 13.9, 7.8, 2.4, '#cbd5e1', edge='#64748b')
        for k in range(14):
            z = 0.7 + k * 0.12
            self._line([(11.45, 4.98, z), (13.85, 4.98, z)], '#64748b', 0.6)
        self._disk(12.65, 6.4, 2.43, 1.05, '#0f172a')
        self._disk(12.65, 6.4, 2.45, 0.12, '#94a3b8')
        self._text(12.65, 6.4, 3.3, "CONDENSER", '#e2e8f0', 5, bbox=True)
        self._line([(12.0, 3.4, 1.75), (12.0, 3.4, 2.8), (12.0, 4.8, 2.8), (12.0, 4.8, 2.0), (12.0, 5.0, 2.0)], '#ef4444', 2.2)
        self._line([(13.4, 5.0, 1.0), (13.4, 4.85, 1.0), (13.4, 4.85, 5.3), (10.0, 4.85, 5.3), (7.7, 4.85, 5.3)], '#3b82f6', 2.2)
        self._line([(7.7, 6.4, 5.3), (11.0, 6.4, 5.3), (11.0, 3.4, 5.3), (11.0, 3.4, 1.0), (11.3, 3.4, 1.0)], '#93c5fd', 2.6)
        self._box(10.7, 0.0, 0.0, 12.5, 0.8, 3.0, '#64748b', edge='#334155')
        self._box(10.95, -0.06, 2.0, 12.25, 0.0, 2.75, '#020617', edge='#10b981')
        self._box(11.0, -0.05, 0.8, 11.2, 0.0, 1.0, '#ef4444')
        self._box(11.4, -0.05, 0.8, 11.6, 0.0, 1.0, '#10b981')
        self._text(11.6, 0.4, 3.3, "CONTROL PANEL", '#e2e8f0', 5, bbox=True)
        self._text(5.0, 5.85, 6.35, "EVAPORATOR + FANS", '#bae6fd', 5, bbox=True)
        self._box(-6.3, -0.5, 0.0, -3.1, 1.4, 0.15, '#1e293b')
        self._box(-4.9, 0.45, 0.15, -4.5, 0.7, 1.7, '#1e293b')
        self._box(-8.0, 0.4, 1.7, -1.5, 0.75, 5.9, '#020617', edge='#475569')
        self._box(-7.8, 0.34, 1.9, -1.7, 0.4, 5.7, '#0f172a', edge='#1e293b')
        y = G['y']
        self._text(-4.75, y, 5.52, "COLDPULSE  |  LIVE MONITOR", '#38bdf8', 8, 'bold')
        self._line([(-7.6, y, 5.35), (-1.9, y, 5.35)], '#334155', 1.0)
        gx0, gx1, z0, h = G['x0'], G['x1'], G['z0'], G['h']
        self._line([(gx0, y, z0), (gx1, y, z0), (gx1, y, z0 + h), (gx0, y, z0 + h), (gx0, y, z0)], '#64748b', 1.0)
        for t in (4.0, 8.0):
            zz = z0 + t / 12 * h
            self._line([(gx0, y, zz), (gx1, y, zz)], '#ef4444' if t == 8.0 else '#1e293b', 0.8, '--')
        self._line([(G['xn'], y, z0), (G['xn'], y, z0 + h)], '#475569', 0.8, '--')
        self._text((gx0 + G['xn']) / 2, y, z0 + h + 0.14, "TEMP vs TIME", '#64748b', 5.5)
        self._text((G['xn'] + gx1) / 2, y, z0 + h + 0.14, "FORECAST +30m", '#fcd34d', 5.5)
        self._text(gx0 - 0.02, y, z0 + 4.0 / 12 * h, "4", '#64748b', 5, ha='right')
        self._text(gx0 - 0.02, y, z0 + 8.0 / 12 * h, "8", '#fca5a5', 5, ha='right')
        self._text(-2.95, y, 5.05, "INTERNAL TEMP", '#64748b', 5.5)
        self._text(-2.95, y, 4.12, "PREDICTED (30m)", '#64748b', 5.5)
        self._text(-2.95, y, 3.28, "TREND", '#64748b', 5.5)
        for lx, lab in ((-7.4, "NORMAL"), (-6.15, "WARNING"), (-4.9, "CRITICAL")):
            self._text(lx + 0.18, y, 2.7, lab, '#94a3b8', 5.5, ha='left')
        self._text(-1.95, y, 2.7, "NODE: ROOM_01", '#475569', 5, ha='right')

    def _build_dynamic_scene(self, temp):
        G = self._G
        y = G['y']
        pred = float(self.latest_prediction)
        t_level = 0 if temp < 6.0 else (1 if temp < 8.0 else 2)
        p_level = 0 if pred < THRESHOLD - 1.0 else (1 if pred < THRESHOLD else 2)
        level = max(t_level, p_level)
        lvl_col = self._LEVEL_COLORS[level]
        tint = ['#38bdf8', '#f59e0b', '#ef4444'][t_level]
        a = [0.06, 0.12, 0.22][t_level]
        powered = self.power_status == 1
        self._layer = 3
        self._box(0.4, 0.0, 0.4, 6.0, 0.4, 6.0, tint, a, edge='#38bdf8')
        self._box(6.0, 0.0, 5.0, 9.6, 0.4, 6.0, tint, a, edge='#38bdf8')
        self._box(9.6, 0.4, 0.4, 10.0, 7.6, 6.0, tint, a, edge='#38bdf8')
        self._box(0.0, 0.0, 5.6, 10.0, 8.0, 6.0, tint, a, edge='#38bdf8')
        self._layer = 2
        th = math.radians(75 if self.door_open else 0)
        d = np.array([-math.cos(th), -math.sin(th), 0.0])
        n = np.array([math.sin(th), -math.cos(th), 0.0])
        hinge, w = np.array([9.6, 0.0, 0.4]), 3.6
        self._prism(hinge, d * w, n * 0.3, (0, 0, 4.6), '#f59e0b' if self.door_open else '#cbd5e1', 0.92, '#475569')
        self._prism(hinge + d * (w - 0.6) + n * 0.3 + np.array([0, 0, 1.7]), d * 0.15, n * 0.15, (0, 0, 1.2), '#1e293b')
        tx, ty, tz = hinge + d * (w / 2) + n * 0.45 + np.array([0, 0, 3.9])
        self._text(tx, ty, tz, "COLD ROOM  2-8 °C", '#0f172a', 5.5, 'bold')
        offs = [0.8 if self.door_open else 0.2, 0.0, -0.3, -0.2]
        for (name, (sx, sy, sz), mount), off in zip(self._SENSORS, offs):
            val = temp + off
            lv = 0 if val < 6.0 else (1 if val < 8.0 else 2)
            col = '#64748b' if self.sensor_fault else self._LEVEL_COLORS[lv]
            self._box(sx - 0.1, sy - 0.13, sz + 0.08, sx + 0.1, sy - 0.09, sz + 0.24, col, edge=col)
            lab = f"{name} ERR" if self.sensor_fault else f"{name} {val:.1f}°C"
            self._text(sx, sy - 0.2, sz - 0.2, lab, 'white', 5, bbox=True)
        self._box(1.0, 1.0, 4.25, 1.05, 1.1, 4.35, lvl_col, edge=lvl_col)
        self._cyl(12.0, 3.4, 0.25, 1.6, 0.7, '#2563eb' if self.compressor_status else '#ef4444')
        self._cyl(12.0, 3.4, 1.6, 1.75, 0.35, '#e2e8f0')
        for fx in (3.2, 5.0, 6.8):
            self._fan_v(fx, 4.30, 5.2, 0.38, powered and self.compressor_status)
        self._fan_h(12.65, 6.4, 2.45, 1.05, bool(self.compressor_status))
        for i, lx in enumerate((11.2, 11.7, 12.2)):
            on_col = self._LEVEL_COLORS[i]
            dim = ['#064e3b', '#451a03', '#450a0a'][i]
            c = on_col if level == i else dim
            self._box(lx - 0.1, -0.05, 1.55, lx + 0.1, 0.0, 1.8, c, edge=c)
        disp = "ERR" if self.sensor_fault else f"{self.internal_temp:.1f}°C"
        self._text(11.6, -0.12, 2.38, disp, '#34d399' if not self.sensor_fault else '#ef4444', 11, 'bold')
        if powered and self.compressor_status:
            path = [np.array(p, float) for p in ((4.2, 5.1), (1.0, 5.1), (1.0, 0.8), (7.4, 0.8), (7.4, 5.1), (4.2, 5.1))]
            segs = [np.linalg.norm(b - a_) for a_, b in zip(path[:-1], path[1:])]
            total = sum(segs)
            def at(s):
                s %= total
                for a_, b, l in zip(path[:-1], path[1:], segs):
                    if s <= l: return a_ + (b - a_) * (s / l)
                    s -= l
                return path[-1]
            spacing = 2.4
            off = (self.step_count * 0.5) % spacing
            for lane in (2.6, 5.0, 7.4):
                for k in range(int(total // spacing) + 1):
                    p0, p1 = at(off + k * spacing), at(off + k * spacing + 0.9)
                    self._arrow((lane, p0[0], p0[1]), (lane, p1[0], p1[1]), '#38bdf8', 1.8)
        if self.door_open:
            y0 = -2.6 + (self.step_count * 0.35) % 1.0
            for z in (1.2, 2.4, 3.6):
                self._arrow((7.6, y0, z), (7.6, y0 + 1.4, z), '#f97316', 2.0)
                self._arrow((7.6, 0.9, z), (7.6, 2.2, z), '#f97316', 2.0)
        temps, last = [], 4.0
        for r in list(self.history)[-30:]:
            v = r.get("internal_temp_c", np.nan)
            if v is None or (isinstance(v, float) and np.isnan(v)): v = last
            last = float(v)
            temps.append(last)
        def gz(t): return G['z0'] + min(max(t, 0.0), 12.0) / 12.0 * G['h']
        if len(temps) >= 2:
            nn = len(temps)
            pts = [(G['x0'] + (G['xn'] - G['x0']) * (30 - nn + i) / 29.0, y, gz(t)) for i, t in enumerate(temps)]
            self._line(pts, '#38bdf8', 2.0)
            self._line([pts[-1], (G['x1'], y, gz(pred))], '#fcd34d', 2.0, '--')
            self._text(G['x1'], y, gz(pred), "●", lvl_col, 8)
            trend = temps[-1] - temps[-2]
        else:
            trend = 0.0
        self._text(-2.95, y, 4.62, "FAULT" if self.sensor_fault else f"{temp:.1f}°C",
                   '#ef4444' if self.sensor_fault else self._LEVEL_COLORS[t_level], 14, 'bold')
        self._text(-2.95, y, 3.78, f"{pred:.1f}°C", self._LEVEL_COLORS[p_level], 12, 'bold')
        self._text(-2.95, y, 3.02, f"{trend:+.2f}°C/10m", '#cbd5e1', 8)
        for i, lx in enumerate((-7.4, -6.15, -4.9)):
            dim = ['#064e3b', '#451a03', '#450a0a'][i]
            self._text(lx, y, 2.7, "●", self._LEVEL_COLORS[i] if level == i else dim, 15)
        msg = ["SYSTEM NORMAL - NO EXCURSION RISK", "WARNING - MONITOR CLOSELY", "EARLY WARNING: EXCURSION IN ~30 MIN"][level]
        bar = lvl_col if not (level == 2 and self.step_count % 2) else '#7f1d1d'
        self._line([(-7.6, y, 2.05), (-1.9, y, 2.05), (-1.9, y, 2.4), (-7.6, y, 2.4), (-7.6, y, 2.05)], bar, 2.0)
        self._text(-4.75, y, 2.22, msg, bar, 6.5, 'bold')

    def draw_realistic_3d_twin(self, temp):
        ax = self.ax
        ax.clear()
        ax.set_axis_off()
        ax.computed_zorder = False
        if not hasattr(self, "_static_scene"):
            self._layers = {0: [], 1: [], 2: [], 3: []}
            self._lines, self._texts, self._layer = defaultdict(list), [], 2
            self._build_static_scene()
            self._static_scene = ({k: list(v) for k, v in self._layers.items()},
                                  {k: list(v) for k, v in self._lines.items()}, list(self._texts))
        layers, lines, texts = self._static_scene
        self._layers = {k: list(v) for k, v in layers.items()}
        self._lines = defaultdict(list, {k: list(v) for k, v in lines.items()})
        self._texts, self._layer = list(texts), 2
        self._build_dynamic_scene(temp)
        for layer, zo in ((0, 0.0), (1, 0.5), (2, 1.0), (3, 1.5)):
            faces = self._layers[layer]
            if not faces: continue
            pc = Poly3DCollection([f[0] for f in faces], facecolors=[f[1] for f in faces],
                                  edgecolors=[f[2] for f in faces], linewidths=0.5)
            ax.add_collection3d(pc)
            pc.set_zorder(zo)
        for (color, lw, ls), segs in self._lines.items():
            lc = Line3DCollection(segs, colors=color, linewidths=lw, linestyles=ls)
            ax.add_collection3d(lc)
            lc.set_zorder(5)
        for t in self._texts:
            kw = dict(color=t['color'], fontsize=t['size'], fontweight=t['weight'],
                      ha=t['ha'], va='center', zorder=10)
            if t['bbox']:
                kw['bbox'] = dict(boxstyle='round,pad=0.2', fc='#0f172a', ec='#334155', alpha=0.85)
            ax.text(t['x'], t['y'], t['z'], t['s'], **kw)
        ax.set_xlim([-9, 14.5])
        ax.set_ylim([-4.5, 9])
        ax.set_zlim([-0.3, 7])
        try:
            ax.set_box_aspect((23.5, 13.5, 7.3), zoom=1.4)
        except TypeError:
            ax.set_box_aspect((23.5, 13.5, 7.3))
        ax.view_init(elev=28, azim=-55)
        self.canvas.draw()

    # --- Control Toggles ---
    def toggle_power(self):
        self.power_status = 1 - self.power_status
        self.btn_power.config(text=f"⚡ POWER: {'ON' if self.power_status else 'CUT'}")
        if self.power_status == 0: self.power_cut_step = self.step_count
        self.log_msg(f"[SYSTEM] Power toggled to {'ON' if self.power_status else 'CUT'}")

    def toggle_door(self):
        self.door_open = 1 - self.door_open
        self.btn_door.config(text=f"🚪 DOOR: {'OPEN' if self.door_open else 'CLOSED'}")
        if self.door_open: self.door_open_step = self.step_count
        else: self.door_closed_step = self.step_count
        self.log_msg(f"[SYSTEM] Door toggled to {'OPEN' if self.door_open else 'CLOSED'}")

    def toggle_defrost(self):
        self.defrost_cycle = 1 - self.defrost_cycle
        self.btn_defrost.config(text=f"❄️ DEFROST: {'ON' if self.defrost_cycle else 'OFF'}")
        self.log_msg(f"[SYSTEM] Defrost toggled to {'ON' if self.defrost_cycle else 'OFF'}")

    def toggle_fault(self):
        self.sensor_fault = 1 - self.sensor_fault
        self.btn_fault.config(text=f"⚠️ SENSOR FAULT: {'YES' if self.sensor_fault else 'NO'}")
        self.log_msg(f"[SYSTEM] Sensor fault toggled to {'YES' if self.sensor_fault else 'NO'}")

    def trigger_load(self):
        self.load_change += 20.0
        self.log_msg(f"[SYSTEM] Added 20kg warm stock. Total load: {self.load_change}kg")

    # ==================================================
    #  PHYSICS ENGINE
    # ==================================================
    def update_simulation(self):
        self.step_count += 1
        hour = (self.step_count * 10 // 60) % 24
        self.ambient_temp = 25.0 + 8.0 * np.sin(np.pi * (hour - 6) / 12)

        if self.power_status == 1 and self.defrost_cycle == 0:
            if self.internal_temp > THERMOSTAT_ON:
                if self.compressor_status == 0:
                    self.compressor_start_step = self.step_count
                self.compressor_status = 1
            elif self.internal_temp < THERMOSTAT_OFF:
                self.compressor_status = 0
        else:
            self.compressor_status = 0

        heat_leak = HEAT_LEAK_COEF * (self.ambient_temp - self.internal_temp)
        door_heat = DOOR_HEAT_COEF * (self.ambient_temp - self.internal_temp) if self.door_open else 0
        defrost_heat = DEFROST_HEAT_RATE if self.defrost_cycle else 0
        load_heat = 0.05 * self.load_change

        if self.compressor_status:
            cooling = -min(COOLING_MAX,
                           COOLING_BASE + max(0.0, self.internal_temp - SETPOINT) * COOLING_GAIN)
        else:
            cooling = 0.0

        delta = (heat_leak + door_heat + defrost_heat + cooling
                 + load_heat + random.uniform(-0.02, 0.02))
        self.internal_temp = round(
            max(-5.0, min(40.0, self.internal_temp + delta)), 2
        )

        if self.load_change > 0:
            self.load_change = max(0.0, self.load_change - 2.0)

        current_row = {
            "timestamp": pd.Timestamp.now(),
            "room_id": 0,
            "hour_of_day": hour,
            "day_of_week": (self.step_count // 144) % 7,
            "internal_temp_c": np.nan if self.sensor_fault else self.internal_temp,
            "ambient_temp_c": self.ambient_temp,
            "ambient_humidity_pct": 60.0,
            "solar_radiation_wm2": max(0, 800 * np.sin(np.pi * (hour - 6) / 12)),
            "wind_speed_kmh": 10.0,
            "setpoint_temp_c": SETPOINT,
            "door_open": self.door_open,
            "power_status": self.power_status,
            "compressor_status": self.compressor_status,
            "defrost_cycle": self.defrost_cycle,
            "sensor_fault": self.sensor_fault,
            "load_change_kg": self.load_change,
            "door_openings_planned": 0,
        }

        self.history.append(current_row)

        if len(self.history) >= 6:
            df = pd.DataFrame(self.history)
            current_row["temp_diff_10m"] = float(df['internal_temp_c'].iloc[-1] - df['internal_temp_c'].iloc[-2])
            current_row["temp_diff_30m"] = float(df['internal_temp_c'].iloc[-1] - df['internal_temp_c'].iloc[-4])
            current_row["temp_rolling_mean_30m"] = float(df['internal_temp_c'].iloc[-4:].mean())
            std_val = df['internal_temp_c'].iloc[-4:].std()
            current_row["temp_rolling_std_30m"] = float(std_val) if not pd.isna(std_val) else 0.0
            current_row["internal_vs_setpoint_diff"] = float(df['internal_temp_c'].iloc[-1] - SETPOINT)

            current_row["power_outage_duration_min"] = float((self.step_count - self.power_cut_step) * 10) if self.power_status == 0 else 0.0
            current_row["time_since_power_cut_min"] = float((self.step_count - self.power_cut_step) * 10) if self.power_status == 1 and self.power_cut_step > -999 else 9999.0
            current_row["door_open_duration_min"] = float((self.step_count - self.door_open_step) * 10) if self.door_open else 0.0
            current_row["time_since_door_closed_min"] = float((self.step_count - self.door_closed_step) * 10) if not self.door_open else 0.0
            current_row["compressor_runtime_min"] = float((self.step_count - self.compressor_start_step) * 10) if self.compressor_status else 0.0
            current_row["time_since_compressor_start_min"] = float((self.step_count - self.compressor_start_step) * 10) if self.compressor_status else 9999.0

            current_row["door_open_count_last_1h"] = float(df['door_open'].rolling(window=6).sum().iloc[-1])
            current_row["compressor_runtime_min_last_1h"] = float(df['compressor_status'].rolling(window=6).sum().iloc[-1] * 10)

            self.make_prediction(current_row)
            self.update_ui(current_row)

        self.root.after(1000, self.update_simulation)

    def make_prediction(self, features):
        if USE_REAL_MODEL:
            if hasattr(model, "feature_names_in_"):
                feature_cols = model.feature_names_in_
            elif hasattr(model, "feature_name_"):
                feature_cols = model.feature_name_
            else:
                feature_cols = list(features.keys())
        else:
            feature_cols = [
                'hour_of_day', 'day_of_week', 'internal_temp_c', 'ambient_temp_c',
                'ambient_humidity_pct', 'solar_radiation_wm2', 'wind_speed_kmh',
                'setpoint_temp_c', 'door_open', 'power_status', 'compressor_status',
                'defrost_cycle', 'sensor_fault', 'load_change_kg', 'door_openings_planned',
                'temp_diff_10m', 'temp_diff_30m', 'temp_rolling_mean_30m', 'temp_rolling_std_30m',
                'internal_vs_setpoint_diff', 'power_outage_duration_min', 'time_since_power_cut_min',
                'door_open_duration_min', 'time_since_door_closed_min', 'compressor_runtime_min',
                'door_open_count_last_1h', 'compressor_runtime_min_last_1h'
            ]
        X = np.array([[float(features.get(col, np.nan)) for col in feature_cols]])

        if USE_REAL_MODEL:
            try:
                pred = model.predict(X)[0]
            except Exception as e:
                print(f"Model prediction error: {e}")
                pred = self.internal_temp
        else:
            if self.sensor_fault: pred = 4.0
            elif self.power_status == 0 or self.door_open or self.load_change > 0:
                trend = features.get('temp_diff_10m', 0) or 0.1
                pred = self.internal_temp + (trend * 4) + 0.5
            else:
                pred = self.internal_temp + (features.get('temp_diff_10m', 0) * 2)

        pred = round(float(pred), 2)
        self.latest_prediction = pred

        # ═══════════════════════════════════════════════════════════
        # ⭐ SEND TO DJANGO (this was the missing piece!)
        # ═══════════════════════════════════════════════════════════
        if pred >= THRESHOLD:
            risk_level = "HIGH"
        elif pred >= THRESHOLD - 1.0:
            risk_level = "MEDIUM"
        else:
            risk_level = "SAFE"

        payload = {
            "room_id": "ROOM_01",
            # NaN is not valid JSON → convert to None (null in JSON)
            "internal_temp_c": None if self.sensor_fault else float(self.internal_temp),
            "ambient_temp_c": float(self.ambient_temp),
            "ambient_humidity_pct": 60.0,
            "door_open": bool(self.door_open),
            "power_status": bool(self.power_status),
            "compressor_status": bool(self.compressor_status),
            "predicted_temp_30m": float(pred),
            "risk_level": risk_level,
        }
        threading.Thread(target=send_to_django, args=(payload,), daemon=True).start()

        # --- Logging ---
        log_msg = f"Step {self.step_count:03d} | T:{self.internal_temp:5.2f}°C | Comp:{self.compressor_status} | P:{self.power_status} | D:{self.door_open} | Δ:{features.get('temp_diff_10m', 0):+.2f}"
        if pred >= THRESHOLD:
            self.log_msg(log_msg, "danger")
            self.log_msg(f"🚨 HIGH RISK: Predicted {pred}°C in 30m!", "danger")
            if self.power_status == 0: self.log_msg("   -> Cause: Power Cut", "warn")
            if self.door_open: self.log_msg("   -> Cause: Door Open", "warn")
            if self.load_change > 0: self.log_msg("   -> Cause: Warm Load", "warn")
        elif pred >= THRESHOLD - 1.0:
            self.log_msg(log_msg, "warn")
        else:
            self.log_msg(log_msg, "safe")

    def update_ui(self, features):
        temp = features['internal_temp_c']
        pred = getattr(self, 'latest_prediction', temp)
        self.lbl_ai_temp.config(text=f"Current: {temp if not self.sensor_fault else 'FAULT'} °C")
        self.lbl_ai_pred.config(text=f"Predicted (30m): {pred} °C")
        if pred >= THRESHOLD:
            self.lbl_ai_risk.config(text="RISK: HIGH", fg=DANGER)
            self.lbl_header_status.config(text="🔴 CRITICAL WARNING", fg=DANGER)
        elif pred >= THRESHOLD - 1.0:
            self.lbl_ai_risk.config(text="RISK: MEDIUM", fg=WARN)
            self.lbl_header_status.config(text="🟡 SYSTEM WARNING", fg=WARN)
        else:
            self.lbl_ai_risk.config(text="RISK: SAFE", fg=SUCCESS)
            self.lbl_header_status.config(text="🟢 SYSTEM NORMAL", fg=SUCCESS)
        self.draw_realistic_3d_twin(temp if not self.sensor_fault else 20.0)


if __name__ == "__main__":
    root = tk.Tk()
    app = DigitalTwinApp(root)
    root.mainloop()