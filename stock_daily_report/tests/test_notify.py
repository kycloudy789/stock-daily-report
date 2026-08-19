import unittest
from datetime import date
from unittest.mock import patch

from src.notify import send_daily_report, send_pushplus


class NotifyTest(unittest.TestCase):
    def test_send_daily_report_payload(self):
        cfg = {"PushPlus Token": "test-token", "PushPlus 群组编码": ""}
        captured = {}

        def fake_post(url, json=None, timeout=None):
            captured["url"] = url
            captured["payload"] = json

            class FakeResp:
                def raise_for_status(self):
                    return None

                def json(self):
                    return {"code": 200, "msg": "成功"}

            return FakeResp()

        with patch("src.notify.requests.post", side_effect=fake_post):
            result = send_daily_report(
                cfg,
                "https://example.com/report",
                "摘要内容",
                date(2026, 8, 14),
            )

        self.assertTrue(result)
        self.assertEqual(captured["payload"]["token"], "test-token")
        self.assertIn("点击查看今日股市与基金简报", captured["payload"]["content"])
        self.assertIn("https://example.com/report", captured["payload"]["content"])
        self.assertEqual(captured["payload"]["template"], "html")

    def test_missing_token_returns_false(self):
        cfg = {"PushPlus Token": "", "PushPlus 群组编码": ""}
        with patch("src.notify.requests.post") as fake_post:
            result = send_daily_report(cfg, "https://example.com", "摘要", date(2026, 8, 14))
        self.assertFalse(result)
        fake_post.assert_not_called()

    def test_send_daily_report_with_full_html(self):
        cfg = {"PushPlus Token": "test-token", "PushPlus 群组编码": ""}
        html_content = (
            "<!-- CSS_START --><style>.wrap{}</style><!-- CSS_END -->"
            "<!-- BODY_START --><div class=\"wrap\">完整报告正文</div><!-- BODY_END -->"
        )
        captured = {}

        def fake_post(url, json=None, timeout=None):
            captured["payload"] = json

            class FakeResp:
                def raise_for_status(self):
                    return None

                def json(self):
                    return {"code": 200, "msg": "成功"}

            return FakeResp()

        with patch("src.notify.requests.post", side_effect=fake_post):
            result = send_daily_report(
                cfg,
                "https://example.com/report",
                "摘要内容",
                date(2026, 8, 14),
                html_content,
            )

        self.assertTrue(result)
        self.assertIn("完整报告正文", captured["payload"]["content"])
        self.assertIn("网页版存档链接", captured["payload"]["content"])

    def test_send_pushplus_retries_then_success(self):
        counts = {"n": 0}

        def flaky_post(url, json=None, timeout=None):
            counts["n"] += 1
            if counts["n"] < 3:
                raise RuntimeError("临时网络故障")

            class FakeResp:
                def raise_for_status(self):
                    return None

                def json(self):
                    return {"code": 200, "msg": "成功"}

            return FakeResp()

        with patch("src.notify.requests.post", side_effect=flaky_post), patch(
            "src.notify.time.sleep"
        ) as mock_sleep:
            result = send_pushplus("test-token", "标题", "内容")

        self.assertTrue(result)
        self.assertEqual(counts["n"], 3)
        mock_sleep.assert_called()

    def test_send_daily_report_push_failure_returns_false(self):
        cfg = {"PushPlus Token": "test-token", "PushPlus 群组编码": ""}

        def fail_post(url, json=None, timeout=None):
            raise RuntimeError("PushPlus 服务不可用")

        with patch("src.notify.requests.post", side_effect=fail_post), patch(
            "src.notify.time.sleep"
        ) as mock_sleep:
            result = send_daily_report(
                cfg,
                "https://example.com/report",
                "摘要内容",
                date(2026, 8, 14),
            )

        self.assertFalse(result)
        self.assertGreaterEqual(mock_sleep.call_count, 2)


if __name__ == "__main__":
    unittest.main()
