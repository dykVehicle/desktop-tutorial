"""
投资组合管理模块

管理持仓、跟踪盈亏、记录交易历史。
"""

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from quant_agent.utils.logger import get_logger

logger = get_logger("quant_agent.portfolio")


@dataclass
class Position:
    """
    持仓信息

    Attributes:
        symbol: 股票代码
        quantity: 持仓数量
        avg_price: 平均成本价
        current_price: 当前价格
    """
    symbol: str
    quantity: int
    avg_price: float
    current_price: float = 0.0

    @property
    def market_value(self) -> float:
        """持仓市值"""
        return self.quantity * self.current_price

    @property
    def cost_basis(self) -> float:
        """持仓成本"""
        return self.quantity * self.avg_price

    @property
    def unrealized_pnl(self) -> float:
        """未实现盈亏"""
        return self.market_value - self.cost_basis

    @property
    def unrealized_pnl_pct(self) -> float:
        """未实现盈亏百分比"""
        if self.cost_basis == 0:
            return 0.0
        return self.unrealized_pnl / self.cost_basis


@dataclass
class TradeRecord:
    """
    交易记录

    Attributes:
        date: 交易日期
        symbol: 股票代码
        side: 交易方向 ("buy" | "sell")
        quantity: 交易数量
        price: 成交价格
        commission: 手续费
        pnl: 已实现盈亏（仅卖出时有效）
    """
    date: str
    symbol: str
    side: str
    quantity: int
    price: float
    commission: float = 0.0
    pnl: float = 0.0


