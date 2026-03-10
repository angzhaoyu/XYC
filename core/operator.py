"""
操作器：支持 SendMessage（后台）和 pyautogui（前台）两种模式
SendMessage 模式：不需要鼠标锁，真正并行
"""
import ctypes
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

import numpy as np
import pyautogui
import random
import time
import json
import win32gui
import win32con
import win32api
from pathlib import Path
from contextlib import contextmanager

from window.window_manager import WindowManager
from core.screen_capture import ScreenCapture

pyautogui.FAILSAFE = False


def random_duration(min_time, max_time, use_gauss=True):
    if use_gauss:
        mean = (min_time + max_time) / 2
        std_dev = (max_time - min_time) / 6
        while True:
            d = np.random.normal(mean, std_dev)
            if min_time <= d <= max_time:
                return d
    return random.uniform(min_time, max_time)


def sample_point_in_box(box, sigma_ratio=0.1):
    (x1, y1), (x2, y2) = box
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    sx = abs(x2 - x1) * sigma_ratio
    sy = abs(y2 - y1) * sigma_ratio
    xn, xx = min(x1, x2), max(x1, x2)
    yn, yx = min(y1, y2), max(y1, y2)
    for _ in range(100):
        gx = np.random.normal(cx, sx)
        gy = np.random.normal(cy, sy)
        if xn <= gx <= xx and yn <= gy <= yx:
            return [gx, gy]
    return [np.clip(gx, xn, xx), np.clip(gy, yn, yx)]


def _make_lparam(x, y):
    return (int(y) << 16) | (int(x) & 0xFFFF)


