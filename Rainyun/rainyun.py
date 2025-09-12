# -*- coding:utf-8 -*-
# @Software       :PyCharm
# @Project        :PythonProject
# @Path           :/
# @FileName       :rainyun.py
# @Time           :2025/8/28 00:13
# @Author         :Viper373
# @GitHub         :https://github.com/Viper373
# @Home           :https://viper3.top
# @Blog           :https://blog.viper3.top

import configparser
from DrissionPage import Chromium

config = configparser.ConfigParser()

config.read('env.ini')

username = config['User']['username']
password = config['User']['password']

tab = Chromium().latest_tab
tab.get('https://rainyun.cn/')
login_button = tab.ele('.btn btn-relief-primary btn-primary')
login_button.click()

username = tab.ele('xpath://input[@name="login-field"]').input(username)
password = tab.ele('xpath://input[@name="login-password"]').input(password)

submit_button = tab.ele('xpath://button[@type="submit"]')
submit_button.click()

tab.get('https://app.rainyun.com/account/reward/earn')
