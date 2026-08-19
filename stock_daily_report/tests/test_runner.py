import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from src.runner import _seconds_until, run_daily, run_verify_ai


class RunnerTest(unittest.TestCase):
    def test_seconds_until_waiting_same_day(self):
        tz = ZoneInfo("Asia/Shanghai")
        now = datetime(2026, 8, 19, 13, 30, 0, tzinfo=tz)
        delta = _seconds_until("13:45", now, date(2026, 8, 19))
        self.assertIsNotNone(delta)
        self.assertAlmostEqual(delta, 900, delta=1)

    def test_seconds_until_past_or_wrong_day_returns_none(self):
        tz = ZoneInfo("Asia/Shanghai")
        now = datetime(2026, 8, 19, 14, 5, 0, tzinfo=tz)
        self.assertIsNone(_seconds_until("14:00", now, date(2026, 8, 19)))
        self.assertIsNone(_seconds_until("14:00", now, date(2026, 8, 20)))
        self.assertIsNone(_seconds_until("bad-time", now, date(2026, 8, 19)))
        self.assertIsNone(_seconds_until("", now, date(2026, 8, 19)))
        self.assertIsNone(_seconds_until(None, now, date(2026, 8, 19)))

    def test_sleep_until_waits_then_returns(self):
        tz = ZoneInfo("Asia/Shanghai")
        now = datetime(2026, 8, 19, 13, 45, 0, tzinfo=tz)
        with patch("src.runner.time.sleep") as mock_sleep:
            from src.runner import _sleep_until

            with patch("src.runner.datetime") as mock_dt:
                mock_dt.now.return_value = now
                _sleep_until("13:46", tz, date(2026, 8, 19), "采集行情")
        mock_sleep.assert_called_once()

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

    def test_push_failure_returns_nonzero(self):
        cfg = {
            "时区": "Asia/Shanghai",
            "输出目录": "docs",
            "报告文件名": "index.html",
            "Markdown文件名": "report.md",
            "发布方式": "none",
            "PushPlus Token": "test-token",
            "PushPlus 群组编码": "",
        }
        with tempfile.TemporaryDirectory() as tmp:
            cfg["输出目录"] = str(Path(tmp))
            with patch("src.runner.send_daily_report", return_value=False):
                result = run_daily(
                    cfg,
                    date(2026, 8, 14),
                    dry_run=False,
                    no_push=False,
                    offline=True,
                )
        self.assertEqual(result, 2)

    def test_verify_ai_without_key_returns_zero(self):
        cfg = {"时区": "Asia/Shanghai", "AI 分析师 API Key": ""}
        result = run_verify_ai(cfg, date(2026, 8, 14))
        self.assertEqual(result, 0)

    def test_verify_ai_ready_returns_zero(self):
        cfg = {"时区": "Asia/Shanghai", "AI 分析师 API Key": "sk-test"}
        ready = {
            "enabled": True,
            "ready": True,
            "model": "deepseek-chat",
            "provider": "https://api.deepseek.com",
            "advice": ["保持宽基定投节奏"],
            "funds": ["沪深300ETF（510300）：宽基打底"],
            "today_view": "今日市场震荡。",
            "risk": "注意控制仓位。",
            "error": "",
        }
        with patch("src.runner.run_ai_analyst", return_value=ready):
            result = run_verify_ai(cfg, date(2026, 8, 14))
        self.assertEqual(result, 0)

    def test_verify_ai_failure_returns_nonzero(self):
        cfg = {"时区": "Asia/Shanghai", "AI 分析师 API Key": "sk-test"}
        failed = {
            "enabled": True,
            "ready": False,
            "model": "deepseek-chat",
            "provider": "https://api.deepseek.com",
            "advice": [],
            "funds": [],
            "today_view": "",
            "risk": "",
            "error": "调用失败：模拟错误",
        }
        with patch("src.runner.run_ai_analyst", return_value=failed):
            result = run_verify_ai(cfg, date(2026, 8, 14))
        self.assertEqual(result, 1)


if __name__ == "__main__":
    unittest.main()
