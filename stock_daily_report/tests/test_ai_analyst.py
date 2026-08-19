import json
import unittest
from datetime import date
from pathlib import Path

from src.ai_analyst import _filter_funds, parse_analysis, run_ai_analyst
from src.report import (
    _advice_source_notice,
    build_advice,
    build_fund_suggestions,
    build_html,
    build_today_view,
)


class AiAnalystTest(unittest.TestCase):
    def setUp(self):
        sample = Path(__file__).resolve().parent.parent / "sample_data" / "sample_market.json"
        self.snapshot = json.loads(sample.read_text(encoding="utf-8"))

    def test_no_key_returns_disabled_quickly(self):
        cfg = {"AI 分析师 API Key": ""}
        result = run_ai_analyst(self.snapshot, date(2026, 8, 18), "2026-08-18 14:05", cfg)
        self.assertFalse(result["enabled"])
        self.assertFalse(result["ready"])
        self.assertIn("未配置", result["error"])

    def test_parse_analysis_handles_code_fence_and_chinese_json(self):
        content = (
            '```json\n{"投资建议": ["建议一", "建议二"], '
            '"基金参考": ["医药ETF（512010）：理由"], '
            '"今日观点": "今日震荡", "风险提示": "注意回调"}\n```'
        )
        parsed = parse_analysis(content)
        self.assertEqual(parsed["advice"], ["建议一", "建议二"])
        self.assertIn("医药ETF", parsed["funds"][0])
        self.assertEqual(parsed["today_view"], "今日震荡")

    def test_filter_funds_removes_hallucinated(self):
        snapshot = {"ETF": [{"名称": "半导体ETF", "代码": "512760"}]}
        funds = ["半导体ETF（512760）：跟踪方向", "不存在基金（999999）：编造"]
        kept = _filter_funds(funds, snapshot)
        self.assertEqual(kept, ["半导体ETF（512760）：跟踪方向"])

    def test_advice_prefers_ai_when_ready(self):
        analyst = {
            "enabled": True,
            "ready": True,
            "model": "deepseek-chat",
            "provider": "https://api.deepseek.com",
            "advice": ["AI 建议：周末再平衡"],
            "funds": ["半导体ETF（512760）：行业走强"],
            "today_view": "AI 今日观点",
            "risk": "注意科技板块回调",
            "generated_at": "2026-08-18 14:05",
        }
        snapshot = dict(self.snapshot)
        snapshot["分析师"] = analyst
        advice = build_advice(snapshot)
        self.assertIn("AI 建议", advice[0])
        self.assertIn("注意科技板块回调", advice)
        self.assertEqual(build_today_view(snapshot), "AI 今日观点")
        self.assertIn("半导体ETF", build_fund_suggestions(snapshot)[0])
        html = build_html(snapshot, date(2026, 8, 18), "2026-08-18 14:05")
        self.assertIn("deepseek-chat", html)

    def test_advice_falls_back_without_analyst(self):
        advice = build_advice(self.snapshot)
        self.assertTrue(advice)
        self.assertTrue(any("不构成投资建议" in text for text in advice))
        self.assertNotIn("AI 分析师", advice[0])
        notice = _advice_source_notice(self.snapshot, "基金操作建议")
        self.assertIn("系统规则", notice)
        self.assertIn("基金操作建议", notice)


if __name__ == "__main__":
    unittest.main()
