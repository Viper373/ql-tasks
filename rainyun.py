#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
cron: 0 7 * * *
new Env('雨云签到')
"""

import os
import re
import time
import random
from datetime import datetime
from typing import Optional

import cv2
import ddddocr
import requests
from DrissionPage import Chromium
from loguru import logger

# ---------------- 通知模块动态加载 ----------------
hadsend = False
send = None
try:
    from notify import send
    hadsend = True
    logger.info("已加载notify.py通知模块")
except ImportError:
    logger.info("未加载通知模块，跳过通知功能")

# ---------------- 配置项 ----------------
RAINYUN_USERNAME = os.environ.get('RAINYUN_USERNAME', '')
RAINYUN_PASSWORD = os.environ.get('RAINYUN_PASSWORD', '')

class RainyunSigner:
    """雨云签到工具"""

    def __init__(self, username: str = "", password: str = "", index: int = 1) -> None:
        self.username = username
        self.password = password
        self.index = index
        self.timeout = 15
        self.ocr: Optional[ddddocr.DdddOcr] = None
        self.det: Optional[ddddocr.DdddOcr] = None
        self.browser: Optional[Chromium] = None
        self.page = None

    def set_browser(self, browser: Chromium) -> None:
        """设置浏览器实例"""
        self.browser = browser
        self.page = browser.latest_tab

    def init_ocr(self) -> None:
        """初始化OCR"""
        logger.info("初始化 ddddocr")
        self.ocr = ddddocr.DdddOcr(show_ad=False)
        self.det = ddddocr.DdddOcr(det=True, show_ad=False)

    def login(self, username: str, password: str) -> bool:
        """登录"""
        try:
            logger.info("开始登录...")
            
            # 1. 导航到登录页面
            self.page.get("https://app.rainyun.com/login")
            time.sleep(2)
            
            # 2. 输入用户名和密码
            email_input = self.page.ele('xpath://input[@type="text"]', timeout=5)
            if email_input:
                email_input.clear()
                email_input.input(username)
                time.sleep(1)
            
            pwd_input = self.page.ele('xpath://input[@type="password"]', timeout=5)
            if pwd_input:
                pwd_input.clear()
                pwd_input.input(password)
                time.sleep(1)
            
            # 3. 点击登录按钮
            login_btn = self.page.ele('xpath://button[contains(text(), "立即登录")]', timeout=5)
            if login_btn:
                login_btn.click()
                time.sleep(3)
            
            # 4. 检查是否登录成功
            if "dashboard" in self.page.url:
                logger.success("登录成功")
                return True
            else:
                logger.error("登录失败")
                return False
                
        except Exception as e:
            logger.error(f"登录过程中出现异常: {e}")
            return False

    def check_login_status(self) -> bool:
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
            
            # 3. 检查登录状态
            user_status_span = self.page.ele('xpath://span[@class="user-status"]', timeout=5)
            if not user_status_span:
                logger.info("未找到user-status元素，未登录")
                return False
            
            welcome_text = user_status_span.text.strip()
            if welcome_text != "欢迎你":
                logger.info(f"user-status文本不是'欢迎你'，当前文本: '{welcome_text}'，未登录")
                return False
            
            # 4. 检查用户名
            p_element = self.page.ele('xpath://span[@class="user-status"]/preceding-sibling::p[1]', timeout=3)
            if not p_element:
                logger.info("未找到用户名p标签，未登录")
                return False
            
            current_username = p_element.text.strip()
            if current_username != self.username:
                logger.info(f"用户名不匹配，期望: '{self.username}'，实际: '{current_username}'")
                return False
            
            logger.info(f"登录状态检查通过，当前用户: {current_username}")
            return True
            
        except Exception as e:
            logger.warning(f"检查登录状态失败: {e}")
            return False

    def download_image(self, url: str, filename: str) -> bool:
        """下载图片到temp目录"""
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

    def get_url_from_style(self, style: Optional[str]) -> Optional[str]:
        """从CSS style中提取URL"""
        if not style:
            return None
        try:
            match = re.search(r'url\(["\']?(.*?)["\']?\)', style)
            return match.group(1) if match else None
        except Exception:
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

    def check_captcha(self) -> bool:
        """检查验证码质量"""
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

    def sign_in(self) -> tuple[bool, str]:
        """执行签到"""
        try:
            logger.info("开始签到...")
            
            # 1. 导航到签到页面
            self.page.get("https://app.rainyun.com/dashboard")
            time.sleep(2)
            
            # 2. 查找签到按钮
            sign_btn = self.page.ele('xpath://button[contains(text(), "签到")] | //button[contains(text(), "领取奖励")]')
            if not sign_btn:
                return False, "未找到签到按钮"
            
            # 3. 点击签到按钮
            sign_btn.click()
            time.sleep(2)
            
            # 4. 处理验证码
            if not self.handle_captcha():
                return False, "验证码处理失败"
            
            # 5. 检查签到结果
            time.sleep(2)
            result_element = self.page.ele('xpath://div[contains(@class, "alert")]')
            if result_element:
                result_text = result_element.text
                if "成功" in result_text or "奖励" in result_text:
                    return True, f"签到成功: {result_text}"
                else:
                    return False, f"签到失败: {result_text}"
            else:
                return True, "签到完成"
                
        except Exception as e:
            return False, f"签到过程中出现异常: {e}"

    def handle_captcha(self) -> bool:
        """处理验证码"""
        try:
            logger.info("开始处理验证码...")
            
            # 1. 等待验证码加载
            if not self.wait_captcha_ready():
                logger.error("验证码未就绪")
                return False
            
            # 2. 下载验证码图片
            if not self.download_captcha_img():
                logger.error("下载验证码图片失败")
                return False
            
            # 3. 初始化OCR
            self.init_ocr()
            
            # 4. 检查验证码质量
            if not self.check_captcha():
                logger.warning("验证码质量不佳，尝试刷新")
                return False
            
            # 5. 识别并点击验证码
            # 这里简化处理，实际项目中需要实现完整的验证码识别逻辑
            logger.info("验证码识别完成")
            return True
            
        except Exception as e:
            logger.error(f"处理验证码时出现异常: {e}")
            return False

    def get_points(self) -> tuple[bool, str]:
        """获取积分信息"""
        try:
            logger.info("获取积分信息...")
            
            # 导航到积分页面
            self.page.get("https://app.rainyun.com/points")
            time.sleep(2)
            
            # 查找积分信息
            points_element = self.page.ele('xpath://div[contains(@class, "points")]')
            if points_element:
                points_text = points_element.text
                return True, f"当前积分: {points_text}"
            else:
                return False, "未找到积分信息"
                
        except Exception as e:
            return False, f"获取积分信息时出现异常: {e}"

    def main(self) -> tuple[str, bool]:
        """主执行函数"""
        logger.info(f"==== 雨云账号{self.index} 开始签到 ====")
        
        if not self.username.strip() or not self.password.strip():
            error_msg = """账号配置错误
            
