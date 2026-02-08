"""
市场数据模块的单元测试
"""

import pandas as pd
import pytest

from quant_agent.data.market_data import MarketDataProvider


@pytest.fixture
def provider():
    return MarketDataProvider(source="synthetic")


class TestMarketDataProvider:
    def test_get_data(self, provider):
        data = provider.get_data("000001.SZ", "2024-01-01", "2024-06-30")
        assert isinstance(data, pd.DataFrame)
        assert len(data) > 0
        assert "open" in data.columns
        assert "high" in data.columns
        assert "low" in data.columns
        assert "close" in data.columns
        assert "volume" in data.columns

    def test_data_consistency(self, provider):
        """同一symbol应生成相同数据。"""
        data1 = provider.get_data("000001.SZ", "2024-01-01", "2024-06-30")
        provider.clear_cache()
        data2 = provider.get_data("000001.SZ", "2024-01-01", "2024-06-30")
        pd.testing.assert_frame_equal(data1, data2)

    def test_different_symbols_different_data(self, provider):
        data1 = provider.get_data("000001.SZ", "2024-01-01", "2024-06-30")
        data2 = provider.get_data("600519.SH", "2024-01-01", "2024-06-30")
        # 不同symbol的数据应不同
        assert not data1["close"].equals(data2["close"])

    def test_ohlc_consistency(self, provider):
        """high >= open, close; low <= open, close。"""
        data = provider.get_data("test_symbol", "2024-01-01", "2024-06-30")
        assert (data["high"] >= data["open"]).all()
        assert (data["high"] >= data["close"]).all()
        assert (data["low"] <= data["open"]).all()
        assert (data["low"] <= data["close"]).all()

    def test_volume_positive(self, provider):
        data = provider.get_data("test_symbol", "2024-01-01", "2024-06-30")
        assert (data["volume"] > 0).all()

    def test_caching(self, provider):
        data1 = provider.get_data("000001.SZ", "2024-01-01", "2024-06-30")
        data2 = provider.get_data("000001.SZ", "2024-01-01", "2024-06-30")
        pd.testing.assert_frame_equal(data1, data2)

    def test_cache_returns_copy(self, provider):
        data1 = provider.get_data("000001.SZ", "2024-01-01", "2024-06-30")
        data2 = provider.get_data("000001.SZ", "2024-01-01", "2024-06-30")
        # 修改data1不应影响data2
        data1.iloc[0, 0] = -999
        assert data2.iloc[0, 0] != -999

    def test_get_multiple_data(self, provider):
        symbols = ["000001.SZ", "600519.SH"]
        result = provider.get_multiple_data(symbols, "2024-01-01", "2024-06-30")
        assert len(result) == 2
        assert "000001.SZ" in result
        assert "600519.SH" in result

    def test_clear_cache(self, provider):
        provider.get_data("000001.SZ", "2024-01-01", "2024-06-30")
        assert len(provider._cache) > 0
        provider.clear_cache()
        assert len(provider._cache) == 0

    def test_unsupported_source(self):
        provider = MarketDataProvider(source="unknown")
        with pytest.raises(ValueError, match="不支持的数据源"):
            provider.get_data("test", "2024-01-01", "2024-06-30")

    def test_csv_not_found(self):
        provider = MarketDataProvider(source="csv")
        with pytest.raises(FileNotFoundError):
            provider.get_data("nonexistent", "2024-01-01", "2024-06-30")
