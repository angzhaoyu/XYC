from tasks.base_task import BaseTask


class RichangTask(BaseTask):
    TASK_NAME = "richang"
    IS_DAILY = True

    def run(self):
        pages = [
            ("sxklb", "daily.richang.sllb"),
            ("fhlb",  "daily.richang.fhlb"),
            ("sclb",  "daily.richang.sxlb"),
        ]
        for page, tpl_key in pages:
            self.mgr.navigate_to(page)
            tpl = self.P(tpl_key)
            if self.secten(tpl_key):
                self.op.click_json(tpl)
                self.op.click_json(tpl)

        self.mgr.navigate_to("lingdi")
        self.log.info("✅ 日常领取完成")