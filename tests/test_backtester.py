"""
回测引擎的单元测试
"""

import numpy as np
import pandas as pd
import pytest

from quant_agent.backtest.backtester import Backtester, BacktestResult
from quant_agent.strategies.ma_crossover import MACrossoverStrategy
from quant_agent.strategies.rsi_strategy import RSIStrategy
from quant_agent.strategies.macd_strategy import MACDStrategy
from quant_agent.risk.risk_manager import RiskLimits
from quant_agent.data.market_data import MarketDataProvider


@pytest.fixture
def backtester():
    return Backtester(
        initial_capital=1000000.0,
        commission_rate=0.001,
        slippage=0.001,
    )


@pytest.fixture
def sample_data():
    """生成回测用的市场数据。"""
    provider = MarketDataProvider(source="synthetic")
    return {
        "000001.SZ": provider.get_data("000001.SZ", "2024-01-01", "2024-12-31"),
        "600519.SH": provider.get_data("600519.SH", "2024-01-01", "2024-12-31"),
    }


@pytest.fixture
def strategies():
    return [
        MACrossoverStrategy(short_window=10, long_window=30, weight=0.4),
        RSIStrategy(period=14, weight=0.3),
        MACDStrategy(weight=0.3),
    ]


class TestBacktester:
    def test_basic_backtest(self, backtester, strategies, sample_data):
        result = backtester.run(strategies, sample_data, signal_threshold=0.3)
        assert isinstance(result, BacktestResult)
        assert not result.equity_curve.empty
        assert "initial_capital" in result.metrics
        assert result.metrics["initial_capital"] == 1000000.0

    def test_single_strategy(self, backtester, sample_data):
        strategies = [MACrossoverStrategy(short_window=5, long_window=20)]
        result = backtester.run(strategies, sample_data)
        assert isinstance(result, BacktestResult)

    def test_metrics_present(self, backtester, strategies, sample_data):
        result = backtester.run(strategies, sample_data)
        expected_metrics = [
            "initial_capital", "final_equity", "total_return",
            "total_trades", "sharpe_ratio", "max_drawdown",
        ]
        for key in expected_metrics:
            assert key in result.metrics, f"缺少指标: {key}"

    def test_equity_curve_has_dates(self, backtester, strategies, sample_data):
        result = backtester.run(strategies, sample_data)
        assert "date" in result.equity_curve.columns
        assert "equity" in result.equity_curve.columns

    def test_final_equity_reasonable(self, backtester, strategies, sample_data):
        result = backtester.run(strategies, sample_data)
        final = result.metrics["final_equity"]
        initial = result.metrics["initial_capital"]
        # 最终权益应在合理范围内（不会翻100倍或亏到0）
        assert final > initial * 0.5
        assert final < initial * 3.0

    def test_empty_data(self, backtester, strategies):
        result = backtester.run(strategies, {})
        assert result.metrics.get("error") == "无有效数据" or result.equity_curve.empty

    def test_summary_output(self, backtester, strategies, sample_data):
        result = backtester.run(strategies, sample_data)
        summary = result.summary()
        assert isinstance(summary, str)
        assert "回测绩效报告" in summary

    def test_with_custom_risk_limits(self, sample_data, strategies):
        limits = RiskLimits(
            max_position_pct=0.2,
            stop_loss_pct=0.03,
            take_profit_pct=0.10,
        )
        backtester = Backtester(
            initial_capital=500000.0,
            risk_limits=limits,
        )
        result = backtester.run(strategies, sample_data)
        assert result.metrics["initial_capital"] == 500000.0

    def test_high_threshold_fewer_trades(self, backtester, strategies, sample_data):
        result_low = backtester.run(strategies, sample_data, signal_threshold=0.1)
        result_high = backtester.run(strategies, sample_data, signal_threshold=0.8)
        # 高阈值应产生更少（或相等）的交易
        assert result_high.metrics.get("total_trades", 0) <= result_low.metrics.get("total_trades", 0)

    def test_single_symbol(self, backtester, strategies):
        provider = MarketDataProvider(source="synthetic")
        data = {"000001.SZ": provider.get_data("000001.SZ", "2024-01-01", "2024-06-30")}
        result = backtester.run(strategies, data)
        assert isinstance(result, BacktestResult)

    def test_trades_recorded(self, backtester, strategies, sample_data):
        result = backtester.run(strategies, sample_data, signal_threshold=0.1)
        # 低阈值下应该有交易
        if result.metrics.get("total_trades", 0) > 0:
            assert len(result.trades) > 0
            trade = result.trades[0]
            assert "symbol" in trade
            assert "side" in trade
            assert "quantity" in trade
