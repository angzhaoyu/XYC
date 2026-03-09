import time
import os


class BirdTask:
    """海鸟观看任务"""

    def __init__(self, op, mgr, det):
        self.op = op
        self.mgr = mgr
        self.det = det   # LingdiDetector

    def run(self, choose_beast_fn=None, stop_m=False, imgsave=False, mu=True):
        self.mgr.navigate_to('lingdi')
        self.mgr.get_states()
        self.det.I_resources()

        if self.det.xian == 0:
            return None

        # 进入观看界面
        for _ in range(5):
            self.det.I_resources()
            if not self.det.bird:
                return None
            self.op.click(self.det.bird[0])
            time.sleep(1)
            if self.mgr.get_states() == 'guankan':
                break

        if stop_m:
            self.mgr.get_states()

        if self.mgr.get_states() != 'guankan':
            return None

        # 保存截图
        if imgsave:
            self._save_screenshot()

        # 451 检测
        if mu:
            region = self.det.secten("tasks/transport/birds/451.png")
            if region:
                self.mgr.navigate_to('lingdi')
                return None

        # 观看流程
        self.op.click_json("tasks/transport/mouse_combo/guankan.png")
        time.sleep(40)
        self.op.click_json("tasks/transport/mouse_combo/guanbi.png")
        time.sleep(1)

        for _ in range(3):
            state = self.mgr.get_states()
            if state != 'guankan' and state != 'lingdi':
                self.op.click_json("tasks/transport/mouse_combo/jixukan.png")
                time.sleep(5)
                self.op.click_json("tasks/transport/mouse_combo/guanbi.png")

        # 选择海兽（两次）
        if choose_beast_fn:
            self.det.I_resources()
            choose_beast_fn()
            self.det.I_resources()
            choose_beast_fn()

    def _save_screenshot(self):
        save_dir = "./screenshots"
        os.makedirs(save_dir, exist_ok=True)
        index = 1
        while True:
            file_path = os.path.join(save_dir, f"{index:03d}.png")
            if not os.path.exists(file_path):
                break
            index += 1
        self.op.capture(file_path)

