"""
策略基类模块

定义交易策略的基础接口和数据结构。
所有具体策略必须继承BaseStrategy并实现generate_signals方法。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import pandas as pd


class SignalType(Enum):
    """交易信号类型"""
    BUY = "buy"        # 买入信号
    SELL = "sell"      # 卖出信号
    HOLD = "hold"      # 持有/观望


@dataclass
class Signal:
    """
    交易信号

    Attributes:
        signal_type: 信号类型 (BUY/SELL/HOLD)
        strength: 信号强度 (-1.0到1.0, 正值看多, 负值看空)
        symbol: 股票代码
        strategy_name: 产生信号的策略名称
        reason: 信号产生原因
        metadata: 附加信息
    """
    signal_type: SignalType
    strength: float  # -1.0 to 1.0
    symbol: str
    strategy_name: str
    reason: str = ""
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        """验证信号强度范围"""
        self.strength = max(-1.0, min(1.0, self.strength))


class BaseStrategy(ABC):
    """
    交易策略基类

    所有策略必须继承此类并实现 generate_signals 方法。

    Attributes:
        name: 策略名称
        weight: 策略权重（用于信号融合）
    """

    def __init__(self, name: str, weight: float = 1.0):
        """
        初始化策略。

        Args:
            name: 策略名称
            weight: 策略权重
        """
        self.name = name
        self.weight = weight
        self._is_initialized = False

    @abstractmethod
    def generate_signals(
        self, data: pd.DataFrame, symbol: str
    ) -> list[Signal]:
        """
        根据市场数据生成交易信号。

        Args:
            data: 包含OHLCV和技术指标的DataFrame
            symbol: 股票代码

        Returns:
            交易信号列表（按时间顺序）
        """
        pass

    def generate_latest_signal(
        self, data: pd.DataFrame, symbol: str
    ) -> Signal:
        """
        生成最新的交易信号（仅返回最后一个）。

        Args:
            data: 包含OHLCV和技术指标的DataFrame
            symbol: 股票代码

        Returns:
            最新的交易信号
        """
        signals = self.generate_signals(data, symbol)
        if signals:
            return signals[-1]
        return Signal(
            signal_type=SignalType.HOLD,
            strength=0.0,
            symbol=symbol,
            strategy_name=self.name,
            reason="无信号",
        )

    def validate_data(self, data: pd.DataFrame, required_columns: list[str]) -> bool:
        """
        验证数据是否包含必要的列。

        Args:
            data: 待验证的DataFrame
            required_columns: 必要的列名列表

        Returns:
            验证是否通过
        """
        missing = [col for col in required_columns if col not in data.columns]
        if missing:
            raise ValueError(
                f"策略 {self.name} 缺少必要的数据列: {missing}"
            )
        return True

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}', weight={self.weight})"
