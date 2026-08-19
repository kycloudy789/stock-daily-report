"""每日工作流主流程。"""

from __future__ import annotations

import json
import logging
import sys
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
    if not dry_run:
        try:
            url = resolve_publish_url(cfg, html_path, WORKSPACE_ROOT, target_date)
            print(f"简报已发布：{url}")
        except Exception as exc:
            LOGGER.exception("发布失败，请检查 gh 登录、仓库与网络。")
            print(f"发布失败：{exc}")

    if not no_push and not dry_run:
        if send_daily_report(cfg, url, summary, target_date, html_content):
            print("微信消息已发送。")
        else:
            print("微信消息未发送：缺少 PushPlus Token。")

    print("--- 简报摘要 ---")
    print(summary)
    return 0
