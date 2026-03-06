import time
import pygetwindow as gw
from tasks.transport import TransportTask
from tasks.daily_collect import DailyCollect

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
        time.sleep(0.3)
    except Exception as e:
        if "0" in str(e):
            pass
        else:
            print(f"⚠ 真正的激活错误: {e}")
            return False
    time.sleep(0.5)
    return True

# ========== 配置 ==========
max_rounds = 500
daily_collect_every_n = 50 # 👈 每隔多少轮执行一次 DailyCollect
# ===========================

# 预创建任务
window_tasks = []
for w in windows:
    print(f"初始化窗口: {w.title}, 句柄: {w._hWnd}")
    transport = TransportTask(app_name=w._hWnd)
    daily = DailyCollect(app_name=w._hWnd)  # 👈 每个窗口各创建一个
    window_tasks.append((w, transport, daily))

for round_num in range(max_rounds):
    print(f"\n{'='*60}")
 
    for w, transport, daily in window_tasks:
        print(f"\n▶ 切换窗口: {w.title} (句柄: {w._hWnd})")
        if not safe_activate(w):
            continue

        if round_num - daily_collect_every_n == 0:
            try:
                print(f"  📦 执行 DailyCollect...")
                daily.run()
            except Exception as e:
                print(f"❌ DailyCollect 任务出错: {e}")
    
        # 每轮都跑 TransportTask
        try:
            transport.run()
        except Exception as e:
            print(f"❌ Transport 任务出错: {e}")

        # 仅第 N 轮跑 DailyCollect
        
    print(f"\n⏳ 第 {round_num + 1} 轮完成，等待30秒...")
    time.sleep(60)