class Operator:
    def __init__(self, app_name=None, use_mss=True, scale=1,
                 true_window_json="window/true_window.json",
                 mouse_lock=None, pause_event=None, stop_event=None,
                 use_sendmsg=True):
        self.app_name = app_name
        self.scale = scale
        self.true_window_json = true_window_json
        self._lock = mouse_lock
        self._pause_event = pause_event
        self._stop_event = stop_event
        self._use_sendmsg = use_sendmsg

        self.borders = {'left': 0, 'top': 0, 'right': 0, 'bottom': 0}
        self._load_borders(true_window_json)

        self.wm = None
        if app_name is not None:
            try:
                self.wm = WindowManager(app_name)
            except Exception as e:
                print(f"⚠️ {e}，全屏模式")

        self.cap = ScreenCapture(use_mss=use_mss)

    # ---------- 控制 ----------

    def check_state(self):
        if self._stop_event and self._stop_event.is_set():
            raise InterruptedError("🛑 停止")
        if self._pause_event:
            if not self._pause_event.is_set():
                print("⏸️ 暂停中...")
            self._pause_event.wait()
            if self._stop_event and self._stop_event.is_set():
                raise InterruptedError("🛑 停止")

    @contextmanager
    def locked_step(self):
        if self._use_sendmsg:
            yield
        elif self._lock:
            self._lock.acquire()
            try:
                if self.wm:
                    self.wm.activate()
                    time.sleep(0.05)
                yield
            finally:
                self._lock.release()
        else:
            yield

    @contextmanager
    def _mouse_session(self):
        if self._use_sendmsg:
            yield
        elif self._lock:
            self._lock.acquire()
            try:
                if self.wm:
                    self.wm.activate()
                    time.sleep(0.05)
                yield
            finally:
                self._lock.release()
        else:
            yield

    # ---------- 边框 ----------

    def _load_borders(self, json_path):
        if not json_path or not Path(json_path).exists():
            return
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if 'shapes' in data and data['shapes']:
                pts = data['shapes'][0]['points']
                iw = data.get('imageWidth', 0)
                ih = data.get('imageHeight', 0)
                self.borders = {
                    'left': int(pts[0][0]), 'top': int(pts[0][1]),
                    'right': int(iw - pts[1][0]), 'bottom': int(ih - pts[1][1]),
                }
        except Exception:
            pass

    def _get_system_border(self):
        if not self.wm:
            return 0, 0
        pt = win32gui.ClientToScreen(self.wm.hwnd, (0, 0))
        rect = win32gui.GetWindowRect(self.wm.hwnd)
        return pt[0] - rect[0], pt[1] - rect[1]

    # ---------- 窗口 ----------

    def activate(self):
        if self.wm:
            self.wm.activate()
            return True
        return False

    def set_topmost(self, e=True):
        if self.wm: self.wm.set_topmost(e)

    def window_info(self):
        return self.wm.info() if self.wm else None

    # ---------- 坐标转换 ----------

    def _to_client_coords(self, box):
        if not self.wm:
            return box
        flat = [c for p in box for c in p]
        is_pct = all(0 <= v <= 1 for v in flat)
        sbx, sby = self._get_system_border()
        b = self.borders

        if is_pct:
            rect = self.wm.get_rect()
            ww = rect[2] - rect[0]
            wh = rect[3] - rect[1]
            cw = ww - b['left'] - b['right']
            ch = wh - b['top'] - b['bottom']
            return [
                [box[0][0]*cw + b['left'] - sbx, box[0][1]*ch + b['top'] - sby],
                [box[1][0]*cw + b['left'] - sbx, box[1][1]*ch + b['top'] - sby],
            ]
        else:
            return [[box[0][0]-sbx, box[0][1]-sby], [box[1][0]-sbx, box[1][1]-sby]]

    def _to_screen_coords(self, box):
        if not self.wm:
            return box
        flat = [c for p in box for c in p]
        is_pct = all(0 <= v <= 1 for v in flat)
        rect = self.wm.get_rect()
        wl, wt = rect[0], rect[1]

        if is_pct:
            b = self.borders
            ww = rect[2] - rect[0]
            wh = rect[3] - rect[1]
            cw = ww - b['left'] - b['right']
            ch = wh - b['top'] - b['bottom']
            return [
                [box[0][0]*cw + b['left'] + wl, box[0][1]*ch + b['top'] + wt],
                [box[1][0]*cw + b['left'] + wl, box[1][1]*ch + b['top'] + wt],
            ]
        else:
            return [[box[0][0]+wl, box[0][1]+wt], [box[1][0]+wl, box[1][1]+wt]]

    def transform_box(self, box):
        return self._to_client_coords(box) if self._use_sendmsg else self._to_screen_coords(box)

    # ---------- SendMessage 底层 ----------

    def _send_click_at(self, x, y):
        hwnd = self.wm.hwnd
        lp = _make_lparam(x, y)
        win32api.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lp)
        time.sleep(random.uniform(0.03, 0.08))
        win32api.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lp)

    def _send_drag(self, sx, sy, ex, ey, duration=0.5, steps=20):
        hwnd = self.wm.hwnd
        lp = _make_lparam(sx, sy)
        win32api.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lp)
        time.sleep(0.05)
        for i in range(1, steps + 1):
            t = i / steps
            cx = sx + (ex - sx) * t
            cy = sy + (ey - sy) * t
            win32api.PostMessage(hwnd, win32con.WM_MOUSEMOVE, win32con.MK_LBUTTON,
                                 _make_lparam(cx, cy))
            time.sleep(duration / steps)
        win32api.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, _make_lparam(ex, ey))

    # ---------- 截图 ----------

    def capture(self, save_path=None, activate_first=False):
        self.check_state()
        if self._use_sendmsg and self.wm:
            img = self.cap.grab_background(self.wm.hwnd)
            if img is None:
                region = self.wm.get_region() if self.wm else None
                img = self.cap.grab(region=region, scale=self.scale)
        else:
            with self._mouse_session():
                if activate_first and self.wm:
                    self.wm.activate()
                region = self.wm.get_region() if self.wm else None
                img = self.cap.grab(region=region, scale=self.scale)
        if img is not None and save_path:
            self.cap.save(img, save_path)
        return img

    # ---------- 点击 ----------

    def click(self, box):
        self.check_state()
        ab = self.transform_box(box)
        gx, gy = sample_point_in_box(ab)
        gx, gy = int(gx), int(gy)
        if self._use_sendmsg and self.wm:
            self._send_click_at(gx, gy)
            print(f"🖱️ click({gx},{gy}) → hwnd={self.wm.hwnd}")
        else:
            with self._mouse_session():
                pyautogui.moveTo(gx, gy, duration=random_duration(0.1, 0.2))
                pyautogui.click()
                print(f"🖱️ click({gx},{gy})")

    def click_json(self, path):
        p = Path(path)
        if p.suffix.lower() in {".png", ".jpg", ".jpeg", ""}:
            p = p.with_suffix(".json")
        data = json.load(open(p, encoding='utf-8'))
        box = data["shapes"][0]["points"]
        if self.wm and any(self.borders.values()):
            iw = data.get('imageWidth', 0)
            ih = data.get('imageHeight', 0)
            if iw > 0 and ih > 0:
                b = self.borders
                cw = iw - b['left'] - b['right']
                ch = ih - b['top'] - b['bottom']
                if cw > 0 and ch > 0:
                    box = [
                        [max(0,(box[0][0]-b['left'])/cw), max(0,(box[0][1]-b['top'])/ch)],
                        [min(1,(box[1][0]-b['left'])/cw), min(1,(box[1][1]-b['top'])/ch)],
                    ]
        print(f"   🖱️ {Path(path).stem}")
        self.click(box)
        return True

    def double_click(self, box):
        self.check_state()
        ab = self.transform_box(box)
        gx, gy = int(sample_point_in_box(ab)[0]), int(sample_point_in_box(ab)[1])
        if self._use_sendmsg and self.wm:
            self._send_click_at(gx, gy)
            time.sleep(random.uniform(0.05, 0.1))
            self._send_click_at(gx, gy)
        else:
            with self._mouse_session():
                pyautogui.moveTo(gx, gy, duration=random_duration(0.1, 0.2))
                pyautogui.click()
                time.sleep(random_duration(0.05, 0.1, False))
                pyautogui.click()

    # ---------- 拖拽 ----------

    def drag(self, box, direction, duration=0.5, reback=False):
        self.check_state()
        ab = self.transform_box(box)
        x1, y1 = ab[0]
        x2, y2 = ab[1]

        if self._use_sendmsg and self.wm:
            cw, ch = win32gui.GetClientRect(self.wm.hwnd)[2:4]
            x1, y1 = max(0,min(cw,x1)), max(0,min(ch,y1))
            x2, y2 = max(0,min(cw,x2)), max(0,min(ch,y2))
        else:
            sw, sh = pyautogui.size()
            x1, y1 = max(0,min(sw,x1)), max(0,min(sh,y1))
            x2, y2 = max(0,min(sw,x2)), max(0,min(sh,y2))

        w, h = x2-x1, y2-y1
        if w < 10 or h < 10:
            return

        m = 0.15
        dirs = {
            'up':    lambda: (x1+w*(0.3+random.uniform(0,0.4)), y1+h*(0.8-m), None, y1+h*(0.2+m)),
            'down':  lambda: (x1+w*(0.3+random.uniform(0,0.4)), y1+h*(0.2+m), None, y1+h*(0.8-m)),
            'left':  lambda: (x1+w*(0.8-m), y1+h*(0.3+random.uniform(0,0.4)), x1+w*(0.2+m), None),
            'right': lambda: (x1+w*(0.2+m), y1+h*(0.3+random.uniform(0,0.4)), x1+w*(0.8-m), None),
        }
        sx, sy, ex, ey = dirs[direction]()
        if ex is None: ex = sx + random.uniform(-5, 5)
        if ey is None: ey = sy + random.uniform(-5, 5)
        sx,sy = max(x1,min(x2,sx)), max(y1,min(y2,sy))
        ex,ey = max(x1,min(x2,ex)), max(y1,min(y2,ey))

        if self._use_sendmsg and self.wm:
            self._send_drag(int(sx),int(sy),int(ex),int(ey),duration)
            print(f"↔️ drag({direction}) ({sx:.0f},{sy:.0f})→({ex:.0f},{ey:.0f}) hwnd={self.wm.hwnd}")
        else:
            with self._mouse_session():
                pyautogui.moveTo(sx, sy, duration=0.2)
                pyautogui.dragTo(ex, ey, duration=duration, button='left',
                                 tween=pyautogui.easeInOutQuad)

    def drag_json(self, path, direction, duration=0.5, reback=False):
        p = Path(path)
        if p.suffix.lower() in {".png", ".jpg", ".jpeg", ""}:
            p = p.with_suffix(".json")
        data = json.load(open(p, encoding='utf-8'))
        box = data["shapes"][0]["points"]
        if self.wm and any(self.borders.values()):
            iw = data.get('imageWidth', 0)
            ih = data.get('imageHeight', 0)
            if iw > 0 and ih > 0:
                b = self.borders
                cw = iw - b['left'] - b['right']
                ch = ih - b['top'] - b['bottom']
                if cw > 0 and ch > 0:
                    box = [
                        [max(0,(box[0][0]-b['left'])/cw), max(0,(box[0][1]-b['top'])/ch)],
                        [min(1,(box[1][0]-b['left'])/cw), min(1,(box[1][1]-b['top'])/ch)],
                    ]
        self.drag(box, direction, duration, reback)