# 该文件用于领取每日东西。
import sys
from pathlib import Path
# --- 路径适配 ---
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))
from tasks.get_states import StateManager
import tools.vision
import tools.operate
import time
import json

class DailyCollect:
    def __init__(self, app_name):
        self.mgr = StateManager("tasks/states.txt", app_name=app_name)
        self.vision = vision.MyVision(yolo_model_path="models/best.pt")
        self.op = operate.Operator(app_name=app_name)
    
    def shangdian(self):
        self.mgr.navigate_to("shangdian")
        shangdian_id = "tasks/daily-collect/shangdian.png"
        limit = self.vision.limit_scope(shangdian_id, scale=1.2)
        region =  self.vision.find_image(self.op.capture(), shangdian_id, a_percentage=limit)
        if region:
            self.op.click(region)
        self.mgr.navigate_to("zhuye")

    def qiandao(self):
        self.mgr.navigate_to("caidan")
        path = "tasks/daily-collect/qiandao_id.png"
        limit = self.vision.limit_scope(path, scale=1.2)
        region =  self.vision.find_image(self.op.capture(), path, a_percentage=limit)
        if region:
            self.mgr.navigate_to("qiandao")
            for i in range(1,8):
                self.op.click_json(f"tasks/daily-collect/qiandao_{i}.png")
        self.mgr.navigate_to("zhuye")

    def zhp(self):
        self.mgr.navigate_to("zhp")
        zhp1 = "tasks/daily-collect/zhp_1.png"
        zhp2 = "tasks/daily-collect/zhp_2.png"
        l = ["zhp", "caidan", "zhuye", "zhuanshi", "yuer"]
        self.mgr.navigate_to("zhp")
        if self.secten(zhp1):
            self.mgr.navigate_to("yuer")
            self.op.click_json("tasks/daily-collect/yuer.png")
            self.guanggao(zhp2,l)
        if self.secten(zhp2):
            self.mgr.navigate_to("zhuanshi")
            self.op.click_json("tasks/daily-collect/zhuanshi.png")
            self.guanggao(zhp2,l)
        self.mgr.navigate_to("zhuye")

    def paihang(self):
        limit = self.vision.limit_scope("tasks/daily-collect/paihang_02.png", scale=1)
        m_ = "tasks/daily-collect/paihang_01.png"
        into_p = "tasks/daily-collect/paihang_00.png"
        p = Path("tasks/daily-collect/paihang_02.png")
        if p.suffix.lower() in {".png", ".jpg", ".jpeg"}:
            p = p.with_suffix(".json")
        elif p.suffix == "":
            p = p.with_suffix(".json")
        data = json.load(open(p))
        box = data["shapes"][0]["points"]

        self.mgr.navigate_to("ycfrd")
        if self.secten("tasks/daily-collect/ycfrd_id.png"):
            self.op.click_json(into_p)
            print("进入排行，开始拖拽")
            time.sleep(1)
            self.op.drag( box, "up", duration=0.5)
            time.sleep(0.5)
            print("拖拽完成")
            region = self.vision.find_image(self.op.capture(), m_, a_percentage=limit)
            while region:
                self.op.click(region)
                self.op.click_json("tasks/page-change/ycfrd_szpfb_01.png")
                region = self.vision.find_image(self.op.capture(), m_, a_percentage=limit)
            self.op.click_json("tasks/page-change/ycfrd_szpfb_01.png")

        self.mgr.navigate_to("szpfb")
        if self.secten("tasks/daily-collect/szpfb_id.png"):
            self.op.click_json(into_p)
            time.sleep(1)
            self.op.drag( box, "up", duration=0.5)
            time.sleep(0.5)
            region = self.vision.find_image(self.op.capture(), m_, a_percentage=limit)
            while region:
                self.op.click(region)
                self.op.click_json("tasks/page-change/ycfrd_szpfb_01.png")
                region = self.vision.find_image(self.op.capture(), m_, a_percentage=limit)
            self.op.click_json("tasks/page-change/ycfrd_szpfb_01.png")    

        self.mgr.navigate_to("hszlb")
        if self.secten("tasks/daily-collect/hszlb_id.png"):
            self.op.click_json(into_p)
            time.sleep(1)
            self.op.drag( box, "up", duration=0.5)
            time.sleep(0.5)
            region = self.vision.find_image(self.op.capture(), m_, a_percentage=limit)
            while region:
                self.op.click(region)
                
                self.op.click_json("tasks/page-change/ycfrd_szpfb_01.png")
                region = self.vision.find_image(self.op.capture(), m_, a_percentage=limit)
            self.op.click_json("tasks/page-change/ycfrd_szpfb_01.png")      
        self.mgr.navigate_to("zhuye")

    def ld_paihang(self):
        limit = self.vision.limit_scope("tasks/daily-collect/paihang_02.png", scale=1)
        m_ = "tasks/daily-collect/paihang_01.png"
        into_p = "tasks/daily-collect/paihang_00.png"
        p = Path("tasks/daily-collect/paihang_02.png")
        if p.suffix.lower() in {".png", ".jpg", ".jpeg"}:
            p = p.with_suffix(".json")
        elif p.suffix == "":
            p = p.with_suffix(".json")
        data = json.load(open(p))
        box = data["shapes"][0]["points"]
        self.mgr.navigate_to("ldpaihang")
        if self.secten("tasks/daily-collect/szpfb_id.png"):
            self.op.click_json(into_p)
            print("进入排行，开始拖拽")
            time.sleep(1)
            self.op.drag( box, "up", duration=0.5)
            time.sleep(0.5)
            print("拖拽完成")
            region = self.vision.find_image(self.op.capture(), m_, a_percentage=limit)
            while region:
                self.op.click(region)
                self.op.click_json("tasks/page-change/ycfrd_szpfb_01.png")
                region = self.vision.find_image(self.op.capture(), m_, a_percentage=limit)
            self.op.click_json("tasks/page-change/ycfrd_szpfb_01.png")
        self.mgr.navigate_to("lingdi")

    def guanggao(self,path,l):
        "图片路径，窗口列表"
        state = self.mgr.get_states()
        if state not in l:
            pass
        self.op.click_json(path) #进入广告
        time.sleep(3)
        if self.mgr.get_states() not in l:
            time.sleep(35)
            for i in range(3):
                self.op.click_json("tasks/transport/mouse_combo/guanbi.png")
                time.sleep(1)
                state = self.mgr.get_states()
                if state is None:
                    self.op.click_json("tasks/transport/mouse_combo/guanbi.png")
                    time.sleep(0.5)
                    self.op.click_json("tasks/transport/mouse_combo/jixukan.png")
                    time.sleep(5)
                    self.op.click_json("tasks/transport/mouse_combo/guanbi.png")
        
    def secten(self,  path, scale=1):
        limit = self.vision.limit_scope(path, scale=scale)
        region =  self.vision.find_image(self.op.capture(), path, a_percentage=limit)
        return region

    def richang(self):
        self.mgr.navigate_to("sxklb")
        if self.secten("tasks/daily-collect/sllb_id.png"):
            self.op.click_json("tasks/daily-collect/sllb_id.png")
            self.op.click_json("tasks/daily-collect/sllb_id.png")
        self.mgr.navigate_to("fhlb")
        if self.secten("tasks/daily-collect/fhlb_id.png"):
            self.op.click_json("tasks/daily-collect/fhlb_id.png")
            self.op.click_json("tasks/daily-collect/fhlb_id.png")
        self.mgr.navigate_to("sclb")
        if self.secten("tasks/daily-collect/sxlb_id.png"):
            self.op.click_json("tasks/daily-collect/sxlb_id.png")
            self.op.click_json("tasks/daily-collect/sxlb_id.png")
        self.mgr.navigate_to("lingdi")

    def daoju(self):
        self.mgr.navigate_to("djsd")
        if self.secten("tasks/daily-collect/buy_01.png"):
            print("开始点击收集物品")
            self.op.click_json("tasks/daily-collect/buy_01.png")
            time.sleep(1)
            self.op.click_json("tasks/daily-collect/buy_02.png")
        l = ["djsd", "fhs", "sxk", "lingdi"]
        guankan = "tasks/daily-collect/zhuanshi.png"
        fhs = "tasks/daily-collect/fhs_id.png"

        for i in range(6):
            self.mgr.navigate_to("djsd")
            self.op.click_json(fhs)
            time.sleep(0.5)
            state = self.mgr.get_states()
            if  state == "fhs":
                self.guanggao(guankan,l) 
            else:
                break
        self.mgr.navigate_to("djsd")
        sxk = "tasks/daily-collect/sxk_id.png"
        self.op.click_json(sxk)

        for i in range(4):
            self.mgr.navigate_to("djsd")
            self.op.click_json(sxk)
            time.sleep(0.5)
            state = self.mgr.get_states()
            if  state == "sxk":
                self.guanggao(guankan,l) 
            else:
                break
        self.mgr.navigate_to("lingdi")



    def run(self):
        """"""
        self.shangdian()
        self.qiandao()
        self.zhp()
        self.paihang()
        self.ld_paihang()
        self.richang()
        #self.daoju()


        

'''
if __name__ == "__main__":
    dc = DailyCollect(app_name="幸福小渔村")
    dc.run()
'''    
