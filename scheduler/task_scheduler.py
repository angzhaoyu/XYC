"""任务调度器"""
import time
from core.operator import Operator
from core.vision import MyVision
from core.state_manager import StateManager
from core.config_loader import settings
from core.logger import get_logger
from scheduler.daily_tracker import DailyTracker
from scheduler.region_manager import RegionManager
from scheduler.loop_controller import LoopController


class TaskScheduler:
    def __init__(self, hwnd, account_name="default",
                 selected_tasks=None, loop_ctrl=None,
                 use_sendmsg=True,
                 pause_event=None, stop_event=None):        # ★ 新增
        self.hwnd = hwnd
        self.account_name = account_name
        self.log = get_logger(f"sched.{hwnd}")
        self._pause_event = pause_event                      # ★
        self._stop_event = stop_event                        # ★

        cfg = settings()
        self.op = Operator(
            app_name=hwnd,
            use_sendmsg=use_sendmsg,
            pause_event=pause_event,                         # ★ 传下去
            stop_event=stop_event,                           # ★ 传下去
        )
        self.vision = MyVision()
        self.mgr = StateManager(
            cfg["states"]["file"],
            operator=self.op,
        )

        self.tracker = DailyTracker()
        self.region_mgr = RegionManager(self.op, self.mgr, self.vision)
        self.loop_ctrl = loop_ctrl or LoopController()

        self.task_instances = [
            TC(op=self.op, mgr=self.mgr, vision=self.vision)
            for TC in (selected_tasks or [])
        ]

    def _check_stop(self):
        """检查是否需要停止"""
        if self._stop_event and self._stop_event.is_set():
            raise InterruptedError("🛑 停止")

    def _wait_interruptible(self, seconds):
        """可中断的等待"""
        for _ in range(int(seconds * 10)):
            if self._stop_event and self._stop_event.is_set():
                raise InterruptedError("🛑 停止")
            if self._pause_event:
                self._pause_event.wait()
            time.sleep(0.1)

    def run(self):
        regions = self.region_mgr.get_regions(self.account_name)
        if not regions or not self.loop_ctrl.enable_region_switch:
            regions = ["default"]

        while self.loop_ctrl.should_continue:
            self._check_stop()                                # ★

            rnd = self.loop_ctrl.current_round
            self.log.info(f"📍 第 {rnd + 1} 轮 (hwnd={self.hwnd})")

            for region in regions:
                self._check_stop()                            # ★

                if region != regions[0] and region != "default":
                    if not self.region_mgr.switch_to(region):
                        continue

                self.log.info(f"🌍 大区: {region}")

                for task in self.task_instances:
                    self._check_stop()                        # ★
                    try:
                        if task.IS_DAILY and self.tracker.is_done(
                            self.account_name, region, task.TASK_NAME
                        ):
                            self.log.info(f"⏭️ {task.TASK_NAME} 已完成")
                            continue

                        self.log.info(f"▶️ {task.TASK_NAME}")
                        task.run()

                        if task.IS_DAILY:
                            self.tracker.mark_done(
                                self.account_name, region, task.TASK_NAME
                            )
                    except InterruptedError:
                        self.log.info("⏹️ 停止")
                        return
                    except Exception as e:
                        self.log.error(f"❌ {task.TASK_NAME}: {e}")

            self.loop_ctrl.next_round()

            # ★ 轮间等待（可中断）
            if self.loop_ctrl.should_continue and self.loop_ctrl.wait_minutes > 0:
                wait_sec = self.loop_ctrl.wait_minutes * 60
                self.log.info(f"⏳ 等待 {self.loop_ctrl.wait_minutes} 分钟...")
                try:
                    self._wait_interruptible(wait_sec)
                except InterruptedError:
                    self.log.info("⏹️ 等待中被停止")
                    return

        self.log.info("🏁 调度完成")