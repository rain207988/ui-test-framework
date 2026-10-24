"""YAML 数据文件加载工具（测试数据的统一入口）。

单独抽成模块而不是在各处直接 open(yaml)：
1. 统一 encoding="utf-8"——Windows 下默认编码是 GBK，中文 YAML 不显式指定
   编码会直接 UnicodeDecodeError，这是 Windows 上最常见的坑；
2. 相对路径统一相对项目根目录解析（与 config_loader 同一套规则），
   用例从任何目录启动都能找到数据文件。
"""

from pathlib import Path

import yaml

from common.config_loader import project_root


def load_yaml(relative_path: str) -> dict:
    """读取项目根目录下的 YAML 文件，返回 dict。

    :param relative_path: 相对项目根目录的路径，如 "data/users.yaml"
    """
    path = project_root() / relative_path
    if not path.exists():
        raise FileNotFoundError(f"数据文件不存在：{path}")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
