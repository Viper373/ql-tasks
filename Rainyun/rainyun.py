# -*- coding:utf-8 -*-
# @Software       :PyCharm
# @Project        :AutoTasks
# @Path           :/Rainyun
# @FileName       :rainyun.py
# @Time           :2025/9/13
# @Author         :Viper373
# @GitHub         :https://github.com/Viper373
# @Home           :https://viper3.top
# @Blog           :https://blog.viper3.top

import os
import re
import time
import random
from typing import Optional, List, Tuple, Dict, Any

import cv2
import ddddocr
import requests
from loguru import logger


class RainyunSigner:
    """雨云签到工具"""

    def __init__(self, debug: bool = False, output_collector: Optional[Any] = None) -> None:
        self.debug = debug
        self.timeout = 15
        self.ver = "1.0-DP"
        self.ocr: Optional[ddddocr.DdddOcr] = None
        self.det: Optional[ddddocr.DdddOcr] = None
        self.browser: Optional[Any] = None
        self.page: Optional[Any] = None
        self._last_captcha_urls = {"bg": "", "sprite": ""}
        # 识别相关阈值
        self.min_similarity = 0.35  # 降低阈值，提高识别成功率
        self.output_collector = output_collector
        # 配置日志
        self._setup_logger()
        # 显示信息
        self._show_banner()

    def _setup_logger(self) -> None:
        """配置日志，显示行号和方法名"""
        pass
    
    def _log(self, level: str, message: str) -> None:
        """统一的日志输出方法"""
        log_methods = {
            'info': logger.info,
            'success': logger.success,
            'warning': logger.warning,
            'error': logger.error
        }
        
        log_method = log_methods.get(level, logger.info)
        log_method(message)
        
        # 同时输出到收集器
        if self.output_collector:
            self.output_collector.add_output(level, message)

    def _show_banner(self) -> None:
        """显示程序横幅"""
        logger.info("=" * 70)
        logger.info(f"🌧️  雨云签到工具 v{self.ver} by Viper373")
        logger.info("📦  DrissionPage版本 - 支持验证码自动识别")
        logger.info("🔗  Github: https://github.com/Viper373/AutoTasks")
        logger.info("=" * 70)

    def read_config(self) -> Tuple[str, str]:
        """读取用户配置"""
        username = os.getenv('RAINYUN_USERNAME', 'Viper373')
        password = os.getenv('RAINYUN_PASSWORD', '')
        return username, password

    def init_browser(self) -> None:
        """初始化浏览器（使用全局浏览器实例）"""
        logger.info("使用全局浏览器实例")

    def init_ocr(self) -> None:
        """初始化OCR"""
        logger.info("初始化 ddddocr")
        self.ocr = ddddocr.DdddOcr(show_ad=False)
        self.det = ddddocr.DdddOcr(det=True, show_ad=False)
    
    def relogin(self, username: str, password: str) -> bool:
        """重新登录"""
        try:
            logger.info("正在重新登录...")
            
            # 1. 点击用户头像/菜单
            user_menu = self.page.ele('xpath://li[@id="__BVID__89"]', timeout=5)
            if user_menu:
                user_menu.click()
                time.sleep(1)
                
                # 2. 点击退出登录
                logout_btn = self.page.ele('xpath://ul[@id="_BVID_89_BV_toggle_menu_"]//a[contains(@class, "dropdown-item") and contains(., "退出登录")]', timeout=5)
                logout_btn.click()
                if 'login' in self.page.url:
                    logger.info("已退出当前用户")
                    time.sleep(2)
                else:
                    logger.warning("未找到退出登录按钮")
            else:
                logger.warning("未找到用户菜单")
            
            # 3. 执行登录流程
            logger.info("开始执行登录流程...")
            return self.login(username, password)
            
        except Exception as e:
            logger.error(f"重新登录过程中出现异常: {e}")
            return False

    def check_login_status(self, username: str, password: str) -> bool:
        """检查登录状态"""
        try:
            # 1. 先导航到dashboard页面
            logger.info("导航到dashboard页面...")
            self.page.get("https://app.rainyun.com/dashboard")
            time.sleep(3)  # 等待页面加载
            
            # 2. 检查当前URL是否包含dashboard
            if "dashboard" not in self.page.url:
                logger.info("无法访问dashboard页面，未登录")
                return False
            
            # 2. 检查class="user-status"的span标签文本是否为"欢迎你"
            user_status_span = self.page.ele('xpath://span[@class="user-status"]', timeout=5)
            if not user_status_span:
                logger.info("未找到user-status元素，未登录")
                return False
            
            welcome_text = user_status_span.text.strip()
            if welcome_text != "欢迎你":
                logger.info(f"user-status文本不是'欢迎你'，当前文本: '{welcome_text}'，未登录")
                return False
            
            # 3. 检查同级前一个p标签的文本是否与username一致
            # 查找user-status span的同级前一个p标签
            p_element = self.page.ele('xpath://span[@class="user-status"]/preceding-sibling::p[1]', timeout=3)
            if not p_element:
                logger.info("未找到用户名p标签，未登录")
                return False
            
            current_username = p_element.text.strip()
            if current_username != username:
                logger.info(f"用户名不匹配，期望: '{username}'，实际: '{current_username}'，需要重新登录")
                # 执行重新登录
                if self.relogin(username, password):
                    logger.info("重新登录成功")
                    return True
                else:
                    logger.error("重新登录失败")
                    return False
            
            logger.info(f"登录状态检查通过，当前用户: {current_username}")
            return True
            
        except Exception as e:
            logger.warning(f"检查登录状态失败: {e}")
            return False

    def download_image(self, url: str, filename: str) -> bool:
        """下载图片到temp目录（重试，校验大小）"""
        os.makedirs("temp", exist_ok=True)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://app.rainyun.com/",
        }
        for _ in range(3):
            try:
                resp = requests.get(url, headers=headers, timeout=10)
                if resp.status_code == 200 and resp.content and len(resp.content) > 1024:
                    path = os.path.join("temp", filename)
                    with open(path, "wb") as f:
                        f.write(resp.content)
                    logger.info(f"图片下载成功: {filename}")
                    return True
            except Exception as e:
                logger.debug(f"下载重试: {e}")
            time.sleep(0.2)
        logger.error("下载图片失败！")
        return False

    def get_url_from_style(self, style: Optional[str]) -> Optional[str]:
        """从CSS style中提取URL（兼容 None）"""
        if not style:
            return None
        try:
            match = re.search(r'url\(["\']?(.*?)["\']?\)', style)
            return match.group(1) if match else None
        except Exception:
            return None

    def get_width_from_style(self, style: Optional[str]) -> Optional[str]:
        """从CSS style中提取宽度（兼容 None）"""
        if not style:
            return None
        try:
            match = re.search(r'width:\s*([\d.]+)px', style)
            return match.group(1) if match else None
        except Exception:
            return None

    def get_height_from_style(self, style: Optional[str]) -> Optional[str]:
        """从CSS style中提取高度（兼容 None）"""
        if not style:
            return None
        try:
            match = re.search(r'height:\s*([\d.]+)px', style)
            return match.group(1) if match else None
        except Exception:
            return None

    def download_captcha_images_from_urls(self, bg_url: str, sprite_url: str) -> None:
        """从URL下载验证码图片"""
        if bg_url:
            logger.info("开始下载验证码背景图片")
            self.download_image(bg_url, "captcha.jpg")
        else:
            logger.warning("未获取到背景图片URL")
        
        if sprite_url:
            logger.info("开始下载验证码sprite图片")
            self.download_image(sprite_url, "sprite.jpg")
        else:
            logger.warning("未获取到sprite图片URL")

    def wait_captcha_ready(self) -> bool:
        """等待验证码iframe加载完成"""
        try:
            logger.info("等待验证码iframe加载...")
            
            # 等待验证码iframe出现
            iframe = self.page.ele('xpath://iframe[contains(@src, "turing.captcha")]', timeout=10)
            if not iframe:
                logger.warning("验证码iframe未找到")
                return False
            
            logger.info("找到验证码iframe，等待内容加载...")
            time.sleep(3)  # 给iframe内容加载时间
            
            # 切换到iframe内部检查元素
            try:
                iframe_frame = iframe.get_frame(iframe)
                if iframe_frame:
                    # 检查验证码相关元素是否存在
                    captcha_elements = iframe_frame.eles('xpath://div[contains(@class, "tc-captcha")]', timeout=5)
                    if captcha_elements:
                        logger.info("验证码iframe内容加载完成")
                        return True
                    else:
                        logger.warning("验证码iframe内容未完全加载")
                        return False
                else:
                    logger.warning("无法切换到验证码iframe")
                    return False
            except Exception as e:
                logger.warning(f"检查验证码iframe内容失败: {e}")
                return False
                
        except Exception as e:
            logger.error(f"等待验证码加载失败: {e}")
            return False

    def download_captcha_img(self) -> bool:
        """从iframe中下载验证码图片"""
        try:
            logger.info("开始下载验证码图片...")
            
            # 获取验证码iframe
            iframe = self.page.ele('xpath://iframe[contains(@src, "turing.captcha")]', timeout=5)
            if not iframe:
                logger.error("未找到验证码iframe")
                return False
            
            # 切换到iframe内部
            iframe_frame = iframe.get_frame(iframe)
            if not iframe_frame:
                logger.error("无法切换到验证码iframe")
                return False
            
            # 临时切换页面对象
            temp_page = self.page
            self.page = iframe_frame
            
            try:
                bg_url = self._find_background_image_url()
                sprite_url = self._find_sprite_image_url()
                
                # 下载图片
                if bg_url:
                    logger.info(f"找到背景图片URL")
                    self.download_image(bg_url, "captcha.jpg")
                else:
                    logger.warning("未找到背景图片URL")
                
                if sprite_url:
                    logger.info(f"找到sprite图片URL")
                    self.download_image(sprite_url, "sprite.jpg")
                else:
                    logger.warning("未找到sprite图片URL")
                
                # 检查是否成功下载了图片
                if os.path.exists("temp/captcha.jpg") and os.path.exists("temp/sprite.jpg"):
                    logger.info("验证码图片下载成功")
                    return True
                else:
                    logger.warning("验证码图片下载失败")
                    return False
                    
            finally:
                # 恢复页面对象
                self.page = temp_page
                
        except Exception as e:
            logger.error(f"下载验证码图片失败: {e}")
            return False

    def _download_captcha_images(self) -> None:
        """在iframe内部下载验证码图片"""
        try:
            # 清理temp目录
            if os.path.exists("temp"):
                for filename in os.listdir("temp"):
                    file_path = os.path.join("temp", filename)
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.remove(file_path)

            # 下载背景图片
            bg_url = self._find_background_image_url()
            if bg_url:
                self.download_image(bg_url, "captcha.jpg")
            else:
                logger.warning("未找到背景图片URL")

            # 下载sprite图片
            sprite_url = self._find_sprite_image_url()
            if sprite_url:
                self.download_image(sprite_url, "sprite.jpg")
            else:
                logger.warning("未找到sprite图片URL")
                
        except Exception as e:
            logger.warning(f"下载验证码图片时出错: {e}")

    # 图像预处理，提升特征稳定性
    def _preprocess_gray(self, img):
        if img is None:
            return None
        try:
            if len(img.shape) == 3:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # 增强对比度
            img = cv2.convertScaleAbs(img, alpha=1.2, beta=10)
            
            # 轻微模糊去噪
            img = cv2.GaussianBlur(img, (3, 3), 0)
            
            # CLAHE 增强对比
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            img = clahe.apply(img)
            
            # 形态学操作，去除噪点
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
            img = cv2.morphologyEx(img, cv2.MORPH_CLOSE, kernel)
            
            return img
        except Exception:
            return img

    def _trim_transparent(self, rgba_img):
        try:
            if rgba_img is None or rgba_img.shape[2] < 4:
                return rgba_img
            alpha = rgba_img[:, :, 3]
            ys, xs = (alpha > 0).nonzero()
            if ys.size == 0 or xs.size == 0:
                return rgba_img
            y1, y2 = ys.min(), ys.max() + 1
            x1, x2 = xs.min(), xs.max() + 1
            return rgba_img[y1:y2, x1:x2, :]
        except Exception:
            return rgba_img

    def prepare_icons(self) -> None:
        """从 sprite.jpg 生成更干净的三个图标模板，尽量保留透明区域供匹配。"""
        try:
            sprite_rgba = cv2.imread("temp/sprite.jpg", cv2.IMREAD_UNCHANGED)
            if sprite_rgba is None:
                return
            h, w = sprite_rgba.shape[:2]
            step = w // 3 if w >= 3 else w
            for i in range(3):
                icon = sprite_rgba[:, step * i: step * (i + 1)]
                icon = self._trim_transparent(icon)
                # 保留透明通道保存为png
                cv2.imwrite(f"temp/icon_{i + 1}.png", icon)
        except Exception:
            pass

    def _edge(self, img_gray):
        try:
            img_gray = self._preprocess_gray(img_gray)
            v = max(10, int(max(0, min(255, img_gray.mean()))))
            edges = cv2.Canny(img_gray, v, v * 2)
            return edges
        except Exception:
            return img_gray

    def locate_icons_by_template(self, captcha_bgr) -> dict:
        """直接基于模板匹配在整幅验证码中定位三枚图标，返回 result 字典。"""
        result = {}
        try:
            cap_gray = cv2.cvtColor(captcha_bgr, cv2.COLOR_BGR2GRAY)
            edge_cap = self._edge(cap_gray)
            h_cap, w_cap = cap_gray.shape[:2]

            for j in range(3):
                icon = cv2.imread(f"temp/icon_{j + 1}.png", cv2.IMREAD_UNCHANGED)
                if icon is None:
                    continue
                # 分离 alpha 生成掩膜
                if icon.shape[2] == 4:
                    icon_rgb = cv2.cvtColor(icon, cv2.COLOR_BGRA2BGR)
                    icon_gray = cv2.cvtColor(icon_rgb, cv2.COLOR_BGR2GRAY)
                    mask = icon[:, :, 3]
                else:
                    icon_gray = cv2.cvtColor(icon, cv2.COLOR_BGR2GRAY)
                    mask = None
                edge_icon = self._edge(icon_gray)

                best_score = -1.0
                best_pt = None
                for sc in [0.85, 0.9, 1.0, 1.1, 1.2]:
                    t = edge_icon
                    if abs(sc - 1.0) > 1e-6:
                        tw = max(1, int(edge_icon.shape[1] * sc))
                        th = max(1, int(edge_icon.shape[0] * sc))
                        t = cv2.resize(edge_icon, (tw, th))
                    if t.shape[0] >= edge_cap.shape[0] or t.shape[1] >= edge_cap.shape[1]:
                        continue
                    try:
                        res = cv2.matchTemplate(edge_cap, t, cv2.TM_CCOEFF_NORMED)
                        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
                        if max_val > best_score:
                            best_score = float(max_val)
                            cx = int(max_loc[0] + t.shape[1] / 2)
                            cy = int(max_loc[1] + t.shape[0] / 2)
                            best_pt = (cx, cy)
                    except Exception:
                        continue

                if best_pt is not None:
                    result[f"sprite_{j + 1}.similarity"] = best_score
                    result[f"sprite_{j + 1}.position"] = f"{best_pt[0]},{best_pt[1]}"
        except Exception:
            pass
        return result

    # 简单 NMS，去掉高度重叠的框
    def _nms(self, boxes, iou_thresh: float = 0.3, max_keep: int = 6):
        def iou(a, b):
            x1 = max(a[0], b[0]); y1 = max(a[1], b[1])
            x2 = min(a[2], b[2]); y2 = min(a[3], b[3])
            inter = max(0, x2 - x1) * max(0, y2 - y1)
            area_a = max(0, a[2] - a[0]) * max(0, a[3] - a[1])
            area_b = max(0, b[2] - b[0]) * max(0, b[3] - b[1])
            union = area_a + area_b - inter if area_a + area_b - inter > 0 else 1
            return inter / union
        if not boxes:
            return boxes
        # 按面积从大到小，保留较大框
        boxes = sorted(boxes, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]), reverse=True)
        kept = []
        for b in boxes:
            if all(iou(b, k) < iou_thresh for k in kept):
                kept.append(b)
            if len(kept) >= max_keep:
                break
        return kept

    def _find_background_image_url(self) -> Optional[str]:
        """查找背景图片URL"""
        # 方法1：查找id为slideBg的div元素
        bg_div = self.page.ele('xpath://div[@id="slideBg"]')
        if bg_div:
            style = bg_div.attr('style')
            if style and 'background-image' in style:
                return self.get_url_from_style(style)
        
        # 方法2：查找class包含tc-bg-img的div元素
        bg_elements = self.page.eles('xpath://div[contains(@class, "tc-bg-img")]')
        for element in bg_elements:
            style = element.attr('style')
            if style and 'background-image' in style:
                return self.get_url_from_style(style)
        
        return None

    def _find_sprite_image_url(self) -> Optional[str]:
        """查找sprite图片URL"""
        # 方法1：查找class为tc-instruction-icon的div内的img元素
        sprite_imgs = self.page.eles('xpath://div[contains(@class, "tc-instruction-icon")]//img')
        for img in sprite_imgs:
            src = img.attr('src')
            if src and 'turing.captcha.qcloud.com' in src and 'img_index=0' in src:
                return src
        
        # 方法2：查找所有img元素，筛选包含img_index=0的
        all_imgs = self.page.eles('xpath://img')
        for img in all_imgs:
            src = img.attr('src')
            if src and 'turing.captcha.qcloud.com' in src and 'img_index=0' in src:
                return src
        
        return None

    def cleanup_temp_dir(self) -> None:
        """清理temp目录"""
        try:
            import shutil
            if os.path.exists("temp"):
                shutil.rmtree("temp")
                logger.info("已清理temp目录")
        except Exception as e:
            logger.warning(f"清理temp目录失败: {e}")

    def get_url_from_style(self, style: Optional[str]) -> Optional[str]:
        """从CSS style中提取URL（兼容 None）"""
        if not style:
            return None
        try:
            match = re.search(r'url\(["\']?(.*?)["\']?\)', style)
            return match.group(1) if match else None
        except Exception:
            return None

    def get_width_from_style(self, style: Optional[str]) -> Optional[str]:
        """从CSS style中提取宽度（兼容 None）"""
        if not style:
            return None
        try:
            match = re.search(r'width:\s*([\d.]+)px', style)
            return match.group(1) if match else None
        except Exception:
            return None

    def get_height_from_style(self, style: Optional[str]) -> Optional[str]:
        """从CSS style中提取高度（兼容 None）"""
        if not style:
            return None
        try:
            match = re.search(r'height:\s*([\d.]+)px', style)
            return match.group(1) if match else None
        except Exception:
            return None

    def _preprocess_gray(self, img):
        """图像预处理，提升特征稳定性"""
        if img is None:
            return None
        try:
            if len(img.shape) == 3:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            # 轻微模糊去噪
            img = cv2.GaussianBlur(img, (3, 3), 0)
            # CLAHE 增强对比
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            img = clahe.apply(img)
            return img
        except Exception:
            return img

    def _trim_transparent(self, rgba_img):
        """裁剪透明区域"""
        try:
            if rgba_img is None or rgba_img.shape[2] < 4:
                return rgba_img
            alpha = rgba_img[:, :, 3]
            ys, xs = (alpha > 0).nonzero()
            if ys.size == 0 or xs.size == 0:
                return rgba_img
            y1, y2 = ys.min(), ys.max() + 1
            x1, x2 = xs.min(), xs.max() + 1
            return rgba_img[y1:y2, x1:x2, :]
        except Exception:
            return rgba_img

    def prepare_icons(self) -> None:
        """从 sprite.jpg 生成更干净的三个图标模板"""
        try:
            sprite = cv2.imread("temp/sprite.jpg", cv2.IMREAD_UNCHANGED)
            if sprite is None:
                return
            
            # 裁剪透明区域
            sprite = self._trim_transparent(sprite)
            
            # 分割成三个图标
            h, w = sprite.shape[:2]
            icon_h = h // 3
            
            for i in range(3):
                y1, y2 = i * icon_h, (i + 1) * icon_h
                icon = sprite[y1:y2, :]
                cv2.imwrite(f"temp/sprite_{i + 1}.jpg", icon)
        except Exception as e:
            logger.error(f"准备图标失败: {e}")

    def _edge(self, img_gray):
        """边缘检测"""
        try:
            return cv2.Canny(img_gray, 50, 150)
        except Exception:
            return img_gray

    def locate_icons_by_template(self, captcha_bgr) -> Dict:
        """基于模板匹配定位图标"""
        result = {}
        try:
            captcha_gray = cv2.cvtColor(captcha_bgr, cv2.COLOR_BGR2GRAY)
            captcha_edge = self._edge(captcha_gray)
            
            for i in range(1, 4):
                template = cv2.imread(f"temp/sprite_{i}.jpg", cv2.IMREAD_GRAYSCALE)
                if template is None:
                    continue
                
                template_edge = self._edge(template)
                res = cv2.matchTemplate(captcha_edge, template_edge, cv2.TM_CCOEFF_NORMED)
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
                
                if max_val > 0.3:  # 降低阈值
                    result[f'sprite_{i}'] = {
                        'similarity': max_val,
                        'x': max_loc[0],
                        'y': max_loc[1]
                    }
        except Exception as e:
            logger.error(f"模板匹配失败: {e}")
        
        return result

    def _nms(self, boxes: List[List[int]], iou_thresh: float = 0.3, max_keep: int = 6) -> List[List[int]]:
        """非极大值抑制"""
        if not boxes:
            return []
        
        boxes = sorted(boxes, key=lambda x: (x[2] - x[0]) * (x[3] - x[1]), reverse=True)
        keep = []
        
        while boxes and len(keep) < max_keep:
            current = boxes.pop(0)
            keep.append(current)
            
            boxes = [box for box in boxes if self._compute_iou(current, box) < iou_thresh]
        
        return keep

    def _compute_iou(self, box1: List[int], box2: List[int]) -> float:
        """计算IoU"""
        x1 = max(box1[0], box2[0])
        y1 = max(box1[1], box2[1])
        x2 = min(box1[2], box2[2])
        y2 = min(box1[3], box2[3])
        
        if x2 <= x1 or y2 <= y1:
            return 0.0
        
        intersection = (x2 - x1) * (y2 - y1)
        area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
        area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
        union = area1 + area2 - intersection
        
        return intersection / union if union > 0 else 0.0

    def check_captcha(self) -> bool:
        """按示例逻辑：切三张子图并用 OCR 过滤明显无效的验证码。"""
        if not os.path.exists("temp/sprite.jpg"):
            logger.warning("验证码sprite图片不存在")
            return False

        raw = cv2.imread("temp/sprite.jpg")
        if raw is None:
            logger.warning("无法读取验证码sprite图片")
            return False

        try:
            w = raw.shape[1]
            if w < 3:
                logger.warning("验证码sprite图片宽度不足")
                return False
                
            invalid_cnt = 0
            for i in range(3):
                temp = raw[:, w // 3 * i: w // 3 * (i + 1)]
                if temp.size == 0:
                    logger.warning(f"验证码切片 {i+1} 为空")
                    return False
                cv2.imwrite(f"temp/sprite_{i + 1}.jpg", temp)
                with open(f"temp/sprite_{i + 1}.jpg", mode="rb") as f:
                    temp_rb = f.read()
                if self.ocr.classification(temp_rb) in ["0", "1"]:
                    invalid_cnt += 1
            
            # GitHub Actions 环境使用更宽松的检查标准
            if os.getenv('GITHUB_ACTIONS'):
                # 在 GitHub Actions 环境中，只有全部3个都被判定为无效时才认为质量低
                is_valid = invalid_cnt < 3
                if not is_valid:
                    logger.warning(f"GitHub Actions 环境验证码质量检查：{invalid_cnt}/3 个切片被判定为无效")
            else:
                # 本地环境使用原来的标准
                is_valid = invalid_cnt <= 2
                if not is_valid:
                    logger.warning(f"验证码质量检查：{invalid_cnt}/3 个切片被判定为无效")
                    
            return is_valid
        except Exception as e:
            logger.warning(f"验证码切割/检测异常: {e}")
            # 异常时也尝试继续，而不是直接返回False
            return True

    def check_answer(self, d: dict) -> bool:
        """检查是否存在重复坐标，快速判断识别错误"""
        flipped = dict()
        for key in d.keys():
            if key.endswith('.position'):
                flipped[d[key]] = key
        return len([k for k in d.keys() if k.endswith('.position')]) == len(flipped.keys())

    def compute_similarity(self, img1_path: str, img2_path: str) -> tuple[float, int]:
        """融合 SIFT 与多尺度模板匹配的相似度，更稳健。"""
        if not os.path.exists(img1_path) or not os.path.exists(img2_path):
            return 0.0, 0

        img1 = cv2.imread(img1_path, cv2.IMREAD_GRAYSCALE)
        img2 = cv2.imread(img2_path, cv2.IMREAD_GRAYSCALE)
        img1 = self._preprocess_gray(img1)
        img2 = self._preprocess_gray(img2)

        # SIFT
        try:
            sift = cv2.SIFT_create()
            kp1, des1 = sift.detectAndCompute(img1, None)
            kp2, des2 = sift.detectAndCompute(img2, None)
            if des1 is None or des2 is None:
                sift_score = 0.0
                good_len = 0
            else:
                bf = cv2.BFMatcher()
                matches = bf.knnMatch(des1, des2, k=2)
                good = [m for m_n in matches if len(m_n) == 2 for m, n in [m_n] if m.distance < 0.8 * n.distance]
                sift_score = (len(good) / len(matches)) if matches else 0.0
                good_len = len(good)
        except Exception:
            sift_score = 0.0
            good_len = 0

        # 模板匹配（多尺度，归一化相关系数）
        try:
            scales = [0.85, 0.9, 1.0, 1.1, 1.15]
            tm_score = 0.0
            for sc in scales:
                t = img1
                if abs(sc - 1.0) > 1e-6:
                    w = max(1, int(img1.shape[1] * sc))
                    h = max(1, int(img1.shape[0] * sc))
                    t = cv2.resize(img1, (w, h))
                if t.shape[0] <= img2.shape[0] and t.shape[1] <= img2.shape[1]:
                    res = cv2.matchTemplate(img2, t, cv2.TM_CCOEFF_NORMED)
                    if res.size:
                        tm_score = max(tm_score, float(res.max()))
        except Exception:
            tm_score = 0.0

        # 融合：SIFT和模板匹配的加权平均，更鲁棒
        if sift_score > 0 and tm_score > 0:
            # 两者都有值时，加权平均
            final_score = 0.6 * sift_score + 0.4 * tm_score
        elif sift_score > 0:
            # 只有SIFT时，稍微降低权重
            final_score = sift_score * 0.8
        elif tm_score > 0:
            # 只有模板匹配时，使用原值
            final_score = tm_score
        else:
            # 都没有时，返回0
            final_score = 0.0
            
        return final_score, good_len

    def template_best_match(self, template_img, target_img) -> tuple[float, int, int]:
        """模板匹配，返回最佳分数以及在 target_img 中的匹配中心点坐标(cx, cy)。
        会尝试多尺度缩放模板以适配尺寸差异。
        """
        try:
            tpl = template_img
            src = target_img
            if tpl is None or src is None or tpl.size == 0 or src.size == 0:
                return 0.0, src.shape[1] // 2 if src is not None else 0, src.shape[0] // 2 if src is not None else 0

            if len(tpl.shape) == 3:
                tpl = cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY)
            if len(src.shape) == 3:
                src = cv2.cvtColor(src, cv2.COLOR_BGR2GRAY)

            best_score = 0.0
            best_pt = (src.shape[1] // 2, src.shape[0] // 2)

            # 多尺度因子
            scales = [0.8, 0.9, 1.0, 1.1, 1.2]
            for sc in scales:
                tpl_rs = tpl
                if abs(sc - 1.0) > 1e-6:
                    w = max(1, int(tpl.shape[1] * sc))
                    h = max(1, int(tpl.shape[0] * sc))
                    tpl_rs = cv2.resize(tpl, (w, h))

                if tpl_rs.shape[0] > src.shape[0] or tpl_rs.shape[1] > src.shape[1]:
                    continue

                res = cv2.matchTemplate(src, tpl_rs, cv2.TM_CCOEFF_NORMED)
                if res.size == 0:
                    continue
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
                if max_val > best_score:
                    best_score = float(max_val)
                    # 匹配的左上角 + 模板的中心 -> src中的中心
                    cx = int(max_loc[0] + tpl_rs.shape[1] / 2)
                    cy = int(max_loc[1] + tpl_rs.shape[0] / 2)
                    best_pt = (cx, cy)

            return best_score, best_pt[0], best_pt[1]
        except Exception:
            # 失败则返回居中
            return 0.0, target_img.shape[1] // 2 if target_img is not None else 0, target_img.shape[0] // 2 if target_img is not None else 0

    def check_captcha_success(self) -> bool:
        """检查验证码是否成功"""
        try:
            # 等待验证结果
            time.sleep(2)
            
            # 检查验证码结果元素
            result_ele = self.page.ele('xpath://*[@id="tcOperation"]')
            if result_ele:
                cls_val = result_ele.attr("class")
                if isinstance(cls_val, str) and 'show-success' in cls_val:
                    logger.info("验证码通过")
                    return True
            
            # 检查签到状态
            sign_label = self.page.ele('xpath://span[contains(text(), "每日签到")]/following-sibling::span[1]')
            if sign_label:
                status_text = sign_label.text.strip()
                if status_text == "已完成":
                    self._log('success', "验证码通过，签到成功")
                    return True
                elif "领取奖励" in status_text:
                    logger.warning("验证码失败，签到未成功")
                    return False
            
            logger.warning("验证码状态未知")
            return False
        except Exception as e:
            logger.error(f"检查验证码成功状态失败: {e}")
            return False

    def compute_similarity(self, img1_path: str, img2_path: str) -> Tuple[float, int]:
        """计算两张图片的相似度"""
        try:
            img1 = cv2.imread(img1_path, cv2.IMREAD_GRAYSCALE)
            img2 = cv2.imread(img2_path, cv2.IMREAD_GRAYSCALE)
            
            if img1 is None or img2 is None:
                return 0.0, 0
            
            # 调整图片大小
            h1, w1 = img1.shape
            h2, w2 = img2.shape
            
            if h1 != h2 or w1 != w2:
                img2 = cv2.resize(img2, (w1, h1))
            
            # 计算相似度
            result = cv2.matchTemplate(img1, img2, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            
            return float(max_val), max_loc[0]
        except Exception as e:
            logger.error(f"计算相似度失败: {e}")
            return 0.0, 0

    def template_best_match(self, template_img, target_img) -> Tuple[float, int, int]:
        """模板匹配最佳位置"""
        try:
            if template_img is None or target_img is None:
                return 0.0, 0, 0
            
            result = cv2.matchTemplate(target_img, template_img, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            
            return float(max_val), max_loc[0], max_loc[1]
        except Exception:
            # 失败则返回居中
            return 0.0, target_img.shape[1] // 2 if target_img is not None else 0, target_img.shape[0] // 2 if target_img is not None else 0

    def _refresh_captcha(self) -> bool:
        """刷新验证码并重新下载图片"""
        try:
            reload = self.page.ele('xpath://*[@id="reload"]')
            time.sleep(1.0)
            reload.click()
            time.sleep(2.0)
            logger.info("验证码已刷新，重新下载图片")
            
            # 刷新后需要重新等待iframe加载
            if self.wait_captcha_ready():
                return self.download_captcha_img()
            else:
                logger.error("刷新后验证码iframe未就绪")
                return False
        except Exception:
            logger.warning("刷新按钮不存在，使用 JS 重载 iframe")
            try:
                self.page.run_js("location.reload()")
                time.sleep(2.5)
                logger.info("验证码已刷新，重新下载图片")
                
                # 重载后需要重新等待iframe加载
                if self.wait_captcha_ready():
                    return self.download_captcha_img()
                else:
                    logger.error("重载后验证码iframe未就绪")
                    return False
            except Exception:
                logger.warning("刷新失败")
                return False

    def _detect_captcha_objects(self) -> List:
        """检测验证码中的目标对象"""
        captcha = cv2.imread("temp/captcha.jpg")
        self.prepare_icons()
        global_result = self.locate_icons_by_template(captcha.copy())
        
        with open("temp/captcha.jpg", 'rb') as f:
            captcha_b = f.read()
        
        bboxes = self.det.detection(captcha_b)
        time.sleep(0.1)
        return bboxes

    def _click_captcha_targets(self, bboxes: List) -> bool:
        """点击验证码目标"""
        captcha = cv2.imread("temp/captcha.jpg")
        
        # NMS 去重
        try:
            bboxes = self._nms([list(map(int, b)) for b in bboxes], iou_thresh=0.35, max_keep=8)
        except Exception:
            pass

        # 为每个 sprite 构建候选集
        candidates = {1: [], 2: [], 3: []}
        for i, box in enumerate(bboxes):
            x1, y1, x2, y2 = box
            spec = captcha[y1:y2, x1:x2]
            spec = self._preprocess_gray(spec)
            cv2.imwrite(f"temp/spec_{i + 1}.jpg", spec)
            
            for j in range(3):
                similarity, _ = self.compute_similarity(f"temp/sprite_{j + 1}.jpg", f"temp/spec_{i + 1}.jpg")
                cx, cy = int((x1 + x2) / 2), int((y1 + y2) / 2)
                candidates[j + 1].append((similarity, cx, cy, i))

        # 全局贪心分配
        for key in candidates:
            candidates[key].sort(key=lambda t: t[0], reverse=True)

        selected = {}
        used_boxes = set()
        
        while len(selected) < 3:
            best = None
            best_sprite = None
            
            # 找到所有候选中的全局最优且未用过的框
            for sp in (1, 2, 3):
                if sp in selected:
                    continue
                for item in candidates.get(sp, []):
                    score, cx, cy, bi = item
                    if bi in used_boxes:
                        continue
                    if best is None or score > best[0]:
                        best = (score, cx, cy, bi)
                        best_sprite = sp
                    break
            
            if best is None or best[0] < self.min_similarity:
                logger.warning("高置信度候选不足，使用低分候选继续")
                break
            
            # 选中当前全局最优
            selected[best_sprite] = {
                'similarity': best[0],
                'x': best[1],
                'y': best[2],
                'box_idx': best[3]
            }
            used_boxes.add(best[3])

        # 点击选中的目标
        for sprite_id, result in selected.items():
            x, y = result['x'], result['y']
            
            # 获取slideBg元素的尺寸
            slide_bg = self.page.ele('xpath://*[@id="slideBg"]')
            if not slide_bg:
                continue
                
            style = slide_bg.attr('style')
            width = self.get_width_from_style(style)
            height = self.get_height_from_style(style)
            
            if not width or not height:
                continue
            
            width_raw, height_raw = 672, 480
            x_offset, y_offset = 0.0, 0.0
            final_x = int(x_offset + x / width_raw * float(width))
            final_y = int(y_offset + y / height_raw * float(height))
            
            # 边界夹紧
            final_x = max(2, min(int(width) - 3, final_x))
            final_y = max(2, min(int(height) - 3, final_y))
            
            # 添加微抖动
            final_x += random.randint(1, 2)
            final_y += random.randint(1, 2)
            
            # 使用JS点击
            js = f"""
            var e=document.getElementById('slideBg');
            if(e){{
              var r=e.getBoundingClientRect();
              var cx=Math.round(r.left+{final_x});
              var cy=Math.round(r.top+{final_y});
              ['mousemove','mousedown','mouseup','click'].forEach(function(t){{
                e.dispatchEvent(new MouseEvent(t,{{bubbles:true,cancelable:true,view:window,clientX:cx,clientY:cy}}));
              }});
            }}
            """
            self.page.run_js(js)
            logger.info(f"点击验证码目标 {sprite_id} 位于 ({final_x},{final_y})，匹配率：{result['similarity']}")
            time.sleep(0.5)
        
        # 提交验证码
        confirm = self.page.ele('xpath://*[@id="tcStatus"]/div[2]/div[2]/div/div')
        if confirm:
            logger.info("提交验证码")
            confirm.click()
            time.sleep(5)
            return self.check_captcha_success()
        
        return False

    def process_captcha(self) -> None:
        """
        处理滑动验证码，若未触发验证码则跳过。
        完全按照示例代码逻辑实现
        """
        # 此时self.page已经是验证码iframe页面，直接处理
        if not self.page:
            logger.info("验证码页面不存在，跳过处理。")
            return

        try:
            while True:
                # 在iframe内部直接下载验证码图片
                bg_url = self._find_background_image_url()
                sprite_url = self._find_sprite_image_url()
                
                # 下载图片
                if bg_url:
                    logger.info(f"找到背景图片URL")
                    self.download_image(bg_url, "captcha.jpg")
                else:
                    logger.warning("未找到背景图片URL")
                
                if sprite_url:
                    logger.info(f"找到sprite图片URL")
                    self.download_image(sprite_url, "sprite.jpg")
                else:
                    logger.warning("未找到sprite图片URL")
                
                # 检查是否成功下载了图片
                if not (os.path.exists("temp/captcha.jpg") and os.path.exists("temp/sprite.jpg")):
                    logger.warning("验证码图片下载失败")
                    continue
                
                if self.check_captcha():
                    logger.info("开始识别验证码")
                    captcha = cv2.imread("temp/captcha.jpg")
                    # 基于整图模板匹配的快速定位（兜底），与 det 检测结果融合
                    self.prepare_icons()
                    global_result = self.locate_icons_by_template(captcha.copy())
                    with open("temp/captcha.jpg", 'rb') as f:
                        captcha_b = f.read()
                    # 检测并短暂等待，确保文件系统可读
                    bboxes = self.det.detection(captcha_b)
                    time.sleep(0.1)
                    if not bboxes:
                        logger.warning("det.detection 未返回框，尝试刷新")
                        try:
                            reload = self.page.ele('xpath://*[@id="reload"]')
                            time.sleep(1.0)
                            reload.click()
                            time.sleep(2.0)
                            # 刷新后重新下载验证码图片
                            self._download_captcha_images()
                            continue
                        except Exception:
                            logger.warning("刷新按钮不存在，使用 JS 重载。")
                            try:
                                self.page.run_js("location.reload()")
                                time.sleep(2.5)
                                # 重载后重新下载验证码图片
                                self._download_captcha_images()
                                continue
                            except Exception:
                                logger.warning("JS 重载失败，返回上层并重开验证码。")
                                break
                    # NMS 去重，降低重叠框干扰
                    try:
                        bboxes = self._nms([list(map(int, b)) for b in bboxes], iou_thresh=0.35, max_keep=8)
                    except Exception:
                        pass

                    # 为每个 sprite 构建候选集 (score, cx, cy, box_idx)
                    candidates = {1: [], 2: [], 3: []}
                    for i, box in enumerate(bboxes):
                        x1, y1, x2, y2 = box
                        spec = captcha[y1:y2, x1:x2]
                        # 预处理以稳定特征
                        spec = self._preprocess_gray(spec)
                        cv2.imwrite(f"temp/spec_{i + 1}.jpg", spec)
                        for j in range(3):
                            similarity, _ = self.compute_similarity(f"temp/sprite_{j + 1}.jpg", f"temp/spec_{i + 1}.jpg")
                            cx, cy = int((x1 + x2) / 2), int((y1 + y2) / 2)
                            candidates[j + 1].append((similarity, cx, cy, i))
                            logger.debug(f"候选 {j+1}-{i+1}: 相似度={similarity:.3f}, 位置=({cx},{cy})")

                    # 全局贪心分配：确保不同 sprite 选择不同 bbox，且分数>=阈值
                    for key in candidates:
                        candidates[key].sort(key=lambda t: t[0], reverse=True)

                    selected = {}
                    used_boxes = set()
                    while len(selected) < 3:
                        best = None
                        best_sprite = None
                        # 找到所有候选中的全局最优且未用过的框
                        for sp in (1, 2, 3):
                            if sp in selected:
                                continue
                            for item in candidates.get(sp, []):
                                score, cx, cy, bi = item
                                if bi in used_boxes:
                                    continue
                                if best is None or score > best[0]:
                                    best = (score, cx, cy, bi)
                                    best_sprite = sp
                                break  # 当前 sprite 取其最高候选参与比较
                        if best is None:
                            logger.warning("没有找到合适的候选，使用低分候选继续")
                            break
                        elif best[0] < self.min_similarity:
                            logger.warning(f"最高分数 {best[0]:.3f} 低于阈值 {self.min_similarity}，但仍尝试使用")
                        # 选中当前全局最优
                        selected[best_sprite] = {
                            'similarity': best[0],
                            'position': f"{best[1]},{best[2]}"
                        }
                        used_boxes.add(best[3])

                    # 将选择结果写入 result 结构，供后续点击复用（并融合全图模板匹配结果）
                    result = {}
                    # 将已有选择写入
                    for sp in selected:
                        result[f"sprite_{sp}.similarity"] = selected[sp]['similarity']
                        result[f"sprite_{sp}.position"] = selected[sp]['position']
                    # 对缺失的 sprite，用其最高候选补齐（即便分数较低，或复用同一框），尽量尝试
                    for sp in (1, 2, 3):
                        if sp in selected:
                            continue
                        if candidates.get(sp):
                            score, cx, cy, bi = candidates[sp][0]
                            result[f"sprite_{sp}.similarity"] = score
                            result[f"sprite_{sp}.position"] = f"{cx},{cy}"
                    # 融合整图模板匹配结果（若分数更高则覆盖）
                    for sp in (1, 2, 3):
                        gk = f"sprite_{sp}.similarity"
                        gp = f"sprite_{sp}.position"
                        if gk in global_result and gp in global_result:
                            gscore = float(global_result[gk])
                            if gk not in result or gscore > float(result[gk] or 0):
                                result[gk] = gscore
                                result[gp] = global_result[gp]
                    # 检查结果是否有效
                    if self.check_answer(result) and len(result) >= 6:  # 至少要有3个sprite的位置和相似度
                        logger.info(f"验证码识别成功，共识别到 {len(result)//2} 个目标")
                        for i in range(3):
                            similarity_key = f"sprite_{i + 1}.similarity"
                            position_key = f"sprite_{i + 1}.position"
                            if position_key in result:
                                positon = result[position_key]
                                logger.info(f"图案 {i + 1} 位于 ({positon})，匹配率：{result[similarity_key]}")
                                slideBg = self.page.ele('xpath://*[@id="slideBg"]', timeout=5)
                                style = slideBg.attr("style")
                                x, y = int(positon.split(",")[0]), int(positon.split(",")[1])
                                width_raw, height_raw = captcha.shape[1], captcha.shape[0]
                                # 优先从style读取
                                width = float(self.get_width_from_style(style)) if style else 0.0
                                height = float(self.get_height_from_style(style)) if style else 0.0
                                # 兜底：clientWidth / clientHeight
                                if width == 0 or height == 0:
                                    try:
                                        w_js = self.page.run_js("var e=document.getElementById('slideBg'); return e? e.clientWidth : 0")
                                        h_js = self.page.run_js("var e=document.getElementById('slideBg'); return e? e.clientHeight : 0")
                                        width = float(w_js or 0)
                                        height = float(h_js or 0)
                                    except Exception:
                                        pass
                                # 兜底：getBoundingClientRect
                                if width == 0 or height == 0:
                                    try:
                                        w2 = self.page.run_js("var e=document.getElementById('slideBg'); if(!e) return 0; var r=e.getBoundingClientRect(); return Math.round(r.width)||0")
                                        h2 = self.page.run_js("var e=document.getElementById('slideBg'); if(!e) return 0; var r=e.getBoundingClientRect(); return Math.round(r.height)||0")
                                        width = float(w2 or 0)
                                        height = float(h2 or 0)
                                    except Exception:
                                        pass
                                if width == 0 or height == 0:
                                    logger.error("解析 slideBg 宽高失败，刷新重试")
                                    continue

                                # DrissionPage 的 element.click(x, y) 使用相对元素左上角的偏移
                                x_offset, y_offset = 0.0, 0.0
                                final_x, final_y = int(x_offset + x / width_raw * width), int(y_offset + y / height_raw * height)

                                # 边界夹紧，避免越界
                                final_x = max(2, min(int(width) - 3, final_x))
                                final_y = max(2, min(int(height) - 3, final_y))

                                # 给点击加入 1~2px 的微抖动，避免固定像素触发规则
                                final_x += random.randint(1, 2)
                                final_y += random.randint(1, 2)

                                # 相似度为0则跳过，避免无效点击
                                try:
                                    sim_val = float(result.get(similarity_key, 0) or 0)
                                except Exception:
                                    sim_val = 0.0
                                if sim_val <= 0:
                                    logger.warning("相似度为0，本次不点击，刷新重试")
                                    continue

                                # 使用 JS 在元素内的绝对位置触发点击，避免不同实现对偏移原点的差异
                                try:
                                    logger.debug(f"slideBg size=({width},{height}), click=({final_x},{final_y}), img=({width_raw},{height_raw})")
                                    js = """
var e=document.getElementById('slideBg');
if(e){
  var r=e.getBoundingClientRect();
  var cx=Math.round(r.left+__X__);
  var cy=Math.round(r.top+__Y__);
  ['mousemove','mousedown','mouseup','click'].forEach(function(t){
    e.dispatchEvent(new MouseEvent(t,{bubbles:true,cancelable:true,view:window,clientX:cx,clientY:cy}));
  });
}
""".replace('__X__', str(final_x)).replace('__Y__', str(final_y))
                                    self.page.run_js(js)
                                except Exception as _e:
                                    logger.exception(f"JS 点击触发失败: {_e}")
                        confirm = self.page.ele('xpath://*[@id="tcStatus"]/div[2]/div[2]/div/div')
                        logger.info("提交验证码")
                        confirm.click()
                        time.sleep(5)
                        result_ele = self.page.ele('xpath://*[@id="tcOperation"]')
                        cls_val = result_ele.attr("class") if result_ele else ""
                        if isinstance(cls_val, str) and 'show-success' in cls_val:
                            logger.info("验证码通过")
                            return
                        else:
                            logger.warning("验证码未通过，尝试刷新重试")
                            try:
                                reload = self.page.ele('xpath://*[@id="reload"]')
                                time.sleep(1.0)
                                reload.click()
                                time.sleep(2.0)
                                # 刷新后重新下载验证码图片
                                self._download_captcha_images()
                                continue
                            except Exception:
                                try:
                                    self.page.run_js("location.reload()")
                                    time.sleep(2.5)
                                    # 重载后重新下载验证码图片
                                    self._download_captcha_images()
                                    continue
                                except Exception:
                                    logger.warning("刷新失败，重新进入下一轮")
                                    continue
                    else:
                        logger.warning("验证码识别失败，尝试随机点击策略")
                        # 随机点击策略：在验证码区域随机选择3个点
                        slideBg = self.page.ele('xpath://*[@id="slideBg"]', timeout=5)
                        if slideBg:
                            style = slideBg.attr("style")
                            width = float(self.get_width_from_style(style)) if style else 300
                            height = float(self.get_height_from_style(style)) if style else 200
                            
                            # 在验证码区域随机选择3个点
                            for i in range(3):
                                x = random.randint(50, int(width) - 50)
                                y = random.randint(50, int(height) - 50)
                                logger.info(f"随机点击点 {i+1}: ({x}, {y})")
                                
                                # 执行点击
                                try:
                                    js = f"""
var e=document.getElementById('slideBg');
if(e){{
  var r=e.getBoundingClientRect();
  var cx=Math.round(r.left+{x});
  var cy=Math.round(r.top+{y});
  ['mousemove','mousedown','mouseup','click'].forEach(function(t){{
    e.dispatchEvent(new MouseEvent(t,{{bubbles:true,cancelable:true,view:window,clientX:cx,clientY:cy}}));
  }});
}}
"""
                                    self.page.run_js(js)
                                    time.sleep(0.5)
                                except Exception as e:
                                    logger.warning(f"随机点击失败: {e}")
                        else:
                            logger.warning("未找到验证码区域，无法执行随机点击")
                        # 使用已有（可能为低分或重复）点位尽量点击提交
                        for i in range(3):
                            similarity_key = f"sprite_{i + 1}.similarity"
                            position_key = f"sprite_{i + 1}.position"
                            positon = result.get(position_key)
                            sim_val = result.get(similarity_key, 0)
                            if not positon:
                                continue
                            slideBg = self.page.ele('xpath://*[@id="slideBg"]', timeout=5)
                            if not slideBg:
                                break
                            style = slideBg.attr("style")
                            x, y = map(int, positon.split(","))
                            width_raw, height_raw = captcha.shape[1], captcha.shape[0]
                            width = float(self.get_width_from_style(style)) if style else 0.0
                            height = float(self.get_height_from_style(style)) if style else 0.0
                            if width == 0 or height == 0:
                                try:
                                    w_js = self.page.run_js("var e=document.getElementById('slideBg'); return e? e.clientWidth : 0")
                                    h_js = self.page.run_js("var e=document.getElementById('slideBg'); return e? e.clientHeight : 0")
                                    width = float(w_js or 0)
                                    height = float(h_js or 0)
                                except Exception:
                                    pass
                            if width == 0 or height == 0:
                                continue
                            final_x = int(x / width_raw * width)
                            final_y = int(y / height_raw * height)
                            final_x = max(2, min(int(width) - 3, final_x))
                            final_y = max(2, min(int(height) - 3, final_y))
                            final_x += random.randint(1, 2)
                            final_y += random.randint(1, 2)
                            try:
                                js = """
var e=document.getElementById('slideBg');
if(e){
  var r=e.getBoundingClientRect();
  var cx=Math.round(r.left+__X__);
  var cy=Math.round(r.top+__Y__);
  ['mousemove','mousedown','mouseup','click'].forEach(function(t){
    e.dispatchEvent(new MouseEvent(t,{bubbles:true,cancelable:true,view:window,clientX:cx,clientY:cy}));
  });
}
""".replace('__X__', str(final_x)).replace('__Y__', str(final_y))
                                self.page.run_js(js)
                            except Exception:
                                pass
                        confirm = self.page.ele('xpath://*[@id="tcStatus"]/div[2]/div[2]/div/div')
                        if confirm:
                            logger.info("提交验证码(低分候选)")
                            try:
                                confirm.click()
                                time.sleep(5)
                            except Exception:
                                pass
                        result_ele = self.page.ele('xpath://*[@id="tcOperation"]')
                        cls_val = result_ele.attr("class") if result_ele else ""
                        if isinstance(cls_val, str) and 'show-success' in cls_val:
                            logger.info("验证码通过(低分)")
                            return
                        else:
                            logger.warning("低分候选提交未通过，刷新重试")
                            try:
                                reload = self.page.ele('xpath://*[@id="reload"]')
                                time.sleep(1.0)
                                reload.click()
                                time.sleep(2.0)
                                # 刷新后重新下载验证码图片
                                self._download_captcha_images()
                                continue
                            except Exception:
                                try:
                                    self.page.run_js("location.reload()")
                                    time.sleep(2.5)
                                    # 重载后重新下载验证码图片
                                    self._download_captcha_images()
                                    continue
                                except Exception:
                                    logger.warning("刷新失败，重新进入下一轮")
                                    continue
                else:
                    logger.warning("验证码资源质量低，本轮仍尝试提交")
                # 不在识别阶段刷新；提交后若未通过，再由外层循环刷新
                    
        except Exception as e:
            logger.error(f"处理验证码时发生异常: {e}")

    def login(self, username: str, password: str) -> bool:
        """登录"""
        try:
            logger.info("开始登录流程...")
            self.page.get("https://app.rainyun.com/auth/login")
            self.page.wait.load_start()

            # 查找登录元素，使用更宽松的选择器
            username_input = self.page.ele('xpath://input[@name="login-field"]', timeout=10)
            password_input = self.page.ele('xpath://input[@name="login-password"]', timeout=10)
            login_button = self.page.ele('xpath://button[@class="btn btn-primary btn-block"]', timeout=10)

            if not all([username_input, password_input, login_button]):
                logger.error("页面加载超时，无法找到登录元素！")
                logger.error(f"当前页面URL: {self.page.url}")
                logger.error(f"页面标题: {self.page.title}")
                return False

            # 填写登录信息
            username_input.clear()
            username_input.input(username)
            time.sleep(1)

            password_input.clear()
            password_input.input(password)
            time.sleep(1)

            logger.info("已填写登录信息，点击登录按钮")
            login_button.click()
            logger.info(f"点击登录按钮后，当前页面URL: {self.page.url}")

            # 等待页面响应
            time.sleep(3)
            
            # 先检查是否已经跳转到dashboard
            if "dashboard" in self.page.url:
                logger.info("登录成功，已跳转到仪表板页面")
            else:
                # 检查是否出现验证码
                if self.wait_captcha_ready():
                    logger.warning("触发登录验证码！")
                    # 下载验证码图片
                    if self.download_captcha_img():
                        # 获取iframe页面对象
                        iframe_page = self.page.get_frame('tcaptcha_iframe_dy')
                        if iframe_page:
                            # 临时切换页面处理验证码
                            temp_page = self.page
                            self.page = iframe_page
                            self.process_captcha()
                            self.page = temp_page
                            # 等待登录完成并验证登录状态
                            time.sleep(5)
                    else:
                        logger.warning("验证码图片下载失败")
                else:
                    logger.info("未触发登录验证码")

            # 检查是否成功跳转到仪表板或已登录状态
            logger.info(f"登录处理完成，当前页面URL: {self.page.url}")
            if "dashboard" in self.page.url or self.check_login_status(username, password):
                logger.info("登录成功！")
                return True
            else:
                logger.warning("登录可能失败，检查页面状态")
                return False

        except Exception as e:
            logger.error(f"登录过程中出现异常: {e}")
            return False

    def do_sign_in(self) -> bool:
        """执行签到操作"""
        try:
            logger.info("开始执行签到操作...")
            self.page.get("https://app.rainyun.com/account/reward/earn")
            time.sleep(2)

            # 判断今日是否已签到
            sign_label = self.page.ele('xpath://span[contains(text(), "每日签到")]/following-sibling::span[1]', timeout=10)

            if sign_label:
                status_text = sign_label.text.strip()
                if status_text == "已完成":
                    # 获取当前积分
                    points_element = self.page.ele(
                        'xpath://*[@id="app"]/div[1]/div[3]/div[2]/div/div/div[2]/div[1]/div[1]/div/p/div/h3', timeout=5
                    )
                    current_points = int(''.join(re.findall(r'\d+', points_element.text))) if points_element else 0
                    logger.info(f"今日已签到，当前积分: {current_points} | 约为 {current_points / 2000:.2f} 元")
                    return True

            # 如果未签到，则点击赚取积分
            earn_button = self.page.ele(
                'xpath://*[@id="app"]/div[1]/div[3]/div[2]/div/div/div[2]/div[2]/div/div/div/div[1]/div/div[1]/div/div[1]/div/span[2]/a', timeout=10
            )

            if earn_button:
                logger.info("点击签到按钮...")
                earn_button.click()
                logger.info(f"点击签到按钮后，当前页面URL: {self.page.url}")
                
                # 等待页面响应
                time.sleep(3)
                
                # 检查是否出现验证码
                if self.wait_captcha_ready():
                    logger.warning("触发签到验证码！")
                    # 下载验证码图片
                    if self.download_captcha_img():
                        iframe_page = self.page.get_frame('tcaptcha_iframe_dy')
                        if iframe_page:
                            temp_page = self.page
                            self.page = iframe_page
                            self.process_captcha()
                            self.page = temp_page
                    else:
                        logger.warning("验证码图片下载失败")
                else:
                    logger.info("未触发签到验证码")

                time.sleep(5)
                logger.info(f"签到处理完成，当前页面URL: {self.page.url}")

            # 获取签到后的积分
            points_element = self.page.ele(
                'xpath://*[@id="app"]/div[1]/div[3]/div[2]/div/div/div[2]/div[1]/div[1]/div/p/div/h3'
            )
            current_points = int(''.join(re.findall(r'\d+', points_element.text))) if points_element else 0
            self._log('success', f"签到任务执行成功，当前积分: {current_points} | 约为 {current_points / 2000:.2f} 元")
            
            return True

        except Exception as e:
            logger.error(f"签到过程中出现异常: {e}")
            # 即使出现异常也要清理temp目录
            return False

    def run(self) -> None:
        """运行主程序"""
        try:
            # 读取配置
            user, pwd = self.read_config()
            logger.info(f"已加载用户配置: {user}")

            # 初始化OCR
            self.init_ocr()

            # 检查登录状态
            logger.info("检查登录状态")
            if not self.check_login_status(user, pwd):
                logger.info("未登录，开始登录流程")
                if not self.login(user, pwd):
                    logger.error("登录失败，程序退出")
                    return
            else:
                logger.info("已登录，跳过登录流程")

            # 执行签到
            logger.info("开始执行签到任务")
            if self.do_sign_in():
                logger.info("签到任务完成")
            else:
                logger.error("签到任务失败")

        except Exception as e:
            logger.error(f"程序运行异常: {e}")
        finally:
            self.cleanup()

    def cleanup(self) -> None:
        """清理资源"""
        self.cleanup_temp_dir()
        logger.info("雨云任务清理完成")
