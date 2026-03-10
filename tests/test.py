"""
后台点击测试工具
测试 "幸福小渔村" 窗口是否支持后台点击（不需要弹到前台）

测试方法：
    1. SendMessage  WM_LBUTTONDOWN/UP
    2. PostMessage  WM_LBUTTONDOWN/UP
    3. SendMessage  WM_LBUTTONDOWN/UP（客户区坐标转换）
    4. PostMessage  + WM_ACTIVATE 预激活

使用方式：
    python test_background_click.py
    
    运行后会提示你把目标窗口用其他窗口挡住，
    然后自动在窗口中心点击，观察游戏是否有响应。
"""

import ctypes
import ctypes.wintypes
import win32gui
import win32con
import win32api
import time
import struct

# ================================================================
#  基础工具
# ================================================================

def find_all_windows(title):
    """查找所有匹配标题的窗口"""
    results = []
    def callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            name = win32gui.GetWindowText(hwnd)
            if title in name:
                results.append((hwnd, name))
    win32gui.EnumWindows(callback, None)
    return results


def get_client_center(hwnd):
    """获取窗口客户区中心的坐标（相对于客户区左上角）"""
    rect = win32gui.GetClientRect(hwnd)
    cx = rect[2] // 2
    cy = rect[3] // 2
    return cx, cy


def make_lparam(x, y):
    """将 (x, y) 打包成 lParam"""
    return (y << 16) | (x & 0xFFFF)


def print_header(text):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}")


# ================================================================
#  测试方法
# ================================================================

def test_send_message(hwnd, x, y, name="SendMessage"):
    """
    方法1: SendMessage（同步，等窗口处理完才返回）
    """
    print(f"\n  🧪 测试 {name}...")
    print(f"     坐标: ({x}, {y})")

    lParam = make_lparam(x, y)

    try:
        win32gui.SendMessage(hwnd, win32con.WM_LBUTTONDOWN,
                             win32con.MK_LBUTTON, lParam)
        time.sleep(0.05)
        win32gui.SendMessage(hwnd, win32con.WM_LBUTTONUP,
                             0, lParam)
        print(f"     ✅ 发送成功（SendMessage）")
        return True
    except Exception as e:
        print(f"     ❌ 发送失败: {e}")
        return False


def test_post_message(hwnd, x, y, name="PostMessage"):
    """
    方法2: PostMessage（异步，放入消息队列立即返回）
    """
    print(f"\n  🧪 测试 {name}...")
    print(f"     坐标: ({x}, {y})")

    lParam = make_lparam(x, y)

    try:
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN,
                             win32con.MK_LBUTTON, lParam)
        time.sleep(0.05)
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP,
                             0, lParam)
        print(f"     ✅ 发送成功（PostMessage）")
        return True
    except Exception as e:
        print(f"     ❌ 发送失败: {e}")
        return False


def test_post_with_activate(hwnd, x, y, name="PostMessage+Activate"):
    """
    方法3: 先发 WM_ACTIVATE 再 PostMessage（有些程序需要）
    """
    print(f"\n  🧪 测试 {name}...")
    print(f"     坐标: ({x}, {y})")

    lParam = make_lparam(x, y)

    try:
        # 先告诉窗口"你被激活了"（但不真的弹到前台）
        win32gui.SendMessage(hwnd, win32con.WM_ACTIVATE,
                             win32con.WA_ACTIVE, 0)
        time.sleep(0.02)

        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN,
                             win32con.MK_LBUTTON, lParam)
        time.sleep(0.05)
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP,
                             0, lParam)
        print(f"     ✅ 发送成功（PostMessage+Activate）")
        return True
    except Exception as e:
        print(f"     ❌ 发送失败: {e}")
        return False


def test_send_with_move(hwnd, x, y, name="SendMessage+MouseMove"):
    """
    方法4: 先发 WM_MOUSEMOVE 再点击（模拟真实鼠标移动+点击）
    """
    print(f"\n  🧪 测试 {name}...")
    print(f"     坐标: ({x}, {y})")

    lParam = make_lparam(x, y)

    try:
        # 先移动鼠标到目标位置
        win32gui.SendMessage(hwnd, win32con.WM_MOUSEMOVE, 0, lParam)
        time.sleep(0.02)

        win32gui.SendMessage(hwnd, win32con.WM_LBUTTONDOWN,
                             win32con.MK_LBUTTON, lParam)
        time.sleep(0.05)
        win32gui.SendMessage(hwnd, win32con.WM_LBUTTONUP,
                             0, lParam)
        print(f"     ✅ 发送成功（SendMessage+MouseMove）")
        return True
    except Exception as e:
        print(f"     ❌ 发送失败: {e}")
        return False


