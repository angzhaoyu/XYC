import cv2
import numpy as np
import os
import json
import torch
from pathlib import Path
from core.config_loader import settings


class MyVision:
    def __init__(self, yolo_model_path=None, true_window_json=None):
        cfg = settings()
        self.yolo_model_path = yolo_model_path or cfg.get("yolo", {}).get("model_path", "models/best.pt")
        true_json = true_window_json or cfg.get("window", {}).get("true_window_json", "window/true_window.json")
        self.model = None
        self.ocr_reader = None

        self.borders = {'left': 0, 'top': 0, 'right': 0, 'bottom': 0}
        self._load_borders(true_json)

    def _load_borders(self, json_path):
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
                    'left': int(pts[0][0]), 'top': int(pts[0][1]),
                    'right': int(iw - pts[1][0]), 'bottom': int(ih - pts[1][1]),
                }
        except Exception:
            pass

    def _calc_content_scale(self, img_current, img_template):
        h1, w1 = img_current.shape[:2]
        h2, w2 = img_template.shape[:2]
        b = self.borders
        ocw = w2 - b['left'] - b['right']
        och = h2 - b['top'] - b['bottom']
        ccw = w1 - b['left'] - b['right']
        cch = h1 - b['top'] - b['bottom']
        if ocw > 0 and och > 0:
            return ccw / ocw, cch / och
        return 1.0, 1.0


    def limit_scope(self, image_path, scale=1.0):
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
            # 没有边框就用整图
            cw, ch = w, h
            x1 = points[0][0] / cw
            y1 = points[0][1] / ch
            x2 = points[1][0] / cw
            y2 = points[1][1] / ch
        else:
            x1 = max(0, (points[0][0] - b['left']) / cw)
            y1 = max(0, (points[0][1] - b['top'])  / ch)
            x2 = min(1, (points[1][0] - b['left']) / cw)
            y2 = min(1, (points[1][1] - b['top'])  / ch)

        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        rw, rh = (x2 - x1) * scale, (y2 - y1) * scale
        return [[max(0.0, cx - rw/2), max(0.0, cy - rh/2)],
                [min(1.0, cx + rw/2), min(1.0, cy + rh/2)]]


    def find_image(self, img1_input, img2_input, a_percentage=None, threshold=0.8):
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

        sx, sy = self._calc_content_scale(img1, img2_full)
        h_tpl, w_tpl = img2_roi.shape[:2]
        h_roi, w_roi = roi_img1.shape[:2]

        best_val = -1
        best_loc = None
        best_w, best_h = w_tpl, h_tpl

        scale_list = [(sx, sy), (1.0, 1.0)]
        for off in [0.95, 0.97, 1.03, 1.05]:
            scale_list.append((sx * off, sy * off))

        for s_x, s_y in scale_list:
            nw = max(1, int(w_tpl * s_x))
            nh = max(1, int(h_tpl * s_y))
            if nw >= w_roi or nh >= h_roi or nw < 3 or nh < 3:
                continue
            interp = cv2.INTER_AREA if s_x < 1 else cv2.INTER_LINEAR
            resized = cv2.resize(img2_roi, (nw, nh), interpolation=interp)
            try:
                res = cv2.matchTemplate(roi_img1, resized, cv2.TM_CCOEFF_NORMED)
                _, mv, _, ml = cv2.minMaxLoc(res)
                if mv > best_val:
                    best_val = mv
                    best_loc = ml
                    best_w, best_h = nw, nh
            except Exception:
                continue

        if best_val > threshold and best_loc is not None:
            return [[float(best_loc[0] + ox), float(best_loc[1] + oy)],
                    [float(best_loc[0] + best_w + ox), float(best_loc[1] + best_h + oy)]]
        return None

    def match_score(self, img1_input, img2_input, a_percentage=None):
        img1 = self._load(img1_input) if not isinstance(img1_input, np.ndarray) else img1_input
        img2_full = self._load(img2_input)
        if img1 is None or img2_full is None:
            return -1
        roi, _ = self._get_roi(img1, a_percentage)
        tpl = self._get_template_roi(img2_input, img2_full)
        if len(roi.shape) != len(tpl.shape):
            if len(roi.shape) == 3:
                tpl = cv2.cvtColor(tpl, cv2.COLOR_GRAY2BGR)
            else:
                roi = cv2.cvtColor(roi, cv2.COLOR_GRAY2BGR)
        roi = np.ascontiguousarray(roi.astype(np.uint8))
        tpl = np.ascontiguousarray(tpl.astype(np.uint8))
        sx, sy = self._calc_content_scale(img1, img2_full)
        h_t, w_t = tpl.shape[:2]
        nw = max(1, int(w_t * sx))
        nh = max(1, int(h_t * sy))
        if abs(sx - 1.0) > 0.01 or abs(sy - 1.0) > 0.01:
            interp = cv2.INTER_AREA if sx < 1 else cv2.INTER_LINEAR
            tpl = cv2.resize(tpl, (nw, nh), interpolation=interp)
        h_roi, w_roi = roi.shape[:2]
        if nw >= w_roi or nh >= h_roi:
            return -1
        try:
            res = cv2.matchTemplate(roi, tpl, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(res)
            return max_val
        except Exception:
            return -1

    def _load_yolo_model(self):
        if self.model is None and os.path.exists(self.yolo_model_path):
            self.model = torch.hub.load('ultralytics/yolov5', 'custom',
                                        path=self.yolo_model_path, device='cpu')

    def detect_yolo(self, img_input, a_percentage=None):
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
        x1 = int(min(p[0] for p in points))
        y1 = int(min(p[1] for p in points))
        x2 = int(max(p[0] for p in points))
        y2 = int(max(p[1] for p in points))
        return img_data[y1:y2, x1:x2]

    def _get_roi(self, img, a_perc):
        if not a_perc:
            return img, (0, 0)
        h, w = img.shape[:2]
        x1, y1 = int(a_perc[0][0]*w), int(a_perc[0][1]*h)
        x2, y2 = int(a_perc[1][0]*w), int(a_perc[1][1]*h)
        return img[y1:y2, x1:x2], (x1, y1)
    

    def _find_best_size_template(self, template_path, current_img):
        """
        检查模板路径所在目录是否有 size1/ size2/ 等兄弟目录
        如果有，根据当前截图尺寸选择最匹配的模板
        
        返回: 最佳模板路径列表（可能1个或2个）
        """
        p = Path(template_path)
        parent = p.parent
        filename = p.name

        # 检查是否在 sizeN 目录下
        if not parent.name.startswith("size"):
            # 不在 size 目录，检查同级是否有 size 子目录
            size_dirs = sorted([
                d for d in parent.iterdir()
                if d.is_dir() and d.name.startswith("size") and (d / filename).exists()
            ])
            if not size_dirs:
                return [template_path]  # 无多尺寸，用原始
        else:
            # 已在 sizeN 目录，查找兄弟 size 目录
            grandparent = parent.parent
            size_dirs = sorted([
                d for d in grandparent.iterdir()
                if d.is_dir() and d.name.startswith("size") and (d / filename).exists()
            ])
            if not size_dirs:
                return [template_path]

        # 计算每个 size 模板的内容区域宽度
        h_cur, w_cur = current_img.shape[:2]
        b = self.borders
        cur_cw = w_cur - b['left'] - b['right']

        candidates = []
        for d in size_dirs:
            tpl_path = str(d / filename)
            tpl_img = self._load(tpl_path)
            if tpl_img is None:
                continue
            tpl_cw = tpl_img.shape[1] - b['left'] - b['right']
            ratio = cur_cw / tpl_cw if tpl_cw > 0 else 999
            diff = abs(ratio - 1.0)  # 越接近1.0越好
            candidates.append((tpl_path, diff, ratio))

        if not candidates:
            return [template_path]

        candidates.sort(key=lambda x: x[1])

        # 最佳匹配
        best = candidates[0]

        # 如果最佳很接近（<5%差异），只用最佳
        if best[1] < 0.05:
            return [best[0]]

        # 如果有第二候选且差距不大（都在20%以内），两个都试
        if len(candidates) >= 2:
            second = candidates[1]
            if best[1] < 0.2 and second[1] < 0.2:
                return [best[0], second[0]]

        return [best[0]]


    def find_image_multi(self, img1_input, img2_input, a_percentage=None, threshold=0.8):
        """
        ★ 多尺寸 find_image：自动选择最匹配的模板尺寸
        """
        img1 = self._load(img1_input) if not isinstance(img1_input, np.ndarray) else img1_input
        if img1 is None:
            return None

        img2_path = str(img2_input) if isinstance(img2_input, (str, Path)) else img2_input

        # 获取最佳模板路径（可能多个）
        if isinstance(img2_path, str):
            best_paths = self._find_best_size_template(img2_path, img1)
        else:
            best_paths = [img2_path]

        best_result = None
        best_score = -1

        for tpl_path in best_paths:
            result = self.find_image(img1, tpl_path, a_percentage=a_percentage, threshold=threshold)
            if result:
                # 获取该匹配的分数
                score = self.match_score(img1, tpl_path, a_percentage=a_percentage)
                if score > best_score:
                    best_score = score
                    best_result = result

        return best_result


    def match_score_multi(self, img1_input, img2_input, a_percentage=None):
        """
        ★ 多尺寸 match_score
        """
        img1 = self._load(img1_input) if not isinstance(img1_input, np.ndarray) else img1_input
        if img1 is None:
            return -1

        img2_path = str(img2_input) if isinstance(img2_input, (str, Path)) else img2_input

        if isinstance(img2_path, str):
            best_paths = self._find_best_size_template(img2_path, img1)
        else:
            best_paths = [img2_path]

        best_score = -1
        for tpl_path in best_paths:
            score = self.match_score(img1, tpl_path, a_percentage=a_percentage)
            if score > best_score:
                best_score = score

        return best_score