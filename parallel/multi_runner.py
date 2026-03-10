import threading
import time
import keyboard
from concurrent.futures import ThreadPoolExecutor, as_completed
from window.window_group import WindowGroupManager
from scheduler.task_scheduler import TaskScheduler
from scheduler.loop_controller import LoopController
from core.logger import get_logger


class MultiRunner:
    def __init__(self, app_title, max_workers=None):
        self.log = get_logger("runner")
        self.gm = WindowGroupManager(app_title)
        self.max_workers = max_workers or max(len(self.gm.windows), 1)

        self._pause_event = threading.Event()
        self._pause_event.set()
        self._stop_event = threading.Event()

        keyboard.on_press_key('F9', lambda _: self._toggle_pause())
        keyboard.on_press_key('F10', lambda _: self._stop_all())
        self.log.info("⌨️ F9=暂停/恢复  F10=停止")

    def _toggle_pause(self):
        if self._pause_event.is_set():
            self._pause_event.clear()
            self.log.info("⏸️ 已暂停")
        else:
            self._pause_event.set()
            self.log.info("▶️ 已恢复")

    def _stop_all(self):
        self._stop_event.set()
        self._pause_event.set()
        self.log.info("🛑 停止")

    def run(self, selected_tasks, enable_loop=False, max_rounds=1,
            enable_region_switch=False, use_sendmsg=True,
            accounts_map=None):
        if not self.gm.windows:
            self.log.error("❌ 没有窗口")
            return

        accounts_map = accounts_map or {
            wm.hwnd: f"account_{i}" for i, wm in enumerate(self.gm.windows)
        }

        pool = ThreadPoolExecutor(max_workers=self.max_workers,
                                  thread_name_prefix="win")
        try:
            futures = {}
            for wm in self.gm.windows:
                hwnd = wm.hwnd
                account = accounts_map.get(hwnd, "default")

                loop_ctrl = LoopController(
                    enable_loop=enable_loop,
                    max_rounds=max_rounds,
                    enable_region_switch=enable_region_switch,
                )

                f = pool.submit(
                    self._run_window,
                    hwnd, account, selected_tasks, loop_ctrl, use_sendmsg,
                )
                futures[f] = hwnd

            for f in as_completed(futures, timeout=3600):
                hwnd = futures[f]
                try:
                    f.result()
                    self.log.info(f"✅ {hwnd} 完成")
                except Exception as e:
                    self.log.error(f"❌ {hwnd}: {e}")

        except KeyboardInterrupt:
            self._stop_all()
        finally:
            pool.shutdown(wait=False)
            keyboard.unhook_all()
            self.log.info("🏁 全部结束")

    def _run_window(self, hwnd, account, selected_tasks, loop_ctrl, use_sendmsg):
        scheduler = TaskScheduler(
            hwnd=hwnd,
            account_name=account,
            selected_tasks=selected_tasks,
            loop_ctrl=loop_ctrl,
            use_sendmsg=use_sendmsg,
        )
        scheduler.run()