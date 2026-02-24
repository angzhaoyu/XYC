import sys
from pathlib import Path
# --- 路径适配 ---
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))
import operate
import vision
from tasks.get_states import StateManager



windows = operate.Operator.get_all_windows()

print(windows)
V = vision.MyVision(yolo_model_path="models/best.pt")

img = operate.Operator(app_name="幸福小渔村").capture()
def detect_num(img,limit_img):
    limit = V.limit_scope(limit_img, scale=1)
    date = V.detect_text(img, limit, n=16, math=True)
    #print("=="*30,date)
    if date:
        return int(date[0]['text'])
climit_img1 = "tasks/change-regions/shezhi_01.png"
climit_img2 = "tasks/change-regions/shezhi_02.png"
mgr = StateManager("tasks/states.txt", app_name="幸福小渔村")
mgr.navigate_to("shezhi")
current_region = [detect_num(img,climit_img1),detect_num(img,climit_img2)]
def detect_id(img,filter_path):
    for i in Path(filter_path).glob("*.png"):
        a = V.find_image(img, i, a_percentage=None)
        if a:
            return i.stem

filter_path = "tasks/change-regions/ID/"
current_id =  detect_id(img,filter_path)


print("=="*30,"\n",
      current_region , "\n",
      id
      )