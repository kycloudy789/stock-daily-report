"""生成中文 HTML 与 Markdown 简报。"""

from __future__ import annotations

import html
from datetime import date
from pathlib import Path
from typing import Any, Dict, List


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
        tech_words = ("半导体", "电子", "通信", "计算机", "软件", "元件", "芯片")
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

    advice.append("建议保持组合分散：宽基打底、行业做卫星，单只行业基金不超过权益仓位的 20%，并设置止盈纪律。")
    advice.append("以上为基于公开行情的规则化参考，不构成投资建议；实际决策请结合自身风险承受能力。")
    return advice


def build_sector_views(snapshot: Dict[str, Any]) -> List[str]:
    """按重点行业生成板块观点，缺失时用领涨领跌行业补足。"""
    views: List[str] = []
    sectors = snapshot.get("板块") or {}
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
    ]
    if global_text:
        lines.append("外围：" + "，".join(global_text))
    advice = build_advice(snapshot)
    if advice:
        lines.append("基金建议：" + advice[0])
    return "\n".join(lines)


def _table(headers: List[str], rows: List[List[str]], css_classes: List[List[str]]) -> str:
    head = "".join(f"<th>{html.escape(str(h))}</th>" for h in headers)
    body = ""
    for row, classes in zip(rows, css_classes):
        cells = ""
        for value, cls in zip(row, classes):
            class_attr = f' class="{html.escape(cls)}"' if cls else ""
            cells += f"<td{class_attr}>{html.escape(str(value))}</td>"
        body += f"<tr>{cells}</tr>"
    return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def _index_table(rows: Any) -> str:
    if not isinstance(rows, list) or not rows:
        return '<p class="empty">数据暂缺，稍后重试。</p>'
    headers = ["指数", "最新点位", "涨跌幅", "成交额"]
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
            row.get("名称", ""),
            _fmt(row.get("最新价")),
            _pct(row.get("涨跌幅")),
            amount_text,
        ])
        classes.append(["", "", _css_class(row.get("涨跌幅")), ""])
    return _table(headers, table_rows, classes)


def _key_index_table(rows: Any) -> str:
    if not isinstance(rows, list) or not rows:
        return '<p class="empty">数据暂缺，稍后重试。</p>'
    headers = ["指数", "最新点位", "涨跌幅"]
    table_rows = []
    classes = []
    for row in rows:
        table_rows.append([
            row.get("名称", ""),
            _fmt(row.get("最新价")),
            _pct(row.get("涨跌幅")),
        ])
        classes.append(["", "", _css_class(row.get("涨跌幅"))])
    return _table(headers, table_rows, classes)


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


def _sector_table(rows: Any) -> str:
    if not isinstance(rows, list) or not rows:
        return '<p class="empty">数据暂缺，稍后重试。</p>'
    headers = ["板块", "涨跌幅", "换手率"]
    table_rows = []
    classes = []
    for row in rows:
        table_rows.append([
            row.get("名称", ""),
            _pct(row.get("涨跌幅")),
            _fmt(row.get("换手率"), digits=2, suffix="%"),
        ])
        classes.append(["", _css_class(row.get("涨跌幅")), ""])
    return _table(headers, table_rows, classes)


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


def _global_table(rows: Any) -> str:
    if not isinstance(rows, list) or not rows:
        return '<p class="empty">数据暂缺，稍后重试。</p>'
    headers = ["市场", "最新点位", "涨跌幅"]
    table_rows = []
    classes = []
    for row in rows:
        table_rows.append([row.get("名称", ""), _fmt(row.get("最新价")), _pct(row.get("涨跌幅"))])
        classes.append(["", "", _css_class(row.get("涨跌幅"))])
    return _table(headers, table_rows, classes)


