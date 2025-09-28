# -*- coding:utf-8 -*-
# @Software       :PyCharm
# @Project        :AutoTasks
# @Path           :/leaflow
# @FileName       :leaflow.py
# @Time           :2025/9/13 10:19
# @Author         :Viper373
# @GitHub         :https://github.com/Viper373
# @Home           :https://viper3.top
# @Blog           :https://blog.viper3.top

import os
from typing import Optional, Any

import requests
from lxml import etree
from loguru import logger


class LeaflowSigner:
    """Leaflow 自动签到工具"""

    def __init__(self, debug: bool = False, output_collector: Optional[Any] = None) -> None:
        self.url = "https://checkin.leaflow.net/index.php"
        self.ver = "1.0-DP"
        self.debug = debug
        self.cookies = {
            "PHPSESSID": os.getenv('LEAFLOW_COOKIE'),
        }
        self.headers = {
            "Host": "checkin.leaflow.net",
            "Connection": "keep-alive",
            "Cache-Control": "max-age=0",
            "sec-ch-ua": "\"Chromium\";v=\"140\", \"Not=A?Brand\";v=\"24\", \"Microsoft Edge\";v=\"140\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"Windows\"",
            "Origin": "https://checkin.leaflow.net",
            "Content-Type": "application/x-www-form-urlencoded",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 Edg/140.0.0.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-User": "?1",
            "Sec-Fetch-Dest": "iframe",
            "Referer": "https://checkin.leaflow.net/index.php",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6,ja;q=0.5,ko;q=0.4,fr;q=0.3"
        }
        self.data = "checkin="
        self.output_collector = output_collector
        self._setup_logger()
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
        logger.info(f"🍃  Leaflow签到工具 v{self.ver} by Viper373")
        logger.info("📦  Requests版本 - 简单HTTP签到")
        logger.info("🔗  Github: https://github.com/Viper373/AutoTasks")
        logger.info("=" * 70)

    def run(self) -> None:
        """运行签到任务"""
        try:
            res = requests.post(self.url, headers=self.headers, cookies=self.cookies, data=self.data)

            if res.status_code == 200:
                html = etree.HTML(res.text)

                # 获取各种数据
                checkin = html.xpath("string(//button[@class='checkin-btn'])").strip()
                reward = html.xpath("//div[@class='reward-amount']/text()")
                prompt = html.xpath("//p[@class='mb-0']/text()")
                calendar = html.xpath("string(//div[@class='streak-badge'])").strip()

                history_title = html.xpath("string(//h5[@class='mb-0'])").strip()
                history_detail = html.xpath("//div[@class='history-item']//span/text()")

                # 安全地输出信息，添加索引检查
                if prompt and len(prompt) >= 2:
                    self._log('success', f'{prompt[0]}, {prompt[1]}')

                if reward:
                    self._log('success', f'{checkin}：{reward[0]}')

                if calendar:
                    self._log('success', f'{calendar}')

                if history_title:
                    self._log('success', f'{history_title}')

                if history_detail:
                    for i in range(0, len(history_detail), 2):
                        if i + 1 < len(history_detail):
                            self._log('success', f'签到历史：{history_detail[i]}丨{history_detail[i + 1]}')

            else:
                self._log('error', f"HTTP请求失败，状态码: {res.status_code}")

        except Exception as e:
            self._log('error', f"签到失败：{e}")


def main():
    """主函数"""
    signer = LeaflowSigner()
    signer.run()


if __name__ == "__main__":
    main()