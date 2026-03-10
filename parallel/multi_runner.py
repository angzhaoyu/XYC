import sys
import threading
import time
import keyboard
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))
from tools.window_manager import WindowGroupManager


class MultiRunner:
    def __init__(self, app_title, max_workers=None):
        self.app_title = app_title
        self.gm = WindowGroupManager(app_title)
        self.max_workers = max_workers or len(self.gm.windows) or 4

        self._pause_event = threading.Event()
        self._pause_event.set()
        self._stop_event = threading.Event()

        keyboard.on_press_key('F9',  lambda _: self._toggle_pause())
        keyboard.on_press_key('F10', lambda _: self._stop_all())
        print("⌨️  F9=暂停/恢复  F10=停止")

    def _toggle_pause(self):
        if self._pause_event.is_set():
            self._pause_event.clear()
            print("\n⏸️  已暂停")
        else:
            self._pause_event.set()
            print("\n▶️  已恢复")

    def _stop_all(self):
        self._stop_event.set()
        self._pause_event.set()
        print("\n🛑 停止中...")

    @property
    def stopped(self):
        return self._stop_event.is_set()

    def run(self, task_fn, max_rounds=500, round_timeout=600, **kwargs):
        if not self.gm.windows:
            print("❌ 没有找到窗口")
            return

        hwnds = [wm.hwnd for wm in self.gm.windows]
        print(f"\n🚀 {len(hwnds)} 个窗口，SendMessage 模式，真正并行")

        pool = ThreadPoolExecutor(max_workers=self.max_workers,
                                  thread_name_prefix="task")
        try:
            for round_num in range(max_rounds):
                if self.stopped:
                    break

                print(f"\n{'='*60}\n📍 第 {round_num + 1} 轮")

                futures = {
                    pool.submit(task_fn, hwnd=h, round_num=round_num, **kwargs): h
                    for h in hwnds
                }

                for f in as_completed(futures, timeout=round_timeout):
                    h = futures[f]
                    try:
                        f.result(timeout=10)
                    except InterruptedError:
                        print(f"⏹️ {h} 已停止")
                    except Exception as e:
                        print(f"❌ {h}: {e}")

                if self.stopped:
                    break

                wait = 60
                print(f"⏳ 等待 {wait}s...")
                for _ in range(wait * 10):
                    if self.stopped:
                        break
                    time.sleep(0.1)

        except KeyboardInterrupt:
            self._stop_all()
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
            keyboard.unhook_all()
            print("🏁 全部结束")