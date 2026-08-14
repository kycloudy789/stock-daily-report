"""每日股市与基金简报入口脚本。"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import load_config  # noqa: E402
from src.runner import run_daily  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="生成每日 A 股与全球市场简报")
    parser.add_argument("--date", default=None, help="指定日期 YYYY-MM-DD，默认今天")
    parser.add_argument("--force", action="store_true", help="即使非交易日也强制生成")
    parser.add_argument("--dry-run", action="store_true", help="只生成文档，不发布不推送")
    parser.add_argument("--no-push", action="store_true", help="发布文档但不推送微信")
    parser.add_argument("--offline", action="store_true", help="使用样例数据离线生成，不访问网络")
    parser.add_argument("--publish", choices=["github", "local", "none"], default=None, help="覆盖配置中的发布方式")
    args = parser.parse_args()

    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    target_date = datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else now.date()
    cfg = load_config()
    if args.publish:
        cfg["发布方式"] = args.publish

    return run_daily(
        cfg=cfg,
        target_date=target_date,
        force=args.force,
        dry_run=args.dry_run,
        no_push=args.no_push,
        offline=args.offline,
    )


if __name__ == "__main__":
    raise SystemExit(main())
