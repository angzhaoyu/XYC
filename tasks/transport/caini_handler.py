import time
from core.config_loader import resolve


class CainiHandler:
    def __init__(self, op, mgr, det, vision):
        self.op = op
        self.mgr = mgr
        self.det = det
        self.vision = vision

    def run(self):
        self.mgr.navigate_to('lingdi')
        self.det.I_resources()

        if self.det.res0 + len(self.det.transport) == 6:
            return

        check = resolve("transport.caini.check")
        limit = self.vision.limit_scope(check, scale=1.2)
        if self.vision.find_image(self.op.capture(), check, a_percentage=limit):
            return

        self.mgr.navigate_to('caini')
        click_btn = resolve("transport.caini.click")
        self.op.click_json(click_btn)
        time.sleep(0.5)
        self.mgr.navigate_to('lingdi')