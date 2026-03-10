

```markdown
# XYC 自动化工具

幸福小渔村多窗口自动化脚本，支持后台操作（SendMessage）、多窗口真并行、每日任务自动完成、领地搬运、换区管理。

## 功能

| 功能 | 说明 |
|------|------|
| 🖱️ 后台点击/拖拽 | SendMessage 发送消息，不占用鼠标 |
| 📸 后台截图 | PrintWindow 截图，窗口可被遮挡 |
| 🧵 多窗口并行 | 无锁真并行，每个窗口独立线程 |
| 📋 每日任务 | 商店/签到/转盘/排行/道具/日常，自动跳过已完成 |
| 🚚 领地搬运 | YOLO 识别资源 → 分配海兽 → 观看海鸟 |
| 🔄 换区支持 | 多大区自动切换，每日记录按区独立 |
| 🎮 GUI 控制台 | tkinter 界面，选择任务/启停/查看日志 |
| ⌨️ 热键控制 | F9 暂停/恢复，F10 停止 |

## 目录结构

```
XYC/
├── main.py                     # 入口
├── config/                     # 配置文件
│   ├── settings.yaml           #   全局设置
│   ├── accounts.yaml           #   账号-大区映射
│   ├── task_policy.yaml        #   任务策略
│   └── paths.yaml              #   模板图片路径注册
├── core/                       # 核心引擎
│   ├── operator.py             #   操作器（SendMessage/pyautogui）
│   ├── vision.py               #   视觉识别（YOLO/模板匹配/OCR）
│   ├── screen_capture.py       #   截图（mss/PrintWindow）
│   ├── state_manager.py        #   状态机 + 页面导航
│   ├── config_loader.py        #   配置加载
│   └── logger.py               #   日志
├── window/                     # 窗口管理
│   ├── window_manager.py       #   单窗口
│   └── window_group.py         #   多窗口组
├── scheduler/                  # 调度层
│   ├── task_scheduler.py       #   任务调度器
│   ├── daily_tracker.py        #   每日完成记录
│   ├── region_manager.py       #   换区管理
│   └── loop_controller.py      #   循环控制
├── tasks/                      # 任务实现
│   ├── base_task.py            #   任务基类
│   ├── ad_handler.py           #   广告处理
│   ├── daily/                  #   每日任务
│   │   ├── shop.py
│   │   ├── checkin.py
│   │   ├── zhp.py
│   │   ├── ranking.py
│   │   ├── daoju.py
│   │   └── richang.py
│   ├── transport/              #   领地搬运
│   │   ├── transport_task.py
│   │   ├── lingdi_detect.py
│   │   ├── bird_handler.py
│   │   ├── caini_handler.py
│   │   └── refresh_strategy.py
│   └── explore/                #   探秘（待实现）
│       └── explore_task.py
├── parallel/                   # 并行管理
│   └── multi_runner.py
├── gui/                        # 界面
│   ├── main_window.py
│   ├── task_panel.py
│   └── log_viewer.py
├── templates/                  # 模板图片
├── models/                     # YOLO 模型
├── data/                       # 运行时数据
└── logs/                       # 日志
```

## 安装

### 环境要求

- Windows 10/11
- Python 3.8+

### 依赖安装

```bash
pip install -r requirements.txt
```

### requirements.txt

```
numpy
opencv-python
pyautogui
pygetwindow
pywin32
mss
torch
pyyaml
keyboard
```

### YOLO 模型

将训练好的 `best.pt` 放到 `models/` 目录。

### 边框标注

用 [labelme](https://github.com/wkentaro/labelme) 标注窗口内容区域，保存为 `window/true_window.json`：

1. 截取完整窗口截图
2. 用 labelme 框选**去掉标题栏和边框**的内容区域
3. 保存 JSON

## 快速开始

### 1. GUI 模式（推荐）

```bash
python main.py
```

界面操作：
1. 输入窗口标题 → 点击「扫描窗口」
2. 勾选要执行的任务
3. 设置循环次数
4. 点击「启动」

### 2. 命令行模式

```python
from parallel.multi_runner import MultiRunner
from tasks.daily.shop import ShopTask
from tasks.transport.transport_task import TransportTask

runner = MultiRunner("幸福小渔村")
runner.run(
    selected_tasks=[ShopTask, TransportTask],
    enable_loop=True,
    max_rounds=100,
)
```

### 3. 单窗口调试

```python
from core.operator import Operator
from core.vision import MyVision

