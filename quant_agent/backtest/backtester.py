"""
回测引擎模块

提供历史数据回测功能：
- 事件驱动的回测框架
- 详细绩效分析报告
- 风险指标计算（夏普比率、最大回撤、胜率等）
"""

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from quant_agent.data.market_data import MarketDataProvider
from quant_agent.data.indicators import TechnicalIndicators
from quant_agent.strategies.base import BaseStrategy, Signal, SignalType
from quant_agent.risk.risk_manager import RiskManager, RiskLimits
from quant_agent.portfolio.portfolio import Portfolio
from quant_agent.execution.executor import OrderExecutor, OrderSide
from quant_agent.utils.logger import get_logger

logger = get_logger("quant_agent.backtest")


@dataclass
class BacktestResult:
    """
    回测结果

    Attributes:
        equity_curve: 权益曲线
        trades: 交易记录
        metrics: 绩效指标
        daily_returns: 日收益率序列
    """
    equity_curve: pd.DataFrame
    trades: list[dict]
    metrics: dict
    daily_returns: pd.Series = field(default_factory=pd.Series)

    def summary(self) -> str:
        """生成回测摘要报告。"""
        lines = [
            "=" * 60,
            "回测绩效报告",
            "=" * 60,
        ]
        for key, value in self.metrics.items():
            if isinstance(value, float):
                if "pct" in key or "rate" in key or "return" in key or "ratio" in key.lower():
                    lines.append(f"  {key}: {value:.4f}")
                else:
                    lines.append(f"  {key}: {value:.2f}")
            else:
                lines.append(f"  {key}: {value}")
        lines.append("=" * 60)

        # 亏损归因诊断
        if self.trades:
            sell_trades = [t for t in self.trades if t["side"] == "sell"]
            if sell_trades:
                winning = [t for t in sell_trades if t["pnl"] > 0]
                losing = [t for t in sell_trades if t["pnl"] <= 0]
                total_commission = sum(t["commission"] for t in self.trades)
                lines.append("")
                lines.append("  --- 交易诊断 ---")
                lines.append(f"  总手续费: {total_commission:,.2f}")
                if winning:
                    avg_win = sum(t["pnl"] for t in winning) / len(winning)
                    lines.append(f"  平均盈利: +{avg_win:,.2f}")
                if losing:
                    avg_loss = sum(t["pnl"] for t in losing) / len(losing)
                    lines.append(f"  平均亏损: {avg_loss:,.2f}")
                if winning and losing:
                    ratio = abs(avg_win / avg_loss)
                    lines.append(f"  盈亏比: {ratio:.2f}")
                    if ratio < 1.0:
                        lines.append(f"  ⚠ 盈亏比<1: 平均每笔赚的不够亏的多")
                lines.append("=" * 60)

        return "\n".join(lines)


