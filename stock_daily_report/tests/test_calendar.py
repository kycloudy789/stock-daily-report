import unittest
from datetime import date

from src.calendar import is_trading_day, load_holidays


class CalendarTest(unittest.TestCase):
    def setUp(self):
        self.holidays = load_holidays()

    def test_weekday_is_trading_day(self):
        self.assertTrue(is_trading_day(date(2026, 8, 14), self.holidays))

    def test_weekend_is_not_trading_day(self):
        self.assertFalse(is_trading_day(date(2026, 8, 15), self.holidays))
        self.assertFalse(is_trading_day(date(2026, 8, 16), self.holidays))

    def test_national_day_is_not_trading_day(self):
        self.assertFalse(is_trading_day(date(2026, 10, 1), self.holidays))
        self.assertFalse(is_trading_day(date(2026, 10, 7), self.holidays))
        self.assertTrue(is_trading_day(date(2026, 10, 8), self.holidays))

    def test_spring_festival_is_not_trading_day(self):
        self.assertFalse(is_trading_day(date(2026, 2, 18), self.holidays))
        self.assertTrue(is_trading_day(date(2026, 2, 24), self.holidays))


if __name__ == "__main__":
    unittest.main()
