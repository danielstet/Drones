# liftoff_calibration_hotkeys_gui_explained.py
# Global hotkeys + Visual dashboard + explanations (legend) for what each axis / hotkey means.

import pyvjoy
import time
import math
import sys
import threading

try:
    import keyboard
except ImportError:
    print("Missing dependency: keyboard. Install with: pip install keyboard")
    sys.exit(1)

try:
    import tkinter as tk
    from tkinter import ttk
    GUI_AVAILABLE = True
except Exception:
    GUI_AVAILABLE = False

# --- CONFIGURATION ---
DEVICE_ID = 1

# vJoy range (common)
MIN_VAL = 1
MAX_VAL = 32768
MID_VAL = 16384

# Circle radius around MID (used for calibration circles)
RADIUS = 16000

# --- AXIS MAPPING (your mapping) ---
# Left stick:  Horizontal = Yaw, Vertical = Throttle
# Right stick: Horizontal = Roll, Vertical = Pitch
AXIS_LEFT_H  = pyvjoy.HID_USAGE_RX  # Yaw (turn left/right)
AXIS_LEFT_V  = pyvjoy.HID_USAGE_Z   # Throttle (power up/down)
AXIS_RIGHT_H = pyvjoy.HID_USAGE_X   # Roll (tilt left/right)
AXIS_RIGHT_V = pyvjoy.HID_USAGE_Y   # Pitch (tilt forward/back)

try:
    joystick = pyvjoy.VJoyDevice(DEVICE_ID)
except Exception as e:
    print(f"Error initializing vJoy: {e}")
    sys.exit(1)

# --- Thread control ---
current_thread = None
stop_event = threading.Event()
thread_lock = threading.Lock()

# --- Visual feedback state (what we LAST wrote to vJoy) ---
axis_state_lock = threading.Lock()
axis_state = {
    AXIS_LEFT_H: MID_VAL,
    AXIS_LEFT_V: MIN_VAL,   # "safe" default like real throttle down
    AXIS_RIGHT_H: MID_VAL,
    AXIS_RIGHT_V: MID_VAL,
}

current_mode_lock = threading.Lock()
current_mode = "IDLE / DISARM"
last_update_ts = 0.0

# GUI globals (so we can toggle topmost)
gui_root = None
gui_topmost = True


def _set_mode(name: str):
    global current_mode
    with current_mode_lock:
        current_mode = name


def _touch_update():
    global last_update_ts
    last_update_ts = time.time()


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def set_axis(axis_id, value):
    """
    Writes to vJoy AND updates local state for GUI.

    IMPORTANT:
    - MIN_VAL..MAX_VAL is the raw range of the axis.
    - MID_VAL is the "center" for Roll/Pitch/Yaw.
    - Throttle in a real drone is usually MIN when not armed,
      BUT calibration sometimes wants "center" too (MID).
    """
    val = int(clamp(value, MIN_VAL, MAX_VAL))
    joystick.set_axis(axis_id, val)
    with axis_state_lock:
        axis_state[axis_id] = val
    _touch_update()


def center_for_calibration():
    """
    Centers ALL axes to MID (useful during calibration steps).

    Note: For a REAL drone throttle you usually keep MIN when disarmed,
    but calibration screens often want you to "center" everything,
    so here we set throttle to MID too.
    """
    set_axis(AXIS_LEFT_H, MID_VAL)
    set_axis(AXIS_LEFT_V, MID_VAL)   # calibration center
    set_axis(AXIS_RIGHT_H, MID_VAL)
    set_axis(AXIS_RIGHT_V, MID_VAL)


def disarm_safe():
    """
    Safety stop (like a real radio disarm):
    - Throttle DOWN (MIN)
    - All others centered (MID)
    """
    set_axis(AXIS_LEFT_H, MID_VAL)     # yaw center
    set_axis(AXIS_RIGHT_H, MID_VAL)    # roll center
    set_axis(AXIS_RIGHT_V, MID_VAL)    # pitch center
    set_axis(AXIS_LEFT_V, MIN_VAL)     # throttle minimum


def stop_pattern():
    global current_thread
    with thread_lock:
        if current_thread and current_thread.is_alive():
            stop_event.set()
            current_thread.join(timeout=1.5)
        current_thread = None
        stop_event.clear()
    disarm_safe()
    _set_mode("IDLE / DISARM")
    print("[HOTKEY] STOP + DISARM (Throttle down)")


def start_pattern(worker_func, name: str):
    global current_thread

    # stop any current worker
    stop_pattern()

    def runner():
        _set_mode(f"RUNNING: {name}")
        print(f"[HOTKEY] START: {name}")
        try:
            worker_func(stop_event)
        finally:
            disarm_safe()
            _set_mode("IDLE / DISARM")
            print(f"[HOTKEY] END: {name}")

    with thread_lock:
        stop_event.clear()
        current_thread = threading.Thread(target=runner, daemon=True)
        current_thread.start()


