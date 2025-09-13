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
import requests
from lxml import etree
from loguru import logger

url = "https://checkin.leaflow.net/index.php"
cookies = {
    "PHPSESSID": os.getenv('LEAFLOW_COOKIE'),
}
headers = {
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

data = "checkin="

try:
    res = requests.post(url, headers=headers, cookies=cookies, data=data)

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
            logger.success(f'{prompt[0]}, {prompt[1]}')

        if reward:
            logger.success(f'{checkin}：{reward[0]}')

        if calendar:
            logger.success(f'{calendar}')

        # 处理历史记录数据
        if history_detail:
            # 按照每两个元素一组进行配对（日期和金额），每一天单独输出
            for i in range(0, len(history_detail), 2):
                if i + 1 < len(history_detail):
                    date = history_detail[i]
                    amount = history_detail[i + 1]
                    logger.success(f'{history_title}：{date}丨{amount}')

    else:
        logger.error(f"请求失败，状态码: {res.status_code}")

except requests.exceptions.RequestException as e:
    logger.error(f"请求异常: {e}")
except Exception as e:
    logger.error(f"处理异常: {e}")