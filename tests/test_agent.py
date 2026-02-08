"""
交易智能体模块的单元测试
"""

import numpy as np
import pandas as pd
import pytest

from quant_agent.core.agent import TradingAgent
from quant_agent.strategies.base import Signal, SignalType
from quant_agent.strategies.ma_crossover import MACrossoverStrategy
from quant_agent.strategies.rsi_strategy import RSIStrategy
from quant_agent.strategies.macd_strategy import MACDStrategy
from quant_agent.data.market_data import MarketDataProvider


@pytest.fixture
def agent():
    """创建一个默认配置的交易智能体。"""
    return TradingAgent(signal_threshold=0.3, confidence_decay=0.95)


@pytest.fixture
def agent_with_strategies(agent):
    """创建一个已加载策略的智能体。"""
    agent.setup_default_strategies()
    return agent


@pytest.fixture
def sample_data():
    """生成测试用的市场数据。"""
    provider = MarketDataProvider(source="synthetic")
    return provider.get_data("000001.SZ", "2024-01-01", "2024-12-31")


class TestTradingAgentInit:
    def test_default_init(self, agent):
        assert agent.signal_threshold == 0.3
        assert agent.confidence_decay == 0.95
        assert len(agent.strategies) == 0

    def test_add_strategy(self, agent):
        strategy = MACrossoverStrategy()
        agent.add_strategy(strategy)
        assert len(agent.strategies) == 1

    def test_setup_default_strategies(self, agent):
        agent.setup_default_strategies()
        assert len(agent.strategies) == 3
        names = [s.name for s in agent.strategies]
        assert "MA_Crossover" in names
        assert "RSI" in names
        assert "MACD" in names

    def test_custom_weights(self, agent):
        agent.setup_default_strategies(
            ma_weight=0.5, rsi_weight=0.3, macd_weight=0.2
        )
        weights = {s.name: s.weight for s in agent.strategies}
        assert weights["MA_Crossover"] == 0.5
        assert weights["RSI"] == 0.3
        assert weights["MACD"] == 0.2

    def test_repr(self, agent_with_strategies):
        repr_str = repr(agent_with_strategies)
        assert "TradingAgent" in repr_str


class TestSignalFusion:
    def test_fuse_empty_signals(self, agent_with_strategies):
        signal_type, strength = agent_with_strategies.fuse_signals([])
        assert signal_type == SignalType.HOLD
        assert strength == 0.0

    def test_fuse_buy_signals(self, agent_with_strategies):
        signals = [
            Signal(SignalType.BUY, 0.8, "test", "MA_Crossover"),
            Signal(SignalType.BUY, 0.6, "test", "RSI"),
            Signal(SignalType.BUY, 0.7, "test", "MACD"),
        ]
        signal_type, strength = agent_with_strategies.fuse_signals(signals)
        assert signal_type == SignalType.BUY
        assert strength > 0

    def test_fuse_sell_signals(self, agent_with_strategies):
        signals = [
            Signal(SignalType.SELL, -0.8, "test", "MA_Crossover"),
            Signal(SignalType.SELL, -0.6, "test", "RSI"),
            Signal(SignalType.SELL, -0.7, "test", "MACD"),
        ]
        signal_type, strength = agent_with_strategies.fuse_signals(signals)
        assert signal_type == SignalType.SELL
        assert strength < 0

    def test_fuse_mixed_signals(self, agent_with_strategies):
        signals = [
            Signal(SignalType.BUY, 0.5, "test", "MA_Crossover"),
            Signal(SignalType.SELL, -0.5, "test", "RSI"),
            Signal(SignalType.HOLD, 0.0, "test", "MACD"),
        ]
        signal_type, strength = agent_with_strategies.fuse_signals(signals)
        # 混合信号应产生较弱的综合信号
        assert abs(strength) < 0.5

    def test_fuse_below_threshold(self, agent_with_strategies):
        signals = [
            Signal(SignalType.BUY, 0.1, "test", "MA_Crossover"),
            Signal(SignalType.HOLD, 0.0, "test", "RSI"),
        ]
        signal_type, strength = agent_with_strategies.fuse_signals(signals)
        assert signal_type == SignalType.HOLD


class TestAnalyzeSymbol:
    def test_analyze_basic(self, agent_with_strategies, sample_data):
        analysis = agent_with_strategies.analyze_symbol("000001.SZ", sample_data)
        assert "symbol" in analysis
        assert "latest_price" in analysis
        assert "signal_type" in analysis
        assert "signal_strength" in analysis
        assert "strategy_signals" in analysis
        assert analysis["symbol"] == "000001.SZ"

    def test_analyze_has_strategy_signals(self, agent_with_strategies, sample_data):
        analysis = agent_with_strategies.analyze_symbol("000001.SZ", sample_data)
        assert len(analysis["strategy_signals"]) == 3

    def test_signal_history(self, agent_with_strategies, sample_data):
        agent_with_strategies.analyze_symbol("000001.SZ", sample_data)
        history = agent_with_strategies.get_signal_history()
        assert len(history) == 1


class TestRunBacktest:
    def test_basic_backtest(self, agent_with_strategies):
        result = agent_with_strategies.run_backtest(
            symbols=["000001.SZ"],
            start_date="2024-01-01",
            end_date="2024-06-30",
        )
        assert result is not None
        assert "total_return" in result.metrics

    def test_multi_symbol_backtest(self, agent_with_strategies):
        result = agent_with_strategies.run_backtest(
            symbols=["000001.SZ", "600519.SH"],
            start_date="2024-01-01",
            end_date="2024-06-30",
        )
        assert result is not None

    def test_auto_setup_strategies(self):
        """未设置策略时应自动加载默认策略。"""
        agent = TradingAgent()
        result = agent.run_backtest(
            symbols=["000001.SZ"],
            start_date="2024-01-01",
            end_date="2024-06-30",
        )
        assert len(agent.strategies) == 3  # 默认3个策略
        assert result is not None

    def test_backtest_result_structure(self, agent_with_strategies):
        result = agent_with_strategies.run_backtest(
            symbols=["000001.SZ"],
            start_date="2024-01-01",
            end_date="2024-06-30",
        )
        assert hasattr(result, "equity_curve")
        assert hasattr(result, "trades")
        assert hasattr(result, "metrics")
        assert hasattr(result, "daily_returns")
