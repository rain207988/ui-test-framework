"""商品详情页面对象：读商品信息、按数量加购。"""

from selenium.webdriver.common.by import By

from base.base_page import BasePage


class GoodsDetailPage(BasePage):
    # 详情页路径按商品 id 变化，open() 由调用方传完整路径（如 /goods/1）
    PATH = "/goods"

    # 详情页关键信息都埋了 id：读名称/价格/库存不依赖 DOM 顺序，
    # 就算"价格"和"库存"两行位置对调，定位器也照样命中
    DETAIL_BOX = (By.ID, "goods-detail")
    DETAIL_NAME = (By.ID, "detail-name")
    DETAIL_PRICE = (By.ID, "detail-price")
    DETAIL_STOCK = (By.ID, "detail-stock")
    QUANTITY_INPUT = (By.ID, "buy-quantity")       # 数量输入框（type=number）
    ADD_CART_BUTTON = (By.ID, "btn-add-cart")      # 加入购物车按钮
    BACK_LINK = (By.ID, "link-back")               # 返回商品列表

    def wait_ready(self):
        """等待详情区可见（从列表页点链接进来时用于同步新页面就绪）。"""
        self.find(self.DETAIL_BOX)
        return self

    def open_detail(self, goods_id):
        """直接打开指定商品的详情页。"""
        self.open(f"{self.PATH}/{goods_id}")
        self.wait_ready()
        return self

    # ---------------- 商品信息读取 ---------------- #

    def name(self) -> str:
        return self.get_text(self.DETAIL_NAME)

    def price(self) -> str:
        """形如 '199.00' 的字符串（服务端模板 %.2f 格式化，直接做字符串断言）。"""
        return self.get_text(self.DETAIL_PRICE)

    def stock(self) -> str:
        return self.get_text(self.DETAIL_STOCK)

    # ---------------- 操作 ---------------- #

    def set_quantity(self, quantity: int):
        """设置购买数量。number 输入框同样用 clear + send_keys 清写。"""
        self.input(self.QUANTITY_INPUT, quantity)
        return self

    def add_to_cart(self):
        """点击加入购物车并等待成功提示（POST 后 redirect 回本页）。"""
        self.click(self.ADD_CART_BUTTON)
        return self.wait_flash_contains("已加入购物车")

    def back_to_goods(self):
        """点击返回链接，回到商品列表页并交接页面对象。"""
        self.click(self.BACK_LINK)
        from pages.goods_page import GoodsPage
        goods = GoodsPage(self.driver)
        goods.find((By.ID, "goods-table"))
        return goods
