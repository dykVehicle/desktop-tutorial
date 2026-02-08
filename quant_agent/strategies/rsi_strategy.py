"""
RSI策略 (Relative Strength Index Strategy)

基于相对强弱指标的反转策略：
- RSI < 超卖线 → 买入信号（超卖反弹）
- RSI > 超买线 → 卖出信号（超买回调）
"""

import pandas as pd

from quant_agent.data.indicators import TechnicalIndicators
from .base import BaseStrategy, Signal, SignalType


class RSIStrategy(BaseStrategy):
    """
    RSI策略

    利用RSI指标的超买超卖区域产生交易信号。
    """

    def __init__(
        self,
        period: int = 14,
        overbought: float = 70.0,
        oversold: float = 30.0,
        weight: float = 1.0,
    ):
        """
        初始化RSI策略。

        Args:
            period: RSI计算周期
            overbought: 超买阈值（默认70）
            oversold: 超卖阈值（默认30）
            weight: 策略权重
        """
        super().__init__(name="RSI", weight=weight)
        self.period = period
        self.overbought = overbought
        self.oversold = oversold

    def generate_signals(
        self, data: pd.DataFrame, symbol: str
    ) -> list[Signal]:
        """
        根据RSI超买超卖生成交易信号。

        当RSI从超卖区域回升时产生买入信号，
        从超买区域回落时产生卖出信号。
        信号强度与RSI偏离中心值50的程度成正比。

        Args:
            data: 包含OHLCV数据的DataFrame
            symbol: 股票代码

        Returns:
            交易信号列表
        """
        self.validate_data(data, ["close"])

        rsi = TechnicalIndicators.rsi(data["close"], self.period)
        signals = []

        for i in range(1, len(data)):
            if pd.isna(rsi.iloc[i]) or pd.isna(rsi.iloc[i - 1]):
                continue

            current_rsi = rsi.iloc[i]
            prev_rsi = rsi.iloc[i - 1]

            if prev_rsi <= self.oversold and current_rsi > self.oversold:
                # RSI从超卖区域回升
                strength = (self.oversold - min(prev_rsi, self.oversold)) / self.oversold
                strength = min(max(strength, 0.3), 1.0)
                signals.append(
                    Signal(
                        signal_type=SignalType.BUY,
                        strength=strength,
                        symbol=symbol,
                        strategy_name=self.name,
                        reason=f"RSI超卖反弹: {prev_rsi:.1f} → {current_rsi:.1f}",
                        metadata={
                            "rsi": round(current_rsi, 2),
                            "prev_rsi": round(prev_rsi, 2),
                            "date": str(data.index[i]),
                        },
                    )
                )
            elif prev_rsi >= self.overbought and current_rsi < self.overbought:
                # RSI从超买区域回落
                strength = (max(prev_rsi, self.overbought) - self.overbought) / (
                    100 - self.overbought
                )
                strength = min(max(strength, 0.3), 1.0)
                signals.append(
                    Signal(
                        signal_type=SignalType.SELL,
                        strength=-strength,
                        symbol=symbol,
                        strategy_name=self.name,
                        reason=f"RSI超买回调: {prev_rsi:.1f} → {current_rsi:.1f}",
                        metadata={
                            "rsi": round(current_rsi, 2),
                            "prev_rsi": round(prev_rsi, 2),
                            "date": str(data.index[i]),
                        },
                    )
                )

        return signals
