"""商品列表页面对象：搜索、读行数据、行级加购、进详情。"""

from selenium.webdriver.common.by import By


from base.base_page import FLASH_MESSAGE, BasePage


class GoodsPage(BasePage):
    PATH = "/goods"

    # 搜索区：有 id 用 id
    SEARCH_INPUT = (By.ID, "search-input")
    SEARCH_BUTTON = (By.ID, "btn-search")
    # 表格区：行、行内子元素没有 id，用 CSS 选择器限定作用范围
    # "#goods-table tr.goods-row"：先锚定表格 id 再匹配行 class——范围收得越窄，
    # 误匹配到页面上其他表格行的可能性越小（可读性也更好）
    GOODS_ROWS = (By.CSS_SELECTOR, "#goods-table tr.goods-row")
    EMPTY_RESULT = (By.ID, "empty-result")            # 搜索无结果提示
    ROW_NAME_LINK = (By.CSS_SELECTOR, "a.goods-name")  # 行内：商品名链接
    ROW_PRICE = (By.CSS_SELECTOR, "td.goods-price")    # 行内：价格单元格
    ROW_ADD_CART = (By.CSS_SELECTOR, "button.btn-add-cart")  # 行内：加购按钮
    FLASH = FLASH_MESSAGE

    def open_goods_page(self):
        self.open(self.PATH)
        # 就绪标志：表格可见（服务端渲染，表格在即数据在）
        self.find((By.ID, "goods-table"))
        return self

    def search(self, keyword: str):
        """输入关键词并点搜索，同步等待新页面加载完成。

        同步机制踩坑实录：不能等"搜索框的值等于关键词"——输入框在点击搜索
        【之前】就已经被我们填上了这个值，旧页面就能让该条件立刻通过，
        等待形同虚设，随后读到的还是旧页面的 10 行数据（假阳性）。
        正确姿势：GET 表单提交后 URL 会变成 /goods?keyword=...，
        以"URL 出现 keyword= 查询串"作为新页面已到达的标志。
        """
        self.input(self.SEARCH_INPUT, keyword)
        self.click(self.SEARCH_BUTTON)
        self.wait.until(lambda d: "keyword=" in d.current_url)
        return self

    # ---------------- 行数据读取 ---------------- #

    def row_count(self) -> int:
        """当前列表行数（此刻快照，不等待；搜索结果同步由 search() 负责）。"""
        return len(self.find_all(self.GOODS_ROWS))

    def _row(self, index: int):
        rows = self.find_all(self.GOODS_ROWS)
        if index >= len(rows):
            raise IndexError(f"商品行索引越界：index={index}，实际行数={len(rows)}")
        return rows[index]

    def row_name(self, index: int) -> str:
        """第 index 行（0 起）的商品名。

        行内子元素查找用 row.find_element(By.CSS_SELECTOR, ...)：
        把查找范围限定在这一行内，而不是全页搜索——既快又不会错拿别行的元素。
        """
        return self._row(index).find_element(*self.ROW_NAME_LINK).text

    def row_price(self, index: int) -> str:
        return self._row(index).find_element(*self.ROW_PRICE).text

    def row_goods_id(self, index: int) -> str:
        """行上的 data-goods-id 属性（data-* 属性就是给测试/JS 用的稳定钩子）。"""
        return self._row(index).get_attribute("data-goods-id")

    # ---------------- 行级操作 ---------------- #

    def add_to_cart_by_row(self, index: int):
        """点击第 index 行的"加入购物车"，等待加购成功提示出现。

        行内按钮藏在每行自己的 <form> 里，row.find_element 限定作用域后点击。
        点击后 POST /cart/add -> redirect 回列表页并 flash"已加入购物车"，
        用 wait_flash_contains 跨过新旧页面切换的窗口期。
        """
        self._row(index).find_element(*self.ROW_ADD_CART).click()
        return self.wait_flash_contains("已加入购物车")

    def open_detail_by_row(self, index: int):
        """点击第 index 行商品名链接进入详情页，返回详情页对象。

        页面对象之间可以互相"交接"（返回下一个页面的实例），
        这是链式用例的常规写法：page = goods.open_detail_by_row(0)。
        从 pages.goods_detail_page 导入放在方法内（延迟导入），避免模块循环依赖。
        """
        self._row(index).find_element(*self.ROW_NAME_LINK).click()
        from pages.goods_detail_page import GoodsDetailPage
        detail = GoodsDetailPage(self.driver)
        detail.wait_ready()
        return detail

    def is_empty_result_shown(self) -> bool:
        """搜索无结果提示是否可见。"""
        return self.is_displayed(self.EMPTY_RESULT)
