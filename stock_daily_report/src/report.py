"""生成中文 HTML 与 Markdown 简报。"""

from __future__ import annotations

import html
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional


def _fmt(value: Any, digits: int = 2, suffix: str = "") -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.{digits}f}{suffix}"
    except (TypeError, ValueError):
        return str(value)


def _pct(value: Any) -> str:
    if value is None:
        return "—"
    number = float(value)
    text = f"{number:+.2f}%"
    return text


def _previous_close(row: Dict[str, Any]) -> Any:
    """优先取行情接口的昨收，缺失时用最新价与涨跌幅反推。"""
    previous = row.get("昨收")
    if previous not in (None, 0, "-", "--", ""):
        return previous
    latest = row.get("最新价")
    change = row.get("涨跌幅")
    if latest in (None, 0) or change is None:
        return None
    try:
        return float(latest) / (1 + float(change) / 100)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _prev_close_text(row: Dict[str, Any]) -> str:
    value = _previous_close(row)
    return _fmt(value) if value is not None else "—"


def _css_class(value: Any) -> str:
    if value is None:
        return ""
    try:
        return "up" if float(value) > 0 else ("down" if float(value) < 0 else "flat")
    except (TypeError, ValueError):
        return ""


def _sector_names(sectors: Any, limit: int = 5) -> str:
    if not isinstance(sectors, list):
        return "暂无数据"
    names = [str(s.get("名称", "")) for s in sectors[:limit] if s.get("名称")]
    return "、".join(names) if names else "暂无数据"


def _overview_text(snapshot: Dict[str, Any]) -> List[str]:
    """市场概览：成交额、涨跌家数与涨跌停数量。"""
    summary = snapshot.get("汇总") or {}
    lines: List[str] = []
    if isinstance(summary, dict):
        amount = summary.get("两市成交额")
        up = summary.get("上涨家数")
        down = summary.get("下跌家数")
        limit_up = summary.get("涨停家数")
        limit_down = summary.get("跌停家数")
        parts = []
        if amount not in (None, 0):
            try:
                parts.append(f"两市成交额约 {float(amount) / 1e8:.0f} 亿元")
            except (TypeError, ValueError):
                parts.append("两市成交额数据暂缺")
        else:
            parts.append("两市成交额数据暂缺")
        if up not in (None, 0) or down not in (None, 0):
            parts.append(f"上涨 {up} 家 / 下跌 {down} 家")
        if limit_up not in (None, 0) or limit_down not in (None, 0):
            parts.append(f"涨停 {limit_up} 家 / 跌停 {limit_down} 家")
        lines.append("；".join(parts))
    if not lines:
        lines.append("市场情绪数据暂缺，可参考下方指数与板块表现。")
    return lines


def _turnover_assessment(summary: Dict[str, Any]) -> str:
    """用固定阈值对成交额与涨跌家数做规则化客观评价。"""
    amount = summary.get("两市成交额")
    up = summary.get("上涨家数")
    down = summary.get("下跌家数")
    limit_up = summary.get("涨停家数")
    limit_down = summary.get("跌停家数")

    volume_text = "两市成交额数据暂缺"
    volume_level = 2
    if amount not in (None, 0):
        try:
            yi = float(amount) / 1e8
            if yi >= 15000:
                volume_text = f"两市成交额约 {yi:.0f} 亿元，处于高量能区（不低于 15000 亿元）"
                volume_level = 4
            elif yi >= 12000:
                volume_text = f"两市成交额约 {yi:.0f} 亿元，处于中高量能区（12000-15000 亿元）"
                volume_level = 3
            elif yi >= 10000:
                volume_text = f"两市成交额约 {yi:.0f} 亿元，处于正常量能区（10000-12000 亿元）"
                volume_level = 2
            elif yi >= 8000:
                volume_text = f"两市成交额约 {yi:.0f} 亿元，处于中低量能区（8000-10000 亿元）"
                volume_level = 1
            else:
                volume_text = f"两市成交额约 {yi:.0f} 亿元，处于低量能区（低于 8000 亿元）"
                volume_level = 0
        except (TypeError, ValueError):
            pass

    breadth_text = ""
    breadth_level = 2
    if up not in (None, 0) and down not in (None, 0):
        try:
            ratio = float(up) / float(down)
            if ratio >= 2:
                breadth_text = "上涨家数明显多于下跌家数，赚钱效应显著偏强"
                breadth_level = 4
            elif ratio >= 1.3:
                breadth_text = "上涨家数多于下跌家数，赚钱效应偏强"
                breadth_level = 3
            elif ratio >= 0.8:
                breadth_text = "涨跌家数相对均衡，赚钱效应中性"
                breadth_level = 2
            elif ratio >= 0.5:
                breadth_text = "下跌家数多于上涨家数，赚钱效应偏弱"
                breadth_level = 1
            else:
                breadth_text = "下跌家数明显多于上涨家数，赚钱效应显著偏弱"
                breadth_level = 0
        except (TypeError, ValueError, ZeroDivisionError):
            pass

    limit_text = ""
    if limit_up not in (None, 0) or limit_down not in (None, 0):
        limit_text = f"涨停 {limit_up} 家 / 跌停 {limit_down} 家"

    if volume_level >= 3 and breadth_level >= 3:
        sentiment = "放量且赚钱效应较好，情绪偏热，短线追高需注意拥挤度"
    elif volume_level >= 3 and breadth_level <= 1:
        sentiment = "放量但下跌家数占优，存在量价背离，情绪偏谨慎"
    elif volume_level <= 1 and breadth_level >= 3:
        sentiment = "缩量但赚钱效应尚可，反弹持续性仍待验证，情绪中性"
    elif volume_level <= 1 and breadth_level <= 1:
        sentiment = "缩量且赚钱效应偏弱，观望情绪较浓，情绪偏冷"
    else:
        sentiment = "量能与涨跌家数均处于中性区间，情绪总体中性"
    if limit_up and limit_up >= 60:
        sentiment += "，涨停家数较多，局部赚钱效应活跃"
    if limit_down and limit_down >= 20:
        sentiment += "，跌停家数偏多，短线风险需要留意"

    parts = [volume_text]
    if breadth_text:
        parts.append(breadth_text)
    if limit_text:
        parts.append(limit_text)
    return "；".join(parts) + f"。客观评价：{sentiment}。"


