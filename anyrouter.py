#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
cron: 0 6 * * *
new Env('AnyRouter签到')
"""

import os
import time
import random
from datetime import datetime
import warnings
warnings.filterwarnings("ignore")

import requests
from bs4 import BeautifulSoup
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
ANYROUTER_COOKIE = os.environ.get('ANYROUTER_COOKIE')
ANYROUTER_NEW_API_USER = os.environ.get('ANYROUTER_NEW_API_USER')

class AnyRouterSigner:
    """AnyRouter 自动签到与信息提取工具"""

    def __init__(self, cookie: str = "", index: int = 1) -> None:
        self.cookie = cookie
        self.index = index

        # 统一请求头
        self.common_headers = {
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'cache-control': 'no-store',
            'origin': 'https://anyrouter.top',
            'referer': 'https://anyrouter.top/console',
            'sec-ch-ua': '"Chromium";v="140", "Not=A?Brand";v="24", "Microsoft Edge";v="140"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0',
        }

        self.session = requests.Session()
        self.session.headers.update(self.common_headers)
        # 可选 new-api-user 头
        if ANYROUTER_NEW_API_USER:
            self.session.headers['new-api-user'] = ANYROUTER_NEW_API_USER

    def _cookie_dict(self) -> dict:
        """将环境变量中的 Cookie 串解析为 dict 传给 requests.cookies"""
        cookie_dict: dict[str, str] = {}
        if not self.cookie:
            return cookie_dict
        # 支持以分号分隔的 cookie 串
        parts = [p.strip() for p in self.cookie.split(';') if p.strip()]
        for p in parts:
            if '=' in p:
                k, v = p.split('=', 1)
                cookie_dict[k.strip()] = v.strip()
        return cookie_dict

    def _post_signin(self) -> tuple[bool, str]:
        """调用签到接口，返回(success, message)"""
        try:
            url = 'https://anyrouter.top/api/user/sign_in'
            resp = self.session.post(url, timeout=30, verify=False, cookies=self._cookie_dict())
            if resp.status_code != 200:
                return False, f"HTTP {resp.status_code}"
            data = resp.json() if resp.content else {}
            message = str(data.get('message', ''))
            success = bool(data.get('success', False))
            return success, message
        except Exception as e:
            return False, f"签到请求异常: {e}"

    def _fetch_console_top2(self) -> tuple[list[str], list[str]]:
        """抓取控制台页面的前两个标题与内容"""
        titles: list[str] = []
        contents: list[str] = []
        try:
            url = 'https://anyrouter.top/console'
            resp = self.session.get(url, timeout=30, cookies=self._cookie_dict())
            if resp.status_code != 200:
                return titles, contents
            soup = BeautifulSoup(resp.text, 'html.parser')
            title_divs = soup.select('div.text-xs.text-gray-500')
            content_divs = soup.select('div.text-lg.font-semibold')
            titles = [d.get_text(strip=True) for d in title_divs[:2]]
            contents = [d.get_text(strip=True) for d in content_divs[:2]]
            return titles, contents
        except Exception:
            return titles, contents

    def main(self) -> tuple[str, bool]:
        """主执行函数"""
        logger.info(f"==== AnyRouter账号{self.index} 开始签到 ====")
        
        if not self.cookie.strip():
            error_msg = """账号配置错误
            
❌ 错误原因: Cookie为空
            
🔧 解决方法:
1. 在青龙面板中添加环境变量ANYROUTER_COOKIE（Cookie值）
2. 确保Cookie格式正确"""
            
            logger.error(error_msg)
            return error_msg, False

        try:
            ok, msg = self._post_signin()
            sign_message = msg if msg else "签到完成"
            
            titles, contents = self._fetch_console_top2()
            # 仅取前两个，成对输出
            info_messages = []
            n = min(len(titles), len(contents), 2)
            for i in range(n):
                info_messages.append(f'{titles[i]}：{contents[i]}')

            # 组合结果消息
            final_msg = f"""AnyRouter签到结果

📝 签到: {sign_message}
📊 信息: {" | ".join(info_messages) if info_messages else "无"}
⏰ 时间: {datetime.now().strftime('%m-%d %H:%M')}"""
            
            logger.info(f"{'任务完成' if ok else '任务失败'}")
            return final_msg, ok
            
        except Exception as e:
            error_msg = f"AnyRouter任务异常: {e}"
            logger.error(error_msg)
            return error_msg, False

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
    """主程序入口"""
    logger.info(f"==== AnyRouter签到开始 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ====")
    
    # 随机延迟（整体延迟）
    delay_seconds = random.randint(1, 5)  # 固定1-10秒随机延迟
    if delay_seconds > 0:
        logger.info(f"随机延迟: {format_time_remaining(delay_seconds)}")
        wait_with_countdown(delay_seconds, "AnyRouter签到")
    
    # 获取Cookie配置
    cookies = ANYROUTER_COOKIE.split('&') if ANYROUTER_COOKIE else []
    cookies = [c.strip() for c in cookies if c.strip()]
    
    if not cookies:
        error_msg = """未找到ANYROUTER_COOKIE环境变量
        
🔧 配置方法:
1. ANYROUTER_COOKIE: Cookie值"""
        
        logger.error(error_msg)
        notify_user("AnyRouter签到失败", error_msg)
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
            signer = AnyRouterSigner(cookie, index + 1)
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
            title = f"AnyRouter账号{index + 1}签到{status}"
            notify_user(title, result_msg)
            
        except Exception as e:
            error_msg = f"账号{index + 1}: 执行异常 - {str(e)}"
            logger.error(error_msg)
            notify_user(f"AnyRouter账号{index + 1}签到失败", error_msg)
    
    # 发送汇总通知
    if total_count > 1:
        summary_msg = f"""AnyRouter签到汇总

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
        
        notify_user("AnyRouter签到汇总", summary_msg)
    
    logger.info(f"==== AnyRouter签到完成 - 成功{success_count}/{total_count} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ====")

if __name__ == "__main__":
    main()