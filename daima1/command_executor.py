import time
import keyboard
from typing import List
import os
import json
from functions.operate import *
from functions.interactive import *
from functions.coordinate_utils import CoordinateConverter


def time_sleep(base_time):
        actual_time = base_time + random.uniform(-0.3, -0.2)
        actual_time = max(0, actual_time) 
        time.sleep(actual_time)

class KeyboardExecutor:
    """键盘命令执行器"""
    
    def __init__(self, command_file: str):
        self.command_file = command_file
        
    def _press(self, keys: List[str]):
        """执行按键"""
        if len(keys) == 1:
            keyboard.press_and_release(keys[0])
            print(f"Pressed: {keys[0]}")
        else:
            # 组合键 - 同时按下所有键
            for key in keys:
                keyboard.press(key)
            time.sleep(0.05)  # 短暂保持
            for key in reversed(keys):
                keyboard.release(key)
            print(f"Pressed combo: {' + '.join(keys)}")
    
    def _long_press(self, key: str, duration: float):
        """执行长按"""
        keyboard.press(key)
        time.sleep(duration)
        keyboard.release(key)
        print(f"Long pressed: {key} for {duration}s")
    
    def execute(self):
        """执行命令序列"""
        with open(self.command_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            print(f"Executing: {line}")
            parts = [p.strip() for p in line.split(',')]
            
            # 提取按键和参数
            keys = []
            action = 'press'
            duration = 0
            n_time = 0
            
            for part in parts:
                if 'long_press=' in part:
                    action = 'long_press'
                    duration = float(part.split('=')[1])
                elif 'n_time=' in part:
                    n_time = float(part.split('=')[1])
                elif part == 'press':
                    action = 'press'
                elif part and part not in ['press']:
                    keys.append(part)
            
            # 执行动作
            if keys:
                if action == 'long_press' and duration > 0:
                    self._long_press(keys[0], duration)
                else:
                    self._press(keys)
            
            # 动作执行完后等待
            if n_time > 0:
                print(f"Waiting {n_time}s before next action")
                time.sleep(n_time)


class MouseExecutor:
    def __init__(self, command_file: str, app_name: str = "Phone"):
        """
        Args:
            command_file: 命令文件路径 (如 .recorder/analyzer_xxx/mouse_combo.txt)
            app_name: 应用窗口名称
        """
        self.command_file = command_file
        self.app_name = app_name
        base_dir = os.path.dirname(command_file).replace('\\', '/')
        self.image_folder = os.path.join(base_dir, "mouse_combo").replace('\\', '/')

        # 当前处理的状态
        self.image_path = None  # 当前图片路径
        self.image_region = None  # 当前目标在屏幕上的坐标
        self.slide_direction = None  # 滑动方向
        
    def execute_commands(self):
        """执行所有命令"""
        commands = self._read_commands()      
        for command_parts in commands:
            self._execute_single_command(command_parts)
    
    def _read_commands(self) -> List[List[str]]:
        """读取命令文件"""
        try:
            with open(self.command_file, 'r', encoding='utf-8') as f:
                result = []
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    # 按逗号分割，去除空白
                    parts = [part.strip() for part in line.split(',') if part.strip()]
                    result.append(parts)
                return result
        except Exception as e:
            print(f"错误: 无法读取命令文件: {e}")
            return []
    
    def _execute_single_command(self, command_parts: List[str]):
        """
        执行单条命令
        Args:
            command_parts: 命令部分列表，如 ['Figure1', 'recognize', 'click', 'sleep=2.5']
        """
        # 重置状态
        self.image_region = None
        self.slide_direction = None
        sleep_time = None
        
        # 解析命令
        #figure_name = None
        use_recognize = False
        action = None
        
        for part in command_parts:
            # 1. 解析 Figure
            if part.startswith('Figure'):
                figure_num = part.replace('Figure', '')
                self.image_path = os.path.join(self.image_folder, f"{figure_num}.png").replace('\\', '/')

            
            # 2. 解析识别方式
            elif part == 'recognize':
                use_recognize = True
            elif part == 'no_recognize':
                use_recognize = False
            
            # 3. 解析动作
            elif part == 'click':
                action = 'click'
            elif part.startswith('slide_'):
                action = 'slide'
                self.slide_direction = part.replace('slide_', '')  # up/down/left/right
            
            # 4. 解析 sleep
            elif part.startswith('sleep='):
                sleep_time = float(part.split('=')[1])
            
            # 5. 解析 duration
            elif part.startswith('duration='):
                duration = float(part.split('=')[1])
        
        # 执行识别（如果需要）
        if use_recognize and self.image_path:
            self._recognize_and_convert(self.image_path)
        elif not use_recognize and self.image_path:
            # 不识别时，使用标注文件中的坐标
            self._get_annotated_region(self.image_path)
        
        # 执行动作
        if action and self.image_region:
            if action == 'click':
                self._click()
            elif action == 'slide':
                self._slide()
        # 执行 sleep
        if sleep_time:
            #print(f"  Sleep: {sleep_time}s")
            time.sleep(sleep_time)

    #识别图片并转换坐标到屏幕坐标
    def _recognize_and_convert(self, image_path: str) -> Optional[List[List[float]]]:
        if not os.path.exists(image_path):
            print(f"    警告: 图片不存在 {image_path}")
            return None
        # 读取对应的 json 标注文件
        json_path = image_path.replace('.png', '.json')
        if not os.path.exists(json_path):
            print(f"    警告: 标注文件不存在 {json_path}")
            return None
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not data['shapes']:
            print(f"    警告: 标注文件中没有标注框")
            return None

        points = data['shapes'][0]['points']
        x1, y1 = points[0]
        x2, y2 = points[1]
        x1, x2 = int(min(x1, x2)), int(max(x1, x2))
        y1, y2 = int(min(y1, y2)), int(max(y1, y2))
        full_image = cv2.imread(image_path)
        if full_image is None:
            print(f"    警告: 无法读取图片 {image_path}")
            return None
        template = full_image[y1:y2, x1:x2]
        if template.size == 0:
            print(f"    警告: 切割区域为空")
            return None

        recognized_region = screenshot_recognize(template)
        if not recognized_region:
            print(f"    警告: 未识别到目标")
            return None
        self.image_region = recognized_region 

    #从标注文件读取矩形框区域并转换到屏幕坐标
    def _get_annotated_region(self, image_path: str) -> Optional[List[List[float]]]:
        # 读取对应的 json 标注文件
        json_path = image_path.replace('.png', '.json')
        if not os.path.exists(json_path):
            print(f"警告: 标注文件不存在 {json_path}")
            return None
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if data['shapes']:
            points = data['shapes'][0]['points']
            # 转换点1: 图片像素 -> 百分比 -> 屏幕坐标
            percentage_coord1 = CoordinateConverter(
                points,
                'a_pixel',
                image_path
            ).a_percentage          
            self.image_region = CoordinateConverter(
                percentage_coord1,
                'a_percentage',
                self.app_name
            ).s_pixel
          
    def _click(self):
        if self.image_region:
            click(self.image_region)
    
    def _slide(self):
        if self.image_region and self.slide_direction:
            human_like_drag(self.image_region, self.slide_direction)



"""
if __name__ == "__main__":
    # 执行鼠标命令
    mouse_executor = CommandExecutor(
        "./recorder/analyzer_a/mouse_combo.txt",
        app_name="Phone"
    )
    mouse_executor.execute_command()
    # 执行键盘命令
    keyboard_executor = CommandExecutor(
        "./recorder/analyzer_Phone_20251002_231419/keyboard_combo.txt",
        app_name="Phone"
    )
    keyboard_executor.execute_command()



if __name__ == "__main__":
    executor = MouseExecutor(
        command_file="./recorder/analyzer_resurrection_coin/mouse_combo.txt",
        app_name="Phone"
    )
    executor.execute_commands()


"""