"""
技术指标计算模块

提供常用的技术指标计算功能，包括：
- 移动平均线 (SMA, EMA)
- RSI (相对强弱指标)
- MACD (指数平滑异同移动平均线)
- 布林带 (Bollinger Bands)
- ATR (平均真实波幅)
"""

import numpy as np
import pandas as pd
from typing import Optional


class TechnicalIndicators:
    """技术指标计算器"""

    @staticmethod
    def sma(series: pd.Series, period: int) -> pd.Series:
        """
        简单移动平均线 (Simple Moving Average)

        Args:
            series: 价格序列
            period: 周期

        Returns:
            SMA序列
        """
        return series.rolling(window=period, min_periods=period).mean()

    @staticmethod
    def ema(series: pd.Series, period: int) -> pd.Series:
        """
        指数移动平均线 (Exponential Moving Average)

        Args:
            series: 价格序列
            period: 周期

        Returns:
            EMA序列
        """
        return series.ewm(span=period, adjust=False).mean()

    @staticmethod
    def rsi(series: pd.Series, period: int = 14) -> pd.Series:
        """
        相对强弱指标 (Relative Strength Index)

        Args:
            series: 价格序列
            period: 计算周期，默认14

        Returns:
            RSI序列 (0-100)
        """
        delta = series.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)

        avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
        avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    @staticmethod
    def macd(
        series: pd.Series,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
    ) -> tuple[pd.Series, pd.Series, pd.Series]:
        """
        MACD指标 (Moving Average Convergence Divergence)

        Args:
            series: 价格序列
            fast_period: 快线周期，默认12
            slow_period: 慢线周期，默认26
            signal_period: 信号线周期，默认9

        Returns:
            (macd_line, signal_line, histogram) 三元组
        """
        ema_fast = series.ewm(span=fast_period, adjust=False).mean()
        ema_slow = series.ewm(span=slow_period, adjust=False).mean()

        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
        histogram = macd_line - signal_line

        return macd_line, signal_line, histogram

    @staticmethod
    def bollinger_bands(
        series: pd.Series, period: int = 20, std_dev: float = 2.0
    ) -> tuple[pd.Series, pd.Series, pd.Series]:
        """
        布林带 (Bollinger Bands)

        Args:
            series: 价格序列
            period: 周期，默认20
            std_dev: 标准差倍数，默认2.0

        Returns:
            (upper_band, middle_band, lower_band) 三元组
        """
        middle = series.rolling(window=period).mean()
        std = series.rolling(window=period).std()
        upper = middle + std_dev * std
        lower = middle - std_dev * std

        return upper, middle, lower

    @staticmethod
    def atr(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        period: int = 14,
    ) -> pd.Series:
        """
        平均真实波幅 (Average True Range)

        Args:
            high: 最高价序列
            low: 最低价序列
            close: 收盘价序列
            period: 周期，默认14

        Returns:
            ATR序列
        """
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()

        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = true_range.rolling(window=period).mean()

        return atr

    @staticmethod
    def compute_all(
        df: pd.DataFrame,
        sma_periods: Optional[list[int]] = None,
        rsi_period: int = 14,
        macd_params: Optional[tuple[int, int, int]] = None,
        bb_period: int = 20,
        atr_period: int = 14,
    ) -> pd.DataFrame:
        """
        计算所有技术指标并添加到DataFrame中。

        Args:
            df: 包含OHLCV数据的DataFrame
            sma_periods: SMA周期列表，默认[10, 20, 30, 60]
            rsi_period: RSI周期
            macd_params: MACD参数 (fast, slow, signal)
            bb_period: 布林带周期
            atr_period: ATR周期

        Returns:
            添加了技术指标的DataFrame
        """
        result = df.copy()
        ti = TechnicalIndicators

        # 移动平均线
        if sma_periods is None:
            sma_periods = [10, 20, 30, 60]
        for period in sma_periods:
            result[f"sma_{period}"] = ti.sma(result["close"], period)
            result[f"ema_{period}"] = ti.ema(result["close"], period)

        # RSI
        result["rsi"] = ti.rsi(result["close"], rsi_period)

        # MACD
        if macd_params is None:
            macd_params = (12, 26, 9)
        macd_line, signal_line, histogram = ti.macd(
            result["close"], *macd_params
        )
        result["macd"] = macd_line
        result["macd_signal"] = signal_line
        result["macd_hist"] = histogram

        # 布林带
        upper, middle, lower = ti.bollinger_bands(result["close"], bb_period)
        result["bb_upper"] = upper
        result["bb_middle"] = middle
        result["bb_lower"] = lower

        # ATR
        result["atr"] = ti.atr(
            result["high"], result["low"], result["close"], atr_period
        )

        return result
