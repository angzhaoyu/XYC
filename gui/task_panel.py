import tkinter as tk
from tkinter import ttk


# 任务注册表：(显示名, 分类, 模块路径, 类名)
TASK_REGISTRY = [
    # 每日任务
    ("商店领取",     "daily",     "tasks.daily.shop",      "ShopTask"),
    ("签到",         "daily",     "tasks.daily.checkin",    "CheckinTask"),
    ("转盘",         "daily",     "tasks.daily.zhp",        "ZhpTask"),
    ("排行榜",       "daily",     "tasks.daily.ranking",    "RankingTask"),
    ("道具商店",     "daily",     "tasks.daily.daoju",      "DaojuTask"),
    ("日常领取",     "daily",     "tasks.daily.richang",    "RichangTask"),
    # 循环任务
    ("领地搬运",     "loop",      "tasks.transport.transport_task", "TransportTask"),
    ("自动探秘",     "loop",      "tasks.explore.explore_task",     "ExploreTask"),
]


class TaskPanel:
    def __init__(self, parent):
        self.frame = ttk.LabelFrame(parent, text="任务选择", padding=6)
        self.vars = {}
        self._build()

    def _build(self):
        # 全选按钮
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(fill="x", pady=(0, 4))
        ttk.Button(btn_frame, text="全选", command=self._select_all, width=6).pack(
            side="left", padx=2)
        ttk.Button(btn_frame, text="全不选", command=self._deselect_all, width=6).pack(
            side="left", padx=2)

        # 每日任务
        ttk.Label(self.frame, text="── 每日任务 ──",
                  foreground="blue").pack(anchor="w", pady=(4, 2))

        for name, cat, mod, cls in TASK_REGISTRY:
            if cat == "daily":
                var = tk.BooleanVar(value=True)
                self.vars[(mod, cls)] = var
                ttk.Checkbutton(self.frame, text=name,
                                variable=var).pack(anchor="w", padx=12)

        # 循环任务
        ttk.Label(self.frame, text="── 循环任务 ──",
                  foreground="green").pack(anchor="w", pady=(8, 2))

        for name, cat, mod, cls in TASK_REGISTRY:
            if cat == "loop":
                var = tk.BooleanVar(value=True)
                self.vars[(mod, cls)] = var
                ttk.Checkbutton(self.frame, text=name,
                                variable=var).pack(anchor="w", padx=12)

    def get_selected(self):
        """返回选中的任务类列表"""
        import importlib
        selected = []
        for (mod_path, cls_name), var in self.vars.items():
            if var.get():
                try:
                    mod = importlib.import_module(mod_path)
                    cls = getattr(mod, cls_name)
                    selected.append(cls)
                except Exception as e:
                    print(f"⚠️ 加载 {mod_path}.{cls_name} 失败: {e}")
        return selected

    def _select_all(self):
        for v in self.vars.values():
            v.set(True)

    def _deselect_all(self):
        for v in self.vars.values():
            v.set(False)