#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
cron: 0 9 * * *
new Env('leaflow签到')
"""

import os
import re
import time
import random
from datetime import datetime
from typing import Optional

import requests
from lxml import etree
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
LEAFLOW_COOKIE = os.environ.get('LEAFLOW_COOKIE', '')

class LeaflowSigner:
    """Leaflow 自动签到工具"""

    def __init__(self, cookie: str = "", index: int = 1) -> None:
        self.cookie = cookie
        self.index = index
        self.checkin_url = "https://checkin.leaflow.net"
        self.main_site = "https://leaflow.net"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

    def create_session(self):
        """根据cookie创建会话"""
        session = requests.Session()
        session.headers.update(self.headers)
        
        # 如果提供了cookie，设置到会话中
        if self.cookie:
            # 解析cookie字符串
            if 'PHPSESSID=' in self.cookie:
                # 如果cookie中包含PHPSESSID，直接使用
                session.headers['Cookie'] = self.cookie
            else:
                # 否则尝试作为完整的Cookie头使用
                session.headers['Cookie'] = self.cookie
        
        return session

    def test_authentication(self, session):
        """测试认证是否有效"""
        try:
            # 尝试访问需要认证的页面
            test_urls = [
                f"{self.main_site}/dashboard",
                f"{self.main_site}/profile",
                f"{self.main_site}/user",
                self.checkin_url,
            ]
            
            for url in test_urls:
                try:
                    response = session.get(url, timeout=30)
                    logger.debug(f"[账号{self.index}] 测试 {url}: {response.status_code}")
                    
                    if response.status_code == 200:
                        content = response.text.lower()
                        if any(indicator in content for indicator in ['dashboard', 'profile', 'user', 'logout', 'welcome']):
                            logger.info(f"✅ [账号{self.index}] 认证有效")
                            return True, "认证成功"
                    elif response.status_code in [301, 302, 303]:
                        location = response.headers.get('location', '')
                        if 'login' not in location.lower():
                            logger.info(f"✅ [账号{self.index}] 认证有效 (重定向)")
                            return True, "认证成功 (重定向)"
                except Exception as e:
                    logger.debug(f"[账号{self.index}] 测试 {url} 失败: {str(e)}")
                    continue
            
            return False, "认证失败 - 未找到有效的认证页面"
            
        except Exception as e:
            return False, f"认证测试错误: {str(e)}"

    def perform_checkin(self, session):
        """执行签到操作"""
        logger.info(f"🎯 [账号{self.index}] 执行签到...")
        
        try:
            # 方法1: 直接访问签到页面
            response = session.get(self.checkin_url, timeout=30)
            
            if response.status_code == 200:
                result = self.analyze_and_checkin(session, response.text)
                if result[0]:
                    return result
            
            # 方法2: 尝试API端点
            api_endpoints = [
                f"{self.checkin_url}/api/checkin",
                f"{self.checkin_url}/checkin",
                f"{self.main_site}/api/checkin",
                f"{self.main_site}/checkin"
            ]
            
            for endpoint in api_endpoints:
                try:
                    # GET请求
                    response = session.get(endpoint, timeout=30)
                    if response.status_code == 200:
                        success, message = self.check_checkin_response(response.text)
                        if success:
                            return True, message
                    
                    # POST请求
                    response = session.post(endpoint, data={'checkin': '1'}, timeout=30)
                    if response.status_code == 200:
                        success, message = self.check_checkin_response(response.text)
                        if success:
                            return True, message
                            
                except Exception as e:
                    logger.debug(f"[账号{self.index}] API端点 {endpoint} 失败: {str(e)}")
                    continue
            
            return False, "所有签到方法都失败了"
            
        except Exception as e:
            return False, f"签到错误: {str(e)}"

    def analyze_and_checkin(self, session, html_content):
        """分析页面内容并执行签到"""
        # 检查是否已经签到
        if self.already_checked_in(html_content):
            return True, "今日已签到"
        
        # 检查是否需要签到
        if not self.is_checkin_page(html_content):
            return False, "不是签到页面"
        
        # 尝试POST签到
        try:
            checkin_data = {'checkin': '1', 'action': 'checkin', 'daily': '1'}
            
            # 提取CSRF token
            csrf_token = self.extract_csrf_token(html_content)
            if csrf_token:
                checkin_data['_token'] = csrf_token
                checkin_data['csrf_token'] = csrf_token
            
            response = session.post(self.checkin_url, data=checkin_data, timeout=30)
            
            if response.status_code == 200:
                return self.check_checkin_response(response.text)
                
        except Exception as e:
            logger.debug(f"[账号{self.index}] POST签到失败: {str(e)}")
        
        return False, "签到执行失败"

    def already_checked_in(self, html_content):
        """检查是否已经签到"""
        content_lower = html_content.lower()
        indicators = [
            'already checked in', '今日已签到', 'checked in today',
            'attendance recorded', '已完成签到', 'completed today'
        ]
        return any(indicator in content_lower for indicator in indicators)

    def is_checkin_page(self, html_content):
        """判断是否是签到页面"""
        content_lower = html_content.lower()
        indicators = ['check-in', 'checkin', '签到', 'attendance', 'daily']
        return any(indicator in content_lower for indicator in indicators)

    def extract_csrf_token(self, html_content):
        """提取CSRF token"""
        patterns = [
            r'name=["\']_token["\'][^>]*value=["\']([^"\']+)["\']',
            r'name=["\']csrf_token["\'][^>]*value=["\']([^"\']+)["\']',
            r'<meta[^>]*name=["\']csrf-token["\'][^>]*content=["\']([^"\']+)["\']',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html_content, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None

    def check_checkin_response(self, html_content):
        """检查签到响应"""
        content_lower = html_content.lower()
        
        success_indicators = [
            'check-in successful', 'checkin successful', '签到成功',
            'attendance recorded', 'earned reward', '获得奖励',
            'success', '成功', 'completed'
        ]
        
        if any(indicator in content_lower for indicator in success_indicators):
            # 提取奖励信息
            reward_patterns = [
                r'获得奖励[^\d]*(\d+\.?\d*)\s*元',
                r'earned.*?(\d+\.?\d*)\s*(credits?|points?)',
                r'(\d+\.?\d*)\s*(credits?|points?|元)'
            ]
            
            for pattern in reward_patterns:
                match = re.search(pattern, html_content, re.IGNORECASE)
                if match:
                    reward = match.group(1)
                    return True, f"签到成功! 获得 {reward} 积分"
            
            return True, "签到成功!"
        
        return False, "签到响应表示失败"

    def checkin(self) -> tuple[bool, str]:
        """执行签到"""
        try:
            # 创建会话
            session = self.create_session()
            
            # 测试认证
            auth_result = self.test_authentication(session)
            if not auth_result[0]:
                return False, f"认证失败: {auth_result[1]}"
            
            # 执行签到
            return self.perform_checkin(session)
            
        except Exception as e:
            return False, f"签到失败：{e}"

    def main(self) -> tuple[str, bool]:
        """主执行函数"""
        logger.info(f"==== leaflow账号{self.index} 开始签到 ====")
        
        if not self.cookie.strip():
            error_msg = """账号配置错误
            
