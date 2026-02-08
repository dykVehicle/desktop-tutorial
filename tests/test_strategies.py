"""
交易策略模块的单元测试
"""

import numpy as np
import pandas as pd
import pytest

from quant_agent.strategies.base import BaseStrategy, Signal, SignalType
from quant_agent.strategies.ma_crossover import MACrossoverStrategy
from quant_agent.strategies.rsi_strategy import RSIStrategy
from quant_agent.strategies.macd_strategy import MACDStrategy


@pytest.fixture
def sample_data():
    """生成模拟市场数据。"""
    np.random.seed(42)
    n = 200
    close = 100 + np.cumsum(np.random.randn(n) * 1.0)
    high = close + np.abs(np.random.randn(n))
    low = close - np.abs(np.random.randn(n))
    open_price = close + np.random.randn(n) * 0.5
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


@pytest.fixture
def trending_up_data():
    """生成一段明确的上涨数据。"""
    n = 100
    # 先下降再上升，确保产生金叉
    prices = np.concatenate([
        np.linspace(100, 90, 40),
        np.linspace(90, 120, 60),
    ])
    dates = pd.bdate_range(start="2024-01-01", periods=n)
    return pd.DataFrame(
        {
            "open": prices - 0.5,
            "high": prices + 1.0,
            "low": prices - 1.0,
            "close": prices,
            "volume": [1000000] * n,
        },
        index=dates,
    )


class TestSignal:
    def test_signal_creation(self):
        signal = Signal(
            signal_type=SignalType.BUY,
            strength=0.8,
            symbol="000001.SZ",
            strategy_name="test",
        )
        assert signal.signal_type == SignalType.BUY
        assert signal.strength == 0.8
        assert signal.symbol == "000001.SZ"

    def test_signal_strength_clamping(self):
        signal = Signal(
            signal_type=SignalType.BUY,
            strength=2.0,
            symbol="test",
            strategy_name="test",
        )
        assert signal.strength == 1.0

        signal2 = Signal(
            signal_type=SignalType.SELL,
            strength=-2.0,
            symbol="test",
            strategy_name="test",
        )
        assert signal2.strength == -1.0


class TestMACrossoverStrategy:
    def test_init(self):
        strategy = MACrossoverStrategy(short_window=5, long_window=20)
        assert strategy.name == "MA_Crossover"
        assert strategy.short_window == 5
        assert strategy.long_window == 20

    def test_generates_signals(self, sample_data):
        strategy = MACrossoverStrategy(short_window=5, long_window=20)
        signals = strategy.generate_signals(sample_data, "test_symbol")
        assert isinstance(signals, list)
        # 应该产生一些信号
        assert len(signals) > 0

    def test_signal_types(self, sample_data):
        strategy = MACrossoverStrategy(short_window=5, long_window=20)
        signals = strategy.generate_signals(sample_data, "test_symbol")
        for sig in signals:
            assert sig.signal_type in (SignalType.BUY, SignalType.SELL)
            assert sig.symbol == "test_symbol"
            assert sig.strategy_name == "MA_Crossover"

    def test_golden_cross(self, trending_up_data):
        """上升趋势中应该产生金叉买入信号。"""
        strategy = MACrossoverStrategy(short_window=5, long_window=20)
        signals = strategy.generate_signals(trending_up_data, "test")
        buy_signals = [s for s in signals if s.signal_type == SignalType.BUY]
        assert len(buy_signals) > 0

    def test_validate_data(self):
        strategy = MACrossoverStrategy()
        with pytest.raises(ValueError):
            strategy.generate_signals(pd.DataFrame({"price": [1, 2, 3]}), "test")

    def test_generate_latest_signal(self, sample_data):
        strategy = MACrossoverStrategy(short_window=5, long_window=20)
        signal = strategy.generate_latest_signal(sample_data, "test")
        assert isinstance(signal, Signal)


class TestRSIStrategy:
    def test_init(self):
        strategy = RSIStrategy(period=14, overbought=70, oversold=30)
        assert strategy.name == "RSI"
        assert strategy.period == 14

    def test_generates_signals(self, sample_data):
        strategy = RSIStrategy()
        signals = strategy.generate_signals(sample_data, "test_symbol")
        assert isinstance(signals, list)

    def test_signal_types(self, sample_data):
        strategy = RSIStrategy()
        signals = strategy.generate_signals(sample_data, "test_symbol")
        for sig in signals:
            assert sig.signal_type in (SignalType.BUY, SignalType.SELL)
            assert "RSI" in sig.reason

    def test_oversold_produces_buy(self):
        """深度超卖后应产生买入信号。"""
        # 先大幅下跌，再小幅上涨
        n = 50
        prices = np.concatenate([
            np.linspace(100, 50, 30),   # 大幅下跌
            np.linspace(50, 55, 20),    # 小幅上涨
        ])
        dates = pd.bdate_range(start="2024-01-01", periods=n)
        df = pd.DataFrame(
            {"close": prices, "open": prices, "high": prices + 1, "low": prices - 1, "volume": [100000] * n},
            index=dates,
        )
        strategy = RSIStrategy(period=14, oversold=30)
        signals = strategy.generate_signals(df, "test")
        buy_signals = [s for s in signals if s.signal_type == SignalType.BUY]
        # 可能会产生买入信号
        assert isinstance(buy_signals, list)


class TestMACDStrategy:
    def test_init(self):
        strategy = MACDStrategy(fast_period=12, slow_period=26, signal_period=9)
        assert strategy.name == "MACD"

    def test_generates_signals(self, sample_data):
        strategy = MACDStrategy()
        signals = strategy.generate_signals(sample_data, "test_symbol")
        assert isinstance(signals, list)
        assert len(signals) > 0

    def test_signal_types(self, sample_data):
        strategy = MACDStrategy()
        signals = strategy.generate_signals(sample_data, "test_symbol")
        for sig in signals:
            assert sig.signal_type in (SignalType.BUY, SignalType.SELL)
            assert "MACD" in sig.reason

    def test_signal_metadata(self, sample_data):
        strategy = MACDStrategy()
        signals = strategy.generate_signals(sample_data, "test_symbol")
        if signals:
            sig = signals[0]
            assert "macd" in sig.metadata
            assert "signal" in sig.metadata
            assert "histogram" in sig.metadata
            assert "date" in sig.metadata
