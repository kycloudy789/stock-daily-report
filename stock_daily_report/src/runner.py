"""每日工作流主流程。"""

from __future__ import annotations

import json
import logging
import sys
import time
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .ai_analyst import run_ai_analyst
from .calendar import is_trading_day, load_holidays
from .eastmoney import build_market_snapshot
from .notify import send_daily_report
from .publish import resolve_publish_url
from .report import build_summary, write_reports

LOGGER = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE_ROOT = PROJECT_ROOT.parent


def _seconds_until(wait_at: str | None, now: datetime, target_date: date) -> float | None:
    """计算距目标时刻的剩余秒数；跨日、格式非法或已过时不等待。"""
    if not wait_at or now.date() != target_date:
        return None
    try:
        hour_s, minute_s = wait_at.split(":", 1)
        target = now.replace(hour=int(hour_s), minute=int(minute_s), second=0, microsecond=0)
    except ValueError:
        return None
    delta = (target - now).total_seconds()
    if delta <= 0:
        return None
    return delta


def _sleep_until(wait_at: str | None, tz: ZoneInfo, target_date: date, label: str) -> None:
    """在工作流排队时间不确定时，把关键动作锁到目标时刻附近。"""
    now = datetime.now(tz)
    delta = _seconds_until(wait_at, now, target_date)
    if delta is None:
        return
    print(f"等待到 {wait_at}（约 {delta / 60:.1f} 分钟）后再{label}，以贴近目标送达时间。")
    time.sleep(delta)


def _load_sample(snapshot: dict, target_date: date) -> dict:
    sample_path = PROJECT_ROOT / "sample_data" / "sample_market.json"
    if sample_path.exists():
        data = json.loads(sample_path.read_text(encoding="utf-8"))
        data["日期"] = target_date.isoformat()
        snapshot.update(data)
    return snapshot


def run_daily(
    cfg: dict,
    target_date: date,
    force: bool = False,
    dry_run: bool = False,
    no_push: bool = False,
    offline: bool = False,
    collect_after: str | None = None,
    push_after: str | None = None,
) -> int:
    """执行采集、生成、发布与推送。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    holidays = load_holidays()
    if not force and not is_trading_day(target_date, holidays):
        print(f"{target_date.isoformat()} 不是 A 股交易日，本次任务跳过。")
        return 0

    tz = ZoneInfo(str(cfg.get("时区") or "Asia/Shanghai"))
    if not offline and not dry_run:
        _sleep_until(collect_after, tz, target_date, "采集行情")
    source_time = datetime.now(tz).strftime("%Y-%m-%d %H:%M")

    if offline:
        snapshot: dict = {}
        _load_sample(snapshot, target_date)
        print("离线模式：使用样例数据生成简报。")
        snapshot["分析师"] = {
            "enabled": False,
            "ready": False,
            "model": "",
            "provider": "",
            "advice": [],
            "funds": [],
            "today_view": "",
            "risk": "",
            "error": "离线模式跳过 AI 分析师",
            "generated_at": source_time,
        }
    else:
        snapshot = build_market_snapshot()
        snapshot["分析师"] = run_ai_analyst(snapshot, target_date, source_time, cfg)

    output_value = Path(str(cfg.get("输出目录") or "docs"))
    output_dir = output_value if output_value.is_absolute() else WORKSPACE_ROOT / output_value
    html_path = write_reports(cfg, snapshot, target_date, source_time, output_dir)
    print(f"简报已生成：{html_path}")
    html_content = html_path.read_text(encoding="utf-8")

    summary = build_summary(snapshot, target_date)
    url = None
    publish_failed = False
    if not dry_run:
        try:
            url = resolve_publish_url(cfg, html_path, WORKSPACE_ROOT, target_date)
            print(f"简报已发布：{url}")
        except Exception as exc:
            LOGGER.exception("发布失败，请检查 gh 登录、仓库与网络。")
            print(f"发布失败：{exc}")
            publish_failed = True

    if not no_push and not dry_run:
        _sleep_until(push_after, tz, target_date, "推送微信")
        if send_daily_report(cfg, url, summary, target_date, html_content):
            print("微信消息已发送。")
        else:
            print("微信消息推送失败：请检查 PushPlus Token 与网络；本次任务将标记为失败。")
            if publish_failed:
                print("本次任务同时存在发布失败，运行结论：发布与推送均异常。")
            return 2
    if publish_failed:
        return 1

    print("--- 简报摘要 ---")
    print(summary)
    return 0


def run_verify_ai(cfg: dict, target_date: date) -> int:
    """只验证 AI 分析师接口：用样例行情调用一次真实接口，不生成报告、不发布、不推送。"""
    tz = ZoneInfo(str(cfg.get("时区") or "Asia/Shanghai"))
    source_time = datetime.now(tz).strftime("%Y-%m-%d %H:%M")
    snapshot: dict = {}
    _load_sample(snapshot, target_date)
    result = run_ai_analyst(snapshot, target_date, source_time, cfg)

    print("--- AI 分析师验证 ---")
    print(f"启用: {result.get('enabled')}")
    print(f"模型: {result.get('model')}（{result.get('provider')}）")
    if not result.get("enabled"):
        print("未配置 API Key，跳过真实调用。按说明配置后再验证。")
        return 0
    if result.get("error"):
        print(f"状态: {result['error']}")
    print(f"就绪: {result.get('ready')}")
    for key, title in (
        ("advice", "投资建议"),
        ("funds", "基金参考"),
    ):
        items = result.get(key) or []
        print(f"{title}（{len(items)} 条）:")
        for line in items:
            print("- " + str(line))
    if result.get("today_view"):
        print("今日观点:", result["today_view"])
    if result.get("risk"):
        print("风险提示:", result["risk"])
    return 0 if result.get("ready") else 1
