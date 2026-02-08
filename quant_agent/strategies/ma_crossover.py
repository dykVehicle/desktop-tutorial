"""
均线交叉策略 (Moving Average Crossover Strategy)

经典的趋势跟踪策略：
- 短期均线上穿长期均线 → 买入信号
- 短期均线下穿长期均线 → 卖出信号
"""

import pandas as pd

from quant_agent.data.indicators import TechnicalIndicators
from .base import BaseStrategy, Signal, SignalType


class MACrossoverStrategy(BaseStrategy):
    """
    均线交叉策略

    通过短期和长期移动平均线的交叉产生交易信号。
    """

    def __init__(
        self,
        short_window: int = 10,
        long_window: int = 30,
        weight: float = 1.0,
    ):
        """
        初始化均线交叉策略。

        Args:
            short_window: 短期均线周期
            long_window: 长期均线周期
            weight: 策略权重
        """
        super().__init__(name="MA_Crossover", weight=weight)
        self.short_window = short_window
        self.long_window = long_window

    def generate_signals(
        self, data: pd.DataFrame, symbol: str
    ) -> list[Signal]:
        """
        根据均线交叉生成交易信号（含趋势过滤）。

        金叉（短期上穿长期）产生买入信号，
        死叉（短期下穿长期）产生卖出信号。
        增加趋势过滤: 使用60日均线判断大趋势方向，
        只在趋势顺方向时发出信号，减少震荡市的假信号。

        Args:
            data: 包含OHLCV数据的DataFrame
            symbol: 股票代码

        Returns:
            交易信号列表
        """
        self.validate_data(data, ["close"])

        ti = TechnicalIndicators
        short_ma = ti.sma(data["close"], self.short_window)
        long_ma = ti.sma(data["close"], self.long_window)
        # 趋势过滤: 用更长周期均线判断大方向
        trend_period = max(self.long_window * 2, 60)
        trend_ma = ti.sma(data["close"], trend_period)

        signals = []

        for i in range(1, len(data)):
            if (
                pd.isna(short_ma.iloc[i])
                or pd.isna(long_ma.iloc[i])
                or pd.isna(short_ma.iloc[i - 1])
                or pd.isna(long_ma.iloc[i - 1])
            ):
                continue

            prev_diff = short_ma.iloc[i - 1] - long_ma.iloc[i - 1]
            curr_diff = short_ma.iloc[i] - long_ma.iloc[i]

            # 计算信号强度（基于均线间距与价格的比值）
            price = data["close"].iloc[i]
            strength = abs(curr_diff) / price if price > 0 else 0
            # 放大因子: 1%的均线间距 → 强度0.5，2% → 1.0
            strength = min(strength * 50, 1.0)

            # 趋势判断: 价格在趋势均线之上=上升趋势，反之下降趋势
            has_trend_filter = not pd.isna(trend_ma.iloc[i])
            is_uptrend = has_trend_filter and price > trend_ma.iloc[i]
            is_downtrend = has_trend_filter and price < trend_ma.iloc[i]

            if prev_diff <= 0 and curr_diff > 0:
                # 金叉: 短期均线上穿长期均线
                # 趋势过滤: 上升趋势中的金叉更可靠
                if has_trend_filter and not is_uptrend:
                    strength *= 0.3  # 逆势信号大幅减弱
                signals.append(
                    Signal(
                        signal_type=SignalType.BUY,
                        strength=strength,
                        symbol=symbol,
                        strategy_name=self.name,
                        reason=f"金叉: SMA{self.short_window}上穿SMA{self.long_window}"
                        + ("（顺势）" if is_uptrend else "（逆势）"),
                        metadata={
                            "short_ma": round(short_ma.iloc[i], 2),
                            "long_ma": round(long_ma.iloc[i], 2),
                            "trend": "up" if is_uptrend else "down",
                            "date": str(data.index[i]),
                        },
                    )
                )
            elif prev_diff >= 0 and curr_diff < 0:
                # 死叉: 短期均线下穿长期均线
                if has_trend_filter and not is_downtrend:
                    strength *= 0.3  # 逆势信号大幅减弱
                signals.append(
                    Signal(
                        signal_type=SignalType.SELL,
                        strength=-strength,
                        symbol=symbol,
                        strategy_name=self.name,
                        reason=f"死叉: SMA{self.short_window}下穿SMA{self.long_window}"
                        + ("（顺势）" if is_downtrend else "（逆势）"),
                        metadata={
                            "short_ma": round(short_ma.iloc[i], 2),
                            "long_ma": round(long_ma.iloc[i], 2),
                            "trend": "up" if is_uptrend else "down",
                            "date": str(data.index[i]),
                        },
                    )
                )

        return signals
