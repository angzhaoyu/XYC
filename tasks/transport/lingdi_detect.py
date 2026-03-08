import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
import os
import cv2
import numpy as np
# 注意数字范围：1-11（12 个数字）

class LingdiDetector:
    """领地识别：资源/海鸟/运输 + 海兽数量（模板匹配）"""

    RIMGES_DIR = "tasks/transport/rimges"

    def __init__(self, vision, op):
        self.vision = vision
        self.op = op

        # 识别结果
        self.resource = None
        self.res0 = None
        self.transport = None
        self.bird = None
        self.chose = None
        self.shangxian = None
        self.xian = None

    # ========== YOLO 资源识别 ==========

    def I_resources(self):
        resources, birds, transported = self._detect_yolo()
        self.res0 = len(resources)

        # 过滤与 bird 重叠的 resource
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

    # ========== 海兽数量识别（模板匹配替代 OCR）==========

    def _get_size_dirs(self):
        """扫描 rimges/ 下所有 size* 子目录，按名称排序"""
        base = Path(self.RIMGES_DIR)
        if not base.exists():
            return []
        dirs = sorted([d for d in base.iterdir() if d.is_dir() and d.name.startswith("size")])
        return dirs

    # ========== 海兽数量识别 ==========



    def I_beasts(self):
        screenshot = self.op.capture()

        self.chose     = self._match_number(screenshot, "chose",     range(0, 2))
        self.shangxian = self._match_number(screenshot, "shangxian", range(1, 12))
        self.xian      = self._match_number(screenshot, "xian",      range(0, 12))


        if self.xian != 0 and self.chose == 0:
            self.chose = 1

        print(f"当前选择: {self.chose}, 上限: {self.shangxian}, 闲: {self.xian}")

    def _match_number(self, screenshot, prefix, values):
        """遍历所有 size 目录 × 所有候选值，返回全局最高置信度的数值"""
        values = list(values)
        size_dirs = self._get_size_dirs()

        if not size_dirs:
            print(f"⚠️ 未找到 {self.RIMGES_DIR}/size* 目录")
            return 0

        # 1. 找搜索区域（用任意一个存在的模板）
        limit = None
        for d in size_dirs:
            for v in values:
                path = str(d / f"{prefix}_{v}.png")
                if os.path.exists(path):
                    limit = self.vision.limit_scope(path, scale=4)
                    break
            if limit is not None:
                break

        if limit is None:
            print(f"⚠️ 未找到 {prefix} 的模板文件")
            return 0

        # 2. 遍历所有 size × 所有 value
        best_conf = -1
        best_val = values[0]

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

        print(f"  {prefix} → {best_val} (conf={best_conf:.3f}, from={best_dir})")
        return best_val


    def _match_confidence(self, img_input, template_path, a_percentage=None):
        img1 = img_input if isinstance(img_input, np.ndarray) else self.vision._load(img_input)
        img2_full = self.vision._load(template_path)
        if img1 is None or img2_full is None:
            return -1

        roi, _ = self.vision._get_roi(img1, a_percentage)
        tpl = self.vision._get_template_roi(template_path, img2_full)

        # 格式对齐
        if len(roi.shape) != len(tpl.shape):
            if len(roi.shape) == 3:
                tpl = cv2.cvtColor(tpl, cv2.COLOR_GRAY2BGR)
            else:
                roi = cv2.cvtColor(roi, cv2.COLOR_GRAY2BGR)
        roi = np.ascontiguousarray(roi.astype(np.uint8))
        tpl = np.ascontiguousarray(tpl.astype(np.uint8))

        # 缩放模板（窗口大小可能变了）
        sx, sy = self.vision._calc_content_scale(img1, img2_full)
        h_t, w_t = tpl.shape[:2]
        new_w = max(1, int(w_t * sx))
        new_h = max(1, int(h_t * sy))

        if abs(sx - 1.0) > 0.01 or abs(sy - 1.0) > 0.01:
            interp = cv2.INTER_AREA if sx < 1 else cv2.INTER_LINEAR
            tpl = cv2.resize(tpl, (new_w, new_h), interpolation=interp)

        h_roi, w_roi = roi.shape[:2]
        if new_w >= w_roi or new_h >= h_roi or new_w < 3 or new_h < 3:
            return -1

        try:
            res = cv2.matchTemplate(roi, tpl, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(res)
            return max_val
        except Exception:
            return -1

    # ========== 通用查找 ==========

    def secten(self, path, scale=1):
        limit = self.vision.limit_scope(path, scale=scale)
        return self.vision.find_image(self.op.capture(), path, a_percentage=limit)
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))
from tools.vision import MyVision
from tools.operate import Operator
app_name = "幸福小渔村"
vision = MyVision(yolo_model_path="models/best.pt")
op = Operator(app_name)
det = LingdiDetector(vision, op)
det.I_beasts()
"""  