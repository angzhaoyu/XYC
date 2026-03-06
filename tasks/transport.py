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
        MAX_RETRY = 5
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
                n_sz = min(n_sz, self.shangxian)
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
        ocr_sel = fix_ocr_text(ocr_sel[0].get('text', '') if ocr_sel else '') if ocr_sel else ''
        print(f"ocr_sel识别结果: {ocr_sel}")
        raw_sel = ocr_sel
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

    def secten(self,  path, scale=1):
        limit = self.vision.limit_scope(path, scale=scale)
        region =  self.vision.find_image(self.op.capture(), path, a_percentage=limit)
        return region         
            
            
    def tra_bird(self, stop_m = False, imgsave=False, mu =True ):
        self.mgr.navigate_to('lingdi')
        self.mgr.get_states()
        self.I_resources()
        if self.xian == 0:
            return None

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
            if imgsave == True:
                save_dir = "./screenshots"
                if not os.path.exists(save_dir):
                    os.makedirs(save_dir)
                index = 1
                while True:
                    file_path = os.path.join(save_dir, f"{index:03d}.png")
                    if not os.path.exists(file_path):
                        break
                    index += 1
                self.op.capture(file_path) 
            if mu == True:
                region = self.secten("tasks/transport/birds/438.png")
                if region:
                    self.mgr.navigate_to('lingdi')
                    return None

            self.op.click_json("tasks/transport/mouse_combo/guankan.png")
            time.sleep(35)
            self.op.click_json("tasks/transport/mouse_combo/guanbi.png")
            time.sleep(1)
            for i in range(3):
                state = self.mgr.get_states()
                if state != 'guankan' and state != 'lingdi':
                    self.op.click_json("tasks/transport/mouse_combo/jixukan.png")
                    time.sleep(5)
                    self.op.click_json("tasks/transport/mouse_combo/guanbi.png")
            self.I_resources()
            self.choose_beast()
            self.I_resources()
            self.choose_beast()


    def run(self, t_m = False):       
        print("="*60 ,"🚀 开始运输任务", sep="\n" )
        self.xian = None
        self.chose = None
        self.shangxian = None
        # ====================================
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



import re

def fix_ocr_text(text):
    """
    修正 OCR 识别结果，将常见误识别字符纠正为 "x/y" 格式
    x 应该是 0 或 1，y 是数字
    """
    if not text:
        return text
    
    # 转小写处理（可选）
    text = text.strip()
    
    # 常见的 "/" 误识别字符
    slash_mistakes = ['l', 'L', 'I', 'i', '|', '\\', '.', '!', ']', '[', '丨']
    
    # 常见的数字误识别映射
    digit_fixes = {
        'o': '0', 'O': '0', 'D': '0',
        'l': '1', 'L': '1', 'I': '1', 'i': '1', '|': '1',
        'z': '2', 'Z': '2',
        's': '5', 'S': '5',
        'b': '6', 'G': '6',
        'q': '9', 'g': '9',
    }
    
    # 尝试匹配 "数字 + 分隔符 + 数字" 的模式
    # 第一个字符应该是 0 或 1（或其误识别形式）
    
    result = list(text)
    
    # 如果长度为3，假设格式是 "x/y"
    if len(result) == 3:
        # 修正第一个字符（应该是 0 或 1）
        if result[0] in ['o', 'O', 'D']:
            result[0] = '0'
        elif result[0] in ['l', 'L', 'I', 'i', '|']:
            result[0] = '1'
        
        # 修正中间的分隔符（应该是 /）
        if result[1] in slash_mistakes:
            result[1] = '/'
        
        # 修正第三个字符（应该是数字）
        if result[2] in digit_fixes:
            result[2] = digit_fixes[result[2]]
    
    # 如果长度为2，可能漏识别了分隔符，如 "12" 实际是 "1/2"
    elif len(result) == 2:
        first = result[0]
        second = result[1]
        
        # 修正第一个字符
        if first in ['o', 'O', 'D']:
            first = '0'
        elif first in ['l', 'L', 'I', 'i', '|']:
            first = '1'
        
        # 修正第二个字符
        if second in digit_fixes:
            second = digit_fixes[second]
        
        return f"{first}/{second}"
    
    return ''.join(result)


def parse_ocr_ratio(text):
    """
    解析 OCR 结果，返回 (当前数量, 上限) 元组
    例如: "1/3" -> (1, 3)
    """
    fixed_text = fix_ocr_text(text)
    
    # 尝试用 / 分割
    if '/' in fixed_text:
        parts = fixed_text.split('/')
        if len(parts) == 2:
            try:
                chose = int(parts[0])
                shangxian = int(parts[1])
                return chose, shangxian
            except ValueError:
                pass
    
    # 解析失败返回 None
    print(f"OCR 解析失败: 原文='{text}', 修正后='{fixed_text}'")
    return None, None

'''
if __name__ == "__main__":
    task = TransportTask(app_name=1249806)
    #task.I_beasts()
    task.run()
    #task.tra_bird()

'''
    
