import os
import cv2
import numpy as np
from pathlib import Path
from core.config_loader import paths


class LingdiDetector:
    def __init__(self, vision, op):
        self.vision = vision
        self.op = op
        self.RIMGES_DIR = paths("transport.rimges_dir")

        self.resource = None
        self.res0 = None
        self.transport = None
        self.bird = None
        self.chose = None
        self.shangxian = None
        self.xian = None

    def I_resources(self):
        resources, birds, transported = self._detect_yolo()
        self.res0 = len(resources)
        self.resource = [
            res for res in resources
            if not any(self._is_overlap(res, b) for b in birds)
        ]
        self.transport = transported
        self.bird = birds

    def _detect_yolo(self):
        img = self.op.capture()
        datas = self.vision.detect_yolo(img)
        resources, birds, transported = [], [], []
        if datas:
            for item in datas:
                name = item['name'].lower()
                box = item['box']
                if 'resource' in name:
                    resources.append(box)
                elif 'bird' in name:
                    birds.append(box)
                elif 'transport' in name:
                    transported.append(box)
        return resources, birds, transported

    @staticmethod
    def _is_overlap(box1, box2):
        x1a, y1a = box1[0]; x1b, y1b = box1[1]
        x2a, y2a = box2[0]; x2b, y2b = box2[1]
        return not (x1b < x2a or x1a > x2b or y1b < y2a or y1a > y2b)

    def I_beasts(self):
        screenshot = self.op.capture()
        self.chose     = self._match_number(screenshot, "chose",     range(0, 2))
        self.shangxian = self._match_number(screenshot, "shangxian", range(1, 7))
        self.xian      = self._match_number(screenshot, "xian",      range(0, 9))
        """ if self.xian != 0 and self.chose == 0:
            self.chose = 1"""
        print(f"chose={self.chose}, shangxian={self.shangxian}, xian={self.xian}")

    def _get_size_dirs(self):
        base = Path(self.RIMGES_DIR)
        if not base.exists():
            return []
        return sorted([d for d in base.iterdir() if d.is_dir() and d.name.startswith("size")])

    def _match_number(self, screenshot, prefix, values):
        values = list(values)
        size_dirs = self._get_size_dirs()
        if not size_dirs:
            return 0

        limit = None
        for d in size_dirs:
            for v in values:
                path = str(d / f"{prefix}_{v}.png")
                if os.path.exists(path):
                    limit = self.vision.limit_scope(path, scale=16)
                    break
            if limit:
                break
        if not limit:
            return 0

        best_conf = -1
        best_val = values[0]
        best_dir = ""

        for d in size_dirs:
            for v in values:
                path = str(d / f"{prefix}_{v}.png")
                if not os.path.exists(path):
                    continue
                conf = self._match_confidence(screenshot, path, limit)
                if conf > best_conf:
                    best_conf = conf
                    best_val = v
                    best_dir = d.name

        print(f"  {prefix} → {best_val} (conf={best_conf:.3f}, {best_dir})")
        return best_val

    def _match_confidence(self, img_input, template_path, a_percentage=None):
        img1 = img_input if isinstance(img_input, np.ndarray) else self.vision._load(img_input)
        img2_full = self.vision._load(template_path)
        if img1 is None or img2_full is None:
            return -1
        roi, _ = self.vision._get_roi(img1, a_percentage)
        tpl = self.vision._get_template_roi(template_path, img2_full)
        if len(roi.shape) != len(tpl.shape):
            if len(roi.shape) == 3:
                tpl = cv2.cvtColor(tpl, cv2.COLOR_GRAY2BGR)
            else:
                roi = cv2.cvtColor(roi, cv2.COLOR_GRAY2BGR)
        roi = np.ascontiguousarray(roi.astype(np.uint8))
        tpl = np.ascontiguousarray(tpl.astype(np.uint8))
        sx, sy = self.vision._calc_content_scale(img1, img2_full)
        h_t, w_t = tpl.shape[:2]
        nw = max(1, int(w_t * sx))
        nh = max(1, int(h_t * sy))
        if abs(sx - 1.0) > 0.01 or abs(sy - 1.0) > 0.01:
            interp = cv2.INTER_AREA if sx < 1 else cv2.INTER_LINEAR
            tpl = cv2.resize(tpl, (nw, nh), interpolation=interp)
        h_roi, w_roi = roi.shape[:2]
        if nw >= w_roi or nh >= h_roi or nw < 3 or nh < 3:
            return -1
        try:
            res = cv2.matchTemplate(roi, tpl, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(res)
            return max_val
        except Exception:
            return -1

    def secten(self, path, scale=1):
        limit = self.vision.limit_scope(path, scale=scale)
        return self.vision.find_image(self.op.capture(), path, a_percentage=limit)