def test_click_at_custom_pos(hwnd, x, y):
    """
    方法5: 指定任意坐标点击（用于测试特定按钮）
    """
    print(f"\n  🧪 测试自定义坐标点击...")
    print(f"     坐标: ({x}, {y})")

    lParam = make_lparam(x, y)

    try:
        win32gui.PostMessage(hwnd, win32con.WM_MOUSEMOVE, 0, lParam)
        time.sleep(0.02)
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONDOWN,
                             win32con.MK_LBUTTON, lParam)
        time.sleep(0.05)
        win32gui.PostMessage(hwnd, win32con.WM_LBUTTONUP,
                             0, lParam)
        print(f"     ✅ 发送成功")
        return True
    except Exception as e:
        print(f"     ❌ 发送失败: {e}")
        return False


# ================================================================
#  综合测试
# ================================================================

def run_single_test(hwnd, method_func, x, y, method_name):
    """运行单个测试并等待用户确认"""
    success = method_func(hwnd, x, y, method_name)
    if success:
        result = input(f"     👀 游戏有反应吗？(y/n/q退出): ").strip().lower()
        return result
    return 'n'


def run_all_tests(hwnd):
    """运行所有测试方法"""
    cx, cy = get_client_center(hwnd)
    cw, ch = win32gui.GetClientRect(hwnd)[2], win32gui.GetClientRect(hwnd)[3]

    print(f"\n📋 窗口信息:")
    print(f"   句柄: {hwnd}")
    print(f"   标题: {win32gui.GetWindowText(hwnd)}")
    print(f"   客户区: {cw} x {ch}")
    print(f"   点击位置: 中心 ({cx}, {cy})")

    print(f"\n⚠️  请注意观察游戏画面是否有点击反应！")
    print(f"   （如有按钮在中心附近，效果更明显）")

    tests = [
        ("SendMessage",            test_send_message),
        ("PostMessage",            test_post_message),
        ("PostMessage+Activate",   test_post_with_activate),
        ("SendMessage+MouseMove",  test_send_with_move),
    ]

    results = {}

    for name, func in tests:
        print(f"\n{'─'*40}")
        r = run_single_test(hwnd, func, cx, cy, name)
        if r == 'q':
            break
        results[name] = (r == 'y')
        time.sleep(0.5)

    return results


# ================================================================
#  连续点击测试（更容易观察效果）
# ================================================================

def rapid_click_test(hwnd, method='post', count=1, interval=0.5, x=None, y=None):
    """
    连续点击测试 — 更容易观察到效果

    Args:
        hwnd:     窗口句柄
        method:   'send' 或 'post'
        count:    点击次数
        interval: 每次间隔(秒)
        x, y:     点击坐标（默认=客户区中心）
    """
    if x is None or y is None:
        x, y = get_client_center(hwnd)

    lParam = make_lparam(x, y)
    send = win32gui.SendMessage if method == 'send' else win32gui.PostMessage

    print(f"\n🔄 连续后台点击测试:")
    print(f"   方法: {method}Message")
    print(f"   坐标: ({x}, {y})")
    print(f"   次数: {count}  间隔: {interval}s")
    print(f"   ⚠️  请把其他窗口盖在游戏上面，观察游戏是否有反应\n")

    time.sleep(2)  # 给用户时间切走

    for i in range(count):
        send(hwnd, win32con.WM_MOUSEMOVE, 0, lParam)
        time.sleep(0.01)
        send(hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lParam)
        time.sleep(0.05)
        send(hwnd, win32con.WM_LBUTTONUP, 0, lParam)
        print(f"   点击 {i+1}/{count}")
        time.sleep(interval)


    print(f"\n✅ 连续点击完成，请检查游戏是否有反应")


# ================================================================
#  主程序
# ================================================================

