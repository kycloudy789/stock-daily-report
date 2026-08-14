import tempfile
import unittest
from datetime import date
from pathlib import Path

from src.runner import run_daily


class RunnerTest(unittest.TestCase):
    def test_offline_dry_run_generates_files(self):
        cfg = {
            "时区": "Asia/Shanghai",
            "输出目录": "docs",
            "报告文件名": "index.html",
            "Markdown文件名": "report.md",
            "发布方式": "none",
            "PushPlus Token": "",
            "PushPlus 群组编码": "",
        }
        with tempfile.TemporaryDirectory() as tmp:
            cfg["输出目录"] = str(Path(tmp))
            result = run_daily(
                cfg,
                date(2026, 8, 14),
                dry_run=True,
                no_push=True,
                offline=True,
            )
        self.assertEqual(result, 0)

    def test_non_trading_day_skips(self):
        cfg = {"时区": "Asia/Shanghai", "发布方式": "none"}
        result = run_daily(cfg, date(2026, 8, 15), dry_run=True)
        self.assertEqual(result, 0)


if __name__ == "__main__":
    unittest.main()
