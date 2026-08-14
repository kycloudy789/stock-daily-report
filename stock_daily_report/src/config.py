"""读取配置文件与环境变量。"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def load_config(path: Path | None = None) -> Dict[str, Any]:
    """加载配置：环境变量优先级高于配置文件。"""
    config_path = path or Path(PROJECT_ROOT) / "config.json"
    cfg: Dict[str, Any] = {
        "时区": "Asia/Shanghai",
        "输出目录": "docs",
        "报告文件名": "index.html",
        "Markdown文件名": "report.md",
        "发布方式": "github",
        "GitHub仓库": "",
        "GitHub页面基础地址": "",
        "PushPlus Token": "",
        "PushPlus 群组编码": "",
    }
    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as f:
            cfg.update(json.load(f))

    env_map = {
        "PushPlus Token": "PUSHPLUS_TOKEN",
        "PushPlus 群组编码": "PUSHPLUS_TOPIC",
        "GitHub仓库": "GITHUB_REPO",
        "GitHub页面基础地址": "PAGE_BASE_URL",
    }
    for key, env_name in env_map.items():
        value = _env(env_name)
        if value:
            cfg[key] = value
    return cfg


def require_pushplus_token(cfg: Dict[str, Any]) -> str:
    token = str(cfg.get("PushPlus Token", "")).strip()
    if not token:
        raise RuntimeError("缺少 PushPlus Token，请在 config.json 或环境变量 PUSHPLUS_TOKEN 中配置。")
    return token
