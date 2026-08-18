"""腾讯行情接口，作为东方财富不可用时的备用数据源。"""

from __future__ import annotations

import json
import subprocess
from typing import Any, Dict, List, Optional

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

INDEX_CODES = {
    "sh000001": "上证指数",
    "sz399001": "深证成指",
    "sz399006": "创业板指",
    "sh000688": "科创50",
    "sh000300": "沪深300",
    "sh000905": "中证500",
    "sh000852": "中证1000",
}

GLOBAL_CODES = {
    "usDJI": "道琼斯",
    "usIXIC": "纳斯达克",
    "usINX": "标普500",
    "hkHSI": "恒生指数",
    "hkHSTECH": "恒生科技",
}

KEY_INDEX_CODES = {
    "sh000510": "中证A500",
    "sz399997": "中证白酒",
    "sz399989": "中证医疗",
    "sz399975": "证券公司",
    "sz399986": "中证银行",
    "sz399809": "保险主题",
    "sh930641": "中证中药",
    "sh930697": "家用电器",
    "sh930997": "新能源车",
    "sh931151": "光伏产业",
    "hkHSTECH": "恒生科技",
}

ETF_CODES = {
    "sh510300": "沪深300ETF",
    "sh510050": "上证50ETF",
    "sh510500": "中证500ETF",
    "sh512100": "中证1000ETF",
    "sh588000": "科创50ETF",
    "sz159915": "创业板ETF",
    "sh512760": "半导体ETF",
    "sh512880": "证券ETF",
    "sh512010": "医药ETF",
    "sh515030": "新能源车ETF",
    "sh512690": "白酒ETF",
    "sh513100": "纳指ETF",
    "sh513330": "恒生互联网ETF",
    "sh518880": "黄金ETF",
    "sh510880": "红利ETF",
}


def _to_float(value: str) -> Optional[float]:
    value = value.strip()
    if value in ("", "-", "--", "0.00"):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _curl_bytes(url: str) -> bytes:
    result = subprocess.run(
        ["curl", "-sS", "--max-time", "15", "-A", UA, url],
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"腾讯行情请求失败：{result.stderr.decode('utf-8', errors='replace').strip()}")
    return result.stdout


def _fetch_quotes(code_names: Dict[str, str]) -> List[Dict[str, Any]]:
    codes = ",".join(code_names)
    raw = _curl_bytes(f"https://qt.gtimg.cn/q={codes}")
    text = raw.decode("gbk", errors="replace")
    rows: Dict[str, Dict[str, Any]] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("v_") or "=" not in line:
            continue
        code = line[2: line.index("=")]
        start = line.find('"')
        end = line.rfind('"')
        if start < 0 or end <= start:
            continue
        fields = line[start + 1: end].split("~")
        if len(fields) < 40:
            continue
        amount = _to_float(fields[37])
        rows[code] = {
            "最新价": _to_float(fields[3]),
            "昨收": _to_float(fields[4]),
            "涨跌额": _to_float(fields[31]),
            "涨跌幅": _to_float(fields[32]),
            "成交额": amount * 10000 if amount is not None else None,
        }

    result: List[Dict[str, Any]] = []
    for code, name in code_names.items():
        row = rows.get(code)
        if not row:
            continue
        row["名称"] = name
        row["代码"] = code
        result.append(row)
    return result


def get_tencent_index_quotes() -> List[Dict[str, Any]]:
    return _fetch_quotes(INDEX_CODES)


def get_tencent_global_quotes() -> List[Dict[str, Any]]:
    return _fetch_quotes(GLOBAL_CODES)


def get_tencent_key_quotes() -> List[Dict[str, Any]]:
    """重点指数备用源：行业宽基与恒生科技。"""
    return _fetch_quotes(KEY_INDEX_CODES)


def get_tencent_etf_quotes() -> List[Dict[str, Any]]:
    return _fetch_quotes(ETF_CODES)


def get_tencent_recent_summary(code: str = "sh000001", days: int = 5) -> Dict[str, Any]:
    """通过腾讯日 K 线生成最近 N 个交易日涨跌统计，作为东方财富不可用时的备用。"""
    url = (
        "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
        f"?param={code},day,,,{days + 1},qfq"
    )
    raw = _curl_bytes(url)
    try:
        payload = json.loads(raw.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"腾讯 K 线返回格式异常：{exc}") from exc
    if payload.get("code") != 0:
        raise RuntimeError(f"腾讯 K 线接口返回异常：{payload.get('msg') or payload}")

    node = (payload.get("data") or {}).get(code) or {}
    klines = node.get("qfqday") or node.get("day") or []
    rows: List[Dict[str, Any]] = []
    prev_close: Optional[float] = None
    for line in klines:
        if not isinstance(line, list) or len(line) < 5:
            continue
        close = _to_float(str(line[2]))
        if close is None:
            continue
        if prev_close is not None:
            change = round((close - prev_close) / prev_close * 100, 2)
        else:
            change = None
        rows.append({"日期": str(line[0]), "收盘价": close, "涨跌幅": change})
        prev_close = close

    changes = [float(r["涨跌幅"]) for r in rows if r.get("涨跌幅") is not None]
    if len(changes) < 1 or len(rows) < 2:
        return {"可用": False}
    return {
        "可用": True,
        "日期": rows[-1]["日期"],
        "累计涨跌幅": round(sum(changes), 2),
        "最大单日涨幅": round(max(changes), 2),
        "最大单日跌幅": round(min(changes), 2),
        "平均涨跌幅": round(sum(changes) / len(changes), 2),
        "明细": rows,
    }
