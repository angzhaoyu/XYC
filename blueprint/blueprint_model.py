"""
蓝图数据模型 - 支持多窗口尺寸
"""
import json
import shutil
from pathlib import Path


class Box:
    def __init__(self, label="", points=None, box_type="identity", target_page=None):
        self.label = label
        self.points = points or [[0, 0], [0, 0]]
        self.box_type = box_type
        self.target_page = target_page

    def to_dict(self):
        d = {"label": self.label, "points": self.points, "box_type": self.box_type}
        if self.box_type == "link":
            d["target_page"] = self.target_page
        return d

    @classmethod
    def from_dict(cls, data):
        return cls(
            label=data.get("label", ""),
            points=data.get("points", [[0, 0], [0, 0]]),
            box_type=data.get("box_type", "identity"),
            target_page=data.get("target_page"),
        )


class SizeVariant:
    """一种窗口尺寸的截图+标注"""
    def __init__(self, size_name="", image_path="", width=0, height=0,
                 borders=None):
        self.size_name = size_name       # 如 "1_3", "1_4"
        self.image_path = image_path
        self.width = width               # 截图宽
        self.height = height             # 截图高
        self.borders = borders or {'left': 0, 'top': 0, 'right': 0, 'bottom': 0}
        self.boxes = []                  # 该尺寸下的标注

    @property
    def content_width(self):
        return self.width - self.borders['left'] - self.borders['right']

    def to_dict(self):
        return {
            "size_name": self.size_name,
            "image": self.image_path,
            "width": self.width, "height": self.height,
            "borders": self.borders,
            "boxes": [b.to_dict() for b in self.boxes],
        }

    @classmethod
    def from_dict(cls, data):
        sv = cls(
            size_name=data.get("size_name", ""),
            image_path=data.get("image", ""),
            width=data.get("width", 0),
            height=data.get("height", 0),
            borders=data.get("borders"),
        )
        sv.boxes = [Box.from_dict(b) for b in data.get("boxes", [])]
        return sv


class Page:
    def __init__(self, page_id, name_cn="", name_en="", is_popup=False):
        self.page_id = page_id
        self.name_cn = name_cn
        self.name_en = name_en
        self.is_popup = is_popup
        self.variants = []       # ★ 多尺寸变体，第一个是显示用的
        self.boxes = []          # 兼容旧版：无多尺寸时的标注

    @property
    def display_name(self):
        return self.name_cn or self.name_en or self.page_id

    @property
    def primary_image(self):
        """第一个变体的图片路径"""
        if self.variants:
            return self.variants[0].image_path
        return ""

    def to_dict(self):
        d = {
            "name_cn": self.name_cn,
            "name_en": self.name_en,
            "is_popup": self.is_popup,
            "boxes": [b.to_dict() for b in self.boxes],
            "variants": [v.to_dict() for v in self.variants],
        }
        # 兼容：如果有旧的 image 字段
        if self.variants:
            d["image"] = self.variants[0].image_path
        return d

    @classmethod
    def from_dict(cls, page_id, data):
        p = cls(page_id,
                name_cn=data.get("name_cn", ""),
                name_en=data.get("name_en", ""),
                is_popup=data.get("is_popup", False))
        p.boxes = [Box.from_dict(b) for b in data.get("boxes", [])]
        p.variants = [SizeVariant.from_dict(v) for v in data.get("variants", [])]

        # 兼容旧版：没有 variants 但有 image
        if not p.variants and data.get("image"):
            sv = SizeVariant(size_name="default", image_path=data["image"])
            sv.boxes = list(p.boxes)
            p.variants.append(sv)

        return p


class BlueprintProject:
    def __init__(self, name, project_dir):
        self.name = name
        self.project_dir = Path(project_dir)
        self.pages = {}
        self._page_order = []

    @property
    def config_path(self):
        return self.project_dir / "project.json"

    @property
    def images_dir(self):
        return self.project_dir / "images"

    def create(self):
        self.project_dir.mkdir(parents=True, exist_ok=True)
        self.images_dir.mkdir(exist_ok=True)
        self.save()

    def save(self):
        data = {
            "project_name": self.name,
            "page_order": self._page_order,
            "pages": {pid: self.pages[pid].to_dict() for pid in self._page_order},
        }
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, project_dir):
        project_dir = Path(project_dir)
        with open(project_dir / "project.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        proj = cls(data["project_name"], project_dir)
        proj._page_order = data.get("page_order", [])
        for pid in proj._page_order:
            if pid in data.get("pages", {}):
                proj.pages[pid] = Page.from_dict(pid, data["pages"][pid])
        return proj

    def _gen_id(self):
        i = 1
        while f"page_{i:03d}" in self.pages:
            i += 1
        return f"page_{i:03d}"

    def import_image(self, source_path, size_name="default"):
        """导入图片，支持添加为新页面或现有页面的尺寸变体"""
        src = Path(source_path)
        pid = self._gen_id()
        dest = f"{pid}_{size_name}{src.suffix}"
        shutil.copy2(src, self.images_dir / dest)

        page = Page(pid, name_en=pid)
        sv = SizeVariant(size_name=size_name, image_path=f"images/{dest}")

        # 读取图片尺寸
        try:
            from PIL import Image as PILImage
            with PILImage.open(str(src)) as img:
                sv.width, sv.height = img.size
        except Exception:
            pass

        page.variants.append(sv)
        self.pages[pid] = page
        self._page_order.append(pid)
        return page

    def add_variant(self, page_id, source_path, size_name, borders=None):
        """给现有页面添加一个尺寸变体"""
        page = self.pages.get(page_id)
        if not page:
            return None

        src = Path(source_path)
        dest = f"{page_id}_{size_name}{src.suffix}"
        shutil.copy2(src, self.images_dir / dest)

        sv = SizeVariant(
            size_name=size_name,
            image_path=f"images/{dest}",
            borders=borders or {'left': 0, 'top': 0, 'right': 0, 'bottom': 0},
        )
        try:
            from PIL import Image as PILImage
            with PILImage.open(str(src)) as img:
                sv.width, sv.height = img.size
        except Exception:
            pass

        page.variants.append(sv)
        return sv

    def remove_page(self, page_id):
        if page_id not in self.pages:
            return
        page = self.pages[page_id]
        for sv in page.variants:
            img = self.project_dir / sv.image_path
            if img.exists():
                img.unlink()
        del self.pages[page_id]
        self._page_order.remove(page_id)

    def get_image_abs_path(self, page_id, variant_idx=0):
        page = self.pages.get(page_id)
        if page and page.variants and variant_idx < len(page.variants):
            return str(self.project_dir / page.variants[variant_idx].image_path)
        return None

    def get_page_names(self):
        return {pid: self.pages[pid].display_name for pid in self._page_order}