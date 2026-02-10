


import pygetwindow as gw
import cv2
import numpy as np
from typing import Union, List, Optional, Dict, Tuple
import pyautogui
import os
import json

def check_coords(coord):
    coords = coord if isinstance(coord[0], list) else [coord]
    return all(0 <= x <= 1 and 0 <= y <= 1 for x, y in coords)

class CoordinateConverter:
    """坐标转换工具类，支持屏幕坐标和应用窗口坐标之间的转换，支持固定边框"""
    
    def __init__(self,
                 coord: Union[List[float], List[List[float]]], 
                 coord_type: str,
                 obj: Union[str, np.ndarray] = None,
                 json_path="F:\\DNF\\dnf-ai\\mission_group\\recognition\\kuangjia\\1.json",
                 ):
        """
        初始化坐标转换器
        
        Args:
            coord: 单个坐标[x,y]或多个坐标[[x1,y1],[x2,y2]]
            coord_type: 坐标类型 ('a_pixel', 'a_percentage', 's_pixel', 's_percentage')
                - a_pixel: 相对于窗口的像素坐标（包含边框）
                - a_percentage: 相对于内容区域的百分比（不包含边框）
                - s_pixel: 屏幕绝对像素坐标
                - s_percentage: 屏幕百分比坐标
            obj: 可以是图片路径(str)、cv图片(ndarray)或app名称(str)
            json_path: JSON配置文件路径，包含边框信息
        """
        self.screen_width, self.screen_height = pyautogui.size()
        self._original_coord = coord
        self._coord_type = coord_type.lower()
        self._is_single = not isinstance(coord[0], (list, tuple))
        
        if self._coord_type == 'a_percentage' or self._coord_type == 's_percentage':
            if check_coords(coord) == False:
                raise ValueError("给的百分比坐标有问题")

        # 统一处理为列表格式
        if self._is_single:
            self._coord = [coord]
        else:
            self._coord = coord
        
        # 初始化边框信息
        self._borders = {'left': 0, 'right': 0, 'top': 0, 'bottom': 0}
        self._json_image_size = None
        
        # 解析JSON配置文件
        if json_path:
            self._parse_json_config(json_path)
        
        # 解析object类型
        self._app_window = None
        self._image_size = None
        self._parse_object(obj)
        
        # 缓存转换结果
        self._cache = {}        
        self._calculate_all_coordinates()

        image_extensions = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.webp')
        if type(obj) != np.ndarray:
            if obj and any(obj.lower().endswith(ext) for ext in image_extensions): 
                if self._get_result('a_percentage') is None and self._get_result('a_pixel'):
                    raise ValueError("无法转化成百分比坐标")
                if self._get_result('a_percentage')  and self._get_result('a_pixel') is None:
                    raise ValueError("无法转化成像素坐标")
    
    def _parse_json_config(self, json_path: str):
        """解析JSON配置文件，获取边框信息"""
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            if 'shapes' in data and len(data['shapes']) > 0:
                points = data['shapes'][0]['points']
                imageHeight = data.get('imageHeight', 0)
                imageWidth = data.get('imageWidth', 0)
                
                # 保存JSON中的图片尺寸
                self._json_image_size = (imageWidth, imageHeight)
                
                # 计算边框
                self._borders['left'] = points[0][0]
                self._borders['right'] = imageWidth - points[1][0]
                self._borders['top'] = points[0][1]
                self._borders['bottom'] = imageHeight - points[1][1]
                
                #print(f"加载边框配置: 左={self._borders['left']}, 右={self._borders['right']}, "
                      #f"上={self._borders['top']}, 下={self._borders['bottom']}")
        except Exception as e:
            pass
            #print(f"解析JSON配置文件失败: {e}")
    
    def _get_content_area(self) -> Tuple[float, float, float, float]:
        """获取内容区域的位置和大小（去除边框）"""
        if self._app_window:
            # 内容区域相对于屏幕的位置
            content_x = self._app_window.left + self._borders['left']
            content_y = self._app_window.top + self._borders['top']
            content_width = self._app_window.width - self._borders['left'] - self._borders['right']
            content_height = self._app_window.height - self._borders['top'] - self._borders['bottom']
            return content_x, content_y, content_width, content_height
        return None
    
    def _parse_object(self, obj):
        """解析object参数，判断是图片路径、cv图片还是app名称"""
        if obj is None:
            return
        
        if isinstance(obj, np.ndarray):
            # cv图片
            self._image_size = (obj.shape[1], obj.shape[0])  # (width, height)
        elif isinstance(obj, str):
            # 判断是图片路径还是app名称
            # 检查是否是图片文件（通过扩展名判断）
            image_extensions = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.webp')
            if any(obj.lower().endswith(ext) for ext in image_extensions):
                # 图片路径
                if os.path.exists(obj):
                    img = cv2.imread(obj)
                    if img is not None:
                        self._image_size = (img.shape[1], img.shape[0])
            else:
                # app名称
                try:
                    windows = gw.getWindowsWithTitle(obj)
                    if windows:
                        if windows[0].left >= 0:
                            self._app_window = windows[0]
                        else:
                            raise ValueError(f"未检出到{obj}窗口")
                except:
                    raise ValueError(f"未检出到{obj}窗口")
    
    def _calculate_all_coordinates(self):
        """计算所有可能的坐标类型"""
        # 首先转换到屏幕像素坐标（如果可能）
        s_pixel = self._to_screen_pixel()
        
        if s_pixel is not None:
            # 可以计算所有屏幕相关坐标
            self._cache['s_pixel'] = s_pixel
            self._cache['s_percentage'] = self._screen_pixel_to_percentage(s_pixel)
            
            # 如果有app窗口信息，可以计算app坐标
            if self._app_window is not None:
                self._cache['a_pixel'] = self._screen_to_app_pixel(s_pixel)
                self._cache['a_percentage'] = self._app_pixel_to_percentage(
                    self._cache['a_pixel']
                )
        else:
            # 无法转换到屏幕坐标（只有图片信息）
            if self._coord_type == 'a_pixel':
                self._cache['a_pixel'] = self._coord
                if self._image_size:
                    self._cache['a_percentage'] = self._app_pixel_to_percentage_with_image(self._coord)
            elif self._coord_type == 'a_percentage':
                self._cache['a_percentage'] = self._coord
                if self._image_size:
                    self._cache['a_pixel'] = self._app_percentage_to_pixel_with_image(self._coord)
    
    def _to_screen_pixel(self) -> Optional[List[List[float]]]:
        """转换到屏幕像素坐标"""
        if self._coord_type == 's_pixel':
            return self._coord
        elif self._coord_type == 's_percentage':   
            return [[c[0] * self.screen_width, c[1] * self.screen_height] for c in self._coord]
        elif self._coord_type == 'a_pixel' and self._app_window:
            # a_pixel是相对于窗口的，直接加上窗口位置
            return [[c[0] + self._app_window.left, 
                    c[1] + self._app_window.top] for c in self._coord]
        elif self._coord_type == 'a_percentage' and self._app_window:
            # a_percentage是相对于内容区域的百分比
            content_area = self._get_content_area()
            if content_area:
                content_x, content_y, content_width, content_height = content_area
                return [[c[0] * content_width + content_x,
                        c[1] * content_height + content_y] for c in self._coord]
        return None
    
    def _screen_pixel_to_percentage(self, coords: List[List[float]]) -> List[List[float]]:
        """屏幕像素坐标转百分比"""
        return [[c[0] / self.screen_width, c[1] / self.screen_height] for c in coords]

    def _screen_to_app_pixel(self, coords: List[List[float]]) -> List[List[float]]:
        """屏幕像素坐标转app像素坐标（相对于窗口，包含边框）"""
        result = []
        for c in coords:
            # 转换为相对于窗口的坐标
            app_x = c[0] - self._app_window.left
            app_y = c[1] - self._app_window.top
            
            # 检查坐标是否在窗口内
            if (app_x < 0 or app_x > self._app_window.width or 
                app_y < 0 or app_y > self._app_window.height):               
                raise ValueError(f"给的屏幕坐标[{c[0]}, {c[1]}]不在app窗口内. ")
            result.append([app_x, app_y])
        
        return result
    
    def _app_pixel_to_percentage(self, coords: List[List[float]]) -> List[List[float]]:
        """app像素坐标转app百分比坐标
        a_pixel包含边框，a_percentage不包含边框
        """
        content_area = self._get_content_area()
        if content_area:
            _, _, content_width, content_height = content_area
            result = []
            for c in coords:
                # 减去边框，得到相对于内容区域的坐标
                content_x = c[0] - self._borders['left']
                content_y = c[1] - self._borders['top']
                
                # 检查是否在内容区域内
                if content_x < 0 or content_y < 0 or content_x > content_width or content_y > content_height:
                    # 坐标在边框区域内，无法转换为内容区域百分比
                    raise ValueError(f"坐标[{c[0]}, {c[1]}]在边框区域内，无法转换为内容区域百分比")
                
                # 转换为百分比
                result.append([content_x / content_width, content_y / content_height])
            return result
        else:
            # 没有边框信息，直接使用窗口尺寸
            return [[c[0] / self._app_window.width, c[1] / self._app_window.height] for c in coords]
    
    def _app_percentage_to_pixel(self, coords: List[List[float]]) -> List[List[float]]:
        """app百分比坐标转app像素坐标
        a_percentage不包含边框，a_pixel包含边框
        """
        content_area = self._get_content_area()
        if content_area:
            _, _, content_width, content_height = content_area
            result = []
            for c in coords:
                # 百分比转换为内容区域像素，然后加上边框
                pixel_x = c[0] * content_width + self._borders['left']
                pixel_y = c[1] * content_height + self._borders['top']
                result.append([pixel_x, pixel_y])
            return result
        else:
            # 没有边框信息，直接使用窗口尺寸
            return [[c[0] * self._app_window.width, c[1] * self._app_window.height] for c in coords]
    
    def _app_pixel_to_percentage_with_image(self, coords: List[List[float]]) -> List[List[float]]:
        """使用图片尺寸将app像素坐标转为百分比（考虑边框）"""
        if self._json_image_size:
            # 有JSON配置的图片尺寸和边框信息
            content_width = self._json_image_size[0] - self._borders['left'] - self._borders['right']
            content_height = self._json_image_size[1] - self._borders['top'] - self._borders['bottom']
            result = []
            for c in coords:
                # 减去边框
                content_x = c[0] - self._borders['left']
                content_y = c[1] - self._borders['top']
                if content_x < 0 or content_y < 0 or content_x > content_width or content_y > content_height:
                    raise ValueError(f"坐标[{c[0]}, {c[1]}]在边框区域内，无法转换为内容区域百分比")
                result.append([content_x / content_width, content_y / content_height])
            return result
        elif self._image_size:
            # 只有图片尺寸，没有边框信息
            return [[c[0] / self._image_size[0], c[1] / self._image_size[1]] for c in coords]
        return None
    
    def _app_percentage_to_pixel_with_image(self, coords: List[List[float]]) -> List[List[float]]:
        """使用图片尺寸将app百分比坐标转为像素（考虑边框）"""
        if self._json_image_size:
            # 有JSON配置的图片尺寸和边框信息
            content_width = self._json_image_size[0] - self._borders['left'] - self._borders['right']
            content_height = self._json_image_size[1] - self._borders['top'] - self._borders['bottom']
            result = []
            for c in coords:
                # 百分比转换为内容区域像素，然后加上边框
                pixel_x = c[0] * content_width + self._borders['left']
                pixel_y = c[1] * content_height + self._borders['top']
                result.append([pixel_x, pixel_y])
            return result
        elif self._image_size:
            # 只有图片尺寸，没有边框信息
            return [[c[0] * self._image_size[0], c[1] * self._image_size[1]] for c in coords]
        return None
    
    def _get_result(self, coord_type: str):
        """获取指定类型的坐标结果"""
        result = self._cache.get(coord_type)
        if result is None:
            return None
        # 如果原始输入是单个坐标，返回单个坐标
        if self._is_single:
            return result[0]
        return result
    
    @property
    def s_pixel(self):
        """获取屏幕像素坐标"""
        return self._get_result('s_pixel')
    
    @property
    def s_percentage(self):
        """获取屏幕百分比坐标"""
        return self._get_result('s_percentage')
    
    @property
    def a_pixel(self):
        """获取app像素坐标（包含边框）"""
        return self._get_result('a_pixel')
    
    @property
    def a_percentage(self):
        """获取app百分比坐标（不包含边框，相对于内容区域）"""
        return self._get_result('a_percentage')
    
    @property
    def all(self):
        """获取所有可用的坐标类型"""
        result = {}
        for key in ['s_pixel', 's_percentage', 'a_pixel', 'a_percentage']:
            value = self._get_result(key)
            if value is not None:
                result[key] = value
        return result
    
    @property
    def borders(self) -> Dict[str, float]:
        """获取边框信息"""
        return self._borders.copy()
    
    def __repr__(self):
        """友好的打印输出"""
        available = []
        for key in ['s_pixel', 's_percentage', 'a_pixel', 'a_percentage']:
            if key in self._cache:
                available.append(key)
        border_info = f", borders={self._borders}" if any(self._borders.values()) else ""
        return f"CoordinateConverter(available_types={available}{border_info})"
