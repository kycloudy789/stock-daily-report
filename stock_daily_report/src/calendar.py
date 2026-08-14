"""A股交易日历：周末与法定节假日判断。"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Set


def load_holidays(path: Path | None = None) -> Set[str]:
    """读取节假日配置，返回格式为 YYYY-MM-DD 的日期字符串集合。"""
    path = path or Path(__file__).resolve().parent.parent / "holidays.json"
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    result: Set[str] = set()
    for year, days in data.items():
        if not year.isdigit():
            continue
        if isinstance(days, list):
            result.update(str(day) for day in days)
    return result


def is_trading_day(day: date, holidays: Set[str] | None = None) -> bool:
    """判断某一天是否为 A 股交易日。"""
    if day.weekday() >= 5:
        return False
    holidays = holidays if holidays is not None else load_holidays()
    return day.isoformat() not in holidays
