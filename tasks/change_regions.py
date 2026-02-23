import sys
from pathlib import Path
# --- 路径适配 ---
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))
import operate
import vision
from tasks.get_states import StateManager


img = operate.Operator(app_name="幸福小渔村").capture()
V = vision.MyVision(yolo_model_path="models/best.pt")

def detect_num(img,limit_img):
    limit = V.limit_scope(limit_img, scale=1)
    date = V.detect_text(img, limit, n=4, math=True)
    #print("=="*30,date)
    if date:
        return int(date[0]['text'])
climit_img1 = "tasks/change-regions/shezhi_01.png"
climit_img2 = "tasks/change-regions/shezhi_02.png"
mgr = StateManager("tasks/states.txt", app_name="幸福小渔村")
mgr.navigate_to("shezhi")
current_r = [detect_num(img,climit_img1),detect_num(img,climit_img2)]

mgr.navigate_to("fwq")
flimit_img1 = "tasks/change-regions/fwq_01.png"
flimit_img2 = "tasks/change-regions/fwq_02.png"
current_f1 = [detect_num(img,flimit_img1),detect_num(img,flimit_img2)]

flimit_img3 = "tasks/change-regions/fwq_03.png"
flimit_img4 = "tasks/change-regions/fwq_04.png"
current_f2 = [detect_num(img,flimit_img3),detect_num(img,flimit_img4)]

flimit_img5 = "tasks/change-regions/fwq_05.png"
flimit_img6 = "tasks/change-regions/fwq_06.png"
current_f3 = [detect_num(img,flimit_img5),detect_num(img,flimit_img6)]



print("=="*30,"\n",
      current_r , "\n",
      current_f1, "\n",
      current_f2, "\n",
      current_f3, "\n",
      )