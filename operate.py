import numpy as np
import pyautogui
import random
import time
import os
import pygetwindow as gw
import json
from pathlib import Path
from PIL import Image
from coordinate_utils import CoordinateConverter
import cv2
# ==================== 工具函数更新 ====================

def get_target_window(app_name_or_id):
    """辅助函数：获取窗口对象，支持名称(str)或句柄(int)"""
    if isinstance(app_name_or_id, str):
        windows = gw.getWindowsWithTitle(app_name_or_id)
        return windows[0] if windows else None
    elif isinstance(app_name_or_id, int):
        # ✅ 修复：pygetwindow 不支持 gw.Window(hwnd)
        # 必须遍历所有窗口，通过句柄匹配
        for w in gw.getAllWindows():
            if w._hWnd == app_name_or_id:
                return w
        return None


def random_duration(min_time, max_time, use_gauss=True):
    """生成随机持续时间"""
    if use_gauss:
        mean = (min_time + max_time) / 2
        std_dev = (max_time - min_time) / 6
        while True:
            duration = np.random.normal(mean, std_dev)
            if min_time <= duration <= max_time:
                return duration
    else:
        return random.uniform(min_time, max_time)

def sample_point_in_box(box, sigma_ratio=0.1):
    """在边界框内根据高斯分布采样一个点"""
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


# ==================== 封装类 ====================

class Operator:
    def __init__(self, app_name=None):
        """
        Args:
            app_name: 窗口名称(str)或窗口ID(int)
        """
        self.app_name = app_name
        self._window = None
        
        if app_name is not None:
            self._window = get_target_window(app_name)
            if self._window:
                print(f"✅ 绑定窗口: {self._window.title} (ID: {self._window._hWnd})")
            else:
                print(f"⚠️ 未找到窗口: {app_name}，将使用全屏模式")
    
    def transform_box(self, box):
        """
        智能转换坐标到屏幕绝对坐标
        支持：
            - 百分比坐标 [[0~1, 0~1], ...]   -> a_percentage
            - 像素坐标   [[>1, >1], ...]      -> a_pixel
        """
        if self.app_name is None or self._window is None:
            return box

        # 判断坐标是否像是百分比（所有值都在 0~1 之间）
        def is_percentage(coord_list):
            flat = [c for point in coord_list for c in point]
            return all(0 <= v <= 1 for v in flat)

        coord_type = 'a_percentage' if is_percentage(box) else 'a_pixel'

        converter = CoordinateConverter(box, coord_type=coord_type, obj=self._window.title)
        return converter.s_pixel

    def capture(self, save_path=None, region=None):
        """
        截图功能：增加窗口自动弹出/置顶逻辑
        """
        try:
            # --- 新增：窗口弹出/激活逻辑 ---
            if self._window:
                try:
                    if self._window.isMinimized:
                        self._window.restore()  # 如果最小化了，先恢复
                    self._window.activate()     # 将窗口带到前台
                    time.sleep(0.2)             # 等待窗口渲染/弹出动画完成
                except Exception as e:
                    print(f"⚠️ 无法弹出窗口: {e}")

            # 确定截图范围
            capture_region = None
            if region:
                x1, y1, x2, y2 = region
                capture_region = (int(x1), int(y1), int(x2 - x1), int(y2 - y1))
            elif self._window:
                # 重新获取最新的窗口位置（防止激活后位置变动）
                capture_region = (
                    self._window.left, 
                    self._window.top, 
                    self._window.width, 
                    self._window.height
                )

            # 执行截图
            img = pyautogui.screenshot(region=capture_region)
            img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            if save_path:
                folder = os.path.dirname(save_path)
                if folder and not os.path.exists(folder):
                    os.makedirs(folder)
                cv2.imwrite(save_path, img)
                print(f"📸 截图已保存至: {save_path}")
            
            return img

        except Exception as e:
            print(f"❌ 截图失败: {e}")
            return None

    def click(self, box):
        abs_box = self.transform_box(box)
        gx, gy = sample_point_in_box(abs_box)
        duration = random_duration(0.1, 0.2)
        pyautogui.moveTo(gx, gy, duration=duration)
        pyautogui.click()
        print(f"🖱️ 点击: ({gx:.0f}, {gy:.0f})")

    def click_json(self, path):
        """输入图片名或json名，读取labelme格式的矩形区域并点击"""
        p = Path(path)
        if p.suffix.lower() in {".png", ".jpg", ".jpeg"}:
            p = p.with_suffix(".json")
        elif p.suffix == "":
            p = p.with_suffix(".json")

        data = json.load(open(p))

        # 提取第一个矩形区域的 points（labelme标准格式）
        box = data["shapes"][0]["points"]
        print(f"点击box{box}")
        print(f"   🖱️ 点击: {Path(path).stem}")
        self.click(box)
        return True

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
        
        if direction == 'up':
            start_x = x1 + width * (0.3 + random.uniform(0, 0.4))
            start_y = y1 + height * (0.8 - margin)
            end_x = start_x + random.uniform(-20, 20)
            end_y = y1 + height * (0.2 + margin)
        elif direction == 'down':
            start_x = x1 + width * (0.3 + random.uniform(0, 0.4))
            start_y = y1 + height * (0.2 + margin)
            end_x = start_x + random.uniform(-20, 20)
            end_y = y1 + height * (0.8 - margin)
        elif direction == 'left':
            start_x = x1 + width * (0.8 - margin)
            start_y = y1 + height * (0.3 + random.uniform(0, 0.4))
            end_x = x1 + width * (0.2 + margin)
            end_y = start_y + random.uniform(-20, 20)
        elif direction == 'right':
            start_x = x1 + width * (0.2 + margin)
            start_y = y1 + height * (0.3 + random.uniform(0, 0.4))
            end_x = x1 + width * (0.8 - margin)
            end_y = start_y + random.uniform(-20, 20)
        else:
            raise ValueError("direction 必须是 'up', 'down', 'left', 或 'right'")

        if reback:
            pyautogui.moveTo(x1 + 5, start_y, duration=0.2)
            pyautogui.dragTo(end_x, start_y, duration=duration, button='left')
            return

        pyautogui.moveTo(start_x, start_y, duration=0.2)
        pyautogui.dragTo(end_x, end_y, duration=duration, button='left', tween=pyautogui.easeInOutQuad)
        print(f"↔️ 拖动 {direction}: ({start_x:.0f},{start_y:.0f}) -> ({end_x:.0f},{end_y:.0f})")


# 方式1：通过ID绑定并截图
"""
op = Operator(app_name= 1249806) 
#op.capture(save_path="screenshots/capture_by_id.png")
op.click_json("tasks/page-change/guankan_lingdi_01.png")
"""