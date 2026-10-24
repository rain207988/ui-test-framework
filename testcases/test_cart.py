"""购物车模块用例：行数/总价、改数量、删商品、空购物车。

数据确定性：购物车用例对"购物车里有什么"有强假设，所以每条用例都挂
reset_data 夹具（用例开始前重置种子数据），加购动作在用例内自己完成——
"用例自带前置数据"比"依赖前面用例留下的状态"可靠一个数量级。

种子价格参照（seed.py）：无线蓝牙耳机 199.00 / 智能手表 Pro 1299.00。
"""

import allure
import pytest

from pages.cart_page import CartPage
from pages.goods_page import GoodsPage

PRICE_HEADPHONE = "199.00"      # 商品1 单价
PRICE_WATCH = "1299.00"         # 商品2 单价


def _add_two_goods_and_open_cart(logged_in) -> CartPage:
    """公共前置：把第 1、2 件商品各加购 1 件后进入购物车页。"""
    goods = GoodsPage(logged_in.driver).open_goods_page()
    goods.add_to_cart_by_row(0)
    goods.add_to_cart_by_row(1)
    goods.go_cart_by_nav()
    cart = CartPage(logged_in.driver)
    cart.find(CartPage.CART_TABLE)      # 同步：等购物车表格渲染完成
    return cart


@allure.feature("购物车模块")
class TestCart:

    @allure.story("购物车展示")
    @pytest.mark.smoke
    def test_cart_rows_and_total(self, reset_data, logged_in):
        """加购两件商品后：购物车 2 行，合计 = 199.00 + 1299.00 = 1498.00。"""
        cart = _add_two_goods_and_open_cart(logged_in)

        assert cart.row_count() == 2
        assert cart.total() == "1498.00"
        assert cart.row_subtotal(0) == PRICE_HEADPHONE
        assert cart.row_subtotal(1) == PRICE_WATCH

    @allure.story("修改数量")
    def test_update_quantity_changes_total(self, reset_data, logged_in):
        """把第 1 件数量从 1 改成 3：小计与合计变为 3 x 199.00 = 597.00。"""
        goods = GoodsPage(logged_in.driver).open_goods_page()
        goods.add_to_cart_by_row(0)
        goods.go_cart_by_nav()
        cart = CartPage(logged_in.driver)
        cart.find(CartPage.CART_TABLE)

        assert cart.total() == PRICE_HEADPHONE      # 前置确认：初始 1 件

        cart.update_quantity(0, 3)                  # 方法内部已等"数量已更新"flash
        assert cart.row_subtotal(0) == "597.00"
        assert cart.total() == "597.00"

    @allure.story("删除商品")
    def test_delete_item_decreases_rows(self, reset_data, logged_in):
        """删除第 1 行：行数 2 -> 1，合计只剩剩余那件的金额。"""
        cart = _add_two_goods_and_open_cart(logged_in)
        assert cart.row_count() == 2

        cart.delete_item(0)                         # 方法内部已等"已删除"flash
        assert cart.row_count() == 1
        assert cart.total() == PRICE_WATCH          # 剩下的是第 2 件

    @allure.story("空购物车")
    def test_empty_cart_shows_empty_tip(self, reset_data, logged_in):
        """没加购任何东西直接进购物车：显示"购物车空空如也"，行数为 0。"""
        cart = CartPage(logged_in.driver).open_cart()

        assert cart.row_count() == 0
        assert cart.is_empty(), "空购物车应显示 #cart-empty 提示"
        assert "空空如也" in cart.get_text(CartPage.CART_EMPTY)
        # 空车时"去结算"链接不渲染（模板 {% if items %} 控制）
        assert not cart.is_displayed(CartPage.CHECKOUT_LINK, timeout=2)
