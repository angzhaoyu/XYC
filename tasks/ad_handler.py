"""通用广告处理"""
import time
from core.config_loader import resolve
from core.logger import get_logger


class AdHandler:
    def __init__(self, op, mgr):
        self.op = op
        self.mgr = mgr
        self.log = get_logger("ad")

    def watch_and_close(self, valid_states):
        """
        看广告 → 等待 → 关闭
        valid_states: 广告看完后可能的状态列表
        """
        close_btn = resolve("ad.close")
        continue_btn = resolve("ad.continue_watch")

        self.log.info("📺 开始看广告")
        time.sleep(3)
        
        state = self.mgr.get_states()
        if not state:
            # 在广告中，等待
            time.sleep(35)
            for _ in range(3):
                self.op.click_json(close_btn)
                time.sleep(1)
                state = self.mgr.get_states()
                if state in valid_states:
                    return True

                # 可能需要继续观看
                self.op.click_json(continue_btn)
                time.sleep(5)
                self.op.click_json(close_btn)
                time.sleep(1)

        return self.mgr.get_states() in valid_states