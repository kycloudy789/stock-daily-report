import unittest
from unittest.mock import patch

from src.eastmoney import _fallback_global_quotes


class FallbackSourceTest(unittest.TestCase):
    def test_global_fallback_merges_nikkei_and_kospi(self):
        def tencent_fail():
            raise RuntimeError("腾讯全球失败")

        sina_rows = [{"名称": "日经225", "代码": "N225", "最新价": 44946.64, "涨跌幅": -0.90}]
        kospi_row = {"名称": "韩国KOSPI", "代码": "KS11", "最新价": 6920.88, "涨跌幅": 1.58}
        with patch("src.eastmoney.get_tencent_global_quotes", side_effect=tencent_fail), \
             patch("src.eastmoney.get_sina_global_quotes", return_value=sina_rows), \
             patch("src.eastmoney.get_kospi_quote", return_value=kospi_row):
            rows = _fallback_global_quotes()

        names = [row["名称"] for row in rows]
        self.assertIn("日经225", names)
        self.assertIn("韩国KOSPI", names)
        self.assertEqual(rows[-1]["最新价"], 6920.88)

    def test_global_fallback_raises_when_all_fail(self):
        def fail():
            raise RuntimeError("不可用")

        with patch("src.eastmoney.get_tencent_global_quotes", side_effect=fail), \
             patch("src.eastmoney.get_sina_global_quotes", side_effect=fail), \
             patch("src.eastmoney.get_kospi_quote", side_effect=fail):
            with self.assertRaises(RuntimeError):
                _fallback_global_quotes()


class NaverQuoteTest(unittest.TestCase):
    def test_parse_kospi_payload(self):
        payload = [
            {
                "localTradedAt": "2026-08-14",
                "closePrice": "6,920.88",
                "compareToPreviousClosePrice": "107.54",
                "fluctuationsRatio": "1.58",
            }
        ]
        raw = __import__("json").dumps(payload).encode("utf-8")
        with patch("src.naver._curl_bytes", return_value=raw):
            from src.naver import get_kospi_quote
            row = get_kospi_quote()
        self.assertEqual(row["名称"], "韩国KOSPI")
        self.assertEqual(row["最新价"], 6920.88)
        self.assertEqual(row["涨跌幅"], 1.58)


class SinaGlobalQuoteTest(unittest.TestCase):
    def test_parse_nikkei_line(self):
        text = 'var hq_str_int_nikkei="日经指数,44946.64,-408.35,-0.90";'
        with patch("src.sina._curl_bytes", return_value=text.encode("gbk")):
            from src.sina import get_sina_global_quotes
            rows = get_sina_global_quotes()
        names = [row["名称"] for row in rows]
        self.assertIn("日经225", names)
        nikkei = next(row for row in rows if row["名称"] == "日经225")
        self.assertEqual(nikkei["涨跌幅"], -0.90)


if __name__ == "__main__":
    unittest.main()
