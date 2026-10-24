"""登录页面对象。

PO 纪律：本类只有【定位器】和【页面动作】，不含任何 assert——
断言是用例层的事，PO 只负责"怎么操作页面"；
这样页面结构变了只改这里，断言逻辑变了只改用例，两边互不牵连。
"""

from selenium.webdriver.common.by import By

from base.base_page import FLASH_MESSAGE, NAV_LOGIN, BasePage


class LoginPage(BasePage):
    PATH = "/login"

    # ------------------------------------------------------------------ #
    # 定位器：一律 (By.ID,) 或 (By.CSS_SELECTOR,)
    # 为什么 By.ID 优先：id 在 HTML 规范里就是唯一的，被测系统专门为自动化埋了
    # 稳定 id，用 id 定位既快（浏览器原生 getElementById）又不怕布局调整；
    # 没有 id 的（如行内子元素）才退而求其次用 CSS 选择器。
    # 不用 XPath：绝对路径脆（改一个 div 层级就挂）、文本定位慢且依赖文案，
    # //div[2]/form/input[1] 这种表达式两周后没人看得懂。
    # ------------------------------------------------------------------ #
    USERNAME_INPUT = (By.ID, "username")          # 用户名输入框
    PASSWORD_INPUT = (By.ID, "password")          # 密码输入框
    LOGIN_BUTTON = (By.ID, "btn-login")           # 登录提交按钮
    FLASH = FLASH_MESSAGE                          # 提示信息（继承自 base.html）
    NAV_LOGIN_LINK = NAV_LOGIN                     # 未登录状态导航栏的"登录"链接

    def open_login_page(self):
        """打开登录页并等待表单可交互（等待输入框可见即认为页面就绪）。"""
        self.open(self.PATH)
        self.find(self.USERNAME_INPUT)
        return self

    def login(self, username: str, password: str):
        """填表并提交登录。

        提交后浏览器 POST /login -> 302 重定向，本方法【不等待】结果——
        等待谁的页面就绪是调用方/下一个页面对象的职责（页面对象之间不做隐式耦合）。
        用例里通常紧接着调用 wait_flash_contains / 下一个 Page 的 find 来同步。
        """
        self.input(self.USERNAME_INPUT, username)
        self.input(self.PASSWORD_INPUT, password)
        self.click(self.LOGIN_BUTTON)

    def login_and_expect_success(self, username: str, password: str):
        """登录并等待跳转到商品页完成（以"导航栏用户问候"出现为就绪标志）。

        单独提供这个复合动作是因为：登录成功是 302 跳转，用例几乎每次都要
        "登录 + 等跳转"两步，把同步点收敛到 PO 里，用例层就不用重复写等待。

        等待写法的讲究：用 find_elements 轮询而不是 is_displayed——
        until 的条件函数会被反复执行，is_displayed 内部自带 3 秒等待，
        套在轮询里会让"每次轮询"都阻塞 3 秒；find_elements 是立即返回的
        当前快照（空列表为假值 -> 继续轮询），轮询节奏由 WebDriverWait 控制。
        """
        self.login(username, password)
        self.wait.until(lambda d: d.find_elements(By.ID, "nav-user"))
        return self

    def flash_text_after_submit(self, expected: str) -> str:
        """登录失败后等待 flash 出现期望文案并返回完整文本（登录失败不跳转，
        flash 在当前页渲染）。"""
        return self.wait_flash_contains(expected)