def _find(rows: Any, name: str) -> Dict[str, Any] | None:
    if not isinstance(rows, list):
        return None
    for row in rows:
        if str(row.get("名称", "")) == name:
            return row
    return None


def _index_summary(rows: Any, name: str) -> str:
    row = _find(rows, name)
    if not row:
        return "暂无数据"
    return f"{_fmt(row.get('最新价'))}（{_pct(row.get('涨跌幅'))}）"


def _source_text(snapshot: Dict[str, Any]) -> str:
    sources = snapshot.get("来源") or {}
    used = {str(value) for value in sources.values() if value and value != "暂缺"}
    if not used:
        return "公开行情"
    if "腾讯/新浪/Naver" in used:
        used.discard("腾讯")
        used.discard("新浪")
    order = ["东方财富", "腾讯", "新浪", "Naver", "腾讯/新浪/Naver", "新浪行业替代"]
    ordered = [name for name in order if name in used]
    extra = sorted(name for name in used if name not in order)
    return "、".join(ordered + extra)


def build_advice(snapshot: Dict[str, Any]) -> List[str]:
    """根据近几日与当日行情生成基金操作建议。"""
    advice: List[str] = []
    recent = snapshot.get("近期") or {}

    if isinstance(recent, dict) and recent.get("可用"):
        total = float(recent["累计涨跌幅"])
        if total >= 3:
            advice.append(
                f"近 5 个交易日上证指数累计上涨 {total:+.2f}%，短线趋势偏强。"
                "宽基指数基金可继续分批定投，行业基金建议等回调再买入，避免一次性追高。"
            )
        elif total <= -3:
            advice.append(
                f"近 5 个交易日上证指数累计下跌 {total:+.2f}%，市场情绪偏弱。"
                "建议保持定投纪律摊薄成本，高仓位基金可分批止盈或降仓，不要用杠杆抄底。"
            )
        else:
            advice.append(
                f"近 5 个交易日上证指数累计 {total:+.2f}%，整体处于震荡区间。"
                "宽基基金按既定节奏定投即可，行业基金轻仓参与，等趋势明朗后再加仓。"
            )
        if float(recent["最大单日跌幅"]) <= -1.5:
            advice.append("近几日出现单日明显回调，短线波动加大，可把行业基金仓位控制在总仓位一半以内。")

    sectors = snapshot.get("板块") or {}
    top_sectors = sectors.get("领涨行业") if isinstance(sectors, dict) else None
    if isinstance(top_sectors, list) and top_sectors:
        names = _sector_names(top_sectors, 5)
        tech_words = ("AI", "人工智能", "算力", "半导体", "电子", "通信", "计算机", "软件", "元件", "芯片")
        defense_words = ("银行", "煤炭", "公用事业", "电力", "石油", "保险")
        consumer_words = ("白酒", "食品饮料", "家电", "汽车", "医药")
        if any(word in names for word in tech_words):
            advice.append(f"今日领涨方向集中在 {names}，科技成长风格占优；相关行业基金可观察回踩后的机会，避免追涨。")
        elif any(word in names for word in defense_words):
            advice.append(f"今日领涨方向集中在 {names}，市场偏向防御；红利、低波类基金相对抗跌，可适度配置。")
        elif any(word in names for word in consumer_words):
            advice.append(f"今日领涨方向集中在 {names}，消费与核心资产出现反弹；可小仓位参与，关注持续性。")
        else:
            advice.append(f"今日领涨方向集中在 {names}，板块轮动较快，建议以分散配置代替押注单一行业。")

    global_rows = snapshot.get("全球") or []
    dow = _find(global_rows, "道琼斯")
    kospi = _find(global_rows, "韩国KOSPI")
    if dow or kospi:
        parts = []
        if dow:
            parts.append(f"道琼斯 {_pct(dow.get('涨跌幅'))}")
        if kospi:
            parts.append(f"韩国KOSPI {_pct(kospi.get('涨跌幅'))}")
        parts_text = "，".join(parts)
        if any("+" in part for part in parts):
            advice.append(f"外围市场 {parts_text}，对 A 股情绪形成支撑；但外围波动仍可能传导，仓位不宜一次性打满。")
        else:
            advice.append(f"外围市场 {parts_text}，海外风险偏好偏弱；A 股基金操作以防御和定投为主，不宜重仓追涨。")

    etf_rows = snapshot.get("ETF") or []
    if isinstance(etf_rows, list) and etf_rows:
        strong = sorted(
            [e for e in etf_rows if e.get("涨跌幅") is not None],
            key=lambda x: float(x["涨跌幅"]),
            reverse=True,
        )[:3]
        if strong:
            strong_text = "、".join(
                f"{s.get('名称', '')} {_pct(s.get('涨跌幅'))}" for s in strong
            )
            advice.append(f"今日场内 ETF 中相对强势的有 {strong_text}，可将其作为观察行业基金强弱的风向标。")

    summary = snapshot.get("汇总") or {}
    if isinstance(summary, dict):
        up = summary.get("上涨家数")
        down = summary.get("下跌家数")
        if up not in (None, 0) and down not in (None, 0):
            try:
                ratio = float(up) / float(down)
                if ratio < 0.7:
                    advice.append(f"今日上涨 {up} 家、下跌 {down} 家，市场赚钱效应弱；基金操作宜以防守和定投为主，不追高。")
                elif ratio > 1.5:
                    advice.append(f"今日上涨 {up} 家、下跌 {down} 家，市场赚钱效应较好；可维持既定仓位，行业基金小步分批参与。")
            except (TypeError, ValueError, ZeroDivisionError):
                pass

    key_rows = snapshot.get("重点指数") or []
    if isinstance(key_rows, list) and key_rows:
        key_with_change = [
            r for r in key_rows
            if r.get("涨跌幅") is not None and abs(float(r["涨跌幅"])) >= 0.5
        ]
        strong_key = sorted(key_with_change, key=lambda x: float(x["涨跌幅"]), reverse=True)[:2]
        weak_key = sorted(key_with_change, key=lambda x: float(x["涨跌幅"]))[:2]
        if strong_key and weak_key:
            strong_text = "、".join(f"{s.get('名称', '')} {_pct(s.get('涨跌幅'))}" for s in strong_key)
            weak_text = "、".join(f"{w.get('名称', '')} {_pct(w.get('涨跌幅'))}" for w in weak_key)
            advice.append(
                f"重点观察指数中 {strong_text} 相对强势，{weak_text} 相对偏弱；"
                "对应行业基金可顺势关注强势方向，弱势方向暂以观望为主。"
            )

    fund_refs = build_fund_suggestions(snapshot)
    if fund_refs:
        advice.append("今日具体基金标的参考：" + "；".join(fund_refs))
    advice.append("建议保持组合分散：宽基打底、行业做卫星，单只行业基金不超过权益仓位的 20%，并设置止盈纪律。")
    advice.append("以上基金标的与建议由程序按公开行情规则化生成，仅供研究参考，不构成投资建议；投资者应自行判断并承担风险。")
    advice.append("以上为基于公开行情的规则化参考，不构成投资建议；实际决策请结合自身风险承受能力。")
    return advice


