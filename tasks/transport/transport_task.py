import time
from tasks.base_task import BaseTask
from tasks.transport.lingdi_detect import LingdiDetector
from tasks.transport.bird_handler import BirdHandler
from tasks.transport.caini_handler import CainiHandler


class TransportTask(BaseTask):
    TASK_NAME = "transport"
    IS_DAILY = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.det = LingdiDetector(self.vision, self.op)
        self.bird_handler = BirdHandler(self.op, self.mgr, self.det, self.vision)
        self.caini_handler = CainiHandler(self.op, self.mgr, self.det, self.vision)

    def run(self):
        self.log.info("🚀 开始运输")
        self.det.xian = None
        self.det.chose = None
        self.det.shangxian = None

        self.mgr.get_states()
        self.mgr.navigate_to("lingdi")
        self.det.I_resources()

        n_res = self.det.res0
        self.log.info(f"资源: {n_res}")

        while n_res > 0:
            self.choose_beast()
            self.det.I_resources()
            n_res = self.det.res0
            if self.det.xian == 0:
                break

        try:
            if self.det.bird:
                if len(self.det.transport) + len(self.det.bird) != 6:
                    self.bird_handler.run(choose_beast_fn=self.choose_beast)
        except Exception as e:
            self.log.error(f"❌ {e}")

        self.log.info("✅ 运输完成")

    def choose_beast(self):
        self.log.info("选择海兽")
        for attempt in range(5):
            self.mgr.navigate_to('lingdi')
            n_res = self.det.res0
            if n_res == 0:
                return None
            if self.det.xian is not None and self.det.xian == 0:
                return None

            self.mgr.get_states()
            if self.det.resource:
                self.op.click(self.det.resource[0])
            else:
                return None

            time.sleep(0.5)
            self.mgr.get_states()
            self.mgr.states_change("caiji_shangzhen_01")
            state = self.mgr.get_states()

            if state == 'shangzhen':
                self.det.I_beasts()

                if self.det.chose == 0 and self.det.xian == 0:
                    self.mgr.states_change("shangzhen_lingdi_01")
                    return None

                n_sz = (self.det.xian + self.det.chose) // n_res
                n_sz = max(n_sz, 1)
                n_sz = min(n_sz, self.det.shangxian)

                combo_prefix = self.P("transport.mouse_combo.slot_prefix")

                if n_sz == 1:
                    pass
                elif n_sz <= self.det.shangxian:
                    for i in range(n_sz - 1):
                        if self.det.xian == 0:
                            break
                        path = combo_prefix.format(i + 2)
                        self.mgr.get_states()
                        self.op.click_json(path)
                        self.det.xian -= 1
                elif n_sz > self.det.shangxian:
                    self.mgr.get_states()
                    self.op.click_json(self.P("transport.mouse_combo.yjsz"))
                    self.det.xian -= self.det.shangxian + 1

                self.mgr.states_change("shangzhen_lingdi_02")
                self.log.info(f"完成选择, 闲={self.det.xian}")
                return
            else:
                self.log.warning(f"第{attempt+1}次未进入上阵")
                self.mgr.navigate_to('lingdi')
                self.mgr.states_change("shangzhen_lingdi_01")
                time.sleep(1)