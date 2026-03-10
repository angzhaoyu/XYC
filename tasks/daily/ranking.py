import time
from tasks.base_task import BaseTask


class RankingTask(BaseTask):
    TASK_NAME = "ranking"
    IS_DAILY = True

    def run(self):
        collect = self.P("daily.ranking.collect")
        enter = self.P("daily.ranking.enter")
        drag_area = self.P("daily.ranking.drag_area")
        back_btn = "tasks/states/page-change/ycfrd_szpfb_01.json"

        limit = self.vision.limit_scope(
            self.P("daily.ranking.drag_area"), scale=1
        )

        # 养成分榜
        self.mgr.navigate_to("ycfrd")
        if self.secten("daily.id_checks.ycfrd"):
            self._collect_rank(enter, drag_area, collect, limit, back_btn)

        # 数值排行
        self.mgr.navigate_to("szpfb")
        time.sleep(1)
        self._collect_rank(enter, drag_area, collect, limit, back_btn)

        # 海兽战力
        self.mgr.navigate_to("hszlb")
        time.sleep(1)
        self._collect_rank(enter, drag_area, collect, limit, back_btn)

        self.mgr.navigate_to("zhuye")
        self.log.info("✅ 排行榜完成")

    def _collect_rank(self, enter, drag_area, collect, limit, back_btn):
        self.op.click_json(enter)
        time.sleep(1)
        self.op.drag_json(drag_area, "up", duration=0.5)
        time.sleep(0.5)

        for _ in range(10):
            region = self.vision.find_image(
                self.op.capture(), collect, a_percentage=limit
            )
            if not region:
                break
            self.op.click(region)
            self.op.click_json(back_btn)
            time.sleep(0.5)

        self.op.click_json(back_btn)