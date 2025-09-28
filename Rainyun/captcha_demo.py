import time
from loguru import logger

from rainyun import RainyunSigner
from DrissionPage import Chromium


def main():
    # 创建浏览器实例
    browser = Chromium()
    signer = RainyunSigner(debug=True)
    try:
        # 初始化组件
        signer.init_ocr()
        signer.init_browser()

        # 设置页面对象
        signer.page = browser.latest_tab

        logger.info("打开注册页")
        signer.page.get("https://app.rainyun.com/auth/reg")
        time.sleep(2)

        # 填写注册表单
        username = signer.page.ele('xpath://*[@id="username"]', timeout=signer.timeout)
        pwd = signer.page.ele('xpath://input[@name="register-password"]', timeout=signer.timeout)
        repwd = signer.page.ele('xpath://input[@name="register-repassword"]', timeout=signer.timeout)
        privacy_input = signer.page.ele('xpath://*[@id="register-privacy-policy"]', timeout=signer.timeout)
        privacy_input.click()
        submit_btn = signer.page.ele('xpath://button[@type="submit"]', timeout=signer.timeout)

        if not all([username, pwd, repwd, submit_btn]):
            logger.error("注册页元素未找到，终止")
            return

        username.clear()
        username.input("Viper")
        time.sleep(0.3)
        pwd.clear()
        pwd.input("Passw0rd!@#")
        time.sleep(0.3)
        repwd.clear()
        repwd.input("Passw0rd!@#")
        time.sleep(0.3)

        logger.info("提交注册，触发验证码")
        submit_btn.click()
        time.sleep(2)

        # 进入验证码 iframe 并调用统一处理
        captcha_iframe = signer.page.ele('xpath://*[@id="tcaptcha_iframe_dy"]', timeout=5)
        if captcha_iframe:
            logger.warning("触发验证码！开始处理")
            iframe_page = signer.page.get_frame('tcaptcha_iframe_dy')
            temp_page = signer.page
            signer.page = iframe_page
            signer.process_captcha()
            signer.page = temp_page
        else:
            logger.info("未触发验证码，结束")

        time.sleep(3)
    except Exception as e:
        logger.exception(f"demo 运行异常: {e}")
    finally:
        signer.cleanup()
        # 关闭浏览器
        try:
            browser.quit()
        except:
            pass


if __name__ == "__main__":
    main()
