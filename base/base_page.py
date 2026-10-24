"""BasePage：所有页面对象的父类，封装"等待 + 基础操作"两个横切关注点。

核心设计决策——为什么全部使用显式等待（WebDriverWait）：
1. UI 自动化 80% 的"随机失败"（flaky）本质是时序问题：脚本执行速度（毫秒级）
   远快于页面渲染速度（网络往返 + JS 执行，几百毫秒到几秒）。
   点完按钮立刻找元素，大概率找到的是"旧页面"或"还没渲染完的页面"。

2. 三种等待方案的对比：
   - time.sleep(3)：固定等待。等短了必挂，等长了极慢（10 个用例每个多等 3 秒=30 秒），
     且网络稍抖动照样挂——既慢又不可靠，是反模式，本框架全项目禁止；
   - 隐式等待 implicitly_wait(10)：全局生效于所有 find_*，"找不到就最多等 10 秒"。
     问题：a) 它只管"找元素"，不管"元素可点击/文本变了/消失"这类条件；
          b) 全局隐性生效，某一行的慢查找会拖慢全项目，失败时无法定位是哪一步在等；
          c) 与显式等待混用时轮询逻辑叠加，等待时间不可预测；
   - 显式等待 WebDriverWait(driver, timeout).until(condition)：针对"某一次查找"
     指定"成功条件"，条件不满足时每隔 polling 间隔（默认 0.5s）重新求值一次 lambda，
     条件满足立刻返回（不等满 timeout），超时抛 TimeoutException。
     快而不僵：元素 0.1s 就绪就 0.1s 返回，10s 没就绪才报错。

3. until 的底层机制（面试高频）：WebDriverWait.until(f) 在循环里反复调用 f(self.driver)，
   f 返回真值则立即返回该值；f 抛 NoSuchElementException/False/TimeoutException
   之外的异常则直接向外抛（不重试），到达 timeout 则抛 TimeoutException 并携带
   最后一次的异常信息。poll 默认 0.5 秒，可用 poll_frequency 调整。

定位器约定：一律 (By.ID, ...) 或 (By.CSS_SELECTOR, ...)——见 docs/04。
"""

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from common.config_loader import config
from common.logger import logger

# flash 提示条在 base.html 里定义，所有页面共享，所以定位器放在 BasePage
FLASH_MESSAGE = (By.ID, "flash")

# 导航栏元素同样在 base.html 里对所有页面可见，操作方法也统一收在 BasePage
NAV_CART = (By.ID, "nav-cart")
NAV_USER = (By.ID, "nav-user")
NAV_LOGIN = (By.ID, "nav-login")
LOGOUT_BUTTON = (By.ID, "btn-logout")


