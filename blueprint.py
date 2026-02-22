import tkinter as tk
from tkinter import filedialog
from PIL import Image, ImageTk
import json
import os

# 全局状态
current_image_path = None
current_annotations = []
current_project_file = None

def create_window(title="Annotation Tool", initial_width=1000, initial_height=600):
    root = tk.Tk()
    root.title(title)
    root.geometry(f"{initial_width}x{initial_height}")
    root.minsize(800, 500)
    return root

# 主布局设置
def setup_layout(root, canvas):
    # 左侧按钮区
    left_frame = tk.Frame(root, bg="lightgray", width=200)
    left_frame.pack(side=tk.LEFT, fill=tk.Y)
    left_frame.pack_propagate(False)

    # 项目管理按钮
    open_btn = tk.Button(
        left_frame, text="打开项目", font=("Arial", 11),
        command=lambda: open_project(canvas)
    )
    open_btn.pack(pady=10, padx=20, fill=tk.X)

    save_btn = tk.Button(
        left_frame, text="保存项目", font=("Arial", 11),
        command=lambda: save_project()
    )
    save_btn.pack(pady=5, padx=20, fill=tk.X)

    import_btn = tk.Button(
        left_frame, text="导入图片", font=("Arial", 12, "bold"),
        bg="steelblue", fg="white",
        command=lambda: import_new_image(canvas)
    )
    import_btn.pack(pady=15, padx=20, fill=tk.X)

    # 分隔线
    separator = tk.Frame(left_frame, height=2, bg="gray")
    separator.pack(fill=tk.X, pady=15)

    # 标注模式按钮
    identity_btn = tk.Button(left_frame, text="身份确认", font=("Arial", 11), command=lambda: select_mode("identity"))
    identity_btn.pack(pady=10, padx=20, fill=tk.X)

    link_btn = tk.Button(left_frame, text="跳转", font=("Arial", 11), command=lambda: select_mode("link"))
    link_btn.pack(pady=10, padx=20, fill=tk.X)

    # 右侧图片区
    right_frame = tk.Frame(root)
    right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

    canvas.configure(bg="white", highlightthickness=0)
    canvas.pack(fill=tk.BOTH, expand=True)

    return open_btn, save_btn, import_btn, identity_btn, link_btn

# 模式选择（占位）
current_mode = None
def select_mode(mode):
    global current_mode
    current_mode = mode
    print(f"当前标注模式: {mode}")

# 加载图片到画布（不带文件对话框）
def load_image_to_canvas(canvas, image_path):
    global current_image_path
    current_image_path = image_path

    img = Image.open(image_path)
    # 限制最大显示尺寸，防止超大图片
    max_size = (1200, 800)
    img.thumbnail(max_size, Image.Resampling.LANCZOS)

    photo = ImageTk.PhotoImage(img)

    # 清空画布（包括初始提示）
    canvas.delete("all")
    canvas.create_image(0, 0, anchor=tk.NW, image=photo)
    canvas.image = photo  # 保持引用

    # 调整窗口大小
    img_width, img_height = img.size
    root = canvas.winfo_toplevel()
    new_width = img_width + 200
    new_height = max(img_height, 600)
    root.geometry(f"{new_width}x{new_height}")

    print(f"已加载图片: {image_path}")

# 新导入图片（清空标注，视为新项目）
def import_new_image(canvas):
    global current_image_path, current_annotations, current_project_file
    image_path = filedialog.askopenfilename(
        title="选择图片",
        filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp *.gif")]
    )
    if not image_path:
        return

    load_image_to_canvas(canvas, image_path)
    current_annotations = []          # 清空旧标注
    current_project_file = None       # 新图片，需要重新保存项目
    print("新图片导入，旧标注已清空")

# 打开项目（加载 JSON + 图片 + 标注）
def open_project(canvas):
    json_path = filedialog.askopenfilename(
        title="打开项目文件",
        filetypes=[("JSON files", "*.json")]
    )
    if not json_path:
        return

    load_project(canvas, json_path)

# 加载项目核心逻辑
def load_project(canvas, json_path):
    global current_annotations, current_project_file, current_image_path
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        image_path = data.get('image_path')
        if not image_path or not os.path.exists(image_path):
            print("图片路径无效或文件不存在")
            return

        load_image_to_canvas(canvas, image_path)
        current_annotations = data.get('annotations', [])
        current_project_file = json_path

        # 后续在这里绘制已保存的矩形框
        print(f"项目加载成功: {json_path}")
    except Exception as e:
        print(f"加载项目失败: {e}")

# 保存项目（如果未保存过则另存为）
def save_project():
    global current_project_file
    if not current_image_path:
        print("没有加载图片，无法保存")
        return

    if current_project_file is None:
        save_as_project()
        return

    save_to_file(current_project_file)

# 另存为
def save_as_project():
    path = filedialog.asksaveasfilename(
        title="另存为项目文件",
        defaultextension=".json",
        filetypes=[("JSON files", "*.json")]
    )
    if not path:
        return

    save_to_file(path)
    global current_project_file
    current_project_file = path

# 实际写入文件并更新最近项目记录
def save_to_file(path):
    data = {
        'image_path': current_image_path,
        'annotations': current_annotations
    }
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"项目保存成功: {path}")

        # 更新最近打开记录（实现“下次打开自动加载”）
        config_file = 'config.json'
        config_data = {'last_project': path}
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=4)
    except Exception as e:
        print(f"保存失败: {e}")

if __name__ == "__main__":
    root = create_window()
    canvas = tk.Canvas(root)  # 先创建 canvas，后面传入

    # 自动加载上次保存的项目
    config_file = 'config.json'
    loaded = False
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            last_project = config.get('last_project')
            if last_project and os.path.exists(last_project):
                load_project(canvas, last_project)
                loaded = True
        except Exception as e:
            print(f"自动加载失败: {e}")

    # 设置布局
    setup_layout(root, canvas)

    # 如果没有自动加载成功，显示初始提示
    if not loaded:
        canvas.create_text(
            400, 300,
            text="请点击“打开项目”加载上次保存\n或“导入图片”开始新标注",
            font=("Arial", 16), fill="gray", tag="prompt"
        )

    root.mainloop()