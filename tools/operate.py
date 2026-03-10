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
import threading
import win32gui
import win32con
import win32api
from pathlib import Path
from contextlib import contextmanager

import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from tools.window_manager import WindowManager
from tools.screen_capture import ScreenCapture

pyautogui.FAILSAFE = False


# ==================== 工具函数 ====================

def random_duration(min_time, max_time, use_gauss=True):
    if use_gauss:
        mean = (min_time + max_time) / 2
        std_dev = (max_time - min_time) / 6
        while True:
            duration = np.random.normal(mean, std_dev)
            if min_time <= duration <= max_time:
                return duration
    return random.uniform(min_time, max_time)


def sample_point_in_box(box, sigma_ratio=0.1):
    (x1, y1), (x2, y2) = box
    center_x, center_y = (x1 + x2) / 2, (y1 + y2) / 2
    width, height = abs(x2 - x1), abs(y2 - y1)
    sigma_x, sigma_y = width * sigma_ratio, height * sigma_ratio
    x_min, x_max = min(x1, x2), max(x1, x2)
    y_min, y_max = min(y1, y2), max(y1, y2)

    for _ in range(100):
        gx = np.random.normal(center_x, sigma_x)
        gy = np.random.normal(center_y, sigma_y)
        if x_min <= gx <= x_max and y_min <= gy <= y_max:
            return [gx, gy]
    return [np.clip(gx, x_min, x_max), np.clip(gy, y_min, y_max)]


def _make_lparam(x, y):
    """坐标打包成 lParam"""
    return (int(y) << 16) | (int(x) & 0xFFFF)


# ==================== 主类 ====================