class BasePage:
    """页面对象基类：子类只定义"定位器 + 业务动作"，不写断言、不写等待细节。"""

    def __init__(self, driver):
        self.driver = driver
        self.base_url = str(config["base_url"]).rstrip("/")
        self.timeout = int(config.get("timeout", 10))
        # 每个页面对象持有一个自己的 WebDriverWait 实例，供各方法复用
        self.wait = WebDriverWait(self.driver, self.timeout)

    # ------------------------------------------------------------------ #
    # 基础操作层：子类和用例都经由这些方法与元素交互
    # ------------------------------------------------------------------ #

    def find(self, locator):
        """查找"可见"的元素（visibility_of_element_located）。

        为什么条件是"可见"而不是"存在"（presence）：
        一个 display:none 或还在隐藏父容器里的元素也能被 presence 找到，
        但对它 click()/send_keys() 会报 ElementNotInteractableException。
        "可见"= 存在 + 非隐藏 + 有尺寸，是"能交互"最接近的代理条件。
        """
        return self.wait.until(EC.visibility_of_element_located(locator))

    def find_clickable(self, locator):
        """查找"可点击"的元素（element_to_be_clickable）。

        clickable = 元素可见且 enabled。按钮还没绑定完事件/还在遮罩下时
        贸然点击会被吞掉或报错，等"可点击"能挡掉这一类 flaky。
        """
        return self.wait.until(EC.element_to_be_clickable(locator))

    def click(self, locator):
        """等待可点击后再点击。"""
        element = self.find_clickable(locator)
        element.click()
        return element

    def input(self, locator, text):
        """清空后输入文本。先 clear 是因为表单可能有默认值/浏览器自动填充残留。"""
        element = self.find(locator)
        element.clear()
        element.send_keys(str(text))
        return element

    def get_text(self, locator):
        """返回元素可见文本（.text 只返回"渲染出来的"文本，不含 display:none 的内容）。"""
        return self.find(locator).text

    def get_attribute(self, locator, attribute):
        """读取元素属性（如 data-goods-id、class、value）。"""
        return self.find(locator).get_attribute(attribute)

    def find_all(self, locator):
        """查找当前 DOM 中所有匹配的元素，返回 list（可能为空）。

        注意：这是"此刻快照"，不等待——数行数、数按钮这类读取当前列表的操作用裸
        find_elements；而"等待某元素出现"必须用上面的 find/wait 系列。
        """
        return self.driver.find_elements(*locator)

    def is_displayed(self, locator, timeout: int = 3) -> bool:
        """元素在 timeout 秒内变为可见则 True，超时返回 False 而不抛异常。

        用途：断言"空结果提示出现了"、"取消按钮消失了"这类存在性判断。
        参数化 timeout：默认用 3 秒而不是全局 10 秒——等待"应该不存在"的元素
        出现时，失败路径没必要陪跑满 10 秒，缩短超时能显著加快负向用例速度。
        """
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.visibility_of_element_located(locator)
            )
            return True
        except TimeoutException:
            return False

    def open(self, path: str):
        """直接打开 base_url + path。

        driver.get 会阻塞到页面 onload 完成，因此返回后"初始 HTML"已就绪，
        但 JS 动态渲染的内容仍需显式等待——本项目服务端渲染，onload 即可用。
        """
        url = f"{self.base_url}{path}"
        logger.info("打开页面：%s", url)
        self.driver.get(url)
        return self

    # ------------------------------------------------------------------ #
    # flash 提示条（全站共享）的读取与同步
    # ------------------------------------------------------------------ #

    def wait_flash_contains(self, expected: str, timeout: int = None) -> str:
        """等待 flash 中出现期望文本，返回 flash 的完整文本。

        为什么不简单 get_text(FLASH)：
        点击"提交"后浏览器要先 POST 再 302 渲染新页面，如果立刻读 flash，
        读到的可能是【旧页面残留的上一条提示】（Stale/陈旧数据假阳性）。
        text_to_be_present_in_element 会一直轮询直到【期望文本真的出现】，
        天然跨过了"旧页面 -> 新页面"的切换窗口，是处理 flash 的标准姿势。
        """
        timeout = timeout or self.timeout
        WebDriverWait(self.driver, timeout).until(
            EC.text_to_be_present_in_element(FLASH_MESSAGE, expected)
        )
        actual = self.find(FLASH_MESSAGE).text
        logger.info("flash 提示：%s", actual)
        return actual

    # ------------------------------------------------------------------ #
    # 导航栏操作（base.html 对所有页面共享，故收敛在基类）
    # ------------------------------------------------------------------ #

    def nav_user_text(self) -> str:
        """导航栏用户问候文本，如"你好，柠檬"——登录成功的核心标识。"""
        return self.get_text(NAV_USER)

    def is_logged_in(self) -> bool:
        """导航栏出现 #nav-user 即视为已登录（未登录时该元素根本不渲染）。"""
        return self.is_displayed(NAV_USER, timeout=3)

    def go_cart_by_nav(self):
        """点击导航栏"购物车"链接。"""
        self.click(NAV_CART)

    def logout(self):
        """点击导航栏退出按钮（POST 表单提交），跳回登录页并闪出"已退出登录"。"""
        self.click(LOGOUT_BUTTON)
        # 等待跳转后的登录页关键元素出现，保证调用方拿到的是"已切过去"的页面
        self.wait.until(EC.visibility_of_element_located(NAV_LOGIN))
        return self
