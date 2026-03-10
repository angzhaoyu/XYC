"""换区管理"""
import time
from core.config_loader import accounts as load_accounts
from core.logger import get_logger
from window.window_manager import WindowManager


class RegionManager:
    def __init__(self, op, mgr, vision):
        self.op = op
        self.mgr = mgr
        self.vision = vision
        self.log = get_logger("region")
        self.cfg = load_accounts().get("region_switch", {})

    def get_regions(self, account_name):
        for acc in load_accounts().get("accounts", []):
            if acc["name"] == account_name:
                return acc.get("regions", [])
        return []

    def switch_to(self, target_region):
        self.log.info(f"🔄 切换到: {target_region}")
        self.mgr.navigate_to("huanqu")

        region_templates = self.cfg.get("region_list", {})
        tpl = region_templates.get(target_region)
        if not tpl:
            self.log.error(f"未配置: {target_region}")
            return False

        region = self.vision.find_image(self.op.capture(), tpl)
        if not region:
            self.log.error(f"未找到: {target_region}")
            return False

        self.op.click(region)
        time.sleep(1)

        confirm = self.cfg.get("confirm")
        if confirm:
            self.op.click_json(confirm)
        time.sleep(5)

        self._refresh_hwnd()
        return True

    def _refresh_hwnd(self):
        try:
            title = self.op.wm.title
            self.op.wm = WindowManager(title)
            self.log.info(f"🔄 句柄刷新: {self.op.wm.hwnd}")
        except Exception as e:
            self.log.error(f"句柄刷新失败: {e}")