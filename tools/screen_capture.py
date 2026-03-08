"""截图模块 - 负责高效截图"""

import cv2
import numpy as np
import os


class ScreenCapture:
    def __init__(self, use_mss=True):
        """
        Args:
            use_mss: True 用 mss（快），False 用 pyautogui（兼容）
        """
        self.use_mss = use_mss
        self._sct = None

        if use_mss:
            import mss
            self._sct = mss.mss()

    def grab(self, region=None, scale=1):
        """
        截图
        Args:
            region: dict {"left", "top", "width", "height"} 或 None(全屏)
            scale:  放大倍数，1=原始，2=放大2倍
        Returns:
            numpy 数组 (BGR)
        """
        if self.use_mss:
            img = self._grab_mss(region)
        else:
            img = self._grab_pyautogui(region)

        if img is None:
            return None

        if scale != 1:
            h, w = img.shape[:2]
            img = cv2.resize(
                img, (int(w * scale), int(h * scale)),
                interpolation=cv2.INTER_NEAREST
            )

        return img

    def _grab_mss(self, region):
        """使用 mss 截图（推荐，快）"""
        import mss
        if self._sct is None:
            self._sct = mss.mss()

        monitor = region if region else self._sct.monitors[1]
        frame = np.array(self._sct.grab(monitor))
        return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

    def _grab_pyautogui(self, region):
        """使用 pyautogui 截图（慢，但兼容性好）"""
        import pyautogui
        if region:
            r = (region["left"], region["top"], region["width"], region["height"])
            img = pyautogui.screenshot(region=r)
        else:
            img = pyautogui.screenshot()
        return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

    @staticmethod
    def save(img, path):
        """保存截图"""
        folder = os.path.dirname(path)
        if folder and not os.path.exists(folder):
            os.makedirs(folder)
        cv2.imwrite(path, img)
        print(f"📸 截图已保存: {path}")