"""
时区与交易时间管理模块的单元测试
"""

from datetime import datetime, timezone, timedelta
import pytest

from quant_agent.utils.timezone import (
    BEIJING_TZ,
    now_beijing,
    beijing_str,
    is_trading_day,
    is_trading_hours,
    get_market_status,
)


class TestBeijingTime:
    def test_now_beijing_has_timezone(self):
        dt = now_beijing()
        assert dt.tzinfo is not None
        assert dt.utcoffset() == timedelta(hours=8)

    def test_beijing_str_format(self):
        s = beijing_str()
        # 格式应为 YYYY-MM-DD HH:MM:SS
        assert len(s) == 19
        parts = s.split(" ")
        assert len(parts) == 2
        assert len(parts[0].split("-")) == 3
        assert len(parts[1].split(":")) == 3

    def test_beijing_str_custom_format(self):
        s = beijing_str("%Y%m%d")
        assert len(s) == 8

    def test_timezone_offset(self):
        assert BEIJING_TZ.utcoffset(None) == timedelta(hours=8)


class TestTradingDay:
    def test_monday_is_trading_day(self):
        # 2024-01-08 是周一
        dt = datetime(2024, 1, 8, 10, 0, tzinfo=BEIJING_TZ)
        assert is_trading_day(dt) is True

    def test_friday_is_trading_day(self):
        # 2024-01-12 是周五
        dt = datetime(2024, 1, 12, 10, 0, tzinfo=BEIJING_TZ)
        assert is_trading_day(dt) is True

    def test_saturday_not_trading_day(self):
        # 2024-01-13 是周六
        dt = datetime(2024, 1, 13, 10, 0, tzinfo=BEIJING_TZ)
        assert is_trading_day(dt) is False

    def test_sunday_not_trading_day(self):
        # 2024-01-14 是周日
        dt = datetime(2024, 1, 14, 10, 0, tzinfo=BEIJING_TZ)
        assert is_trading_day(dt) is False


class TestTradingHours:
    def test_morning_session(self):
        # 周一上午 10:00 = 交易时间
        dt = datetime(2024, 1, 8, 10, 0, tzinfo=BEIJING_TZ)
        assert is_trading_hours(dt) is True

    def test_morning_open(self):
        # 09:30 = 刚开盘
        dt = datetime(2024, 1, 8, 9, 30, tzinfo=BEIJING_TZ)
        assert is_trading_hours(dt) is True

    def test_morning_close(self):
        # 11:30 = 上午收盘
        dt = datetime(2024, 1, 8, 11, 30, tzinfo=BEIJING_TZ)
        assert is_trading_hours(dt) is True

    def test_afternoon_session(self):
        # 下午 14:00 = 交易时间
        dt = datetime(2024, 1, 8, 14, 0, tzinfo=BEIJING_TZ)
        assert is_trading_hours(dt) is True

    def test_afternoon_close(self):
        # 15:00 = 下午收盘
        dt = datetime(2024, 1, 8, 15, 0, tzinfo=BEIJING_TZ)
        assert is_trading_hours(dt) is True

    def test_before_market(self):
        # 08:00 = 盘前
        dt = datetime(2024, 1, 8, 8, 0, tzinfo=BEIJING_TZ)
        assert is_trading_hours(dt) is False

    def test_lunch_break(self):
        # 12:00 = 午休
        dt = datetime(2024, 1, 8, 12, 0, tzinfo=BEIJING_TZ)
        assert is_trading_hours(dt) is False

    def test_after_market(self):
        # 16:00 = 收盘后
        dt = datetime(2024, 1, 8, 16, 0, tzinfo=BEIJING_TZ)
        assert is_trading_hours(dt) is False

    def test_weekend_never_trading(self):
        # 周六 10:00 也不算交易时间
        dt = datetime(2024, 1, 13, 10, 0, tzinfo=BEIJING_TZ)
        assert is_trading_hours(dt) is False

    def test_just_before_open(self):
        # 09:29 = 未开盘
        dt = datetime(2024, 1, 8, 9, 29, tzinfo=BEIJING_TZ)
        assert is_trading_hours(dt) is False

    def test_just_after_close(self):
        # 15:01 = 已收盘
        dt = datetime(2024, 1, 8, 15, 1, tzinfo=BEIJING_TZ)
        assert is_trading_hours(dt) is False


class TestMarketStatus:
    def test_weekend(self):
        dt = datetime(2024, 1, 13, 10, 0, tzinfo=BEIJING_TZ)
        status = get_market_status(dt)
        assert "休市" in status
        assert "周六" in status

    def test_before_open(self):
        dt = datetime(2024, 1, 8, 8, 0, tzinfo=BEIJING_TZ)
        status = get_market_status(dt)
        assert "盘前" in status or "未开盘" in status

    def test_morning_trading(self):
        dt = datetime(2024, 1, 8, 10, 0, tzinfo=BEIJING_TZ)
        status = get_market_status(dt)
        assert "交易中" in status
        assert "上午" in status

    def test_lunch_break(self):
        dt = datetime(2024, 1, 8, 12, 0, tzinfo=BEIJING_TZ)
        status = get_market_status(dt)
        assert "午间" in status

    def test_afternoon_trading(self):
        dt = datetime(2024, 1, 8, 14, 0, tzinfo=BEIJING_TZ)
        status = get_market_status(dt)
        assert "交易中" in status
        assert "下午" in status

    def test_after_close(self):
        dt = datetime(2024, 1, 8, 16, 0, tzinfo=BEIJING_TZ)
        status = get_market_status(dt)
        assert "收盘" in status
