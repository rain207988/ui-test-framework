"""pytest 全局夹具（fixture）与钩子：用例层的基础设施都在这里。

本文件承担四件事：
1. 会话级 autouse 夹具：确认被测服务就绪 + 重置种子数据（保证数据确定性）；
2. driver 夹具：function 级创建/退出浏览器（每个用例一个全新会话，互不污染）；
3. reset_data 夹具：需要"干净世界"的用例（购物车/订单）在用例前再重置一次；
4. pytest_runtest_makereport 钩子：call 阶段失败自动截图并贴进 Allure 报告。
"""

import re
import time

import allure
import pytest
import requests
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

from common.config_loader import config, project_root
from common.data_loader import load_yaml
from common.driver_factory import create_driver
from common.logger import logger
from pages.login_page import LoginPage

SCREENSHOT_DIR = project_root() / "screenshots"


# --------------------------------------------------------------------------- #
# HTTP 工具：与被测系统交互只走 requests（reset 种子数据），不走浏览器
# --------------------------------------------------------------------------- #

def _http_session() -> requests.Session:
    """带连接重试的 requests 会话。

    为什么不用 time.sleep 轮询等服务启动：requests 的 Retry 机制
    （urllib3 提供）在连接被拒时会按 backoff_factor 指数退避后自动重试，
    "等服务就绪"这件事交给 HTTP 客户端内部机制处理，
    项目代码里不出现任何 sleep。
    """
    session = requests.Session()
    retry = Retry(
        total=10,               # 最多重试 10 次（服务没起时给启动留时间）
        connect=10,
        backoff_factor=0.5,     # 退避间隔 0.5s, 1s, 2s, 4s ...
        # POST 也要重试：/api/test/reset 幂等（重置成固定种子态），重试无副作用
        allowed_methods=None,
        status_forcelist=[502, 503, 504],   # 网关类错误也重试
    )
    session.mount("http://", HTTPAdapter(max_retries=retry))
    return session


def reset_mall_data() -> None:
    """调用被测系统测试后门，把数据库还原成种子状态。

    为什么被测系统要提供 /api/test/reset：UI 用例会改数据（加购/下单/改库存），
    想让"第 1 次跑"和"第 10 次跑"结果完全一致，最可靠的办法不是用例自己
    想方设法清理（越清越乱），而是每次跑之前把世界一键还原。
    真实项目里这个接口等价于测试环境的"数据初始化流水线"。
    """
    base = config["base_url"]
    resp = _http_session().post(
        f"{base}/api/test/reset",
        headers={"X-Test-Key": config["test_key"]},
        timeout=15,
    )
    resp.raise_for_status()
    logger.info("已重置 demo-mall 种子数据（%s）", base)


# --------------------------------------------------------------------------- #
# 会话级：服务就绪 + 数据重置
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="session", autouse=True)
def _mall_ready_and_reset():
    """整个测试会话开始前：确认被测服务可用并重置一次种子数据。

    autouse=True：所有用例都隐式依赖它，用例文件里看不到引用，但顺序有保证——
    pytest 会先执行会话级夹具再执行用例，reset 一定发生在第一条用例之前。
    """
    # 先探活：GET 一个公开页面，连不上时 Retry 会退避重试，服务没起就绪会在此报错
    probe = _http_session().get(f"{config['base_url']}/goods", timeout=15)
    probe.raise_for_status()
    reset_mall_data()
    yield


# --------------------------------------------------------------------------- #
# 浏览器与登录
# --------------------------------------------------------------------------- #

@pytest.fixture()
def driver():
    """function 级浏览器夹具：每个用例独享一个全新浏览器。

    为什么 function 级而不是 session 级：
    1. 隔离——session/cookie/购物车状态不跨用例残留，一条用例的失败不会连环污染
       后面的用例（排查"一条挂全串挂"比多花几秒启动浏览器贵得多）；
    2. 失败截图/退出逻辑简单可控（yield 后必然执行 quit）。
    """
    d = create_driver()
    logger.info("浏览器会话已创建")
    yield d
    d.quit()
    logger.info("浏览器会话已退出")


@pytest.fixture()
def logged_in(driver):
    """已用 lemon 登录成功的浏览器（返回 LoginPage 上下文，可继续导航）。

    把"打开登录页 -> 填表 -> 提交 -> 等跳转完成"收敛成一个夹具，
    避免十几条用例重复同一段样板代码；需要其他账号的用例自己走 LoginPage。
    """
    users = load_yaml(config["users_file"])
    account = users["valid_accounts"][0]           # lemon
    page = LoginPage(driver)
    page.open_login_page()
    page.login_and_expect_success(account["username"], account["password"])
    return page


@pytest.fixture()
def reset_data():
    """用例级数据还原：购物车/订单类用例对数据有强假设（空车、无历史订单），
    在用例开始前再重置一次，彻底消除"同会话内前面用例留下的脏数据"。

    注意与 _mall_ready_and_reset 的分工：会话级 reset 保证"跨运行可重复"，
    本夹具保证"会话内用例之间互不影响"。
    """
    reset_mall_data()
    yield


# --------------------------------------------------------------------------- #
# 失败自动截图钩子
# --------------------------------------------------------------------------- #

@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    """用例 call 阶段失败时：保存截图到 screenshots/ 并 attach 进 Allure。

    机制说明（hookwrapper）：
    - hookwrapper=True 让本函数"包裹"原始 hook：yield 拿到的是内部 hook 的
      结果包装（TestReport 在 yield 后通过 get_result() 取出）；
    - call 阶段 = 测试函数体执行阶段（setup 是夹具阶段，teardown 是清理阶段）；
    - 截图必须在"浏览器还活着"的时候做——teardown 里 driver 已 quit，
      所以要趁 report 一产生、driver fixture 还没退出时立刻拍；
    - item.funcargs 里能拿到该用例实际用到的所有夹具实例，driver 不在
      （比如纯 requests 用例）就跳过，不能因为截图把框架自己搞挂。
    """
    outcome = yield
    report = outcome.get_result()

    if report.when != "call" or not report.failed:
        return

    web_driver = item.funcargs.get("driver") if hasattr(item, "funcargs") else None
    if web_driver is None:
        return

    timestamp = time.strftime("%Y%m%d-%H%M%S")
    # nodeid 形如 testcases/test_login.py::TestLogin::test_xxx，压成安全文件名
    safe_name = re.sub(r'[\\/:*?"<>|\s]+', "_", item.nodeid.replace("::", "__"))
    screenshot_path = SCREENSHOT_DIR / f"{timestamp}__{safe_name}.png"

    try:
        SCREENSHOT_DIR.mkdir(exist_ok=True)
        web_driver.save_screenshot(str(screenshot_path))
        # attach 进 Allure：报告里点开失败用例直接看到现场画面
        allure.attach(
            web_driver.get_screenshot_as_png(),
            name=f"失败截图-{item.name}",
            attachment_type=allure.attachment_type.PNG,
        )
        logger.error("用例失败，已保存截图：%s", screenshot_path)
    except Exception as exc:  # noqa: BLE001 截图失败绝不能反过来影响测试流程
        logger.error("生成失败截图时出错：%s", exc)
