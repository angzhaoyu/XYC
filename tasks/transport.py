# transport.py
import sys
import time
import re
import os
import cv2
import numpy as np
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
        self.op = operate.Operator(app_name)
        self.resource = None
        self.res0 = None
        self.transport = None
        self.bird = None
        self.chose = None
        self.shangxian = None
        self.xian = None
        self.num = 0
 

    def choose_beast(self):
        print("开始选择海兽")
        MAX_RETRY = 20
        for attempt in range(MAX_RETRY):
            self.mgr.navigate_to('lingdi')
            n_res = self.res0
            print(f"资源数量: {n_res}")

            if n_res == 0:
                return None
            if self.xian is not None and self.xian == 0:
                return None

            self.mgr.get_states()
            if self.resource:
                self.op.click(self.resource[0])
            else:
                return None

            time.sleep(0.5)
            state = self.mgr.get_states()
            self.mgr.states_change("caiji_shangzhen_01")
            state = self.mgr.get_states()

            if state == 'shangzhen':
                # ✅ 成功进入上阵界面
                print("开始识别海兽数量")
                self.I_beasts()

                if self.chose == 0 and self.xian == 0:
                    self.mgr.states_change("shangzhen_lingdi_01")
                    return None

                n_sz = (self.xian + self.chose) // n_res
                n_sz = max(n_sz, 1)
                print(f"分配数量: {n_sz}个资源")

                if n_sz == 1:
                    pass
                elif n_sz <= self.shangxian:
                    for i in range(n_sz - 1):
                        if self.xian == 0:
                            break
                        path = f'tasks/transport/mouse_combo/00{i+2}.png'
                        print(f"点击路径: {path}")
                        self.mgr.get_states()
                        self.op.click_json(path)
                        self.xian -= 1
                elif n_sz > self.shangxian:
                    self.mgr.get_states()
                    self.op.click_json('tasks/transport/mouse_combo/yjsz.png')
                    self.xian -= self.shangxian + 1

                self.mgr.states_change("shangzhen_lingdi_02")
                print(f"完成选择海兽, 当前闲: {self.xian}")
                return  # ✅ 成功，退出

            else:
                # ✅ 失败，重试（不再递归）
                print(f"⚠ 第{attempt+1}次未进入上阵界面，重试...")
                self.mgr.navigate_to('lingdi')
                self.mgr.states_change("shangzhen_lingdi_01")
                time.sleep(1)

        print("⚠ 达到最大重试次数，放弃选择海兽")

    def I_resources(self):
        #print("开始识别资源")
        resources, birds, transported= self.detect_resources_and_birds()
        self.res0 = len(resources)
        filtered_resources = []
        for res in resources:
            overlap_with_any_bird = False
            for bird in birds:
                if self.is_overlap(res, bird):
                    overlap_with_any_bird = True
                    break # 只要与一个bird重叠，就无需检查其他birds
            # 如果没有与任何bird重叠，则保留该resource
            if not overlap_with_any_bird:
                filtered_resources.append(res)
        self.resource = filtered_resources
        self.transport = transported
        self.bird =  birds



    def detect_resources_and_birds(self):
        img_input =  self.op.capture()
        datas = self.vision.detect_yolo(img_input)
        #print(f"YOLO 识别结果: {datas}")
        resources = []
        birds = []
        transported = []
        if datas:
            #print(f"DEBUG: {datas}") 
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
        # box1 坐标
        x1_min, y1_min = box1[0]
        x1_max, y1_max = box1[1]
        # box2 坐标
        x2_min, y2_min = box2[0]
        x2_max, y2_max = box2[1]
        if x1_max < x2_min or x1_min > x2_max or y1_max < y2_min or y1_min > y2_max:
            return False
        return True


    def I_beasts(self):
        screenshot = self.op.capture()
        # limit_1 for chose/shangxian
        limit_1 = self.vision.limit_scope("tasks/transport/mouse_combo/chose.png", scale=1.0)
        ocr_sel = self.vision.detect_text(screenshot, a_percentage=limit_1, n=16)
        print(f"ocr_sel识别结果: {ocr_sel}")
        raw_sel = ocr_sel[0].get('text', '') if ocr_sel else ''     
        match_sel = re.search(r'(\d+)/(\d+)', raw_sel)
        if match_sel:
            chose     = int(match_sel.group(1))
            shangxian = int(match_sel.group(2))
        else:
            # 没有找到 / ，尝试取：第一个数字 + 最后一位数字作为分母
            m = re.match(r'^(\d).?(\d)$', raw_sel)   # 开头一个数字，可选任意1个字符，结尾一个数字
            if m:
                chose     = int(m.group(1))          # 第一个数字（通常 0 或 1）
                shangxian = int(m.group(2))          # 只取最后一位作为分母
            else:
                chose     = 0
                shangxian = 3
            if raw_sel and raw_sel[0].isdigit():
                chose = int(raw_sel[0])

        print(f"chose:{chose}, shangxian: {shangxian}")
        # limit_2 for xian
        limit_2 = self.vision.limit_scope("tasks/transport/mouse_combo/xian.png", scale=1.0)
        print("=" * 60)
        #print(screenshot)
        ocr_xian = self.vision.detect_text(screenshot, a_percentage=limit_2, n=16, math=True)
        #print("=" * 60)
        #print(f"xian现有结果: {ocr_xian}")


        raw_xian = ocr_xian[0].get('text', '') if ocr_xian else ''
        match_xian = re.search(r'(\d+)', raw_xian)
        xian = int(match_xian.group(1))
        self.chose = int(chose)
        if xian != 0 and chose == 0:
            self.chose = 1
        self.shangxian = int(shangxian)
        self.xian = xian

        print(f"当前选择: {self.chose}, 上限: {shangxian}, 闲: {xian}")

            
            
            
    def tra_bird(self, stop_m = False):
        self.mgr.navigate_to('lingdi')
        self.mgr.get_states()
        self.I_resources()
        if self.xian == 0:
            return None
            """print("没有闲位，等待5秒")
            num_t1 = len(self.transport)
            num_t2 = len(self.transport)
            while num_t1 == num_t2:
                self.I_resources()
                num_t1 = len(self.transport)
                time.sleep(5)"""

        for i in range(5):
            self.I_resources()
            self.op.click(self.bird[0]) #进入
            time.sleep(1)
            state = self.mgr.get_states()
            if state == 'guankan':
                break
        if stop_m:
            state = self.mgr.get_states()
            pass
        if self.mgr.get_states() == 'guankan':
            self.op.click_json("tasks/transport/mouse_combo/guankan.png")
            time.sleep(35)
            self.op.click_json("tasks/transport/mouse_combo/guanbi.png")
            time.sleep(1)
            for i in range(3):
                state = self.mgr.get_states()
                if state != 'guankan' or state != 'lingdi':
                    self.op.click_json("tasks/transport/mouse_combo/jixukan.png")
                    time.sleep(5)
                    self.op.click_json("tasks/transport/mouse_combo/guanbi.png")
            self.I_resources()
            self.choose_beast()


    def run(self, t_m = False):       
        print("="*60 ,"🚀 开始运输任务", sep="\n" )
        self.mgr.get_states()
        self.mgr.navigate_to("lingdi")
        self.I_resources()
        print(f"识别资源{self.resource}")
        print(f"识别到鸟{self.bird}")
        
        n_res = self.res0
        print(f"资源数量: {n_res}")
        while n_res > 0:
            print(f"开始选择海兽")
            self.choose_beast()
            print(f"完成一次选择")
            self.I_resources()
            n_res = self.res0
            if self.xian == 0:
                break
        try:
            if self.bird:
                if len(self.transport) + len(self.bird) != 6:
                    self.tra_bird() 

        except Exception as e:
            print(f"❌ 异常: {e}")
        print("=" * 60)


''''''
if __name__ == "__main__":
    task = TransportTask(app_name=1249806)
    #task.I_beasts()
    task.run()
    #task.tra_bird()

    
    
