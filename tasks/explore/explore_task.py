from tasks.base_task import BaseTask


class ExploreTask(BaseTask):
    TASK_NAME = "explore"
    IS_DAILY = False

    def run(self):
        self.log.info("🔍 探秘（待实现）")
        # TODO: 探秘逻辑
        pass