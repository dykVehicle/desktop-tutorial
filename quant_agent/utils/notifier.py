"""
企业微信 Webhook 通知模块

提供向企业微信群发送通知的功能，支持：
- 文本消息（text）
- Markdown 消息（markdown）
- 回测报告推送（明确标注为回测/模拟数据）
- 交易信号推送（标注市场状态和数据来源）
- 异常告警推送

所有时间戳统一使用北京时间 (UTC+8)。
"""

import json
import urllib.request
import urllib.error
from typing import Optional

from quant_agent.utils.logger import get_logger
from quant_agent.utils.timezone import (
    beijing_str,
    is_trading_hours,
    get_market_status,
)

logger = get_logger("quant_agent.notifier")

# 默认 Webhook URL
DEFAULT_WEBHOOK_URL = (
    "https://qyapi.weixin.qq.com/cgi-bin/webhook/send"
    "?key=ffde818b-8622-4c14-a18b-3447a3c40b93"
)


class WeChatNotifier:
    """
    企业微信 Webhook 通知器

    通过企业微信群机器人 Webhook 发送消息通知。
    支持文本消息和 Markdown 格式消息。
    所有时间戳使用北京时间。
    """

    def __init__(self, webhook_url: Optional[str] = None):
        """
        初始化通知器。

        Args:
            webhook_url: 企业微信 Webhook 地址。
                         如果为 None，则使用默认配置的地址。
        """
        self.webhook_url = webhook_url or DEFAULT_WEBHOOK_URL
        self._enabled = True

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value

    def _send_request(self, payload: dict) -> dict:
        """
        发送 HTTP POST 请求到 Webhook。

        Args:
            payload: 请求体字典

        Returns:
            响应结果字典

        Raises:
            Exception: 请求失败时抛出异常
        """
        if not self._enabled:
            logger.debug("通知功能已禁用，跳过发送")
            return {"errcode": 0, "errmsg": "disabled"}

        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            self.webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode("utf-8"))
                if result.get("errcode") != 0:
                    logger.warning(
                        f"企业微信通知发送异常: {result.get('errmsg', '未知错误')}"
                    )
                else:
                    logger.info("企业微信通知发送成功")
                return result
        except urllib.error.URLError as e:
            logger.error(f"企业微信通知发送失败 (网络错误): {e}")
            return {"errcode": -1, "errmsg": str(e)}
        except Exception as e:
            logger.error(f"企业微信通知发送失败: {e}")
            return {"errcode": -1, "errmsg": str(e)}

    def send_text(self, content: str, mentioned_list: Optional[list[str]] = None) -> dict:
        """
        发送文本消息。

        Args:
            content: 消息内容
            mentioned_list: 需要 @ 的用户ID列表，"@all" 表示所有人

        Returns:
            发送结果
        """
        payload = {
            "msgtype": "text",
            "text": {
                "content": content,
            },
        }
        if mentioned_list:
            payload["text"]["mentioned_list"] = mentioned_list

        return self._send_request(payload)

    def send_markdown(self, content: str) -> dict:
        """
        发送 Markdown 格式消息。

        企业微信支持的 Markdown 语法：
        - 标题 (#, ##, ###)
        - 加粗 (**text**)
        - 链接 [text](url)
        - 引用 (>)
        - 字体颜色 <font color="...">text</font>
        - 有序/无序列表

        Args:
            content: Markdown 格式内容

        Returns:
            发送结果
        """
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "content": content,
            },
        }
        return self._send_request(payload)

    def send_backtest_report(
        self,
        metrics: dict,
        trades: Optional[list] = None,
        data_source: str = "synthetic",
    ) -> dict:
        """
        发送回测报告到企业微信。

        注意：报告会明确标注为【历史回测】，并注明数据来源，
        避免与实盘交易混淆。

        Args:
            metrics: 回测绩效指标字典
            trades: 交易记录列表（可选）
            data_source: 数据来源 ("synthetic"=合成模拟 | "csv"=历史文件 | "api"=实时API)

        Returns:
            发送结果
        """
        now = beijing_str()
        market_status = get_market_status()

        # 数据来源标签
        source_labels = {
            "synthetic": "🔬 合成模拟数据",
            "csv": "📂 历史CSV数据",
            "api": "🌐 实时API数据",
        }
        source_label = source_labels.get(data_source, f"📦 {data_source}")

        # 收益率颜色
        total_return = metrics.get("total_return", 0)
        return_color = "green" if total_return >= 0 else "red"
        return_sign = "+" if total_return >= 0 else ""

        # 构建 Markdown 消息
        lines = [
            "# 📊 量化交易 · 历史回测报告",
            f"> ⏰ 北京时间: {now}",
            f"> 🏛️ 市场状态: {market_status}",
            f"> 📌 数据来源: {source_label}",
            f"> ⚠️ **本报告为历史回测结果，非实盘交易，仅供策略评估参考**",
            "",
            "## 💰 收益概览",
            f"**初始资金**: {metrics.get('initial_capital', 0):,.0f}",
            f"**最终权益**: {metrics.get('final_equity', 0):,.0f}",
            f"**总收益率**: <font color=\"{return_color}\">"
            f"{return_sign}{total_return:.2%}</font>",
            f"**总盈亏**: <font color=\"{return_color}\">"
            f"{return_sign}{metrics.get('total_pnl', 0):,.2f}</font>",
        ]

        # 风险指标
        sharpe = metrics.get("sharpe_ratio", 0)
        sharpe_color = "green" if sharpe > 0 else "red"
        max_dd = metrics.get("max_drawdown", 0)

        lines += [
            "",
            "## 📈 风险指标",
            f"**年化收益率**: {metrics.get('annualized_return', 0):.2%}",
            f"**年化波动率**: {metrics.get('annual_volatility', 0):.2%}",
            f"**夏普比率**: <font color=\"{sharpe_color}\">{sharpe:.4f}</font>",
            f"**最大回撤**: <font color=\"red\">{max_dd:.2%}</font>",
            f"**Sortino比率**: {metrics.get('sortino_ratio', 0):.4f}",
            f"**Calmar比率**: {metrics.get('calmar_ratio', 0):.4f}",
        ]

        # 交易统计
        win_rate = metrics.get("win_rate", 0)
        win_color = "green" if win_rate >= 0.5 else "warning"

        lines += [
            "",
            "## 🔄 交易统计",
            f"**总交易次数**: {metrics.get('total_trades', 0)}",
            f"**买入次数**: {metrics.get('buy_trades', 0)}",
            f"**卖出次数**: {metrics.get('sell_trades', 0)}",
            f"**盈利交易**: {metrics.get('winning_trades', 0)}",
            f"**亏损交易**: {metrics.get('losing_trades', 0)}",
            f"**胜率**: <font color=\"{win_color}\">{win_rate:.1%}</font>",
        ]

        content = "\n".join(lines)
        return self.send_markdown(content)

    def send_signal_alert(
        self,
        analysis: dict,
        data_source: str = "synthetic",
    ) -> dict:
        """
        发送交易信号提醒。

        非交易时间的信号会被明确标注为非实盘信号。

        Args:
            analysis: 标的分析结果字典（由 TradingAgent.analyze_symbol 生成）
            data_source: 数据来源

        Returns:
            发送结果
        """
        now = beijing_str()
        market_status = get_market_status()
        trading = is_trading_hours()

        signal_type = analysis.get("signal_type", "hold")
        strength = analysis.get("signal_strength", 0)
        symbol = analysis.get("symbol", "N/A")
        price = analysis.get("latest_price", 0)

        # 数据来源标签
        source_labels = {
            "synthetic": "合成模拟数据",
            "csv": "历史CSV数据",
            "api": "实时API数据",
        }
        source_label = source_labels.get(data_source, data_source)

        # 信号类型对应的颜色和表情
        signal_config = {
            "buy": ("green", "🟢 买入"),
            "sell": ("red", "🔴 卖出"),
            "hold": ("gray", "⚪ 观望"),
        }
        color, signal_text = signal_config.get(signal_type, ("gray", "⚪ 未知"))

        # 根据是否交易时间和数据来源决定标题
        if not trading or data_source != "api":
            title = "# 📡 交易信号（仅供参考·非实盘）"
        else:
            title = "# 📡 实盘交易信号提醒"

        lines = [
            title,
            f"> ⏰ 北京时间: {now}",
            f"> 🏛️ 市场状态: {market_status}",
            f"> 📌 数据来源: {source_label}",
        ]

        if not trading:
            lines.append(f"> ⚠️ **当前为非交易时间，本信号基于历史数据分析，仅供参考**")

        lines += [
            "",
            f"**标的**: {symbol}",
            f"**最新价格**: {price:.2f}",
            f"**综合信号**: <font color=\"{color}\">{signal_text}</font>",
            f"**信号强度**: {strength:.4f}",
            "",
            "### 各策略信号",
        ]

        for sig in analysis.get("strategy_signals", []):
            s_type = sig.get("type", "hold")
            s_color = {"buy": "green", "sell": "red"}.get(s_type, "gray")
            lines.append(
                f"- **{sig.get('strategy', 'N/A')}**: "
                f"<font color=\"{s_color}\">{s_type}</font> "
                f"(强度: {sig.get('strength', 0):.4f}) "
                f"- {sig.get('reason', '')}"
            )

        content = "\n".join(lines)
        return self.send_markdown(content)

    def send_error_alert(self, error_msg: str, context: str = "") -> dict:
        """
        发送异常告警。

        Args:
            error_msg: 错误信息
            context: 错误上下文

        Returns:
            发送结果
        """
        now = beijing_str()
        lines = [
            "# ⚠️ 系统异常告警",
            f"> ⏰ 北京时间: {now}",
            "",
            f"**错误信息**: {error_msg}",
        ]
        if context:
            lines.append(f"**上下文**: {context}")

        content = "\n".join(lines)
        return self.send_markdown(content)
