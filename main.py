from parallel.multi_runner import MultiRunner
from tasks.transport.transport import TransportTask
from tasks.daily_collect import DailyCollect


def make_tasks(runner):
    """每个窗口只创建一次任务对象"""
    tasks = {}
    for wm in runner.gm.windows:
        hwnd = wm.hwnd
        tasks[hwnd] = {
            'transport': TransportTask(
                app_name=hwnd,
                mouse_lock=runner._mouse_lock,
                pause_event=runner._pause_event,
                stop_event=runner._stop_event,
            ),
            'daily': DailyCollect(
                app_name=hwnd,
                mouse_lock=runner._mouse_lock,
                pause_event=runner._pause_event,
                stop_event=runner._stop_event,
            ),
        }
    return tasks


def window_task(hwnd, tasks, round_num, daily_every_n=3, **kwargs):
    """复用已创建的任务对象"""
    t = tasks[hwnd]

    if round_num - daily_every_n == 0:
        try:
            t['daily'].run()
        except Exception as e:
            print(f"❌ DailyCollect 出错: {e}")

    t['transport'].run()


if __name__ == "__main__":
    runner = MultiRunner("幸福小渔村")
    runner.gm.arrange(columns=6)
    tasks = make_tasks(runner)
    runner.run(window_task, max_rounds=500, tasks=tasks, daily_every_n=0)

