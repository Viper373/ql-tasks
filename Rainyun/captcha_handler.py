# -*- coding:utf-8 -*-
# @Software       :PyCharm
# @Project        :AutoTasks
# @Path           :/Rainyun
# @FileName       :captcha_handler.py.py
# @Time           :2025/9/9 06:32
# @Author         :Viper373
# @GitHub         :https://github.com/Viper373
# @Home           :https://viper3.top
# @Blog           :https://blog.viper3.top


import os
import cv2
import numpy as np
import requests
from loguru import logger
import time
import ddddocr


class CaptchaHandler:
    """点选验证码处理器"""

    def __init__(self, page, ocr=None, det=None):
        self.page = page
        self.ocr = ocr if ocr else ddddocr.DdddOcr(ocr=False, det=False, show_ad=False)
        self.det = det if det else ddddocr.DdddOcr(det=True, show_ad=False)

    def download_image(self, url, filename):
        """下载图片"""
        os.makedirs("temp", exist_ok=True)
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                path = os.path.join("temp", filename)
                with open(path, "wb") as f:
                    f.write(response.content)
                return True
        except Exception as e:
            logger.error(f"下载图片失败: {e}")
        return False

    def extract_style_url(self, style):
        """从style属性提取URL"""
        import re
        match = re.search(r'url\(["\']?(.*?)["\']?\)', style)
        return match.group(1) if match else None

    def extract_dimensions(self, style):
        """从style属性提取宽高"""
        import re
        width_match = re.search(r'width:\s*([\d.]+)px', style)
        height_match = re.search(r'height:\s*([\d.]+)px', style)
        width = float(width_match.group(1)) if width_match else 0
        height = float(height_match.group(1)) if height_match else 0
        return width, height

    def download_captcha_images(self):
        """下载验证码相关图片"""
        # 清理临时目录
        if os.path.exists("temp"):
            for f in os.listdir("temp"):
                os.remove(os.path.join("temp", f))

        try:
            # 下载背景图（包含需要点击的目标）
            bg_elem = self.page.ele('xpath://*[@id="slideBg"]', timeout=10)
            if bg_elem:
                style = bg_elem.attr("style")
                bg_url = self.extract_style_url(style)
                if bg_url:
                    logger.info(f"下载背景图: {bg_url}")
                    self.download_image(bg_url, "background.jpg")

            # 下载提示图（需要按顺序点击的图形）
            prompt_elem = self.page.ele('xpath://*[@id="instruction"]/div/img', timeout=10)
            if prompt_elem:
                prompt_url = prompt_elem.attr("src")
                logger.info(f"下载提示图: {prompt_url}")
                self.download_image(prompt_url, "prompt.jpg")

            return True
        except Exception as e:
            logger.error(f"下载验证码图片失败: {e}")
            return False

    def split_prompt_images(self):
        """分割提示图，获取需要点击的图形"""
        prompt_img = cv2.imread("temp/prompt.jpg")
        if prompt_img is None:
            return []

        h, w = prompt_img.shape[:2]
        # 通常提示图是横向排列的3个或4个图形
        num_items = 3  # 根据实际情况调整
        item_width = w // num_items

        items = []
        for i in range(num_items):
            x_start = i * item_width
            x_end = (i + 1) * item_width if i < num_items - 1 else w
            item = prompt_img[:, x_start:x_end]

            # 保存分割后的图形
            cv2.imwrite(f"temp/item_{i}.jpg", item)
            items.append(item)

        return items

    def detect_shapes_color_based(self, bg_img):
        """基于颜色和形状检测目标"""
        results = []

        # 转换到HSV色彩空间
        hsv = cv2.cvtColor(bg_img, cv2.COLOR_BGR2HSV)

        # 定义不同颜色的HSV范围（根据实际验证码调整）
        color_ranges = [
            # 黄色
            {"lower": np.array([20, 100, 100]), "upper": np.array([30, 255, 255]), "name": "yellow"},
            # 紫色
            {"lower": np.array([125, 50, 50]), "upper": np.array([155, 255, 255]), "name": "purple"},
            # 青色/蓝色
            {"lower": np.array([90, 50, 50]), "upper": np.array([120, 255, 255]), "name": "cyan"},
            # 粉色
            {"lower": np.array([150, 50, 50]), "upper": np.array([180, 255, 255]), "name": "pink"},
            # 橙色
            {"lower": np.array([5, 100, 100]), "upper": np.array([20, 255, 255]), "name": "orange"},
        ]

        for color_info in color_ranges:
            # 创建颜色掩码
            mask = cv2.inRange(hsv, color_info["lower"], color_info["upper"])

            # 形态学操作去噪
            kernel = np.ones((5, 5), np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

            # 查找轮廓
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for contour in contours:
                area = cv2.contourArea(contour)
                # 过滤太小的区域
                if area < 500:
                    continue

                # 获取边界框
                x, y, w, h = cv2.boundingRect(contour)

                # 提取该区域的图像
                roi = bg_img[y:y + h, x:x + w]

                # 计算中心点
                cx = x + w // 2
                cy = y + h // 2

                results.append({
                    "bbox": (x, y, x + w, y + h),
                    "center": (cx, cy),
                    "roi": roi,
                    "color": color_info["name"],
                    "area": area
                })

        return results

    def match_template_multi_scale(self, bg_img, template, scales=None):
        """多尺度模板匹配"""
        if scales is None:
            scales = np.linspace(0.5, 1.5, 20)

        best_match = None
        best_val = -1

        gray_bg = cv2.cvtColor(bg_img, cv2.COLOR_BGR2GRAY)
        gray_template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

        for scale in scales:
            # 调整模板大小
            resized = cv2.resize(gray_template, None, fx=scale, fy=scale)

            # 如果模板大于背景图，跳过
            if resized.shape[0] > gray_bg.shape[0] or resized.shape[1] > gray_bg.shape[1]:
                continue

            # 模板匹配
            result = cv2.matchTemplate(gray_bg, resized, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

            if max_val > best_val:
                best_val = max_val
                h, w = resized.shape
                best_match = {
                    "confidence": max_val,
                    "location": max_loc,
                    "size": (w, h),
                    "scale": scale
                }

        return best_match

    def find_click_positions(self):
        """找到需要点击的位置"""
        bg_img = cv2.imread("temp/background.jpg")
        if bg_img is None:
            logger.error("无法读取背景图")
            return []

        # 分割提示图
        prompt_items = self.split_prompt_images()
        if not prompt_items:
            logger.error("无法分割提示图")
            return []

        click_positions = []

        # 方法1：基于颜色和形状检测
        detected_shapes = self.detect_shapes_color_based(bg_img)

        # 方法2：模板匹配
        for idx, template in enumerate(prompt_items):
            logger.info(f"处理第 {idx + 1} 个图形")

            # 尝试模板匹配
            match = self.match_template_multi_scale(bg_img, template)

            if match and match["confidence"] > 0.6:  # 置信度阈值
                x, y = match["location"]
                w, h = match["size"]
                center_x = x + w // 2
                center_y = y + h // 2

                click_positions.append({
                    "index": idx,
                    "center": (center_x, center_y),
                    "confidence": match["confidence"],
                    "method": "template"
                })
                logger.info(f"模板匹配成功，置信度: {match['confidence']:.2f}")
            else:
                # 如果模板匹配失败，尝试从检测到的形状中匹配
                best_shape = None
                best_similarity = 0

                for shape in detected_shapes:
                    # 这里可以添加更复杂的相似度计算
                    # 简单示例：比较颜色直方图
                    hist1 = cv2.calcHist([template], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
                    hist1 = cv2.normalize(hist1, hist1).flatten()

                    hist2 = cv2.calcHist([shape["roi"]], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
                    hist2 = cv2.normalize(hist2, hist2).flatten()

                    similarity = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)

                    if similarity > best_similarity:
                        best_similarity = similarity
                        best_shape = shape

                if best_shape and best_similarity > 0.5:
                    click_positions.append({
                        "index": idx,
                        "center": best_shape["center"],
                        "confidence": best_similarity,
                        "method": "color_shape"
                    })
                    logger.info(f"颜色形状匹配成功，相似度: {best_similarity:.2f}")

        # 排序确保按顺序点击
        click_positions.sort(key=lambda x: x["index"])

        return click_positions

    def process_captcha(self):
        """处理点选验证码主函数"""
        try:
            # 检查是否存在验证码
            slideBg = self.page.ele('xpath://*[@id="slideBg"]', timeout=5)
            if not slideBg:
                logger.info("未检测到验证码")
                return True

            logger.info("开始处理点选验证码")

            # 下载验证码图片
            if not self.download_captcha_images():
                logger.error("下载验证码图片失败")
                return False

            # 查找点击位置
            positions = self.find_click_positions()

            if len(positions) == 0:
                logger.warning("未能识别任何点击位置，尝试刷新验证码")
                self.refresh_captcha()
                return False

            # 获取实际显示尺寸
            style = slideBg.attr("style")
            display_width, display_height = self.extract_dimensions(style)

            # 获取原始图片尺寸
            bg_img = cv2.imread("temp/background.jpg")
            orig_height, orig_width = bg_img.shape[:2]

            # 计算缩放比例
            scale_x = display_width / orig_width if orig_width > 0 else 1
            scale_y = display_height / orig_height if orig_height > 0 else 1

            # 按顺序点击
            for pos in positions:
                cx, cy = pos["center"]

                # 转换到页面坐标
                # 注意：点击坐标是相对于元素中心的偏移
                offset_x = (cx * scale_x) - (display_width / 2)
                offset_y = (cy * scale_y) - (display_height / 2)

                logger.info(f"点击第 {pos['index'] + 1} 个位置: ({offset_x:.0f}, {offset_y:.0f})")
                slideBg.click(offset_x, offset_y)
                time.sleep(0.5)  # 点击间隔

            # 提交验证
            confirm_btn = self.page.ele('xpath://*[@id="tcStatus"]/div[2]/div[2]/div/div', timeout=5)
            if confirm_btn:
                logger.info("提交验证码")
                confirm_btn.click()
                time.sleep(3)

                # 检查结果
                result_elem = self.page.ele('xpath://*[@id="tcOperation"]', timeout=5)
                if result_elem and "success" in result_elem.attr("class"):
                    logger.info("验证码验证成功!")
                    return True
                else:
                    logger.warning("验证码验证失败")
                    return False

        except Exception as e:
            logger.error(f"处理验证码异常: {e}")
            return False

    def refresh_captcha(self):
        """刷新验证码"""
        try:
            reload_btn = self.page.ele('xpath://*[@id="reload"]', timeout=3)
            if reload_btn:
                reload_btn.click()
                time.sleep(2)
                logger.info("已刷新验证码")
        except:
            pass