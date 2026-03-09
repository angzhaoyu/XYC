# screen_capture.py 中

import mss
import numpy as np
import cv2


class ScreenCapture:
    def __init__(self, use_mss=True):
        self.use_mss = use_mss

    def grab(self, region=None, scale=1):
        if self.use_mss:
            return self._grab_mss(region, scale)
        else:
            return self._grab_pyautogui(region, scale)

    def _grab_mss(self, region, scale):
        # ★ 每次截图新建 mss 实例，线程安全
        with mss.mss() as sct:
            if region:
                monitor = {
                    "left": region["left"],
                    "top": region["top"],
                    "width": region["width"],
                    "height": region["height"],
                }
            else:
                monitor = sct.monitors[0]

            img = sct.grab(monitor)
            frame = np.array(img)
            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

            if scale != 1:
                frame = cv2.resize(frame, None, fx=scale, fy=scale)

            return frame

    def _grab_pyautogui(self, region, scale):
        import pyautogui
        if region:
            img = pyautogui.screenshot(region=(
                region["left"], region["top"],
                region["width"], region["height"]
            ))
        else:
            img = pyautogui.screenshot()

        frame = np.array(img)
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

        if scale != 1:
            frame = cv2.resize(frame, None, fx=scale, fy=scale)

        return frame

    def save(self, img, path):
        cv2.imwrite(str(path), img)