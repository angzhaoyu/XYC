import mss
import numpy as np
import cv2
import win32gui
import win32ui
from ctypes import windll


class ScreenCapture:
    def __init__(self, use_mss=True):
        self.use_mss = use_mss

    def grab(self, region=None, scale=1):
        with mss.mss() as sct:
            monitor = region or sct.monitors[0]
            img = sct.grab(monitor)
            frame = cv2.cvtColor(np.array(img), cv2.COLOR_BGRA2BGR)
            if scale != 1:
                frame = cv2.resize(frame, None, fx=scale, fy=scale)
            return frame

    def grab_background(self, hwnd):
        """PrintWindow 后台截图"""
        try:
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            w, h = right - left, bottom - top
            if w <= 0 or h <= 0:
                return None

            hwndDC = win32gui.GetWindowDC(hwnd)
            mfcDC = win32ui.CreateDCFromHandle(hwndDC)
            saveDC = mfcDC.CreateCompatibleDC()
            bmp = win32ui.CreateBitmap()
            bmp.CreateCompatibleBitmap(mfcDC, w, h)
            saveDC.SelectObject(bmp)

            windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), 3)

            img = np.frombuffer(bmp.GetBitmapBits(True), dtype=np.uint8).reshape((h, w, 4))
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

            win32gui.DeleteObject(bmp.GetHandle())
            saveDC.DeleteDC()
            mfcDC.DeleteDC()
            win32gui.ReleaseDC(hwnd, hwndDC)
            return img
        except Exception as e:
            print(f"⚠️ 后台截图失败: {e}")
            return None

    def save(self, img, path):
        cv2.imwrite(str(path), img)