def build_sector_views(snapshot: Dict[str, Any]) -> List[str]:
    """按重点行业生成板块观点，缺失时用领涨领跌行业补足。"""
    views: List[str] = []
    sectors = snapshot.get("板块") or {}
    key_rows = snapshot.get("重点方向")
    if not isinstance(key_rows, list) or not key_rows:
        key_rows = sectors.get("重点行业") if isinstance(sectors, dict) else None
    if not isinstance(key_rows, list) or not key_rows:
        key_rows = []
    if not key_rows:
        key_rows = (sectors.get("领涨行业") if isinstance(sectors, dict) else None) or []
    for row in key_rows:
        name = str(row.get("名称", ""))
        change = row.get("涨跌幅")
        if not name or change is None:
            continue
        try:
            change = float(change)
        except (TypeError, ValueError):
            continue
        if change >= 1.5:
            views.append(f"{name}今日走强，资金关注度上升；相关基金可等待回踩企稳后分批参与。")
        elif change >= 0.3:
            views.append(f"{name}今日小幅上涨，短线趋势偏稳；持有者按既定节奏操作，暂不加仓。")
        elif change <= -1.5:
            views.append(f"{name}今日明显走弱，短线承压；相关基金暂以观望为主，不急于抄底。")
        elif change <= -0.3:
            views.append(f"{name}今日震荡回调，消化前期抛压；基金仓位可控制，等趋势明朗再操作。")
        else:
            views.append(f"{name}今日窄幅震荡，方向不明；多看少动，等待明确信号。")
    return views[:12]


def _trend_change(snapshot: Dict[str, Any], name: str, limit: int) -> Optional[float]:
    rows = _trend_rows(snapshot, name)
    if not rows:
        return None
    closes = [
        row.get("收盘价")
        for row in rows[-limit:]
        if row.get("收盘价") is not None
    ]
    if len(closes) < 2 or not closes[0]:
        return None
    return (closes[-1] - closes[0]) / closes[0] * 100


def _direction_leader(rows: Any, keywords: tuple) -> Dict[str, Any] | None:
    if not isinstance(rows, list):
        return None
    matched = [
        row for row in rows
        if row.get("涨跌幅") is not None and any(
            keyword in str(row.get("名称", "")) for keyword in keywords
        )
    ]
    if not matched:
        return None
    return max(matched, key=lambda row: float(row["涨跌幅"]))


