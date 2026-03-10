import tkinter as tk
from tkinter import ttk, scrolledtext
import logging
import queue


class QueueHandler(logging.Handler):
    """把日志发到队列，GUI 线程安全读取"""

    def __init__(self, q):
        super().__init__()
        self.q = q

    def emit(self, record):
        self.q.put(self.format(record))


class LogViewer:
    def __init__(self, parent, poll_interval=100):
        self.frame = ttk.LabelFrame(parent, text="日志", padding=4)
        self.poll_interval = poll_interval
        self.q = queue.Queue()

        # 文本框
        self.text = scrolledtext.ScrolledText(
            self.frame, wrap="word", height=20, font=("Consolas", 9),
            state="disabled", bg="#1e1e1e", fg="#d4d4d4",
        )
        self.text.pack(fill="both", expand=True)

        # 清除按钮
        ttk.Button(self.frame, text="清除", command=self._clear, width=6).pack(
            anchor="e", pady=(4, 0))

        # 注册到根 logger
        handler = QueueHandler(self.q)
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(threadName)s] %(message)s",
                              datefmt="%H:%M:%S")
        )
        logging.getLogger("XYC").addHandler(handler)

        # 定时拉取
        self._poll()

    def _poll(self):
        while not self.q.empty():
            try:
                msg = self.q.get_nowait()
                self.text.config(state="normal")
                self.text.insert("end", msg + "\n")
                self.text.see("end")
                self.text.config(state="disabled")
            except queue.Empty:
                break
        self.frame.after(self.poll_interval, self._poll)

    def _clear(self):
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.config(state="disabled")