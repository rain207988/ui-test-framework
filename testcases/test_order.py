"""订单模块用例：e2e 下单、支付、取消、状态机规则、未登录访问。

订单状态机（被测系统业务规则）：
    pending --支付--> paid（终态，不再提供取消入口）
    pending --取消--> cancelled（库存回滚）
UI 层的表现：只有 pending 订单行才渲染"支付/取消"按钮，
paid 行的取消按钮消失——这就是"状态不允许"的 UI 断言点。
"""

import allure
import pytest

from common.config_loader import config
from pages.cart_page import CartPage
from pages.checkout_page import CheckoutPage
from pages.goods_detail_page import GoodsDetailPage
from pages.goods_page import GoodsPage
from pages.login_page import LoginPage
from pages.orders_page import OrdersPage


def _create_pending_order(logged_in) -> OrdersPage:
    """公共前置：通过完整 UI 链路下一单——列表加购第 1 件 -> 购物车 -> 结算 -> 提交。

    返回时订单页已就绪且"下单成功"flash 已出现。
    """
    driver = logged_in.driver
    goods = GoodsPage(driver).open_goods_page()
    goods.add_to_cart_by_row(0)
    goods.go_cart_by_nav()

    cart = CartPage(driver)
    cart.find(CartPage.CART_TABLE)
    checkout = cart.checkout()
    orders = checkout.submit_order()
    orders.wait_flash_contains("下单成功")
    return orders


@allure.feature("订单模块")
class TestCreateOrder:

    @allure.story("e2e下单")
    @pytest.mark.smoke
    def test_e2e_create_order_pending(self, reset_data, logged_in):
        """全链路 e2e：搜索 -> 详情 -> 加购2件 -> 结算 -> 提交 -> 出现 pending 订单。"""
        driver = logged_in.driver

        # Act：搜索"耳机"进详情，改数量为 2 加购
        goods = GoodsPage(driver).open_goods_page()
        goods.search("耳机")
        detail = goods.open_detail_by_row(0)
        assert detail.name() == "无线蓝牙耳机"
        detail.set_quantity(2).add_to_cart()

        # 购物车 -> 结算，金额 = 2 x 199.00
        logged_in.go_cart_by_nav()
        cart = CartPage(driver)
        cart.find(CartPage.CART_TABLE)
        assert cart.total() == "398.00"
        checkout = cart.checkout()
        assert checkout.total() == "398.00"

        # 提交订单 -> 订单页
        orders = checkout.submit_order()
        flash_text = orders.wait_flash_contains("下单成功")

        # Assert：订单页出现 1 条 pending 订单，订单号 ORD 开头
        assert "下单成功" in flash_text
        assert orders.row_count() == 1
        assert orders.row_status(0) == "pending"
        assert orders.row_order_no(0).startswith("ORD")

    @allure.story("未登录访问保护页")
    def test_orders_requires_login(self, driver):
        """未登录直接访问 /orders：重定向登录页并提示"请先登录"。"""
        driver.get(f"{config['base_url']}/orders")

        login = LoginPage(driver)
        assert "/login" in driver.current_url
        assert "请先登录" in login.wait_flash_contains("请先登录")


@allure.feature("订单模块")
class TestOrderActions:

    @allure.story("支付订单")
    def test_pay_pending_order(self, reset_data, logged_in):
        """pending 订单点支付：状态 pending -> paid，提示"支付成功"。"""
        orders = _create_pending_order(logged_in)
        assert orders.row_status(0) == "pending"

        flash_text = orders.pay(0)      # 方法内部已等"支付成功"flash

        assert "支付成功" in flash_text
        assert orders.row_status(0) == "paid"
        assert "status-paid" in orders.row_status_class(0)

    @allure.story("取消订单")
    def test_paid_order_cannot_cancel(self, reset_data, logged_in):
        """paid 是终态：支付后该行取消按钮消失，状态保持 paid。"""
        orders = _create_pending_order(logged_in)
        orders.pay(0)

        assert not orders.has_cancel_button(0), "paid 订单不应再渲染取消按钮"
        assert orders.row_status(0) == "paid"

    @allure.story("取消订单")
    def test_cancel_pending_order_restores_stock(self, reset_data, logged_in):
        """取消 pending 订单：状态变 cancelled，且库存回滚到 50。"""
        orders = _create_pending_order(logged_in)
        assert orders.row_status(0) == "pending"

        flash_text = orders.cancel(0)

        assert "订单已取消" in flash_text
        assert orders.row_status(0) == "cancelled"
        assert "status-cancelled" in orders.row_status_class(0)

        # 库存回滚验证：下单扣了 1 件库存（50->49），取消应恢复（49->50）
        detail = GoodsDetailPage(orders.driver).open_detail(1)
        assert detail.stock() == "50"
