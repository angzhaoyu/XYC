import sys
import threading
import time
import keyboard
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError

PROJECT_ROOT = Path(__file__).parent
sys.path.append(str(PROJECT_ROOT))

from tools.window_manager import WindowGroupManager


class MultiRunner:
    def __init__(self, app_title, max_workers=None):
        self.app_title = app_title
        self.gm = WindowGroupManager(app_title)
        self._mouse_lock = threading.RLock()
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
            print("\n⏸️  已暂停 (F9恢复)")
        else:
            self._pause_event.set()
            print("\n▶️  已恢复")

    def _stop_all(self):
        print("\n🛑 停止中...")
        self._stop_event.set()
        self._pause_event.set()

    @property
    def stopped(self):
        return self._stop_event.is_set()

    def run(self, task_fn, max_rounds=500, round_timeout=600, **kwargs):
        """
        Args:
            task_fn:        任务函数
            max_rounds:     最大轮数
            round_timeout:  每轮超时（秒），防止卡死
        """
        if not self.gm.windows:
            print("❌ 没有找到窗口")
            return

        hwnds = [wm.hwnd for wm in self.gm.windows]
        n = len(hwnds)
        print(f"\n🚀 {n} 个窗口，最多 {max_rounds} 轮")
        print("=" * 60)

        # ★ 线程池放循环外，不重复创建
        pool = ThreadPoolExecutor(max_workers=self.max_workers,
                                  thread_name_prefix="task")
        try:
            for round_num in range(max_rounds):
                if self.stopped:
                    break

                print(f"\n{'='*60}")
                print(f"📍 第 {round_num + 1} 轮")

                self.gm.activate_all()

                futures = {}
                for hwnd in hwnds:
                    f = pool.submit(
                        task_fn,
                        hwnd=hwnd,
                        round_num=round_num,
                        **kwargs,
                    )
                    futures[f] = hwnd

                # ★ 带超时等待，防止卡死
                for f in as_completed(futures, timeout=round_timeout):
                    hwnd = futures[f]
                    try:
                        f.result(timeout=10)
                    except InterruptedError:
                        print(f"⏹️ 句柄={hwnd} 已停止")
                    except TimeoutError:
                        print(f"⏰ 句柄={hwnd} 超时")
                    except Exception as e:
                        print(f"❌ 句柄={hwnd}: {e}")

                if self.stopped:
                    break

                # 可中断等待
                wait = 60
                print(f"\n⏳ 第 {round_num + 1} 轮完成，等待 {wait}s...")
                for _ in range(wait * 10):
                    if self.stopped:
                        break
                    time.sleep(0.1)

        except KeyboardInterrupt:
            self._stop_all()
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
            keyboard.unhook_all()
            print("\n🏁 全部结束")