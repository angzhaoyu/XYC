# transport.py
import sys
import time
import re
import os
from pathlib import Path
# --- 路径适配 ---
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))
import vision
import operate
from tasks.get_states import StateManager


class TransportTask:
    def __init__(self, app_name=None):
        self.vision = vision.MyVision(yolo_model_path="models/best.pt")
        self.mgr = StateManager("tasks/states.txt", app_name=app_name)
        self.mgr.navigate_to("lingdi")
        self.operator = operate.Operator(app_name)

    def detect_resources_and_birds(self):
        img_input =  self.operator.capture()
        datas = self.vision.detect_yolo(img_input)
        print(f"YOLO 识别结果: {datas}")
        resources = []
        birds = []
        transported = []
        if datas:
            print(f"DEBUG: {datas}") 
            for item in datas:
                name = item['name'].lower()  # 转小写
                box = item['box']
                if 'resource' in name:       # 包含 resource 即可
                    resources.append(box)
                elif 'bird' in name:         # 包含 bird 即可
                    birds.append(box)
                elif 'transport' in name:    # 包含 transport 即可
                    transported.append(box)
        return resources, birds, transported       

    def is_overlap(self, box1, box2):
        """
        判断两个矩形框是否重叠
        box格式: [[x1, y1], [x2, y2]] 左上角和右下角
        """
        # box1 坐标
        x1_min, y1_min = box1[0]
        x1_max, y1_max = box1[1]
        # box2 坐标
        x2_min, y2_min = box2[0]
        x2_max, y2_max = box2[1]
        # 不重叠的条件（任一为真则不重叠）
        # box1 在 box2 左边 / 右边 / 上边 / 下边
        if x1_max < x2_min or x1_min > x2_max or y1_max < y2_min or y1_min > y2_max:
            return False
        return True


# --- 运行部分 ---
"""
"""""""""
tt = TransportTask(app_name="幸福小渔村")

resources, birds, transported = tt.detect_resources_and_birds()
print(f"资源点: {resources}")   
print(f"鸟点: {birds}")
print(f"已运输: {transported}")

#img = Image.fromarray(cv2.cvtColor(data, cv2.COLOR_BGR2RGB))

