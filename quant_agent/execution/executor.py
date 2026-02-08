"""
订单执行模块

管理订单的创建、验证和执行，支持：
- 市价单模拟执行
- 滑点模拟
- 手续费计算
- 订单状态跟踪
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import uuid

from quant_agent.portfolio.portfolio import Portfolio
from quant_agent.risk.risk_manager import RiskManager
from quant_agent.utils.logger import get_logger

logger = get_logger("quant_agent.execution")


class OrderSide(Enum):
    """订单方向"""
    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    """订单状态"""
    PENDING = "pending"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


@dataclass
class Order:
    """
    交易订单

    Attributes:
        symbol: 股票代码
        side: 交易方向
        quantity: 交易数量
        price: 价格（市价单为参考价）
        order_id: 订单ID
        status: 订单状态
        filled_quantity: 已成交数量
        filled_price: 成交价格
        commission: 手续费
        reject_reason: 拒绝原因
        date: 交易日期
    """
    symbol: str
    side: OrderSide
    quantity: int
    price: float
    order_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: int = 0
    filled_price: float = 0.0
    commission: float = 0.0
    reject_reason: str = ""
    date: str = ""


class OrderExecutor:
    """
    订单执行器

    模拟订单的执行过程，包括滑点和手续费。
    """

    def __init__(
        self,
        commission_rate: float = 0.001,
        slippage: float = 0.001,
    ):
        """
        初始化订单执行器。

        Args:
            commission_rate: 手续费率
            slippage: 滑点比例
        """
        self.commission_rate = commission_rate
        self.slippage = slippage
        self.order_history: list[Order] = []

    def create_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: int,
        price: float,
        date: str = "",
    ) -> Order:
        """
        创建订单。

        Args:
            symbol: 股票代码
            side: 交易方向
            quantity: 交易数量
            price: 参考价格
            date: 交易日期

        Returns:
            创建的订单
        """
        order = Order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            date=date,
        )
        self.order_history.append(order)
        return order

    def execute_order(
        self,
        order: Order,
        portfolio: Portfolio,
        risk_manager: Optional[RiskManager] = None,
    ) -> Order:
        """
        执行订单。

        流程：
        1. 计算含滑点的成交价
        2. 风控检查（如果提供了risk_manager）
        3. 计算手续费
        4. 执行买入/卖出

        Args:
            order: 待执行的订单
            portfolio: 投资组合
            risk_manager: 风险管理器（可选）

        Returns:
            执行后的订单
        """
        if order.status != OrderStatus.PENDING:
            return order

        # 计算含滑点的成交价
        if order.side == OrderSide.BUY:
            filled_price = order.price * (1 + self.slippage)
        else:
            filled_price = order.price * (1 - self.slippage)

        filled_price = round(filled_price, 2)

        # 计算手续费
        commission = round(order.quantity * filled_price * self.commission_rate, 2)

        # 风控检查
        if risk_manager and order.side == OrderSide.BUY:
            current_position_value = 0.0
            if order.symbol in portfolio.positions:
                current_position_value = portfolio.positions[order.symbol].market_value

            allowed, adjusted_qty, reason = risk_manager.check_position_size(
                symbol=order.symbol,
                proposed_quantity=order.quantity,
                price=filled_price,
                current_portfolio_value=portfolio.total_equity,
                current_position_value=current_position_value,
            )

            if not allowed:
                order.status = OrderStatus.REJECTED
                order.reject_reason = reason
                logger.warning(f"订单被拒绝: {order.order_id} - {reason}")
                return order

            if adjusted_qty < order.quantity:
                order.quantity = adjusted_qty

            # 检查总仓位暴露
            allowed, reason = risk_manager.check_total_exposure(
                total_position_value=portfolio.total_position_value,
                proposed_trade_value=order.quantity * filled_price,
                portfolio_value=portfolio.total_equity,
            )
            if not allowed:
                order.status = OrderStatus.REJECTED
                order.reject_reason = reason
                logger.warning(f"订单被拒绝: {order.order_id} - {reason}")
                return order

        # 执行交易
        order.filled_price = filled_price
        order.commission = commission

        if order.side == OrderSide.BUY:
            success = portfolio.buy(
                symbol=order.symbol,
                quantity=order.quantity,
                price=filled_price,
                commission=commission,
                date=order.date,
            )
        else:
            success = portfolio.sell(
                symbol=order.symbol,
                quantity=order.quantity,
                price=filled_price,
                commission=commission,
                date=order.date,
            )

        if success:
            order.status = OrderStatus.FILLED
            order.filled_quantity = order.quantity
            logger.info(
                f"订单成交: {order.order_id} {order.side.value} "
                f"{order.symbol} {order.quantity}股 @ {filled_price:.2f}"
            )
        else:
            order.status = OrderStatus.REJECTED
            order.reject_reason = "交易执行失败（资金或持仓不足）"

        return order

    def get_filled_orders(self) -> list[Order]:
        """获取已成交订单列表。"""
        return [o for o in self.order_history if o.status == OrderStatus.FILLED]

    def get_rejected_orders(self) -> list[Order]:
        """获取被拒绝的订单列表。"""
        return [o for o in self.order_history if o.status == OrderStatus.REJECTED]

    def reset(self):
        """重置订单历史。"""
        self.order_history.clear()
