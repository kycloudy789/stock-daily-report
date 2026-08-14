"""新浪财经接口，作为板块数据不可用时的备用数据源。"""

from __future__ import annotations

import json
import subprocess
from typing import Any, Dict, List

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

KEY_SECTOR_KEYWORDS = [
    "银行", "证券", "保险", "酿酒", "医药", "半导体", "新能源", "光伏",
    "军工", "地产", "煤炭", "有色金属", "电力", "计算机", "通信", "汽车",
    "家电", "食品", "人工智能", "机器人",
]

GLOBAL_CODES = {
    "int_dji": ("道琼斯", "DJIA"),
    "int_nasdaq": ("纳斯达克", "IXIC"),
    "int_sp500": ("标普500", "SPX"),
    "int_hangseng": ("恒生指数", "HSI"),
    "int_nikkei": ("日经225", "N225"),
}


def _curl_bytes(url: str) -> bytes:
    result = subprocess.run(
        [
            "curl", "-sS", "--max-time", "15", "-A", UA,
            "-H", "Referer: https://finance.sina.com.cn/",
            url,
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"新浪板块请求失败：{result.stderr.decode('utf-8', errors='replace').strip()}")
    return result.stdout


def _parse_sectors() -> List[Dict[str, Any]]:
    raw = _curl_bytes("http://vip.stock.finance.sina.com.cn/q/view/newSinaHy.php")
    text = raw.decode("gbk", errors="replace")
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise RuntimeError("新浪板块接口返回格式异常")
    try:
        payload = json.loads(text[start: end + 1])
    except json.JSONDecodeError:
        payload = {}
        for pair in text[start + 1: end].split(","):
            if '":"' not in pair:
                continue
            key, value = pair.split('":"', 1)
            payload[key.strip().strip('"')] = value.rstrip('"')

    rows: List[Dict[str, Any]] = []
    for value in payload.values():
        parts = value.split(",")
        if len(parts) < 6:
            continue
        try:
            change = float(parts[5])
        except ValueError:
            continue
        rows.append({
            "名称": parts[1].strip(),
            "代码": parts[0].strip(),
            "涨跌幅": change,
            "成交额": None,
            "换手率": None,
        })
    return rows


def get_sina_sector_highlights(top_n: int = 10, bottom_n: int = 10) -> Dict[str, Any]:
    """新浪行业板块领涨与领跌。"""
    sectors = _parse_sectors()
    top = sorted(sectors, key=lambda x: float(x["涨跌幅"]), reverse=True)[:top_n]
    bottom = sorted(sectors, key=lambda x: float(x["涨跌幅"]))[:bottom_n]
    key_sectors = [
        s for s in sectors
        if any(kw in str(s.get("名称", "")) for kw in KEY_SECTOR_KEYWORDS)
    ]
    return {
        "领涨行业": top,
        "领跌行业": bottom,
        "重点行业": sorted(key_sectors, key=lambda x: float(x["涨跌幅"]), reverse=True)[:20],
    }


def get_sina_concept_highlights(top_n: int = 10) -> List[Dict[str, Any]]:
    """东方财富概念接口不可用时，用新浪领涨行业替代热门概念。"""
    sectors = _parse_sectors()
    top = sorted(sectors, key=lambda x: float(x["涨跌幅"]), reverse=True)[:top_n]
    return [{"名称": s["名称"], "涨跌幅": s["涨跌幅"]} for s in top]


def get_sina_global_quotes() -> List[Dict[str, Any]]:
    """新浪全球指数，备用源补充日经 225 等。"""
    codes = ",".join(GLOBAL_CODES)
    raw = _curl_bytes(f"https://hq.sinajs.cn/list={codes}")
    text = raw.decode("gbk", errors="replace")
    rows: List[Dict[str, Any]] = []
    for code, (name, symbol) in GLOBAL_CODES.items():
        marker = f'var hq_str_{code}="'
        start = text.find(marker)
        if start < 0:
            continue
        start += len(marker)
        end = text.find('"', start)
        fields = text[start:end].split(",")
        if len(fields) < 4 or not fields[1]:
            continue
        try:
            latest = float(fields[1])
            change = float(fields[3])
        except ValueError:
            continue
        rows.append({
            "名称": name,
            "代码": symbol,
            "最新价": latest,
            "涨跌幅": change,
        })
    if not rows:
        raise RuntimeError("新浪全球指数接口返回为空")
    return rows
