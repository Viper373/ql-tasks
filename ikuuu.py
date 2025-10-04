#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
cron: 0 8 * * *
new Env('ikuuu签到')
"""

import os
import time
import random
from datetime import datetime
from typing import Optional

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
IKUUU_USERNAME = os.environ.get('IKUUU_USERNAME', '')
IKUUU_PASSWORD = os.environ.get('IKUUU_PASSWORD', '')

class IKuuuClient:
    """iKuuu 自动登录与签到客户端"""

    def __init__(self, username: str = "", password: str = "", index: int = 1) -> None:
        self.username = username
        self.password = password
        self.index = index
        self.browser: Optional[Chromium] = None
        self.tab = None
        self.base_url = 'https://ikuuu.org/user'

    def set_browser(self, browser: Chromium) -> None:
        """设置浏览器实例"""
        self.browser = browser
        self.tab = browser.latest_tab

    def _random_wait(self, max_seconds: float = 2.0) -> None:
        """随机等待0-max_seconds秒"""
        wait_time = random.uniform(0, max_seconds)
        time.sleep(wait_time)

    def navigate_to_profile(self) -> bool:
        """导航到用户页面"""
        try:
            self.tab.get(self.base_url)
            self._random_wait(1.0)
            logger.info('成功导航到用户页面')
            return True
        except Exception as e:
            logger.error(f'导航到用户页面失败: {e}')
            return False

    def is_logged_in(self) -> bool:
        """检查是否已登录"""
        try:
            # 尝试多种登录状态标识
            selectors = [
                'xpath://div[@class="d-sm-none d-lg-inline-block"]',
                'xpath://div[contains(@class, "user-menu")]',
                'xpath://a[contains(@href, "/profile")]',
                'xpath://div[contains(text(), "Hi")]',
                'xpath://span[contains(text(), "Hi")]'
            ]
            
            for selector in selectors:
                try:
                    element = self.tab.ele(selector, timeout=2)
                    if element:
                        text = element.text or ''
                        if 'Hi' in text or 'profile' in text.lower():
                            logger.info('用户已登录')
                            return True
                except:
                    continue
            
            logger.info('用户未登录')
            return False
        except Exception as e:
            logger.warning(f'检查登录状态时出错: {e}')
            return False

    def login(self) -> bool:
        """登录操作"""
        try:
            logger.info('开始尝试登录...')

            # 查找登录表单元素
            email_input = self.tab.ele('xpath://input[@id="email"]', timeout=5)
            pwd_input = self.tab.ele('xpath://input[@id="password"]', timeout=5)

            if not email_input or not pwd_input:
                # 可能已经登录了，检查一下
                if self.is_logged_in():
                    logger.info('用户已登录，无需重复登录')
                    return True
                logger.error('未找到登录表单元素')
                return False

            # 清空并输入用户名
            email_input.clear()
            self._random_wait(0.5)
            email_input.input(self.username)
            self._random_wait(0.5)

            # 清空并输入密码
            pwd_input.clear()
            self._random_wait(0.5)
            pwd_input.input(self.password)
            self._random_wait(0.5)

            # 点击登录按钮
            submit_btn = self.tab.ele('xpath://button[@type="submit"]', timeout=3)
            if not submit_btn:
                logger.error('未找到登录按钮')
                return False

            submit_btn.click()
            self._random_wait()

            # 检查登录结果
            if self.is_logged_in():
                logger.success('登录成功')
                return True
            else:
                logger.error('登录失败，请检查用户名和密码')
                return False

        except Exception as e:
            logger.error(f'登录过程中发生异常: {e}')
            return False

    def checkin(self) -> tuple[bool, str]:
        """签到操作"""
        try:
            logger.info('开始尝试签到...')

            btn = self.tab.ele('xpath://div[@id="checkin-div"]', timeout=5)
            if not btn:
                return False, '未找到签到按钮'

            # 检查按钮当前状态
            current_text = btn.text or ''
            if '明日再来' in current_text:
                return True, '今日已签到'

            # 执行签到
            btn.click()
            logger.info('签到按钮已点击')
            self._random_wait(1.5)

            # 检查签到结果
            try:
                status_text = self.tab.ele('xpath://h2[@id="swal2-title"]', timeout=3)
                if status_text:
                    text = status_text.text or ''
                    if '签到成功' in text:
                        reward = self.tab.ele('xpath://div[@id="swal2-content"]', timeout=3)
                        reward_text = reward.text if reward else '未知奖励'
                        logger.success(f'签到成功：{reward_text}')
                        self.tab.ele('xpath://button[@class="swal2-confirm swal2-styled"]', timeout=3).click()  # 点击OK关闭弹窗
                        return True, f'签到成功：{reward_text}'
                    else:
                        return False, f'签到状态异常: {text}'
                elif '明日再来' in self.tab.ele('xpath://div[@id="checkin-div"]', timeout=3):
                    return True, '今日已签到'
                else:
                    return False, '签到异常，未找到状态提示'
            except Exception as e1:
                return False, f'签到状态检查失败: {e1}'

        except Exception as e2:
            return False, f'签到过程中发生异常: {e2}'

    def fetch_info(self) -> tuple[bool, str]:
        """获取用户信息"""
        try:
            logger.info('开始获取用户信息...')

            # 确保在正确的页面
            self.tab.get(self.base_url)
            time.sleep(3)

            # 查找信息卡片
            rows = self.tab.eles('xpath://div[@class="row"][1]/div[contains(@class, "col-lg-3") and contains(@class, "col-md-3") and contains(@class, "col-sm-12")]', timeout=5)
            if not rows:
                return False, '未找到信息卡片'

            if len(rows) < 3:
                return False, f'信息卡片数量不足，期望至少3个，实际{len(rows)}个'

            def _block_text(idx: int) -> dict:
                """提取单个卡片信息"""
                try:
                    if idx >= len(rows):
                        return {'header': '', 'details': '', 'stats': ''}

                    block = rows[idx]
                    header_ele = block.ele('xpath:.//h4')
                    details_ele = block.ele('xpath:.//div[@class="card-body"]')
                    stats_ele = block.ele('xpath:.//div[@class="card-stats"]')

                    return {
                        'header': header_ele.text if header_ele else '',
                        'details': details_ele.text if details_ele else '',
                        'stats': stats_ele.text if stats_ele else ''
                    }
                except Exception as e:
                    logger.warning(f'提取第{idx}个卡片信息失败: {e}')
                    return {'header': '', 'details': '', 'stats': ''}

            # 提取各个卡片信息并输出
            info_messages = []
            logger.info('=== 用户信息详情 ===')

            for i in range(min(len(rows), 4)):  # 最多处理4个卡片
                block_info = _block_text(i)
                header = block_info['header'].strip()
                details = block_info['details'].strip()
                stats = block_info['stats'].strip()

                if header and details:
                    if stats:
                        message = f'{header}: {details} | {stats}'
                        info_messages.append(message)
                        logger.success(message)
                    else:
                        message = f'{header}: {details}'
                        info_messages.append(message)
                        logger.success(message)

            return True, " | ".join(info_messages) if info_messages else "用户信息获取成功"

        except Exception as e:
            return False, f'获取用户信息时发生异常: {e}'

    def main(self) -> tuple[str, bool]:
        """主执行函数"""
        logger.info(f"==== ikuuu账号{self.index} 开始签到 ====")
        
        if not self.username.strip() or not self.password.strip():
            error_msg = """账号配置错误
            
