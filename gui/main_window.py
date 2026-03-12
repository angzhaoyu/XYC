import tkinter as tk
from tkinter import ttk
import threading
import json
from pathlib import Path

from gui.task_tab import TaskTab
from gui.window_tab import WindowTab
from parallel.multi_runner import MultiRunner
from core.logger import get_logger

HISTORY_FILE = "data/title_history.json"


class MainWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("XYC 自动化控制台")
        self.root.geometry("960x680")

        self.log = get_logger("gui")
        self.runner = None
        self._thread = None

        # 标题历史
        self.title_history = self._load_history()

        self._build_ui()

    def _build_ui(self):
        # ========== 顶部：窗口标题选择 ==========
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill="x")

        ttk.Label(top, text="窗口标题:").pack(side="left")

        self.var_title = tk.StringVar(value="幸福小渔村")
        self.combo_title = ttk.Combobox(
            top, textvariable=self.var_title,
            values=self.title_history, width=20
        )
        self.combo_title.pack(side="left", padx=4)
        self.combo_title.bind("<<ComboboxSelected>>", self._on_title_select)

        ttk.Button(top, text="📌 记住", command=self._save_title).pack(side="left", padx=2)
        ttk.Button(top, text="🗑️", command=self._del_title, width=3).pack(side="left")
        ttk.Button(top, text="🔍 扫描", command=self._scan_windows).pack(side="left", padx=8)
        self.lbl_count = ttk.Label(top, text="未扫描", foreground="gray")
        self.lbl_count.pack(side="left")

        self.var_sendmsg = tk.BooleanVar(value=True)
        ttk.Checkbutton(top, text="后台操作", variable=self.var_sendmsg).pack(side="right")

        # ========== Tab 页 ==========
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=4)

        # Tab 1: 任务+状态
        self.task_tab = TaskTab(self.notebook, self)
        self.notebook.add(self.task_tab.frame, text="📋 任务")

        # Tab 2: 窗口管理
        self.window_tab = WindowTab(self.notebook, self)
        self.notebook.add(self.window_tab.frame, text="🪟 窗口")

        # Tab 3: 蓝图（占位，PyQt5 嵌入较复杂，提供独立启动按钮）
        bp_frame = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(bp_frame, text="📐 蓝图")
        ttk.Label(bp_frame, text="蓝图编辑器使用 PyQt5，点击下方按钮独立启动").pack(pady=20)
        ttk.Button(bp_frame, text="🚀 启动蓝图编辑器",
                   command=self._launch_blueprint).pack()
        ttk.Button(bp_frame, text="📤 导出到 templates/",
                   command=self._export_blueprint).pack(pady=8)

        # ========== 底部：控制按钮 ==========
        bottom = ttk.Frame(self.root, padding=8)
        bottom.pack(fill="x")

        self.btn_start = ttk.Button(bottom, text="▶️ 启动", command=self._start, width=12)
        self.btn_start.pack(side="left", padx=4)
        self.btn_pause = ttk.Button(bottom, text="⏸️ 暂停", command=self._pause,
                                     width=12, state="disabled")
        self.btn_pause.pack(side="left", padx=4)
        self.btn_stop = ttk.Button(bottom, text="⏹️ 停止", command=self._stop,
                                    width=12, state="disabled")
        self.btn_stop.pack(side="left", padx=4)
        self.lbl_status = ttk.Label(bottom, text="就绪", foreground="gray")
        self.lbl_status.pack(side="right", padx=8)

    # ========== 标题历史 ==========

    def _load_history(self):
        p = Path(HISTORY_FILE)
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
        return ["幸福小渔村"]

    def _save_history(self):
        Path(HISTORY_FILE).parent.mkdir(parents=True, exist_ok=True)
        Path(HISTORY_FILE).write_text(
            json.dumps(self.title_history, ensure_ascii=False), encoding="utf-8"
        )

    def _save_title(self):
        t = self.var_title.get().strip()
        if t and t not in self.title_history:
            self.title_history.append(t)
            self.combo_title["values"] = self.title_history
            self._save_history()

    def _del_title(self):
        t = self.var_title.get().strip()
        if t in self.title_history:
            self.title_history.remove(t)
            self.combo_title["values"] = self.title_history
            self._save_history()

    def _on_title_select(self, event=None):
        self.window_tab.refresh()

    # ========== 扫描 ==========

    def _scan_windows(self):
        from window.window_group import WindowGroupManager
        title = self.var_title.get().strip()
        if not title:
            return
        try:
            gm = WindowGroupManager(title)
            n = len(gm.windows)
            self.lbl_count.config(text=f"{n} 个窗口")
            self.window_tab.load_windows(gm)
            self.task_tab.load_states(gm)
        except Exception as e:
            self.lbl_count.config(text=f"失败: {e}")

    # ========== 启停 ==========

    def _start(self):
        selected = self.task_tab.get_selected_tasks()
        if not selected:
            return
        title = self.var_title.get().strip()
        if not title:
            return

        self.btn_start.config(state="disabled")
        self.btn_pause.config(state="normal")
        self.btn_stop.config(state="normal")
        self.lbl_status.config(text="运行中", foreground="green")

        self.runner = MultiRunner(title)
        self._thread = threading.Thread(target=self._run, args=(selected,), daemon=True)
        self._thread.start()

    def _run(self, selected):
        try:
            self.runner.run(
                selected_tasks=selected,
                enable_loop=self.task_tab.var_loop.get(),
                max_rounds=self.task_tab.var_rounds.get(),
                enable_region_switch=self.task_tab.var_region.get(),
                use_sendmsg=self.var_sendmsg.get(),
                wait_minutes=self.task_tab.var_wait.get(),
            )
        except Exception as e:
            self.log.error(f"运行异常: {e}")
        finally:
            self.root.after(0, self._on_finished)

    def _on_finished(self):
        self.btn_start.config(state="normal")
        self.btn_pause.config(state="disabled", text="⏸️ 暂停")
        self.btn_stop.config(state="disabled")
        self.lbl_status.config(text="已停止", foreground="gray")

    def _pause(self):
        if self.runner:
            self.runner._toggle_pause()
            paused = not self.runner._pause_event.is_set()
            self.btn_pause.config(text="▶️ 恢复" if paused else "⏸️ 暂停")
            self.lbl_status.config(
                text="已暂停" if paused else "运行中",
                foreground="orange" if paused else "green",
            )

    def _stop(self):
        if self.runner:
            self.runner._stop_all()

    # ========== 蓝图 ==========

    def _launch_blueprint(self):
        import subprocess, sys
        title = self.var_title.get().strip()
        subprocess.Popen([sys.executable, "-m", "blueprint.blueprint_editor",
                          "--app", title])

    def _export_blueprint(self):
        from blueprint.blueprint_export import export_blueprint
        title = self.var_title.get().strip().replace(" ", "_")
        proj_dir = Path("blueprint") / title
        if not (proj_dir / "project.json").exists():
            from tkinter import messagebox
            messagebox.showwarning("提示", f"未找到蓝图项目: {proj_dir}")
            return
        ok = export_blueprint(str(proj_dir), "templates")
        from tkinter import messagebox
        if ok:
            messagebox.showinfo("成功", "已导出到 templates/")
        else:
            messagebox.showerror("失败", "导出失败")

    def run(self):
        self.root.mainloop()