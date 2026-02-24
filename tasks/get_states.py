import sys
import time
from pathlib import Path
from collections import deque

sys.path.append(str(Path(__file__).parent.parent))
import vision
from operate import Operator


class StateManager:
    def __init__(self, states_file, app_name=None, screenshot_path=None, yolo_model="models/best.pt"):
        self.operator = Operator(app_name)
        self.screenshot_path = screenshot_path

        self.states_file_path = Path(states_file).resolve()
        self.base_dir = self.states_file_path.parent.parent

        # 解析配置
        self.states_config = self._parse_states(self.states_file_path)

        # 初始化识别
        self.v = vision.MyVision(yolo_model_path=yolo_model)
        # 仅用 page-change 构建导航图（pop 不参与导航）
        self.state_graph = self._build_graph()

    # ==================== 解析 ====================
    def _parse_states(self, file_path):
        """
        解析 states.txt，按节分类：
          pop-states / pop-change / page-states / page-change
        """
        config = {
            "pop-states":  {},
            "pop-change":  {},
            "page-states": {},
            "page-change": {},
        }
        self.pop_order  = []     # 弹窗检测顺序（优先检测）
        self.page_order = []     # 页面检测顺序

        if not file_path.exists():
            print(f"❌ 找不到配置文件: {file_path}")
            return config

        current_section = None

        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                raw = line.strip()

                # 识别节标记
                if raw.startswith("#"):
                    tag = raw.lstrip("#").strip()
                    if tag in config:
                        current_section = tag
                    continue

                # 去掉行内注释
                line_clean = raw.split('#')[0].strip()
                if not line_clean or '=' not in line_clean:
                    continue

                key, val = [x.strip() for x in line_clean.split('=', 1)]
                val = val.strip('"')

                if current_section and current_section in config:
                    config[current_section][key] = val

                    if current_section == "pop-states":
                        self.pop_order.append(key)
                    elif current_section == "page-states":
                        self.page_order.append(key)

        #print(f"📋 弹窗状态: {self.pop_order}")
        #print(f"📋 页面状态: {self.page_order}")
        #print(f"📋 弹窗关闭: {list(config['pop-change'].keys())}")
        #print(f"📋 页面跳转: {list(config['page-change'].keys())}")
        return config

    # ==================== 导航图 ====================
    def _build_graph(self):
        """仅用 page-change 构建导航图，pop 不参与"""
        graph = {}
        for key in self.states_config["page-change"]:
            parts = key.split('_')
            if len(parts) >= 3:
                from_state = parts[0]
                to_state = parts[1]
                if from_state not in graph:
                    graph[from_state] = {}
                if to_state not in graph[from_state]:
                    graph[from_state][to_state] = key
        #print(f"📊 导航图: {graph}")
        return graph

    # ==================== 弹窗处理 ====================
    def _check_popup(self, img_source):
        """
        检测是否有弹窗，有则返回弹窗名，无返回 None
        """
        for pop_name in self.pop_order:
            base_path_str = self.states_config["pop-states"][pop_name]
            img_path = Path(base_path_str).with_suffix(".png")
            if not img_path.is_absolute():
                img_path = self.base_dir / img_path
            if not img_path.exists():
                continue
            res = self.v.find_image(img_source, str(img_path))
            if res:
                print(f"🔔 检测到弹窗: [{pop_name}]")
                return pop_name
        return None

    def _dismiss_popup(self, pop_name):
        """
        关闭弹窗：找到该弹窗对应的任意一个 pop-change，执行点击
        """
        # 找到 pop_name 开头的第一个 change
        for key, val in self.states_config["pop-change"].items():
            if key.startswith(pop_name + "_"):
                json_path = Path(val).with_suffix(".json")
                if not json_path.is_absolute():
                    json_path = self.base_dir / json_path
                print(f"  ❎ 关闭弹窗 [{pop_name}] → 点击 {json_path}")
                self.operator.click_json(str(json_path))
                time.sleep(0.5)
                return True
        print(f"  ⚠️ 未找到弹窗 [{pop_name}] 的关闭配置")
        return False

    def _clear_popups(self, max_attempts=5):
        """
        循环清除所有弹窗，直到没有弹窗为止
        返回: True 清除成功（或无弹窗），False 无法清除
        """
        for i in range(max_attempts):
            img_source = self.screenshot_path if self.screenshot_path else self.operator.capture()
            pop = self._check_popup(img_source)
            if pop is None:
                return True
            print(f"  🔄 清除弹窗 (第 {i+1} 次)")
            if not self._dismiss_popup(pop):
                return False
            time.sleep(0.5)
        print("  ❌ 弹窗清除次数超限")
        return False

    # ==================== 状态识别 ====================
    def get_states(self, auto_dismiss_popup=True):
        """
        获取当前状态：
        1. 先检查弹窗，自动关闭
        2. 再检查页面状态
        """
        img_source = self.screenshot_path if self.screenshot_path else self.operator.capture()

        # 1. 检查弹窗
        if auto_dismiss_popup:
            pop = self._check_popup(img_source)
            if pop is not None:
                self._dismiss_popup(pop)
                time.sleep(0.5)
                # 重新截图
                img_source = self.screenshot_path if self.screenshot_path else self.operator.capture()
                # 递归清除（可能有多层弹窗）
                pop2 = self._check_popup(img_source)
                if pop2 is not None:
                    self._clear_popups()
                    img_source = self.screenshot_path if self.screenshot_path else self.operator.capture()

        # 2. 检查页面状态
        for state_name in self.page_order:
            base_path_str = self.states_config["page-states"][state_name]
            img_path = Path(base_path_str).with_suffix(".png")
            if not img_path.is_absolute():
                img_path = self.base_dir / img_path
            if not img_path.exists():
                print(f"⚠️ 找不到状态图片: {img_path}")
                continue
            res = self.v.find_image(img_source, str(img_path))
            if res:
                print(f"✅ 当前状态: [{state_name}]")
                return state_name

        print("❌ 未匹配到任何状态")
        return None

    def get_raw_state(self):
        """
        获取原始状态（不自动关闭弹窗），返回 (类型, 名称)
        类型: "pop" / "page" / None
        """
        img_source = self.screenshot_path if self.screenshot_path else self.operator.capture()

        # 先查弹窗
        pop = self._check_popup(img_source)
        if pop:
            return ("pop", pop)

        # 再查页面
        for state_name in self.page_order:
            base_path_str = self.states_config["page-states"][state_name]
            img_path = Path(base_path_str).with_suffix(".png")
            if not img_path.is_absolute():
                img_path = self.base_dir / img_path
            if not img_path.exists():
                continue
            res = self.v.find_image(img_source, str(img_path))
            if res:
                return ("page", state_name)

        return (None, None)

    # ==================== 导航 ====================
    def navigate_to(self, target, max_retries=3):
        """
        导航到目标页面状态
        遇到弹窗自动关闭后重新规划路径
        """
        for retry in range(max_retries):
            # 获取当前状态（自动清弹窗）
            current = self.get_states()
            if current is None:
                print("❌ 无法获取当前状态")
                return False

            if current == target:
                print(f"🎉 已到达目标 [{target}]")
                return True

            # BFS 找路径
            path = self._find_path(current, target)
            if path is None:
                print(f"❌ 无法从 [{current}] 到达 [{target}]")
                return False

            print(f"📍 路径: {' -> '.join(path)}")

            success = True
            for i in range(len(path) - 1):
                from_s = path[i]
                to_s = path[i + 1]

                # 执行前再次检查（可能出现弹窗）
                state_type, state_name = self.get_raw_state()
                if state_type == "pop":
                    print(f"🔔 导航中遇到弹窗 [{state_name}]，清除后重新规划")
                    self._clear_popups()
                    success = False
                    break

                # 确认当前状态
                actual = self.get_states(auto_dismiss_popup=True)
                if actual != from_s:
                    print(f"⚠️ 状态偏移: 期望 [{from_s}] 实际 [{actual}]，重新规划")
                    success = False
                    break

                change_key = self.state_graph[from_s][to_s]
                print(f"⚡ 执行: {from_s} -> {to_s}")
                if not self.states_change(change_key):
                    print(f"❌ 转换失败，重新规划")
                    success = False
                    break

            if success:
                final = self.get_states()
                if final == target:
                    print(f"🎉 导航成功: [{target}]")
                    return True

            print(f"🔄 重新规划路径 (第 {retry+2} 次)")

        print(f"❌ 导航失败，重试次数耗尽")
        return False

    def _find_path(self, start, end):
        """BFS 最短路径"""
        if start not in self.state_graph:
            return None
        visited = {start}
        queue = deque([(start, [start])])
        while queue:
            curr, path = queue.popleft()
            for next_s in self.state_graph.get(curr, {}):
                if next_s == end:
                    return path + [next_s]
                if next_s not in visited:
                    visited.add(next_s)
                    queue.append((next_s, path + [next_s]))
        return None

    # ==================== 状态转换 ====================
    def states_change(self, key):
        """执行页面跳转"""
        if key not in self.states_config["page-change"]:
            print(f"❌ 找不到转换: {key}")
            return False

        parts = key.split('_')
        start_state = parts[0]
        target_state = parts[1]

        current = self.get_states()
        if current != start_state:
            print(f"❌ 当前状态 [{current}] 非起始 [{start_state}]")
            return False

        json_path = Path(self.states_config["page-change"][key]).with_suffix(".json")
        if not json_path.is_absolute():
            json_path = self.base_dir / json_path

        for i in range(5):
            current = self.get_states()
            if current == target_state:
                print(f"🎉 已到达 [{target_state}]")
                return True

            print(f"⚡ [{key}] 第 {i+1} 次尝试，点击 {json_path}")
            self.operator.click_json(str(json_path))
            time.sleep(1.0)

            if self.get_states() == target_state:
                return True

        print(f"❌ 转换失败: {key}")
        return False


# ==================== 运行 ====================
"""mgr = StateManager("tasks/states.txt", app_name="幸福小渔村")
mgr.get_states()
mgr.navigate_to("caidan")"""