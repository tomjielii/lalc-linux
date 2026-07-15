import cv2
import numpy as np
from PIL import Image
import os

from input.input_handler import input_handler, REFERENCE_WIDTH, REFERENCE_HEIGHT
from recognize.template_match import template_match
from recognize.color_template_match import color_template_match
# from recognize.easy_ocr import detect_text_in_image, find_text_in_image, img_ocr
from recognize.rapid_ocr import detect_text_in_image, find_text_in_image
from recognize.utils import pil_to_cv2, mask_screenshot, fill_mask_screenshot
from recognize.img_registry import register_images_from_directory, get_image
from recognize.feature_match import feature_match
from recognize.pyramid_template_match import pyramid_template_match
from recognize.brightness_threshold_match import brightness_threshold_match
from recognize.precise_template_match import precise_template_match
from utils.logger import init_logger

logger = init_logger()


class ImageRecognizer:
    """
    轻量级图像识别类，用于在游戏截图中识别目标并返回中心坐标
    """

    def __init__(self):
        """
        初始化轻量级图像识别器
        """
        # 将图片注册到内存中
        try:
            register_images_from_directory()
        except Exception as e:
            raise Exception(f"图片初始化异常：{e}")
        

    def template_match(self, screenshot:Image.Image, template:str, threshold=0.8, visualize=False, grayscale=True, mask=None, mask_template=None, screenshot_scale=1):
        """
        模板匹配
        :param screenshot: PIL图像对象，来自game_input.screenshot
        :param template: 模板图像名字（无后缀）
        :param threshold: 匹配阈值
        :param visualize: 是否可视化匹配结果
        :param mask: 对目标图片掩码/裁剪
        :param mask_template: 对模板图片掩码/裁剪
        :param screenshot_scale: 对目标图片的缩放倍率
        :return: 匹配结果列表，每个元素包含(中心x坐标, 中心y坐标, 匹配分数)
        """
        if mask is None:
            mask = [0, 0, REFERENCE_WIDTH, REFERENCE_HEIGHT]
        template_name = template 
        template = get_image(template)
        if not mask_template is None:
            template = mask_screenshot(template, *mask_template)
        screenshot = mask_screenshot(screenshot, *mask)
        debug_image = []
        tmp = template_match(screenshot, template, threshold, visualize, grayscale, screenshot_scale, debug_image=debug_image)
        res = []
        for i in tmp:
            res.append((i[0]+mask[0], i[1]+mask[1], i[2]))
        log_pic = None if len(res) == 0 else debug_image[0]
        logger.debug(f"模板 {template_name}, 截取目标图片{mask}, 截取模板图片{mask_template}, 阈值 {threshold},匹配结果: {res}", log_pic)
        return res
    

    def precise_template_match(self, screenshot:Image.Image, template:str, threshold=0.7, visualize=False, grayscale=True, mask=None, screenshot_scale=1):
        """
        模板匹配
        :param screenshot: PIL图像对象，来自game_input.screenshot
        :param template: 模板图像名字（无后缀）
        :param threshold: 匹配阈值
        :param visualize: 是否可视化匹配结果
        :param mask: 对目标图片掩码/裁剪
        :param screenshot_scale: 对目标图片的缩放倍率
        :return: 匹配结果列表，每个元素包含(中心x坐标, 中心y坐标, 匹配分数)
        """
        if mask is None:
            mask = [0, 0, REFERENCE_WIDTH, REFERENCE_HEIGHT]
        template_name = template
        template = get_image(template)
        screenshot = mask_screenshot(screenshot, *mask)
        debug_image = []
        tmp = precise_template_match(screenshot, template, threshold, visualize, grayscale, screenshot_scale, debug_image=debug_image)
        res = []
        for i in tmp:
            res.append((i[0]+mask[0], i[1]+mask[1], i[2]))
        log_pic = None if len(res) == 0 else debug_image[0]
        logger.debug(f"执行精确模板匹配，模板{template_name}, 对目标图片做截取{mask}, 阈值 {threshold}匹配结果：{res}", log_pic)
        return res

    def pyramid_template_match(self, screenshot:Image.Image, template:str, threshold=0.7, visualize=False, grayscale=True, mask=None):
        """
        金字塔模板匹配
        :param screenshot: PIL图像对象，来自game_input.screenshot
        :param template: 模板图像名字（无后缀）
        :param threshold: 匹配阈值
        :param visualize: 是否可视化匹配结果
        :return: 匹配结果列表，每个元素包含(中心x坐标, 中心y坐标, 匹配分数, 对目标图像缩放倍率)
        """
        if mask is None:
            mask = [0, 0, REFERENCE_WIDTH, REFERENCE_HEIGHT]
        
        template_name = template
        template = get_image(template)
        screenshot = mask_screenshot(screenshot, *mask)
        debug_image = []
        tmp = pyramid_template_match(screenshot, template, threshold, visualize, grayscale, debug_image=debug_image)
        res = []
        for i in tmp:
            res.append((i[0]+mask[0], i[1]+mask[1], i[2], i[3]))
        log_pic = None if len(res) == 0 else debug_image[0]
        logger.debug(f"执行金字塔模板匹配，模板{template_name}, 对目标图片做截取{mask}, 阈值 {threshold}匹配结果：{res}", log_pic)
        return res

    def color_template_match(self, screenshot:Image.Image, template:str, threshold=0.7, visualize=False, grayscale=False, mask=None):
        """
        结合颜色的模板匹配
        :param screenshot: PIL图像对象，来自game_input.screenshot
        :param template: 模板图像名字（无后缀）
        :param threshold: 匹配阈值
        :param visualize: 是否可视化匹配结果
        :return: 匹配结果列表，每个元素包含(中心x坐标, 中心y坐标, 总和匹配分数, 模板匹配分数，颜色相似度分数)
        """
        if mask is None:
            mask = [0, 0, REFERENCE_WIDTH, REFERENCE_HEIGHT]
            
        template = get_image(template)
        screenshot = mask_screenshot(screenshot, *mask)
        tmp = color_template_match(screenshot, template, threshold, visualize, grayscale)
        res = []
        for i in tmp:
            res.append((i[0]+mask[0], i[1]+mask[1], i[2]))
        return res

    def feature_match(self, screenshot:Image.Image, template:str, threshold=0.7, visualize=False, grayscale=True, max_instances=5, mask=None):
        """
        特征点匹配
        :param screenshot: PIL图像对象，来自game_input.screenshot
        :param template: 模板图像名字（无后缀）
        :param threshold: 匹配阈值
        :param visualize: 是否可视化匹配结果
        :param grayscale: 是否使用灰度图进行匹配
        :param max_instances: 最大匹配实例数
        :return: 匹配结果列表，每个元素包含(中心x坐标, 中心y坐标, 匹配分数)
        """
        if mask is None:
            mask = [0, 0, REFERENCE_WIDTH, REFERENCE_HEIGHT]
            
        template = get_image(template)
        screenshot = mask_screenshot(screenshot, *mask)

        tmp = feature_match(screenshot, template, visualize, grayscale, max_instances, threshold)
        res = []
        for i in tmp:
            res.append((i[0]+mask[0], i[1]+mask[1], i[2]))
        return res

    def brightness_threshold_match(self, screenshot:Image.Image, threshold=180, visualize=False, grayscale=True, 
                                  mask=None, screenshot_scale=1, box_width=50, box_height=50, step=10):
        """
        基于滑动窗口和亮度阈值分割的方框检测
        :param screenshot: PIL图像对象，来自game_input.screenshot
        :param threshold: 亮度阈值，高于此值的区域被认为是"亮"的方框
        :param visualize: 是否可视化匹配结果
        :param grayscale: 是否将图像转换为灰度图
        :param mask: 对目标图片掩码/裁剪
        :param screenshot_scale: 对目标图片的缩放倍率
        :param box_width: 检测窗口的宽度（像素）
        :param box_height: 检测窗口的高度（像素）
        :param step: 窗口滑动的步长（像素），步长越小越精确，但速度越慢
        :return: 匹配结果列表，每个元素包含(中心x坐标, 中心y坐标, 平均亮度分数)
        """
        if mask is None:
            mask = [0, 0, REFERENCE_WIDTH, REFERENCE_HEIGHT]
            
        screenshot = mask_screenshot(screenshot, *mask)
        tmp = brightness_threshold_match(screenshot, threshold, visualize, grayscale, screenshot_scale,
                                       box_width, box_height, step)
        res = []
        for i in tmp:
            res.append((i[0]+mask[0], i[1]+mask[1], i[2]))
        return res

    def detect_text_in_image(self, screenshot: Image.Image, visualize=False, threshold=0.3, mask=None):
        """
        根据输入的游戏截图，进行文字检测，返回能检测的所有的文字检测信息
        :param screenshot: PIL图像对象，来自game_input.screenshot
        :param visualize: 是否可视化检测结果，默认为False
        :param threshold: 结果置信至少的置信度
        :param mask: 截图遮罩区域 [x, y, width, height]
        :return: 检测到的结果列表，内部元素为元组(文字, 中心横坐标, 中心纵坐标, 置信度)
        """
        if mask is None:
            mask = [0, 0, REFERENCE_WIDTH, REFERENCE_HEIGHT]
            
        _img = fill_mask_screenshot(screenshot , *mask)
        debug_image = []
        res = detect_text_in_image(_img, visualize, threshold, debug_image=debug_image)
        log_pic = None if len(res) == 0 else debug_image[0]
        logger.debug(f"执行文字识别，对目标图片做截取{mask}，识别结果：{res}", log_pic)
        return res

    def find_text_in_image(self, screenshot: Image.Image, target_text, visualize=False, threshold=0.5, mask=None):
        """
        在图像中查找指定的文字
        :param screenshot: PIL图像对象，来自game_input.screenshot
        :param target_text: 要查找的目标文字
        :param visualize: 是否可视化检测结果，默认为False
        :param threshold: 结果置信至少的置信度
        :param mask: 截图遮罩区域 [x, y, width, height]
        :return: 匹配的文字坐标列表，每个元素为元组(文字, 中心横坐标, 中心纵坐标, 置信度)
        """
        
        if mask is None:
            mask = [0, 0, REFERENCE_WIDTH, REFERENCE_HEIGHT]
        
        detected_texts = self.detect_text_in_image(screenshot, threshold=threshold, visualize=visualize, mask=mask)
        
        found_texts = []
        for text in detected_texts:
            if target_text in text[0]:
                found_texts.append(text)
        logger.debug(f"执行文字查找，目标文字{target_text}, 对目标图片做截取{mask}，查找结果：{found_texts}")
        return found_texts

