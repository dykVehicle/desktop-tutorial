"""
投资组合模块的单元测试
"""

import pytest

from quant_agent.portfolio.portfolio import Portfolio, Position, TradeRecord


@pytest.fixture
def portfolio():
    """创建一个初始资金为100万的投资组合。"""
    return Portfolio(initial_capital=1000000.0)


class TestPosition:
    def test_position_creation(self):
        pos = Position(symbol="test", quantity=100, avg_price=10.0, current_price=12.0)
        assert pos.market_value == 1200.0
        assert pos.cost_basis == 1000.0
        assert pos.unrealized_pnl == 200.0
        assert abs(pos.unrealized_pnl_pct - 0.2) < 1e-10

    def test_position_no_change(self):
        pos = Position(symbol="test", quantity=100, avg_price=10.0, current_price=10.0)
        assert pos.unrealized_pnl == 0.0
        assert pos.unrealized_pnl_pct == 0.0


class TestPortfolioBuy:
    def test_buy_success(self, portfolio):
        assert portfolio.buy("test", 100, 10.0, commission=1.0, date="2024-01-01")
        assert "test" in portfolio.positions
        assert portfolio.positions["test"].quantity == 100
        assert portfolio.cash == 1000000.0 - 100 * 10.0 - 1.0

    def test_buy_insufficient_funds(self, portfolio):
        assert not portfolio.buy("test", 1000000, 10.0)

    def test_buy_zero_quantity(self, portfolio):
        assert not portfolio.buy("test", 0, 10.0)

    def test_buy_add_to_existing(self, portfolio):
        portfolio.buy("test", 100, 10.0, date="2024-01-01")
        portfolio.buy("test", 100, 12.0, date="2024-01-02")
        assert portfolio.positions["test"].quantity == 200
        assert portfolio.positions["test"].avg_price == 11.0  # 加权平均


class TestPortfolioSell:
    def test_sell_success(self, portfolio):
        portfolio.buy("test", 100, 10.0, date="2024-01-01")
        assert portfolio.sell("test", 50, 12.0, date="2024-01-02")
        assert portfolio.positions["test"].quantity == 50

    def test_sell_all(self, portfolio):
        portfolio.buy("test", 100, 10.0, date="2024-01-01")
        assert portfolio.sell("test", 100, 12.0, date="2024-01-02")
        assert "test" not in portfolio.positions

    def test_sell_no_position(self, portfolio):
        assert not portfolio.sell("test", 100, 10.0)

    def test_sell_more_than_held(self, portfolio):
        portfolio.buy("test", 50, 10.0, date="2024-01-01")
        assert not portfolio.sell("test", 100, 12.0)

    def test_sell_zero_quantity(self, portfolio):
        portfolio.buy("test", 100, 10.0)
        assert not portfolio.sell("test", 0, 12.0)

    def test_sell_pnl_calculation(self, portfolio):
        portfolio.buy("test", 100, 10.0, date="2024-01-01")
        portfolio.sell("test", 100, 12.0, commission=2.0, date="2024-01-02")
        # PnL = (12 - 10) * 100 - 2 = 198
        assert portfolio.realized_pnl == 198.0


class TestPortfolioEquity:
    def test_total_equity(self, portfolio):
        assert portfolio.total_equity == 1000000.0

    def test_equity_after_buy(self, portfolio):
        portfolio.buy("test", 100, 10.0, date="2024-01-01")
        portfolio.update_prices({"test": 10.0})
        assert portfolio.total_equity == 1000000.0  # 价格未变

    def test_equity_with_price_change(self, portfolio):
        portfolio.buy("test", 100, 10.0, date="2024-01-01")
        portfolio.update_prices({"test": 12.0})
        # cash = 999000, position_value = 100 * 12 = 1200
        assert portfolio.total_equity == 999000.0 + 1200.0

    def test_total_return(self, portfolio):
        assert portfolio.total_return == 0.0

    def test_total_position_value(self, portfolio):
        assert portfolio.total_position_value == 0.0


class TestPortfolioRecording:
    def test_record_equity(self, portfolio):
        portfolio.record_equity("2024-01-01")
        eq = portfolio.get_equity_curve()
        assert len(eq) == 1
        assert eq.iloc[0]["equity"] == 1000000.0

    def test_trade_summary_empty(self, portfolio):
        summary = portfolio.get_trade_summary()
        assert summary["total_trades"] == 0

    def test_trade_summary_with_trades(self, portfolio):
        portfolio.buy("A", 100, 10.0, date="2024-01-01")
        portfolio.sell("A", 100, 12.0, date="2024-01-02")
        summary = portfolio.get_trade_summary()
        assert summary["total_trades"] == 2
        assert summary["buy_trades"] == 1
        assert summary["sell_trades"] == 1

    def test_get_holdings(self, portfolio):
        portfolio.buy("A", 100, 10.0, date="2024-01-01")
        portfolio.update_prices({"A": 12.0})
        holdings = portfolio.get_holdings()
        assert len(holdings) == 1
        assert holdings[0]["symbol"] == "A"
        assert holdings[0]["quantity"] == 100


class TestPortfolioReset:
    def test_reset(self, portfolio):
        portfolio.buy("test", 100, 10.0)
        portfolio.reset()
        assert portfolio.cash == 1000000.0
        assert len(portfolio.positions) == 0
        assert len(portfolio.trade_history) == 0
