"""我的订单页面对象：订单行读取、支付、取消。"""

from selenium.webdriver.common.by import By

from base.base_page import FLASH_MESSAGE, BasePage


class OrdersPage(BasePage):
    PATH = "/orders"

    ORDERS_TABLE = (By.ID, "orders-table")
    ORDER_ROWS = (By.CSS_SELECTOR, "#orders-table tr.order-row")   # 订单行
    ORDERS_EMPTY = (By.ID, "orders-empty")                          # 无订单提示
    FLASH = FLASH_MESSAGE
    # 行内元素：状态格 / 支付按钮 / 取消按钮（无 id，行内 CSS 选择器）
    ROW_STATUS = (By.CSS_SELECTOR, "td.order-status")
    ROW_PAY_BTN = (By.CSS_SELECTOR, "button.btn-pay-order")
    ROW_CANCEL_BTN = (By.CSS_SELECTOR, "button.btn-cancel-order")

    def open_orders(self):
        self.open(self.PATH)
        self.find(self.ORDERS_TABLE)
        return self

    def wait_ready(self):
        """订单页就绪标志：表格可见（无订单时表格同样渲染，只是内容是提示行）。"""
        self.find(self.ORDERS_TABLE)
        return self

    # ---------------- 状态读取 ---------------- #

    def row_count(self) -> int:
        return len(self.find_all(self.ORDER_ROWS))

    def _row(self, index: int):
        rows = self.find_all(self.ORDER_ROWS)
        if index >= len(rows):
            raise IndexError(f"订单行索引越界：index={index}，实际行数={len(rows)}")
        return rows[index]

    def row_order_no(self, index: int) -> str:
        """第 index 行订单号（ORD 开头）。"""
        return self._row(index).find_element(By.CSS_SELECTOR, "td.order-no").text

    def row_status(self, index: int) -> str:
        """第 index 行状态文本：pending / paid / cancelled。"""
        return self._row(index).find_element(*self.ROW_STATUS).text

    def row_status_class(self, index: int) -> str:
        """状态格的 class 属性（如 'order-status status-paid'）。

        断言"状态已变"时除了文本还可验证状态样式类，双保险：
        文本断言业务含义，class 断言前端渲染分支真的走到了 paid 那条线。
        """
        return self._row(index).find_element(*self.ROW_STATUS).get_attribute("class")

    def has_cancel_button(self, index: int) -> bool:
        """第 index 行是否还有"取消"按钮。

        模板里只有 pending 订单才渲染取消按钮，所以"按钮消失"本身就是
        "paid 订单不允许取消"这个业务规则的 UI 表现。用 find_elements 取列表
        （没有就返回空列表）而不是 find_element（没有会抛异常），存在性判断
        一律用 find_elements 判长度。
        """
        return len(self._row(index).find_elements(*self.ROW_CANCEL_BTN)) > 0

    def is_empty(self) -> bool:
        return self.is_displayed(self.ORDERS_EMPTY)

    # ---------------- 行级操作 ---------------- #

    def pay(self, index: int) -> str:
        """支付第 index 行订单，等待"支付成功"flash 并返回文本。"""
        self._row(index).find_element(*self.ROW_PAY_BTN).click()
        return self.wait_flash_contains("支付成功")

    def cancel(self, index: int) -> str:
        """取消第 index 行订单，等待"订单已取消"flash 并返回文本。"""
        self._row(index).find_element(*self.ROW_CANCEL_BTN).click()
        return self.wait_flash_contains("订单已取消")
