import time
import os
from core.config_loader import resolve


class BirdHandler:
    def __init__(self, op, mgr, det, vision):
        self.op = op
        self.mgr = mgr
        self.det = det
        self.vision = vision

    def run(self, choose_beast_fn=None, stop_m=False, imgsave=False, mu=True):
        self.mgr.navigate_to('lingdi')
        self.mgr.get_states()
        self.det.I_resources()
        if self.det.xian == 0:
            return None

        for _ in range(5):
            self.det.I_resources()
            if not self.det.bird:
                return None
            self.op.click(self.det.bird[0])
            time.sleep(1)
            if self.mgr.get_states() == 'guankan':
                break

        if self.mgr.get_states() != 'guankan':
            return None

        if imgsave:
            self._save_screenshot()

        if mu:
            bird_tpl = resolve("transport.birds.bird_451")
            region = self.det.secten(bird_tpl)
            if region:
                self.mgr.navigate_to('lingdi')
                return None

        guankan = resolve("transport.mouse_combo.guankan")
        guanbi = resolve("transport.mouse_combo.guanbi")
        jixukan = resolve("transport.mouse_combo.jixukan")

        self.op.click_json(guankan)
        time.sleep(35)
        self.op.click_json(guanbi)
        time.sleep(1)

        for _ in range(3):
            state = self.mgr.get_states()
            if state != 'guankan' and state != 'lingdi':
                self.op.click_json(jixukan)
                time.sleep(5)
                self.op.click_json(guanbi)

        if choose_beast_fn:
            self.det.I_resources()
            choose_beast_fn()
            self.det.I_resources()
            choose_beast_fn()

    def _save_screenshot(self):
        save_dir = "./data/screenshots"
        os.makedirs(save_dir, exist_ok=True)
        index = 1
        while True:
            fp = os.path.join(save_dir, f"{index:03d}.png")
            if not os.path.exists(fp):
                break
            index += 1
        self.op.capture(fp)