def build_fund_suggestions(snapshot: Dict[str, Any]) -> List[str]:
    """结合重点方向与近期走势，给出具体基金标的参考及理由。"""
    suggestions: List[str] = []
    etf_by_name = {
        str(row.get("名称", "")): row
        for row in snapshot.get("ETF") or []
    }
    direction_rows = snapshot.get("重点方向") or []
    if not isinstance(direction_rows, list):
        direction_rows = []

    tech_leader = _direction_leader(
        direction_rows,
        ("AI", "人工智能", "算力", "通信", "半导体", "芯片", "软件", "计算机", "电子", "光模块", "机器人"),
    )
    med_leader = _direction_leader(
        direction_rows,
        ("医药", "创新药", "医疗", "生物", "中药"),
    )

    def pick_fund(direction: Dict[str, Any], kind: str) -> str:
        name = str(direction.get("名称", ""))
        if kind == "医药":
            return "医药ETF"
        if "半导体" in name or "芯片" in name:
            return "半导体ETF"
        return "科创50ETF"

    for direction, kind in ((tech_leader, "科技"), (med_leader, "医药")):
        if not direction:
            continue
        fund_name = pick_fund(direction, kind)
        fund_row = etf_by_name.get(fund_name)
        if not fund_row:
            continue
        code = str(fund_row.get("代码", ""))
        today = _pct(fund_row.get("涨跌幅"))
        week = _trend_change(snapshot, fund_name, 5)
        month = _trend_change(snapshot, fund_name, 21)
        direction_change = float(direction["涨跌幅"])
        reason = (
            f"跟踪{str(direction.get('名称', ''))}方向，该方向今日{direction_change:+.2f}%，"
            f"{fund_name}今日{today}"
        )
        if week is not None:
            reason += f"，近一周{week:+.2f}%"
        if month is not None:
            reason += f"，近一月{month:+.2f}%"
        if direction_change <= -1.5:
            reason += "；短线仍在走弱，建议等企稳后分批观察，不宜追跌满仓"
        elif direction_change >= 1.5 and week is not None and week > 0:
            reason += "；短线与近一周都偏强，可小仓位分批参与，做好止盈纪律"
        elif week is not None and week < 0:
            reason += "；近一周仍在回调，可先观察，等趋势转好再加仓"
        else:
            reason += "；量价平稳，可按既定节奏分批"
        label = f"{fund_name}（{code or fund_name}）"
        suggestions.append(f"{label}：{reason}。")

    if not suggestions:
        broad = etf_by_name.get("沪深300ETF")
        if broad:
            code = str(broad.get("代码", ""))
            today = _pct(broad.get("涨跌幅"))
            week = _trend_change(snapshot, "沪深300ETF", 5)
            reason = f"今日{today}"
            if week is not None:
                reason += f"，近一周{week:+.2f}%"
            reason += "；重点方向数据暂缺时，先以沪深300作为宽基配置底仓"
            suggestions.append(f"沪深300ETF（{code}）：{reason}。")

    return suggestions[:3]


def build_today_view(snapshot: Dict[str, Any]) -> str:
    """今日观点：结合指数、成交与外围方向生成一段总结。"""
    indexes = snapshot.get("指数") or []
    sh = _find(indexes, "上证指数")
    cyb = _find(indexes, "创业板指")
    summary = snapshot.get("汇总") or {}
    global_rows = snapshot.get("全球") or []
    dow = _find(global_rows, "道琼斯")
    kospi = _find(global_rows, "韩国KOSPI")

    parts = ["A 股今日整体"]
    if sh:
        sh_change = sh.get("涨跌幅")
        if sh_change is not None:
            if float(sh_change) > 0.5:
                parts.append("震荡上行")
            elif float(sh_change) > 0:
                parts.append("小幅上涨")
            elif float(sh_change) > -0.5:
                parts.append("窄幅震荡")
            else:
                parts.append("震荡走弱")
    if cyb:
        cyb_change = cyb.get("涨跌幅")
        if cyb_change is not None:
            if float(cyb_change) > 0:
                parts.append("，创业板表现相对活跃")
            else:
                parts.append("，成长风格相对偏弱")
    amount = summary.get("两市成交额") if isinstance(summary, dict) else None
    if amount:
        try:
            parts.append(f"，两市成交额约 {float(amount) / 1e8:.0f} 亿元")
        except (TypeError, ValueError):
            pass
    parts.append("。")
    text = "".join(parts)

    if dow or kospi:
        foreign = []
        if dow:
            foreign.append(f"美股道指 {_pct(dow.get('涨跌幅'))}")
        if kospi:
            foreign.append(f"韩股 {_pct(kospi.get('涨跌幅'))}")
        text += f"外围方面：{'，'.join(foreign)}；海外风险偏好整体"
        if any("+" in part for part in foreign):
            text += "偏暖，对 A 股情绪形成一定支撑。"
        else:
            text += "偏谨慎，A 股操作宜控制仓位。"
    else:
        text += "外围数据暂缺，建议同步关注晚间美股表现。"
    text += "基金操作上，宽基按定投节奏执行，行业基金不追涨、等回调，保持组合分散。"
    return text


def build_summary(snapshot: Dict[str, Any], target_date: date) -> str:
    """生成用于微信推送与收件箱的简短摘要。"""
    indexes = snapshot.get("指数") or []
    sh = _index_summary(indexes, "上证指数")
    cyb = _index_summary(indexes, "创业板指")
    sectors = snapshot.get("板块") or {}
    top = _sector_names(sectors.get("领涨行业") if isinstance(sectors, dict) else None, 3)
    global_rows = snapshot.get("全球") or []
    dow = _find(global_rows, "道琼斯")
    kospi = _find(global_rows, "韩国KOSPI")
    global_text = []
    if dow:
        global_text.append(f"道指 {_pct(dow.get('涨跌幅'))}")
    if kospi:
        global_text.append(f"韩股 {_pct(kospi.get('涨跌幅'))}")

    lines = [
        f"{target_date.isoformat()} 股市简报",
        f"A股：上证指数 {sh}；创业板指 {cyb}",
        f"主要板块：{top}",
        "市场情绪：" + _turnover_assessment(snapshot.get("汇总") or {}),
    ]
    if global_text:
        lines.append("外围：" + "，".join(global_text))
    advice = build_advice(snapshot)
    if advice:
        lines.append("基金建议：" + advice[0])
    fund_refs = build_fund_suggestions(snapshot)
    if fund_refs:
        lines.append("基金标的参考：" + fund_refs[0])
    return "\n".join(lines)


