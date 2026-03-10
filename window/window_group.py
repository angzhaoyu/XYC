"""从原 window_manager.py 拆出的 WindowGroupManager"""
import time
import json
import cv2
from pathlib import Path
from datetime import datetime

import win32api
from window.window_manager import WindowManager


class WindowGroupManager:
    def __init__(self, title):
        self.title = title
        self.windows = []
        self.refresh()

    def refresh(self):
        import win32gui
        hwnds = []
        def callback(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                name = win32gui.GetWindowText(hwnd)
                if self.title in name:
                    hwnds.append(hwnd)
        win32gui.EnumWindows(callback, None)
        self.windows = [WindowManager(h, quiet=True) for h in hwnds]
        print(f"🔍 找到 {len(self.windows)} 个 '{self.title}' 窗口")
        return self.windows

    @staticmethod
    def get_screen_size():
        w = win32api.GetSystemMetrics(0)
        h = win32api.GetSystemMetrics(1)
        return w, h

    def arrange(self, columns=None):
        if not self.windows:
            return
        n = len(self.windows)
        columns = columns or n
        screen_w, _ = self.get_screen_size()
        col_width = screen_w // columns

        for wm in self.windows:
            if wm.is_minimized():
                wm.restore()
                time.sleep(0.05)

        ref_rect = self.windows[0].get_rect()
        ref_w = ref_rect[2] - ref_rect[0]
        ref_h = ref_rect[3] - ref_rect[1]
        scale = col_width / ref_w if ref_w > 0 else 1
        target_h = max(int(ref_h * scale), 50)
        target_w = col_width

        for i, wm in enumerate(self.windows):
            col = i % columns
            row = i // columns
            x = col * col_width
            y = row * target_h
            if not wm.is_at(x, y, target_w, target_h):
                wm.move(x, y, target_w, target_h)
            time.sleep(0.03)

    def activate_all(self):
        for wm in self.windows:
            wm.activate()
            time.sleep(0.1)

    def __len__(self):
        return len(self.windows)

    def __getitem__(self, index):
        return self.windows[index]