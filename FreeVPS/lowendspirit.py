# -*- coding:utf-8 -*-
# @Software       :PyCharm
# @Project        :Auto-Signin
# @Path           :/FreeVPS
# @FileName       :lowendspirit.py
# @Time           :2025/1/8
# @Author         :Viper373
# @GitHub         :https://github.com/Viper373
# @Home           :https://viper3.top
# @Blog           :https://blog.viper3.top

import os
from DrissionPage import Chromium, ChromiumOptions
from loguru import logger
from pathlib import Path
import tools


class Lowendtalk:

    def __init__(self) -> None:
        self.url = "https://lowendspirit.com/"
        self.new_topic_url = "https://lowendspirit.com/post/discussion"
        self.tab = Chromium().latest_tab

    def read_config(self) -> tuple[str, str]:
        """从环境变量读取。"""
        env_user = os.getenv('LES_USERNAME') or os.getenv('LOWEND_USERNAME')
        env_pass = os.getenv('LES_PASSWORD') or os.getenv('LOWEND_PASSWORD')
        if env_user and env_pass:
            return env_user, env_pass
        raise RuntimeError('未通过环境变量获得 LowEndSpirit 凭据')

    def check_login_status(self):
        """
        检查是否已经登录
        :param username: 用户名
        :return: 是否已登录
        """
        try:
            # 查找class为Username的a标签
            if self.tab.ele('xpath://a[@class="Button Primary Action NewDiscussion BigButton"]'):
                logger.info("检测到已登录")
                return True
            else:
                logger.info("未找到用户名元素，可能未登录")
                return False
        except Exception as e:
            logger.warning(f"检查登录状态失败: {e}")
            return False

    def login(self, username: str, password: str):
        """
        登录LowEndTalk论坛
        :param username: 用户名
        :param password: 密码
        :return: 是否登录成功
        """
        try:
            logger.info("开始登录LowEndTalk论坛...")
            # 先访问论坛首页
            self.tab.get(self.url)
            self.tab.wait.load_start()

            # 检查是否已经登录
            if self.check_login_status():
                logger.info("用户已登录，跳过登录流程")
                return True

            # 点击登录按钮
            sign_in = self.tab.ele("xpath://a[@class='SignInPopup']")
            sign_in.click()

            # 查找用户名输入框
            username_input = self.tab.ele("xpath://input[@id='Form_Email']")

            # 查找密码输入框
            password_input = self.tab.ele("xpath://input[@id='Form_Password']")

            # 输入用户名和密码
            username_input.input(username)
            password_input.input(password)

            # 查找登录按钮并点击
            login_button = self.tab.ele("xpath://input[@id='Form_SignIn']")
            login_button.click()
            self.tab.wait.load_start()

        except Exception as e:
            logger.error(f"登录过程出现异常: {e}")
            return False

    def create_new_topic(self, title: str, content: str):
        """
        创建新话题
        :param title: 话题标题
        :param content: 话题内容
        :return: 是否创建成功
        """
        try:
            logger.info("开始创建新话题...")
            self.tab.get(self.new_topic_url)
            self.tab.wait.load_start()

            # 查找标题输入框
            title_input = self.tab.ele("xpath://input[@id='Form_Name']")

            # 输入标题
            title_input.input(title)

            # 查找内容输入框
            content_input = self.tab.ele("xpath://textarea[@id='Form_Body']")

            # 输入内容
            content_input.input(content)

            # 选择分类
            self.tab.ele("xpath://select[@id='Form_CategoryID']")("xpath://option[@value='1']").click()

            # 查找发布按钮
            submit_button = self.tab.ele("xpath://input[@id='Form_PostDiscussion']")

            # 点击发布
            submit_button.click()
            self.tab.wait.load_start()

            logger.info("话题发布成功！")

        except Exception as e:
            logger.error(f"创建话题过程出现异常: {e}")
            return False

    def run_task(self, title: str, content: str):
        """
        自动发布帖子主任务
        :param title: 帖子标题
        :param content: 帖子内容
        :return: None
        """
        try:
            username, password = self.read_config()
            full_title = tools.translate_text(title, origin_lang="auto", target_lang="en")
            full_content = tools.translate_text(content, origin_lang="auto", target_lang="en")
            # 登录并发布
            if self.login(username, password):
                if self.create_new_topic(full_title, full_content):
                    logger.info("LowEndTalk帖子发布完成！")
                else:
                    logger.error("帖子发布失败")
            else:
                logger.error("登录失败，无法发布帖子")
        except Exception as e:
            logger.error(f'run_task执行失败: {e}')
            logger.exception('详细错误信息:')


if __name__ == "__main__":
    # 使用示例
    lowendtalk = Lowendtalk()

    try:
        logger.info("开始自动发布任务...")
        title, content = tools.get_vps_article()
        lowendtalk.run_task(title, content)

    except Exception as e:
        logger.error(f"主程序执行失败: {e}")
    finally:
        lowendtalk.tab.close()