def _table(
    headers: List[str],
    rows: List[List[str]],
    css_classes: List[List[str]],
    html_columns: tuple = (),
) -> str:
    head = "".join(f"<th>{html.escape(str(h))}</th>" for h in headers)
    body = ""
    for row_index, (row, classes) in enumerate(zip(rows, css_classes)):
        cells = ""
        for column_index, (value, cls) in enumerate(zip(row, classes)):
            class_name = cls
            if column_index in html_columns:
                class_name = "name-cell"
            class_attr = f' class="{html.escape(class_name)}"' if class_name else ""
            if column_index in html_columns:
                cells += f"<td{class_attr}>{value}</td>"
            else:
                cells += f"<td{class_attr}>{html.escape(str(value))}</td>"
        body += f"<tr>{cells}</tr>"
    return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def _index_table(snapshot: Dict[str, Any], rows: Any) -> str:
    if not isinstance(rows, list) or not rows:
        return '<p class="empty">数据暂缺，稍后重试。</p>'
    headers = ["指数", "最新点位", "昨日收盘", "涨跌幅", "成交额"]
    table_rows = []
    classes = []
    for row in rows:
        amount = row.get("成交额")
        if amount is None or str(amount).strip() in ("", "-", "--"):
            amount_text = "—"
        else:
            try:
                amount_text = _fmt(float(amount) / 1e8, digits=0, suffix="亿")
            except (TypeError, ValueError):
                amount_text = "—"
        table_rows.append([
            _trend_cell(snapshot, row),
            _fmt(row.get("最新价")),
            _prev_close_text(row),
            _pct(row.get("涨跌幅")),
            amount_text,
        ])
        classes.append(["", "", "", _css_class(row.get("涨跌幅")), ""])
    return _table(headers, table_rows, classes, html_columns=(0,))


def _key_index_table(snapshot: Dict[str, Any], rows: Any) -> str:
    if not isinstance(rows, list) or not rows:
        return '<p class="empty">数据暂缺，稍后重试。</p>'
    headers = ["指数", "最新点位", "昨日收盘", "涨跌幅"]
    table_rows = []
    classes = []
    for row in rows:
        table_rows.append([
            _trend_cell(snapshot, row),
            _fmt(row.get("最新价")),
            _prev_close_text(row),
            _pct(row.get("涨跌幅")),
        ])
        classes.append(["", "", "", _css_class(row.get("涨跌幅"))])
    return _table(headers, table_rows, classes, html_columns=(0,))


def _overview_html(snapshot: Dict[str, Any]) -> str:
    summary = snapshot.get("汇总") or {}
    items = []
    if isinstance(summary, dict):
        amount = summary.get("两市成交额")
        if amount not in (None, 0):
            try:
                items.append(("两市成交额", f"约 {float(amount) / 1e8:.0f} 亿元"))
            except (TypeError, ValueError):
                items.append(("两市成交额", "数据暂缺"))
        else:
            items.append(("两市成交额", "数据暂缺"))
        up = summary.get("上涨家数")
        down = summary.get("下跌家数")
        if up not in (None, 0) or down not in (None, 0):
            items.append(("涨跌家数", f"{up} / {down}"))
        else:
            items.append(("涨跌家数", "数据暂缺"))
        limit_up = summary.get("涨停家数")
        limit_down = summary.get("跌停家数")
        if limit_up not in (None, 0) or limit_down not in (None, 0):
            items.append(("涨停 / 跌停", f"{limit_up} / {limit_down}"))
        else:
            items.append(("涨停 / 跌停", "数据暂缺"))
    if not items:
        items = [("两市成交额", "数据暂缺"), ("涨跌家数", "数据暂缺"), ("涨停 / 跌停", "数据暂缺")]
    cards = "".join(
        f'<div class="stat"><div class="stat-label">{html.escape(str(label))}</div>'
        f'<div class="stat-value">{html.escape(str(value))}</div></div>'
        for label, value in items
    )
    return f'<div class="overview-grid">{cards}</div>'


def _trend_rows(snapshot: Dict[str, Any], name: str) -> List[Dict[str, Any]]:
    trends = snapshot.get("走势") or {}
    data = trends.get(name) if isinstance(trends, dict) else None
    rows = data.get("明细") if isinstance(data, dict) else None
    return rows if isinstance(rows, list) else []


def _trend_chart_svg(rows: List[Dict[str, Any]], label: str, width: int = 240, height: int = 86) -> str:
    """把最近若干交易日的收盘价画成内联 SVG 折线图。"""
    closes = [row.get("收盘价") for row in rows if row.get("收盘价") is not None]
    if len(closes) < 2:
        return ""
    dates = [
        str(row.get("日期", ""))[-5:]
        for row in rows
        if row.get("收盘价") is not None
    ]
    min_value = min(closes)
    max_value = max(closes)
    span = max_value - min_value or 1
    pad_x = 10
    pad_y = 12
    count = len(closes)
    points = []
    for index, close in enumerate(closes):
        x = pad_x + (width - 2 * pad_x) * index / (count - 1)
        y = pad_y + (height - 2 * pad_y) * (1 - (close - min_value) / span)
        points.append(f"{x:.1f},{y:.1f}")
    change = (closes[-1] - closes[0]) / closes[0] * 100 if closes[0] else 0
    color = "#c0392b" if change > 0 else ("#0e8a5f" if change < 0 else "#5a6572")
    return (
        '<div class="trend-chart">'
        f'<div class="trend-chart-head"><span>{label}</span>'
        f'<span class="trend-change">{change:+.2f}%</span></div>'
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{label}变化">'
        f'<polyline fill="none" stroke="{color}" stroke-width="2" points="{" ".join(points)}"/>'
        "</svg>"
        f'<div class="trend-chart-meta">{dates[0]} 至 {dates[-1]}</div>'
        "</div>"
    )


def _trend_html(snapshot: Dict[str, Any], name: str) -> str:
    rows = _trend_rows(snapshot, name)
    if len(rows) < 2:
        return ""
    week = _trend_chart_svg(rows[-5:], "近一周")
    month = _trend_chart_svg(rows[-21:], "近一月")
    if not week and not month:
        return ""
    return (
        f'<details class="trend"><summary>{html.escape(name)}'
        '<span class="trend-badge">近一周/近一月</span></summary>'
        f'<div class="trend-grid">{week}{month}</div></details>'
    )