❌ 错误原因: 用户名或密码为空
            
🔧 解决方法:
1. 在青龙面板中添加环境变量IKUUU_USERNAME（用户名）
2. 在青龙面板中添加环境变量IKUUU_PASSWORD（密码）
3. 确保用户名和密码正确"""
            
            logger.error(error_msg)
            return error_msg, False

        # 1. 导航到用户页面
        if not self.navigate_to_profile():
            return "任务失败：页面导航失败", False

        # 2. 检查登录状态并登录
        if not self.is_logged_in():
            if not self.login():
                return "任务失败：登录失败", False

        # 3. 执行签到
        checkin_success, checkin_message = self.checkin()

        # 4. 获取用户信息
        info_success, info_message = self.fetch_info()

        # 5. 组合结果消息
        final_msg = f"""ikuuu签到结果

📝 签到: {checkin_message}
📊 信息: {info_message}
⏰ 时间: {datetime.now().strftime('%m-%d %H:%M')}"""
        
        logger.info(f"{'任务完成' if checkin_success else '任务失败'}")
        return final_msg, checkin_success

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
    
    # 显示倒计时（每10秒显示一次）
    remaining = delay_seconds
    while remaining > 0:
        if remaining % 10 == 0:
            logger.info(f"{task_name} 倒计时: {format_time_remaining(remaining)}")
        
        sleep_time = min(10, remaining)
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
    logger.info(f"==== ikuuu签到开始 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ====")
    
    # 随机延迟（整体延迟）
    delay_seconds = random.randint(1, 10)  # 固定1-10秒随机延迟
    if delay_seconds > 0:
        logger.info(f"随机延迟: {format_time_remaining(delay_seconds)}")
        wait_with_countdown(delay_seconds, "ikuuu签到")
    
    # 获取账号配置
    usernames = IKUUU_USERNAME.split('&') if IKUUU_USERNAME else []
    passwords = IKUUU_PASSWORD.split('&') if IKUUU_PASSWORD else []
    
    # 清理空白项
    usernames = [u.strip() for u in usernames if u.strip()]
    passwords = [p.strip() for p in passwords if p.strip()]
    
    if not usernames or not passwords:
        error_msg = """未找到IKUUU_USERNAME或IKUUU_PASSWORD环境变量
        
🔧 配置方法:
1. IKUUU_USERNAME: 用户名
2. IKUUU_PASSWORD: 密码"""
        
        logger.error(error_msg)
        notify_user("ikuuu签到失败", error_msg)
        return
    
    if len(usernames) != len(passwords):
        error_msg = f"""用户名和密码数量不匹配
        
📊 当前配置:
- 用户名数量: {len(usernames)}
- 密码数量: {len(passwords)}"""
        
        logger.error(error_msg)
        notify_user("ikuuu签到失败", error_msg)
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
            client = IKuuuClient(username, password, index + 1)
            # 注意：这里需要设置浏览器实例
            if browser:
                client.set_browser(browser)
            result_msg, is_success = client.main()
            
            if is_success:
                success_count += 1
            
            results.append({
                'index': index + 1,
                'success': is_success,
                'message': result_msg
            })
            
            # 发送单个账号通知
            status = "成功" if is_success else "失败"
            title = f"ikuuu账号{index + 1}签到{status}"
            notify_user(title, result_msg)
            
        except Exception as e:
            error_msg = f"账号{index + 1}: 执行异常 - {str(e)}"
            logger.error(error_msg)
            notify_user(f"ikuuu账号{index + 1}签到失败", error_msg)
    
    # 发送汇总通知
    if total_count > 1:
        summary_msg = f"""ikuuu签到汇总

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
        
        notify_user("ikuuu签到汇总", summary_msg)
    
    logger.info(f"==== ikuuu签到完成 - 成功{success_count}/{total_count} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ====")

if __name__ == "__main__":
    main()