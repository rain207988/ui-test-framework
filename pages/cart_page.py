"""购物车页面对象：行数/总价读取、改数量、删商品、去结算。

本页的同步难点：每个行内操作（更新/删除）都是 form POST -> 302 重回 /cart，
点击返回时新页面还没渲染。所有操作方法内部都先等待对应 flash 出现
（"数量已更新"/"已删除"）再返回，调用方拿到的必然是新页面，读取行数/总价零竞态。
"""

from selenium.webdriver.common.by import By

from base.base_page import FLASH_MESSAGE, BasePage


class CartPage(BasePage):
    PATH = "/cart"

    CART_TABLE = (By.ID, "cart-table")
    CART_ROWS = (By.CSS_SELECTOR, "#cart-table tr.cart-row")   # 购物车行
    CART_TOTAL = (By.ID, "cart-total")                          # 合计金额
    CART_EMPTY = (By.ID, "cart-empty")                          # 空购物车提示
    FLASH = FLASH_MESSAGE
    # 行内元素（无 id，CSS 选择器限定在行内）
    ROW_QTY_INPUT = (By.CSS_SELECTOR, "input.cart-qty")         # 数量输入框
    ROW_UPDATE_BTN = (By.CSS_SELECTOR, "button.btn-update-qty")  # 更新按钮
    ROW_DELETE_BTN = (By.CSS_SELECTOR, "button.btn-delete-item")  # 删除按钮
    CHECKOUT_LINK = (By.ID, "btn-checkout")                     # 去结算链接

    def open_cart(self):
        self.open(self.PATH)
        self.find(self.CART_TABLE)
        return self

    # ---------------- 状态读取 ---------------- #

    def row_count(self) -> int:
        """购物车商品行数（空车时模板不渲染 tr.cart-row，自然返回 0）。"""
        return len(self.find_all(self.CART_ROWS))

    def total(self) -> str:
        """合计金额字符串，如 '398.00'。"""
        return self.get_text(self.CART_TOTAL)

    def row_subtotal(self, index: int) -> str:
        """第 index 行小计金额。"""
        return self._row(index).find_element(By.CSS_SELECTOR, "td.cart-subtotal").text

    def _row(self, index: int):
        rows = self.find_all(self.CART_ROWS)
        if index >= len(rows):
            raise IndexError(f"购物车行索引越界：index={index}，实际行数={len(rows)}")
        return rows[index]

    def is_empty(self) -> bool:
        """是否显示空购物车提示。"""
        return self.is_displayed(self.CART_EMPTY)

    # ---------------- 行级操作 ---------------- #

    def update_quantity(self, index: int, quantity: int) -> str:
        """把第 index 行数量改为 quantity 并点更新，返回 flash 文本。

        实现细节：数量输入框在行内的 <form> 里，先取行元素再在其中定位输入框；
        点击更新后等 flash"数量已更新"出现——这一步同时完成了"等新页面渲染"。
        """
        row = self._row(index)
        qty_input = row.find_element(*self.ROW_QTY_INPUT)
        qty_input.clear()
        qty_input.send_keys(str(quantity))
        row.find_element(*self.ROW_UPDATE_BTN).click()
        return self.wait_flash_contains("数量已更新")

    def delete_item(self, index: int) -> str:
        """删除第 index 行商品，返回 flash 文本（含"已删除"）。"""
        self._row(index).find_element(*self.ROW_DELETE_BTN).click()
        return self.wait_flash_contains("已删除")

    def checkout(self):
        """点击"去结算"进入确认订单页，交接 CheckoutPage。"""
        self.click(self.CHECKOUT_LINK)
        from pages.checkout_page import CheckoutPage
        page = CheckoutPage(self.driver)
        page.wait_ready()
        return page
