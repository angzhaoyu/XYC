from core.config_loader import policy
from core.logger import get_logger


class RefreshStrategy:
    def __init__(self):
        cfg = policy().get("transport", {}).get("refresh", {})
        self.ad_limit = cfg.get("ad_limit_per_day", 2)
        self.card_threshold = cfg.get("card_cost_threshold", 3)
        self.card_reserve = cfg.get("card_min_reserve", 5)
        self.only_when_empty = cfg.get("only_when_empty", True)

        self.ad_used = 0
        self.card_cost = 0
        self.log = get_logger("refresh")

    def should_refresh(self, resources, transports, card_count):
        if self.only_when_empty and (resources > 0 or transports > 0):
            return False, "领地非空"
        if self.card_cost >= self.card_threshold:
            return False, f"卡消耗达阈值({self.card_cost}/{self.card_threshold})"
        if card_count < self.card_reserve:
            return False, f"卡不足({card_count}<{self.card_reserve})"
        return True, "可刷新"

    def use_ad(self):
        if self.ad_used >= self.ad_limit:
            return False
        self.ad_used += 1
        return True

    def use_card(self):
        self.card_cost += 1
        return True