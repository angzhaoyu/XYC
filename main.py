from parallel.multi_runner import MultiRunner
from tasks.transport.transport import TransportTask
from tasks.daily_collect import DailyCollect


def make_tasks(runner):
    tasks = {}
    for wm in runner.gm.windows:
        hwnd = wm.hwnd
        tasks[hwnd] = {
            'transport': TransportTask(app_name=hwnd),  # ★ 不需要 mouse_lock 了
            'daily': DailyCollect(app_name=hwnd),
        }
    return tasks


def window_task(hwnd, tasks, round_num, daily_every_n=3, **kwargs):
    t = tasks[hwnd]
    if round_num - daily_every_n == 0:
        try:
            t['daily'].run()
        except Exception as e:
            print(f"❌ DailyCollect: {e}")
    t['transport'].run()


if __name__ == "__main__":
    runner = MultiRunner("幸福小渔村")
    tasks = make_tasks(runner)
    runner.run(window_task, max_rounds=500, tasks=tasks, daily_every_n=1000)