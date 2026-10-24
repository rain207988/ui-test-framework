"""商品模块用例：列表、搜索、详情、加购。

数据确定性说明：断言依赖种子数据（demo-mall/seed.py）——
商品 10 件（id 1-10）；第 1 件"无线蓝牙耳机"199.00 元库存 50。
会话级 reset 已保证起点是种子态；本文件里的加购只往购物车加东西、
不断言购物车状态，因此不需要用例级 reset。
"""

import allure
import pytest

from pages.goods_detail_page import GoodsDetailPage
from pages.goods_page import GoodsPage


@allure.feature("商品模块")
class TestGoodsList:
    """商品列表与搜索。"""

    @allure.story("商品列表")
    @pytest.mark.smoke
    def test_default_list_has_10_rows(self, logged_in):
        """默认列表展示全部 10 件在售商品。"""
        logged_in.open("/goods")
        goods = GoodsPage(logged_in.driver)
        goods.find(GoodsPage.GOODS_ROWS)
        assert goods.row_count() == 10

    @allure.story("商品搜索")
    def test_search_hit_one_row(self, logged_in):
        """搜索"耳机"：只命中第 1 件"无线蓝牙耳机"（LIKE 模糊匹配）。"""
        goods = GoodsPage(logged_in.driver).open_goods_page()
        goods.search("耳机")

        assert goods.row_count() == 1
        assert goods.row_name(0) == "无线蓝牙耳机"

    @allure.story("商品搜索")
    def test_search_no_result_shows_empty_tip(self, logged_in):
        """搜索不存在的关键词：出现 #empty-result 提示"没有找到相关商品"。"""
        goods = GoodsPage(logged_in.driver).open_goods_page()
        goods.search("绝不存在的商品XYZ")

        assert goods.is_empty_result_shown(), "无结果时应显示 #empty-result 提示"
        assert "没有找到相关商品" in goods.get_text(GoodsPage.EMPTY_RESULT)

    @allure.story("商品详情")
    def test_open_detail_from_list(self, logged_in):
        """从列表点商品名进详情：名称/价格/库存与种子数据一致。"""
        goods = GoodsPage(logged_in.driver).open_goods_page()
        goods.search("耳机")
        detail = goods.open_detail_by_row(0)

        assert "/goods/1" in logged_in.driver.current_url
        assert detail.name() == "无线蓝牙耳机"
        assert detail.price() == "199.00"
        assert detail.stock() == "50"


@allure.feature("商品模块")
class TestAddToCart:
    """加购入口验证（列表页入口 + 详情页入口）。"""

    @allure.story("加入购物车")
    def test_add_to_cart_from_detail(self, logged_in):
        """详情页购买入口：设置数量后加购，提示"已加入购物车"。"""
        detail = GoodsDetailPage(logged_in.driver).open_detail(1)
        detail.set_quantity(2).add_to_cart()

        flash_text = detail.wait_flash_contains("已加入购物车")
        assert "已加入购物车" in flash_text

    @allure.story("加入购物车")
    def test_add_to_cart_from_list_row(self, logged_in):
        """列表页快捷入口：直接点第 1 行"加入购物车"，提示"已加入购物车"。"""
        goods = GoodsPage(logged_in.driver).open_goods_page()
        flash_text = goods.add_to_cart_by_row(0)

        assert "已加入购物车" in flash_text
