import tkinter as tk
from tkinter import ttk
import threading

TASK_REGISTRY = [
    ("商店领取",   "daily", "tasks.daily.shop",      "ShopTask"),
    ("签到",       "daily", "tasks.daily.checkin",    "CheckinTask"),
    ("转盘",       "daily", "tasks.daily.zhp",        "ZhpTask"),
    ("排行榜",     "daily", "tasks.daily.ranking",    "RankingTask"),
    ("道具商店",   "daily", "tasks.daily.daoju",      "DaojuTask"),
    ("日常领取",   "daily", "tasks.daily.richang",    "RichangTask"),
    ("领地搬运",   "loop",  "tasks.transport.transport_task", "TransportTask"),
    ("自动探秘",   "loop",  "tasks.explore.explore_task",     "ExploreTask"),
]


class TaskTab:
    def __init__(self, parent, main_win):
        self.main_win = main_win
        self.frame = ttk.Frame(parent)
        self.task_vars = {}
        self._gm = None

        self._build()

    def _build(self):
        paned = ttk.PanedWindow(self.frame, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=4, pady=4)

        # ========== 左：任务+循环 ==========
        left = ttk.Frame(paned, width=280)
        paned.add(left, weight=0)

        # 任务选择
        tf = ttk.LabelFrame(left, text="任务选择", padding=6)
        tf.pack(fill="both", expand=True)

        btn_row = ttk.Frame(tf)
        btn_row.pack(fill="x", pady=(0, 4))
        ttk.Button(btn_row, text="全选", command=self._all, width=5).pack(side="left", padx=2)
        ttk.Button(btn_row, text="全不选", command=self._none, width=5).pack(side="left", padx=2)

        ttk.Label(tf, text="── 每日 ──", foreground="blue").pack(anchor="w")
        for name, cat, mod, cls in TASK_REGISTRY:
            if cat == "daily":
                var = tk.BooleanVar(value=True)
                self.task_vars[(mod, cls)] = var
                ttk.Checkbutton(tf, text=name, variable=var).pack(anchor="w", padx=12)

        ttk.Label(tf, text="── 循环 ──", foreground="green").pack(anchor="w", pady=(8, 0))
        for name, cat, mod, cls in TASK_REGISTRY:
            if cat == "loop":
                var = tk.BooleanVar(value=True)
                self.task_vars[(mod, cls)] = var
                ttk.Checkbutton(tf, text=name, variable=var).pack(anchor="w", padx=12)

        # 循环设置
        lf = ttk.LabelFrame(left, text="循环设置", padding=6)
        lf.pack(fill="x", pady=(4, 0))

        self.var_loop = tk.BooleanVar(value=True)
        ttk.Checkbutton(lf, text="启用循环", variable=self.var_loop).grid(row=0, column=0)
        ttk.Label(lf, text="轮数:").grid(row=0, column=1, padx=(8, 0))
        self.var_rounds = tk.IntVar(value=100)
        ttk.Spinbox(lf, from_=1, to=9999, textvariable=self.var_rounds, width=5).grid(row=0, column=2)

        ttk.Label(lf, text="间隔(分钟):").grid(row=1, column=0, sticky="w", pady=2)
        self.var_wait = tk.IntVar(value=3)
        ttk.Spinbox(lf, from_=0, to=120, textvariable=self.var_wait, width=5).grid(row=1, column=1, columnspan=2, sticky="w")

        self.var_region = tk.BooleanVar(value=False)
        ttk.Checkbutton(lf, text="启用换区", variable=self.var_region).grid(row=2, column=0, columnspan=3, sticky="w")

        # ========== 右：状态显示 ==========
        right = ttk.Frame(paned)
        paned.add(right, weight=1)

        sf = ttk.LabelFrame(right, text="页面状态（点击导航所有窗口）", padding=6)
        sf.pack(fill="both", expand=True)

        self.state_listbox = tk.Listbox(sf, font=("Consolas", 11), selectmode="single",
                                         bg="#1e1e1e", fg="#d4d4d4", selectforeground="white",
                                         selectbackground="#2196F3")
        self.state_listbox.pack(fill="both", expand=True)
        self.state_listbox.bind("<Double-1>", self._on_state_click)

        ttk.Button(sf, text="🔄 刷新状态", command=self._refresh_states).pack(anchor="e", pady=(4, 0))

    # ========== 任务 ==========

    def _all(self):
        for v in self.task_vars.values():
            v.set(True)

    def _none(self):
        for v in self.task_vars.values():
            v.set(False)

    def get_selected_tasks(self):
        import importlib
        selected = []
        for (mod_path, cls_name), var in self.task_vars.items():
            if var.get():
                try:
                    mod = importlib.import_module(mod_path)
                    selected.append(getattr(mod, cls_name))
                except Exception as e:
                    print(f"⚠️ 加载失败 {mod_path}.{cls_name}: {e}")
        return selected

    # ========== 状态 ==========

    def load_states(self, gm):
        """扫描后加载状态列表"""
        self._gm = gm
        self._refresh_states()

    def _refresh_states(self):
        self.state_listbox.delete(0, "end")
        try:
            from core.state_manager import StateManager
            from core.operator import Operator
            if not self._gm or not self._gm.windows:
                return
            # 用第一个窗口读状态配置
            hwnd = self._gm.windows[0].hwnd
            op = Operator(app_name=hwnd, use_sendmsg=True)
            mgr = StateManager("tasks/states/states.txt", operator=op)

            for name in mgr.page_order:
                self.state_listbox.insert("end", f"  {name}")
        except Exception as e:
            self.state_listbox.insert("end", f"加载失败: {e}")

    def _on_state_click(self, event):
        """双击状态 → 所有窗口导航到该状态"""
        sel = self.state_listbox.curselection()
        if not sel or not self._gm:
            return
        target = self.state_listbox.get(sel[0]).strip()
        if not target or target.startswith("加载"):
            return

        # 在线程中并行导航所有窗口
        def navigate_all():
            from core.operator import Operator
            from core.state_manager import StateManager
            for wm in self._gm.windows:
                try:
                    op = Operator(app_name=wm.hwnd, use_sendmsg=True)
                    mgr = StateManager("tasks/states/states.txt", operator=op)
                    mgr.navigate_to(target)
                except Exception as e:
                    print(f"❌ {wm.hwnd} 导航到 {target} 失败: {e}")

        threading.Thread(target=navigate_all, daemon=True).start()