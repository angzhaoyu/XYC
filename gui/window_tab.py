import tkinter as tk
from tkinter import ttk, messagebox
import json
import time
from pathlib import Path

LAYOUT_DIR = Path("data/layouts")


class WindowTab:
    def __init__(self, parent, main_win):
        self.main_win = main_win
        self.frame = ttk.Frame(parent)
        self._gm = None

        self._build()

    def _build(self):
        # ========== 左：窗口列表 ==========
        left = ttk.LabelFrame(self.frame, text="窗口列表", padding=6)
        left.pack(side="left", fill="both", expand=True, padx=(4, 2), pady=4)

        self.win_list = tk.Listbox(left, font=("Consolas", 10), height=15)
        self.win_list.pack(fill="both", expand=True)
        self.win_list.bind("<Double-1>", self._on_activate)

        btn_row = ttk.Frame(left)
        btn_row.pack(fill="x", pady=(4, 0))
        ttk.Button(btn_row, text="🔄 刷新", command=self.refresh, width=8).pack(side="left", padx=2)
        ttk.Button(btn_row, text="📌 激活", command=self._activate_selected, width=8).pack(side="left", padx=2)
        ttk.Button(btn_row, text="全部激活", command=self._activate_all, width=8).pack(side="left", padx=2)

        # ========== 右：尺寸+布局 ==========
        right = ttk.Frame(self.frame)
        right.pack(side="right", fill="y", padx=(2, 4), pady=4)

        # 尺寸控制
        sf = ttk.LabelFrame(right, text="窗口尺寸（屏幕宽的 1/N）", padding=6)
        sf.pack(fill="x")

        self.size_buttons = {}
        for n in [2, 3, 4, 5, 6]:
            btn = ttk.Button(sf, text=f"1/{n}", width=5,
                             command=lambda x=n: self._resize_selected(x))
            btn.pack(side="left", padx=2, pady=2)
            self.size_buttons[n] = btn

        ttk.Button(sf, text="排列全部", command=self._arrange_all).pack(side="left", padx=8)

        # 列数选择
        cf = ttk.Frame(sf)
        cf.pack(fill="x", pady=(4, 0))
        ttk.Label(cf, text="排列列数:").pack(side="left")
        self.var_cols = tk.IntVar(value=3)
        ttk.Spinbox(cf, from_=1, to=10, textvariable=self.var_cols, width=4).pack(side="left", padx=4)

        # 布局管理
        lf = ttk.LabelFrame(right, text="布局样板", padding=6)
        lf.pack(fill="x", pady=(8, 0))

        self.layout_list = tk.Listbox(lf, height=6, font=("Consolas", 9))
        self.layout_list.pack(fill="x")

        btn_row2 = ttk.Frame(lf)
        btn_row2.pack(fill="x", pady=(4, 0))
        ttk.Button(btn_row2, text="💾 保存当前", command=self._save_layout, width=10).pack(side="left", padx=2)
        ttk.Button(btn_row2, text="📂 还原", command=self._restore_layout, width=8).pack(side="left", padx=2)
        ttk.Button(btn_row2, text="🗑️ 删除", command=self._delete_layout, width=6).pack(side="left", padx=2)

        # 窗口信息
        self.lbl_info = ttk.Label(right, text="", font=("Consolas", 9), foreground="gray")
        self.lbl_info.pack(fill="x", pady=(8, 0))

    # ========== 窗口列表 ==========

    def load_windows(self, gm):
        self._gm = gm
        self._refresh_list()
        self._load_layouts()

    def refresh(self):
        if self._gm:
            self._gm.refresh()
            self._refresh_list()

    def _refresh_list(self):
        self.win_list.delete(0, "end")
        if not self._gm:
            return
        for i, wm in enumerate(self._gm.windows):
            rect = wm.get_rect()
            w, h = rect[2] - rect[0], rect[3] - rect[1]
            self.win_list.insert("end", f"[{i}] {wm.hwnd}  {w}x{h}  ({rect[0]},{rect[1]})")

    def _get_selected_wm(self):
        sel = self.win_list.curselection()
        if not sel or not self._gm:
            return None
        idx = sel[0]
        if idx < len(self._gm.windows):
            return self._gm.windows[idx]
        return None

    # ========== 激活 ==========

    def _on_activate(self, event=None):
        self._activate_selected()

    def _activate_selected(self):
        wm = self._get_selected_wm()
        if wm:
            wm.activate()
            rect = wm.get_rect()
            cw, ch = wm.get_client_size()
            self.lbl_info.config(
                text=f"句柄={wm.hwnd}  窗口={rect[2]-rect[0]}x{rect[3]-rect[1]}  客户区={cw}x{ch}"
            )

    def _activate_all(self):
        if self._gm:
            self._gm.activate_all()

    # ========== 尺寸 ==========

    def _resize_selected(self, n):
        """将选中窗口调整为屏幕宽的 1/n"""
        wm = self._get_selected_wm()
        if not wm or not self._gm:
            return
        screen_w, _ = self._gm.get_screen_size()
        target_w = screen_w // n

        # 保持宽高比
        rect = wm.get_rect()
        cur_w = rect[2] - rect[0]
        cur_h = rect[3] - rect[1]
        if cur_w > 0:
            scale = target_w / cur_w
            target_h = int(cur_h * scale)
        else:
            target_h = cur_h

        wm.move(rect[0], rect[1], target_w, max(target_h, 100))
        self._refresh_list()
        self.lbl_info.config(text=f"已调整为 1/{n} 屏幕宽 ({target_w}x{target_h})")

    def _arrange_all(self):
        if self._gm:
            self._gm.arrange(columns=self.var_cols.get())
            self._refresh_list()

    # ========== 布局 ==========

    def _layout_dir(self):
        title = self.main_win.var_title.get().strip().replace(" ", "_")
        d = LAYOUT_DIR / title
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _load_layouts(self):
        self.layout_list.delete(0, "end")
        d = self._layout_dir()
        for f in sorted(d.glob("*.json")):
            self.layout_list.insert("end", f.stem)

    def _save_layout(self):
        if not self._gm or not self._gm.windows:
            return
        from tkinter import simpledialog
        name = simpledialog.askstring("保存布局", "布局名称:")
        if not name:
            return

        layout = []
        for wm in self._gm.windows:
            rect = wm.get_rect()
            cw, ch = wm.get_client_size()
            layout.append({
                "left": rect[0], "top": rect[1],
                "width": rect[2] - rect[0], "height": rect[3] - rect[1],
                "client_width": cw, "client_height": ch,
            })

        path = self._layout_dir() / f"{name}.json"
        path.write_text(json.dumps(layout, indent=2), encoding="utf-8")
        self._load_layouts()
        self.lbl_info.config(text=f"已保存: {name}")

    def _restore_layout(self):
        sel = self.layout_list.curselection()
        if not sel or not self._gm:
            return
        name = self.layout_list.get(sel[0])
        path = self._layout_dir() / f"{name}.json"
        if not path.exists():
            return

        layout = json.loads(path.read_text(encoding="utf-8"))
        for i, wm in enumerate(self._gm.windows):
            j = i % len(layout)
            s = layout[j]
            bw, bh = wm.get_border_size()
            tw = s["client_width"] + bw
            th = s["client_height"] + bh
            wm.move(s["left"], s["top"], tw, th)
            time.sleep(0.03)

        self._refresh_list()
        self.lbl_info.config(text=f"已还原: {name}")

    def _delete_layout(self):
        sel = self.layout_list.curselection()
        if not sel:
            return
        name = self.layout_list.get(sel[0])
        path = self._layout_dir() / f"{name}.json"
        if path.exists():
            path.unlink()
        self._load_layouts()