# --- WORKERS (each accepts stop_event) ---
def circles_worker(ev: threading.Event):
    """
    Moves BOTH sticks in circles to show the calibration screen
    the full range of motion.
    """
    angle = 0.0
    step = 0.1
    while not ev.is_set():
        ls_x = math.cos(angle)
        ls_y = math.sin(angle)
        rs_x = math.cos(angle)
        rs_y = -math.sin(angle)

        set_axis(AXIS_LEFT_H,  MID_VAL + int(ls_x * RADIUS))  # yaw circle
        set_axis(AXIS_LEFT_V,  MID_VAL + int(ls_y * RADIUS))  # throttle circle (around MID for calibration)
        set_axis(AXIS_RIGHT_H, MID_VAL + int(rs_x * RADIUS))  # roll circle
        set_axis(AXIS_RIGHT_V, MID_VAL + int(rs_y * RADIUS))  # pitch circle

        angle += step
        time.sleep(0.01)


def throttle_up_worker(ev: threading.Event):
    """
    Throttle UP to 100% (MAX), then back to MID (calibration).
    """
    set_axis(AXIS_LEFT_H, MID_VAL)
    set_axis(AXIS_RIGHT_H, MID_VAL)
    set_axis(AXIS_RIGHT_V, MID_VAL)

    while not ev.is_set():
        for i in range(MID_VAL, MAX_VAL, 1000):
            if ev.is_set(): return
            set_axis(AXIS_LEFT_V, i)
            time.sleep(0.01)

        set_axis(AXIS_LEFT_V, MAX_VAL)
        time.sleep(0.4)
        set_axis(AXIS_LEFT_V, MID_VAL)
        time.sleep(0.3)


def pitch_up_worker(ev: threading.Event):
    """
    Pitch UP to 100% (MAX), then back to MID.
    """
    set_axis(AXIS_LEFT_H, MID_VAL)
    set_axis(AXIS_LEFT_V, MID_VAL)
    set_axis(AXIS_RIGHT_H, MID_VAL)

    while not ev.is_set():
        for i in range(MID_VAL, MAX_VAL, 1000):
            if ev.is_set(): return
            set_axis(AXIS_RIGHT_V, i)
            time.sleep(0.01)

        set_axis(AXIS_RIGHT_V, MAX_VAL)
        time.sleep(0.4)
        set_axis(AXIS_RIGHT_V, MID_VAL)
        time.sleep(0.3)


def roll_right_worker(ev: threading.Event):
    """
    Roll RIGHT to 100% (MAX), then back to MID.
    """
    set_axis(AXIS_LEFT_H, MID_VAL)
    set_axis(AXIS_LEFT_V, MID_VAL)
    set_axis(AXIS_RIGHT_V, MID_VAL)

    while not ev.is_set():
        for i in range(MID_VAL, MAX_VAL, 1000):
            if ev.is_set(): return
            set_axis(AXIS_RIGHT_H, i)
            time.sleep(0.01)

        set_axis(AXIS_RIGHT_H, MAX_VAL)
        time.sleep(0.4)
        set_axis(AXIS_RIGHT_H, MID_VAL)
        time.sleep(0.3)


def yaw_left_worker(ev: threading.Event):
    """
    Yaw LEFT to 100% (MIN), then back to MID.
    """
    set_axis(AXIS_LEFT_V, MID_VAL)
    set_axis(AXIS_RIGHT_H, MID_VAL)
    set_axis(AXIS_RIGHT_V, MID_VAL)

    while not ev.is_set():
        for i in range(MID_VAL, MIN_VAL, -1000):
            if ev.is_set(): return
            set_axis(AXIS_LEFT_H, i)
            time.sleep(0.01)

        set_axis(AXIS_LEFT_H, MIN_VAL)
        time.sleep(0.4)
        set_axis(AXIS_LEFT_H, MID_VAL)
        time.sleep(0.3)


def throttle_down_worker(ev: threading.Event):
    """
    Throttle DOWN to 0% (MIN), then back to MID (calibration).
    """
    set_axis(AXIS_LEFT_H, MID_VAL)
    set_axis(AXIS_RIGHT_H, MID_VAL)
    set_axis(AXIS_RIGHT_V, MID_VAL)

    while not ev.is_set():
        for i in range(MID_VAL, MIN_VAL, -1000):
            if ev.is_set(): return
            set_axis(AXIS_LEFT_V, i)
            time.sleep(0.01)

        set_axis(AXIS_LEFT_V, MIN_VAL)
        time.sleep(0.4)
        set_axis(AXIS_LEFT_V, MID_VAL)
        time.sleep(0.3)


