import time

class CainiTask:
    """采泥任务"""

    def __init__(self, op, mgr, det):
        self.op = op
        self.mgr = mgr
        self.det = det   # LingdiDetector

    def run(self):
        self.mgr.navigate_to('lingdi')
        self.det.I_resources()
        print(f"当前资源: {self.det.res0}, 已运输: {len(self.det.transport)}")

        if self.det.res0 + len(self.det.transport) == 6:
            return

        path0 = "tasks/transport/caini/00.png"
        if self.det.secten(path0):
            return

        self.mgr.navigate_to('caini')
        self.op.click_json("tasks/transport/caini/1.png")
        time.sleep(0.5)
        self.mgr.navigate_to('lingdi')
        