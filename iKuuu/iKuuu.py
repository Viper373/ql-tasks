# -*- coding:utf-8 -*-
# @Software       :PyCharm
# @Project        :AutoTasks
# @Path           :/iKuuu
# @FileName       :iKuuu.py
# @Time           :2025/9/7 09:33
# @Author         :Viper373
# @GitHub         :https://github.com/Viper373
# @Home           :https://viper3.top
# @Blog           :https://blog.viper3.top

import os
import time
import random
from typing import Dict, Optional, Any

from DrissionPage import Chromium, ChromiumOptions
from loguru import logger


class IKuuuClient:
    """iKuuu 自动登录与签到客户端"""

    def __init__(self, config_path: str = '../env.ini', debug: bool = False, output_collector: Optional[Any] = None) -> None:
        self.config_path = config_path
        self.username: Optional[str] = None
        self.password: Optional[str] = None
        self.browser: Optional[Chromium] = None
        self.tab: Optional[Any] = None
        self.base_url = 'https://ikuuu.org/user'
        self.ver = "1.0-DP"
        self.debug = debug
        self.output_collector = output_collector
        self._setup_logger()
        self._load_config()
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
        logger.info(f"🚀  iKuuu签到工具 v{self.ver} by Viper373")
        logger.info("📦  DrissionPage版本 - 自动登录与签到")
        logger.info("🔗  Github: https://github.com/Viper373/AutoTasks")
        logger.info("=" * 70)

    def _random_wait(self, max_seconds: float = 2.0) -> None:
        """随机等待0-max_seconds秒"""
        wait_time = random.uniform(0, max_seconds)
        time.sleep(wait_time)

    def _load_config(self) -> bool:
        """从环境变量读取配置"""
        env_user = os.getenv('IKUUU_USERNAME')
        env_pass = os.getenv('IKUUU_PASSWORD')
        if env_user and env_pass:
            self.username, self.password = env_user, env_pass
            logger.info("已从环境变量加载 iKuuu 配置")
            return True
        logger.error("缺少 IKUUU_USERNAME/IKUUU_PASSWORD 环境变量")
        return False

    def start(self) -> bool:
        """启动浏览器"""
        try:
            # 浏览器由全局管理器提供，直接使用
            if not self.browser or not self.tab:
                logger.error("浏览器未初始化")
                return False
            logger.info("使用全局浏览器实例")
            return True
        except Exception as e:
            logger.error(f"浏览器启动失败: {e}")
            return False

    def navigate_to_profile(self) -> bool:
        """导航到用户页面"""
        try:
            self.tab.get(self.base_url)
            self._random_wait(1.0)
            logger.info("成功导航到用户页面")
            return True
        except Exception as e:
            logger.error(f"导航到用户页面失败: {e}")
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
                            logger.info("用户已登录")
                            return True
                except:
                    continue
            
            logger.info("用户未登录")
            return False
        except Exception as e:
            logger.warning(f"检查登录状态时出错: {e}")
            return False

    def login(self) -> bool:
        """登录操作"""
        try:
            logger.info("开始尝试登录...")

            # 查找登录表单元素
            email_input = self.tab.ele('xpath://input[@id="email"]', timeout=5)
            pwd_input = self.tab.ele('xpath://input[@id="password"]', timeout=5)

            if not email_input or not pwd_input:
                # 可能已经登录了，检查一下
                if self.is_logged_in():
                    logger.info("用户已登录，无需重复登录")
                    return True
                logger.error("未找到登录表单元素")
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
                logger.error("未找到登录按钮")
                return False

            submit_btn.click()
            self._random_wait()

            # 检查登录结果
            if self.is_logged_in():
                logger.success("登录成功")
                return True
            else:
                logger.error("登录失败，请检查用户名和密码")
                return False

        except Exception as e:
            logger.error(f"登录过程中发生异常: {e}")
            return False

    def checkin(self) -> bool | None:
        """签到操作"""
        try:
            logger.info("开始尝试签到...")

            btn = self.tab.ele('xpath://div[@id="checkin-div"]', timeout=5)
            if not btn:
                logger.error("未找到签到按钮")
                return False

            # 检查按钮当前状态
            current_text = btn.text or ''
            if '明日再来' in current_text:
                logger.info("今日已签到")
                return True

            # 执行签到
            btn.click()
            logger.info("签到按钮已点击")
            self._random_wait(1.5)

            # 检查签到结果
            try:
                status_text = self.tab.ele('xpath://h2[@id="swal2-title"]', timeout=3)
                if status_text:
                    text = status_text.text or ''
                    if '签到成功' in text:
                        reward = self.tab.ele('xpath://div[@id="swal2-content"]', timeout=3)
                        self._log('success', f"签到成功：{reward.text}")
                        self.tab.ele('xpath://button[@class="swal2-confirm swal2-styled"]', timeout=3).click()  # 点击OK关闭弹窗
                        return True
                    else:
                        logger.warning(f"签到状态异常: {text}")
                        return False
                elif '明日再来' in self.tab.ele('xpath://div[@id="checkin-div"]', timeout=3):
                    logger.info("今日已签到")
                    return True
                else:
                    logger.error("签到异常，未找到状态提示")
                    return False
            except Exception as e1:
                logger.error(f"签到状态检查失败: {e1}")

        except Exception as e2:
            logger.error(f"签到过程中发生异常: {e2}")
            return False

    def fetch_info(self) -> bool:
        """获取用户信息"""
        try:
            logger.info("开始获取用户信息...")

            # 确保在正确的页面
            self.tab.get(self.base_url)
            time.sleep(3)

            # 查找信息卡片
            rows = self.tab.eles('xpath://div[@class="row"][1]/div[contains(@class, "col-lg-3") and contains(@class, "col-md-3") and contains(@class, "col-sm-12")]', timeout=5)
            if not rows:
                logger.warning("未找到信息卡片")
                return False

            if len(rows) < 3:
                logger.warning(f"信息卡片数量不足，期望至少3个，实际{len(rows)}个")
                return False

            def _block_text(idx: int) -> Dict[str, str]:
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
                    logger.warning(f"提取第{idx}个卡片信息失败: {e}")
                    return {'header': '', 'details': '', 'stats': ''}

            # 提取各个卡片信息并输出
            logger.info("=== 用户信息详情 ===")

            for i in range(min(len(rows), 4)):  # 最多处理4个卡片
                block_info = _block_text(i)
                header = block_info['header'].strip()
                details = block_info['details'].strip()
                stats = block_info['stats'].strip()

                if header and details:
                    if stats:
                        logger.info(f"{header}: {details} | {stats}")
                    else:
                        logger.info(f"{header}: {details}")

            self._log('success', "用户信息获取成功")
            return True

        except Exception as e:
            logger.error(f"获取用户信息时发生异常: {e}")
            return False

    def close(self) -> None:
        """关闭浏览器"""
        # 浏览器由全局管理器管理，不需要在这里关闭
        logger.info("iKuuu任务清理完成")

    def run(self) -> bool:
        """执行完整的签到流程"""
        try:
            logger.info("=== 开始执行 iKuuu 自动签到任务 ===")

            # 1. 启动浏览器
            if not self.start():
                logger.error("任务失败：浏览器启动失败")
                return False

            # 2. 导航到用户页面
            if not self.navigate_to_profile():
                logger.error("任务失败：页面导航失败")
                return False

            # 3. 检查登录状态并登录
            if not self.is_logged_in():
                if not self.login():
                    logger.error("任务失败：登录失败")
                    return False

            # 4. 执行签到
            checkin_success = self.checkin()

            # 5. 获取用户信息
            info_success = self.fetch_info()

            # 6. 汇总结果
            if checkin_success:
                if info_success:
                    self._log('success', "=== 任务完成：签到成功，信息获取成功 ===")
                else:
                    logger.success("=== 任务部分成功：签到成功，信息获取失败 ===")
                return True
            else:
                if info_success:
                    logger.error("=== 任务部分失败：签到失败，信息获取成功 ===")
                else:
                    logger.error("=== 任务失败：签到失败，信息获取失败 ===")
                return False

        except Exception as e:
            logger.error(f"执行流程时发生异常: {e}")
            return False


if __name__ == '__main__':
    client = IKuuuClient()
    try:
        success = client.run()
        if success:
            logger.success("iKuuu 自动签到任务执行成功")
        else:
            logger.error("iKuuu 自动签到任务执行失败")
    except KeyboardInterrupt:
        logger.info("用户中断操作")
    except Exception as e:
        logger.error(f"程序执行异常: {e}")
    finally:
        client.close()
