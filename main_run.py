import time
import pygetwindow as gw
from tasks.transport import TransportTask

windows = gw.getWindowsWithTitle("幸福小渔村")
if not windows:
    print("未找到任何窗口，退出")
    exit()

def safe_activate(w):
    """安全激活窗口，忽略pygetwindow的假错误"""
    try:
        if w.isMinimized:
            w.restore()
            time.sleep(0.3)
        w.activate()
    except Exception as e:
        # 错误码0实际上是成功，pygetwindow的bug
        if "0" in str(e):
            pass  # 忽略，实际已激活成功
        else:
            print(f"⚠ 真正的激活错误: {e}")
            return False
    time.sleep(0.5)
    return True

# 预创建任务
window_tasks = []
for w in windows:
    print(f"初始化窗口: {w.title}, 句柄: {w._hWnd}")
    task = TransportTask(app_name=w._hWnd)
    window_tasks.append((w, task))

max_rounds = 500
for round_num in range(max_rounds):
    print(f"\n{'='*60}")
    print(f"📍 第 {round_num + 1} 轮")

    for w, task in window_tasks:
        print(f"\n▶ 切换窗口: {w.title} (句柄: {w._hWnd})")
        
        if not safe_activate(w):
            continue

        try:
            task.run()
        except Exception as e:
            print(f"❌ 任务出错: {e}")

    print(f"\n⏳ 第 {round_num + 1} 轮完成，等待10秒...")
    time.sleep(60)