# -*- coding:utf-8 -*-
# @Software       :PyCharm
# @Project        :AutoTasks
# @Path           :/NodeSeek
# @FileName       :nodeseek.py
# @Time           :2025/9/29
# @Author         :Viper373
# @GitHub         :https://github.com/Viper373
# @Home           :https://viper3.top
# @Blog           :https://blog.viper3.top

import os
import time
import random
import base64
import hashlib
import hmac
import urllib.parse
from typing import Optional, Any, Dict

import cloudscraper
from loguru import logger


class NodeSeekSigner:
    """NodeSeek 自动签到工具"""

    def __init__(self, debug: bool = False, output_collector: Optional[Any] = None) -> None:
        self.debug = debug
        self.ver = "1.0-DP"
        self.output_collector = output_collector
        
        # 配置参数
        self.cookie = os.getenv('NODESEEK_COOKIE', '')
        self.member_id = os.getenv('NODESEEK_MEMBER_ID', '')
        self.random_signin = os.getenv('NODESEEK_RANDOM', 'true').lower() == 'true'
        
        # 初始化scraper
        self.scraper = self._init_scraper()
        
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
        logger.info(f"🔍  NodeSeek签到工具 v{self.ver} by Viper373")
        logger.info("📦  CloudScraper版本 - 支持反爬虫检测")
        logger.info("🔗  Github: https://github.com/Viper373/AutoTasks")
        logger.info("=" * 70)

    def _init_scraper(self) -> cloudscraper.CloudScraper:
        """初始化cloudscraper"""
        try:
            # 获取代理环境变量
            proxies = []
            ns_proxies = os.getenv("NODESEEK_PROXIES", None)
            if ns_proxies:
                proxies = [proxy for proxy in ns_proxies.split(",")]

            # cloudscraper基础配置
            scraper = cloudscraper.create_scraper(
                # 代理配置
                rotating_proxies=proxies,
                proxy_options={"rotation_strategy": "smart", "ban_time": 300},
                # 基础配置
                interpreter="js2py",
                delay=6,
                enable_stealth=True,
                stealth_options={
                    "min_delay": 5.0,
                    "max_delay": 10.0,
                    "human_like_delays": True,
                    "randomize_headers": True,
                    "browser_quirks": True,
                },
                # Browser emulation
                browser="chrome",
                # Debug mode
                debug=self.debug,
            )
            
            self._log('info', 'CloudScraper初始化成功')
            return scraper
            
        except Exception as e:
            self._log('error', f'CloudScraper初始化失败: {e}')
            raise e

    def _random_wait(self, min_seconds: float = 5.0, max_seconds: float = 20.0) -> None:
        """随机等待指定时间"""
        delay = random.uniform(min_seconds, max_seconds)
        self._log('info', f'等待 {delay:.2f} 秒后继续...')
        time.sleep(delay)

    def get_user_info(self) -> str:
        """获取NodeSeek用户信息"""
        if not self.member_id:
            self._log('warning', '未设置NodeSeek成员ID，跳过用户信息获取')
            return ""

        try:
            self._log('info', '开始获取NodeSeek用户信息...')
            
            url = f"https://www.nodeseek.com/api/account/getInfo/{self.member_id}?readme=1"
            headers = {
                "Accept": "*/*",
                "Accept-Encoding": "gzip, deflate, br, zstd",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Origin": "https://www.nodeseek.com",
                "Referer": f"https://www.nodeseek.com/space/{self.member_id}",
                "Sec-CH-UA": '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
                "Sec-CH-UA-Mobile": "?0",
                "Sec-CH-UA-Platform": '"Windows"',
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
            }
            
            response = self.scraper.get(url, headers=headers)
            data = response.json()
            
            if data.get('success'):
                ns_user_data = data["detail"]
                user_info = f"用户信息：\n【用户】：{ns_user_data['member_name']}\n【等级】：{ns_user_data['rank']}\n【鸡腿数目】：{ns_user_data['coin']}\n【主题帖数】：{ns_user_data['nPost']}\n【评论数】：{ns_user_data['nComment']}"
                self._log('success', 'NodeSeek用户信息获取成功')
                return user_info
            else:
                self._log('error', 'NodeSeek用户信息获取失败')
                return "用户信息获取失败"
                
        except Exception as e:
            self._log('error', f'NodeSeek用户信息获取异常: {e}')
            return "用户信息获取异常"

    def signin(self) -> str:
        """NodeSeek签到"""
        if not self.cookie:
            self._log('error', '未设置NodeSeek Cookie')
            return "签到失败：未设置NodeSeek Cookie"

        try:
            self._log('info', '开始执行NodeSeek签到...')
            
            url = f"https://www.nodeseek.com/api/attendance?random={str(self.random_signin).lower()}"
            headers = {
                "Accept": "*/*",
                "Accept-Encoding": "gzip, deflate, br, zstd",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Content-Length": "0",
                "Origin": "https://www.nodeseek.com",
                "Referer": "https://www.nodeseek.com/board",
                "Sec-CH-UA": '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
                "Sec-CH-UA-Mobile": "?0",
                "Sec-CH-UA-Platform": '"Windows"',
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
                "Cookie": self.cookie,
            }

            response = self.scraper.post(url, headers=headers)
            data = response.json()
            
            msg = data.get("message", "")
            success = data.get("success", False)
            
            if success:
                self._log('success', f'NodeSeek签到成功: {msg}')
            else:
                if '已完成签到' in msg:
                    self._log('success', f'NodeSeek今日已签到: {msg}')
                else:
                    self._log('warning', f'NodeSeek签到状态: {msg}')
            
            return f"签到信息：{msg}"
            
        except Exception as e:
            self._log('error', f'NodeSeek签到异常: {e}')
            return "签到异常：NodeSeek签到失败，请检查Cookie是否正确"

    def run(self) -> bool:
        """执行完整的NodeSeek签到流程"""
        try:
            self._log('info', '=== 开始执行 NodeSeek 自动签到任务 ===')
            
            # 检查配置
            if not self.cookie:
                self._log('error', '任务失败：未配置NodeSeek Cookie')
                return False
            
            # 随机等待
            self._random_wait(5, 20)
            
            # 执行签到
            signin_result = self.signin()
            self._log('info', signin_result)
            
            # 随机等待
            self._random_wait(5, 20)
            
            # 获取用户信息
            user_info = self.get_user_info()
            if user_info:
                self._log('info', user_info)
            
            # 汇总结果
            if '签到成功' in signin_result or '已完成签到' in signin_result:
                self._log('success', '=== NodeSeek任务完成：签到成功 ===')
                return True
            else:
                self._log('error', '=== NodeSeek任务失败：签到失败 ===')
                return False
                
        except Exception as e:
            self._log('error', f'NodeSeek任务执行异常: {e}')
            return False


if __name__ == '__main__':
    signer = NodeSeekSigner(debug=False, output_collector=None)
    try:
        success = signer.run()
        if success:
            logger.success("NodeSeek 自动签到任务执行成功")
        else:
            logger.error("NodeSeek 自动签到任务执行失败")
    except KeyboardInterrupt:
        logger.info("用户中断操作")
    except Exception as e:
        logger.error(f"程序执行异常: {e}")
