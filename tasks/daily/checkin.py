import time
from tasks.base_task import BaseTask


class CheckinTask(BaseTask):
    TASK_NAME = "checkin"
    IS_DAILY = True

    def run(self):
        self.mgr.navigate_to("caidan")
        entry = self.P("daily.checkin.entry")
        limit = self.vision.limit_scope(entry, scale=1.2)
        region = self.vision.find_image(self.op.capture(), entry, a_percentage=limit)
        if region:
            self.mgr.navigate_to("qiandao")
            tpl = self.P("daily.checkin.days")
            for i in range(1, 8):
                path = tpl.format(i)
                self.op.click_json(path)
                time.sleep(0.3)
        self.mgr.navigate_to("zhuye")
        self.log.info("✅ 签到完成")