def main():
    TITLE = "幸福小渔村"

    print_header(f"后台点击测试工具 — '{TITLE}'")

    # 1. 查找窗口
    windows = find_all_windows(TITLE)
    if not windows:
        print(f"❌ 未找到 '{TITLE}' 窗口，请先打开游戏")
        return

    print(f"\n🔍 找到 {len(windows)} 个窗口:")
    for i, (hwnd, name) in enumerate(windows):
        rect = win32gui.GetWindowRect(hwnd)
        w, h = rect[2]-rect[0], rect[3]-rect[1]
        print(f"   [{i}] 句柄={hwnd}  大小={w}x{h}  标题={name}")

    # 2. 选择窗口
    if len(windows) == 1:
        choice = 0
    else:
        choice = input(f"\n选择测试窗口 [0-{len(windows)-1}] (默认0): ").strip()
        choice = int(choice) if choice else 0

    hwnd = windows[choice][0]

    # 3. 选择测试模式
    print(f"\n📌 测试模式:")
    print(f"   [1] 逐个方法测试（每次点一下，你确认有没有反应）")
    print(f"   [2] 连续点击测试（快速点10次，更容易观察）")
    print(f"   [3] 指定坐标点击（手动输入x,y）")
    print(f"   [4] 全部测试")

    mode = input(f"\n选择模式 [1/2/3/4] (默认1): ").strip() or "1"

    if mode == "1":
        # 逐个测试
        print(f"\n⚠️  接下来会逐个测试 4 种后台点击方法")
        print(f"   请用其他窗口挡住游戏，观察游戏有没有反应")
        input(f"   准备好后按 Enter...")

        results = run_all_tests(hwnd)

        print_header("测试结果汇总")
        any_ok = False
        for name, ok in results.items():
            status = "✅ 有效" if ok else "❌ 无效"
            print(f"   {name:30s}  {status}")
            if ok:
                any_ok = True

        if any_ok:
            print(f"\n🎉 后台点击可行！可以使用真并行方案（方案3）")
        else:
            print(f"\n😢 后台点击不可行，建议使用多线程+鼠标锁方案（方案1）")

    elif mode == "2":
        # 连续点击
        print(f"\n选择方法: [s]SendMessage / [p]PostMessage (默认p)")
        m = input(f"   ").strip().lower() or 'p'
        method = 'send' if m == 's' else 'post'

        print(f"\n⚠️  2秒后开始连续点击，请立刻切到其他窗口挡住游戏！")
        rapid_click_test(hwnd, method=method, count=10, interval=0.5)

        ok = input(f"\n👀 游戏有反应吗？(y/n): ").strip().lower()
        if ok == 'y':
            print(f"🎉 后台点击可行！")
        else:
            print(f"😢 此方法后台点击无效")

    elif mode == "3":
        # 指定坐标
        cx, cy = get_client_center(hwnd)
        print(f"\n   客户区中心: ({cx}, {cy})")
        pos = input(f"   输入坐标 x,y (默认中心): ").strip()
        if pos:
            x, y = map(int, pos.split(","))
        else:
            x, y = cx, cy

        print(f"\n⚠️  2秒后开始连续点击 ({x},{y})，请切走！")
        rapid_click_test(hwnd, method='post', count=10, interval=0.5, x=x, y=y)

    elif mode == "4":
        # 全部测试
        print(f"\n⚠️  将依次测试所有方法")
        input(f"   请挡住游戏窗口，准备好后按 Enter...")

        results = run_all_tests(hwnd)

        # 再测连续点击
        for method in ['send', 'post']:
            print(f"\n{'─'*40}")
            print(f"🔄 连续 {method}Message 测试（2秒后开始）")
            time.sleep(2)
            rapid_click_test(hwnd, method=method, count=5, interval=0.3)
            ok = input(f"   👀 有反应吗？(y/n): ").strip().lower()
            results[f"rapid_{method}"] = (ok == 'y')

        print_header("完整测试结果")
        any_ok = False
        for name, ok in results.items():
            status = "✅ 有效" if ok else "❌ 无效"
            print(f"   {name:30s}  {status}")
            if ok:
                any_ok = True

        if any_ok:
            working = [k for k, v in results.items() if v]
            print(f"\n🎉 后台点击可行！有效方法: {working}")
            print(f"   → 可以使用真并行方案")
        else:
            print(f"\n😢 所有后台点击方法均无效")
            print(f"   → 建议使用方案1（多线程+鼠标锁）")


if __name__ == "__main__":
    main()