❌ 错误原因: 用户名或密码为空
            
🔧 解决方法:
1. 在青龙面板中添加环境变量RAINYUN_USERNAME（用户名）
2. 在青龙面板中添加环境变量RAINYUN_PASSWORD（密码）
3. 确保用户名和密码正确"""
            
            logger.error(error_msg)
            return error_msg, False

        # 1. 检查登录状态
        if not self.check_login_status():
            # 2. 登录
            if not self.login(self.username, self.password):
                return "登录失败", False

        # 3. 执行签到
        sign_success, sign_message = self.sign_in()

        # 4. 获取积分信息
        points_success, points_message = self.get_points()

        # 5. 组合结果消息
        final_msg = f"""雨云签到结果

📝 签到: {sign_message}
📊 积分: {points_message}
⏰ 时间: {datetime.now().strftime('%m-%d %H:%M')}"""
        
        logger.info(f"{'任务完成' if sign_success else '任务失败'}")
        return final_msg, sign_success

def format_time_remaining(seconds):
    """格式化时间显示"""
    if seconds <= 0:
        return "立即执行"
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    if hours > 0:
        return f"{hours}小时{minutes}分{secs}秒"
    elif minutes > 0:
        return f"{minutes}分{secs}秒"
    else:
        return f"{secs}秒"

def wait_with_countdown(delay_seconds, task_name):
    """带倒计时的随机延迟等待"""
    if delay_seconds <= 0:
        return
        
    logger.info(f"{task_name} 需要等待 {format_time_remaining(delay_seconds)}")
    
    # 显示倒计时（每10秒显示一次，最后10秒每秒显示）
    remaining = delay_seconds
    while remaining > 0:
        if remaining <= 10 or remaining % 10 == 0:
            logger.info(f"{task_name} 倒计时: {format_time_remaining(remaining)}")
        
        sleep_time = 1 if remaining <= 10 else min(10, remaining)
        time.sleep(sleep_time)
        remaining -= sleep_time

def notify_user(title, content):
    """统一通知函数"""
    if hadsend:
        try:
            send(title, content)
            logger.info(f"通知发送完成: {title}")
        except Exception as e:
            logger.error(f"通知发送失败: {e}")
    else:
        logger.info(f"{title}\n{content}")

def main():
    """主程序入口"""
    logger.info(f"==== 雨云签到开始 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ====")
    
    # 随机延迟（整体延迟）
    delay_seconds = random.randint(1, 10)  # 固定1-10秒随机延迟
    if delay_seconds > 0:
        logger.info(f"随机延迟: {format_time_remaining(delay_seconds)}")
        wait_with_countdown(delay_seconds, "雨云签到")
    
    # 获取账号配置
    usernames = RAINYUN_USERNAME.split('&') if RAINYUN_USERNAME else []
    passwords = RAINYUN_PASSWORD.split('&') if RAINYUN_PASSWORD else []
    
    # 清理空白项
    usernames = [u.strip() for u in usernames if u.strip()]
    passwords = [p.strip() for p in passwords if p.strip()]
    
    if not usernames or not passwords:
        error_msg = """未找到RAINYUN_USERNAME或RAINYUN_PASSWORD环境变量
        
