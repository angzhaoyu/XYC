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
from pathlib import Path
from contextlib import contextmanager

from tools.window_manager import WindowManager
from tools.screen_capture import ScreenCapture

# ==================== 工具函数（不变）====================

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


# ==================== 主类 ====================

class Operator:
    def __init__(self, app_name=None, use_mss=True, scale=1,
                 true_window_json="window/true_window.json",
                 mouse_lock=None,
                 pause_event=None,      # ★ 暂停事件
                 stop_event=None):      # ★ 停止事件
        self.app_name = app_name
        self.scale = scale
        self.true_window_json = true_window_json
        self._lock = mouse_lock
        self._pause_event = pause_event   # threading.Event, set=运行中
        self._stop_event = stop_event     # threading.Event, set=要停止

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

    # ==================== 暂停/停止检查 ====================

    def check_state(self):
        """每次操作前调用，处理暂停和停止"""
        # 检查停止
        if self._stop_event and self._stop_event.is_set():
            raise InterruptedError("🛑 收到停止信号")
        # 检查暂停（阻塞等待直到恢复）
        if self._pause_event:
            if not self._pause_event.is_set():
                print("⏸️  已暂停，等待恢复...")
            self._pause_event.wait()  # set=通过, clear=阻塞
            # 恢复后再检查一次是否要停止
            if self._stop_event and self._stop_event.is_set():
                raise InterruptedError("🛑 收到停止信号")

    # ==================== 鼠标锁 ====================

    @contextmanager
    def _mouse_session(self):
        if self._lock:
            self._lock.acquire()
            try:
                if self.wm and not self._lock:
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

    # ==================== 窗口操作 ====================

    def activate(self):
        if self.wm and not self._lock:
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

    # ==================== ★ 修复：坐标转换 ====================

    def transform_box(self, box):
        """
        将坐标转为屏幕绝对坐标

        百分比坐标：相对于内容区域（不含边框）→ 加边框+窗口偏移
        像素坐标：  相对于截图（含边框）→ 只加窗口偏移
        """
        if self.wm is None:
            return box

        def is_percentage(coord_list):
            flat = [c for point in coord_list for c in point]
            return all(0 <= v <= 1 for v in flat)

        rect = self.wm.get_rect()
        win_left, win_top = rect[0], rect[1]

        if is_percentage(box):
            # ★ 百分比 → 内容区域映射 → 屏幕
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
            # ★ 像素坐标（YOLO/find_image 返回的，相对于整个截图）
            #   截图 = 整个窗口（含边框），所以只加窗口左上角偏移
            return [
                [box[0][0] + win_left,
                 box[0][1] + win_top],
                [box[1][0] + win_left,
                 box[1][1] + win_top],
            ]

    # ==================== 截图 ====================

    def capture(self, save_path=None, activate_first=True):
        self.check_state()
        with self._mouse_session():
            if activate_first and self.wm and not self._lock:
                self.wm.activate()
            region = self.wm.get_region() if self.wm else None
            img = self.cap.grab(region=region, scale=self.scale)
            if img is not None and save_path:
                self.cap.save(img, save_path)
            return img

    # ==================== 点击 ====================

    def click(self, box):
        with self._mouse_session():
            abs_box = self.transform_box(box)
            gx, gy = sample_point_in_box(abs_box)
            duration = random_duration(0.1, 0.2)
            pyautogui.moveTo(gx, gy, duration=duration)
            pyautogui.click()
            print(f"🖱️ 点击: ({gx:.0f}, {gy:.0f})")

    def click_json(self, path):
        """读取 labelme JSON，模板像素 → 内容区域百分比 → 点击"""
        p = Path(path)
        if p.suffix.lower() in {".png", ".jpg", ".jpeg", ""}:
            p = p.with_suffix(".json")

        data = json.load(open(p, encoding='utf-8'))
        box = data["shapes"][0]["points"]

        # 模板像素 → 内容区域百分比（不受窗口大小影响）
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

        print(f"   🖱️ 点击: {Path(path).stem} | box: {box}")
        self.click(box)
        return True

    def double_click(self, box):
        with self._mouse_session():
            abs_box = self.transform_box(box)
            gx, gy = sample_point_in_box(abs_box)
            duration = random_duration(0.1, 0.2)
            pyautogui.moveTo(gx, gy, duration=duration)
            pyautogui.click()
            time.sleep(random_duration(0.05, 0.1, False))
            pyautogui.click()
            print(f"🖱️ 双击: ({gx:.0f}, {gy:.0f})")

    def drag(self, box, direction, duration=0.5, reback=False):
        with self._mouse_session():
            abs_box = self.transform_box(box)
            x1, y1 = abs_box[0]
            x2, y2 = abs_box[1]

            # ★ 打印出来看看
            screen_w, screen_h = pyautogui.size()
            print(f"🔍 drag 输入 box={box}")
            print(f"🔍 转换后 abs_box=({x1:.0f},{y1:.0f})-({x2:.0f},{y2:.0f})")
            print(f"🔍 屏幕={screen_w}x{screen_h}")

            # ★ 先把 box 本身限制在屏幕内
            x1 = max(0, min(screen_w, x1))
            y1 = max(0, min(screen_h, y1))
            x2 = max(0, min(screen_w, x2))
            y2 = max(0, min(screen_h, y2))

            width, height = x2 - x1, y2 - y1
            if width < 10 or height < 10:
                print(f"⚠️ box 太小或无效，跳过拖动")
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
            if ex is None: ex = sx + random.uniform(-5, 5)   # ★ 减小随机量
            if ey is None: ey = sy + random.uniform(-5, 5)

            # ★ 限制在 box 范围内
            sx = max(x1, min(x2, sx))
            sy = max(y1, min(y2, sy))
            ex = max(x1, min(x2, ex))
            ey = max(y1, min(y2, ey))

            # ★ 再限制在屏幕范围内
            sx = max(5, min(screen_w - 5, sx))
            sy = max(5, min(screen_h - 5, sy))
            ex = max(5, min(screen_w - 5, ex))
            ey = max(5, min(screen_h - 5, ey))

            print(f"🔍 最终拖动: ({sx:.0f},{sy:.0f}) -> ({ex:.0f},{ey:.0f})")

            if reback:
                rb_x = max(x1, min(x2, x1 + 5))
                rb_x = max(5, min(screen_w - 5, rb_x))
                pyautogui.moveTo(rb_x, sy, duration=0.2)
                pyautogui.dragTo(ex, sy, duration=duration, button='left')
                return

            pyautogui.moveTo(sx, sy, duration=0.2)
            pyautogui.dragTo(ex, ey, duration=duration, button='left',
                            tween=pyautogui.easeInOutQuad)
            print(f"↔️ 拖动 {direction}: ({sx:.0f},{sy:.0f}) -> ({ex:.0f},{ey:.0f})")


    def drag_json(self, path, direction, duration=0.5, reback=False):
        """读取 labelme JSON 的 box，转百分比后拖动"""
        p = Path(path)
        if p.suffix.lower() in {".png", ".jpg", ".jpeg", ""}:
            p = p.with_suffix(".json")

        data = json.load(open(p, encoding='utf-8'))
        box = data["shapes"][0]["points"]

        # ★ 模板像素 → 内容区域百分比（和 click_json 一样）
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

        print(f"   ↔️ 拖动: {Path(path).stem} | box: {box} | {direction}")
        self.drag(box, direction, duration, reback)



