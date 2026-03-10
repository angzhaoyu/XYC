"""窗口管理模块 - 单窗口管理 + 多窗口组管理"""

import ctypes
import win32gui
import win32con
import win32api
import json
import os
import time
import cv2
from pathlib import Path
from datetime import datetime


# ================================================================
#                       单窗口管理
# ================================================================

class WindowManager:
    def __init__(self, title_or_hwnd, quiet=False):
        if isinstance(title_or_hwnd, int):
            self.hwnd = title_or_hwnd
            self.title = win32gui.GetWindowText(self.hwnd)
        elif isinstance(title_or_hwnd, str):
            self.hwnd = self._find_by_title(title_or_hwnd)
            self.title = title_or_hwnd
        else:
            raise TypeError("参数必须是窗口标题(str)或句柄(int)")

        if not self.hwnd:
            raise Exception(f"❌ 未找到窗口: {title_or_hwnd}")

        if not quiet:
            print(f"✅ 绑定窗口: {self.title} (句柄: {self.hwnd})")

    def _find_by_title(self, title):
        result = []
        def callback(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                name = win32gui.GetWindowText(hwnd)
                if title in name:
                    result.append(hwnd)
        win32gui.EnumWindows(callback, None)
        return result[0] if result else win32gui.FindWindow(None, title)

    @staticmethod
    def list_windows(keyword=None):
        windows = []
        def callback(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title and (keyword is None or keyword in title):
                    windows.append({"hwnd": hwnd, "title": title})
        win32gui.EnumWindows(callback, None)
        return windows

    # ========== 激活 ==========
    def activate(self):
        if win32gui.IsIconic(self.hwnd):
            win32gui.ShowWindow(self.hwnd, win32con.SW_RESTORE)
        fg = win32gui.GetForegroundWindow()
        fg_t = ctypes.windll.user32.GetWindowThreadProcessId(fg, None)
        my_t = ctypes.windll.user32.GetWindowThreadProcessId(self.hwnd, None)
        if fg_t != my_t:
            ctypes.windll.user32.AttachThreadInput(fg_t, my_t, True)
        win32gui.SetForegroundWindow(self.hwnd)
        win32gui.BringWindowToTop(self.hwnd)
        if fg_t != my_t:
            ctypes.windll.user32.AttachThreadInput(fg_t, my_t, False)
        time.sleep(0.15)

    def set_topmost(self, enable=True):
        flag = win32con.HWND_TOPMOST if enable else win32con.HWND_NOTOPMOST
        win32gui.SetWindowPos(self.hwnd, flag, 0, 0, 0, 0,
                              win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)

    # ========== 状态 ==========
    def minimize(self):
        win32gui.ShowWindow(self.hwnd, win32con.SW_MINIMIZE)

    def maximize(self):
        win32gui.ShowWindow(self.hwnd, win32con.SW_MAXIMIZE)

    def restore(self):
        win32gui.ShowWindow(self.hwnd, win32con.SW_RESTORE)

    def is_minimized(self):
        return bool(win32gui.IsIconic(self.hwnd))

    def is_visible(self):
        return bool(win32gui.IsWindowVisible(self.hwnd))

    # ========== 位置/大小 ==========
    def get_rect(self):
        return win32gui.GetWindowRect(self.hwnd)

    def get_client_size(self):
        r = win32gui.GetClientRect(self.hwnd)
        return r[2], r[3]

    def get_border_size(self):
        rect = self.get_rect()
        cw, ch = self.get_client_size()
        border_w = (rect[2] - rect[0]) - cw
        border_h = (rect[3] - rect[1]) - ch
        return border_w, border_h

    def get_region(self):
        left, top, right, bottom = self.get_rect()
        return {"left": left, "top": top,
                "width": right - left, "height": bottom - top}

    def move(self, x, y, width=None, height=None):
        if width is None or height is None:
            rect = self.get_rect()
            width = width or (rect[2] - rect[0])
            height = height or (rect[3] - rect[1])
        win32gui.MoveWindow(self.hwnd, x, y, width, height, True)

    def resize_client(self, client_w, client_h):
        bw, bh = self.get_border_size()
        rect = self.get_rect()
        self.move(rect[0], rect[1], client_w + bw, client_h + bh)

    def is_at(self, x, y, w, h, tolerance=3):
        """检查窗口是否已经在目标位置和大小（允许误差）"""
        rect = self.get_rect()
        cur_x, cur_y = rect[0], rect[1]
        cur_w = rect[2] - rect[0]
        cur_h = rect[3] - rect[1]
        return (abs(cur_x - x) <= tolerance and
                abs(cur_y - y) <= tolerance and
                abs(cur_w - w) <= tolerance and
                abs(cur_h - h) <= tolerance)

    # ========== 信息 ==========
    def info(self):
        rect = self.get_rect()
        cw, ch = self.get_client_size()
        return {
            "标题": self.title, "句柄": self.hwnd,
            "窗口区域": rect,
            "窗口大小": (rect[2] - rect[0], rect[3] - rect[1]),
            "客户区大小": (cw, ch),
            "是否最小化": self.is_minimized(),
        }

    def __repr__(self):
        return f"WindowManager('{self.title}', hwnd={self.hwnd})"


# ================================================================
#                     多窗口组管理
# ================================================================

class WindowGroupManager:
    """管理多个同名窗口的布局"""

    def __init__(self, title):
        self.title = title
        self.windows = []
        self.refresh()

    # ==================== 基础 ====================

    def refresh(self):
        hwnds = []
        def callback(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                name = win32gui.GetWindowText(hwnd)
                if self.title in name:
                    hwnds.append(hwnd)
        win32gui.EnumWindows(callback, None)

        self.windows = [WindowManager(h, quiet=True) for h in hwnds]
        print(f"🔍 找到 {len(self.windows)} 个 '{self.title}' 窗口")
        for i, wm in enumerate(self.windows):
            rect = wm.get_rect()
            w, h = rect[2] - rect[0], rect[3] - rect[1]
            print(f"   [{i}] 句柄={wm.hwnd}  大小={w}x{h}  位置=({rect[0]},{rect[1]})")
        return self.windows

    @staticmethod
    def get_screen_size():
        w = win32api.GetSystemMetrics(0)
        h = win32api.GetSystemMetrics(1)
        return w, h

    # ==================== 功能1：等比平铺排列 ====================

    def arrange(self, columns=None):
        """
        将所有窗口按列平铺排列（等比缩放，不拉伸）

        规则：
            - 按屏幕宽度等分列宽，高度按比例同步缩放
            - 已在某个槽位的窗口保持不动（不因 EnumWindows 顺序变化而重排）
            - 剩余窗口填入剩余槽位
        """
        if not self.windows:
            print("❌ 没有窗口可排列")
            return

        n = len(self.windows)
        if columns is None:
            columns = n

        screen_w, _ = self.get_screen_size()
        col_width = screen_w // columns
        rows = (n + columns - 1) // columns

        print(f"\n📐 排列 {n} 个窗口: {columns}列 x {rows}行")
        print(f"   屏幕宽: {screen_w}  每列宽: {col_width}")

        # 恢复最小化
        for wm in self.windows:
            if wm.is_minimized():
                wm.restore()
                time.sleep(0.05)

        # --- 1. 计算统一目标尺寸（用第一个窗口的比例）---
        ref_rect = self.windows[0].get_rect()
        ref_w = ref_rect[2] - ref_rect[0]
        ref_h = ref_rect[3] - ref_rect[1]
        if ref_w > 0:
            scale = col_width / ref_w
            target_h = max(int(ref_h * scale), 50)
        else:
            target_h = ref_h or 400
        target_w = col_width

        # --- 2. 生成所有槽位坐标 ---
        slots = []
        for i in range(n):
            col = i % columns
            row = i // columns
            x = col * col_width
            y = row * target_h
            slots.append((x, y, target_w, target_h))

        print(f"   目标尺寸: {target_w}x{target_h}  总高: {rows * target_h}px")

        # --- 3. 匹配：找出已在某个槽位的窗口 ---
        slot_taken = [False] * n       # 槽位是否已被占
        window_matched = {}            # { window_index: slot_index }

        for wi, wm in enumerate(self.windows):
            for si, (sx, sy, sw, sh) in enumerate(slots):
                if slot_taken[si]:
                    continue
                if wm.is_at(sx, sy, sw, sh):
                    slot_taken[si] = True
                    window_matched[wi] = si
                    break  # 一个窗口只匹配一个槽位

        # --- 4. 未匹配的窗口 → 分配到剩余槽位 ---
        free_slots = [si for si in range(n) if not slot_taken[si]]
        unplaced = [wi for wi in range(n) if wi not in window_matched]

        for wi, si in zip(unplaced, free_slots):
            window_matched[wi] = si

        # --- 5. 执行移动 ---
        moved = 0
        skipped = 0

        for wi, wm in enumerate(self.windows):
            si = window_matched[wi]
            sx, sy, sw, sh = slots[si]

            if wm.is_at(sx, sy, sw, sh):
                print(f"   ⏭️  窗口[{wi}](句柄{wm.hwnd}): 已在槽位[{si}]，跳过")
                skipped += 1
            else:
                wm.move(sx, sy, sw, sh)
                print(f"   ✅ 窗口[{wi}](句柄{wm.hwnd}): → 槽位[{si}] ({sx},{sy}) {sw}x{sh}")
                moved += 1

            time.sleep(0.03)

        print(f"✅ 排列完成: 移动 {moved} 个, 跳过 {skipped} 个")

    # ==================== 功能2：按图片尺寸等比调整 ====================

    def resize_to_image(self, image_path, reposition=False, columns=None):
        """
        将所有窗口的客户区调整为与图片相同的宽高

        规则：
            - 宽 + 高 同时调整（与图片完全一致）
            - 已经是目标大小的窗口跳过
            - 可选: 调整后重新排列

        Args:
            image_path:  图片路径
            reposition:  调整后是否重新排列
            columns:     重新排列时的列数
        """
        img = cv2.imread(str(image_path))
        if img is None:
            print(f"❌ 无法读取图片: {image_path}")
            return

        img_h, img_w = img.shape[:2]
        print(f"\n🖼️  目标客户区: {img_w} x {img_h}  (来自: {image_path})")

        adjusted = 0
        skipped = 0

        for i, wm in enumerate(self.windows):
            if wm.is_minimized():
                wm.restore()
                time.sleep(0.05)

            cw, ch = wm.get_client_size()

            # ⭐ 已经是目标大小 → 跳过
            if abs(cw - img_w) <= 2 and abs(ch - img_h) <= 2:
                print(f"   ⏭️  窗口[{i}]: 客户区已是 {cw}x{ch}，跳过")
                skipped += 1
            else:
                wm.resize_client(img_w, img_h)
                new_cw, new_ch = wm.get_client_size()
                print(f"   ✅ 窗口[{i}]: {cw}x{ch} → {new_cw}x{new_ch}")
                adjusted += 1

            time.sleep(0.03)

        print(f"✅ 调整完成: 修改 {adjusted} 个, 跳过 {skipped} 个")

        if reposition:
            self.arrange(columns=columns)

    # ==================== 功能3：保存布局 ====================

    def save_layout(self, name=None):
        """
        保存当前所有窗口的位置和大小到 window/ 目录

        记录：
            - 每个窗口的位置、窗口大小、客户区大小
            - 标注一致性：all_same_size / same_width_only / different
        """
        if not self.windows:
            print("❌ 没有窗口可保存")
            return None

        if name is None:
            name = self.title.replace(" ", "_")

        save_dir = Path("window")
        save_dir.mkdir(exist_ok=True)

        win_data_list = []
        for i, wm in enumerate(self.windows):
            rect = wm.get_rect()
            cw, ch = wm.get_client_size()
            win_data_list.append({
                "index": i,
                "hwnd": wm.hwnd,
                "left": rect[0],
                "top": rect[1],
                "width": rect[2] - rect[0],
                "height": rect[3] - rect[1],
                "client_width": cw,
                "client_height": ch,
            })

        # 分析一致性
        sizes = [(d["client_width"], d["client_height"]) for d in win_data_list]
        widths = [d["client_width"] for d in win_data_list]

        if len(set(sizes)) == 1:
            uniformity = "all_same_size"
        elif len(set(widths)) == 1:
            uniformity = "same_width_only"
        else:
            uniformity = "different"

        layout = {
            "title": self.title,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "screen": {"width": self.get_screen_size()[0],
                       "height": self.get_screen_size()[1]},
            "count": len(self.windows),
            "uniformity": uniformity,
            "windows": win_data_list
        }

        path = save_dir / f"{name}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(layout, f, ensure_ascii=False, indent=2)

        print(f"\n💾 布局已保存: {path}")
        print(f"   窗口数: {len(self.windows)}  一致性: {uniformity}")
        for d in win_data_list:
            print(f"   [{d['index']}] ({d['left']},{d['top']}) "
                  f"{d['width']}x{d['height']} "
                  f"客户区={d['client_width']}x{d['client_height']}")

        return str(path)

    # ==================== 功能4：还原布局 ====================

    def restore_layout(self, name=None):
        """
        从 window/ 目录还原布局

        还原策略（按优先级）：
            1. 宽高都一致(all_same_size) → 按客户区精确还原（补偿当前边框）
            2. 仅宽度一致(same_width_only) → 按客户区还原
            3. 各不相同(different) → 按客户区还原
            * 已在目标位置的窗口跳过
            * 当前窗口数 > 保存的 → 多余窗口循环使用保存位置
        """
        if name is None:
            name = self.title.replace(" ", "_")

        path = Path("window") / f"{name}.json"
        if not path.exists():
            print(f"❌ 布局文件不存在: {path}")
            self.list_saved_layouts()
            return False

        with open(path, "r", encoding="utf-8") as f:
            layout = json.load(f)

        print(f"\n📂 加载布局: {path}")
        print(f"   保存时间: {layout.get('timestamp', '?')}")
        print(f"   保存屏幕: {layout['screen']['width']}x{layout['screen']['height']}")
        print(f"   保存窗口数: {layout['count']}  一致性: {layout.get('uniformity')}")

        self.refresh()
        if not self.windows:
            print("❌ 当前没有匹配的窗口")
            return False

        saved = layout["windows"]
        moved = 0
        skipped = 0

        for i, wm in enumerate(self.windows):
            j = i % len(saved)
            sw = saved[j]

            if wm.is_minimized():
                wm.restore()
                time.sleep(0.05)

            # 按客户区精确还原（补偿当前系统边框）
            cw = sw["client_width"]
            ch = sw["client_height"]
            bw, bh = wm.get_border_size()
            target_w = cw + bw
            target_h = ch + bh
            target_x = sw["left"]
            target_y = sw["top"]

            wrap_note = f" (循环自[{j}])" if i >= len(saved) else ""

            # ⭐ 已在目标位置 → 跳过
            if wm.is_at(target_x, target_y, target_w, target_h):
                print(f"   ⏭️  窗口[{i}]: 已就位，跳过{wrap_note}")
                skipped += 1
            else:
                wm.move(target_x, target_y, target_w, target_h)
                print(f"   ✅ 窗口[{i}]: → ({target_x},{target_y}) "
                      f"{target_w}x{target_h} 客户区={cw}x{ch}{wrap_note}")
                moved += 1

            time.sleep(0.03)

        print(f"✅ 布局还原完成: 移动 {moved} 个, 跳过 {skipped} 个")
        return True

    # ==================== 辅助 ====================

    def list_saved_layouts(self):
        save_dir = Path("window")
        if not save_dir.exists():
            print("📁 window/ 目录不存在")
            return []

        files = list(save_dir.glob("*.json"))
        if not files:
            print("📁 暂无保存的布局")
            return []

        print(f"\n📁 已保存的布局 ({len(files)} 个):")
        results = []
        for f in files:
            try:
                data = json.load(open(f, encoding="utf-8"))
                print(f"   📄 {f.stem}  |  "
                      f"窗口={data.get('count','?')}  "
                      f"一致性={data.get('uniformity','?')}  "
                      f"时间={data.get('timestamp','?')}")
                results.append(f.stem)
            except Exception:
                print(f"   ⚠️ {f.name} (读取失败)")
        return results

    def activate_all(self):
        for wm in self.windows:
            wm.activate()
            time.sleep(0.1)

    def minimize_all(self):
        for wm in self.windows:
            wm.minimize()

    def restore_all(self):
        for wm in self.windows:
            wm.restore()
            time.sleep(0.05)

    def __repr__(self):
        return f"WindowGroupManager('{self.title}', count={len(self.windows)})"

    def __len__(self):
        return len(self.windows)

    def __getitem__(self, index):
        return self.windows[index]

""""""
if __name__ == "__main__":
    gm = WindowGroupManager("幸福小渔村")
    # 🔍 找到 6 个 '幸福小渔村' 窗口
    # ---- 功能1：等比排列 ----
    gm.arrange(columns=6)
    # ---- 功能2：按图片调整 ----
    #gm.resize_to_image("./window/001.png")
    ######gm.save_layout("6窗标准")
    # ---- 功能4：还原 ----
    #gm.restore_layout("6窗标准")
    gm.activate_all()