class Backtester:
    """
    回测引擎

    支持多策略、多标的回测，生成详细绩效报告。
    """

    def __init__(
        self,
        initial_capital: float = 1000000.0,
        commission_rate: float = 0.001,
        slippage: float = 0.001,
        risk_limits: Optional[RiskLimits] = None,
    ):
        """
        初始化回测引擎。

        Args:
            initial_capital: 初始资金
            commission_rate: 手续费率
            slippage: 滑点比例
            risk_limits: 风险限制参数
        """
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.slippage = slippage
        self.risk_limits = risk_limits or RiskLimits()

    def run(
        self,
        strategies: list[BaseStrategy],
        data_dict: dict[str, pd.DataFrame],
        signal_threshold: float = 0.3,
    ) -> BacktestResult:
        """
        执行回测。

        Args:
            strategies: 策略列表
            data_dict: {symbol: DataFrame} 数据字典
            signal_threshold: 信号阈值

        Returns:
            回测结果
        """
        # 初始化组件
        portfolio = Portfolio(self.initial_capital)
        risk_manager = RiskManager(self.risk_limits)
        executor = OrderExecutor(self.commission_rate, self.slippage)
        risk_manager.update_peak_equity(self.initial_capital)

        # 跟踪每个持仓的历史最高价（用于移动止损）
        position_high: dict[str, float] = {}
        # 交易冷却期: 同一标的买入/卖出后N天内不再交易
        last_trade_date: dict[str, int] = {}  # symbol -> 上次交易的日期索引
        trade_cooldown = 10  # 冷却10个交易日

        # 为每个标的计算技术指标
        enriched_data = {}
        for symbol, df in data_dict.items():
            enriched_data[symbol] = TechnicalIndicators.compute_all(df)

        # 获取统一的日期序列
        all_dates = set()
        for df in enriched_data.values():
            all_dates.update(df.index)
        all_dates = sorted(all_dates)

        if not all_dates:
            return self._empty_result()

        logger.info(
            f"开始回测: {len(strategies)}个策略, "
            f"{len(data_dict)}个标的, "
            f"{len(all_dates)}个交易日"
        )

        # 预先为每个策略生成所有信号
        strategy_signals: dict[str, dict[str, list[Signal]]] = {}
        for strategy in strategies:
            strategy_signals[strategy.name] = {}
            for symbol, df in enriched_data.items():
                signals = strategy.generate_signals(df, symbol)
                # 按日期索引信号
                signal_by_date = {}
                for sig in signals:
                    date_str = sig.metadata.get("date", "")
                    if date_str:
                        signal_by_date[date_str] = sig
                strategy_signals[strategy.name][symbol] = signal_by_date

        # 逐日回测
        for date in all_dates:
            date_str = str(date)

            # 更新持仓价格
            prices = {}
            for symbol, df in enriched_data.items():
                if date in df.index:
                    prices[symbol] = df.loc[date, "close"]
            portfolio.update_prices(prices)

            # 更新持仓最高价
            for symbol, price in prices.items():
                if symbol in portfolio.positions:
                    if symbol not in position_high or price > position_high[symbol]:
                        position_high[symbol] = price

            # 检查止损止盈（含移动止损）
            closed_symbols = self._check_stop_loss_take_profit(
                portfolio, risk_manager, executor, prices, date_str, position_high
            )
            # 清除已平仓标的的最高价记录
            for sym in closed_symbols:
                position_high.pop(sym, None)

            # 检查最大回撤
            drawdown_hit, _ = risk_manager.check_max_drawdown(portfolio.total_equity)
            if drawdown_hit:
                logger.warning(f"触发最大回撤限制，暂停交易: {date_str}")
                portfolio.record_equity(date_str)
                continue

            # 融合各策略信号（近期信号窗口共识机制）
            for symbol in data_dict.keys():
                if symbol not in prices:
                    continue

                combined_strength = 0.0
                total_weight = 0.0
                signal_reasons = []
                buy_count = 0
                sell_count = 0

                # 回溯近5个交易日的信号，取每个策略的最近信号
                lookback = 5
                date_idx = all_dates.index(date)
                recent_dates = [str(all_dates[max(0, date_idx - d)]) for d in range(lookback)]

                for strategy in strategies:
                    # 查找该策略在近期窗口内的最新信号
                    recent_sig = None
                    for rd in recent_dates:
                        sig = strategy_signals[strategy.name][symbol].get(rd)
                        if sig:
                            recent_sig = sig
                            break

                    if recent_sig:
                        combined_strength += recent_sig.strength * strategy.weight
                        total_weight += strategy.weight
                        signal_reasons.append(
                            f"{strategy.name}: {recent_sig.signal_type.value} ({recent_sig.strength:.2f})"
                        )
                        if recent_sig.signal_type == SignalType.BUY:
                            buy_count += 1
                        elif recent_sig.signal_type == SignalType.SELL:
                            sell_count += 1

                if total_weight > 0:
                    combined_strength /= total_weight

                # 多数共识: 至少2个策略近期方向一致才确认信号
                has_consensus = (buy_count >= 2 and combined_strength > 0) or \
                                (sell_count >= 2 and combined_strength < 0)

                # 根据融合信号执行交易（需满足阈值 + 共识 + 冷却期）
                if abs(combined_strength) >= signal_threshold and has_consensus:
                    # 冷却期检查: 避免同一标的频繁交易
                    current_idx = all_dates.index(date)
                    if symbol in last_trade_date:
                        days_since = current_idx - last_trade_date[symbol]
                        if days_since < trade_cooldown:
                            continue  # 冷却期内跳过

                    price = prices[symbol]

                    if combined_strength > 0 and symbol not in portfolio.positions:
                        # 买入信号（仅在无持仓时买入，避免重复加仓）
                        quantity = risk_manager.calculate_position_size(
                            portfolio_value=portfolio.total_equity,
                            price=price,
                            signal_strength=combined_strength,
                        )
                        if quantity > 0:
                            order = executor.create_order(
                                symbol=symbol,
                                side=OrderSide.BUY,
                                quantity=quantity,
                                price=price,
                                date=date_str,
                            )
                            result_order = executor.execute_order(order, portfolio, risk_manager)
                            if result_order.status.value == "filled":
                                position_high[symbol] = price
                                last_trade_date[symbol] = current_idx

                    elif combined_strength < 0:
                        # 卖出信号
                        if symbol in portfolio.positions:
                            pos = portfolio.positions[symbol]
                            sell_quantity = pos.quantity
                            order = executor.create_order(
                                symbol=symbol,
                                side=OrderSide.SELL,
                                quantity=sell_quantity,
                                price=price,
                                date=date_str,
                            )
                            result_order = executor.execute_order(order, portfolio, risk_manager)
                            if result_order.status.value == "filled":
                                position_high.pop(symbol, None)
                                last_trade_date[symbol] = current_idx

            # 记录权益
            risk_manager.update_peak_equity(portfolio.total_equity)
            portfolio.record_equity(date_str)

        # 生成回测结果
        return self._generate_result(portfolio, executor)

    def _check_stop_loss_take_profit(
        self,
        portfolio: Portfolio,
        risk_manager: RiskManager,
        executor: OrderExecutor,
        prices: dict[str, float],
        date_str: str,
        position_high: Optional[dict[str, float]] = None,
    ) -> list[str]:
        """
        检查并执行止损止盈，含移动止损。

        Returns:
            已平仓的标的代码列表
        """
        symbols_to_close = []

        for symbol, pos in portfolio.positions.items():
            if symbol not in prices:
                continue

            current_price = prices[symbol]

            # 1. 检查硬止损
            stop_loss, reason = risk_manager.check_stop_loss(
                pos.avg_price, current_price
            )
            if stop_loss:
                symbols_to_close.append((symbol, pos.quantity, current_price, reason))
                continue

            # 2. 检查移动止损（优先于硬止盈，锁定利润）
            if position_high:
                highest = position_high.get(symbol, current_price)
                trailing, reason = risk_manager.check_trailing_stop(
                    entry_price=pos.avg_price,
                    current_price=current_price,
                    highest_price=highest,
                )
                if trailing:
                    symbols_to_close.append((symbol, pos.quantity, current_price, reason))
                    continue

            # 3. 检查硬止盈
            take_profit, reason = risk_manager.check_take_profit(
                pos.avg_price, current_price
            )
            if take_profit:
                symbols_to_close.append((symbol, pos.quantity, current_price, reason))

        # 执行平仓
        closed_symbols = []
        for symbol, quantity, price, reason in symbols_to_close:
            logger.info(f"风控平仓: {symbol} - {reason}")
            order = executor.create_order(
                symbol=symbol,
                side=OrderSide.SELL,
                quantity=quantity,
                price=price,
                date=date_str,
            )
            executor.execute_order(order, portfolio)
            closed_symbols.append(symbol)

        return closed_symbols

    def _generate_result(
        self, portfolio: Portfolio, executor: OrderExecutor
    ) -> BacktestResult:
        """生成回测结果。"""
        equity_curve = portfolio.get_equity_curve()

        # 计算日收益率
        daily_returns = pd.Series(dtype=float)
        if not equity_curve.empty and len(equity_curve) > 1:
            equity_series = equity_curve["equity"]
            daily_returns = equity_series.pct_change().dropna()

        # 计算绩效指标
        metrics = self._calculate_metrics(portfolio, daily_returns)

        # 交易记录
        trades = [
            {
                "date": t.date,
                "symbol": t.symbol,
                "side": t.side,
                "quantity": t.quantity,
                "price": t.price,
                "commission": t.commission,
                "pnl": t.pnl,
            }
            for t in portfolio.trade_history
        ]

        result = BacktestResult(
            equity_curve=equity_curve,
            trades=trades,
            metrics=metrics,
            daily_returns=daily_returns,
        )

        logger.info("\n" + result.summary())
        return result

    def _calculate_metrics(
        self, portfolio: Portfolio, daily_returns: pd.Series
    ) -> dict:
        """计算绩效指标。"""
        trade_summary = portfolio.get_trade_summary()

        metrics = {
            "initial_capital": self.initial_capital,
            "final_equity": portfolio.total_equity,
            "total_return": portfolio.total_return,
            "total_pnl": portfolio.total_equity - self.initial_capital,
            "realized_pnl": portfolio.realized_pnl,
            "unrealized_pnl": portfolio.unrealized_pnl,
            "total_trades": trade_summary["total_trades"],
            "buy_trades": trade_summary["buy_trades"],
            "sell_trades": trade_summary["sell_trades"],
            "winning_trades": trade_summary["winning_trades"],
            "losing_trades": trade_summary["losing_trades"],
            "win_rate": trade_summary["win_rate"],
        }

        if len(daily_returns) > 0:
            # 年化收益率 (假设252个交易日)
            total_days = len(daily_returns)
            annualized_return = (1 + portfolio.total_return) ** (252 / max(total_days, 1)) - 1
            metrics["annualized_return"] = annualized_return

            # 年化波动率
            annual_volatility = daily_returns.std() * np.sqrt(252)
            metrics["annual_volatility"] = annual_volatility

            # 夏普比率 (假设无风险利率3%)
            risk_free_rate = 0.03
            if annual_volatility > 0:
                sharpe_ratio = (annualized_return - risk_free_rate) / annual_volatility
            else:
                sharpe_ratio = 0.0
            metrics["sharpe_ratio"] = sharpe_ratio

            # 最大回撤
            equity_curve = portfolio.get_equity_curve()
            if not equity_curve.empty:
                equity_series = equity_curve["equity"]
                peak = equity_series.expanding().max()
                drawdown = (peak - equity_series) / peak
                max_drawdown = float(drawdown.max())
            else:
                max_drawdown = 0.0
            metrics["max_drawdown"] = max_drawdown

            # Sortino比率
            downside_returns = daily_returns[daily_returns < 0]
            if len(downside_returns) > 0:
                downside_std = downside_returns.std() * np.sqrt(252)
                sortino_ratio = (
                    (annualized_return - risk_free_rate) / downside_std
                    if downside_std > 0
                    else 0.0
                )
            else:
                sortino_ratio = 0.0
            metrics["sortino_ratio"] = sortino_ratio

            # Calmar比率
            if max_drawdown > 0:
                calmar_ratio = annualized_return / max_drawdown
            else:
                calmar_ratio = 0.0
            metrics["calmar_ratio"] = calmar_ratio

        return metrics

    def _empty_result(self) -> BacktestResult:
        """返回空的回测结果。"""
        return BacktestResult(
            equity_curve=pd.DataFrame(),
            trades=[],
            metrics={"error": "无有效数据"},
        )
