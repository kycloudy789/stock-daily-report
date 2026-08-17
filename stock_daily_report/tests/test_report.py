import json
import unittest
from datetime import date
from pathlib import Path

from src.report import build_advice, build_html, build_summary


class ReportTest(unittest.TestCase):
    def setUp(self):
        sample = Path(__file__).resolve().parent.parent / "sample_data" / "sample_market.json"
        self.snapshot = json.loads(sample.read_text(encoding="utf-8"))

    def test_html_contains_key_sections(self):
        html = build_html(self.snapshot, date(2026, 8, 14), "2026-08-14 14:00")
        self.assertIn("市场概览", html)
        self.assertIn("A股主要指数", html)
        self.assertIn("重点指数观察", html)
        self.assertIn("主要板块", html)
        self.assertIn("板块观点", html)
        self.assertIn("外盘动向", html)
        self.assertIn("基金操作建议", html)
        self.assertIn("今日观点", html)
        self.assertIn("韩国KOSPI", html)
        self.assertIn("半导体", html)
        self.assertIn("两市成交额", html)
        self.assertIn("恒生科技", html)

    def test_advice_generates_fund_tips(self):
        advice = build_advice(self.snapshot)
        self.assertTrue(advice)
        self.assertTrue(any("定投" in text for text in advice))
        self.assertTrue(any("不构成投资建议" in text for text in advice))

    def test_summary_contains_core_numbers(self):
        summary = build_summary(self.snapshot, date(2026, 8, 14))
        self.assertIn("上证指数", summary)
        self.assertIn("创业板指", summary)
        self.assertIn("主要板块", summary)
        self.assertIn("基金建议", summary)

    def test_html_contains_dynamic_sources(self):
        snapshot = dict(self.snapshot)
        snapshot["来源"] = {
            "指数": "东方财富",
            "全球": "腾讯/新浪/Naver",
            "ETF": "腾讯",
            "板块": "新浪",
            "热门概念": "新浪行业替代",
            "近期": "腾讯",
        }
        html = build_html(snapshot, date(2026, 8, 14), "2026-08-14 14:00")
        self.assertIn("东方财富", html)
        self.assertIn("腾讯/新浪/Naver", html)


if __name__ == "__main__":
    unittest.main()