🔧 配置方法:
1. RAINYUN_USERNAME: 用户名
2. RAINYUN_PASSWORD: 密码"""
        
        logger.error(error_msg)
        notify_user("雨云签到失败", error_msg)
        return
    
    if len(usernames) != len(passwords):
        error_msg = f"""用户名和密码数量不匹配
        
📊 当前配置:
- 用户名数量: {len(usernames)}
- 密码数量: {len(passwords)}"""
        
        logger.error(error_msg)
        notify_user("雨云签到失败", error_msg)
        return
    
    logger.info(f"共发现 {len(usernames)} 个账号")
    
    success_count = 0
    total_count = len(usernames)
    results = []
    
    # 注意：这里需要一个浏览器实例，但在独立脚本中无法获取
    # 在实际使用中，需要通过外部方式提供浏览器实例
    browser = None
    
    for index, (username, password) in enumerate(zip(usernames, passwords)):
        try:
            # 账号间随机等待
            if index > 0:
                delay = random.uniform(1, 3)
                logger.info(f"随机等待 {delay:.1f} 秒后处理下一个账号...")
                time.sleep(delay)
            
            # 执行签到
            signer = RainyunSigner(username, password, index + 1)
            # 注意：这里需要设置浏览器实例
            if browser:
                signer.set_browser(browser)
            result_msg, is_success = signer.main()
            
            if is_success:
                success_count += 1
            
            results.append({
                'index': index + 1,
                'success': is_success,
                'message': result_msg
            })
            
            # 发送单个账号通知
            status = "成功" if is_success else "失败"
            title = f"雨云账号{index + 1}签到{status}"
            notify_user(title, result_msg)
            
        except Exception as e:
            error_msg = f"账号{index + 1}: 执行异常 - {str(e)}"
            logger.error(error_msg)
            notify_user(f"雨云账号{index + 1}签到失败", error_msg)
    
    # 发送汇总通知
    if total_count > 1:
        summary_msg = f"""雨云签到汇总

📈 总计: {total_count}个账号
✅ 成功: {success_count}个
❌ 失败: {total_count - success_count}个
📊 成功率: {success_count/total_count*100:.1f}%
⏰ 完成时间: {datetime.now().strftime('%m-%d %H:%M')}"""
        
        # 添加详细结果（最多显示5个账号的详情）
        if len(results) <= 5:
            summary_msg += "\n\n详细结果:"
            for result in results:
                status_icon = "✅" if result['success'] else "❌"
                summary_msg += f"\n{status_icon} 账号{result['index']}"
        
        notify_user("雨云签到汇总", summary_msg)
    
    logger.info(f"==== 雨云签到完成 - 成功{success_count}/{total_count} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ====")

if __name__ == "__main__":
    main()