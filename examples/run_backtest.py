"""
回测示例

演示如何使用量化交易智能体进行历史数据回测。
"""

import sys
import os

# 确保可以找到项目模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quant_agent.core.agent import TradingAgent
from quant_agent.utils.logger import setup_logger


def main():
    """运行回测示例。"""
    # 设置日志
    setup_logger("quant_agent", level="INFO", console=True)

    print("=" * 60)
    print("量化交易智能体 - 回测示例")
    print("=" * 60)

    # 创建智能体
    agent = TradingAgent(
        signal_threshold=0.3,
        confidence_decay=0.95,
    )

    # 加载默认策略
    agent.setup_default_strategies(
        ma_weight=0.4,
        rsi_weight=0.3,
        macd_weight=0.3,
    )

    print(f"\n智能体: {agent}")
    print(f"策略: {[s.name for s in agent.strategies]}")

    # 运行回测
    print("\n开始回测...")
    result = agent.run_backtest(
        symbols=["000001.SZ", "600519.SH"],
        start_date="2024-01-01",
        end_date="2025-06-30",
    )

    # 输出结果
    print("\n" + result.summary())

    # 输出交易统计
    print(f"\n总交易次数: {len(result.trades)}")
    if result.trades:
        buy_trades = [t for t in result.trades if t["side"] == "buy"]
        sell_trades = [t for t in result.trades if t["side"] == "sell"]
        print(f"买入次数: {len(buy_trades)}")
        print(f"卖出次数: {len(sell_trades)}")

        if sell_trades:
            winning = [t for t in sell_trades if t["pnl"] > 0]
            print(f"盈利交易: {len(winning)}")
            print(f"亏损交易: {len(sell_trades) - len(winning)}")

    # 分析单个标的
    print("\n" + "=" * 60)
    print("个股分析")
    print("=" * 60)

    data = agent.engine.get_market_data("000001.SZ", "2024-01-01", "2025-06-30")
    analysis = agent.analyze_symbol("000001.SZ", data)

    print(f"\n标的: {analysis['symbol']}")
    print(f"最新价格: {analysis['latest_price']:.2f}")
    print(f"综合信号: {analysis['signal_type']} (强度: {analysis['signal_strength']:.4f})")
    print("\n各策略信号:")
    for sig in analysis["strategy_signals"]:
        print(f"  {sig['strategy']}: {sig['type']} ({sig['strength']:.4f}) - {sig['reason']}")


if __name__ == "__main__":
    main()
