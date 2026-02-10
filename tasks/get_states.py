import sys
import time
from pathlib import Path
from collections import deque
# 确保能找到 vision 模块
sys.path.append(str(Path(__file__).parent.parent))
import vision
from operate import Operator

class StateManager:
    def __init__(self, states_file, app_name=None, screenshot_path=None, yolo_model="models/best.pt"):
        """
        Args:
            states_file: states.txt 的路径
            app_name: 窗口名称或 ID
            screenshot_path: 可选，外部提供的截图路径
        """
        self.operator = Operator(app_name)
        self.screenshot_path = screenshot_path
        
        # 转化为绝对路径，确保后续拼接不出错
        self.states_file_path = Path(states_file).resolve()
        self.base_dir = self.states_file_path.parent.parent # 获取项目根目录 (XYC)

        # 1. 解析配置文件
        self.states_config = self._parse_states(self.states_file_path)
        
        # 2. 初始化识别引擎
        self.v = vision.MyVision(yolo_model_path=yolo_model)
        self.state_graph = self._build_graph()

    def _build_graph(self):
        """
        根据 txt 中的 change 配置构建网络
        返回: {起始状态: {目标状态: change_key}}
        """
        graph = {}
        
        for key in self.states_config["change"]:
            # key 格式: 起始_目标_序号，如 celan_qiandao_01
            parts = key.split('_')
            if len(parts) >= 3:
                from_state = parts[0]
                to_state = parts[1]
                
                if from_state not in graph:
                    graph[from_state] = {}
                if to_state not in graph[from_state]:
                    graph[from_state][to_state] = key
        
        #print(f"📊 状态网络: {graph}")
        return graph

    # ========== 新增函数2：导航到目标状态 ==========
    def navigate_to(self, target):
        """
        导航到目标状态
        返回: True 成功, False 失败/无法到达
        """
        current = self.get_states()
        if current is None:
            print("❌ 无法获取当前状态")
            return False
        
        if current == target:
            print(f"🎉 已在目标状态 [{target}]")
            return True
        
        # BFS 找路径
        path = self._find_path(current, target)
        if path is None:
            print(f"❌ 无法从 [{current}] 到达 [{target}]")
            return False
        
        print(f"📍 路径: {' -> '.join(path)}")
        
        # 执行路径
        for i in range(len(path) - 1):
            from_s = path[i]
            to_s = path[i + 1]
            change_key = self.state_graph[from_s][to_s]
            
            print(f"⚡ 执行: {from_s} -> {to_s}")
            if not self.states_change(change_key):
                print(f"❌ 转换失败")
                return False
        
        return self.get_states() == target

    def _find_path(self, start, end):
        """BFS 找最短路径"""
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

    def _parse_states(self, file_path):
        """解析 states.txt 并保持 check 状态的顺序"""
        config = {"check": {}, "out": {}, "change": {}}
        self.check_order = [] 
        
        if not file_path.exists():
            print(f"❌ 找不到配置文件: {file_path}")
            return config

        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.split('#')[0].strip()
                if not line or '=' not in line: continue
                
                key, val = [x.strip() for x in line.split('=')]
                val = val.strip('"')
                
                parts = key.split('_')
                if len(parts) == 1:
                    config["check"][key] = val
                    self.check_order.append(key)
                elif len(parts) == 2:
                    config["out"][key] = val
                elif len(parts) == 3:
                    config["change"][key] = val
        return config

    def get_states(self):
        """
        状态识别：自动补全 .png 后缀
        """
        # 获取图像源
        img_source = self.screenshot_path if self.screenshot_path else self.operator.capture()
        for state_name in self.check_order:
            # 基础路径，例如 "tasks/states/huode"
            base_path_str = self.states_config["check"][state_name]
            
            # --- 关键修改：识别必须用图片 ---
            img_path = Path(base_path_str).with_suffix(".png")            
            # 如果是相对路径，尝试基于项目根目录定位
            if not img_path.is_absolute():
                img_path = self.base_dir / img_path

            if not img_path.exists():
                print(f"⚠️ 找不到状态图片: {img_path}")
                continue
            res = self.v.find_image(img_source, str(img_path)) 
            if res:
                print(f"✅ 匹配成功: 当前状态为 [{state_name}]")
                if state_name == "huode":
                    self.operator.click_json("tasks/states_change/002.json")
                return state_name    
        print("❌ 未匹配到任何预设状态")
        return None

    def states_out(self, key):
        """
        退出逻辑：自动补全 .json 后缀用于点击
        """
        if key not in self.states_config["out"]: return False
        
        initial_state = self.get_states()
        # 点击必须用 JSON
        json_to_click = Path(self.states_config["out"][key]).with_suffix(".json")
        
        for i in range(3):
            print(f"🔄 执行退出操作 [{key}] (第 {i+1} 次尝试)")
            self.operator.click_json(str(json_to_click))
            time.sleep(0.3) # 等待动画
            
            current_state = self.get_states()
            if current_state != initial_state:
                print(f"✨ 退出成功")
                return True
        return False

    def states_change(self, key):
        """
        转换逻辑：自动补全 .json 后缀用于点击
        """
        if key not in self.states_config["change"]: 
            print(f"❌ 配置中找不到转换 Key: {key}")
            return False        
        parts = key.split('_')
        start_state = parts[0]
        if start_state != self.get_states():
            print(f"❌ 当前状态非 [{start_state}]，无法执行")
            return False   
        target_state = parts[1]  
        # 点击必须用 JSON
        json_to_click = Path(self.states_config["change"][key]).with_suffix(".json")
        print(json_to_click)  
        for i in range(3):
            current = self.get_states()
            print(f"🔍 当前状态: {current}, 目标状态: {target_state}")
            
            if current == target_state:
                print(f"🎉 已到达 [{target_state}]")
                return True            
            print(f"⚡ 状态转换 [{key}] (第 {i+1} 次尝试)",str(json_to_click))
            self.operator.click_json(str(json_to_click))
            time.sleep(1.0) # 等待动画          
            if self.get_states() == target_state:
                return True
                
        print(f"❌ 转换失败")
        return False


"""# --- 运行部分 ---"""
# 请确保你的 states.txt 在 XYC/tasks/states.txt
#mgr = StateManager("tasks/states.txt", app_name="幸福小渔村")
#mgr = StateManager("tasks/states.txt",screenshot_path="screenshots/060.png")
# 1. 打印配置看看是否读取成功
#print("Loaded Config:", mgr.states_config)
# 2. 测试识别
#mgr.get_states()
# 3. 测试转换
#mgr.states_change("caiji_shangzhen_01")
#mgr.navigate_to("shangzhen")
# 导航到 qiandao  
#mgr.navigate_to("shangzhen")