❌ 错误原因: Cookie为空
            
🔧 解决方法:
1. 在青龙面板中添加环境变量LEAFLOW_COOKIE（Cookie值）
2. 确保Cookie格式正确"""
            
            logger.error(error_msg)
            return error_msg, False

        # 执行签到
        success, message = self.checkin()
        
        # 组合结果消息
        final_msg = f"""leaflow签到结果

📝 签到: {message}
⏰ 时间: {datetime.now().strftime('%m-%d %H:%M')}"""
        
        logger.info(f"{'任务完成' if success else '任务失败'}")
        return final_msg, success

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
    logger.info(f"==== leaflow签到开始 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ====")
    
    # 随机延迟（整体延迟）
    delay_seconds = random.randint(1, 10)  # 固定1-10秒随机延迟
    if delay_seconds > 0:
        logger.info(f"随机延迟: {format_time_remaining(delay_seconds)}")
        wait_with_countdown(delay_seconds, "leaflow签到")
    
    # 获取Cookie配置
    cookies = LEAFLOW_COOKIE.split('&') if LEAFLOW_COOKIE else []
    cookies = [c.strip() for c in cookies if c.strip()]
    
    if not cookies:
        error_msg = """未找到LEAFLOW_COOKIE环境变量
        
🔧 配置方法:
1. LEAFLOW_COOKIE: Cookie值"""
        
        logger.error(error_msg)
        notify_user("leaflow签到失败", error_msg)
        return
    
    logger.info(f"共发现 {len(cookies)} 个账号")
    
    success_count = 0
    total_count = len(cookies)
    results = []
    
    for index, cookie in enumerate(cookies):
        try:
            # 账号间随机等待
            if index > 0:
                delay = random.uniform(1, 3)
                logger.info(f"随机等待 {delay:.1f} 秒后处理下一个账号...")
                time.sleep(delay)
            
            # 执行签到
            signer = LeaflowSigner(cookie, index + 1)
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
            title = f"leaflow账号{index + 1}签到{status}"
            notify_user(title, result_msg)
            
        except Exception as e:
            error_msg = f"账号{index + 1}: 执行异常 - {str(e)}"
            logger.error(error_msg)
            notify_user(f"leaflow账号{index + 1}签到失败", error_msg)
    
    # 发送汇总通知
    if total_count > 1:
        summary_msg = f"""leaflow签到汇总

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
        
        notify_user("leaflow签到汇总", summary_msg)
    
    logger.info(f"==== leaflow签到完成 - 成功{success_count}/{total_count} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ====")

if __name__ == "__main__":
    main()