def _trend_cell(snapshot: Dict[str, Any], row: Dict[str, Any]) -> str:
    name = str(row.get("名称", ""))
    trend_html_content = _trend_html(snapshot, name)
    if trend_html_content:
        return trend_html_content
    return html.escape(name)


def _concept_html(snapshot: Dict[str, Any], concepts: Any) -> str:
    if not isinstance(concepts, list) or not concepts:
        return '<p class="empty">概念板块数据暂缺，可参考上方领涨行业。</p>'
    items = []
    for row in concepts:
        name = str(row.get("名称", ""))
        trend = _trend_html(snapshot, name)
        if trend:
            items.append(f"<li>{trend}</li>")
        else:
            change = _pct(row.get("涨跌幅"))
            items.append(
                f'<li><span class="concept-name">{html.escape(name)}</span>'
                f'<span class="concept-change {_css_class(row.get("涨跌幅"))}">{html.escape(change)}</span></li>'
            )
    return f'<ul class="concept-list">{"".join(items)}</ul>'


def _sector_table(snapshot: Dict[str, Any], rows: Any) -> str:
    if not isinstance(rows, list) or not rows:
        return '<p class="empty">数据暂缺，稍后重试。</p>'
    headers = ["板块", "最新点位", "昨日收盘", "涨跌幅", "换手率"]
    table_rows = []
    classes = []
    for row in rows:
        table_rows.append([
            _trend_cell(snapshot, row),
            _fmt(row.get("最新价")),
            _prev_close_text(row),
            _pct(row.get("涨跌幅")),
            _fmt(row.get("换手率"), digits=2, suffix="%"),
        ])
        classes.append(["", "", "", _css_class(row.get("涨跌幅")), ""])
    return _table(headers, table_rows, classes, html_columns=(0,))


def _sector_label(rows: Any, fallback: str = "领跌行业") -> str:
    """市场普涨时用更准确的标题，避免领跌列表仍显示上涨。"""
    if isinstance(rows, list) and rows:
        changes = []
        for row in rows:
            change = row.get("涨跌幅")
            if change is None:
                return fallback
            try:
                changes.append(float(change))
            except (TypeError, ValueError):
                return fallback
        if changes and all(value >= 0 for value in changes):
            return "涨幅居后行业"
    return fallback


def _global_table(snapshot: Dict[str, Any], rows: Any) -> str:
    if not isinstance(rows, list) or not rows:
        return '<p class="empty">数据暂缺，稍后重试。</p>'
    headers = ["市场", "最新点位", "昨日收盘", "涨跌幅"]
    table_rows = []
    classes = []
    for row in rows:
        table_rows.append([
            _trend_cell(snapshot, row),
            _fmt(row.get("最新价")),
            _prev_close_text(row),
            _pct(row.get("涨跌幅")),
        ])
        classes.append(["", "", "", _css_class(row.get("涨跌幅"))])
    return _table(headers, table_rows, classes, html_columns=(0,))


def _etf_table(snapshot: Dict[str, Any], rows: Any) -> str:
    if not isinstance(rows, list) or not rows:
        return '<p class="empty">数据暂缺，稍后重试。</p>'
    headers = ["ETF", "最新价", "昨日收盘", "涨跌幅"]
    table_rows = []
    classes = []
    for row in rows:
        table_rows.append([
            _trend_cell(snapshot, row),
            _fmt(row.get("最新价")),
            _prev_close_text(row),
            _pct(row.get("涨跌幅")),
        ])
        classes.append(["", "", "", _css_class(row.get("涨跌幅"))])
    return _table(headers, table_rows, classes, html_columns=(0,))


