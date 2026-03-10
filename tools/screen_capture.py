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
            if region:
                monitor = {
                    "left": region["left"], "top": region["top"],
                    "width": region["width"], "height": region["height"],
                }
            else:
                monitor = sct.monitors[0]
            img = sct.grab(monitor)
            frame = np.array(img)
            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            if scale != 1:
                frame = cv2.resize(frame, None, fx=scale, fy=scale)
            return frame

    def grab_background(self, hwnd):
        """★ 后台截图，窗口被遮挡也能截"""
        try:
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            width = right - left
            height = bottom - top
            if width <= 0 or height <= 0:
                return None

            hwndDC = win32gui.GetWindowDC(hwnd)
            mfcDC = win32ui.CreateDCFromHandle(hwndDC)
            saveDC = mfcDC.CreateCompatibleDC()

            saveBitMap = win32ui.CreateBitmap()
            saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
            saveDC.SelectObject(saveBitMap)

            # PW_RENDERFULLCONTENT = 3
            windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), 3)

            bmpstr = saveBitMap.GetBitmapBits(True)
            img = np.frombuffer(bmpstr, dtype=np.uint8).reshape((height, width, 4))
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

            win32gui.DeleteObject(saveBitMap.GetHandle())
            saveDC.DeleteDC()
            mfcDC.DeleteDC()
            win32gui.ReleaseDC(hwnd, hwndDC)

            return img
        except Exception as e:
            print(f"⚠️ 后台截图失败: {e}")
            return None

    def save(self, img, path):
        cv2.imwrite(str(path), img)