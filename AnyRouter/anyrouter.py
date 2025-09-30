# -*- coding:utf-8 -*-
# @Software       :PyCharm
# @Project        :AutoTasks
# @Path           :/AnyRouter
# @FileName       :anyrouter.py
# @Time           :2025/9/30
# @Author         :Viper373
# @GitHub         :https://github.com/Viper373
# @Home           :https://viper3.top
# @Blog           :https://blog.viper3.top

import os
from typing import Optional, Any, Dict, List, Tuple

import requests
from bs4 import BeautifulSoup
from loguru import logger


class AnyRouterSigner:
    """AnyRouter 自动签到与信息提取工具"""

    def __init__(self, debug: bool = False, output_collector: Optional[Any] = None) -> None:
        self.debug = debug
        self.ver = "1.0-DP"
        self.output_collector = output_collector

        # 从环境变量读取配置
        self.cookie_header = os.getenv('ANYROUTER_COOKIE', '').strip()
        self.new_api_user = os.getenv('ANYROUTER_NEW_API_USER', '').strip()

        # 统一请求头
        self.common_headers: Dict[str, str] = {
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
        if self.new_api_user:
            self.common_headers['new-api-user'] = self.new_api_user

        self.session = requests.Session()
        if self.cookie_header:
            self.session.headers.update({'Cookie': self.cookie_header})
        self.session.headers.update(self.common_headers)

        self._setup_logger()
        self._show_banner()

    def _setup_logger(self) -> None:
        """配置日志"""
        pass

    def _log(self, level: str, message: str) -> None:
        log_methods = {
            'info': logger.info,
            'success': logger.success,
            'warning': logger.warning,
            'error': logger.error,
        }
        (log_methods.get(level, logger.info))(message)
        if self.output_collector:
            self.output_collector.add_output(level, message)

    def _show_banner(self) -> None:
        logger.info("=" * 70)
        logger.info(f"🧭  AnyRouter 工具 v{self.ver} by Viper373")
        logger.info("📦  Requests版本 - 签到与控制台信息抓取")
        logger.info("🔗  Github: https://github.com/Viper373/AutoTasks")
        logger.info("=" * 70)

    def _post_signin(self) -> Tuple[bool, str]:
        """调用签到接口，返回(success, message)"""
        try:
            url = 'https://anyrouter.top/api/user/sign_in'
            resp = self.session.post(url, timeout=30)
            if resp.status_code != 200:
                return False, f"HTTP {resp.status_code}"
            data = resp.json() if resp.content else {}
            message = str(data.get('message', ''))
            success = bool(data.get('success', False))
            return success, message
        except Exception as e:
            return False, f"签到请求异常: {e}"

    def _fetch_console_top2(self) -> Tuple[List[str], List[str]]:
        """抓取控制台页面的前两个标题与内容"""
        titles: List[str] = []
        contents: List[str] = []
        try:
            url = 'https://anyrouter.top/console'
            resp = self.session.get(url, timeout=30)
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

    def run(self) -> bool:
        """执行签到与信息抓取"""
        try:
            if not self.cookie_header:
                self._log('error', '未配置 ANYROUTER_COOKIE，跳过任务')
                return False

            ok, msg = self._post_signin()
            if msg:
                # 只需要提取 message 并推送；此处添加到输出供汇总推送使用
                self._log('success' if ok else 'warning', f'签到结果：{msg}')

            titles, contents = self._fetch_console_top2()
            # 仅取前两个，成对输出
            n = min(len(titles), len(contents), 2)
            for i in range(n):
                self._log('success', f'{titles[i]}：{contents[i]}')

            return ok
        except Exception as e:
            self._log('error', f'AnyRouter任务异常: {e}')
            return False


if __name__ == '__main__':
    signer = AnyRouterSigner(debug=False, output_collector=None)
    try:
        success = signer.run()
        if success:
            logger.success("AnyRouter 任务执行成功")
        else:
            logger.error("AnyRouter 任务执行失败")
    except Exception as e:
        logger.error(f"程序执行异常: {e}")