CSS = """
* { box-sizing: border-box; }
body {
  margin: 0;
  background: #eef2f5;
  color: #1f2933;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif;
  line-height: 1.55;
}
.wrap { max-width: 860px; margin: 0 auto; padding: 20px 16px 40px; }
.header { border-bottom: 3px solid #c2410c; padding-bottom: 14px; margin-bottom: 18px; }
.header h1 { margin: 0 0 6px; font-size: 24px; color: #0b3b5c; }
.header .meta { color: #52606d; font-size: 13px; }
.tag { display: inline-block; background: #0b3b5c; color: #fff; font-size: 12px; padding: 3px 10px; border-radius: 999px; margin-left: 6px; }
section { background: #fff; border: 1px solid #d9e2ec; border-radius: 8px; padding: 16px; margin-bottom: 16px; }
h2 { margin: 0 0 12px; font-size: 18px; color: #0b3b5c; }
.table-wrap { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; min-width: 520px; }
th, td { padding: 9px 10px; text-align: left; border-bottom: 1px solid #e4e7eb; white-space: nowrap; }
th { color: #52606d; font-weight: 600; font-size: 13px; background: #f7f9fb; }
td { font-size: 14px; }
.name-cell { min-width: 150px; white-space: normal; }
.up { color: #c0392b; font-weight: 600; }
.down { color: #0e8a5f; font-weight: 600; }
.flat { color: #5a6572; }
.sector-pair { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.sector-pair .half { min-width: 0; }
.advice { list-style: none; margin: 0; padding: 0; }
.advice li { position: relative; padding: 10px 12px 10px 34px; margin-bottom: 8px; background: #f7f9fb; border-radius: 6px; font-size: 14px; }
.advice li::before { content: "◆"; position: absolute; left: 12px; top: 10px; color: #c2410c; }
.notice { font-size: 12px; color: #7b8794; margin-top: 8px; }
.empty { color: #7b8794; font-size: 13px; }
.overview-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 12px; }
.stat { background: #f7f9fb; border: 1px solid #e4e7eb; border-radius: 6px; padding: 10px 12px; min-width: 0; }
.stat-label { color: #52606d; font-size: 12px; }
.stat-value { font-size: 16px; font-weight: 700; color: #0b3b5c; margin-top: 2px; word-break: break-all; }
.views { list-style: none; margin: 0; padding: 0; }
.views li { position: relative; padding: 8px 10px 8px 26px; margin-bottom: 6px; background: #f7f9fb; border-radius: 6px; font-size: 13px; line-height: 1.5; }
.views li::before { content: "·"; position: absolute; left: 12px; top: 7px; color: #c2410c; font-weight: 700; }
.today-view { background: #fff7ed; border: 1px solid #fbd38d; border-radius: 6px; padding: 12px 14px; font-size: 14px; line-height: 1.7; }
.assessment { margin: 10px 0 0; font-size: 13px; color: #334e68; background: #f0f6fa; border-left: 3px solid #0b3b5c; border-radius: 4px; padding: 8px 10px; line-height: 1.7; }
.trend summary { cursor: pointer; list-style: none; display: inline-flex; align-items: center; gap: 6px; color: #0b3b5c; }
.trend summary::-webkit-details-marker { display: none; }
.trend-badge { font-size: 11px; color: #0b3b5c; background: #e7eef5; border: 1px solid #b7c9d8; border-radius: 999px; padding: 1px 7px; white-space: nowrap; }
.trend-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 10px; background: #f7f9fb; border: 1px solid #e4e7eb; border-radius: 6px; padding: 10px; }
.trend-chart { background: #fff; border: 1px solid #e4e7eb; border-radius: 6px; padding: 8px; min-width: 0; }
.trend-chart-head { display: flex; justify-content: space-between; font-size: 12px; color: #52606d; margin-bottom: 4px; }
.trend-chip { font-size: 12px; color: #0b3b5c; margin-left: 6px; }
.trend-chart svg { width: 100%; height: 86px; display: block; }
.trend-chart-meta { font-size: 11px; color: #7b8794; margin-top: 3px; }
.concept-list { list-style: none; margin: 0; padding: 0; }
.concept-list li { margin-bottom: 6px; }
.concept-name { margin-right: 8px; }
.concept-change { font-weight: 600; }
@media (max-width: 620px) {
  .wrap { padding: 14px 10px 32px; }
  .header h1 { font-size: 20px; }
  .sector-pair { grid-template-columns: 1fr; }
  section { padding: 12px; }
  .overview-grid { grid-template-columns: 1fr 1fr; }
  .trend-grid { grid-template-columns: 1fr; }
}
"""


def build_html(snapshot: Dict[str, Any], target_date: date, source_time: str) -> str:
    """生成适合手机直接查看的单页 HTML。"""
    sectors = snapshot.get("板块") or {}
    recent = snapshot.get("近期") or {}
    recent_text = "暂无"
    if isinstance(recent, dict) and recent.get("可用"):
        recent_text = (
            f"近 5 个交易日上证指数累计 {float(recent['累计涨跌幅']):+.2f}%"
        )

    advice_items = "".join(f"<li>{html.escape(text)}</li>" for text in build_advice(snapshot))
    fund_ref_items = "".join(
        f"<li>{html.escape(text)}</li>"
        for text in build_fund_suggestions(snapshot)
    )
    sector_views = "".join(f"<li>{html.escape(text)}</li>" for text in build_sector_views(snapshot))
    top_html = _sector_table(snapshot, sectors.get("领涨行业") if isinstance(sectors, dict) else None)
    bottom_html = _sector_table(snapshot, sectors.get("领跌行业") if isinstance(sectors, dict) else None)
    bottom_label = _sector_label(sectors.get("领跌行业") if isinstance(sectors, dict) else None)
    key_html = _sector_table(snapshot, sectors.get("重点行业") if isinstance(sectors, dict) else None)
    tech_html = _sector_table(snapshot, snapshot.get("重点方向"))
    concepts = snapshot.get("热门概念") or []
    concept_html = _concept_html(snapshot, concepts)
    overview_text = "；".join(_overview_text(snapshot))
    assessment = _turnover_assessment(snapshot.get("汇总") or {})
    today_view = build_today_view(snapshot)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(str(target_date))} 每日股市与基金简报</title>
<!-- CSS_START -->
<style>{CSS}</style>
<!-- CSS_END -->
</head>
<body>
<!-- BODY_START -->
<div class="wrap">
  <div class="header">
    <h1>{html.escape(str(target_date))} 每日股市与基金简报<span class="tag">交易日速览</span></h1>
    <div class="meta">数据截至 {html.escape(source_time)}（北京时间）· 数据来源：{html.escape(_source_text(snapshot))} · {html.escape(recent_text)}</div>
  </div>

  <section>
    <h2>市场概览</h2>
    {_overview_html(snapshot)}
    <p>{html.escape(overview_text)}</p>
    <p class="assessment"><strong>情绪评价：</strong>{html.escape(assessment)}</p>
    <h2 style="margin-top:14px;">A股主要指数</h2>
    {_index_table(snapshot, snapshot.get("指数"))}
  </section>

  <section>
    <h2>重点指数观察</h2>
    {_key_index_table(snapshot, snapshot.get("重点指数"))}
  </section>

  <section>
    <h2>重点科技与医药方向</h2>
    {tech_html}
  </section>

  <section>
    <h2>主要板块</h2>
    <div class="sector-pair">
      <div class="half"><h2 style="font-size:15px;">领涨行业</h2>{top_html}</div>
      <div class="half"><h2 style="font-size:15px;">{bottom_label}</h2>{bottom_html}</div>
    </div>
    <h2 style="margin-top:16px;">重点关注行业</h2>
    {key_html}
    <h2 style="margin-top:16px;">热门概念</h2>
    {concept_html}
  </section>

  <section>
    <h2>板块观点</h2>
    <ul class="views">{sector_views}</ul>
  </section>

  <section>
    <h2>外盘动向</h2>
    {_global_table(snapshot, snapshot.get("全球"))}
  </section>

  <section>
    <h2>基金参考（场内ETF）</h2>
    {_etf_table(snapshot, snapshot.get("ETF"))}
  </section>

  <section>
    <h2>今日基金标的参考</h2>
    <ul class="advice">{fund_ref_items}</ul>
    <p class="notice">标的与理由由程序按公开行情与历史走势规则化生成，仅供研究参考，不构成投资建议。</p>
  </section>

  <section>
    <h2>基金操作建议</h2>
    <ol class="advice">{advice_items}</ol>
    <p class="notice">建议基于公开行情与历史走势的规则化分析生成，不构成投资建议。市场有风险，投资需谨慎。</p>
  </section>

  <section>
    <h2>今日观点</h2>
    <div class="today-view">{html.escape(today_view)}</div>
  </section>
