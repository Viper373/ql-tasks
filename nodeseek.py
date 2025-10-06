"""
cron: 0 9 * * *
new Env('nodeseek签到')
"""

import os
import random
import time
import json
from datetime import datetime
import cloudscraper
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


def format_time_remaining(seconds: int) -> str:
    if seconds <= 0:
        return "立即执行"
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours > 0:
        return f"{hours}小时{minutes}分{secs}秒"
    if minutes > 0:
        return f"{minutes}分{secs}秒"
    return f"{secs}秒"


def wait_with_countdown(delay_seconds: float, task_name: str) -> None:
    if delay_seconds <= 0:
        return
    logger.info(f"{task_name} 需要等待 {format_time_remaining(int(delay_seconds))}")
    time.sleep(delay_seconds)


def notify_user(title: str, content: str) -> None:
    if hadsend:
        try:
            send(title, content)
            logger.info(f"通知发送完成: {title}")
        except Exception as e:
            logger.error(f"通知发送失败: {e}")
    else:
        logger.info(f"{title}\n{content}")


def create_scraper():
    return cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        }
    )


def parse_result_text(text: str) -> tuple[bool, str]:
    try:
        data = json.loads(text)
    except Exception:
        return False, text[:200]

    success = bool(data.get("success"))
    msg = data.get("message") or data.get("msg") or text[:200]
    return success, msg


def main():
    logger.info(f"==== NodeSeek签到开始 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ====")

    # 随机延迟总开关：默认启用，只有 NODESEEK_RANDOM='false' 才关闭
    random_enabled = os.getenv('NODESEEK_RANDOM', 'true').lower() != 'false'

    # 整体短随机延迟（与其它任务一致）
    overall_delay = random.randint(1, 3) if random_enabled else 0
    if overall_delay > 0:
        logger.info(f"随机延迟: {format_time_remaining(overall_delay)}")
        wait_with_countdown(overall_delay, "NodeSeek签到")

    cookies_env = os.getenv('NODESEEK_COOKIE')
    if not cookies_env.strip():
        err = "未找到NODESEEK_COOKIE环境变量"
        logger.error(err)
        notify_user("NodeSeek 签到失败", err)
        return

    cookie_list = [c.strip() for c in cookies_env.split('&') if c.strip()]
    logger.info(f"共发现 {len(cookie_list)} 个账号")

    url = f"https://www.nodeseek.com/api/attendance?random={'true' if random_enabled else 'false'}"
    headers = {
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Content-Length': '0',
        'Origin': 'https://www.nodeseek.com',
        'Referer': 'https://www.nodeseek.com/board',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
    }

    success_count = 0
    total_count = len(cookie_list)

    scraper = create_scraper()

    for idx, cookie in enumerate(cookie_list):
        display_user = f"账号{idx + 1}"

        if idx > 0:
            delay_between = random.uniform(5, 15) if random_enabled else 0
            if delay_between > 0:
                logger.info(f"随机等待 {delay_between:.1f} 秒后处理下一个账号...")
                time.sleep(delay_between)

        logger.info(f"==== {display_user} 开始签到 ====")
        logger.info(f"当前时间: {datetime.now().strftime('%H:%M:%S')}")

        short_delay = random.uniform(0, 1) if random_enabled else 0
        if short_delay > 0:
            logger.info(f"短暂随机延迟: {short_delay:.1f} 秒")
            time.sleep(short_delay)

        cookie_dict = {}
        for item in cookie.split(';'):
            if '=' in item:
                key, value = item.split('=', 1)
                cookie_dict[key.strip()] = value.strip()

        try:
            resp = scraper.post(url, headers=headers, cookies=cookie_dict, timeout=30)
            ok, msg = parse_result_text(resp.text)
            logger.debug(f"{display_user} 响应状态码: {resp.status_code}")

            def is_already_signed(message: str) -> bool:
                if not isinstance(message, str):
                    return False
                lower_msg = message.lower()
                return (
                    ("已完成" in message)
                    or ("已签到" in message)
                    or ("重复" in message)
                    or ("today" in lower_msg and "signed" in lower_msg)
                    or ("already" in lower_msg)
                    or ("completed" in lower_msg)
                )

            already_signed = is_already_signed(msg)
            if already_signed or (resp.status_code == 200 and ok):
                success_count += 1
                if ok and not already_signed:
                    logger.info(f"{display_user} 签到成功: {msg}")
                    notify_user("NodeSeek 签到", f"{display_user} 签到成功：{msg}")
                else:
                    logger.info(f"{display_user} 今日已签到: {msg}")
                    notify_user("NodeSeek 签到", f"{display_user} 今日已签到：{msg}")
            else:
                logger.error(f"{display_user} 签到失败: {msg}")
                notify_user("NodeSeek 签到失败", f"{display_user} 签到失败：{msg}")
        except Exception as e:
            logger.error(f"{display_user} 签到异常: {e}")
            notify_user("NodeSeek 签到失败", f"{display_user} 签到异常：{e}")

    if total_count > 1:
        summary = (
            f"NodeSeek签到汇总\n\n"
            f"总计: {total_count}个账号\n"
            f"成功: {success_count}个\n"
            f"失败: {total_count - success_count}个\n"
            f"完成时间: {datetime.now().strftime('%m-%d %H:%M')}"
        )
        notify_user("NodeSeek 签到汇总", summary)

    logger.info(f"==== NodeSeek签到完成 - 成功{success_count}/{total_count} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ====")


if __name__ == "__main__":
    main()