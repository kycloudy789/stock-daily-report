"""调用大模型作为 AI 分析师，生成投资建议与基金参考。"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import date
from typing import Any, Dict, List

import requests

LOGGER = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"

SYSTEM_PROMPT = (
    "你是一名专业、谨慎的 A 股与基金分析师，服务对象是主要以基金方式参与市场的个人投资者。"
    "你只能依据用户消息中提供的公开行情数据作答，不得编造数据、指数值或基金标的。"
    "请使用简体中文，条理清晰，语气审慎，明确说明不确定性。"
    "你必须提醒：内容仅供研究参考，不构成投资建议，投资者应自行判断并承担风险。"
    "输出必须是合法 JSON 对象，只包含以下四个字段："
    '"投资建议"：字符串数组，3 到 6 条，每条一句话，包含宽基定投、行业基金仓位、止盈止损等可执行操作；'
    '"基金参考"：字符串数组，2 到 4 条，每条格式为“基金名称（代码）：理由”，只能从数据中出现的 ETF 里挑选；'
    '"今日观点"：字符串，2 到 4 句话，概括今日 A 股与外围市场并说明关注重点；'
    '"风险提示"：字符串，一句话。'
)


def analyst_config(cfg: Dict[str, Any]) -> Dict[str, str]:
    """读取 AI 分析师参数，环境变量优先于配置文件。"""
    return {
        "api_key": str(
            os.environ.get("AI_ANALYST_API_KEY")
            or cfg.get("AI 分析师 API Key")
            or ""
        ).strip(),
        "base_url": str(
            os.environ.get("AI_ANALYST_BASE_URL")
            or cfg.get("AI 分析师 API地址")
            or DEFAULT_BASE_URL
        ).strip().rstrip("/"),
        "model": str(
            os.environ.get("AI_ANALYST_MODEL")
            or cfg.get("AI 分析师模型")
            or DEFAULT_MODEL
        ).strip(),
    }


def _number(value: Any) -> float | None:
    try:
        if value in (None, "", "-", "--"):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _change_text(value: Any) -> str:
    number = _number(value)
    return "" if number is None else f"{number:+.2f}%"


def _trend_change(snapshot: Dict[str, Any], name: str, limit: int) -> float | None:
    trends = snapshot.get("走势") or {}
    data = trends.get(name) if isinstance(trends, dict) else None
    rows = data.get("明细") if isinstance(data, dict) else None
    if not isinstance(rows, list) or len(rows) < 2:
        return None
    closes = [
        _number(row.get("收盘价"))
        for row in rows[-limit:]
        if row.get("收盘价") is not None
    ]
    closes = [value for value in closes if value is not None]
    if len(closes) < 2 or not closes[0]:
        return None
    return (closes[-1] - closes[0]) / closes[0] * 100


def _table_text(rows: Any, snapshot: Dict[str, Any], max_rows: int) -> List[str]:
    if not isinstance(rows, list) or not rows:
        return []
    lines: List[str] = []
    for row in rows[:max_rows]:
        if not isinstance(row, dict):
            continue
        name = str(row.get("名称", "")).strip()
        if not name:
            continue
        parts = [name]
        latest = row.get("最新价")
        if latest not in (None, "", "-", "--"):
            parts.append(str(latest))
        change = _change_text(row.get("涨跌幅"))
        if change:
            parts.append(change)
        week = _trend_change(snapshot, name, 5)
        month = _trend_change(snapshot, name, 21)
        if week is not None:
            parts.append(f"周{week:+.2f}%")
        if month is not None:
            parts.append(f"月{month:+.2f}%")
        lines.append(" ".join(parts))
    return lines


def build_market_prompt(
    snapshot: Dict[str, Any],
    target_date: date,
    source_time: str,
) -> str:
    """把当日市场快照整理成简洁数据文本，供 AI 分析师分析。"""
    lines = [f"交易日：{target_date.isoformat()}；数据截至：{source_time}（北京时间）。"]

    summary = snapshot.get("汇总") or {}
    if isinstance(summary, dict):
        parts = []
        amount = _number(summary.get("两市成交额"))
        if amount is not None and amount > 0:
            parts.append(f"两市成交额约{amount / 1e8:.0f}亿元")
        up = _number(summary.get("上涨家数"))
        down = _number(summary.get("下跌家数"))
        if up is not None and down is not None and (up > 0 or down > 0):
            parts.append(f"上涨{up:.0f}家/下跌{down:.0f}家")
        limit_up = _number(summary.get("涨停家数"))
        limit_down = _number(summary.get("跌停家数"))
        if limit_up is not None or limit_down is not None:
            parts.append(f"涨停{limit_up or 0:.0f}家/跌停{limit_down or 0:.0f}家")
        if parts:
            lines.append("市场情绪：" + "；".join(parts) + "。")

    sections = [
        ("A股主要指数", snapshot.get("指数"), 8),
        ("重点指数观察", snapshot.get("重点指数"), 12),
        ("重点科技与医药方向", snapshot.get("重点方向"), 14),
        ("领涨行业", (snapshot.get("板块") or {}).get("领涨行业"), 6),
        ("领跌行业", (snapshot.get("板块") or {}).get("领跌行业"), 6),
        ("外盘", snapshot.get("全球"), 10),
        ("场内ETF", snapshot.get("ETF"), 14),
    ]
    for label, rows, max_rows in sections:
        text_rows = _table_text(rows, snapshot, max_rows)
        if text_rows:
            lines.append(f"【{label}】")
            lines.extend("- " + text for text in text_rows)

    recent = snapshot.get("近期") or {}
    if isinstance(recent, dict) and recent.get("可用"):
        total = recent.get("累计涨跌幅")
        if total is not None:
            lines.append(
                f"【近期】近几个交易日上证指数累计变化 {_change_text(total)}；"
                f"最大单日跌幅 {_change_text(recent.get('最大单日跌幅'))}。"
            )

    prompt = (
        "以下是今日已抓取的公开行情数据（含近一周/近一月涨跌幅，周/月为收盘价累计变化）。\n\n"
        + "\n".join(lines)
        + "\n\n请按系统角色的要求输出 JSON。"
    )
    return prompt


def request_analysis(prompt: str, conf: Dict[str, str], timeout: int = 90) -> str:
    """调用 OpenAI 兼容的 /chat/completions 接口，返回模型文本。"""
    url = f"{conf['base_url']}/chat/completions"
    headers = {"Authorization": f"Bearer {conf['api_key']}"}
    payload: Dict[str, Any] = {
        "model": conf["model"],
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.35,
        "max_tokens": 1500,
    }
    try:
        payload["response_format"] = {"type": "json_object"}
        resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
        resp.raise_for_status()
    except requests.HTTPError as exc:
        if exc.response is None or exc.response.status_code != 400:
            raise
        payload.pop("response_format", None)
        resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
        resp.raise_for_status()
    data = resp.json()
    return str(data["choices"][0]["message"]["content"])


def _extract_json(text: str) -> Dict[str, Any]:
    text = str(text).strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    return json.loads(text)


def parse_analysis(content: str) -> Dict[str, Any]:
    data = _extract_json(content)

    def to_list(value: Any) -> List[str]:
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    return {
        "advice": to_list(data.get("投资建议"))[:6],
        "funds": to_list(data.get("基金参考"))[:4],
        "today_view": str(data.get("今日观点") or "").strip(),
        "risk": str(data.get("风险提示") or "").strip(),
    }


def _filter_funds(
    funds: List[str],
    snapshot: Dict[str, Any],
) -> List[str]:
    known_names = {str(row.get("名称", "")) for row in snapshot.get("ETF") or []}
    known_codes = {str(row.get("代码", "")) for row in snapshot.get("ETF") or []}
    kept: List[str] = []
    for item in funds:
        name = item.split("（", 1)[0].strip()
        codes = re.findall(r"(\d{6})", item)
        if name in known_names or any(code in known_codes for code in codes):
            kept.append(item)
    return kept[:4]


def run_ai_analyst(
    snapshot: Dict[str, Any],
    target_date: date,
    source_time: str,
    cfg: Dict[str, Any],
) -> Dict[str, Any]:
    """执行一次 AI 分析并返回结构化结果；失败时标记 ready=False 供报告降级。"""
    conf = analyst_config(cfg)
    result: Dict[str, Any] = {
        "enabled": bool(conf["api_key"]),
        "ready": False,
        "model": conf["model"],
        "provider": conf["base_url"],
        "advice": [],
        "funds": [],
        "today_view": "",
        "risk": "",
        "error": "",
        "generated_at": source_time,
    }
    if not conf["api_key"]:
        result["error"] = "未配置 AI 分析师 API Key，当前使用系统规则备用方案。"
        return result
    try:
        prompt = build_market_prompt(snapshot, target_date, source_time)
        content = request_analysis(prompt, conf)
        parsed = parse_analysis(content)
        funds = _filter_funds(parsed["funds"], snapshot)
        if not parsed["advice"] and not parsed["today_view"]:
            raise RuntimeError("AI 分析师返回内容为空")
        result["advice"] = parsed["advice"]
        result["funds"] = funds
        result["today_view"] = parsed["today_view"]
        result["risk"] = parsed["risk"]
        result["ready"] = True
    except Exception as exc:
        LOGGER.warning("AI 分析师调用失败，将使用系统规则备用方案：%s", exc)
        result["error"] = f"AI 分析师调用失败：{exc}"
    return result
