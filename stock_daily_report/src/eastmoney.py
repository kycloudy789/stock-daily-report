"""东方财富公开行情接口采集。

数据来源为东方财富公开 HTTP 接口，未使用任何需要登录或授权的服务。
所有接口均为只读查询，接口返回字段含义：
  f2 最新价，f3 涨跌幅，f4 涨跌额，f6 成交额，f8 换手率
"""

from __future__ import annotations

import logging
import json
import subprocess
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import quote
from zoneinfo import ZoneInfo

import requests

from .sina import get_sina_sector_highlights
from .sina import get_sina_concept_highlights, get_sina_global_quotes
from .naver import get_kospi_quote
from .tencent import (
    get_tencent_etf_quotes,
    get_tencent_global_quotes,
    get_tencent_index_quotes,
    get_tencent_key_quotes,
    get_tencent_recent_summary,
)

LOGGER = logging.getLogger(__name__)

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

INDEX_SECIDS = [
    ("上证指数", "1.000001"),
    ("深证成指", "0.399001"),
    ("创业板指", "0.399006"),
    ("科创50", "1.000688"),
    ("沪深300", "1.000300"),
    ("中证500", "1.000905"),
    ("中证1000", "1.000852"),
    ("北证50", "0.899050"),
]

KEY_INDEX_SECIDS = [
    ("中证A500", "1.000510"),
    ("中证白酒", "0.399997"),
    ("中证医疗", "0.399989"),
    ("证券公司", "0.399975"),
    ("中证银行", "0.399986"),
    ("保险主题", "0.399809"),
    ("中证中药", "2.930641"),
    ("家用电器", "2.930697"),
    ("新能源车", "2.930997"),
    ("光伏产业", "2.931151"),
    ("电网设备", "90.BK0457"),
    ("恒生科技", "124.HSTECH"),
    ("恒生互联网", "124.HSIII"),
    ("恒生港股通新经济", "124.HSSCNE"),
]

GLOBAL_SECIDS = [
    ("道琼斯", "100.DJIA"),
    ("纳斯达克100", "100.NDX"),
    ("标普500", "100.SPX"),
    ("韩国KOSPI", "100.KS11"),
    ("日经225", "100.N225"),
    ("恒生指数", "100.HSI"),
    ("台湾加权", "100.TWII"),
    ("英国富时100", "100.FTSE"),
    ("德国DAX", "100.GDAXI"),
    ("越南胡志明", "100.VNINDEX"),
]

ETF_SECIDS = [
    ("沪深300ETF", "1.510300"),
    ("上证50ETF", "1.510050"),
    ("中证500ETF", "1.510500"),
    ("中证1000ETF", "1.512100"),
    ("科创50ETF", "1.588000"),
    ("创业板ETF", "0.159915"),
    ("半导体ETF", "1.512760"),
    ("证券ETF", "1.512880"),
    ("医药ETF", "1.512010"),
    ("新能源车ETF", "1.515030"),
    ("白酒ETF", "1.512690"),
    ("纳指ETF", "1.513100"),
    ("恒生互联网ETF", "1.513330"),
    ("黄金ETF", "1.518880"),
    ("红利ETF", "1.510880"),
]

KEY_SECTOR_KEYWORDS = [
    "银行", "证券", "保险", "白酒", "医药", "半导体", "新能源", "光伏",
    "军工", "地产", "煤炭", "有色金属", "电力", "计算机", "通信", "汽车",
    "家电", "食品饮料", "人工智能", "机器人",
]


def _to_float(value: Any) -> Optional[float]:
    if value in (None, "-", "--"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": UA,
        "Referer": "https://quote.eastmoney.com/",
        "Accept": "application/json, text/plain, */*",
    })
    return session