</div>
<!-- BODY_END -->
</body>
</html>
"""


def build_markdown(snapshot: Dict[str, Any], target_date: date) -> str:
    """生成 Markdown 简报，便于留档与二次编辑。"""
    lines = [
        f"# {target_date.isoformat()} 每日股市与基金简报",
        "",
        "## 市场概览",
    ]
    summary = snapshot.get("汇总") or {}
    if isinstance(summary, dict):
        amount = summary.get("两市成交额")
        if amount:
            try:
                lines.append(f"- 两市成交额：约 {float(amount) / 1e8:.0f} 亿元")
            except (TypeError, ValueError):
                pass
        up = summary.get("上涨家数")
        down = summary.get("下跌家数")
        if up or down:
            lines.append(f"- 涨跌家数：{up} / {down}")
        limit_up = summary.get("涨停家数")
        limit_down = summary.get("跌停家数")
        if limit_up or limit_down:
            lines.append(f"- 涨停 / 跌停：{limit_up} / {limit_down}")
        lines.append("- 情绪评价：" + _turnover_assessment(summary))
    lines += [
        "",
        "## A股主要指数",
    ]
    for row in snapshot.get("指数") or []:
        lines.append(
            f"- {row.get('名称', '')}：最新 {_fmt(row.get('最新价'))}，昨日 {_prev_close_text(row)}"
            f"（{_pct(row.get('涨跌幅'))}）"
        )
    lines += ["", "## 重点指数观察"]
    for row in snapshot.get("重点指数") or []:
        lines.append(
            f"- {row.get('名称', '')}：最新 {_fmt(row.get('最新价'))}，昨日 {_prev_close_text(row)}"
            f"（{_pct(row.get('涨跌幅'))}）"
        )
    lines += ["", "## 重点科技与医药方向"]
    for row in snapshot.get("重点方向") or []:
        lines.append(
            f"- {row.get('名称', '')}：最新 {_fmt(row.get('最新价'))}，昨日 {_prev_close_text(row)}"
            f"（{_pct(row.get('涨跌幅'))}）"
        )
    lines += ["", "## 主要板块"]
    sectors = snapshot.get("板块") or {}
    if isinstance(sectors, dict):
        lines += ["### 领涨行业"]
        for row in sectors.get("领涨行业") or []:
            lines.append(
                f"- {row.get('名称', '')}：最新 {_fmt(row.get('最新价'))}，昨日 {_prev_close_text(row)}"
                f"（{_pct(row.get('涨跌幅'))}）"
            )
        lines += [f"### {_sector_label(sectors.get('领跌行业'))}"]
        for row in sectors.get("领跌行业") or []:
            lines.append(
                f"- {row.get('名称', '')}：最新 {_fmt(row.get('最新价'))}，昨日 {_prev_close_text(row)}"
                f"（{_pct(row.get('涨跌幅'))}）"
            )
    lines += ["", "## 板块观点"]
    lines.extend(f"- {text}" for text in build_sector_views(snapshot))
    lines += ["", "## 外盘动向"]
    for row in snapshot.get("全球") or []:
        lines.append(
            f"- {row.get('名称', '')}：最新 {_fmt(row.get('最新价'))}，昨日 {_prev_close_text(row)}"
            f"（{_pct(row.get('涨跌幅'))}）"
        )
    lines += ["", "## 基金参考（场内ETF）"]
    for row in snapshot.get("ETF") or []:
        lines.append(
            f"- {row.get('名称', '')}：最新 {_fmt(row.get('最新价'))}，昨日 {_prev_close_text(row)}"
            f"（{_pct(row.get('涨跌幅'))}）"
        )
    lines += ["", "## 今日基金标的参考", ""]
    lines.extend(f"- {text}" for text in build_fund_suggestions(snapshot))
    lines += ["", "## 基金操作建议", ""]
    lines.extend(f"- {text}" for text in build_advice(snapshot))
    lines += ["", "## 今日观点", "", build_today_view(snapshot)]
    lines += ["", "> 不构成投资建议，市场有风险，投资需谨慎。"]
    lines += ["", "> 建议来源：由程序基于东方财富、腾讯、新浪、Naver 公开行情与历史走势规则化生成，非人工投顾判断。"]
    return "\n".join(lines)


def write_reports(
    cfg: Dict[str, Any],
    snapshot: Dict[str, Any],
    target_date: date,
    source_time: str,
    output_dir: Path,
) -> Path:
    """把简报写入输出目录，返回 HTML 文件路径。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    html_path = output_dir / str(cfg.get("报告文件名", "index.html"))
    markdown_path = output_dir / str(cfg.get("Markdown文件名", "report.md"))
    html_path.write_text(build_html(snapshot, target_date, source_time), encoding="utf-8")
    markdown_path.write_text(build_markdown(snapshot, target_date), encoding="utf-8")
    return html_path
