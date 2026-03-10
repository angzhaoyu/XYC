"""每日任务完成记录"""
import json
from pathlib import Path
from datetime import date


class DailyTracker:
    LOG_DIR = Path("data/daily_log")

    def __init__(self):
        self.LOG_DIR.mkdir(parents=True, exist_ok=True)

    def _path(self, account, region):
        today = date.today().isoformat()
        return self.LOG_DIR / f"{account}_{region}_{today}.json"

    def _load(self, account, region):
        p = self._path(account, region)
        if p.exists():
            return json.loads(p.read_text(encoding='utf-8'))
        return {}

    def _save(self, account, region, data):
        p = self._path(account, region)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

    def is_done(self, account, region, task_name):
        return self._load(account, region).get(task_name, False)

    def mark_done(self, account, region, task_name):
        data = self._load(account, region)
        data[task_name] = True
        self._save(account, region, data)