def _etf_table(rows: Any) -> str:
    if not isinstance(rows, list) or not rows:
        return '<p class="empty">数据暂缺，稍后重试。</p>'
    headers = ["ETF", "最新价", "涨跌幅"]
    table_rows = []
    classes = []
    for row in rows:
        table_rows.append([row.get("名称", ""), _fmt(row.get("最新价")), _pct(row.get("涨跌幅"))])
        classes.append(["", "", _css_class(row.get("涨跌幅"))])
    return _table(headers, table_rows, classes)


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
@media (max-width: 620px) {
  .wrap { padding: 14px 10px 32px; }
  .header h1 { font-size: 20px; }
  .sector-pair { grid-template-columns: 1fr; }
  section { padding: 12px; }
  .overview-grid { grid-template-columns: 1fr 1fr; }
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
    sector_views = "".join(f"<li>{html.escape(text)}</li>" for text in build_sector_views(snapshot))
    top_html = _sector_table(sectors.get("领涨行业") if isinstance(sectors, dict) else None)
    bottom_html = _sector_table(sectors.get("领跌行业") if isinstance(sectors, dict) else None)
    bottom_label = _sector_label(sectors.get("领跌行业") if isinstance(sectors, dict) else None)
    key_html = _sector_table(sectors.get("重点行业") if isinstance(sectors, dict) else None)
    concepts = snapshot.get("热门概念") or []
    concept_text = _sector_names(concepts, 10) if isinstance(concepts, list) and concepts else "概念板块数据暂缺，可参考上方领涨行业。"
    overview_text = "；".join(_overview_text(snapshot))
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
    <h2 style="margin-top:14px;">A股主要指数</h2>
    {_index_table(snapshot.get("指数"))}
  </section>

  <section>
    <h2>重点指数观察</h2>
    {_key_index_table(snapshot.get("重点指数"))}
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
    <p>{html.escape(concept_text)}</p>
  </section>

  <section>
    <h2>板块观点</h2>
    <ul class="views">{sector_views}</ul>
  </section>

  <section>
    <h2>外盘动向</h2>
    {_global_table(snapshot.get("全球"))}
  </section>

  <section>
    <h2>基金参考（场内ETF）</h2>
    {_etf_table(snapshot.get("ETF"))}
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
    lines += [
        "",
        "## A股主要指数",
    ]
    for row in snapshot.get("指数") or []:
        lines.append(f"- {row.get('名称', '')}：{_fmt(row.get('最新价'))}（{_pct(row.get('涨跌幅'))}）")
    lines += ["", "## 重点指数观察"]
    for row in snapshot.get("重点指数") or []:
        lines.append(f"- {row.get('名称', '')}：{_fmt(row.get('最新价'))}（{_pct(row.get('涨跌幅'))}）")
    lines += ["", "## 主要板块"]
    sectors = snapshot.get("板块") or {}
    if isinstance(sectors, dict):
        lines += ["### 领涨行业"]
        for row in sectors.get("领涨行业") or []:
            lines.append(f"- {row.get('名称', '')}：{_pct(row.get('涨跌幅'))}")
        lines += [f"### {_sector_label(sectors.get('领跌行业'))}"]
        for row in sectors.get("领跌行业") or []:
            lines.append(f"- {row.get('名称', '')}：{_pct(row.get('涨跌幅'))}")
    lines += ["", "## 板块观点"]
    lines.extend(f"- {text}" for text in build_sector_views(snapshot))
    lines += ["", "## 外盘动向"]
    for row in snapshot.get("全球") or []:
        lines.append(f"- {row.get('名称', '')}：{_fmt(row.get('最新价'))}（{_pct(row.get('涨跌幅'))}）")
    lines += ["", "## 基金参考（场内ETF）"]
    for row in snapshot.get("ETF") or []:
        lines.append(f"- {row.get('名称', '')}：{_fmt(row.get('最新价'))}（{_pct(row.get('涨跌幅'))}）")
    lines += ["", "## 基金操作建议", ""]
    lines.extend(f"- {text}" for text in build_advice(snapshot))
    lines += ["", "## 今日观点", "", build_today_view(snapshot)]
    lines += ["", "> 不构成投资建议，市场有风险，投资需谨慎。"]
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