def print_hotkeys():
    print("\n=== Liftoff Calibration Hotkeys (Meaning) ===")
    print("F8  : Circles -> moves sticks in full circles (range test)")
    print("F1  : Throttle UP -> left stick vertical to max (100%)")
    print("F2  : Pitch UP    -> right stick vertical to max (100%)")
    print("F3  : Roll RIGHT  -> right stick horizontal to max (100%)")
    print("F4  : Yaw LEFT    -> left stick horizontal to min (100% left)")
    print("F5  : Throttle DOWN -> left stick vertical to min (0%)")
    print("F9  : EMERGENCY STOP -> stop + disarm (Throttle MIN)")
    print("F10 : Center for calibration -> set ALL axes to MID")
    print("ESC : Exit script")
    print("============================================\n")


# ---------------- GUI helpers ----------------
def val_to_roll_pitch_yaw_percent(val: int) -> int:
    """
    For Roll/Pitch/Yaw:
    MID -> 0%
    MIN -> -100%
    MAX -> +100%
    """
    if val >= MID_VAL:
        return int(100 * (val - MID_VAL) / (MAX_VAL - MID_VAL))
    else:
        return int(-100 * (MID_VAL - val) / (MID_VAL - MIN_VAL))


def val_to_throttle_percent(val: int) -> int:
    """
    For Throttle:
    MIN -> 0%
    MAX -> 100%
    """
    return int(100 * (val - MIN_VAL) / (MAX_VAL - MIN_VAL))


def toggle_topmost():
    global gui_root, gui_topmost
    if gui_root is None:
        print("[HOTKEY] GUI not running.")
        return
    gui_topmost = not gui_topmost
    try:
        gui_root.attributes("-topmost", gui_topmost)
    except Exception:
        pass
    print(f"[HOTKEY] GUI topmost = {gui_topmost}")


