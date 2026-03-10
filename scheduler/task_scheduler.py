"""任务调度器"""
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
                 use_sendmsg=True):
        self.hwnd = hwnd
        self.account_name = account_name
        self.log = get_logger(f"sched.{hwnd}")

        cfg = settings()
        self.op = Operator(app_name=hwnd, use_sendmsg=use_sendmsg)
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

    def run(self):
        regions = self.region_mgr.get_regions(self.account_name)
        if not regions or not self.loop_ctrl.enable_region_switch:
            regions = ["default"]

        while self.loop_ctrl.should_continue:
            rnd = self.loop_ctrl.current_round
            self.log.info(f"📍 第 {rnd + 1} 轮 (hwnd={self.hwnd})")

            for region in regions:
                if region != regions[0] and region != "default":
                    if not self.region_mgr.switch_to(region):
                        continue

                self.log.info(f"🌍 大区: {region}")

                for task in self.task_instances:
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
        self.log.info("🏁 调度完成")