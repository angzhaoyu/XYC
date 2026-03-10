import time
from tasks.base_task import BaseTask
from tasks.ad_handler import AdHandler


class DaojuTask(BaseTask):
    TASK_NAME = "daoju"
    IS_DAILY = True

    def run(self):
        ad = AdHandler(self.op, self.mgr)
        valid_states = ["djsd", "fhs", "sxk", "lingdi"]
        zhuanshi = self.P("daily.zhp.zhuanshi")

        self.mgr.navigate_to("djsd")

        # 购买
        buy1 = self.P("daily.daoju.buy1")
        buy2 = self.P("daily.daoju.buy2")
        if self.secten(buy1):
            self.log.info("购买物品")
            self.op.click_json(buy1)
            time.sleep(1)
            self.op.click_json(buy2)

        # 奉还石
        fhs = self.P("daily.daoju.fhs")
        for _ in range(6):
            self.mgr.navigate_to("djsd")
            self.op.click_json(fhs)
            time.sleep(0.5)
            if self.mgr.get_states() == "fhs":
                self.op.click_json(zhuanshi)
                ad.watch_and_close(valid_states)
            else:
                break

        # 刷新卡
        sxk = self.P("daily.daoju.sxk")
        for _ in range(4):
            self.mgr.navigate_to("djsd")
            self.op.click_json(sxk)
            time.sleep(0.5)
            if self.mgr.get_states() == "sxk":
                self.op.click_json(zhuanshi)
                ad.watch_and_close(valid_states)
            else:
                break

        self.mgr.navigate_to("lingdi")
        self.log.info("✅ 道具商店完成")