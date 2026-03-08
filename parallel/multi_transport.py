"""
多窗口并行运输任务
用法：
    python -m parallel.multi_transport
"""
import sys
import threading
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from tools.window_manager import WindowGroupManager
from tasks.transport.transport import TransportTask


class MultiTransportRunner:
    def __init__(self, app_title, max_workers=None):
        self.app_title = app_title
        self.gm = WindowGroupManager(app_title)
        self._lock = threading.RLock()
        self.max_workers = max_workers or 6

        # ★ 记录正在运行的句柄
        self._running_hwnds = set()
        self._running_lock = threading.Lock()

    def run_loop(self, interval=10):
        """
        持续监控：每隔 interval 秒扫描一次
        - 发现新窗口 → 自动加入
        - 窗口关闭 → 线程自然退出
        """
        pool = ThreadPoolExecutor(max_workers=self.max_workers,
                                  thread_name_prefix="transport")
        print(f"🔄 监控模式启动，每 {interval}s 扫描一次新窗口")
        print("   按 Ctrl+C 停止\n")

        try:
            while True:
                self.gm.refresh()

                for wm in self.gm.windows:
                    hwnd = wm.hwnd

                    with self._running_lock:
                        if hwnd in self._running_hwnds:
                            continue  # 已在运行，跳过
                        self._running_hwnds.add(hwnd)

                    print(f"🆕 发现新窗口 句柄={hwnd}，提交任务")
                    future = pool.submit(self._run_single, hwnd)
                    future.add_done_callback(
                        lambda f, h=hwnd: self._on_done(f, h)
                    )

                time.sleep(interval)

        except KeyboardInterrupt:
            print("\n⏹️ 监控已停止")
            pool.shutdown(wait=False)

    def _run_single(self, hwnd):
        """单窗口任务"""
        thread_name = threading.current_thread().name
        print(f"  🧵 [{thread_name}] 句柄={hwnd} 开始")
        task = TransportTask(app_name=hwnd, mouse_lock=self._lock)
        task.run()

    def _on_done(self, future, hwnd):
        """任务结束回调：从运行集合中移除"""
        with self._running_lock:
            self._running_hwnds.discard(hwnd)

        try:
            future.result()
            print(f"✅ 句柄={hwnd} 任务完成")
        except Exception as e:
            print(f"❌ 句柄={hwnd} 异常: {e}")

    def run_all(self):
        """所有窗口并行执行运输任务"""
        if not self.gm.windows:
            print("❌ 没有找到窗口")
            return

        n = len(self.gm.windows)
        print(f"\n🚀 启动 {n} 个窗口的并行运输任务")
        print(f"   鼠标锁: {self._lock}")
        print(f"   最大并发: {self.max_workers}")
        print("=" * 60)

        with ThreadPoolExecutor(max_workers=self.max_workers,
                                thread_name_prefix="transport") as pool:
            futures = {}
            for i, wm in enumerate(self.gm.windows):
                future = pool.submit(self._run_single, wm.hwnd, i)
                futures[future] = (i, wm.hwnd)

            for future in as_completed(futures):
                idx, hwnd = futures[future]
                try:
                    future.result()
                    print(f"✅ 窗口[{idx}](句柄{hwnd}) 任务完成")
                except Exception as e:
                    print(f"❌ 窗口[{idx}](句柄{hwnd}) 异常: {e}")

        print("\n" + "=" * 60)
        print("🏁 所有窗口任务结束")

    def _run_single(self, hwnd, index):
        """单个窗口的任务（在子线程中运行）"""
        thread_name = threading.current_thread().name
        print(f"  🧵 [{thread_name}] 窗口[{index}] 句柄={hwnd} 开始")

        task = TransportTask(
            app_name=hwnd,          # 传句柄，精确定位窗口
            mouse_lock=self._lock,  # 共享鼠标锁
        )
        task.run()

    def run_sequential(self):
        """顺序执行（调试用）"""
        for i, wm in enumerate(self.gm.windows):
            print(f"\n--- 窗口[{i}] 句柄={wm.hwnd} ---")
            task = TransportTask(
                app_name=wm.hwnd,
                mouse_lock=self._lock,
            )
            task.run()


if __name__ == "__main__":
    runner = MultiTransportRunner("幸福小渔村")

    # 先排列窗口（可选）
    runner.gm.arrange(columns=6)

    # 并行执行
    runner.run_all()

    # 或顺序调试
    # runner.run_sequential()