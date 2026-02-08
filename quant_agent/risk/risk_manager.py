"""
风险管理模块

提供全面的风险控制功能：
- 仓位大小控制
- 止损止盈管理
- 最大回撤限制
- 单日亏损限制
- 风险度量（VaR等）
"""

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from quant_agent.utils.logger import get_logger

logger = get_logger("quant_agent.risk")


@dataclass
class RiskLimits:
    """
    风险限制参数

    Attributes:
        max_position_pct: 单个标的最大仓位占比
        max_total_position_pct: 总仓位最大占比
        stop_loss_pct: 止损比例
        take_profit_pct: 止盈比例
        max_drawdown_pct: 最大回撤限制
        max_daily_loss_pct: 单日最大亏损比例
    """
    max_position_pct: float = 0.25
    max_total_position_pct: float = 0.7
    stop_loss_pct: float = 0.07       # 止损放宽到7%，减少假止损
    take_profit_pct: float = 0.10     # 止盈缩到10%，更容易触发
    max_drawdown_pct: float = 0.20
    max_daily_loss_pct: float = 0.03


class RiskManager:
    """
    风险管理器

    负责交易前的风险检查和仓位控制，确保交易符合风控要求。
    """

    def __init__(self, limits: Optional[RiskLimits] = None):
        """
        初始化风险管理器。

        Args:
            limits: 风险限制参数，如果为None则使用默认值
        """
        self.limits = limits or RiskLimits()
        self._peak_equity = 0.0
        self._daily_pnl = 0.0
        self._daily_start_equity = 0.0

    def check_position_size(
        self,
        symbol: str,
        proposed_quantity: int,
        price: float,
        current_portfolio_value: float,
        current_position_value: float = 0.0,
    ) -> tuple[bool, int, str]:
        """
        检查拟建仓位大小是否符合风控要求。

        Args:
            symbol: 股票代码
            proposed_quantity: 拟买入数量
            price: 当前价格
            current_portfolio_value: 当前组合总价值
            current_position_value: 该标的当前持仓市值

        Returns:
            (是否允许, 调整后的数量, 原因说明)
        """
        if current_portfolio_value <= 0:
            return False, 0, "投资组合价值为零"

        proposed_value = proposed_quantity * price
        new_position_value = current_position_value + proposed_value
        position_pct = new_position_value / current_portfolio_value

        if position_pct > self.limits.max_position_pct:
            # 计算允许的最大买入数量
            max_value = (
                self.limits.max_position_pct * current_portfolio_value
                - current_position_value
            )
            if max_value <= 0:
                return False, 0, f"{symbol} 仓位已达上限 ({self.limits.max_position_pct:.0%})"

            adjusted_quantity = int(max_value / price)
            if adjusted_quantity <= 0:
                return False, 0, f"{symbol} 仓位已达上限"

            logger.warning(
                f"仓位限制: {symbol} 数量从 {proposed_quantity} 调整至 {adjusted_quantity}"
            )
            return True, adjusted_quantity, f"仓位限制: 数量调整至 {adjusted_quantity}"

        return True, proposed_quantity, "通过"

    def check_total_exposure(
        self,
        total_position_value: float,
        proposed_trade_value: float,
        portfolio_value: float,
    ) -> tuple[bool, str]:
        """
        检查总仓位暴露是否超过限制。

        Args:
            total_position_value: 当前总持仓市值
            proposed_trade_value: 拟交易金额
            portfolio_value: 组合总价值

        Returns:
            (是否允许, 原因说明)
        """
        if portfolio_value <= 0:
            return False, "投资组合价值为零"

        new_total = total_position_value + proposed_trade_value
        exposure = new_total / portfolio_value

        if exposure > self.limits.max_total_position_pct:
            return (
                False,
                f"总仓位暴露 {exposure:.1%} 超过限制 {self.limits.max_total_position_pct:.0%}",
            )
        return True, "通过"

    def check_stop_loss(
        self, entry_price: float, current_price: float
    ) -> tuple[bool, str]:
        """
        检查是否触发止损。

        Args:
            entry_price: 建仓价格
            current_price: 当前价格

        Returns:
            (是否触发止损, 原因说明)
        """
        if entry_price <= 0:
            return False, "建仓价格无效"

        loss_pct = (entry_price - current_price) / entry_price
        if loss_pct >= self.limits.stop_loss_pct:
            return (
                True,
                f"触发止损: 亏损 {loss_pct:.2%} >= {self.limits.stop_loss_pct:.0%}",
            )
        return False, "未触发止损"

    def check_take_profit(
        self, entry_price: float, current_price: float
    ) -> tuple[bool, str]:
        """
        检查是否触发止盈。

        Args:
            entry_price: 建仓价格
            current_price: 当前价格

        Returns:
            (是否触发止盈, 原因说明)
        """
        if entry_price <= 0:
            return False, "建仓价格无效"

        profit_pct = (current_price - entry_price) / entry_price
        if profit_pct >= self.limits.take_profit_pct:
            return (
                True,
                f"触发止盈: 盈利 {profit_pct:.2%} >= {self.limits.take_profit_pct:.0%}",
            )
        return False, "未触发止盈"

    def check_trailing_stop(
        self,
        entry_price: float,
        current_price: float,
        highest_price: float,
        trailing_pct: float = 0.05,
        activation_pct: float = 0.03,
    ) -> tuple[bool, str]:
        """
        检查是否触发移动止损。

        当盈利超过 activation_pct 后激活移动止损：
        如果价格从最高点回落超过 trailing_pct，则平仓锁定利润。

        Args:
            entry_price: 建仓价格
            current_price: 当前价格
            highest_price: 持仓期间最高价
            trailing_pct: 从最高点回撤多少触发 (默认5%)
            activation_pct: 盈利多少后激活移动止损 (默认3%)

        Returns:
            (是否触发, 原因说明)
        """
        if entry_price <= 0 or highest_price <= 0:
            return False, "价格无效"

        # 只有盈利超过激活阈值后才启用移动止损
        profit_from_entry = (highest_price - entry_price) / entry_price
        if profit_from_entry < activation_pct:
            return False, "未达到移动止损激活条件"

        # 从最高点的回撤
        pullback = (highest_price - current_price) / highest_price
        if pullback >= trailing_pct:
            return (
                True,
                f"触发移动止损: 从高点 {highest_price:.2f} 回撤 {pullback:.2%} >= {trailing_pct:.0%}",
            )
        return False, "未触发移动止损"

    def check_max_drawdown(self, current_equity: float) -> tuple[bool, str]:
        """
        检查是否触发最大回撤限制。

        Args:
            current_equity: 当前权益

        Returns:
            (是否触发回撤限制, 原因说明)
        """
        if current_equity > self._peak_equity:
            self._peak_equity = current_equity

        if self._peak_equity <= 0:
            return False, "权益数据无效"

        drawdown = (self._peak_equity - current_equity) / self._peak_equity
        if drawdown >= self.limits.max_drawdown_pct:
            return (
                True,
                f"触发最大回撤限制: 回撤 {drawdown:.2%} >= {self.limits.max_drawdown_pct:.0%}",
            )
        return False, f"当前回撤: {drawdown:.2%}"

    def check_daily_loss(
        self, current_equity: float, start_equity: float
    ) -> tuple[bool, str]:
        """
        检查是否触发单日最大亏损限制。

        Args:
            current_equity: 当前权益
            start_equity: 当日开盘权益

        Returns:
            (是否触发限制, 原因说明)
        """
        if start_equity <= 0:
            return False, "起始权益无效"

        daily_loss = (start_equity - current_equity) / start_equity
        if daily_loss >= self.limits.max_daily_loss_pct:
            return (
                True,
                f"触发单日亏损限制: 日亏 {daily_loss:.2%} >= {self.limits.max_daily_loss_pct:.0%}",
            )
        return False, f"当日盈亏: {-daily_loss:.2%}"

    def calculate_position_size(
        self,
        portfolio_value: float,
        price: float,
        signal_strength: float,
        atr: Optional[float] = None,
    ) -> int:
        """
        基于信号强度和波动率计算建议仓位大小。

        使用Kelly公式的简化版本结合ATR进行仓位计算。

        Args:
            portfolio_value: 组合总价值
            price: 当前价格
            signal_strength: 信号强度 (0-1)
            atr: 平均真实波幅（可选，用于波动率调整）

        Returns:
            建议买入数量
        """
        if portfolio_value <= 0 or price <= 0:
            return 0

        # 基础仓位比例：信号强度 * 最大仓位比例
        base_pct = abs(signal_strength) * self.limits.max_position_pct

        # ATR波动率调整：波动率越大，仓位越小
        if atr is not None and atr > 0:
            volatility_factor = min(price / (atr * 20), 1.5)
            base_pct *= min(volatility_factor, 1.0)

        # 计算金额和数量
        position_value = portfolio_value * base_pct
        quantity = int(position_value / price)

        return max(quantity, 0)

    def update_peak_equity(self, equity: float):
        """更新权益峰值。"""
        if equity > self._peak_equity:
            self._peak_equity = equity

    def reset(self):
        """重置风控管理器状态。"""
        self._peak_equity = 0.0
        self._daily_pnl = 0.0
        self._daily_start_equity = 0.0

    @staticmethod
    def calculate_var(
        returns: pd.Series, confidence: float = 0.95
    ) -> float:
        """
        计算历史VaR (Value at Risk)。

        Args:
            returns: 收益率序列
            confidence: 置信水平

        Returns:
            VaR值（正数表示亏损）
        """
        if len(returns) == 0:
            return 0.0
        return -float(np.percentile(returns.dropna(), (1 - confidence) * 100))

    @staticmethod
    def calculate_max_drawdown(equity_curve: pd.Series) -> float:
        """
        计算最大回撤。

        Args:
            equity_curve: 权益曲线

        Returns:
            最大回撤比例（0到1之间）
        """
        if len(equity_curve) == 0:
            return 0.0

        peak = equity_curve.expanding().max()
        drawdown = (peak - equity_curve) / peak
        return float(drawdown.max())
