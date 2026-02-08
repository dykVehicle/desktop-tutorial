"""
交易智能体模块

核心智能体，负责：
- 多策略信号融合
- 综合决策
- 自适应参数调整
- 交易执行协调
"""

from typing import Optional

import pandas as pd
import numpy as np

from quant_agent.strategies.base import BaseStrategy, Signal, SignalType
from quant_agent.strategies.ma_crossover import MACrossoverStrategy
from quant_agent.strategies.rsi_strategy import RSIStrategy
from quant_agent.strategies.macd_strategy import MACDStrategy
from quant_agent.risk.risk_manager import RiskManager, RiskLimits
from quant_agent.data.indicators import TechnicalIndicators
from quant_agent.core.engine import TradingEngine
from quant_agent.backtest.backtester import BacktestResult
from quant_agent.utils.logger import get_logger
from quant_agent.utils.notifier import WeChatNotifier

logger = get_logger("quant_agent.agent")


class TradingAgent:
    """
    量化交易智能体

    多策略协同的智能交易系统，通过加权信号融合机制
    综合多个策略的判断进行交易决策。

    功能：
    1. 管理多个交易策略
    2. 信号融合与综合决策
    3. 自适应置信度衰减
    4. 协调风控和执行
    """

    def __init__(
        self,
        config: Optional[dict] = None,
        signal_threshold: float = 0.3,
        confidence_decay: float = 0.95,
        webhook_url: Optional[str] = None,
        notify_enabled: bool = True,
    ):
        """
        初始化交易智能体。

        Args:
            config: 配置字典
            signal_threshold: 信号阈值
            confidence_decay: 置信度衰减系数
            webhook_url: 企业微信 Webhook 地址（可选）
            notify_enabled: 是否启用企业微信通知
        """
        self.config = config
        self.signal_threshold = signal_threshold
        self.confidence_decay = confidence_decay
        self.engine = TradingEngine(config)
        self.strategies: list[BaseStrategy] = []
        self._signal_history: list[dict] = []

        # 初始化企业微信通知器
        notifier_config = {}
        if config:
            notifier_config = config.get("notification", {})
        _webhook = webhook_url or notifier_config.get("webhook_url")
        self.notifier = WeChatNotifier(webhook_url=_webhook)
        self.notifier.enabled = notify_enabled

    def add_strategy(self, strategy: BaseStrategy):
        """
        添加交易策略。

        Args:
            strategy: 策略实例
        """
        self.strategies.append(strategy)
        self.engine.add_strategy(strategy)
        logger.info(f"智能体添加策略: {strategy.name} (权重: {strategy.weight})")

    def setup_default_strategies(
        self,
        ma_weight: float = 0.4,
        rsi_weight: float = 0.3,
        macd_weight: float = 0.3,
    ):
        """
        设置默认策略组合。

        Args:
            ma_weight: MA交叉策略权重
            rsi_weight: RSI策略权重
            macd_weight: MACD策略权重
        """
        strategies_config = {}
        if self.config:
            strategies_config = self.config.get("strategies", {})

        # MA交叉策略
        ma_config = strategies_config.get("ma_crossover", {})
        ma_strategy = MACrossoverStrategy(
            short_window=ma_config.get("short_window", 10),
            long_window=ma_config.get("long_window", 30),
            weight=ma_config.get("weight", ma_weight),
        )
        self.add_strategy(ma_strategy)

        # RSI策略
        rsi_config = strategies_config.get("rsi", {})
        rsi_strategy = RSIStrategy(
            period=rsi_config.get("period", 14),
            overbought=rsi_config.get("overbought", 70),
            oversold=rsi_config.get("oversold", 30),
            weight=rsi_config.get("weight", rsi_weight),
        )
        self.add_strategy(rsi_strategy)

        # MACD策略
        macd_config = strategies_config.get("macd", {})
        macd_strategy = MACDStrategy(
            fast_period=macd_config.get("fast_period", 12),
            slow_period=macd_config.get("slow_period", 26),
            signal_period=macd_config.get("signal_period", 9),
            weight=macd_config.get("weight", macd_weight),
        )
        self.add_strategy(macd_strategy)

        logger.info(
            f"默认策略已加载: MA({ma_strategy.weight}), "
            f"RSI({rsi_strategy.weight}), MACD({macd_strategy.weight})"
        )

    def fuse_signals(
        self, signals: list[Signal]
    ) -> tuple[SignalType, float]:
        """
        融合多个策略的信号。

        使用加权平均法融合各策略的信号强度。

        Args:
            signals: 各策略产生的信号列表

        Returns:
            (综合信号类型, 综合信号强度)
        """
        if not signals:
            return SignalType.HOLD, 0.0

        # 加权融合
        total_weight = 0.0
        weighted_strength = 0.0

        for signal in signals:
            # 查找对应策略的权重
            strategy_weight = 1.0
            for s in self.strategies:
                if s.name == signal.strategy_name:
                    strategy_weight = s.weight
                    break

            weighted_strength += signal.strength * strategy_weight
            total_weight += strategy_weight

        if total_weight == 0:
            return SignalType.HOLD, 0.0

        combined_strength = weighted_strength / total_weight

        # 应用置信度衰减
        combined_strength *= self.confidence_decay

        # 确定信号类型
        if combined_strength >= self.signal_threshold:
            return SignalType.BUY, combined_strength
        elif combined_strength <= -self.signal_threshold:
            return SignalType.SELL, combined_strength
        else:
            return SignalType.HOLD, combined_strength

    def analyze_symbol(
        self, symbol: str, data: pd.DataFrame
    ) -> dict:
        """
        分析单个标的。

        Args:
            symbol: 股票代码
            data: OHLCV数据

        Returns:
            分析结果字典
        """
        # 计算技术指标
        enriched = TechnicalIndicators.compute_all(data)

        # 收集各策略的最新信号
        latest_signals = []
        for strategy in self.strategies:
            signal = strategy.generate_latest_signal(enriched, symbol)
            latest_signals.append(signal)

        # 信号融合
        signal_type, strength = self.fuse_signals(latest_signals)

        analysis = {
            "symbol": symbol,
            "latest_price": float(data["close"].iloc[-1]),
            "signal_type": signal_type.value,
            "signal_strength": strength,
            "strategy_signals": [
                {
                    "strategy": sig.strategy_name,
                    "type": sig.signal_type.value,
                    "strength": sig.strength,
                    "reason": sig.reason,
                }
                for sig in latest_signals
            ],
        }

        # 记录信号历史
        self._signal_history.append(analysis)

        # 当出现非HOLD信号时，推送企业微信通知
        if signal_type != SignalType.HOLD and self.notifier.enabled:
            try:
                self.notifier.send_signal_alert(analysis)
            except Exception as e:
                logger.warning(f"发送信号通知失败: {e}")

        return analysis

    def run_backtest(
        self,
        symbols: Optional[list[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> BacktestResult:
        """
        运行回测。

        Args:
            symbols: 股票代码列表
            start_date: 起始日期
            end_date: 结束日期

        Returns:
            回测结果
        """
        if not self.strategies:
            logger.warning("未加载策略，使用默认策略")
            self.setup_default_strategies()

        result = self.engine.run_backtest(symbols, start_date, end_date)

        logger.info(
            f"回测完成: 总收益 {result.metrics.get('total_return', 0):.2%}, "
            f"夏普比率 {result.metrics.get('sharpe_ratio', 0):.2f}"
        )

        # 推送回测报告到企业微信
        if self.notifier.enabled:
            try:
                self.notifier.send_backtest_report(
                    metrics=result.metrics,
                    trades=result.trades,
                )
            except Exception as e:
                logger.warning(f"发送回测报告通知失败: {e}")

        return result

    def get_signal_history(self) -> list[dict]:
        """获取信号历史。"""
        return self._signal_history.copy()

    def __repr__(self) -> str:
        strategy_names = [s.name for s in self.strategies]
        return f"TradingAgent(strategies={strategy_names}, threshold={self.signal_threshold})"
