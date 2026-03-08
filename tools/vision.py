import cv2
import numpy as np
import os
import json
import torch
from pathlib import Path


class MyVision:
    def __init__(self, yolo_model_path='models/best.pt',
                 true_window_json="window/true_window.json"):
        self.yolo_model_path = yolo_model_path
        self.model = None
        self.ocr_reader = None

        # ★ 从 true_window.json 加载固定边框
        self.borders = {'left': 0, 'top': 0, 'right': 0, 'bottom': 0}
        self._load_borders(true_window_json)

    # ==================== ★ 新增方法 ====================

    def _load_borders(self, json_path):
        """从 true_window.json 读取固定边框像素"""
        if not json_path or not Path(json_path).exists():
            return
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if 'shapes' in data and data['shapes']:
                pts = data['shapes'][0]['points']
                iw = data.get('imageWidth', 0)
                ih = data.get('imageHeight', 0)
                self.borders = {
                    'left':   int(pts[0][0]),
                    'top':    int(pts[0][1]),
                    'right':  int(iw - pts[1][0]),
                    'bottom': int(ih - pts[1][1]),
                }
        except Exception:
            pass

    def _calc_content_scale(self, img_current, img_template):
        """当前截图 vs 模板截图，内容区域的缩放比"""
        h1, w1 = img_current.shape[:2]
        h2, w2 = img_template.shape[:2]
        b = self.borders
        orig_cw = w2 - b['left'] - b['right']
        orig_ch = h2 - b['top'] - b['bottom']
        curr_cw = w1 - b['left'] - b['right']
        curr_ch = h1 - b['top'] - b['bottom']
        if orig_cw > 0 and orig_ch > 0:
            return curr_cw / orig_cw, curr_ch / orig_ch
        return 1.0, 1.0

    # ==================== ★ 修改的方法 ====================

    def limit_scope(self, image_path, scale=1.0):
        """★ 用 self.borders 计算内容区域百分比（不依赖 CoordinateConverter）"""
        json_path = os.path.splitext(image_path)[0] + '.json'
        if not os.path.exists(json_path):
            return [[0.0, 0.0], [1.0, 1.0]]

        with open(json_path, 'r', encoding='utf-8') as f:
            points = json.load(f)['shapes'][0]['points']

        img = self._load(image_path)
        if img is None:
            return [[0.0, 0.0], [1.0, 1.0]]

        h, w = img.shape[:2]
        b = self.borders
        cw = w - b['left'] - b['right']
        ch = h - b['top'] - b['bottom']
        if cw <= 0 or ch <= 0:
            return [[0.0, 0.0], [1.0, 1.0]]

        # 像素坐标 → 内容区域百分比
        x1 = max(0, (points[0][0] - b['left']) / cw)
        y1 = max(0, (points[0][1] - b['top'])  / ch)
        x2 = min(1, (points[1][0] - b['left']) / cw)
        y2 = min(1, (points[1][1] - b['top'])  / ch)

        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        rw, rh = (x2 - x1) * scale, (y2 - y1) * scale
        return [[max(0.0, cx - rw/2), max(0.0, cy - rh/2)],
                [min(1.0, cx + rw/2), min(1.0, cy + rh/2)]]

    def _get_roi(self, img, a_perc):
        """★ 百分比是内容区域的，映射时加回边框偏移"""
        if not a_perc:
            return img, (0, 0)
        h, w = img.shape[:2]
        b = self.borders
        cw = w - b['left'] - b['right']
        ch = h - b['top'] - b['bottom']

        x1 = int(a_perc[0][0] * cw + b['left'])
        y1 = int(a_perc[0][1] * ch + b['top'])
        x2 = int(a_perc[1][0] * cw + b['left'])
        y2 = int(a_perc[1][1] * ch + b['top'])

        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        return img[y1:y2, x1:x2], (x1, y1)

    def find_image(self, img1_input, img2_input, a_percentage=None):
        """★ 窗口缩放时自动缩放模板"""
        img1_path = str(img1_input) if isinstance(img1_input, (str, Path)) else img1_input
        img2_path = str(img2_input) if isinstance(img2_input, (str, Path)) else img2_input

        img1 = self._load(img1_path)
        img2_full = self._load(img2_path)
        if img1 is None or img2_full is None:
            return None

        roi_img1, (ox, oy) = self._get_roi(img1, a_percentage)
        img2_roi = self._get_template_roi(img2_path, img2_full)

        if len(roi_img1.shape) != len(img2_roi.shape):
            if len(roi_img1.shape) == 3:
                img2_roi = cv2.cvtColor(img2_roi, cv2.COLOR_GRAY2BGR)
            else:
                roi_img1 = cv2.cvtColor(roi_img1, cv2.COLOR_GRAY2BGR)
        roi_img1 = np.ascontiguousarray(roi_img1.astype(np.uint8))
        img2_roi = np.ascontiguousarray(img2_roi.astype(np.uint8))

        # ★ 按内容区域缩放比 resize 模板
        sx, sy = self._calc_content_scale(img1, img2_full)
        h_tpl, w_tpl = img2_roi.shape[:2]
        new_w = max(1, int(w_tpl * sx))
        new_h = max(1, int(h_tpl * sy))

        if abs(sx - 1.0) > 0.01 or abs(sy - 1.0) > 0.01:
            interp = cv2.INTER_AREA if sx < 1 else cv2.INTER_LINEAR
            img2_roi = cv2.resize(img2_roi, (new_w, new_h), interpolation=interp)

        h_roi, w_roi = roi_img1.shape[:2]
        if new_w >= w_roi or new_h >= h_roi:
            return None

        try:
            res = cv2.matchTemplate(roi_img1, img2_roi, cv2.TM_CCOEFF_NORMED)
            _, m_val, _, m_loc = cv2.minMaxLoc(res)
            if m_val > 0.6:
                h, w = img2_roi.shape[:2]
                return [[float(m_loc[0] + ox), float(m_loc[1] + oy)],
                        [float(m_loc[0] + w + ox), float(m_loc[1] + h + oy)]]
        except Exception as e:
            print(f"匹配过程中出错: {e}")
        return None

    # ==================== 以下完全不变 ====================

    def _load_yolo_model(self):
        if self.model is None and os.path.exists(self.yolo_model_path):
            self.model = torch.hub.load('ultralytics/yolov5', 'custom',
                                        path=self.yolo_model_path, device='cpu')

    def detect_yolo(self, img_input, a_percentage=None):
        """★ 不再写临时文件，避免多线程冲突"""
        self._load_yolo_model()

        if isinstance(img_input, np.ndarray):
            img_bgr = img_input
        else:
            img_bgr = self._load(img_input)

        if img_bgr is None:
            return []

        roi_bgr, (ox, oy) = self._get_roi(img_bgr, a_percentage)
        roi_rgb = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2RGB)

        results = []
        if self.model:
            df = self.model(roi_rgb).pandas().xyxy[0]
            for _, r in df.iterrows():
                results.append({
                    "name": r['name'],
                    "box": [[r['xmin']+ox, r['ymin']+oy],
                            [r['xmax']+ox, r['ymax']+oy]],
                    "conf": r['confidence']
                })
        return results
    def _load(self, data):
        if isinstance(data, str):
            img = cv2.imdecode(np.fromfile(data, dtype=np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                print(f"❌ 无法读取图片路径: {data}")
            return img
        return data

    def _get_template_roi(self, img_path, img_data):
        if not isinstance(img_path, str):
            return img_data
        json_path = os.path.splitext(img_path)[0] + '.json'
        if not os.path.exists(json_path):
            return img_data
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            points = data['shapes'][0]['points']
        x1, y1 = int(min(p[0] for p in points)), int(min(p[1] for p in points))
        x2, y2 = int(max(p[0] for p in points)), int(max(p[1] for p in points))
        return img_data[y1:y2, x1:x2]

    def detect_text(self, img_input, a_percentage=None, n=4, math=None, chinese=None):
        import easyocr
        if not self.ocr_reader:
            self.ocr_reader = easyocr.Reader(['en'], gpu=False)
        img = self._load(img_input)
        roi, (ox, oy) = self._get_roi(img, a_percentage)
        img2 = cv2.resize(roi, None, fx=n, fy=n, interpolation=cv2.INTER_CUBIC)
        gray = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        kernel = np.ones((2, 2), np.uint8)
        processed_img = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
        if math:
            text_output = self.ocr_reader.readtext(
                processed_img, allowlist='0123456789',
                paragraph=False, min_size=5, contrast_ths=0.1,
                adjust_contrast=0.5, text_threshold=0.3, low_text=0.3,
            )
        else:
            text_output = self.ocr_reader.readtext(processed_img)
        final = []
        for (bbox, text, prob) in text_output:
            xs, ys = [p[0] for p in bbox], [p[1] for p in bbox]
            final.append({"text": text, "box": [[min(xs)+ox, min(ys)+oy],
                                                 [max(xs)+ox, max(ys)+oy]]})
        return final