op = Operator("幸福小渔村", use_sendmsg=True)
img = op.capture()                      # 后台截图
op.click([[0.5, 0.5], [0.6, 0.6]])     # 后台点击

vision = MyVision()
result = vision.find_image(img, "templates/daily/shangdian.png")
if result:
    op.click(result)
```

## 配置说明

### config/settings.yaml

```yaml
window:
  title: "幸福小渔村"              # 窗口标题
  true_window_json: "window/true_window.json"  # 边框标注

capture:
  use_sendmsg: true                # true=后台操作  false=前台pyautogui
```

### config/task_policy.yaml

```yaml
transport:
  refresh:
    ad_limit_per_day: 2            # 广告刷新每日上限
    card_cost_threshold: 3         # 刷新卡消耗阈值
    card_min_reserve: 5            # 刷新卡最低保留
```

### config/paths.yaml

所有模板图片路径集中注册，任务代码中不写死路径：

```yaml
daily:
  shop:
    collect: "templates/daily/shangdian.png"
```

任务中引用：

```python
path = self.P("daily.shop.collect")  # → "templates/daily/shangdian.png"
```

### config/accounts.yaml

多账号换区配置：

```yaml
accounts:
  - name: "account_0"
    regions: ["大区A", "大区B", "大区C"]
```

## 操作模式

### SendMessage 模式（默认）

- ✅ 真并行，无鼠标锁
- ✅ 窗口可被遮挡
- ✅ 不占用鼠标
- ⚠️ 极少数应用不支持

### pyautogui 模式

- ✅ 兼容所有应用
- ❌ 需要窗口可见
- ❌ 占用鼠标
- ❌ 多窗口需加锁串行

切换方式：`settings.yaml` 中 `use_sendmsg: false`

## 添加新任务

### 1. 创建任务文件

```python
# tasks/daily/my_task.py
from tasks.base_task import BaseTask

class MyTask(BaseTask):
    TASK_NAME = "my_task"      # 唯一标识
    IS_DAILY = True            # True=每日任务（完成后跳过）

    def run(self):
        self.mgr.navigate_to("target_page")
        
        # 用 paths.yaml 中注册的路径
        if self.secten("daily.my_task.check"):
            self.op.click_json(self.P("daily.my_task.button"))
        
        self.mgr.navigate_to("zhuye")
        self.log.info("✅ 完成")
```

### 2. 注册模板路径

```yaml
# config/paths.yaml
daily:
  my_task:
    check: "templates/daily/my_check.png"
    button: "templates/daily/my_button.png"
```

### 3. 注册到 GUI

```python
# gui/task_panel.py 的 TASK_REGISTRY 列表添加：
("我的任务", "daily", "tasks.daily.my_task", "MyTask"),
```

## 模板图片制作

1. 用 `op.capture("screenshot.png")` 截取当前画面
2. 用 labelme 标注目标区域，保存同名 JSON
3. 放到 `templates/` 对应目录

```
templates/daily/
├── shangdian.png       # 截图
└── shangdian.json      # labelme 标注（框选目标元素）
```

## 热键

| 按键 | 功能 |
|------|------|
| F9 | 暂停 / 恢复 |
| F10 | 停止所有任务 |

## 调度逻辑

```
每轮循环:
  每个大区:
    每日任务:
      已完成? → 跳过
      未完成? → 执行 → 标记完成
    循环任务:
      每轮都执行（搬运/探秘）
  换区 → 下一个大区
下一轮
```

每日完成记录存储在 `data/daily_log/{account}_{region}_{date}.json`，次日自动重置。

## 常见问题

### 后台截图全黑

部分硬件加速渲染的窗口不支持 `PrintWindow`。解决：
- `settings.yaml` 中改 `use_sendmsg: false`
- 或关闭游戏的硬件加速

### 点击没反应

1. 检查 `window/true_window.json` 边框标注是否正确
2. 确认窗口标题匹配
3. 单窗口调试：`op.click([[0.5, 0.5], [0.6, 0.6]])` 测试

### 模板匹配失败

1. 窗口大小变化后需要重新截图或依赖多尺度匹配
2. 可在 `templates/transport/rimges/` 添加多个 size 目录
3. 调低阈值：`secten("key", threshold=0.6)`

### 多窗口乱点

确保使用 `use_sendmsg: true`（默认）。pyautogui 模式下多窗口需要鼠标锁。
```