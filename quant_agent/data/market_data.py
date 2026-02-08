"""
市场数据模块

提供市场数据获取、生成和管理功能。
支持合成数据（用于测试）和CSV文件数据源。
"""

import numpy as np
import pandas as pd
from typing import Optional
from datetime import datetime, timedelta

from quant_agent.utils.logger import get_logger

logger = get_logger("quant_agent.data")


class MarketDataProvider:
    """
    市场数据提供者

    支持多种数据源：
    - synthetic: 合成随机数据（用于测试和演示）
    - csv: 从CSV文件加载
    """

    def __init__(self, source: str = "synthetic"):
        """
        初始化市场数据提供者。

        Args:
            source: 数据源类型 ("synthetic" | "csv")
        """
        self.source = source
        self._cache: dict[str, pd.DataFrame] = {}

    def get_data(
        self,
        symbol: str,
        start_date: str = "2024-01-01",
        end_date: str = "2025-12-31",
        frequency: str = "daily",
    ) -> pd.DataFrame:
        """
        获取市场数据。

        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            frequency: 数据频率

        Returns:
            包含OHLCV数据的DataFrame
        """
        cache_key = f"{symbol}_{start_date}_{end_date}_{frequency}"
        if cache_key in self._cache:
            return self._cache[cache_key].copy()

        if self.source == "synthetic":
            data = self._generate_synthetic_data(symbol, start_date, end_date)
        elif self.source == "csv":
            data = self._load_csv_data(symbol)
        else:
            raise ValueError(f"不支持的数据源: {self.source}")

        self._cache[cache_key] = data
        logger.info(f"获取 {symbol} 数据: {len(data)} 条记录 ({start_date} ~ {end_date})")
        return data.copy()

    def _generate_synthetic_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """
        生成合成的OHLCV数据。

        使用几何布朗运动模拟股价走势，确保数据具有
        一定的趋势性和波动性，适合策略回测。

        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            合成的OHLCV数据
        """
        # 使用symbol的hash作为随机种子，确保同一symbol生成相同数据
        seed = hash(symbol) % (2**31)
        rng = np.random.RandomState(seed)

        # 生成交易日序列
        dates = pd.bdate_range(start=start_date, end=end_date)

        n_days = len(dates)
        if n_days == 0:
            return pd.DataFrame(
                columns=["date", "open", "high", "low", "close", "volume", "symbol"]
            )

        # 基础价格参数
        initial_price = 50.0 + rng.random() * 150.0  # 50-200之间
        mu = 0.0002  # 日收益率均值（年化约5%）
        sigma = 0.02  # 日波动率（年化约32%）

        # 生成几何布朗运动的收益率
        daily_returns = rng.normal(mu, sigma, n_days)

        # 添加一些趋势段（模拟真实市场的趋势特征）
        trend_periods = rng.randint(3, 8)
        period_length = n_days // trend_periods
        for i in range(trend_periods):
            start_idx = i * period_length
            end_idx = min((i + 1) * period_length, n_days)
            trend = rng.uniform(-0.001, 0.001)
            daily_returns[start_idx:end_idx] += trend

        # 计算收盘价
        price_series = initial_price * np.exp(np.cumsum(daily_returns))

        # 生成OHLCV数据
        opens = np.zeros(n_days)
        highs = np.zeros(n_days)
        lows = np.zeros(n_days)
        closes = price_series
        volumes = np.zeros(n_days)

        for i in range(n_days):
            intraday_range = closes[i] * rng.uniform(0.005, 0.03)
            opens[i] = closes[i] + rng.uniform(-intraday_range / 2, intraday_range / 2)
            highs[i] = max(opens[i], closes[i]) + rng.uniform(0, intraday_range / 2)
            lows[i] = min(opens[i], closes[i]) - rng.uniform(0, intraday_range / 2)
            # 确保 high >= open, close 且 low <= open, close
            highs[i] = max(highs[i], opens[i], closes[i])
            lows[i] = min(lows[i], opens[i], closes[i])
            # 成交量：与价格变动幅度正相关
            base_volume = 1000000
            volatility_factor = abs(closes[i] - opens[i]) / closes[i]
            volumes[i] = int(base_volume * (1 + volatility_factor * 20) * rng.uniform(0.5, 1.5))

        df = pd.DataFrame(
            {
                "date": dates,
                "open": np.round(opens, 2),
                "high": np.round(highs, 2),
                "low": np.round(lows, 2),
                "close": np.round(closes, 2),
                "volume": volumes.astype(int),
                "symbol": symbol,
            }
        )
        df = df.set_index("date")
        return df

    def _load_csv_data(self, symbol: str) -> pd.DataFrame:
        """
        从CSV文件加载数据。

        Args:
            symbol: 股票代码（用于查找对应的CSV文件）

        Returns:
            OHLCV数据

        Raises:
            FileNotFoundError: 找不到数据文件
        """
        file_path = f"data/{symbol}.csv"
        try:
            df = pd.read_csv(file_path, parse_dates=["date"])
            df = df.set_index("date")
            df["symbol"] = symbol
            return df
        except FileNotFoundError:
            raise FileNotFoundError(f"找不到数据文件: {file_path}")

    def get_multiple_data(
        self,
        symbols: list[str],
        start_date: str = "2024-01-01",
        end_date: str = "2025-12-31",
        frequency: str = "daily",
    ) -> dict[str, pd.DataFrame]:
        """
        获取多个标的的市场数据。

        Args:
            symbols: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            frequency: 数据频率

        Returns:
            {symbol: DataFrame} 字典
        """
        result = {}
        for symbol in symbols:
            result[symbol] = self.get_data(symbol, start_date, end_date, frequency)
        return result

    def clear_cache(self):
        """清除数据缓存。"""
        self._cache.clear()
        logger.info("数据缓存已清除")
