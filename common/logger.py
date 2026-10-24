"""日志模块：按天滚动的文件日志 + 控制台输出。

为什么不用 print：
1. print 没有时间戳、没有级别，跑完 50 条用例后无法回答"哪一步慢了、失败前发生了什么"；
2. 文件日志是"事后排障"的唯一依据——UI 用例失败时浏览器已经关闭，
   日志 + 截图（见 testcases/conftest.py）是仅存的两份现场。

实现机制：
- logging 是单例注册表：同名 logger 重复调用 get_logger 会拿到同一个对象，
  所以这里加了"已初始化就不重复加 handler"的守卫，否则 pytest 收集多个文件时
  会反复 add handler，导致同一条日志在控制台打印 N 遍；
- TimedRotatingFileHandler(when="midnight")：每天零点切新文件，
  历史日志保留 backupCount 天后自动删除，防止日志目录无限膨胀。
"""

import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from common.config_loader import project_root

LOG_DIR = project_root() / "logs"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_initialized = False


def _init_logger() -> logging.Logger:
    global _initialized
    logger = logging.getLogger("ui_test")
    if _initialized:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    # 文件 handler：按天滚动，保留 14 天
    LOG_DIR.mkdir(exist_ok=True)
    file_handler = TimedRotatingFileHandler(
        filename=LOG_DIR / "ui_test.log",
        when="midnight",
        backupCount=14,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # 控制台 handler：只输出 INFO 及以上，跑批时肉眼可跟
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 阻断日志向 root logger 冒泡，避免 pytest 捕获后重复输出
    logger.propagate = False
    _initialized = True
    return logger


logger = _init_logger()
