"""
MACD策略 (Moving Average Convergence Divergence Strategy)

基于MACD指标的趋势确认策略：
- MACD柱状图由负转正 → 买入信号
- MACD柱状图由正转负 → 卖出信号
"""

import pandas as pd

from quant_agent.data.indicators import TechnicalIndicators
from .base import BaseStrategy, Signal, SignalType


class MACDStrategy(BaseStrategy):
    """
    MACD策略

    利用MACD柱状图的零轴穿越和MACD与信号线的交叉产生交易信号。
    """

    def __init__(
        self,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
        weight: float = 1.0,
    ):
        """
        初始化MACD策略。

        Args:
            fast_period: 快线周期
            slow_period: 慢线周期
            signal_period: 信号线周期
            weight: 策略权重
        """
        super().__init__(name="MACD", weight=weight)
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period

    def generate_signals(
        self, data: pd.DataFrame, symbol: str
    ) -> list[Signal]:
        """
        根据MACD柱状图零轴穿越生成交易信号。

        柱状图由负转正（MACD上穿信号线）产生买入信号，
        柱状图由正转负（MACD下穿信号线）产生卖出信号。
        信号强度与柱状图的绝对值成正比。

        Args:
            data: 包含OHLCV数据的DataFrame
            symbol: 股票代码

        Returns:
            交易信号列表
        """
        self.validate_data(data, ["close"])

        macd_line, signal_line, histogram = TechnicalIndicators.macd(
            data["close"], self.fast_period, self.slow_period, self.signal_period
        )

        signals = []

        # 计算柱状图的标准化因子（用于计算信号强度）
        hist_std = histogram.dropna().std()
        if hist_std == 0 or pd.isna(hist_std):
            hist_std = 1.0

        for i in range(1, len(data)):
            if (
                pd.isna(histogram.iloc[i])
                or pd.isna(histogram.iloc[i - 1])
            ):
                continue

            prev_hist = histogram.iloc[i - 1]
            curr_hist = histogram.iloc[i]

            # 信号强度基于柱状图大小
            strength = min(abs(curr_hist) / hist_std, 1.0)

            if prev_hist <= 0 and curr_hist > 0:
                # MACD柱状图由负转正
                signals.append(
                    Signal(
                        signal_type=SignalType.BUY,
                        strength=strength,
                        symbol=symbol,
                        strategy_name=self.name,
                        reason=f"MACD金叉: 柱状图由负转正 ({prev_hist:.4f} → {curr_hist:.4f})",
                        metadata={
                            "macd": round(macd_line.iloc[i], 4),
                            "signal": round(signal_line.iloc[i], 4),
                            "histogram": round(curr_hist, 4),
                            "date": str(data.index[i]),
                        },
                    )
                )
            elif prev_hist >= 0 and curr_hist < 0:
                # MACD柱状图由正转负
                signals.append(
                    Signal(
                        signal_type=SignalType.SELL,
                        strength=-strength,
                        symbol=symbol,
                        strategy_name=self.name,
                        reason=f"MACD死叉: 柱状图由正转负 ({prev_hist:.4f} → {curr_hist:.4f})",
                        metadata={
                            "macd": round(macd_line.iloc[i], 4),
                            "signal": round(signal_line.iloc[i], 4),
                            "histogram": round(curr_hist, 4),
                            "date": str(data.index[i]),
                        },
                    )
                )

        return signals