class Portfolio:
    """
    投资组合管理器

    管理现金、持仓、交易记录和绩效统计。
    """

    def __init__(self, initial_capital: float = 1000000.0):
        """
        初始化投资组合。

        Args:
            initial_capital: 初始资金
        """
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions: dict[str, Position] = {}
        self.trade_history: list[TradeRecord] = []
        self.equity_history: list[dict] = []
        self._realized_pnl = 0.0

    @property
    def total_position_value(self) -> float:
        """总持仓市值"""
        return sum(pos.market_value for pos in self.positions.values())

    @property
    def total_equity(self) -> float:
        """总权益 = 现金 + 持仓市值"""
        return self.cash + self.total_position_value

    @property
    def total_return(self) -> float:
        """总收益率"""
        if self.initial_capital == 0:
            return 0.0
        return (self.total_equity - self.initial_capital) / self.initial_capital

    @property
    def realized_pnl(self) -> float:
        """已实现盈亏"""
        return self._realized_pnl

    @property
    def unrealized_pnl(self) -> float:
        """未实现盈亏"""
        return sum(pos.unrealized_pnl for pos in self.positions.values())

    def buy(
        self,
        symbol: str,
        quantity: int,
        price: float,
        commission: float = 0.0,
        date: str = "",
    ) -> bool:
        """
        买入操作。

        Args:
            symbol: 股票代码
            quantity: 买入数量
            price: 买入价格
            commission: 手续费
            date: 交易日期

        Returns:
            是否成功
        """
        total_cost = quantity * price + commission
        if total_cost > self.cash:
            logger.warning(
                f"资金不足: 需要 {total_cost:.2f}, 可用 {self.cash:.2f}"
            )
            return False

        if quantity <= 0:
            return False

        self.cash -= total_cost

        if symbol in self.positions:
            pos = self.positions[symbol]
            # 更新加权平均成本
            total_quantity = pos.quantity + quantity
            pos.avg_price = (
                (pos.avg_price * pos.quantity + price * quantity) / total_quantity
            )
            pos.quantity = total_quantity
            pos.current_price = price
        else:
            self.positions[symbol] = Position(
                symbol=symbol,
                quantity=quantity,
                avg_price=price,
                current_price=price,
            )

        trade = TradeRecord(
            date=date,
            symbol=symbol,
            side="buy",
            quantity=quantity,
            price=price,
            commission=commission,
        )
        self.trade_history.append(trade)
        logger.info(f"买入 {symbol}: {quantity}股 @ {price:.2f}, 手续费 {commission:.2f}")
        return True

    def sell(
        self,
        symbol: str,
        quantity: int,
        price: float,
        commission: float = 0.0,
        date: str = "",
    ) -> bool:
        """
        卖出操作。

        Args:
            symbol: 股票代码
            quantity: 卖出数量
            price: 卖出价格
            commission: 手续费
            date: 交易日期

        Returns:
            是否成功
        """
        if symbol not in self.positions:
            logger.warning(f"无持仓: {symbol}")
            return False

        pos = self.positions[symbol]
        if quantity > pos.quantity:
            logger.warning(
                f"持仓不足: {symbol} 持有 {pos.quantity}, 拟卖出 {quantity}"
            )
            return False

        if quantity <= 0:
            return False

        # 计算已实现盈亏
        pnl = (price - pos.avg_price) * quantity - commission
        self._realized_pnl += pnl

        revenue = quantity * price - commission
        self.cash += revenue

        pos.quantity -= quantity
        pos.current_price = price

        if pos.quantity == 0:
            del self.positions[symbol]

        trade = TradeRecord(
            date=date,
            symbol=symbol,
            side="sell",
            quantity=quantity,
            price=price,
            commission=commission,
            pnl=pnl,
        )
        self.trade_history.append(trade)
        logger.info(
            f"卖出 {symbol}: {quantity}股 @ {price:.2f}, "
            f"盈亏 {pnl:.2f}, 手续费 {commission:.2f}"
        )
        return True

    def update_prices(self, prices: dict[str, float]):
        """
        更新持仓的当前价格。

        Args:
            prices: {symbol: price} 字典
        """
        for symbol, price in prices.items():
            if symbol in self.positions:
                self.positions[symbol].current_price = price

    def record_equity(self, date: str):
        """
        记录当前时点的权益快照。

        Args:
            date: 日期
        """
        self.equity_history.append(
            {
                "date": date,
                "equity": self.total_equity,
                "cash": self.cash,
                "position_value": self.total_position_value,
                "realized_pnl": self._realized_pnl,
                "unrealized_pnl": self.unrealized_pnl,
            }
        )

    def get_equity_curve(self) -> pd.DataFrame:
        """
        获取权益曲线。

        Returns:
            权益曲线DataFrame
        """
        if not self.equity_history:
            return pd.DataFrame()
        return pd.DataFrame(self.equity_history)

    def get_trade_summary(self) -> dict:
        """
        获取交易统计摘要。

        Returns:
            交易统计字典
        """
        if not self.trade_history:
            return {
                "total_trades": 0,
                "buy_trades": 0,
                "sell_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "avg_pnl": 0.0,
            }

        sell_trades = [t for t in self.trade_history if t.side == "sell"]
        winning = [t for t in sell_trades if t.pnl > 0]
        losing = [t for t in sell_trades if t.pnl < 0]

        total_sell = len(sell_trades)
        win_rate = len(winning) / total_sell if total_sell > 0 else 0.0

        total_pnl = sum(t.pnl for t in sell_trades)
        avg_pnl = total_pnl / total_sell if total_sell > 0 else 0.0

        return {
            "total_trades": len(self.trade_history),
            "buy_trades": len([t for t in self.trade_history if t.side == "buy"]),
            "sell_trades": total_sell,
            "winning_trades": len(winning),
            "losing_trades": len(losing),
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "avg_pnl": avg_pnl,
        }

    def get_holdings(self) -> list[dict]:
        """
        获取当前持仓列表。

        Returns:
            持仓信息字典列表
        """
        return [
            {
                "symbol": pos.symbol,
                "quantity": pos.quantity,
                "avg_price": pos.avg_price,
                "current_price": pos.current_price,
                "market_value": pos.market_value,
                "unrealized_pnl": pos.unrealized_pnl,
                "unrealized_pnl_pct": pos.unrealized_pnl_pct,
            }
            for pos in self.positions.values()
        ]

    def reset(self):
        """重置投资组合到初始状态。"""
        self.cash = self.initial_capital
        self.positions.clear()
        self.trade_history.clear()
        self.equity_history.clear()
        self._realized_pnl = 0.0

    def __repr__(self) -> str:
        return (
            f"Portfolio(equity={self.total_equity:.2f}, "
            f"cash={self.cash:.2f}, "
            f"positions={len(self.positions)}, "
            f"return={self.total_return:.2%})"
        )
