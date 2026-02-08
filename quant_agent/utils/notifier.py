"""
企业微信 Webhook 通知模块

提供向企业微信群发送通知的功能，支持：
- 文本消息（text）
- Markdown 消息（markdown）
- 回测报告推送
- 交易信号推送
- 异常告警推送
"""

import json
import urllib.request
import urllib.error
from typing import Optional
from datetime import datetime

from quant_agent.utils.logger import get_logger

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

    def send_backtest_report(self, metrics: dict, trades: Optional[list] = None) -> dict:
        """
        发送回测报告到企业微信。

        Args:
            metrics: 回测绩效指标字典
            trades: 交易记录列表（可选）

        Returns:
            发送结果
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 收益率颜色
        total_return = metrics.get("total_return", 0)
        return_color = "green" if total_return >= 0 else "red"
        return_sign = "+" if total_return >= 0 else ""

        # 构建 Markdown 消息
        lines = [
            "# 📊 量化交易回测报告",
            f"> 生成时间: {now}",
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

    def send_signal_alert(self, analysis: dict) -> dict:
        """
        发送交易信号提醒。

        Args:
            analysis: 标的分析结果字典（由 TradingAgent.analyze_symbol 生成）

        Returns:
            发送结果
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        signal_type = analysis.get("signal_type", "hold")
        strength = analysis.get("signal_strength", 0)
        symbol = analysis.get("symbol", "N/A")
        price = analysis.get("latest_price", 0)

        # 信号类型对应的颜色和表情
        signal_config = {
            "buy": ("green", "🟢 买入"),
            "sell": ("red", "🔴 卖出"),
            "hold": ("gray", "⚪ 观望"),
        }
        color, signal_text = signal_config.get(signal_type, ("gray", "⚪ 未知"))

        lines = [
            f"# 📡 交易信号提醒",
            f"> {now}",
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
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines = [
            "# ⚠️ 系统异常告警",
            f"> {now}",
            "",
            f"**错误信息**: {error_msg}",
        ]
        if context:
            lines.append(f"**上下文**: {context}")

        content = "\n".join(lines)
        return self.send_markdown(content)
