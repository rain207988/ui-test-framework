"""登录模块用例：成功、失败（数据驱动）、登出、未登录访问受保护页。

命名与分层约定：
- 类名 Test 前缀（pytest 收集约定），每个类挂 @allure.feature；
- 用例方法名 = "被测行为 + 预期结果"，读用例名就知道验证什么；
- 用例体遵守 AAA 结构：Arrange（准备）- Act（操作）- Assert（断言），
  断言只出现在用例层——这是 PO 分层纪律。
"""

import allure
import pytest

from common.config_loader import config
from common.data_loader import load_yaml
from pages.goods_page import GoodsPage
from pages.login_page import LoginPage


@allure.feature("登录模块")
class TestLogin:
    """登录页主流程。"""

    @allure.story("登录成功")
    @pytest.mark.smoke
    def test_login_success(self, driver):
        """lemon 正确密码登录：跳转商品页，导航栏出现"你好，柠檬"。"""
        page = LoginPage(driver).open_login_page()
        page.login_and_expect_success("lemon", "123456")

        # 断言1：登录成功后落在商品页（Flask 302 到 /goods）
        assert "/goods" in driver.current_url
        # 断言2：导航栏用户问候显示昵称（同时证明 session 已建立、页面是登录态渲染）
        goods = GoodsPage(driver)
        assert goods.nav_user_text() == "你好，柠檬"

    @allure.story("登录成功")
    def test_login_success_second_account(self, driver):
        """第二个种子账号 test 也能正常登录（防止用例只对单一账号有效）。"""
        page = LoginPage(driver).open_login_page()
        page.login_and_expect_success("test", "123456")
        assert GoodsPage(driver).nav_user_text() == "你好，测试号"

    @allure.story("登录失败")
    @pytest.mark.parametrize(
        "case",
        load_yaml(config["users_file"])["invalid_accounts"],
        ids=lambda c: c["case_name"],       # 报告里显示中文用例名而非 case0/case1
    )
    def test_login_failed_data_driven(self, driver, case):
        """数据驱动登录失败：错误密码/不存在用户/空用户名都提示"用户名或密码错误"。

        parametrize 直接吃 YAML 里的字典列表——新增失败场景只需在 users.yaml
        加一条记录，用例代码零改动，这就是数据驱动的价值。
        """
        page = LoginPage(driver).open_login_page()
        page.login(case["username"], case["password"])

        # 登录失败不跳转（仍在 /login），flash 出现统一错误文案
        actual_flash = page.flash_text_after_submit(case["expected_flash"])
        assert case["expected_flash"] in actual_flash
        assert "/login" in driver.current_url

    @allure.story("登出")
    def test_logout(self, driver):
        """登录后退出：回到登录页，导航栏重新出现"登录"入口。"""
        page = LoginPage(driver).open_login_page()
        page.login_and_expect_success("lemon", "123456")

        page.logout()
        assert "/login" in driver.current_url
        assert page.is_displayed(LoginPage.NAV_LOGIN_LINK), "退出后应重新出现登录入口"

    @allure.story("未登录访问保护页")
    def test_cart_requires_login(self, driver):
        """未登录直接访问 /cart：被重定向到登录页并提示"请先登录"。"""
        # 直接 GET /cart（不经登录页），服务端 web_login_required 拦截并 302
        driver.get(f"{config['base_url']}/cart")

        login = LoginPage(driver)
        assert "/login" in driver.current_url, "未登录访问 /cart 应被重定向到登录页"
        flash_text = login.wait_flash_contains("请先登录")
        assert "请先登录" in flash_text
