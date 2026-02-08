"""
订单执行模块的单元测试
"""

import pytest

from quant_agent.execution.executor import OrderExecutor, Order, OrderSide, OrderStatus
from quant_agent.portfolio.portfolio import Portfolio
from quant_agent.risk.risk_manager import RiskManager, RiskLimits


@pytest.fixture
def executor():
    return OrderExecutor(commission_rate=0.001, slippage=0.001)


@pytest.fixture
def portfolio():
    return Portfolio(initial_capital=1000000.0)


@pytest.fixture
def risk_manager():
    return RiskManager(RiskLimits(max_position_pct=0.3, max_total_position_pct=0.8))


class TestOrderCreation:
    def test_create_order(self, executor):
        order = executor.create_order("test", OrderSide.BUY, 100, 10.0, "2024-01-01")
        assert order.symbol == "test"
        assert order.side == OrderSide.BUY
        assert order.quantity == 100
        assert order.price == 10.0
        assert order.status == OrderStatus.PENDING

    def test_order_in_history(self, executor):
        executor.create_order("test", OrderSide.BUY, 100, 10.0)
        assert len(executor.order_history) == 1


class TestOrderExecution:
    def test_execute_buy(self, executor, portfolio):
        order = executor.create_order("test", OrderSide.BUY, 100, 10.0, "2024-01-01")
        result = executor.execute_order(order, portfolio)
        assert result.status == OrderStatus.FILLED
        assert result.filled_quantity == 100
        assert "test" in portfolio.positions

    def test_execute_sell(self, executor, portfolio):
        # 先买入
        buy_order = executor.create_order("test", OrderSide.BUY, 100, 10.0, "2024-01-01")
        executor.execute_order(buy_order, portfolio)
        # 再卖出
        sell_order = executor.create_order("test", OrderSide.SELL, 50, 12.0, "2024-01-02")
        result = executor.execute_order(sell_order, portfolio)
        assert result.status == OrderStatus.FILLED
        assert portfolio.positions["test"].quantity == 50

    def test_slippage_buy(self, executor, portfolio):
        order = executor.create_order("test", OrderSide.BUY, 100, 100.0)
        result = executor.execute_order(order, portfolio)
        # 买入滑点: 100 * 1.001 = 100.10
        assert result.filled_price == 100.10

    def test_slippage_sell(self, executor, portfolio):
        buy_order = executor.create_order("test", OrderSide.BUY, 100, 100.0)
        executor.execute_order(buy_order, portfolio)
        sell_order = executor.create_order("test", OrderSide.SELL, 100, 100.0)
        result = executor.execute_order(sell_order, portfolio)
        # 卖出滑点: 100 * 0.999 = 99.90
        assert result.filled_price == 99.90

    def test_commission(self, executor, portfolio):
        order = executor.create_order("test", OrderSide.BUY, 100, 100.0)
        result = executor.execute_order(order, portfolio)
        # 手续费: 100 * 100.10 * 0.001 = 10.01
        assert result.commission == 10.01

    def test_insufficient_funds(self, executor):
        small_portfolio = Portfolio(initial_capital=100.0)
        order = executor.create_order("test", OrderSide.BUY, 100, 10.0)
        result = executor.execute_order(order, small_portfolio)
        assert result.status == OrderStatus.REJECTED

    def test_with_risk_manager(self, executor, portfolio, risk_manager):
        order = executor.create_order("test", OrderSide.BUY, 100, 10.0)
        result = executor.execute_order(order, portfolio, risk_manager)
        assert result.status == OrderStatus.FILLED

    def test_risk_manager_rejects_large_position(self, executor, portfolio, risk_manager):
        # 尝试买入超过30%仓位的量
        order = executor.create_order("test", OrderSide.BUY, 50000, 10.0)
        result = executor.execute_order(order, portfolio, risk_manager)
        # 应该被调整或拒绝
        if result.status == OrderStatus.FILLED:
            assert result.filled_quantity < 50000

    def test_already_filled_order(self, executor, portfolio):
        order = executor.create_order("test", OrderSide.BUY, 100, 10.0)
        executor.execute_order(order, portfolio)
        # 重复执行
        result = executor.execute_order(order, portfolio)
        assert result.status == OrderStatus.FILLED  # 不会重新执行


class TestOrderQueries:
    def test_get_filled_orders(self, executor, portfolio):
        order = executor.create_order("test", OrderSide.BUY, 100, 10.0)
        executor.execute_order(order, portfolio)
        filled = executor.get_filled_orders()
        assert len(filled) == 1

    def test_get_rejected_orders(self, executor):
        small_portfolio = Portfolio(initial_capital=100.0)
        order = executor.create_order("test", OrderSide.BUY, 100, 10.0)
        executor.execute_order(order, small_portfolio)
        rejected = executor.get_rejected_orders()
        assert len(rejected) == 1

    def test_reset(self, executor, portfolio):
        executor.create_order("test", OrderSide.BUY, 100, 10.0)
        executor.reset()
        assert len(executor.order_history) == 0
