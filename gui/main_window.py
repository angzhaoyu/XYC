import tkinter as tk
from tkinter import ttk, messagebox
import threading

from gui.task_panel import TaskPanel
from gui.log_viewer import LogViewer
from parallel.multi_runner import MultiRunner
from core.logger import get_logger


class MainWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("XYC 自动化控制台")
        self.root.geometry("860x620")
        self.root.resizable(True, True)

        self.log = get_logger("gui")
        self.runner = None
        self._thread = None

        self._build_ui()

    # ========== UI 构建 ==========

    def _build_ui(self):
        # 顶部：窗口设置
        top = ttk.LabelFrame(self.root, text="窗口设置", padding=8)
        top.pack(fill="x", padx=8, pady=(8, 4))

        ttk.Label(top, text="窗口标题:").grid(row=0, column=0, sticky="w")
        self.var_title = tk.StringVar(value="幸福小渔村")
        ttk.Entry(top, textvariable=self.var_title, width=20).grid(row=0, column=1, padx=4)

        ttk.Label(top, text="模式:").grid(row=0, column=2, padx=(16, 0))
        self.var_sendmsg = tk.BooleanVar(value=True)
        ttk.Checkbutton(top, text="后台操作(SendMessage)",
                        variable=self.var_sendmsg).grid(row=0, column=3)

        ttk.Button(top, text="🔍 扫描窗口", command=self._scan_windows).grid(
            row=0, column=4, padx=(16, 0))
        self.lbl_window_count = ttk.Label(top, text="未扫描")
        self.lbl_window_count.grid(row=0, column=5, padx=8)

        # 中间左：任务选择 + 循环设置
        mid = ttk.Frame(self.root)
        mid.pack(fill="both", expand=True, padx=8, pady=4)

        left = ttk.Frame(mid, width=320)
        left.pack(side="left", fill="y", padx=(0, 4))
        left.pack_propagate(False)

        # 任务面板
        self.task_panel = TaskPanel(left)
        self.task_panel.frame.pack(fill="both", expand=True)

        # 循环设置
        loop_frame = ttk.LabelFrame(left, text="循环设置", padding=6)
        loop_frame.pack(fill="x", pady=(4, 0))

        self.var_loop = tk.BooleanVar(value=True)
        ttk.Checkbutton(loop_frame, text="启用循环",
                        variable=self.var_loop,
                        command=self._on_loop_toggle).grid(row=0, column=0, sticky="w")

        ttk.Label(loop_frame, text="轮数:").grid(row=0, column=1, padx=(12, 0))
        self.var_rounds = tk.IntVar(value=100)
        self.spin_rounds = ttk.Spinbox(loop_frame, from_=1, to=9999,
                                        textvariable=self.var_rounds, width=6)
        self.spin_rounds.grid(row=0, column=2, padx=4)

        self.var_region = tk.BooleanVar(value=False)
        ttk.Checkbutton(loop_frame, text="启用换区",
                        variable=self.var_region).grid(row=1, column=0,
                                                       columnspan=3, sticky="w", pady=2)

        # 中间右：日志
        right = ttk.Frame(mid)
        right.pack(side="right", fill="both", expand=True)
        self.log_viewer = LogViewer(right)
        self.log_viewer.frame.pack(fill="both", expand=True)

        # 底部：控制按钮
        bottom = ttk.Frame(self.root, padding=8)
        bottom.pack(fill="x")

        self.btn_start = ttk.Button(bottom, text="▶️ 启动",
                                     command=self._start, width=12)
        self.btn_start.pack(side="left", padx=4)

        self.btn_pause = ttk.Button(bottom, text="⏸️ 暂停",
                                     command=self._pause, width=12, state="disabled")
        self.btn_pause.pack(side="left", padx=4)

        self.btn_stop = ttk.Button(bottom, text="⏹️ 停止",
                                    command=self._stop, width=12, state="disabled")
        self.btn_stop.pack(side="left", padx=4)

        self.lbl_status = ttk.Label(bottom, text="就绪", foreground="gray")
        self.lbl_status.pack(side="right", padx=8)

    # ========== 事件 ==========

    def _on_loop_toggle(self):
        state = "normal" if self.var_loop.get() else "disabled"
        self.spin_rounds.config(state=state)

    def _scan_windows(self):
        from window.window_group import WindowGroupManager
        title = self.var_title.get().strip()
        if not title:
            messagebox.showwarning("提示", "请输入窗口标题")
            return
        try:
            gm = WindowGroupManager(title)
            count = len(gm.windows)
            self.lbl_window_count.config(text=f"找到 {count} 个窗口")
            self.log.info(f"扫描到 {count} 个 '{title}' 窗口")
        except Exception as e:
            self.lbl_window_count.config(text="扫描失败")
            self.log.error(f"扫描失败: {e}")

    def _start(self):
        selected = self.task_panel.get_selected()
        if not selected:
            messagebox.showwarning("提示", "请至少选择一个任务")
            return

        title = self.var_title.get().strip()
        if not title:
            messagebox.showwarning("提示", "请输入窗口标题")
            return

        self.btn_start.config(state="disabled")
        self.btn_pause.config(state="normal")
        self.btn_stop.config(state="normal")
        self.lbl_status.config(text="运行中", foreground="green")

        self.runner = MultiRunner(title)

        self._thread = threading.Thread(
            target=self._run_tasks,
            args=(selected,),
            daemon=True,
        )
        self._thread.start()

    def _run_tasks(self, selected):
        try:
            self.runner.run(
                selected_tasks=selected,
                enable_loop=self.var_loop.get(),
                max_rounds=self.var_rounds.get(),
                enable_region_switch=self.var_region.get(),
                use_sendmsg=self.var_sendmsg.get(),
            )
        except Exception as e:
            self.log.error(f"运行异常: {e}")
        finally:
            self.root.after(0, self._on_finished)

    def _on_finished(self):
        self.btn_start.config(state="normal")
        self.btn_pause.config(state="disabled")
        self.btn_stop.config(state="disabled")
        self.lbl_status.config(text="已停止", foreground="gray")

    def _pause(self):
        if self.runner:
            self.runner._toggle_pause()
            is_paused = not self.runner._pause_event.is_set()
            self.btn_pause.config(text="▶️ 恢复" if is_paused else "⏸️ 暂停")
            self.lbl_status.config(
                text="已暂停" if is_paused else "运行中",
                foreground="orange" if is_paused else "green",
            )

    def _stop(self):
        if self.runner:
            self.runner._stop_all()

    def run(self):
        self.root.mainloop()