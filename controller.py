import time
import win32gui
import win32con
import threading

class GameController:
    def __init__(self, gui_update_callback):
        self.gui_update = gui_update_callback # 用于回传状态给界面
        self.is_running = False

    def force_focus(self, hwnd):
        """强力弹出并置顶窗口"""
        try:
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
            return True
        except Exception as e:
            print(f"弹出失败: {e}")
            return False

    def start_loop(self, windows):
        self.is_running = True
        self.thread = threading.Thread(target=self._logic_loop, args=(windows,), daemon=True)
        self.thread.start()

    def stop_loop(self):
        self.is_running = False

    def _logic_loop(self, windows):
        while self.is_running:
            for win in windows:
                if not self.is_running: break
                hwnd = win._hWnd
                
                # 1. 界面显示正在操作
                self.gui_update(hwnd, "🔥 正在弹出...", True)
                
                # 2. 弹出窗口
                if self.force_focus(hwnd):
                    time.sleep(1.5) # 等待窗口稳定
                    
                    # --- 这里是后续添加采集逻辑的地方 ---
                    # 如：vision.find_bird(win.box)
                    print(f"窗口 {hwnd} 逻辑执行中...")
                    time.sleep(2) 
                    
                # 3. 恢复界面状态
                self.gui_update(hwnd, "✅ 等待轮询", False)
            
            time.sleep(1)