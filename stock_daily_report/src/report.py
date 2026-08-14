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

    advice.append("建议保持组合分散：宽基打底、行业做卫星，单只行业基金不超过权益仓位的 20%，并设置止盈纪律。")
    advice.append("以上为基于公开行情的规则化参考，不构成投资建议；实际决策请结合自身风险承受能力。")
    return advice


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
@media (max-width: 620px) {
  .wrap { padding: 14px 10px 32px; }
  .header h1 { font-size: 20px; }
  .sector-pair { grid-template-columns: 1fr; }
  section { padding: 12px; }
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
    top_html = _sector_table(sectors.get("领涨行业") if isinstance(sectors, dict) else None)
    bottom_html = _sector_table(sectors.get("领跌行业") if isinstance(sectors, dict) else None)
    key_html = _sector_table(sectors.get("重点行业") if isinstance(sectors, dict) else None)
    concepts = snapshot.get("热门概念") or []
    concept_text = _sector_names(concepts, 10) if isinstance(concepts, list) and concepts else "概念板块数据暂缺，可参考上方领涨行业。"

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
    <h1>{html.escape(str(target_date))} 每日股市与基金简报<span class="tag">盘中速览</span></h1>
    <div class="meta">数据截至 {html.escape(source_time)}（北京时间）· 数据来源：{html.escape(_source_text(snapshot))} · {html.escape(recent_text)}</div>
  </div>

  <section>
    <h2>A股主要指数</h2>
    {_index_table(snapshot.get("指数"))}
  </section>

  <section>
    <h2>主要板块</h2>
    <div class="sector-pair">
      <div class="half"><h2 style="font-size:15px;">领涨行业</h2>{top_html}</div>
      <div class="half"><h2 style="font-size:15px;">领跌行业</h2>{bottom_html}</div>
    </div>
    <h2 style="margin-top:16px;">重点关注行业</h2>
    {key_html}
    <h2 style="margin-top:16px;">热门概念</h2>
    <p>{html.escape(concept_text)}</p>
  </section>

  <section>
    <h2>全球市场</h2>
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
        "## A股主要指数",
    ]
    for row in snapshot.get("指数") or []:
        lines.append(f"- {row.get('名称', '')}：{_fmt(row.get('最新价'))}（{_pct(row.get('涨跌幅'))}）")
    lines += ["", "## 主要板块"]
    sectors = snapshot.get("板块") or {}
    if isinstance(sectors, dict):
        lines += ["### 领涨行业"]
        for row in sectors.get("领涨行业") or []:
            lines.append(f"- {row.get('名称', '')}：{_pct(row.get('涨跌幅'))}")
        lines += ["### 领跌行业"]
        for row in sectors.get("领跌行业") or []:
            lines.append(f"- {row.get('名称', '')}：{_pct(row.get('涨跌幅'))}")
    lines += ["", "## 全球市场"]
    for row in snapshot.get("全球") or []:
        lines.append(f"- {row.get('名称', '')}：{_fmt(row.get('最新价'))}（{_pct(row.get('涨跌幅'))}）")
    lines += ["", "## 基金参考（场内ETF）"]
    for row in snapshot.get("ETF") or []:
        lines.append(f"- {row.get('名称', '')}：{_fmt(row.get('最新价'))}（{_pct(row.get('涨跌幅'))}）")
    lines += ["", "## 基金操作建议", ""]
    lines.extend(f"- {text}" for text in build_advice(snapshot))
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