def _fetch_with_curl(url: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """使用 curl.exe 请求接口，兼容当前机器可直连、Python 被拒绝的情况。"""
    query = "&".join(f"{quote(str(k))}={quote(str(v))}" for k, v in params.items())
    full_url = f"{url}?{query}"
    result = subprocess.run(
        ["curl", "-sS", "--max-time", "20", "-A", UA, full_url],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(f"curl 请求失败：{(result.stderr or result.stdout).strip()}")
    data = json.loads(result.stdout)
    if data.get("rc") != 0 or data.get("data") is None:
        raise RuntimeError(f"接口返回异常：{data}")
    return data


def fetch_json(url: str, params: Dict[str, Any], retries: int = 3) -> Dict[str, Any]:
    """请求东方财富 JSON 接口，curl 与 requests 互为备份并自动重试。"""
    last_error: Optional[Exception] = None
    for attempt in range(1, retries + 1):
        try:
            return _fetch_with_curl(url, params)
        except Exception as exc:
            last_error = exc
            LOGGER.warning("第 %s 次 curl 请求 %s 失败：%s", attempt, url, exc)
        try:
            with _session() as session:
                resp = session.get(url, params=params, timeout=15)
                resp.raise_for_status()
                data = resp.json()
            if data.get("rc") != 0 or data.get("data") is None:
                raise RuntimeError(f"接口返回异常：{data.get('rt') or data}")
            return data
        except Exception as exc:  # 网络抖动或接口限流时重试
            last_error = exc
            LOGGER.warning("第 %s 次 requests 请求 %s 失败：%s", attempt, url, exc)
            if attempt < retries:
                time.sleep(1.5 * attempt)
    raise RuntimeError(f"请求东方财富接口失败：{last_error}")


def get_quotes(secid_pairs: List[tuple[str, str]]) -> List[Dict[str, Any]]:
    """批量获取行情。"""
    if not secid_pairs:
        return []
    secids = ",".join(secid for _, secid in secid_pairs)
    data = fetch_json(
        "https://push2.eastmoney.com/api/qt/ulist.np/get",
        {
            "fltt": 2,
            "invt": 2,
            "fields": "f12,f14,f2,f3,f4,f6,f8",
            "secids": secids,
        },
    )
    diff = (data.get("data") or {}).get("diff") or []
    name_map = {secid: name for name, secid in secid_pairs}
    result: List[Dict[str, Any]] = []
    for item in diff:
        if not isinstance(item, dict):
            continue
        code = str(item.get("f12") or "")
        result.append({
            "名称": item.get("f14") or name_map.get(code, code),
            "代码": code,
            "最新价": _to_float(item.get("f2")),
            "涨跌幅": _to_float(item.get("f3")),
            "涨跌额": _to_float(item.get("f4")),
            "成交额": _to_float(item.get("f6")),
            "换手率": _to_float(item.get("f8")),
        })
    return result


def get_index_quotes() -> List[Dict[str, Any]]:
    """A股主要指数实时行情。"""
    return get_quotes(INDEX_SECIDS)


def get_key_index_quotes() -> List[Dict[str, Any]]:
    """重点观察指数：行业、宽基与港股科技相关指数。"""
    return get_quotes(KEY_INDEX_SECIDS)


def get_global_quotes() -> List[Dict[str, Any]]:
    """全球主要股指实时行情。"""
    return get_quotes(GLOBAL_SECIDS)


def get_etf_quotes() -> List[Dict[str, Any]]:
    """常见宽基与行业 ETF 行情，作为基金参考。"""
    return get_quotes(ETF_SECIDS)


def get_sector_list(fs: str = "m:90+t:2+f:!50", page_size: int = 2000) -> List[Dict[str, Any]]:
    """获取板块列表，默认行业板块。"""
    data = fetch_json(
        "https://push2.eastmoney.com/api/qt/clist/get",
        {
            "pn": 1,
            "pz": page_size,
            "po": 1,
            "np": 1,
            "fltt": 2,
            "invt": 2,
            "fid": "f3",
            "fs": fs,
            "fields": "f12,f14,f2,f3,f4,f6,f8",
        },
    )
    diff = (data.get("data") or {}).get("diff") or []
    result: List[Dict[str, Any]] = []
    for item in diff:
        if not isinstance(item, dict):
            continue
        result.append({
            "名称": item.get("f14") or item.get("f12") or "",
            "代码": item.get("f12") or "",
            "最新价": _to_float(item.get("f2")),
            "涨跌幅": _to_float(item.get("f3")),
            "涨跌额": _to_float(item.get("f4")),
            "成交额": _to_float(item.get("f6")),
            "换手率": _to_float(item.get("f8")),
        })
    return result


def _sort_by_change(items: List[Dict[str, Any]], reverse: bool = True) -> List[Dict[str, Any]]:
    return sorted(
        [item for item in items if item.get("涨跌幅") is not None],
        key=lambda item: float(item["涨跌幅"]),
        reverse=reverse,
    )


def get_sector_highlights(top_n: int = 10, bottom_n: int = 10) -> Dict[str, Any]:
    """行业板块领涨与领跌。"""
    sectors = get_sector_list()
    top = _sort_by_change(sectors, reverse=True)[:top_n]
    bottom = _sort_by_change(sectors, reverse=False)[:bottom_n]
    key_sectors = [s for s in sectors if any(kw in str(s.get("名称", "")) for kw in KEY_SECTOR_KEYWORDS)]
    return {
        "领涨行业": top,
        "领跌行业": bottom,
        "重点行业": _sort_by_change(key_sectors, reverse=True)[:20],
    }


def get_hot_concepts(top_n: int = 10) -> List[Dict[str, Any]]:
    """热门概念板块。"""
    concepts = get_sector_list(fs="m:90+t:3+f:!50", page_size=500)
    return _sort_by_change(concepts, reverse=True)[:top_n]


def get_kline(secid: str, limit: int = 10) -> List[Dict[str, Any]]:
    """获取日 K 线，返回日期、收盘价与涨跌幅。"""
    data = fetch_json(
        "https://push2his.eastmoney.com/api/qt/stock/kline/get",
        {
            "secid": secid,
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58",
            "klt": 101,
            "fqt": 1,
            "end": "20500101",
            "lmt": limit,
        },
    )
    klines = (data.get("data") or {}).get("klines") or []
    result: List[Dict[str, Any]] = []
    for line in klines:
        parts = str(line).split(",")
        if len(parts) < 8:
            continue
        result.append({
            "日期": parts[0],
            "收盘价": _to_float(parts[2]),
            "涨跌幅": _to_float(parts[7]),
        })
    return result


def get_recent_summary(secid: str, days: int = 5) -> Dict[str, Any]:
    """最近 N 个交易日的涨跌统计。"""
    klines = get_kline(secid, limit=days + 1)
    if len(klines) < 2:
        return {"可用": False}
    changes = [float(k["涨跌幅"]) for k in klines[1:] if k.get("涨跌幅") is not None]
    if not changes:
        return {"可用": False}
    return {
        "可用": True,
        "日期": klines[-1]["日期"],
        "累计涨跌幅": round(sum(changes), 2),
        "最大单日涨幅": round(max(changes), 2),
        "最大单日跌幅": round(min(changes), 2),
        "平均涨跌幅": round(sum(changes) / len(changes), 2),
        "明细": klines,
    }


def get_market_summary() -> Dict[str, Any]:
    """两市情绪汇总：成交额、涨跌家数与涨跌停数量。"""
    today = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y%m%d")
    data = fetch_json(
        "https://push2ex.eastmoney.com/getTopicZDFenBu",
        {
            "ut": "7eea3edcaed734bea9cbfc24409ed989",
            "dpt": "wz.ztzt",
            "Pageindex": 0,
            "pagesize": 1,
            "sort": "fbt:asc",
            "date": today,
        },
    )
    fenbu = (data.get("data") or {}).get("fenbu") or []
    up = down = flat = limit_up = limit_down = 0
    amount = None
    for item in fenbu:
        if not isinstance(item, dict):
            continue
        for key, count in item.items():
            try:
                bucket = int(key)
                count = int(count)
            except (TypeError, ValueError):
                continue
            if bucket > 0:
                up += count
                if bucket >= 10:
                    limit_up += count
            elif bucket < 0:
                down += count
                if bucket <= -10:
                    limit_down += count
            else:
                flat += count
    if up or down or flat:
        amount = sum(
            row.get("成交额") or 0
            for row in get_index_quotes()
            if row.get("名称") in ("上证指数", "深证成指")
        ) or None
    return {
        "两市成交额": amount,
        "上涨家数": up,
        "下跌家数": down,
        "平盘家数": flat,
        "涨停家数": limit_up,
        "跌停家数": limit_down,
    }


def _summary_from_indexes() -> Dict[str, Any]:
    """腾讯备用源：用沪深两指数成交额估算两市成交额，涨跌家数暂缺。"""
    rows = get_tencent_index_quotes()
    amount = sum(
        row.get("成交额") or 0
        for row in rows
        if row.get("名称") in ("上证指数", "深证成指")
    ) or None
    return {
        "两市成交额": amount,
        "上涨家数": 0,
        "下跌家数": 0,
        "平盘家数": 0,
        "涨停家数": 0,
        "跌停家数": 0,
    }


def get_key_index_quotes_with_hang_seng() -> List[Dict[str, Any]]:
    """东财重点指数，并补腾讯恒生科技（东财接口偶发不返回该指数）。"""
    rows = get_quotes(KEY_INDEX_SECIDS)
    # 东财返回的名称带“指数”后缀，统一成简报展示名，避免重复补齐。
    expected_names = {secid.split(".")[-1]: name for name, secid in KEY_INDEX_SECIDS}
    for row in rows:
        code = str(row.get("代码") or "")
        if code in expected_names:
            row["名称"] = expected_names[code]
    # 东方财富批量接口偶发丢弃 930 系指数，逐个补齐缺失项。
    got = {str(row.get("名称", "")) for row in rows}
    missing = [name for name, secid in KEY_INDEX_SECIDS if name not in got]
    for name in missing:
        try:
            secid = next(secid for item_name, secid in KEY_INDEX_SECIDS if item_name == name)
            rows.extend(get_quotes([(name, secid)]))
        except Exception as exc:
            LOGGER.warning("补齐重点指数 %s 失败：%s", name, exc)
    names = {str(row.get("名称", "")) for row in rows}
    if "恒生科技" not in names:
        try:
            hstech_rows = get_tencent_key_quotes()
            rows.extend(row for row in hstech_rows if str(row.get("名称", "")) == "恒生科技")
        except Exception as exc:
            LOGGER.warning("腾讯恒生科技备用失败：%s", exc)
    order = [name for name, _ in KEY_INDEX_SECIDS]
    rows.sort(key=lambda row: order.index(str(row.get("名称"))) if str(row.get("名称")) in order else 99)
    return rows


def _fallback_global_quotes() -> List[Dict[str, Any]]:
    """合并腾讯、新浪、Naver 备用源，尽量补全球主要指数。"""
    rows: Dict[str, Dict[str, Any]] = {}
    try:
        for row in get_tencent_global_quotes():
            rows.setdefault(str(row.get("名称", "")), row)
    except Exception as exc:
        LOGGER.warning("腾讯全球指数备用失败：%s", exc)
    try:
        for row in get_sina_global_quotes():
            rows.setdefault(str(row.get("名称", "")), row)
    except Exception as exc:
        LOGGER.warning("新浪全球指数备用失败：%s", exc)
    try:
        kospi = get_kospi_quote()
        rows.setdefault(str(kospi.get("名称", "")), kospi)
    except Exception as exc:
        LOGGER.warning("Naver 韩股备用失败：%s", exc)
    if not rows:
        raise RuntimeError("所有全球行情备用源均失败")
    return list(rows.values())


def build_market_snapshot() -> Dict[str, Any]:
    """采集全部市场数据；东方财富失败时自动切换到腾讯、新浪、Naver 备用源。"""
    fallback: Dict[str, Any] = {
        "指数": (get_tencent_index_quotes, "腾讯"),
        "全球": (_fallback_global_quotes, "腾讯/新浪/Naver"),
        "ETF": (get_tencent_etf_quotes, "腾讯"),
        "板块": (get_sina_sector_highlights, "新浪"),
        "热门概念": (get_sina_concept_highlights, "新浪行业替代"),
        "近期": (lambda: get_tencent_recent_summary("sh000001", days=6), "腾讯"),
        "汇总": (_summary_from_indexes, "腾讯"),
        "重点指数": (get_tencent_key_quotes, "腾讯"),
    }
    providers = [
        ("指数", "东方财富", get_index_quotes),
        ("全球", "东方财富", get_global_quotes),
        ("ETF", "东方财富", get_etf_quotes),
        ("板块", "东方财富", get_sector_highlights),
        ("热门概念", "东方财富", get_hot_concepts),
        ("近期", "东方财富", lambda: get_recent_summary("1.000001", days=6)),
        ("汇总", "东方财富", get_market_summary),
        ("重点指数", "东方财富", get_key_index_quotes_with_hang_seng),
    ]
    snapshot: Dict[str, Any] = {}
    sources: Dict[str, str] = {}
    for key, primary_source, fetcher in providers:
        try:
            snapshot[key] = fetcher()
            sources[key] = primary_source
        except Exception as exc:
            LOGGER.exception("采集 %s 失败：%s", key, exc)
            backup = fallback.get(key)
            if not backup:
                snapshot[key] = []
                sources[key] = "暂缺"
                continue
            try:
                backup_func, backup_source = backup
                snapshot[key] = backup_func()
                sources[key] = backup_source
                LOGGER.info("已使用备用数据源补齐 %s", key)
            except Exception as backup_exc:
                LOGGER.exception("备用数据源采集 %s 也失败：%s", key, backup_exc)
                snapshot[key] = []
                sources[key] = "暂缺"
    snapshot["来源"] = sources
    return snapshot
