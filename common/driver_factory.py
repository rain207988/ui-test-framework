"""浏览器驱动工厂：全框架唯一创建 WebDriver 的地方。

为什么必须收口到一个工厂函数：
1. 统一出口才能统一行为——窗口尺寸、无头开关、启动参数只在这一处生效，
   不会出现"10 个用例 10 种浏览器配置"的失控局面；
2. 换浏览器/换 CI 环境只改这里（或改 config.yaml），用例层零改动；
3. 杜绝散落在用例里 new WebDriver——那是无法维护的反模式。

驱动版本问题：Selenium 4.6+ 内置 Selenium Manager，
webdriver.Chrome(options=...) 会自动根据本机 Chrome 版本下载匹配的 chromedriver
并缓存到 ~/.cache/selenium，不需要再手工下载 driver、也不需要 webdriver_manager。
"""

from selenium import webdriver

from common.config_loader import config
from common.logger import logger


def _build_options(browser: str, headless: bool):
    """按浏览器类型构造启动选项。两种浏览器的公共参数保持一致，保证行为可比。"""
    if browser == "chrome":
        options = webdriver.ChromeOptions()
    elif browser == "edge":
        options = webdriver.EdgeOptions()
    else:
        raise ValueError(f"不支持的浏览器类型：{browser}（仅支持 chrome/edge）")

    # 固定窗口尺寸：分辨率不一致会导致"本地能看到元素、CI 上找不到"的环境差异
    options.add_argument(f"--window-size={config['window_width']},{config['window_height']}")
    options.add_argument("--disable-gpu")          # Windows 无头模式下 Chrome 需要禁 GPU 才稳定
    options.add_argument("--disable-infobars")     # 关闭"Chrome正受到自动化软件控制"提示条，避免遮挡
    options.add_argument("--no-first-run")         # 跳过首次运行向导
    options.add_argument("--disable-extensions")   # 不加载扩展，环境干净可复现

    if headless:
        # --headless=new 是 Chrome 109+ 的新无头模式，与真实浏览器行为更一致
        # （旧 --headless 是独立的 Headless Chrome 内核，某些渲染行为有差异）
        options.add_argument("--headless=new")
    return options


def create_driver() -> webdriver.Chrome:
    """按配置创建并返回一个就绪的 WebDriver。

    谁负责 quit：由 testcases/conftest.py 的 driver fixture（yield 之后）负责退出，
    工厂只管"生"，不管"死"——生命周期归 fixture 管理，职责分离。
    """
    browser = str(config.get("browser", "chrome")).lower()
    headless = bool(config.get("headless", False))
    logger.info("创建浏览器：browser=%s headless=%s", browser, headless)

    options = _build_options(browser, headless)

    if browser == "chrome":
        # 不传 Service/驱动路径：Selenium Manager 自动匹配本机 Chrome 版本下载驱动
        driver = webdriver.Chrome(options=options)
    else:
        driver = webdriver.Edge(options=options)

    # 显式声明隐式等待为 0：本框架的等待策略 100% 依赖显式等待（WebDriverWait），
    # 不允许隐式/显式混用——两者叠加会让"元素找不到"的失败原因变得无法分析
    # （隐式等待作用于 find_elements 等所有查找，会让轮询行为变得不可预测）。
    driver.implicitly_wait(0)
    return driver
