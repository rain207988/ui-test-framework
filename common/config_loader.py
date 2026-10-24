"""配置加载模块：全框架唯一的配置读取入口。

设计要点：
1. 模块级单例 `config`：其他模块 `from common.config_loader import config` 即可，
   整个进程只解析一次 YAML，避免每个 Page/用例都重复读文件；
2. 支持环境变量覆盖 base_url / headless：
   这是"配置分层"的常见做法——文件里放默认值（5000），CI/临时验证用环境变量
   （UI_TEST_BASE_URL=http://127.0.0.1:5001）覆盖，做到不改代码不改文件就能换环境；
3. 所有路径都相对"项目根目录"解析：用 `Path(__file__).resolve()` 反推根目录，
   而不是 os.getcwd()——因为 pytest 可能从任意目录启动，
   依赖工作目录的路径在别人机器上必挂，这是新手最常见的坑之一。
"""

import os
from pathlib import Path

import yaml

# 项目根目录：common/config_loader.py 在 <root>/common/ 下，parent.parent 即根
PROJECT_ROOT = Path(__file__).resolve().parent.parent

CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"


def _load_yaml_file(path: Path) -> dict:
    """读取单个 YAML 文件并返回 dict。文件缺失时直接报错——配置缺失应该"响亮地失败"，
    而不是带着空配置继续跑，最后在几十个用例后面出现莫名其妙的失败。"""
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在：{path}")
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


def load_config() -> dict:
    """读取 config.yaml 并应用环境变量覆盖，返回最终生效的配置 dict。"""
    cfg = _load_yaml_file(CONFIG_PATH)

    # 环境变量优先：只要设置了 UI_TEST_BASE_URL 就覆盖文件里的 base_url
    env_base_url = os.environ.get("UI_TEST_BASE_URL")
    if env_base_url:
        # rstrip("/") 统一去掉末尾斜杠，保证 BasePage.open 拼接时不会出现双斜杠
        cfg["base_url"] = env_base_url.rstrip("/")

    # headless 同样允许环境变量覆盖（CI 里不想改文件时用）
    env_headless = os.environ.get("UI_TEST_HEADLESS")
    if env_headless:
        cfg["headless"] = env_headless.strip().lower() in ("1", "true", "yes")

    return cfg


# 模块级单例：全框架共用这一份配置
config = load_config()


def project_root() -> Path:
    """返回项目根目录 Path，供 conftest 存截图、logger 存日志等使用。"""
    return PROJECT_ROOT