class Operator:
    def __init__(self, app_name=None, use_mss=True, scale=1,
                 true_window_json="window/true_window.json",
                 mouse_lock=None,
                 pause_event=None,
                 stop_event=None,
                 use_sendmsg=True):       # ★ 新增：是否用 SendMessage
        self.app_name = app_name
        self.scale = scale
        self.true_window_json = true_window_json
        self._lock = mouse_lock
        self._pause_event = pause_event
        self._stop_event = stop_event
        self._use_sendmsg = use_sendmsg   # ★

        # 加载固定边框
        self.borders = {'left': 0, 'top': 0, 'right': 0, 'bottom': 0}
        self._load_borders(true_window_json)

        # 窗口管理
        self.wm = None
        if app_name is not None:
            try:
                self.wm = WindowManager(app_name)
            except Exception as e:
                print(f"⚠️ {e}，将使用全屏模式")

        self.cap = ScreenCapture(use_mss=use_mss)

    # ==================== 暂停/停止 ====================

    def check_state(self):
        if self._stop_event and self._stop_event.is_set():
            raise InterruptedError("🛑 收到停止信号")
        if self._pause_event:
            if not self._pause_event.is_set():
                print("⏸️  已暂停，等待恢复...")
            self._pause_event.wait()
            if self._stop_event and self._stop_event.is_set():
                raise InterruptedError("🛑 收到停止信号")

    # ==================== 锁（SendMessage 模式下不需要）====================

    @contextmanager
    def locked_step(self):
        """高层锁，SendMessage 模式下直接 yield"""
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
        """SendMessage 模式下不需要锁"""
        if self._use_sendmsg:
            yield
        elif self._lock:
            self._lock.acquire()
            try:
                if self.wm:
                    rect = self.wm.get_rect()
                    title_x = (rect[0] + rect[2]) // 2
                    title_y = rect[1] + 5
                    pyautogui.moveTo(title_x, title_y, duration=0)
                    time.sleep(0.02)
                    self.wm.activate()
                    time.sleep(0.05)
                yield
            finally:
                self._lock.release()
        else:
            yield

    # ==================== 边框 ====================

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
                    'left':   int(pts[0][0]),
                    'top':    int(pts[0][1]),
                    'right':  int(iw - pts[1][0]),
                    'bottom': int(ih - pts[1][1]),
                }
        except Exception:
            pass

    # ==================== ★ 系统边框 ====================

    def _get_system_border(self):
        """窗口框架到客户区的偏移"""
        if not self.wm:
            return 0, 0
        pt = win32gui.ClientToScreen(self.wm.hwnd, (0, 0))
        rect = win32gui.GetWindowRect(self.wm.hwnd)
        return pt[0] - rect[0], pt[1] - rect[1]

    # ==================== 窗口操作 ====================

    def activate(self):
        if self.wm:
            self.wm.activate()
            return True
        return False

    def set_topmost(self, enable=True):
        if self.wm:
            self.wm.set_topmost(enable)

    def window_info(self):
        if self.wm:
            return self.wm.info()
        return None

    # ==================== ★ 坐标转换（两套）====================

    def _to_client_coords(self, box):
        """
        百分比/像素坐标 → 客户区坐标（给 SendMessage 用）
        """
        if not self.wm:
            return box

        def is_percentage(coord_list):
            flat = [c for point in coord_list for c in point]
            return all(0 <= v <= 1 for v in flat)

        sys_bx, sys_by = self._get_system_border()
        b = self.borders

        if is_percentage(box):
            # 百分比 → 内容区域 → 客户区坐标
            rect = self.wm.get_rect()
            win_w = rect[2] - rect[0]
            win_h = rect[3] - rect[1]
            cw = win_w - b['left'] - b['right']
            ch = win_h - b['top'] - b['bottom']
            return [
                [box[0][0] * cw + b['left'] - sys_bx,
                 box[0][1] * ch + b['top']  - sys_by],
                [box[1][0] * cw + b['left'] - sys_bx,
                 box[1][1] * ch + b['top']  - sys_by],
            ]
        else:
            # 截图像素 → 客户区（减去系统边框）
            return [
                [box[0][0] - sys_bx, box[0][1] - sys_by],
                [box[1][0] - sys_bx, box[1][1] - sys_by],
            ]

    def _to_screen_coords(self, box):
        """
        百分比/像素坐标 → 屏幕坐标（给 pyautogui 用）
        """
        if not self.wm:
            return box

        def is_percentage(coord_list):
            flat = [c for point in coord_list for c in point]
            return all(0 <= v <= 1 for v in flat)

        rect = self.wm.get_rect()
        win_left, win_top = rect[0], rect[1]

        if is_percentage(box):
            b = self.borders
            win_w = rect[2] - rect[0]
            win_h = rect[3] - rect[1]
            cw = win_w - b['left'] - b['right']
            ch = win_h - b['top'] - b['bottom']
            return [
                [box[0][0] * cw + b['left'] + win_left,
                 box[0][1] * ch + b['top']  + win_top],
                [box[1][0] * cw + b['left'] + win_left,
                 box[1][1] * ch + b['top']  + win_top],
            ]
        else:
            return [
                [box[0][0] + win_left, box[0][1] + win_top],
                [box[1][0] + win_left, box[1][1] + win_top],
            ]

    def transform_box(self, box):
        """根据模式选择坐标系"""
        if self._use_sendmsg:
            return self._to_client_coords(box)
        else:
            return self._to_screen_coords(box)

    # ==================== ★ SendMessage 底层方法 ====================

    def _send_click_at(self, x, y):
        """向窗口发送点击消息（客户区坐标）"""
        hwnd = self.wm.hwnd
        lparam = _make_lparam(x, y)
        win32api.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
        time.sleep(random.uniform(0.03, 0.08))
        win32api.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lparam)

    def _send_move_to(self, x, y):
        """向窗口发送鼠标移动消息"""
        hwnd = self.wm.hwnd
        lparam = _make_lparam(x, y)
        win32api.PostMessage(hwnd, win32con.WM_MOUSEMOVE, 0, lparam)

    def _send_drag(self, sx, sy, ex, ey, duration=0.5, steps=20):
        """向窗口发送拖拽消息"""
        hwnd = self.wm.hwnd

        # 按下
        lparam = _make_lparam(sx, sy)
        win32api.PostMessage(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
        time.sleep(0.05)

        # 移动
        for i in range(1, steps + 1):
            t = i / steps
            cx = sx + (ex - sx) * t
            cy = sy + (ey - sy) * t
            lp = _make_lparam(cx, cy)
            win32api.PostMessage(hwnd, win32con.WM_MOUSEMOVE, win32con.MK_LBUTTON, lp)
            time.sleep(duration / steps)

        # 松开
        lparam = _make_lparam(ex, ey)
        win32api.PostMessage(hwnd, win32con.WM_LBUTTONUP, 0, lparam)

    # ==================== 截图 ====================

    def capture(self, save_path=None, activate_first=False):
        self.check_state()
        if self._use_sendmsg:
            # ★ 后台截图，不需要激活
            img = self.cap.grab_background(self.wm.hwnd) if self.wm else self.cap.grab()
            if img is not None and save_path:
                self.cap.save(img, save_path)
            return img
        else:
            with self._mouse_session():
                if activate_first and self.wm:
                    self.wm.activate()
                region = self.wm.get_region() if self.wm else None
                img = self.cap.grab(region=region, scale=self.scale)
                if img is not None and save_path:
                    self.cap.save(img, save_path)
                return img

    # ==================== 点击 ====================

    def click(self, box):
        self.check_state()
        abs_box = self.transform_box(box)
        gx, gy = sample_point_in_box(abs_box)
        gx, gy = int(gx), int(gy)

        if self._use_sendmsg and self.wm:
            self._send_click_at(gx, gy)
            print(f"🖱️ 点击(msg): ({gx}, {gy}) → 句柄{self.wm.hwnd}")
        else:
            with self._mouse_session():
                pyautogui.moveTo(gx, gy, duration=random_duration(0.1, 0.2))
                pyautogui.click()
                print(f"🖱️ 点击: ({gx}, {gy})")

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
                        [max(0, (box[0][0] - b['left']) / cw),
                         max(0, (box[0][1] - b['top'])  / ch)],
                        [min(1, (box[1][0] - b['left']) / cw),
                         min(1, (box[1][1] - b['top'])  / ch)],
                    ]

        print(f"   🖱️ 点击: {Path(path).stem}")
        self.click(box)
        return True

    def double_click(self, box):
        self.check_state()
        abs_box = self.transform_box(box)
        gx, gy = sample_point_in_box(abs_box)
        gx, gy = int(gx), int(gy)

        if self._use_sendmsg and self.wm:
            self._send_click_at(gx, gy)
            time.sleep(random.uniform(0.05, 0.1))
            self._send_click_at(gx, gy)
            print(f"🖱️ 双击(msg): ({gx}, {gy})")
        else:
            with self._mouse_session():
                pyautogui.moveTo(gx, gy, duration=random_duration(0.1, 0.2))
                pyautogui.click()
                time.sleep(random_duration(0.05, 0.1, False))
                pyautogui.click()
                print(f"🖱️ 双击: ({gx}, {gy})")

    # ==================== 拖拽 ====================

    def drag(self, box, direction, duration=0.5, reback=False):
        self.check_state()
        abs_box = self.transform_box(box)
        x1, y1 = abs_box[0]
        x2, y2 = abs_box[1]

        # 限制范围
        if self._use_sendmsg:
            cw, ch = win32gui.GetClientRect(self.wm.hwnd)[2:4]
            x1 = max(0, min(cw, x1))
            y1 = max(0, min(ch, y1))
            x2 = max(0, min(cw, x2))
            y2 = max(0, min(ch, y2))
        else:
            sw, sh = pyautogui.size()
            x1 = max(0, min(sw, x1))
            y1 = max(0, min(sh, y1))
            x2 = max(0, min(sw, x2))
            y2 = max(0, min(sh, y2))

        width, height = x2 - x1, y2 - y1
        if width < 10 or height < 10:
            print("⚠️ box 太小，跳过拖动")
            return

        margin = 0.15
        directions = {
            'up':    lambda: (x1 + width * (0.3 + random.uniform(0, 0.4)),
                              y1 + height * (0.8 - margin),
                              None, y1 + height * (0.2 + margin)),
            'down':  lambda: (x1 + width * (0.3 + random.uniform(0, 0.4)),
                              y1 + height * (0.2 + margin),
                              None, y1 + height * (0.8 - margin)),
            'left':  lambda: (x1 + width * (0.8 - margin),
                              y1 + height * (0.3 + random.uniform(0, 0.4)),
                              x1 + width * (0.2 + margin), None),
            'right': lambda: (x1 + width * (0.2 + margin),
                              y1 + height * (0.3 + random.uniform(0, 0.4)),
                              x1 + width * (0.8 - margin), None),
        }

        if direction not in directions:
            raise ValueError(f"direction 必须是 {list(directions.keys())}")

        sx, sy, ex, ey = directions[direction]()
        if ex is None: ex = sx + random.uniform(-5, 5)
        if ey is None: ey = sy + random.uniform(-5, 5)

        sx = max(x1, min(x2, sx))
        sy = max(y1, min(y2, sy))
        ex = max(x1, min(x2, ex))
        ey = max(y1, min(y2, ey))

        if self._use_sendmsg and self.wm:
            self._send_drag(int(sx), int(sy), int(ex), int(ey), duration)
            print(f"↔️ 拖动(msg) {direction}: ({sx:.0f},{sy:.0f})->({ex:.0f},{ey:.0f})")
        else:
            with self._mouse_session():
                if reback:
                    rb_x = max(x1, min(x2, x1 + 5))
                    pyautogui.moveTo(rb_x, sy, duration=0.2)
                    pyautogui.dragTo(ex, sy, duration=duration, button='left')
                    return
                pyautogui.moveTo(sx, sy, duration=0.2)
                pyautogui.dragTo(ex, ey, duration=duration, button='left',
                                 tween=pyautogui.easeInOutQuad)
                print(f"↔️ 拖动 {direction}: ({sx:.0f},{sy:.0f})->({ex:.0f},{ey:.0f})")

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
                        [max(0, (box[0][0] - b['left']) / cw),
                         max(0, (box[0][1] - b['top'])  / ch)],
                        [min(1, (box[1][0] - b['left']) / cw),
                         min(1, (box[1][1] - b['top'])  / ch)],
                    ]

        print(f"   ↔️ 拖动: {Path(path).stem} | {direction}")
        self.drag(box, direction, duration, reback)

"""
if __name__ == "__main__":
    operate = Operator("幸福小渔村")
    operate.capture(save_path= "001.png")"""