def gui_thread():
    global gui_root, gui_topmost

    if not GUI_AVAILABLE:
        return

    root = tk.Tk()
    gui_root = root
    root.title("vJoy Calibration Dashboard + Legend")

    # start topmost ON
    try:
        root.attributes("-topmost", True)
    except Exception:
        pass

    style = ttk.Style()
    try:
        style.theme_use("clam")
    except Exception:
        pass

    mode_var = tk.StringVar(value="IDLE / DISARM")
    info_var = tk.StringVar(value="")

    frm = ttk.Frame(root, padding=10)
    frm.grid(row=0, column=0, sticky="nsew")

    # Header
    ttk.Label(frm, text="Current Mode:", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="w")
    ttk.Label(frm, textvariable=mode_var, font=("Segoe UI", 11)).grid(row=0, column=1, sticky="w", padx=8)

    # Bars (values)
    ttk.Label(frm, text="Yaw (RX)  = turn left/right").grid(row=1, column=0, sticky="w")
    yaw_bar = ttk.Progressbar(frm, length=260, maximum=200)  # center=100
    yaw_bar.grid(row=1, column=1, sticky="w")
    yaw_txt = ttk.Label(frm, text="0%")
    yaw_txt.grid(row=1, column=2, sticky="w", padx=8)

    ttk.Label(frm, text="Throttle (Z) = power / up-down").grid(row=2, column=0, sticky="w")
    thr_bar = ttk.Progressbar(frm, length=260, maximum=100)
    thr_bar.grid(row=2, column=1, sticky="w")
    thr_txt = ttk.Label(frm, text="0%")
    thr_txt.grid(row=2, column=2, sticky="w", padx=8)

    ttk.Label(frm, text="Roll (X) = strafe/tilt left-right").grid(row=3, column=0, sticky="w")
    roll_bar = ttk.Progressbar(frm, length=260, maximum=200)
    roll_bar.grid(row=3, column=1, sticky="w")
    roll_txt = ttk.Label(frm, text="0%")
    roll_txt.grid(row=3, column=2, sticky="w", padx=8)

    ttk.Label(frm, text="Pitch (Y) = forward/back tilt").grid(row=4, column=0, sticky="w")
    pitch_bar = ttk.Progressbar(frm, length=260, maximum=200)
    pitch_bar.grid(row=4, column=1, sticky="w")
    pitch_txt = ttk.Label(frm, text="0%")
    pitch_txt.grid(row=4, column=2, sticky="w", padx=8)

    # Raw values line
    raw_var = tk.StringVar(value="")
    ttk.Label(frm, textvariable=raw_var).grid(row=5, column=0, columnspan=3, sticky="w", pady=(6, 0))

    ttk.Separator(frm).grid(row=6, column=0, columnspan=3, sticky="ew", pady=8)

    # Legend / Explanations
    legend_text = (
        "What do the % mean?\n"
        "• Roll/Pitch/Yaw: 0% = center (MID). -100% = full left/down (MIN). +100% = full right/up (MAX).\n"
        "• Throttle: 0% = MIN (stick fully down). 100% = MAX (stick fully up).\n\n"
        "Hotkeys:\n"
        "• F8  Circles: moves sticks in circles (shows full range to calibration).\n"
        "• F1  Throttle UP: throttle to MAX then back to MID.\n"
        "• F2  Pitch UP: pitch to MAX then back to MID.\n"
        "• F3  Roll RIGHT: roll to MAX then back to MID.\n"
        "• F4  Yaw LEFT: yaw to MIN then back to MID.\n"
        "• F5  Throttle DOWN: throttle to MIN then back to MID.\n"
        "• F9  EMERGENCY: stop + disarm (Throttle MIN) — use anytime.\n"
        "• F10 Center: puts ALL axes on MID for calibration step.\n"
        "• F12 Toggle Topmost: keep this window on top.\n"
        "• ESC Exit.\n"
    )
    legend = ttk.Label(frm, text=legend_text, justify="left", wraplength=760)
    legend.grid(row=7, column=0, columnspan=3, sticky="w")

    ttk.Separator(frm).grid(row=8, column=0, columnspan=3, sticky="ew", pady=8)
    ttk.Label(frm, textvariable=info_var, font=("Segoe UI", 10, "bold")).grid(row=9, column=0, columnspan=3, sticky="w")

    def refresh():
        with current_mode_lock:
            mode_var.set(current_mode)

        with axis_state_lock:
            yaw_v = axis_state[AXIS_LEFT_H]
            thr_v = axis_state[AXIS_LEFT_V]
            roll_v = axis_state[AXIS_RIGHT_H]
            pitch_v = axis_state[AXIS_RIGHT_V]

        yaw_p = val_to_roll_pitch_yaw_percent(yaw_v)
        roll_p = val_to_roll_pitch_yaw_percent(roll_v)
        pitch_p = val_to_roll_pitch_yaw_percent(pitch_v)
        thr_p = val_to_throttle_percent(thr_v)

        yaw_bar["value"] = 100 + yaw_p
        roll_bar["value"] = 100 + roll_p
        pitch_bar["value"] = 100 + pitch_p
        thr_bar["value"] = thr_p

        yaw_txt.config(text=f"{yaw_p:+d}%")
        roll_txt.config(text=f"{roll_p:+d}%")
        pitch_txt.config(text=f"{pitch_p:+d}%")
        thr_txt.config(text=f"{thr_p:d}%")

        raw_var.set(
            f"Raw values: Yaw={yaw_v}  Throttle={thr_v}  Roll={roll_v}  Pitch={pitch_v} "
            f"(MIN={MIN_VAL}, MID={MID_VAL}, MAX={MAX_VAL})"
        )

        age = time.time() - last_update_ts if last_update_ts else 0.0
        info_var.set(f"Last update: {age:.2f}s ago | F9 = EMERGENCY STOP (Throttle down)")

        root.after(50, refresh)

    refresh()
    root.mainloop()


def main():
    disarm_safe()
    print_hotkeys()

    # Start GUI (optional)
    if GUI_AVAILABLE:
        threading.Thread(target=gui_thread, daemon=True).start()
        print("[INFO] GUI dashboard started (move it to 2nd monitor if you can).")
    else:
        print("[INFO] GUI not available. Use vJoy Monitor / Game Controllers for visual feedback.")

    # Register hotkeys (global)
    keyboard.add_hotkey("F8",  lambda: start_pattern(circles_worker, "Circles (full range)"))
    keyboard.add_hotkey("F1",  lambda: start_pattern(throttle_up_worker, "Throttle UP (to MAX)"))
    keyboard.add_hotkey("F2",  lambda: start_pattern(pitch_up_worker, "Pitch UP (to MAX)"))
    keyboard.add_hotkey("F3",  lambda: start_pattern(roll_right_worker, "Roll RIGHT (to MAX)"))
    keyboard.add_hotkey("F4",  lambda: start_pattern(yaw_left_worker, "Yaw LEFT (to MIN)"))
    keyboard.add_hotkey("F5",  lambda: start_pattern(throttle_down_worker, "Throttle DOWN (to MIN)"))
    #m
    keyboard.add_hotkey("F9",  stop_pattern)
    keyboard.add_hotkey("F10", lambda: (stop_pattern(), center_for_calibration(), _set_mode("CENTER (MID for calibration)"), print("[HOTKEY] CENTER (MID)")))
    keyboard.add_hotkey("F12", toggle_topmost)

    # wait until ESC
    keyboard.wait("esc")
    stop_pattern()
    print("[HOTKEY] EXIT")


if __name__ == "__main__":
    main()
