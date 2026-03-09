import time
from collections import deque

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from tools.vision import MyVision
from tools.operate import Operator


class StateManager:
    def __init__(self, states_file, app_name=None, operator=None, screenshot_path=None, yolo_model="models/best.pt"):
        if operator:
            self.operator = operator
        else:
            self.operator = Operator(app_name)
        self.screenshot_path = screenshot_path
        self.states_file_path = Path(states_file).resolve()
        self.base_dir = self.states_file_path.parent.parent

        self.states_config = self._parse_states(self.states_file_path)
        self.v = MyVision(yolo_model_path=yolo_model)
        self.state_graph = self._build_graph()

    # ==================== 解析 ====================
    def _parse_states(self, file_path):
        config = {
            "pop-states":  {},
            "pop-change":  {},
            "page-states": {},
            "page-change": {},
        }
        self.pop_order  = []
        self.page_order = []

        if not file_path.exists():
            print(f"❌ 找不到配置文件: {file_path}")
            return config

        current_section = None

        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                raw = line.strip()
                if raw.startswith("#"):
                    tag = raw.lstrip("#").strip()
                    if tag in config:
                        current_section = tag
                    continue

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

        return config

    # ==================== 导航图 ====================
    def _build_graph(self):
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
        return graph

    # ==================== 内部识别（不加锁）====================

    def _capture(self):
        """获取图像源（不加锁，由调用方负责）"""
        return self.screenshot_path if self.screenshot_path else self.operator.capture()

    def _check_popup(self, img_source):
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
        for i in range(max_attempts):
            img_source = self._capture()
            pop = self._check_popup(img_source)
            if pop is None:
                return True
            print(f"  🔄 清除弹窗 (第 {i+1} 次)")
            if not self._dismiss_popup(pop):
                return False
            time.sleep(0.5)
        print("  ❌ 弹窗清除次数超限")
        return False

    def _identify_state(self, img_source):
        """纯识别，不截图不加锁"""
        candidates = []
        for state_name in self.page_order:
            base_path_str = self.states_config["page-states"][state_name]
            img_path = Path(base_path_str).with_suffix(".png")
            if not img_path.is_absolute():
                img_path = self.base_dir / img_path
            if not img_path.exists():
                continue
            score = self.v.match_score(img_source, str(img_path))
            if score > 0.9:
                return state_name
            if score > 0.7:
                candidates.append((state_name, score))

        if candidates:
            candidates.sort(key=lambda x: x[1], reverse=True)
            return candidates[0][0]
        return None

    # ==================== 对外接口（加锁）====================

    def get_states(self, auto_dismiss_popup=True):
        """截图 + 弹窗处理 + 状态识别，整个过程原子"""
        with self.operator.locked_step():
            img_source = self._capture()

            if auto_dismiss_popup:
                pop = self._check_popup(img_source)
                if pop is not None:
                    self._dismiss_popup(pop)
                    time.sleep(0.5)
                    img_source = self._capture()
                    pop2 = self._check_popup(img_source)
                    if pop2 is not None:
                        self._clear_popups()
                        img_source = self._capture()

            state = self._identify_state(img_source)
            if state:
                print(f"✅ 当前状态: [{state}]")
            else:
                print("❌ 未匹配到任何状态")
            return state

    def get_raw_state(self):
        """获取原始状态（不关弹窗）"""
        with self.operator.locked_step():
            img_source = self._capture()

            pop = self._check_popup(img_source)
            if pop:
                return ("pop", pop)

            state = self._identify_state(img_source)
            if state:
                return ("page", state)

            return (None, None)

    # ==================== 状态转换（原子操作）====================

    def states_change(self, key):
        """截图→检查→点击→等待→验证，全在一把锁内"""
        if key not in self.states_config["page-change"]:
            print(f"❌ 找不到转换: {key}")
            return False

        parts = key.split('_')
        start_state = parts[0]
        target_state = parts[1]

        json_path = Path(self.states_config["page-change"][key]).with_suffix(".json")
        if not json_path.is_absolute():
            json_path = self.base_dir / json_path

        for i in range(5):
            with self.operator.locked_step():
                # 截图 + 识别当前状态
                img = self._capture()
                current = self._identify_state(img)

                if current == target_state:
                    print(f"🎉 已到达 [{target_state}]")
                    return True

                if i == 0 and current != start_state:
                    print(f"❌ 当前状态 [{current}] 非起始 [{start_state}]")
                    return False

                # 点击（在锁内，不会被别的线程打断）
                print(f"⚡ [{key}] 第 {i+1} 次尝试，点击 {json_path}")
                self.operator.click_json(str(json_path))

            # 等待页面切换（锁外，让其他线程有机会操作）
            time.sleep(1.0)

            # 再次验证（重新加锁）
            with self.operator.locked_step():
                img = self._capture()
                if self._identify_state(img) == target_state:
                    print(f"🎉 已到达 [{target_state}]")
                    return True

        print(f"❌ 转换失败: {key}")
        return False

    # ==================== 导航 ====================

    def navigate_to(self, target, max_retries=3):
        for retry in range(max_retries):
            current = self.get_states()
            if current is None:
                print("❌ 无法获取当前状态")
                return False

            if current == target:
                print(f"🎉 已到达目标 [{target}]")
                return True

            path = self._find_path(current, target)
            if path is None:
                print(f"❌ 无法从 [{current}] 到达 [{target}]")
                return False

            print(f"📍 路径: {' -> '.join(path)}")

            success = True
            for i in range(len(path) - 1):
                from_s = path[i]
                to_s = path[i + 1]

                # 检查弹窗
                state_type, state_name = self.get_raw_state()
                if state_type == "pop":
                    print(f"🔔 导航中遇到弹窗 [{state_name}]，清除后重新规划")
                    with self.operator.locked_step():
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
    

"""
if __name__ == "__main__":
    mgr = StateManager("tasks/states/states.txt", app_name="幸福小渔村")
    mgr.get_states()
    #mgr.navigate_to("djsd")"""
