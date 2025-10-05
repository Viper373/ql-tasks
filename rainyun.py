#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
cron: 0 7 * * *
new Env('雨云签到')
"""

import os
import time
import random
import json
from datetime import datetime
from typing import Dict, Any, Optional

import requests
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
RAINYUN_API_KEY = os.environ.get('RAINYUN_API_KEY')

# 公共请求头
COMMON_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    "cache-control": "no-cache",
    "pragma": "no-cache",
    "priority": "u=1, i",
    "sec-ch-ua": "\"Not;A=Brand\";v=\"99\", \"Microsoft Edge\";v=\"139\", \"Chromium\";v=\"139\"",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": "\"Windows\"",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "referer": "https://app.rainyun.com/",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0"
}

class Config:
    """简化的配置类，使用环境变量"""
    
    def __init__(self):
        self.config = {
            "auth": {},
            "headers": {}
        }
        if RAINYUN_API_KEY:
            self.config["auth"]["x-api-key"] = RAINYUN_API_KEY
            logger.info("Config: 使用API密钥认证")
        else:
            logger.error("Config: 未找到RAINYUN_API_KEY，无法进行认证。请设置环境变量。")
    
    def get(self, key: str, default=None):
        """获取配置值"""
        return self.config.get(key, default)
    
    def load_header_auth(self, headers: Dict[str, str], boolean: bool = False):
        """加载认证信息到请求头"""
        headers = headers.copy()
        auth = self.config.get("auth", {})
        key = auth.get('x-api-key', None)
        
        if key:
            headers['x-api-key'] = str(key)
            return True if boolean else headers
        
        return False if boolean else headers
    
    def load_cookies_auth(self) -> Dict[str, str]:
        """加载cookie认证信息"""
        if self.load_header_auth({}, True):
            return {}  # 如果有API密钥，则不使用cookie认证
        return {}  # 否则也返回空，因为用户明确表示不需要dev-code和rain-session
    
    def update_cookies_from_response(self, response, current_cookies: Dict[str, str]) -> Dict[str, str]:
        """从响应中更新cookie"""
        # 根据用户要求，不使用dev-code和rain-session，因此不从响应中更新这些cookie
        return current_cookies

# 创建配置实例
config = Config()

# 合并配置中的headers，就像原始仓库一样
COMMON_HEADERS = COMMON_HEADERS | config.get('headers', {})

# 获取CSRF token的函数
def get_csrf_token():
    cookies = config.load_cookies_auth()
    url = "https://api.v2.rainyun.com/user/csrf"

    try:
        response = requests.get(url, headers=config.load_header_auth(COMMON_HEADERS), cookies=cookies, timeout=10)
        cookies = config.update_cookies_from_response(response, cookies)

        if response.status_code == 200:
            return response.json().get('data'), cookies
        return None, cookies
    except requests.exceptions.RequestException:
        return None, cookies


def check_in(data):
    if not isinstance(data, dict):
        return {'error': '未提供数据。'}

    if data.get('randstr') and data.get('ticket'):
        data = {
            "task_name": "每日签到",
            "verifyCode": "",
            "vticket": data['ticket'],
            "vrandstr": data['randstr']
        }

    # 获取CSRF token并更新cookies
    csrf_token, cookies = get_csrf_token()
    if csrf_token is None:
        return {'error': '无法获取 CSRF 令牌。可能已经退出登录。'}

    # 准备请求头
    headers = config.load_header_auth(COMMON_HEADERS)
    headers.update({
        "content-type": "application/json",
        "x-csrf-token": csrf_token
    })

    try:
        # 转发请求到目标API
        response = requests.post(
            "https://api.v2.rainyun.com/user/reward/tasks",
            headers=headers,
            cookies=cookies,
            json=data,
            timeout=10
        )

        # 更新cookie
        config.update_cookies_from_response(response, cookies)

        # 返回API的响应
        return response.json()
    except requests.exceptions.RequestException as e:
        return {'error': str(e)}


def get_check_in_status():
    # 获取CSRF token并更新cookies
    csrf_token, cookies = get_csrf_token()
    if csrf_token is None:
        return {'error': '无法获取 CSRF 令牌。可能已经退出登录。'}

    # 准备请求头
    headers = config.load_header_auth(COMMON_HEADERS)
    headers.update({
        "x-csrf-token": csrf_token
    })

    try:
        # 获取任务列表
        response = requests.get(
            "https://api.v2.rainyun.com/user/reward/tasks",
            headers=headers,
            cookies=cookies,
            timeout=10
        )

        # 更新cookie
        config.update_cookies_from_response(response, cookies)

        if response.status_code == 200:
            data = response.json()
            tasks = data.get('data', [])
            for task in tasks:
                if task.get('Name') == '每日签到' and task.get('Status') == 2:
                    return {'check_in': True}
            return {'check_in': False}
        return {'error': 'Failed to get tasks', 'code': response.status_code}
    except requests.exceptions.RequestException as e:
        return {'error': str(e)}


def get_user_info():
    """获取用户信息"""
    csrf_token, cookies = get_csrf_token()
    if csrf_token is None:
        return {'error': '无法获取 CSRF 令牌。可能已经退出登录。'}

    headers = config.load_header_auth(COMMON_HEADERS)
    headers.update({
        "x-csrf-token": csrf_token
    })

    try:
        response = requests.get(
            "https://api.v2.rainyun.com/user",
            headers=headers,
            cookies=cookies,
            timeout=10
        )

        config.update_cookies_from_response(response, cookies)

        if response.status_code == 200:
            return response.json()
        return {'error': 'Failed to get user info', 'code': response.status_code}
    except requests.exceptions.RequestException as e:
        return {'error': str(e)}


class RainyunSigner:
    """雨云签到工具"""

    def __init__(self, index: int = 1) -> None:
        self.index = index

    def check_auth_status(self) -> bool:
        """检查认证状态"""
        try:
            logger.info("检查认证状态...")
            user_info = get_user_info()
            if 'error' in user_info:
                logger.warning(f"认证失败: {user_info['error']}")
                return False

            if user_info.get('code') == 200:
                logger.info("认证成功")
                return True
            else:
                logger.warning(f"认证失败: {user_info.get('msg', '未知错误')}")
                return False
        except Exception as e:
            logger.error(f"检查认证状态失败: {e}")
            return False

    def get_checkin_status(self) -> tuple[bool, str]:
        """获取签到状态"""
        try:
            logger.info("获取签到状态...")
            status = get_check_in_status()
            if 'error' in status:
                return False, f"获取状态失败: {status['error']}"
            
            if status.get('check_in'):
                return True, "今日已签到"
            else:
                return False, "今日未签到"
        except Exception as e:
            return False, f"获取签到状态异常: {e}"

    def sign_in(self) -> tuple[bool, str]:
        """执行签到"""
        try:
            logger.info("开始签到...")
            # 先检查签到状态
            status_success, status_msg = self.get_checkin_status()
            if status_success and "已签到" in status_msg:
                return True, "今日已签到"
            
            # 执行签到
            result = check_in({
                "task_name": "每日签到",
                "verifyCode": "",
                "vticket": "",
                "vrandstr": ""
            })
            
            if 'error' in result:
                return False, f"签到失败: {result['error']}"
            
            if result.get('code') == 0:
                return True, "签到成功"
            else:
                error_msg = result.get('msg', '未知错误')
                if "已签到" in error_msg:
                    return True, "今日已签到"
                return False, f"签到失败: {error_msg}"
        except Exception as e:
            return False, f"签到过程中出现异常: {e}"

    def get_points(self) -> tuple[bool, str]:
        """获取积分信息"""
        try:
            logger.info("获取积分信息...")
            user_info = get_user_info()
            if 'error' in user_info:
                return False, f"获取积分失败: {user_info['error']}"
            
            if user_info.get('code') == 200:
                user_data = user_info.get('data', {})
                points = int(user_data.get('Points', "N/A"))
                return True, f"当前积分: {points}丨约等于: {points / 2000:.2f}元"
            else:
                return False, f"获取积分失败: {user_info.get('msg', '未知错误')}"
        except Exception as e:
            return False, f"获取积分信息时出现异常: {e}"

    def main(self) -> tuple[str, bool]:
        """主执行函数"""
        logger.info(f"==== 雨云账号{self.index} 开始签到 ====")
        
        # 检查认证状态
        if not self.check_auth_status():
            return "认证失败", False
        
        # 执行签到
        sign_success, sign_message = self.sign_in()

        # 获取积分信息
        points_success, points_message = self.get_points()

        # 构建最终消息
        final_msg = f"""雨云签到结果
