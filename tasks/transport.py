# transport.py
import sys
import time
import re
import os
import cv2
import numpy as np
import pyautogui
import pygetwindow as gw
from pathlib import Path

# --- 路径适配 ---
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

import vision
import operate
from tasks.get_states import StateManager


class TransportTask:
    """
    运输任务：自动采集领地资源
    """
    
    # 状态常量
    STATUS_SUCCESS = "success"
    STATUS_NO_RESOURCE = "no_resource"
    STATUS_NO_BEAST = "no_beast"
    STATUS_NOT_IN_LINGDI = "not_in_lingdi"
    STATUS_ERROR = "error"
    
    VALID_STATES = ["lingdi", "caiji", "shangzhen"]
    
    # 延迟配置
    CLICK_DELAY = 0.8
    ACTION_DELAY = 0.5
    STATE_CHECK_DELAY = 0.8
    
    # 重试和超时配置
    CLICK_RETRY = 2           # 每次点击重试次数
    STATE_WAIT_ROUNDS = 8     # 等待状态变化的轮数
    GLOBAL_STEP_TIMEOUT = 30  # 单步骤全局超时（秒）
    BIRD_WAIT_TIMEOUT = 20    # 等鸟超时
    MAX_RECOVERY = 3          # 最大恢复次数
    
    def __init__(self, window_title=None, window_handle=None, debug=False):
        self.debug = debug
        self.window_title = window_title
        self.window_handle = window_handle
        self.window = None
        
        self._bind_window()
        
        self.vision = vision.MyVision(
            yolo_model_path=str(PROJECT_ROOT / "models/best.pt")
        )
        
        self.combo_dir = PROJECT_ROOT / "tasks/transport/mouse_combo"
        self.screenshot_dir = PROJECT_ROOT / "screenshots"
        self.screenshot_path = str(self.screenshot_dir / "current.png")
        
        self._ensure_dirs()
        
        self.win_w = 0
        self.win_h = 0
        
        # 状态数据
        self.resources = []
        self.remaining_beasts = 0
        
        # 全局超时控制
        self.step_start_time = time.time()

    def _ensure_dirs(self):
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

    def _bind_window(self):
        try:
            if self.window_handle:
                try:
                    import win32gui
                    title = win32gui.GetWindowText(self.window_handle)
                    windows = gw.getWindowsWithTitle(title)
                    for w in windows:
                        if w._hWnd == self.window_handle:
                            self.window = w
                            break
                except ImportError:
                    print("⚠️ 需要安装 pywin32")
                    
            elif self.window_title:
                windows = gw.getWindowsWithTitle(self.window_title)
                if windows:
                    self.window = windows[0]
            
            if self.window:
                print(f"✅ 绑定窗口: {self.window.title}")
            else:
                print("⚠️ 未绑定窗口")
                
        except Exception as e:
            print(f"❌ 绑定窗口失败: {e}")

    def activate_window(self):
        if not self.window:
            return False
        try:
            windows = gw.getWindowsWithTitle(self.window.title)
            if windows:
                self.window = windows[0]
            if self.window.isMinimized:
                self.window.restore()
                time.sleep(0.5)
            self.window.activate()
            time.sleep(0.3)
            try:
                import win32gui, win32con
                hwnd = self.window._hWnd
                win32gui.SetForegroundWindow(hwnd)
                win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                    win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
                win32gui.SetWindowPos(hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0,
                    win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
            except ImportError:
                pass
            return True
        except Exception as e:
            print(f"⚠️ 置顶失败: {e}")
            return False

    # ==================== 超时控制 ====================
    
    def reset_step_timer(self):
        """重置步骤计时器"""
        self.step_start_time = time.time()
    
    def is_step_timeout(self):
        """检查当前步骤是否超时"""
        return (time.time() - self.step_start_time) > self.GLOBAL_STEP_TIMEOUT

    # ==================== 屏幕与状态 ====================

    def refresh_screen(self):
        try:
            if self.window:
                windows = gw.getWindowsWithTitle(self.window.title)
                if windows:
                    self.window = windows[0]
                left = max(0, self.window.left)
                top = max(0, self.window.top)
                width = self.window.width
                height = self.window.height
                if self.window.left < 0:
                    width += self.window.left
                if self.window.top < 0:
                    height += self.window.top
                screenshot = pyautogui.screenshot(region=(left, top, width, height))
            else:
                screenshot = pyautogui.screenshot()
            
            screenshot.save(self.screenshot_path)
            img = cv2.imread(self.screenshot_path)
            if img is not None:
                self.win_h, self.win_w = img.shape[:2]
            return True
        except Exception as e:
            print(f"❌ 截图失败: {e}")
            return False

    def get_state(self):
        """获取当前状态（单次）"""
        if not self.refresh_screen():
            return None
        return get_current_state(
            self.screenshot_path,
            states_dir=str(PROJECT_ROOT / "tasks/states/")
        )

    def get_state_safe(self):
        """获取状态，处理未知状态"""
        for _ in range(3):
            state = self.get_state()
            
            if state in self.VALID_STATES:
                return state
            
            # 未知状态，尝试关闭弹窗
            if state is not None:
                if self.debug:
                    print(f"   ⚠️ 未知状态[{state}]，尝试关闭")
                self._do_click_json("009.png")
                time.sleep(0.5)
            else:
                time.sleep(0.3)
        
        return None

    def detect_resources_and_birds(self):
        """YOLO检测"""
        self.refresh_screen()
        datas = self.vision.detect_yolo(self.screenshot_path)
        
        resources, birds, transported = [], [], 0
        if datas:
            for item in datas:
                if item['name'] == 'resources':
                    resources.append(item['box'])
                elif item['name'] == 'bird':
                    birds.append(item['box'])
                elif item['name'] == 'transported':
                    transported += 1
        
        return resources, birds, transported

    # ==================== 底层点击 ====================

    def _do_click(self, x, y):
        """底层点击（窗口内坐标）"""
        if self.window:
            screen_x = self.window.left + x
            screen_y = self.window.top + y
        else:
            screen_x, screen_y = x, y
        
        duration = operate.random_duration(0.15, 0.3)
        pyautogui.moveTo(screen_x, screen_y, duration=duration)
        time.sleep(0.08)
        pyautogui.click()
        time.sleep(self.CLICK_DELAY)

    def _do_click_box(self, box):
        """点击box区域"""
        target = operate.sample_point_in_box(box)
        self._do_click(int(target[0]), int(target[1]))

    def _do_click_json(self, ref_image_name):
        """点击JSON定义的区域"""
        full_path = str(self.combo_dir / ref_image_name)
        if not os.path.exists(full_path):
            print(f"   ❌ 文件不存在: {ref_image_name}")
            return False
        
        scope_perc = self.vision.limit_scope(full_path)
        if not scope_perc:
            print(f"   ❌ 无法解析: {ref_image_name}")
            return False
        
        x1 = scope_perc[0][0] * self.win_w
        y1 = scope_perc[0][1] * self.win_h
        x2 = scope_perc[1][0] * self.win_w
        y2 = scope_perc[1][1] * self.win_h
        
        self._do_click_box([[x1, y1], [x2, y2]])
        return True

    # ==================== 核心：点击并确认状态 ====================

    def click_and_confirm(self, click_func, target_state, action_name="操作"):
        """
        点击并确认状态变化，失败则重试
        
        Args:
            click_func: 点击函数
            target_state: 期望的目标状态
            action_name: 日志名称
            
        Returns:
            bool: 是否成功到达目标状态
        """
        self.reset_step_timer()
        
        for attempt in range(self.CLICK_RETRY + 1):
            # 检查全局超时
            if self.is_step_timeout():
                print(f"   ⏰ {action_name} 全局超时")
                return False
            
            if attempt > 0:
                print(f"   🔄 重试 {action_name} ({attempt}/{self.CLICK_RETRY})")
            
            # 执行点击
            print(f"   🖱️ {action_name}")
            click_func()
            
            # 等待状态变化
            for _ in range(self.STATE_WAIT_ROUNDS):
                if self.is_step_timeout():
                    print(f"   ⏰ 等待状态超时")
                    break
                
                current = self.get_state_safe()
                
                if current == target_state:
                    if self.debug:
                        print(f"   ✅ 确认状态: {target_state}")
                    return True
                
                time.sleep(self.STATE_CHECK_DELAY)
            
            # 本次点击未成功，检查当前状态决定是否继续
            current = self.get_state_safe()
            if current == target_state:
                return True
            
            print(f"   ⚠️ {action_name}后状态={current}, 期望={target_state}")
        
        return False

    def click_json_confirm(self, ref_image, target_state, action_name=None):
        """JSON点击并确认状态"""
        name = action_name or ref_image
        return self.click_and_confirm(
            lambda: self._do_click_json(ref_image),
            target_state,
            name
        )

    # ==================== 状态恢复 ====================

    def force_back_to_lingdi(self):
        """强制返回领地（多种手段）"""
        print("   🔙 强制返回领地...")
        
        for attempt in range(5):
            current = self.get_state_safe()
            
            if current == "lingdi":
                print("   ✅ 已在领地")
                return True
            
            if self.debug:
                print(f"   [{attempt+1}/5] 当前状态: {current}")
            
            if current == "shangzhen":
                self._do_click_json("004.png")  # 取消
                time.sleep(1)
            elif current == "caiji":
                self._do_click_json("005.png")  # 退出/确定（复用）
                time.sleep(1)
            else:
                # 未知状态，按ESC
                pyautogui.press('escape')
                time.sleep(1)
                # 再尝试点击关闭
                self._do_click_json("009.png")
                time.sleep(0.5)
        
        final = self.get_state_safe()
        return final == "lingdi"

    def ensure_state(self, target_state):
        """确保处于目标状态"""
        current = self.get_state_safe()
        
        if current == target_state:
            return True
        
        if target_state == "lingdi":
            return self.force_back_to_lingdi()
        
        return False

    # ==================== OCR ====================

    def ocr_region(self, image_name):
        full_path = str(self.combo_dir / image_name)
        if not os.path.exists(full_path):
            return None
        scope_perc = self.vision.limit_scope(full_path)
        if not scope_perc:
            return None
        return self.vision.detect_text(self.screenshot_path, a_percentage=scope_perc)

    def parse_number(self, text_list, default=0):
        if not text_list:
            return default
        raw = text_list[0].get('text', '')
        if self.debug:
            print(f"   OCR数字: '{raw}'")
        match = re.search(r'\d+', raw)
        return int(match.group()) if match else default

    def parse_fraction(self, text_list):
        """解析 '已选/总数' 格式"""
        if not text_list:
            return 0, 3  # 默认
        
        raw = text_list[0].get('text', '')
        if self.debug:
            print(f"   OCR分数: '{raw}'")
        
        nums = re.findall(r'\d+', raw)
        if len(nums) >= 2:
            return int(nums[0]), int(nums[1])
        elif len(nums) == 1:
            return int(nums[0]), 3
        return 0, 3

    # ==================== 资源分配算法 ====================

    def calculate_allocation(self, total_beasts, num_resources):
        """
        均分算法：尽量平均分配
        
        例如：6兽3资源 -> [2, 2, 2]
              5兽3资源 -> [2, 2, 1]
              4兽3资源 -> [2, 1, 1]
        """
        if num_resources <= 0:
            return []
        if total_beasts <= 0:
            return [0] * num_resources
        
        base = total_beasts // num_resources
        extra = total_beasts % num_resources
        
        allocation = []
        for i in range(num_resources):
            if i < extra:
                allocation.append(base + 1)
            else:
                allocation.append(base)
        
        return allocation

    # ==================== 防鸟点击资源 ====================

    def get_safe_click_point(self, res_box, bird_boxes):
        """获取避开鸟的安全点击位置"""
        rx1, ry1 = res_box[0]
        rx2, ry2 = res_box[1]
        
        # 多个采样点
        sample_points = [
            ((rx1 + rx2) / 2, (ry1 + ry2) / 2),
            (rx1 + (rx2 - rx1) * 0.3, ry1 + (ry2 - ry1) * 0.3),
            (rx1 + (rx2 - rx1) * 0.7, ry1 + (ry2 - ry1) * 0.3),
            (rx1 + (rx2 - rx1) * 0.3, ry1 + (ry2 - ry1) * 0.7),
            (rx1 + (rx2 - rx1) * 0.7, ry1 + (ry2 - ry1) * 0.7),
        ]
        
        for px, py in sample_points:
            safe = True
            for bird_box in bird_boxes:
                bx1, by1 = bird_box[0]
                bx2, by2 = bird_box[1]
                margin = 30
                if (bx1 - margin <= px <= bx2 + margin and 
                    by1 - margin <= py <= by2 + margin):
                    safe = False
                    break
            if safe:
                return (int(px), int(py))
        
        return None

    def click_resource_to_caiji(self, res_index):
        """
        点击资源并确认进入caiji状态
        
        Returns:
            str: "success" / "resource_gone" / "timeout" / "failed"
        """
        self.reset_step_timer()
        
        for attempt in range(self.CLICK_RETRY + 1):
            if self.is_step_timeout():
                return "timeout"
            
            if attempt > 0:
                print(f"   🔄 重试点击资源 ({attempt}/{self.CLICK_RETRY})")
            
            # 检测资源和鸟
            bird_wait_start = time.time()
            click_point = None
            
            while time.time() - bird_wait_start < self.BIRD_WAIT_TIMEOUT:
                if self.is_step_timeout():
                    return "timeout"
                
                resources, birds, _ = self.detect_resources_and_birds()
                
                if res_index >= len(resources):
                    print(f"   ⚠️ 资源 {res_index} 已消失")
                    return "resource_gone"
                
                res_box = resources[res_index]
                
                if birds:
                    click_point = self.get_safe_click_point(res_box, birds)
                    if click_point is None:
                        print(f"   🐦 被鸟挡住，等待...")
                        time.sleep(2)
                        continue
                else:
                    rx1, ry1 = res_box[0]
                    rx2, ry2 = res_box[1]
                    click_point = (int((rx1+rx2)/2), int((ry1+ry2)/2))
                
                break
            
            if click_point is None:
                print(f"   ⏰ 等鸟超时")
                return "timeout"
            
            # 点击
            print(f"   🖱️ 点击资源")
            self._do_click(click_point[0], click_point[1])
            
            # 等待状态变为 caiji
            for _ in range(self.STATE_WAIT_ROUNDS):
                if self.is_step_timeout():
                    return "timeout"
                
                current = self.get_state_safe()
                if current == "caiji":
                    return "success"
                
                time.sleep(self.STATE_CHECK_DELAY)
            
            print(f"   ⚠️ 点击资源后未进入caiji")
        
        return "failed"

    # ==================== 选兽逻辑（核心修复） ====================

    def read_shangzhen_info(self):
        """
        读取上阵界面信息
        Returns:
            tuple: (stock, selected, capacity) 或 None
        """
        self.refresh_screen()
        
        # 读取库存（002.png）
        ocr_stock = self.ocr_region("002.png")
        stock = self.parse_number(ocr_stock, default=0)
        
        # 读取已选/容量（003.png）
        ocr_sel = self.ocr_region("003.png")
        selected, capacity = self.parse_fraction(ocr_sel)
        
        print(f"   📊 库存:{stock}, 已选:{selected}/{capacity}")
        
        return stock, selected, capacity

    def select_beasts(self, target_count):
        """
        在上阵界面选择指定数量的兽
        
        Args:
            target_count: 目标数量
            
        Returns:
            tuple: (actually_selected, status)
                - actually_selected: 实际选择的数量
                - status: "success" / "no_beast" / "failed"
        """
        # 读取当前状态
        stock, selected, capacity = self.read_shangzhen_info()
        
        total_available = stock + selected
        
        if total_available <= 0:
            print("   ⛔ 没有可用的兽")
            return 0, "no_beast"
        
        # 计算实际目标
        actual_target = min(target_count, capacity, total_available)
        
        print(f"   🎯 目标选择: {actual_target} (请求:{target_count})")
        
        # 如果已经够了
        if selected >= actual_target:
            print(f"   ✅ 已选{selected}，满足目标{actual_target}")
            return selected, "success"
        
        # 如果需要全选（目标>=可用 或 目标>=容量）
        if actual_target >= total_available or actual_target >= capacity:
            print(f"   🐾 一键上阵（全选）")
            self._do_click_json("008.png")
            time.sleep(self.ACTION_DELAY)
            
            # 验证
            _, new_selected, _ = self.read_shangzhen_info()
            return new_selected, "success"
        
        # 需要补选
        need_more = actual_target - selected
        print(f"   🐾 需要再选 {need_more} 个")
        
        # 点击位置：006.png=第2个, 007.png=第3个
        slot_files = ["006.png", "007.png"]
        
        current_selected = selected
        
        for i in range(need_more):
            if i >= len(slot_files):
                break
            
            slot_file = slot_files[i]
            print(f"   🐾 选择槽位 {i+2}")
            self._do_click_json(slot_file)
            time.sleep(self.ACTION_DELAY)
            
            current_selected += 1
        
        # 验证选择结果
        _, final_selected, _ = self.read_shangzhen_info()
        
        if final_selected >= actual_target:
            print(f"   ✅ 选择完成: {final_selected}")
            return final_selected, "success"
        else:
            print(f"   ⚠️ 选择可能未完全生效: {final_selected}/{actual_target}")
            return final_selected, "success"  # 仍然继续

    # ==================== 扫描 ====================

    def scan_resources(self):
        """扫描领地资源"""
        print("\n🔍 扫描资源...")
        
        if not self.ensure_state("lingdi"):
            print("❌ 无法进入领地")
            return False
        
        resources, birds, transported = self.detect_resources_and_birds()
        self.resources = resources
        
        print(f"📊 资源:{len(resources)} | 鸟:{len(birds)} | 运输中:{transported}")
        return True

    # ==================== 单资源处理 ====================

    def process_one_resource(self, res_index, target_beasts, is_last=False):
        """
        处理单个资源
        
        Args:
            res_index: 资源索引
            target_beasts: 目标分配兽数
            is_last: 是否最后一个（用于决定是否全选）
            
        Returns:
            tuple: (status, beasts_used)
                - status: "success" / "no_beast" / "resource_gone" / "timeout" / "failed"
                - beasts_used: 实际使用的兽数
        """
        print(f"\n--- 资源 {res_index + 1} (目标:{target_beasts}, 最后:{is_last}) ---")
        
        # 1. 确保在领地
        if not self.ensure_state("lingdi"):
            print("   ❌ 无法返回领地")
            return "failed", 0
        
        # 2. 点击资源 -> caiji
        click_result = self.click_resource_to_caiji(res_index)
        
        if click_result != "success":
            print(f"   ❌ 点击资源失败: {click_result}")
            self.force_back_to_lingdi()
            return click_result, 0
        
        # 3. 点击001进入上阵界面
        self.refresh_screen()
        btn_path = str(self.combo_dir / "001.png")
        btn_pos = self.vision.find_image(self.screenshot_path, btn_path)
        
        if not btn_pos:
            print("   ❌ 找不到001按钮（可能资源已被采集）")
            self.force_back_to_lingdi()
            return "resource_gone", 0
        
        if not self.click_and_confirm(
            lambda: self._do_click_box(btn_pos),
            "shangzhen",
            "进入上阵"
        ):
            print("   ❌ 进入上阵失败")
            self.force_back_to_lingdi()
            return "failed", 0
        
        # 4. 选兽
        if is_last:
            # 最后一个资源，全选
            print("   🐾 最后资源，一键上阵")
            self._do_click_json("008.png")
            time.sleep(self.ACTION_DELAY)
            _, selected, capacity = self.read_shangzhen_info()
            beasts_used = selected
        else:
            beasts_used, select_status = self.select_beasts(target_beasts)
            
            if select_status == "no_beast":
                # 没兽了，取消
                self.click_json_confirm("004.png", "lingdi", "取消")
                return "no_beast", 0
        
        # 5. 确定出发
        if not self.click_json_confirm("005.png", "lingdi", "确定出发"):
            print("   ⚠️ 确定后未回到领地，强制返回")
            self.force_back_to_lingdi()
        
        print(f"   ✅ 完成，使用{beasts_used}只兽")
        time.sleep(self.ACTION_DELAY)
        
        return "success", beasts_used

    # ==================== 主流程 ====================

    def run(self):
        print("\n" + "=" * 60)
        print("🚀 开始运输任务")
        print("=" * 60)
        
        try:
            self.activate_window()
            time.sleep(0.5)
            
            return self._run_with_recovery()
            
        except Exception as e:
            print(f"❌ 异常: {e}")
            import traceback
            traceback.print_exc()
            self.force_back_to_lingdi()
            return self.STATUS_ERROR

    def _run_with_recovery(self):
        """带恢复机制的主流程"""
        
        for recovery in range(self.MAX_RECOVERY + 1):
            if recovery > 0:
                print(f"\n🔄 === 恢复尝试 {recovery}/{self.MAX_RECOVERY} ===")
                if not self.force_back_to_lingdi():
                    print("   ❌ 无法恢复到领地")
                    continue
            
            result = self._run_main()
            
            if result in [self.STATUS_SUCCESS, self.STATUS_NO_RESOURCE, 
                          self.STATUS_NO_BEAST, self.STATUS_NOT_IN_LINGDI]:
                return result
            
            # 其他情况需要恢复
            print(f"   ⚠️ 需要恢复，结果: {result}")
        
        print("❌ 超过最大恢复次数")
        return self.STATUS_ERROR

    def _run_main(self):
        """主任务逻辑"""
        
        # 1. 扫描资源
        if not self.scan_resources():
            return self.STATUS_NOT_IN_LINGDI
        
        if not self.resources:
            print("✨ 没有可采集的资源")
            return self.STATUS_NO_RESOURCE
        
        num_resources = len(self.resources)
        print(f"\n📦 共 {num_resources} 个资源待处理")
        
        # 2. 处理第一个资源，探测兽数
        print("\n" + "="*50)
        print("📦 处理第一个资源（探测兽数）")
        print("="*50)
        
        # 点击第一个资源
        click_result = self.click_resource_to_caiji(0)
        if click_result == "resource_gone":
            # 重新扫描
            if self.scan_resources() and self.resources:
                return self._run_main()  # 重新开始
            return self.STATUS_NO_RESOURCE
        elif click_result != "success":
            return "need_recovery"
        
        # 进入上阵
        self.refresh_screen()
        btn_path = str(self.combo_dir / "001.png")
        btn_pos = self.vision.find_image(self.screenshot_path, btn_path)
        
        if not btn_pos:
            print("   ❌ 找不到001按钮")
            self.force_back_to_lingdi()
            return "need_recovery"
        
        if not self.click_and_confirm(
            lambda: self._do_click_box(btn_pos),
            "shangzhen",
            "进入上阵"
        ):
            self.force_back_to_lingdi()
            return "need_recovery"
        
        # 读取兽数
        stock, selected, capacity = self.read_shangzhen_info()
        total_beasts = stock + selected
        
        if total_beasts <= 0:
            print("   ⛔ 没有兽")
            self.click_json_confirm("004.png", "lingdi", "取消")
            return self.STATUS_NO_BEAST
        
        # 计算分配
        allocation = self.calculate_allocation(total_beasts, num_resources)
        print(f"   📋 分配计划: {allocation} (总计:{total_beasts})")
        
        self.remaining_beasts = total_beasts
        
        # 第一个资源的目标
        first_target = allocation[0]
        is_only_one = (num_resources == 1)
        
        # 选兽
        if is_only_one:
            print("   🐾 唯一资源，一键上阵")
            self._do_click_json("008.png")
            time.sleep(self.ACTION_DELAY)
            beasts_used = min(total_beasts, capacity)
        else:
            beasts_used, status = self.select_beasts(first_target)
            if status == "no_beast":
                self.click_json_confirm("004.png", "lingdi", "取消")
                return self.STATUS_NO_BEAST
        
        self.remaining_beasts -= beasts_used
        
        # 确定出发
        if not self.click_json_confirm("005.png", "lingdi", "确定出发"):
            self.force_back_to_lingdi()
        
        print(f"   ✅ 第一个资源完成，用{beasts_used}兽，剩余{self.remaining_beasts}")
        
        processed = 1
        
        # 3. 处理剩余资源
        for i in range(1, num_resources):
            if self.remaining_beasts <= 0:
                print(f"\n⛔ 没有剩余的兽，停止")
                break
            
            # 重新计算分配
            remaining_res = num_resources - i
            new_allocation = self.calculate_allocation(self.remaining_beasts, remaining_res)
            target = new_allocation[0] if new_allocation else 0
            
            if target <= 0:
                print(f"\n⏭️ 跳过资源 {i+1}")
                continue
            
            is_last = (i == num_resources - 1)
            
            print(f"\n{'='*50}")
            print(f"📦 资源 {i+1}/{num_resources}")
            print(f"   剩余兽:{self.remaining_beasts}, 本次目标:{target}")
            print(f"{'='*50}")
            
            status, beasts_used = self.process_one_resource(i, target, is_last)
            
            if status == "success":
                self.remaining_beasts -= beasts_used
                processed += 1
                print(f"   剩余兽: {self.remaining_beasts}")
            elif status == "no_beast":
                print(f"   ⛔ 没兽了")
                break
            elif status == "resource_gone":
                print(f"   ⚠️ 资源消失，继续下一个")
                continue
            elif status in ["timeout", "failed"]:
                return "need_recovery"
        
        # 确保回到领地
        self.ensure_state("lingdi")
        
        print(f"\n{'='*50}")
        print(f"📊 任务完成: 处理了 {processed}/{num_resources} 个资源")
        print(f"{'='*50}")
        
        return self.STATUS_SUCCESS


# ==================== 测试 ====================

def test_allocation():
    print("\n测试分配算法:")
    task = TransportTask()
    
    test_cases = [
        (6, 3),  # -> [2, 2, 2]
        (5, 3),  # -> [2, 2, 1]
        (4, 3),  # -> [2, 1, 1]
        (3, 3),  # -> [1, 1, 1]
        (2, 3),  # -> [1, 1, 0]
        (1, 3),  # -> [1, 0, 0]
        (10, 3), # -> [4, 3, 3]
        (7, 2),  # -> [4, 3]
    ]
    
    for beasts, resources in test_cases:
        result = task.calculate_allocation(beasts, resources)
        total = sum(result)
        print(f"  {beasts}兽 {resources}资源 -> {result} (总计:{total})")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", help="测试分配算法")
    parser.add_argument("--window", type=str, default="幸福小渔村")
    parser.add_argument("--debug", action="store_true")
    
    args = parser.parse_args()
    
    if args.test:
        test_allocation()
    else:
        task = TransportTask(window_title=args.window, debug=args.debug)
        result = task.run()
        
        exit_codes = {
            TransportTask.STATUS_SUCCESS: 0,
            TransportTask.STATUS_NO_RESOURCE: 0,
            TransportTask.STATUS_NO_BEAST: 1,
            TransportTask.STATUS_NOT_IN_LINGDI: 2,
            TransportTask.STATUS_ERROR: 3
        }
        sys.exit(exit_codes.get(result, 3))