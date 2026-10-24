"""确认订单（结算）页面对象：读应付金额、提交订单。"""

from selenium.webdriver.common.by import By

from base.base_page import BasePage


class CheckoutPage(BasePage):
    PATH = "/checkout"

    CHECKOUT_TABLE = (By.ID, "checkout-table")
    CHECKOUT_TOTAL = (By.ID, "checkout-total")     # 应付金额
    CHECKOUT_FORM = (By.ID, "checkout-form")
    SUBMIT_BUTTON = (By.ID, "btn-submit-order")    # 提交订单按钮

    def wait_ready(self):
        """结算页就绪标志：结算表格可见。"""
        self.find(self.CHECKOUT_TABLE)
        return self

    def total(self) -> str:
        """应付金额字符串，如 '398.00'。"""
        return self.get_text(self.CHECKOUT_TOTAL)

    def submit_order(self):
        """提交订单：POST /checkout -> 302 到订单页并闪出"下单成功，订单号 ORD..."。

        这里只负责点击；等待"下单成功"flash / 读取订单行是订单页对象的事
        （下一个页面对象负责自己的就绪同步），保持每页职责单一。
        """
        self.click(self.SUBMIT_BUTTON)
        from pages.orders_page import OrdersPage
        page = OrdersPage(self.driver)
        page.wait_ready()
        return page
