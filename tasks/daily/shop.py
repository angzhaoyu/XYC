from tasks.base_task import BaseTask


class ShopTask(BaseTask):
    TASK_NAME = "shop"
    IS_DAILY = True

    def run(self):
        self.mgr.navigate_to("shangdian")
        tpl = self.P("daily.shop.collect")
        limit = self.vision.limit_scope(tpl, scale=1.2)
        region = self.vision.find_image(self.op.capture(), tpl, a_percentage=limit)
        if region:
            self.op.click(region)
        self.mgr.navigate_to("zhuye")
        self.log.info("✅ 商店领取完成")