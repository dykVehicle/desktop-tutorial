"""
技术指标模块的单元测试
"""

import numpy as np
import pandas as pd
import pytest

from quant_agent.data.indicators import TechnicalIndicators


@pytest.fixture
def sample_price_series():
    """生成一个简单的价格序列用于测试。"""
    np.random.seed(42)
    prices = 100 + np.cumsum(np.random.randn(100) * 0.5)
    return pd.Series(prices, name="close")


@pytest.fixture
def sample_ohlcv_df():
    """生成一个完整的OHLCV DataFrame。"""
    np.random.seed(42)
    n = 100
    close = 100 + np.cumsum(np.random.randn(n) * 0.5)
    high = close + np.abs(np.random.randn(n) * 0.5)
    low = close - np.abs(np.random.randn(n) * 0.5)
    open_price = close + np.random.randn(n) * 0.3
    volume = np.random.randint(100000, 1000000, n)

    dates = pd.bdate_range(start="2024-01-01", periods=n)
    return pd.DataFrame(
        {
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        },
        index=dates,
    )


class TestSMA:
    def test_sma_basic(self, sample_price_series):
        sma = TechnicalIndicators.sma(sample_price_series, 10)
        assert len(sma) == len(sample_price_series)
        # 前9个值应为NaN
        assert sma.iloc[:9].isna().all()
        # 第10个值应等于前10个价格的平均值
        expected = sample_price_series.iloc[:10].mean()
        assert abs(sma.iloc[9] - expected) < 1e-10

    def test_sma_period_1(self, sample_price_series):
        sma = TechnicalIndicators.sma(sample_price_series, 1)
        # period=1时，SMA就是原始值
        pd.testing.assert_series_equal(sma, sample_price_series)


class TestEMA:
    def test_ema_basic(self, sample_price_series):
        ema = TechnicalIndicators.ema(sample_price_series, 10)
        assert len(ema) == len(sample_price_series)
        # EMA不应有NaN（adjust=False）
        assert not ema.isna().any()

    def test_ema_vs_sma_convergence(self, sample_price_series):
        """对于常数序列，EMA应等于该常数。"""
        constant_series = pd.Series([100.0] * 50)
        ema = TechnicalIndicators.ema(constant_series, 10)
        assert abs(ema.iloc[-1] - 100.0) < 1e-10


class TestRSI:
    def test_rsi_range(self, sample_price_series):
        rsi = TechnicalIndicators.rsi(sample_price_series, 14)
        valid_rsi = rsi.dropna()
        assert (valid_rsi >= 0).all()
        assert (valid_rsi <= 100).all()

    def test_rsi_uptrend(self):
        """持续上涨时RSI应接近100。"""
        prices = pd.Series(range(100, 200))
        rsi = TechnicalIndicators.rsi(prices, 14)
        assert rsi.iloc[-1] > 90

    def test_rsi_downtrend(self):
        """持续下跌时RSI应接近0。"""
        prices = pd.Series(range(200, 100, -1))
        rsi = TechnicalIndicators.rsi(prices, 14)
        assert rsi.iloc[-1] < 10


class TestMACD:
    def test_macd_basic(self, sample_price_series):
        macd_line, signal_line, histogram = TechnicalIndicators.macd(
            sample_price_series, 12, 26, 9
        )
        assert len(macd_line) == len(sample_price_series)
        assert len(signal_line) == len(sample_price_series)
        assert len(histogram) == len(sample_price_series)

    def test_macd_histogram_is_difference(self, sample_price_series):
        macd_line, signal_line, histogram = TechnicalIndicators.macd(
            sample_price_series
        )
        diff = macd_line - signal_line
        pd.testing.assert_series_equal(histogram, diff)


class TestBollingerBands:
    def test_bollinger_basic(self, sample_price_series):
        upper, middle, lower = TechnicalIndicators.bollinger_bands(
            sample_price_series, 20, 2.0
        )
        valid_idx = middle.dropna().index
        # upper应大于middle，middle应大于lower
        assert (upper[valid_idx] >= middle[valid_idx]).all()
        assert (middle[valid_idx] >= lower[valid_idx]).all()


class TestATR:
    def test_atr_positive(self, sample_ohlcv_df):
        atr = TechnicalIndicators.atr(
            sample_ohlcv_df["high"],
            sample_ohlcv_df["low"],
            sample_ohlcv_df["close"],
            14,
        )
        valid_atr = atr.dropna()
        assert (valid_atr > 0).all()


class TestComputeAll:
    def test_compute_all_adds_columns(self, sample_ohlcv_df):
        result = TechnicalIndicators.compute_all(sample_ohlcv_df)
        # 检查新增的列
        expected_columns = [
            "sma_10", "sma_20", "sma_30", "sma_60",
            "ema_10", "ema_20", "ema_30", "ema_60",
            "rsi", "macd", "macd_signal", "macd_hist",
            "bb_upper", "bb_middle", "bb_lower", "atr",
        ]
        for col in expected_columns:
            assert col in result.columns, f"缺少列: {col}"

    def test_compute_all_preserves_original(self, sample_ohlcv_df):
        result = TechnicalIndicators.compute_all(sample_ohlcv_df)
        # 原始列应保持不变
        pd.testing.assert_series_equal(result["close"], sample_ohlcv_df["close"])
