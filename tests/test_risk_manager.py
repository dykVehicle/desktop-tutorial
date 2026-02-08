"""
风险管理模块的单元测试
"""

import numpy as np
import pandas as pd
import pytest

from quant_agent.risk.risk_manager import RiskManager, RiskLimits


@pytest.fixture
def risk_manager():
    """创建默认风险管理器。"""
    limits = RiskLimits(
        max_position_pct=0.3,
        max_total_position_pct=0.8,
        stop_loss_pct=0.05,
        take_profit_pct=0.15,
        max_drawdown_pct=0.15,
        max_daily_loss_pct=0.03,
    )
    return RiskManager(limits)


class TestPositionSize:
    def test_normal_position(self, risk_manager):
        allowed, qty, reason = risk_manager.check_position_size(
            symbol="test",
            proposed_quantity=100,
            price=10.0,
            current_portfolio_value=100000.0,
            current_position_value=0.0,
        )
        assert allowed
        assert qty == 100

    def test_exceeds_position_limit(self, risk_manager):
        allowed, qty, reason = risk_manager.check_position_size(
            symbol="test",
            proposed_quantity=5000,
            price=10.0,
            current_portfolio_value=100000.0,
            current_position_value=0.0,
        )
        # 5000 * 10 = 50000, 超过30%限制
        assert allowed  # 允许但会调整数量
        assert qty < 5000  # 数量应被调整

    def test_position_already_at_limit(self, risk_manager):
        allowed, qty, reason = risk_manager.check_position_size(
            symbol="test",
            proposed_quantity=100,
            price=10.0,
            current_portfolio_value=100000.0,
            current_position_value=30000.0,  # 已达30%
        )
        assert not allowed
        assert qty == 0

    def test_zero_portfolio_value(self, risk_manager):
        allowed, qty, reason = risk_manager.check_position_size(
            symbol="test",
            proposed_quantity=100,
            price=10.0,
            current_portfolio_value=0.0,
        )
        assert not allowed


class TestTotalExposure:
    def test_normal_exposure(self, risk_manager):
        allowed, reason = risk_manager.check_total_exposure(
            total_position_value=50000.0,
            proposed_trade_value=10000.0,
            portfolio_value=100000.0,
        )
        assert allowed

    def test_exceeds_exposure(self, risk_manager):
        allowed, reason = risk_manager.check_total_exposure(
            total_position_value=70000.0,
            proposed_trade_value=20000.0,
            portfolio_value=100000.0,
        )
        assert not allowed


class TestStopLoss:
    def test_no_stop_loss(self, risk_manager):
        triggered, reason = risk_manager.check_stop_loss(100.0, 96.0)
        assert not triggered  # 4% < 5%

    def test_stop_loss_triggered(self, risk_manager):
        triggered, reason = risk_manager.check_stop_loss(100.0, 94.0)
        assert triggered  # 6% > 5%

    def test_exactly_at_threshold(self, risk_manager):
        triggered, reason = risk_manager.check_stop_loss(100.0, 95.0)
        assert triggered  # 5% >= 5%


class TestTakeProfit:
    def test_no_take_profit(self, risk_manager):
        triggered, reason = risk_manager.check_take_profit(100.0, 110.0)
        assert not triggered  # 10% < 15%

    def test_take_profit_triggered(self, risk_manager):
        triggered, reason = risk_manager.check_take_profit(100.0, 120.0)
        assert triggered  # 20% > 15%


class TestMaxDrawdown:
    def test_no_drawdown(self, risk_manager):
        risk_manager.update_peak_equity(100000.0)
        triggered, reason = risk_manager.check_max_drawdown(95000.0)
        assert not triggered  # 5% < 15%

    def test_drawdown_triggered(self, risk_manager):
        risk_manager.update_peak_equity(100000.0)
        triggered, reason = risk_manager.check_max_drawdown(84000.0)
        assert triggered  # 16% > 15%


class TestDailyLoss:
    def test_no_daily_loss(self, risk_manager):
        triggered, reason = risk_manager.check_daily_loss(98000.0, 100000.0)
        assert not triggered  # 2% < 3%

    def test_daily_loss_triggered(self, risk_manager):
        triggered, reason = risk_manager.check_daily_loss(96000.0, 100000.0)
        assert triggered  # 4% > 3%


class TestCalculatePositionSize:
    def test_basic_position_size(self, risk_manager):
        qty = risk_manager.calculate_position_size(
            portfolio_value=100000.0,
            price=10.0,
            signal_strength=0.5,
        )
        assert qty > 0
        assert qty * 10.0 <= 100000.0 * 0.3  # 不超过最大仓位

    def test_zero_signal(self, risk_manager):
        qty = risk_manager.calculate_position_size(
            portfolio_value=100000.0,
            price=10.0,
            signal_strength=0.0,
        )
        assert qty == 0

    def test_with_atr(self, risk_manager):
        qty1 = risk_manager.calculate_position_size(
            portfolio_value=100000.0,
            price=10.0,
            signal_strength=0.5,
            atr=None,
        )
        qty2 = risk_manager.calculate_position_size(
            portfolio_value=100000.0,
            price=10.0,
            signal_strength=0.5,
            atr=2.0,  # 高波动
        )
        # 高波动率时仓位应更小
        assert qty2 <= qty1


class TestStaticMethods:
    def test_calculate_var(self):
        returns = pd.Series(np.random.randn(1000) * 0.01)
        var = RiskManager.calculate_var(returns, confidence=0.95)
        assert var > 0

    def test_calculate_max_drawdown(self):
        # 先涨后跌
        equity = pd.Series([100, 110, 120, 100, 90, 95])
        max_dd = RiskManager.calculate_max_drawdown(equity)
        # 最大回撤应是 (120-90)/120 = 25%
        assert abs(max_dd - 0.25) < 1e-10

    def test_calculate_max_drawdown_no_drawdown(self):
        equity = pd.Series([100, 110, 120, 130])
        max_dd = RiskManager.calculate_max_drawdown(equity)
        assert max_dd == 0.0

    def test_reset(self, risk_manager):
        risk_manager.update_peak_equity(100000.0)
        risk_manager.reset()
        assert risk_manager._peak_equity == 0.0
