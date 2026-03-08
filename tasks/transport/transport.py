import time
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

from tools.vision import MyVision
from tools.operate import Operator
from tasks.get_states import StateManager
from tasks.transport.lingdi_detect import LingdiDetector
from tasks.transport.bird import BirdTask
from tasks.transport.caini import CainiTask



class TransportTask:
    def __init__(self, app_name=None):
        self.vision = MyVision(yolo_model_path="models/best.pt")
        self.mgr = StateManager("tasks/states/states.txt", app_name=app_name)
        self.op = Operator(app_name)

        # 三个子模块
        self.det = LingdiDetector(self.vision, self.op)
        self.bird_task = BirdTask(self.op, self.mgr, self.det)
        self.caini_task = CainiTask(self.op, self.mgr, self.det)

    # ========== 选择海兽 ==========

    def choose_beast(self):
        print("开始选择海兽")
        MAX_RETRY = 5

        for attempt in range(MAX_RETRY):
            self.mgr.navigate_to('lingdi')
            n_res = self.det.res0
            print(f"资源数量: {n_res}")

            if n_res == 0:
                return None
            if self.det.xian is not None and self.det.xian == 0:
                return None

            self.mgr.get_states()
            if self.det.resource:
                self.op.click(self.det.resource[0])
            else:
                return None

            time.sleep(0.5)
            self.mgr.get_states()
            self.mgr.states_change("caiji_shangzhen_01")
            state = self.mgr.get_states()

            if state == 'shangzhen':
                print("开始识别海兽数量")
                self.det.I_beasts()

                if self.det.chose == 0 and self.det.xian == 0:
                    self.mgr.states_change("shangzhen_lingdi_01")
                    return None

                n_sz = (self.det.xian + self.det.chose) // n_res
                n_sz = max(n_sz, 1)
                n_sz = min(n_sz, self.det.shangxian)
                print(f"分配数量: {n_sz}个资源")

                if n_sz == 1:
                    pass
                elif n_sz <= self.det.shangxian:
                    for i in range(n_sz - 1):
                        if self.det.xian == 0:
                            break
                        path = f'tasks/transport/mouse_combo/00{i+2}.png'
                        print(f"点击路径: {path}")
                        self.mgr.get_states()
                        self.op.click_json(path)
                        self.det.xian -= 1
                elif n_sz > self.det.shangxian:
                    self.mgr.get_states()
                    self.op.click_json('tasks/transport/mouse_combo/yjsz.png')
                    self.det.xian -= self.det.shangxian + 1

                self.mgr.states_change("shangzhen_lingdi_02")
                print(f"完成选择海兽, 当前闲: {self.det.xian}")
                return
            else:
                print(f"⚠ 第{attempt+1}次未进入上阵界面，重试...")
                self.mgr.navigate_to('lingdi')
                self.mgr.states_change("shangzhen_lingdi_01")
                time.sleep(1)

        print("⚠ 达到最大重试次数，放弃选择海兽")

    # ========== 主流程 ==========

    def run(self):
        print("=" * 60, "\n🚀 开始运输任务")
        self.det.xian = None
        self.det.chose = None
        self.det.shangxian = None

        self.mgr.get_states()
        self.mgr.navigate_to("lingdi")
        self.det.I_resources()
        print(f"识别资源: {self.det.resource}")
        print(f"识别海鸟: {self.det.bird}")

        n_res = self.det.res0
        print(f"资源数量: {n_res}")

        while n_res > 0:
            print("开始选择海兽")
            self.choose_beast()
            print("完成一次选择")
            self.det.I_resources()
            n_res = self.det.res0
            if self.det.xian == 0:
                break

        try:
            if self.det.bird:
                if len(self.det.transport) + len(self.det.bird) != 6:
                    self.bird_task.run(choose_beast_fn=self.choose_beast)
        except Exception as e:
            print(f"❌ 异常: {e}")

        print("=" * 60)
""""""
if __name__ == "__main__":
    transport_task = TransportTask(app_name="幸福小渔村")
    transport_task.run()