📝 签到: {sign_message}
📊 积分: {points_message}
⏰ 时间: {datetime.now().strftime('%m-%d %H:%M')}"""
        
        logger.info(f"{'任务完成' if sign_success else '任务失败'}")
        return final_msg, sign_success


def wait_with_countdown(delay_seconds, task_name):
    """带倒计时的等待函数"""
    logger.info(f"{task_name} 需要等待 {delay_seconds}秒")
    time.sleep(delay_seconds)


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
    """主函数"""
    logger.info("==== 雨云签到开始 - {} ====".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    
    # 检查认证配置
    if not RAINYUN_API_KEY:
        error_msg = """未找到认证配置
请设置环境变量：
RAINYUN_API_KEY

获取方法：
API密钥：登录雨云 → 总览 → 用户 → 账户设置 → API密钥
"""
        logger.error(error_msg)
        notify_user("雨云签到失败", error_msg)
        return
    
    # 随机延迟
    delay = random.randint(1, 5)
    logger.info(f"随机延迟: {delay}秒")
    wait_with_countdown(delay, "雨云签到")
    
    logger.info("开始执行雨云签到")
    
    success_count = 0
    total_count = 1  # API方式只支持单个账号
    results = []
    
    try:
        # 执行签到
        signer = RainyunSigner(1)  # API方式不需要用户名密码
        result_msg, is_success = signer.main()
        
        if is_success:
            success_count += 1
        
        results.append({'index': 1, 'success': is_success, 'message': result_msg})
        
        status = "成功" if is_success else "失败"
        title = f"雨云签到{status}"
        notify_user(title, result_msg)
            
    except Exception as e:
        error_msg = f"执行异常 - {str(e)}"
        logger.error(error_msg)
        notify_user("雨云签到失败", error_msg)
    
    logger.info(f"==== 雨云签到完成 - 成功{success_count}/{total_count} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ====")


if __name__ == "__main__":
    main()