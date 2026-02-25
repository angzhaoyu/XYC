import cv2
import numpy as np
import os
import json
import torch
from coordinate_utils import CoordinateConverter
from pathlib import Path
from PIL import Image

class MyVision:
    def __init__(self, yolo_model_path='models/best.pt'):
        # 只保存路径，不立即加载模型
        self.yolo_model_path = yolo_model_path
        self.model = None  # 延迟加载
        self.ocr_reader = None

    # --- 1. 范围限制功能 ---
    def limit_scope(self, image_path, scale=1.0):
        json_path = os.path.splitext(image_path)[0] + '.json'
        if not os.path.exists(json_path): 
            return [[0.0, 0.0], [1.0, 1.0]]
        
        with open(json_path, 'r', encoding='utf-8') as f:
            points = json.load(f)['shapes'][0]['points']
        
        # 转换为 a_percentage
        converter = CoordinateConverter(points, 'a_pixel', obj=image_path)
        (x1, y1), (x2, y2) = converter.a_percentage
        
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        w, h = (x2 - x1) * scale, (y2 - y1) * scale
        return [[max(0.0, cx - w/2), max(0.0, cy - h/2)], [min(1.0, cx + w/2), min(1.0, cy + h/2)]]

    # --- 私有方法：按需加载 YOLO 模型 ---
    def _load_yolo_model(self):
        if self.model is None and os.path.exists(self.yolo_model_path):
            #print("正在加载 YOLO 模型...（仅首次调用 detect_yolo 时加载）")
            self.model = torch.hub.load('ultralytics/yolov5', 'custom', path=self.yolo_model_path, device='cpu')  # 可改为 'cuda' 如果需要
            #print("YOLO 模型加载完成！")

    # --- 修正后的 YOLO 识别函数（延迟加载）---
    def detect_yolo(self, img_input, a_percentage=None):
        if isinstance(img_input, np.ndarray):
            os.makedirs("window", exist_ok=True)
            save_path_temp = "window/temp_image.png"
            cv2.imwrite(save_path_temp, img_input)
            img_input = save_path_temp
            print(f"YOLO 识别输入: {img_input}")         
        self._load_yolo_model()  # 关键：在这里才加载
        img_bgr = self._load(img_input)
        roi_bgr, (ox, oy) = self._get_roi(img_bgr, a_percentage)
        roi_rgb = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2RGB)

        print("YOLO 识别中...")
        results = []
        if self.model:
            df = self.model(roi_rgb).pandas().xyxy[0]
            for _, r in df.iterrows():
                results.append({
                    "name": r['name'], 
                    "box": [[r['xmin']+ox, r['ymin']+oy], [r['xmax']+ox, r['ymax']+oy]],
                    "conf": r['confidence']
                })
        return results

    def _load(self, data):
        """支持中文路径读取图片"""
        if isinstance(data, str):
            img = cv2.imdecode(np.fromfile(data, dtype=np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                print(f"❌ 无法读取图片路径: {data}")
            return img 
        return data


    def find_image(self, img1_input, img2_input, a_percentage=None):
        # 1. 确保输入是字符串路径（处理 Path 对象）
        img1_path = str(img1_input) if isinstance(img1_input, (str, Path)) else img1_input
        img2_path = str(img2_input) if isinstance(img2_input, (str, Path)) else img2_input

        # 2. 加载图片
        img1 = self._load(img1_path)      # 大图
        img2_full = self._load(img2_path) # 模板图
        
        if img1 is None or img2_full is None:
            return None

        # 3. 获取各自的 ROI
        roi_img1, (ox, oy) = self._get_roi(img1, a_percentage)
        img2_roi = self._get_template_roi(img2_path, img2_full)

        # --- 核心修复：强制对齐数据格式 ---
        # A. 确保通道数一致 (如果一个是单通道一个是三通道会报错)
        if len(roi_img1.shape) != len(img2_roi.shape):
            if len(roi_img1.shape) == 3:
                img2_roi = cv2.cvtColor(img2_roi, cv2.COLOR_GRAY2BGR)
            else:
                roi_img1 = cv2.cvtColor(roi_img1, cv2.COLOR_GRAY2BGR)

        # B. 确保数据类型一致 (强制转为 uint8)
        roi_img1 = roi_img1.astype(np.uint8)
        img2_roi = img2_roi.astype(np.uint8)

        # C. 确保连续内存 (防止 UMat 报错)
        roi_img1 = np.ascontiguousarray(roi_img1)
        img2_roi = np.ascontiguousarray(img2_roi)

        # 4. 执行匹配
        try:
            res = cv2.matchTemplate(roi_img1, img2_roi, cv2.TM_CCOEFF_NORMED)
            _, m_val, _, m_loc = cv2.minMaxLoc(res)
            
            if m_val > 0.8:
                h, w = img2_roi.shape[:2]
                return [[float(m_loc[0] + ox), float(m_loc[1] + oy)], 
                        [float(m_loc[0] + w + ox), float(m_loc[1] + h + oy)]]
        except Exception as e:
            print(f"匹配过程中出错: {e}")
            
        return None



    def _get_template_roi(self, img_path, img_data):
        """新增辅助函数：根据 JSON 裁切模板图"""
        if not isinstance(img_path, str):
            return img_data # 如果传入的不是路径，直接返回原图
            
        json_path = os.path.splitext(img_path)[0] + '.json'
        if not os.path.exists(json_path):
            return img_data # 没有 JSON 则不裁切
            
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # 获取第一个标注形状的像素点
            points = data['shapes'][0]['points']
            
        # 计算矩形区域
        x1, y1 = int(min(p[0] for p in points)), int(min(p[1] for p in points))
        x2, y2 = int(max(p[0] for p in points)), int(max(p[1] for p in points))
        
        # 执行裁切
        return img_data[y1:y2, x1:x2]

    # --- 文字识别 ---
    def detect_text(self, img_input, a_percentage=None, n=4, math = None, chinese = None):
        import easyocr
        if not self.ocr_reader: 
            '''
            #print("正在初始化 EasyOCR（仅首次调用时加载）")
            if chinese:
                self.ocr_reader = easyocr.Reader(['ch_sim'], gpu=True)  # 可改为 True 使用 GPU
            else:'''
            self.ocr_reader = easyocr.Reader(['en'], gpu=True)  # 可改为 True 使用 GPU
        img = self._load(img_input)
        roi, (ox, oy) = self._get_roi(img, a_percentage)

        img2 = cv2.resize(roi, None, fx=n, fy=n, interpolation=cv2.INTER_CUBIC)
        # 2. 转为灰度
        gray = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
        # 3. 增强对比度 & 二值化
        # 使用大津法 (Otsu's thresholding) 自动寻找阈值
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        # 4. 形态学操作（可选）：去除噪点或加粗文字
        kernel = np.ones((2,2), np.uint8)
        processed_img = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
        
        '''
        cv2.imwrite("debug_1_resized_color.jpg", img2)          # 放大后的彩色原图
        cv2.imwrite("debug_2_gray.jpg", gray)
        
        image_path = "./debug_3_processed.jpg"
        cv2.imwrite(image_path, processed_img)     
        '''

        if math:
            #img11 = cv2.imread(image_path)      
            text_output = self.ocr_reader.readtext(
                processed_img,
                #detail = 0,                # 只返回文字列表
                allowlist = '0123456789',  # 只认 0~9，极大提高纯数字准确率
                # 可选加这些参数进一步优化
                paragraph = False,         # 不合并成段落
                min_size = 5,             # 忽略太小的检测框
                contrast_ths = 0.1,
                adjust_contrast = 0.5,
                text_threshold = 0.3,
                low_text = 0.3,
            )
        else:
            text_output = self.ocr_reader.readtext(processed_img)
            
        final = []
        for (bbox, text, prob) in text_output:
            xs, ys = [p[0] for p in bbox], [p[1] for p in bbox]
            final.append({"text": text, "box": [[min(xs)+ox, min(ys)+oy], [max(xs)+ox, max(ys)+oy]]})
        return final

    def _get_roi(self, img, a_perc):
        if not a_perc: 
            return img, (0, 0)
        h, w = img.shape[:2]
        x1, y1 = int(a_perc[0][0]*w), int(a_perc[0][1]*h)
        x2, y2 = int(a_perc[1][0]*w), int(a_perc[1][1]*h)
        return img[y1:y2, x1:x2], (x1, y1)
    


'''
vision = MyVision(yolo_model_path="models/best.pt")
a_percentage = vision.limit_scope("tasks/transport/mouse_combo/002.png", scale=1.0)
if a_percentage:
    results = vision.detect_text("tasks/transport/mouse_combo/002.png",a_percentage)
print(results, len(results))

print(a_percentage)

results = vision.detect_text("01.png")
print(results, len(results))


vision = MyVision(yolo_model_path="models/best.pt")
a_percentage = vision.limit_scope("tasks/transport/mouse_combo/003.png", scale=1)
if a_percentage:
    print(a_percentage)
    results = vision.detect_text("screenshots/current.png", a_percentage, n=16)
print(results, len(results))
#find_image(self, img1_input, img2_input, a_percentage=None)
# 
# 

a_percentage = vision.detect_yolo("screenshots/100.png")
print(a_percentage)

import operate
img = operate.Operator(app_name="幸福小渔村").capture()

vision = MyVision(yolo_model_path="models/best.pt")
limit = vision.limit_scope("tasks/change-regions/shezhi.png", scale=1)
a_percentage = vision.detect_text(img, limit, n=4)
print("=="*30,a_percentage)

'''''''''