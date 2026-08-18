"""Naver 金融接口，提供韩国 KOSPI 指数备用行情。"""

from __future__ import annotations

import json
import subprocess
from typing import Any, Dict

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def _curl_bytes(url: str) -> bytes:
    result = subprocess.run(
        ["curl", "-sS", "--max-time", "15", "-A", UA, url],
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Naver 行情请求失败：{result.stderr.decode('utf-8', errors='replace').strip()}")
    return result.stdout


def _to_float(value: Any) -> float:
    return float(str(value).replace(",", "").strip())


def get_kospi_quote() -> Dict[str, Any]:
    """获取韩国 KOSPI 指数最新行情。"""
    raw = _curl_bytes("https://m.stock.naver.com/api/index/KOSPI/price")
    try:
        payload = json.loads(raw.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Naver KOSPI 接口返回格式异常：{exc}") from exc
    if not isinstance(payload, list) or not payload:
        raise RuntimeError("Naver KOSPI 接口返回空数据")
    first = payload[0]
    try:
        latest = _to_float(first.get("closePrice"))
        change = _to_float(first.get("fluctuationsRatio"))
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"Naver KOSPI 字段解析失败：{exc}") from exc
    return {
        "名称": "韩国KOSPI",
        "代码": "KS11",
        "最新价": latest,
        "涨跌幅": change,
        "昨收": round(latest / (1 + change / 100), 2),
    }
