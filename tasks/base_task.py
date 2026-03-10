from core.operator import Operator
from core.vision import MyVision
from core.state_manager import StateManager
from core.config_loader import settings, resolve, policy, paths
from core.logger import get_logger


class BaseTask:
    TASK_NAME = "base"
    IS_DAILY = False

    def __init__(self, op: Operator, mgr: StateManager = None,
                 vision: MyVision = None):
        self.op = op
        self.vision = vision or MyVision()
        self.mgr = mgr or StateManager(
            settings()["states"]["file"], operator=self.op,
        )
        self.log = get_logger(f"task.{self.TASK_NAME}")
        self._policy = policy()

    def P(self, key):
        """快捷获取路径: self.P('daily.shop.collect')"""
        return resolve(key)

    def secten(self, path_or_key, scale=1.2, threshold=0.6):
        if '.' in path_or_key and '/' not in path_or_key and '\\' not in path_or_key:
            path = resolve(path_or_key)
        else:
            path = path_or_key
        limit = self.vision.limit_scope(path, scale=scale)
        return self.vision.find_image(
            self.op.capture(), path, a_percentage=limit, threshold=threshold,
        )

    def run(self):
        raise NotImplementedError