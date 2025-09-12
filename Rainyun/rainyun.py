import os
import random
import re
import time
from typing import Optional
import cv2
import ddddocr
import requests
from loguru import logger
from DrissionPage import ChromiumOptions, Chromium


class RainyunSigner:
    """雨云签到工具"""

    def __init__(self, debug: bool = False):
        self.debug = debug
        self.timeout = 15
        self.ver = "1.0-DP"
        self.ocr = None
        self.det = None
        self.browser = None
        self.page = None
        self._last_captcha_urls = {"bg": "", "sprite": ""}
        # 识别相关阈值（可按需调参）
        self.min_similarity = 0.58
        # 配置日志
        self._setup_logger()
        # 显示信息
        self._show_banner()

    def _setup_logger(self) -> None:
        """配置日志，显示行号和方法名"""
        pass

    def _show_banner(self) -> None:
        """显示程序横幅"""
        logger.info("------------------------------------------------------------------")
        logger.info(f"雨云签到工具 v{self.ver} by Viper373 ~ (DrissionPage版)")
        logger.info("Github发布页: https://github.com/Viper373/AutoTasks")
        logger.info("------------------------------------------------------------------")

    def read_config(self) -> tuple[str, str]:
        """从环境变量读取凭据。"""
        env_user = os.getenv('RAINYUN_USERNAME')
        env_pass = os.getenv('RAINYUN_PASSWORD')
        if env_user and env_pass:
            return env_user, env_pass
        raise RuntimeError('未通过环境变量获得 RainYun 凭据')

    def init_browser(self) -> None:
        """初始化DrissionPage浏览器 - 修复版本"""
        try:
            logger.info("正在初始化浏览器...")

            # 创建浏览器选项
            co = ChromiumOptions()

            # 基础设置
            co.set_argument('--no-sandbox')
            co.set_argument('--disable-gpu')
            co.set_argument('--disable-dev-shm-usage')
            co.set_argument('--disable-setuid-sandbox')
            co.set_argument('--disable-extensions')
            co.set_argument('--disable-plugins')
            co.set_argument('--log-level=3')
            co.set_argument('--silent')
            co.set_argument('--disable-logging')
            co.set_argument('--disable-web-security')
            co.set_argument('--allow-running-insecure-content')
            co.set_argument('--ignore-certificate-errors')
            co.set_argument('--ignore-ssl-errors')
            co.set_argument('--ignore-certificate-errors-spki-list')

            # 窗口设置
            co.set_argument('--window-size=1920,1080')
            co.set_argument('--start-maximized')

            # 如果不是调试模式，设置无头模式
            if not self.debug:
                co.headless()
                logger.info("使用无头模式启动浏览器")
            else:
                logger.info("使用有头模式启动浏览器（调试模式）")

            # 设置用户代理
            co.set_user_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

            # 尝试指定Chrome路径（如果系统中有多个版本）
            possible_chrome_paths = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                r"C:\Users\{}\AppData\Local\Google\Chrome\Application\chrome.exe".format(os.getenv('USERNAME', '')),
                "chrome",  # 系统PATH中的chrome
                "chromium",  # 系统PATH中的chromium
            ]

            chrome_path = None
            for path in possible_chrome_paths:
                if os.path.exists(path) or path in ["chrome", "chromium"]:
                    chrome_path = path
                    break

            if chrome_path and os.path.exists(chrome_path):
                co.set_browser_path(chrome_path)
                logger.info(f"使用Chrome路径: {chrome_path}")

            # 设置端口范围，避免端口冲突
            co.set_argument('--remote-debugging-port=0')  # 自动分配端口

            # 创建浏览器实例
            logger.info("正在启动浏览器进程...")
            self.browser = Chromium(co)

            # 获取页面对象
            self.page = self.browser.latest_tab

            if self.page is None:
                raise Exception("无法获取浏览器页面对象")

            logger.info("浏览器初始化成功")

            # 测试浏览器是否正常工作
            logger.info("正在测试浏览器连接...")
            self.page.get("about:blank")
            logger.info("浏览器测试成功")

        except Exception as e:
            logger.error(f"初始化浏览器失败: {e}")
            logger.info("尝试使用最简配置重新初始化...")

            try:
                # 最简配置重试
                co_simple = ChromiumOptions()
                if not self.debug:
                    co_simple.headless()
                co_simple.set_argument('--no-sandbox')
                co_simple.set_argument('--disable-dev-shm-usage')

                self.browser = Chromium(co_simple)
                self.page = self.browser.latest_tab

                if self.page is None:
                    raise Exception("简化配置也无法获取页面对象")

                logger.info("使用简化配置初始化成功")

            except Exception as e2:
                logger.error(f"简化配置也失败: {e2}")

                # 最后尝试：完全默认配置
                try:
                    logger.info("尝试使用完全默认配置...")
                    self.browser = Chromium()
                    self.page = self.browser.latest_tab

                    if self.page is None:
                        raise Exception("默认配置也无法获取页面对象")

                    logger.info("使用默认配置初始化成功")
                except Exception as e3:
                    logger.error(f"所有初始化方式都失败了: {e3}")
                    logger.error("请检查以下问题：")
                    logger.error("1. 是否正确安装了Chrome或Chromium浏览器")
                    logger.error("2. 是否有其他程序占用了调试端口")
                    logger.error("3. 是否有防火墙或安全软件阻止了浏览器启动")
                    logger.error("4. 尝试以管理员身份运行程序")
                    raise

    def init_ocr(self) -> None:
        """初始化OCR组件"""
        logger.info("初始化 ddddocr")
        self.ocr = ddddocr.DdddOcr(ocr=True, show_ad=False)
        self.det = ddddocr.DdddOcr(det=True, show_ad=False)

    def check_login_status(self, username: str, password: str) -> bool:
        """
        检查当前是否已登录
        :param username: 用户名
        :param password: 密码
        """
        try:
            user_status = self.page.ele('xpath://span[@class="user-status"]/parent::*//p', timeout=3)
            if user_status:
                user_name = user_status.text
                if username == user_name:
                    logger.info(f"检测到当前登录用户: {user_name}")
                    return True
                else:
                    logger.warning(f"检测到当前登录用户: {user_name}，与预期用户: {username} 不符，需要重新登录")
                    # 先退出当前用户
                    try:
                        user_info = user_status.parent().parent('xpath://div')
                        user_info.click()
                        time.sleep(1)
                        exit_login = user_info.ele('xpath://../following-sibling::ul/li[last()]')
                        exit_login.click()
                        time.sleep(2)
                        logger.info("已退出当前用户，等待主程序重新登录")
                    except Exception as e:
                        logger.warning(f"退出登录时出现异常: {e}")
                    return False

            return False
        except Exception as e:
            logger.debug(f"检查登录状态时出现异常: {e}")
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

    def wait_captcha_ready(self, max_wait: float = 4.0) -> bool:
        """等待验证码图片资源加载完成（背景样式与小图 naturalWidth>0）"""
        start = time.time()
        while time.time() - start < max_wait:
            slideBg = self.page.ele('xpath://*[@id="slideBg"]')
            sprite = self.page.ele('xpath://*[@id="instruction"]/div/img')
            style = slideBg.attr('style') if slideBg else None
            ok_style = bool(style and 'url(' in style)
            try:
                nw = self.page.run_js("var i=document.querySelector('#instruction img'); return i? i.naturalWidth:0")
            except Exception:
                nw = 0
            if ok_style and nw and nw > 0:
                return True
            time.sleep(0.2)
        return False

    # 图像预处理，提升特征稳定性
    def _preprocess_gray(self, img):
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

    def download_captcha_img(self) -> None:
        """下载验证码相关图片"""
        # 清理temp目录
        if os.path.exists("temp"):
            for filename in os.listdir("temp"):
                file_path = os.path.join("temp", filename)
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.remove(file_path)

        # 等待资源就绪
        if not self.wait_captcha_ready(4.0):
            logger.warning("验证码资源未就绪，稍后重试")
            time.sleep(0.8)

        # 下载背景图片
        slideBg = self.page.ele('xpath://*[@id="slideBg"]')
        if slideBg:
            img1_style = slideBg.attr('style')
            img1_url = self.get_url_from_style(img1_style)
            if img1_url:
                if img1_url.startswith("//"):
                    img1_url = "https:" + img1_url
                logger.info("开始下载验证码图片(1)")
                self.download_image(img1_url, "captcha.jpg")

        # 下载小图标
        sprite = self.page.ele('xpath://*[@id="instruction"]/div/img')
        if sprite:
            img2_url = sprite.attr('src')
            if img2_url:
                if img2_url.startswith("//"):
                    img2_url = "https:" + img2_url
                logger.info("开始下载验证码图片(2)")
                self.download_image(img2_url, "sprite.jpg")

    def check_captcha(self) -> bool:
        """按示例逻辑：切三张子图并用 OCR 过滤明显无效的验证码。"""
        if not os.path.exists("temp/sprite.jpg"):
            return False

        raw = cv2.imread("temp/sprite.jpg")
        if raw is None:
            return False

        try:
            w = raw.shape[1]
            invalid_cnt = 0
            for i in range(3):
                temp = raw[:, w // 3 * i: w // 3 * (i + 1)]
                if temp.size == 0:
                    return False
                cv2.imwrite(f"temp/sprite_{i + 1}.jpg", temp)
                with open(f"temp/sprite_{i + 1}.jpg", mode="rb") as f:
                    temp_rb = f.read()
                if self.ocr.classification(temp_rb) in ["0", "1"]:
                    invalid_cnt += 1
            # 放宽：仅当全部被判为 0/1 时才认为识别率很低
            return invalid_cnt < 3
        except Exception as e:
            logger.exception(f"验证码切割/检测异常: {e}")
            return False

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

        # 融合：偏向 SIFT，模板匹配作为补充
        final_score = max(sift_score, tm_score * 0.9)
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

    def process_captcha(self) -> None:
        """
        处理滑动验证码，若未触发验证码则跳过。
        完全按照示例代码逻辑实现
        """
        try:
            # 尝试获取验证码元素
            slideBg = self.page.ele('xpath://*[@id="slideBg"]', timeout=5)
        except:
            logger.info("未触发验证码，跳过处理。")
            return

        if not slideBg:
            logger.info("验证码元素不存在，跳过处理。")
            return

        try:
            while True:
                self.download_captcha_img()
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
                            time.sleep(1.0)
                            continue
                        except Exception:
                            logger.warning("刷新按钮不存在，使用 JS 重载 iframe。")
                            try:
                                self.page.run_js("location.reload()")
                                time.sleep(1.5)
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
                        if best is None or best[0] < self.min_similarity:
                            logger.warning("高置信度候选不足，使用低分候选继续")
                            break
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
                    if self.check_answer(result):
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
                                time.sleep(1.0)
                                continue
                            except Exception:
                                try:
                                    self.page.run_js("location.reload()")
                                    time.sleep(1.5)
                                    continue
                                except Exception:
                                    logger.warning("刷新失败，重新进入下一轮")
                                    continue
                    else:
                        logger.warning("验证码识别失败，仍尝试使用可用点位提交")
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
                                time.sleep(1.0)
                                continue
                            except Exception:
                                try:
                                    self.page.run_js("location.reload()")
                                    time.sleep(1.5)
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
        """执行登录操作"""
        try:
            logger.info("开始登录流程...")

            # 等待页面加载并填写登录信息
            username_input = self.page.ele('xpath://input[@name="login-field"]', timeout=self.timeout)
            password_input = self.page.ele('xpath://input[@name="login-password"]', timeout=self.timeout)
            login_button = self.page.ele('xpath://*[@id="app"]/div[1]/div[1]/div/div[2]/fade/div/div/span/form/button', timeout=self.timeout)

            if not all([username_input, password_input, login_button]):
                logger.error("页面加载超时，无法找到登录元素！")
                return False

            # 清空并填写用户名和密码
            username_input.clear()
            username_input.input(username)
            time.sleep(1)

            password_input.clear()
            password_input.input(password)
            time.sleep(1)

            logger.info("已填写登录信息，点击登录按钮")
            login_button.click()

            # 处理登录验证码
            time.sleep(3)
            captcha_iframe = self.page.ele('xpath://*[@id="tcaptcha_iframe_dy"]', timeout=5)
            if captcha_iframe:
                logger.warning("触发登录验证码！")
                # 获取iframe页面对象
                iframe_page = self.page.get_frame('tcaptcha_iframe_dy')
                # 临时切换页面处理验证码
                temp_page = self.page
                self.page = iframe_page
                self.process_captcha()
                self.page = temp_page

            # 等待登录完成并验证登录状态
            time.sleep(5)
            
            # 检查是否成功跳转到仪表板或已登录状态
            if "dashboard" in self.page.url or self.check_login_status(username, password):
                logger.info("登录成功！")
                return True
            else:
                logger.warning("验证码通过但登录可能失败，检查页面状态")
                # 如果还在登录页面，尝试再次检查登录状态
                if "login" in self.page.url:
                    logger.warning("仍在登录页面，登录可能失败")
                    return False
                else:
                    # 如果跳转到了其他页面，可能是登录成功
                    logger.info("页面已跳转，认为登录成功")
                    return True

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
            sign_label = self.page.ele('xpath://span[contains(text(), "每日签到")]/following-sibling::span[1]')

            if sign_label:
                status_text = sign_label.text.strip()
                if status_text == "已完成":
                    # 获取当前积分
                    points_element = self.page.ele(
                        'xpath://*[@id="app"]/div[1]/div[3]/div[2]/div/div/div[2]/div[1]/div[1]/div/p/div/h3'
                    )
                    current_points = int(''.join(re.findall(r'\d+', points_element.text))) if points_element else 0
                    logger.info(f"今日已签到，当前积分: {current_points} | 约为 {current_points / 2000:.2f} 元")
                    return True

            # 如果未签到，则点击赚取积分
            earn_button = self.page.ele(
                'xpath://*[@id="app"]/div[1]/div[3]/div[2]/div/div/div[2]/div[2]/div/div/div/div[1]/div/div[1]/div/div[1]/div/span[2]/a'
            )

            if earn_button:
                logger.info("点击签到按钮...")
                earn_button.click()
                time.sleep(3)

                # 处理签到验证码
                captcha_iframe = self.page.ele('xpath://*[@id="tcaptcha_iframe_dy"]', timeout=5)
                if captcha_iframe:
                    logger.warning("触发签到验证码！")
                    iframe_page = self.page.get_frame('tcaptcha_iframe_dy')
                    temp_page = self.page
                    self.page = iframe_page
                    self.process_captcha()
                    self.page = temp_page
                else:
                    logger.info("未触发签到验证码")

                time.sleep(5)

            # 获取签到后的积分
            points_element = self.page.ele(
                'xpath://*[@id="app"]/div[1]/div[3]/div[2]/div/div/div[2]/div[1]/div[1]/div/p/div/h3'
            )
            current_points = int(''.join(re.findall(r'\d+', points_element.text))) if points_element else 0
            logger.info(f"签到任务执行成功，当前积分: {current_points} | 约为 {current_points / 2000:.2f} 元")
            return True

        except Exception as e:
            logger.error(f"签到过程中出现异常: {e}")
            return False

    def run(self) -> None:
        """运行主程序"""
        try:
            # 读取配置
            user, pwd = self.read_config()
            logger.info(f"已加载用户配置: {user}")

            # 随机延时
            if not self.debug:
                delay_sec = random.randint(0, 3)
                logger.info(f"随机延时等待 {delay_sec} 秒")
                time.sleep(delay_sec)

            # 初始化组件
            self.init_ocr()
            self.init_browser()

            # 加载反检测脚本
            if os.path.exists("stealth.min.js"):
                with open("stealth.min.js", mode="r") as f:
                    js = f.read()
                self.page.run_js_loaded(js)
                logger.info("已加载反检测脚本")

            # 先访问登录页面检查登录状态
            logger.info("检查登录状态")
            self.page.get("https://app.rainyun.com/auth/login")
            time.sleep(2)

            # 检查是否已登录
            if self.check_login_status(user, pwd):
                logger.info("检测到已登录，跳过登录流程")
                login_success = True
            else:
                logger.info("未登录，开始登录流程")
                login_success = self.login(user, pwd)

            # 检查登录结果并执行签到
            if login_success:
                if "dashboard" not in self.page.url:
                    logger.info("正在跳转到仪表板")
                    self.page.get("https://app.rainyun.com/dashboard")
                    time.sleep(2)

                # 执行签到
                self.do_sign_in()
            else:
                logger.error("登录失败！")

        except Exception as e:
            logger.error(f"程序执行出错: {e}")
        finally:
            self.cleanup()

    def cleanup(self) -> None:
        """清理资源"""
        if self.browser:
            try:
                self.browser.quit()
                logger.info("浏览器已关闭")
            except:
                pass


def main():
    """主函数"""
    # 可以在这里设置debug=True来调试浏览器问题
    signer = RainyunSigner(debug=True)
    signer.run()


if __name__ == "__main__":
    main()
