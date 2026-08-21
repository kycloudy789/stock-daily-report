import json
import unittest
from datetime import date
from pathlib import Path

from src.report import build_advice, build_fund_suggestions, build_html, build_summary


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
        self.assertIn("昨日收盘", html)
        self.assertIn("情绪评价", html)
        self.assertIn("重点科技与医药方向", html)
        self.assertIn("今日基金标的参考", html)
        self.assertIn("近5日", html)
        self.assertNotIn("近一周/近一月", html)

    def test_trend_html_short_range_single_chart(self):
        from src.report import _trend_html

        rows5 = [
            {"日期": f"2026-08-{10 + i:02d}", "收盘价": 3000.0 + i * 10}
            for i in range(5)
        ]
        snapshot = {"走势": {"上证指数": {"明细": rows5}}}
        html_short = _trend_html(snapshot, "上证指数")
        self.assertIn("近5日", html_short)
        self.assertNotIn("近一周", html_short)
        self.assertEqual(html_short.count("<svg"), 1)

        rows_long = rows5 + [
            {"日期": f"2026-09-{i + 1:02d}", "收盘价": 3100.0 + i * 5}
            for i in range(20)
        ]
        snapshot_long = {"走势": {"上证指数": {"明细": rows_long}}}
        html_long = _trend_html(snapshot_long, "上证指数")
        self.assertIn("近一周", html_long)
        self.assertIn("近一月", html_long)
        self.assertEqual(html_long.count("<svg"), 2)

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
        self.assertIn("市场情绪：", summary)

    def test_turnover_assessment_five_levels(self):
        from src.report import _turnover_assessment

        cases = [
            (
                {
                    "两市成交额": 18000e8,
                    "上涨家数": 4000,
                    "下跌家数": 1000,
                    "涨停家数": 80,
                    "跌停家数": 5,
                },
                "很强",
            ),
            (
                {
                    "两市成交额": 13000e8,
                    "上涨家数": 2600,
                    "下跌家数": 2400,
                },
                "强",
            ),
            (
                {
                    "两市成交额": 11000e8,
                    "上涨家数": 2500,
                    "下跌家数": 2500,
                },
                "一般",
            ),
            (
                {
                    "两市成交额": 9000e8,
                    "上涨家数": 2500,
                    "下跌家数": 2500,
                },
                "弱",
            ),
            (
                {
                    "两市成交额": 5000e8,
                    "上涨家数": 1000,
                    "下跌家数": 4000,
                    "跌停家数": 40,
                },
                "很弱",
            ),
        ]
        for summary, expected in cases:
            text = _turnover_assessment(summary)
            self.assertTrue(text.startswith(expected + "。"), text)

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

    def test_fund_suggestions_include_tech_and_medicine(self):
        suggestions = build_fund_suggestions(self.snapshot)
        joined = "".join(suggestions)
        self.assertTrue(suggestions)
        self.assertIn("科创50ETF", joined)
        self.assertIn("医药ETF", joined)
        self.assertTrue(any("近一周" in text for text in suggestions))


if __name__ == "__main__":
    unittest.main()