recognize_handler = ImageRecognizer()


if __name__ == "__main__":
    # 测试所有匹配算法
    print("=== 图像识别测试 ===")

    import os
    from input.input_handler import input_handler
    from recognize.img_registry import IMG_REGISTRY

    con = input_handler
    con.refresh_window_state()
    
    # 截图
    os.makedirs("test_output", exist_ok=True)
    try:
        screenshot = con.capture_screenshot(save_path="test_output/recognizer_test.png")
        print(f"截图成功: {screenshot.size}")
    except Exception as e:
        print(f"截图失败: {e}")
        exit(1)
    
    # 取第一个已注册模板做匹配测试（跳过 dataset 类）
    test_template = None
    for name in IMG_REGISTRY:
        if not name.startswith("dataset_"):
            test_template = name
            break
    
    if test_template is None:
        print("错误: 没有可用的模板")
        exit(1)
    
    print(f"使用模板: {test_template}")
    
    # 测试模板匹配
    print("\n1. 测试模板匹配:")
    try:
        matches = recognize_handler.template_match(screenshot, test_template, visualize=False)
        print(f"   找到 {len(matches)} 个匹配")
        for m in matches[:5]:
            print(f"     坐标 ({m[0]}, {m[1]}) 置信度 {m[2]:.3f}")
    except Exception as e:
        print(f"   模板匹配出错: {e}")
    
    print("\n测试完成")