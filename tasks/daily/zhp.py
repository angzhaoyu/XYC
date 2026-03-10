import time
from tasks.base_task import BaseTask
from tasks.ad_handler import AdHandler


class ZhpTask(BaseTask):
    TASK_NAME = "zhp"
    IS_DAILY = True

    def run(self):
        ad = AdHandler(self.op, self.mgr)
        valid_states = ["zhp", "caidan", "zhuye", "zhuanshi", "yuer"]

        zhp1 = self.P("daily.zhp.check1")
        zhp2 = self.P("daily.zhp.check2")
        yuer = self.P("daily.zhp.yuer")
        zhuanshi = self.P("daily.zhp.zhuanshi")

        self.mgr.navigate_to("zhp")
        if self.secten(zhp1):
            self.mgr.navigate_to("yuer")
            self.op.click_json(yuer)
            self.op.click_json(zhp2)
            ad.watch_and_close(valid_states)

        time.sleep(1)
        self.mgr.navigate_to("zhp")
        time.sleep(1)

        if self.secten(zhp2):
            self.mgr.navigate_to("zhuanshi")
            self.op.click_json(zhuanshi)
            self.op.click_json(zhp2)
            ad.watch_and_close(valid_states)

        self.mgr.navigate_to("zhuye")
        self.log.info("✅ 杂货铺完成")