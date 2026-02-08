"""
交易引擎模块

事件驱动的交易引擎，协调数据、策略、风控和执行各模块。
"""

from typing import Optional

import yaml
import pandas as pd

from quant_agent.data.market_data import MarketDataProvider
from quant_agent.data.indicators import TechnicalIndicators
from quant_agent.strategies.base import BaseStrategy
from quant_agent.risk.risk_manager import RiskManager, RiskLimits
from quant_agent.portfolio.portfolio import Portfolio
from quant_agent.execution.executor import OrderExecutor
from quant_agent.backtest.backtester import Backtester, BacktestResult
from quant_agent.utils.logger import get_logger

logger = get_logger("quant_agent.engine")


class TradingEngine:
    """
    交易引擎

    负责协调各模块工作，提供统一的交易接口。
    支持回测和模拟交易两种模式。
    """

    def __init__(self, config: Optional[dict] = None):
        """
        初始化交易引擎。

        Args:
            config: 配置字典，如果为None则使用默认配置
        """
        self.config = config or self._default_config()
        self._setup_components()

    def _default_config(self) -> dict:
        """返回默认配置。"""
        return {
            "engine": {
                "mode": "backtest",
                "initial_capital": 1000000.0,
                "commission_rate": 0.001,
                "slippage": 0.001,
            },
            "data": {
                "source": "synthetic",
                "symbols": ["000001.SZ", "600519.SH"],
                "start_date": "2024-01-01",
                "end_date": "2025-12-31",
                "frequency": "daily",
            },
            "risk": {
                "max_position_pct": 0.3,
                "max_total_position_pct": 0.8,
                "stop_loss_pct": 0.05,
                "take_profit_pct": 0.15,
                "max_drawdown_pct": 0.15,
                "max_daily_loss_pct": 0.03,
            },
            "agent": {
                "signal_threshold": 0.3,
            },
        }

    def _setup_components(self):
        """初始化各组件。"""
        engine_config = self.config.get("engine", {})
        risk_config = self.config.get("risk", {})

        self.data_provider = MarketDataProvider(
            source=self.config.get("data", {}).get("source", "synthetic")
        )

        self.risk_limits = RiskLimits(
            max_position_pct=risk_config.get("max_position_pct", 0.3),
            max_total_position_pct=risk_config.get("max_total_position_pct", 0.8),
            stop_loss_pct=risk_config.get("stop_loss_pct", 0.05),
            take_profit_pct=risk_config.get("take_profit_pct", 0.15),
            max_drawdown_pct=risk_config.get("max_drawdown_pct", 0.15),
            max_daily_loss_pct=risk_config.get("max_daily_loss_pct", 0.03),
        )

        self.backtester = Backtester(
            initial_capital=engine_config.get("initial_capital", 1000000.0),
            commission_rate=engine_config.get("commission_rate", 0.001),
            slippage=engine_config.get("slippage", 0.001),
            risk_limits=self.risk_limits,
        )

        self.strategies: list[BaseStrategy] = []

    @classmethod
    def from_config_file(cls, config_path: str) -> "TradingEngine":
        """
        从配置文件创建交易引擎。

        Args:
            config_path: YAML配置文件路径

        Returns:
            TradingEngine实例
        """
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        return cls(config)

    def add_strategy(self, strategy: BaseStrategy):
        """
        添加交易策略。

        Args:
            strategy: 策略实例
        """
        self.strategies.append(strategy)
        logger.info(f"添加策略: {strategy}")

    def run_backtest(
        self,
        symbols: Optional[list[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> BacktestResult:
        """
        运行回测。

        Args:
            symbols: 股票代码列表（默认使用配置中的）
            start_date: 起始日期（默认使用配置中的）
            end_date: 结束日期（默认使用配置中的）

        Returns:
            回测结果
        """
        if not self.strategies:
            raise ValueError("请先添加至少一个策略")

        data_config = self.config.get("data", {})
        symbols = symbols or data_config.get("symbols", ["000001.SZ"])
        start_date = start_date or data_config.get("start_date", "2024-01-01")
        end_date = end_date or data_config.get("end_date", "2025-12-31")

        # 获取数据
        logger.info(f"获取市场数据: {symbols}, {start_date} ~ {end_date}")
        data_dict = self.data_provider.get_multiple_data(
            symbols, start_date, end_date
        )

        # 获取信号阈值
        signal_threshold = self.config.get("agent", {}).get("signal_threshold", 0.3)

        # 运行回测
        result = self.backtester.run(
            strategies=self.strategies,
            data_dict=data_dict,
            signal_threshold=signal_threshold,
        )

        return result

    def get_market_data(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        获取市场数据。

        Args:
            symbol: 股票代码
            start_date: 起始日期
            end_date: 结束日期

        Returns:
            市场数据DataFrame
        """
        data_config = self.config.get("data", {})
        start_date = start_date or data_config.get("start_date", "2024-01-01")
        end_date = end_date or data_config.get("end_date", "2025-12-31")

        return self.data_provider.get_data(symbol, start_date, end_date)
