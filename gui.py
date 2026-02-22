import tkinter as tk
from tkinter import ttk, messagebox
import pygetwindow as gw
import os
import win32gui
from PIL import ImageGrab 
from controller import GameController

class FishingVillageGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("幸福小渔村自动化辅助")
        self.root.geometry("850x650")
        
        # 初始化控制器
        self.ctrl = GameController(self.update_row_status)
        self.hwnd_to_item = {}

        # 1. 创建选项卡容器
        self.tab_control = ttk.Notebook(root)
        
        # 2. 初始化各个标签页
        self.tab_territory = ttk.Frame(self.tab_control)
        self.tab_process = ttk.Frame(self.tab_control)
        
        self.tab_control.add(self.tab_territory, text='领地管理')
        self.tab_control.add(self.tab_process, text='进程管理')
        self.tab_control.pack(expand=1, fill="both")

        # 3. 填充页面内容
        self.setup_territory_ui()
        self.setup_process_tab()
        self.setup_bottom_bar()

        # 自动刷新并默认选中
        self.root.after(500, self._initial_selection)

    def _initial_selection(self):
        self.refresh_list()
        children = self.tree.get_children()
        if children:
            self.tree.selection_set(children[0]) # 默认选中第一个
            self.tree.focus(children[0])

    # ... [setup_territory_ui 和 setup_process_tab 保持不变] ...

    def setup_territory_ui(self):
        """仅保留任务选项，删除按钮，通过 F10/F12 触发"""
        container = ttk.Frame(self.tab_territory, padding="20")
        container.pack(fill="both", expand=True)

        # 初始化变量（如果 __init__ 没定义则补全）
        if not hasattr(self, 'var_loop_windows'): self.var_loop_windows = tk.BooleanVar(value=True)
        if not hasattr(self, 'var_task_move'): self.var_task_move = tk.BooleanVar(value=True)
        if not hasattr(self, 'var_task_clay'): self.var_task_clay = tk.BooleanVar(value=False)
        if not hasattr(self, 'var_task_bird'): self.var_task_bird = tk.BooleanVar(value=True)

        # 运行模式
        mode_frame = ttk.LabelFrame(container, text=" 运行模式 (快捷键: F10启动 / F12停止) ", padding="10")
        mode_frame.pack(fill="x", pady=5)
        ttk.Checkbutton(mode_frame, text="🔄 循环切换窗口任务 (未勾选则仅执行当前选中窗口)", 
                        variable=self.var_loop_windows).pack(anchor="w")

        # 任务清单
        task_frame = ttk.LabelFrame(container, text=" 自动化任务清单 ", padding="10")
        task_frame.pack(fill="x", pady=10)
        ttk.Checkbutton(task_frame, text="📦 搬运领地物资", variable=self.var_task_move).pack(anchor="w", pady=5)
        ttk.Checkbutton(task_frame, text="💎 自动获得彩泥", variable=self.var_task_clay).pack(anchor="w", pady=5)
        ttk.Checkbutton(task_frame, text="🦅 自动观看飞鸟", variable=self.var_task_bird).pack(anchor="w", pady=5)

        # 提示文本
        ttk.Label(container, text="提示：程序启动后会自动同步窗口大小", foreground="gray").pack(pady=10)

        # 绑定快捷键
        self.root.bind("<F10>", lambda e: self.start_automation())
        self.root.bind("<F12>", lambda e: self.stop_automation())

    def start_automation(self):
        """F10 触发的逻辑"""
        # 1. 刷新并获取窗口
        windows = self.refresh_list()
        if not windows:
            return

        # 2. 自动同步窗口大小 (调用你 controller 中的方法或系统指令)
        # 假设同步逻辑是置顶并调整，这里可以先让 controller 处理
        
        # 3. 确定操作目标
        if self.var_loop_windows.get():
            target_windows = windows
        else:
            # 如果没手动选，默认取第一个
            selected = self.tree.selection()
            if selected:
                hwnd = int(self.tree.item(selected[0], "values")[2])
                target_windows = [w for w in windows if w._hWnd == hwnd]
            else:
                target_windows = [windows[0]]
                self.tree.selection_set(self.tree.get_children()[0]) # UI上也选中第一个

        # 4. 封装任务配置
        config = {
            "tasks": {
                "move": self.var_task_move.get(),
                "clay": self.var_task_clay.get(),
                "bird": self.var_task_bird.get()
            }
        }

        # 5. 启动 (通知 controller 自动同步大小并开始)
        print("F10 已触发，启动任务...")
        self.ctrl.start_loop(target_windows, config)

    def stop_automation(self):
        """F12 触发的逻辑"""
        print("F12 已触发，中止任务")
        self.ctrl.stop_loop()


    def setup_process_tab(self):
        """进程管理布局"""
        frame = ttk.Frame(self.tab_process)
        frame.pack(expand=1, fill="both")
        tk.Label(frame, text="双击下方列表项可直接弹出对应游戏窗口", fg="#666").pack(pady=5)
        columns = ("idx", "title", "hwnd", "status")
        self.tree = ttk.Treeview(frame, columns=columns, show='headings')
        self.tree.heading("idx", text="序号")
        self.tree.heading("title", text="窗口标题")
        self.tree.heading("hwnd", text="句柄(HWND)")
        self.tree.heading("status", text="当前状态")
        self.tree.column("idx", width=50, anchor="center")
        self.tree.column("title", width=250)
        self.tree.column("hwnd", width=120, anchor="center")
        self.tree.tag_configure('active_row', background='#C1FFC1')
        self.tree.pack(expand=1, fill="both", padx=10, pady=10)
        self.tree.bind("<Double-1>", self.on_double_click)

    def setup_bottom_bar(self):
        """底部控制按钮"""
        bar = tk.Frame(self.root)
        bar.pack(side="bottom", fill="x", pady=10)
        
        tk.Button(bar, text="刷新窗口列表", command=self.refresh_list).pack(side="left", padx=10)
        
        # --- 新增：同步窗口大小按钮 ---
        tk.Button(bar, text="同步窗口大小", command=self.on_sync_size_click, bg="#d1e7dd").pack(side="left", padx=10)
        
        tk.Button(bar, text="手动截图", command=self.on_manual_screenshot, bg="#e1e1e1").pack(side="left", padx=10)
        
        self.run_btn = tk.Button(bar, text="启动 F10", bg="green", fg="white", width=12, command=self.run_script)
        self.run_btn.pack(side="left", padx=10)
        tk.Button(bar, text="中止 F12", bg="red", fg="white", width=12, command=self.stop_script).pack(side="left", padx=10)

    def on_sync_size_click(self):
        """根据 window/001.png 的尺寸调整选中窗口的大小"""
        # 1. 检查基准图片是否存在
        ref_path = "./window/001.png"
        if not os.path.exists(ref_path):
            return messagebox.showerror("错误", f"未找到基准图片：{ref_path}\n请先在该目录下放入标尺图。")

        # 2. 获取图片尺寸
        try:
            from PIL import Image
            with Image.open(ref_path) as img:
                target_w, target_h = img.size
            print(f"📏 基准尺寸已加载: {target_w}x{target_h}")
        except Exception as e:
            return messagebox.showerror("错误", f"读取基准图失败: {e}")

        # 3. 获取 Treeview 选中的窗口句柄
        sel = self.tree.selection()
        if not sel:
            return messagebox.showwarning("提示", "请先在列表中选中一个或多个窗口")

        success_count = 0
        for item in sel:
            hwnd = int(self.tree.item(item, "values")[2])
            
            if win32gui.IsWindow(hwnd):
                # 获取当前窗口位置 (x, y)
                rect = win32gui.GetWindowRect(hwnd)
                curr_x, curr_y = rect[0], rect[1]

                # 调整窗口大小
                # SWP_NOMOVE: 保持当前位置
                # SWP_NOZORDER: 保持当前的 Z 顺序
                import win32con
                win32gui.SetWindowPos(
                    hwnd, 
                    win32con.HWND_TOP, 
                    curr_x, curr_y, target_w, target_h, 
                    win32con.SWP_NOMOVE | win32con.SWP_NOZORDER
                )
                success_count += 1
        
        print(f"✅ 已同步 {success_count} 个窗口的大小")




    # --- 新增的截图逻辑函数 ---
    def on_manual_screenshot(self):
        """截取当前 Treeview 选中的窗口"""
        sel = self.tree.selection()
        if not sel:
            return messagebox.showwarning("提示", "请先在列表中选中一个窗口")

        hwnd = int(self.tree.item(sel[0], "values")[2])
        
        # 1. 自动命名逻辑
        save_dir = "./screenshots"
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)

        index = 1
        while True:
            file_path = os.path.join(save_dir, f"{index:03d}.png")
            if not os.path.exists(file_path):
                break
            index += 1

        # 2. 截图操作
        try:
            if win32gui.IsWindow(hwnd):
                # 弹出并置顶
                self.ctrl.force_focus(hwnd) 
                self.root.after(200) # 等待 200ms 确保窗口完全渲染出来
                
                # 获取坐标并截图
                rect = win32gui.GetWindowRect(hwnd)
                img = ImageGrab.grab(bbox=rect)
                img.save(file_path)
                print(f"✅ 截图已保存: {file_path}")
            else:
                messagebox.showerror("错误", "窗口句柄已失效")
        except Exception as e:
            messagebox.showerror("截图失败", f"原因: {e}")

    # ... [refresh_list, update_row_status 等后续方法保持不变] ...
    def refresh_list(self):
        self.tree.delete(*self.tree.get_children())
        self.hwnd_to_item = {}
        windows = [w for w in gw.getAllWindows() if w.title == "幸福小渔村"]
        for i, win in enumerate(windows):
            item_id = self.tree.insert("", "end", values=(i+1, win.title, win._hWnd, "已就绪"))
            self.hwnd_to_item[win._hWnd] = item_id
        return windows

    def update_row_status(self, hwnd, status, is_active):
        if hwnd in self.hwnd_to_item:
            item_id = self.hwnd_to_item[hwnd]
            vals = list(self.tree.item(item_id, "values"))
            vals[3] = status
            self.root.after(0, lambda: self.tree.item(item_id, values=vals, tags=('active_row' if is_active else '')))
            if is_active: self.root.after(0, lambda: self.tree.see(item_id))

    def on_double_click(self, event):
        sel = self.tree.selection()
        if sel:
            hwnd = int(self.tree.item(sel[0], "values")[2])
            self.ctrl.force_focus(hwnd)

    def run_script(self):
        wins = self.refresh_list()
        if not wins: return messagebox.showwarning("警告", "未发现游戏窗口")
        self.run_btn.config(state="disabled", text="运行中...")
        self.ctrl.start_loop(wins)

    def stop_script(self):
        self.ctrl.stop_loop()
        self.run_btn.config(state="normal", text="启动 F10")