import numpy as np
import cv2
import pyautogui

img = pyautogui.screenshot()
img_array = np.array(img)

# 方式1
img_bgr1 = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
cv2.imwrite('temp.png', img_bgr1)  # PNG无损
img_bgr1_file = cv2.imread('temp.png', cv2.IMREAD_COLOR)

# 方式2  
img_bgr2 = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

# 对比差异
diff = np.abs(img_bgr1_file.astype(np.float32) - img_bgr2.astype(np.float32))
print(f"最大差异: {np.max(diff)}")
print(f"平均差异: {np.mean(diff)}")
print(f"差异像素数: {np.sum(diff > 0)}")