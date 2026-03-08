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
from pathlib import Path

from tools.window_manager import WindowManager
from tools.screen_capture import ScreenCapture
from tools.coordinate_utils import CoordinateConverter


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
                 true_window_json="window/true_window.json"):   # ★ 改动1
        self.app_name = app_name
        self.scale = scale
        self.true_window_json = true_window_json

        # ★ 加载固定边框像素
        self.borders = {'left': 0, 'top': 0, 'right': 0, 'bottom': 0}
        self._load_borders(true_window_json)

        self.wm = None
        if app_name is not None:
            try:
                self.wm = WindowManager(app_name)
            except Exception as e:
                print(f"⚠️ {e}，将使用全屏模式")

        self.cap = ScreenCapture(use_mss=use_mss)

    # ★ 新增：加载边框
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

    # ========== 窗口操作（不变）==========

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

    # ========== ★ 改动2：transform_box ==========

    def transform_box(self, box):
        if self.app_name is None or self.wm is None:
            return box

        def is_percentage(coord_list):
            flat = [c for point in coord_list for c in point]
            return all(0 <= v <= 1 for v in flat)

        coord_type = 'a_percentage' if is_percentage(box) else 'a_pixel'
        converter = CoordinateConverter(
            box, coord_type=coord_type,
            obj=self.wm.title,
            json_path=self.true_window_json   # ★ 用正确的边框配置
        )
        return converter.s_pixel

    # ========== 截图（不变）==========

    def capture(self, save_path=None, activate_first=True):
        if activate_first and self.wm:
            self.wm.activate()
        region = self.wm.get_region() if self.wm else None
        img = self.cap.grab(region=region, scale=self.scale)
        if img is not None and save_path:
            self.cap.save(img, save_path)
        return img

    # ========== 点击（不变）==========

    def click(self, box):
        abs_box = self.transform_box(box)
        gx, gy = sample_point_in_box(abs_box)
        duration = random_duration(0.1, 0.2)
        pyautogui.moveTo(gx, gy, duration=duration)
        pyautogui.click()
        print(f"🖱️ 点击: ({gx:.0f}, {gy:.0f})")

    # ========== ★ 改动3：click_json ==========

    def click_json(self, path):
        """读取 labelme JSON，像素坐标 → 内容区域百分比 → 点击"""
        p = Path(path)
        if p.suffix.lower() in {".png", ".jpg", ".jpeg", ""}:
            p = p.with_suffix(".json")

        data = json.load(open(p, encoding='utf-8'))
        box = data["shapes"][0]["points"]

        # ★ 模板像素 → 内容区域百分比（不受窗口大小影响）
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

    # ========== 以下完全不变 ==========

    def double_click(self, box):
        abs_box = self.transform_box(box)
        gx, gy = sample_point_in_box(abs_box)
        duration = random_duration(0.1, 0.2)
        pyautogui.moveTo(gx, gy, duration=duration)
        pyautogui.click()
        time.sleep(random_duration(0.05, 0.1, False))
        pyautogui.click()
        print(f"🖱️ 双击: ({gx:.0f}, {gy:.0f})")

    def drag(self, box, direction, duration=0.5, reback=False):
        abs_box = self.transform_box(box)
        x1, y1 = abs_box[0]
        x2, y2 = abs_box[1]
        width, height = x2 - x1, y2 - y1
        margin = 0.1

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
        if ex is None:
            ex = sx + random.uniform(-20, 20)
        if ey is None:
            ey = sy + random.uniform(-20, 20)

        if reback:
            pyautogui.moveTo(x1 + 5, sy, duration=0.2)
            pyautogui.dragTo(ex, sy, duration=duration, button='left')
            return

        pyautogui.moveTo(sx, sy, duration=0.2)
        pyautogui.dragTo(ex, ey, duration=duration, button='left',
                         tween=pyautogui.easeInOutQuad)
        print(f"↔️ 拖动 {direction}: ({sx:.0f},{sy:.0f}) -> ({ex:.0f},{ey:.0f})")