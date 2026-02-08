"""
企业微信通知模块的单元测试
"""

import json
from unittest.mock import patch, MagicMock
import pytest

from quant_agent.utils.notifier import WeChatNotifier, DEFAULT_WEBHOOK_URL


@pytest.fixture
def notifier():
    """创建默认通知器。"""
    return WeChatNotifier()


@pytest.fixture
def disabled_notifier():
    """创建一个禁用的通知器。"""
    n = WeChatNotifier()
    n.enabled = False
    return n


@pytest.fixture
def sample_metrics():
    """回测指标样本。"""
    return {
        "initial_capital": 1000000.0,
        "final_equity": 1050000.0,
        "total_return": 0.05,
        "total_pnl": 50000.0,
        "realized_pnl": 30000.0,
        "unrealized_pnl": 20000.0,
        "total_trades": 20,
        "buy_trades": 10,
        "sell_trades": 10,
        "winning_trades": 6,
        "losing_trades": 4,
        "win_rate": 0.6,
        "annualized_return": 0.12,
        "annual_volatility": 0.18,
        "sharpe_ratio": 0.5,
        "max_drawdown": 0.08,
        "sortino_ratio": 0.7,
        "calmar_ratio": 1.5,
    }


@pytest.fixture
def sample_analysis():
    """交易信号分析样本。"""
    return {
        "symbol": "000001.SZ",
        "latest_price": 15.5,
        "signal_type": "buy",
        "signal_strength": 0.65,
        "strategy_signals": [
            {
                "strategy": "MA_Crossover",
                "type": "buy",
                "strength": 0.8,
                "reason": "金叉: SMA10上穿SMA30",
            },
            {
                "strategy": "RSI",
                "type": "buy",
                "strength": 0.5,
                "reason": "RSI超卖反弹: 25.0 → 35.0",
            },
            {
                "strategy": "MACD",
                "type": "hold",
                "strength": 0.0,
                "reason": "无信号",
            },
        ],
    }


class TestNotifierInit:
    def test_default_init(self, notifier):
        assert notifier.webhook_url == DEFAULT_WEBHOOK_URL
        assert notifier.enabled is True

    def test_custom_url(self):
        custom_url = "https://example.com/webhook"
        n = WeChatNotifier(webhook_url=custom_url)
        assert n.webhook_url == custom_url

    def test_disable(self, notifier):
        notifier.enabled = False
        assert notifier.enabled is False


class TestSendText:
    @patch("quant_agent.utils.notifier.urllib.request.urlopen")
    def test_send_text_success(self, mock_urlopen, notifier):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {"errcode": 0, "errmsg": "ok"}
        ).encode("utf-8")
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = notifier.send_text("测试消息")
        assert result["errcode"] == 0

    @patch("quant_agent.utils.notifier.urllib.request.urlopen")
    def test_send_text_with_mentions(self, mock_urlopen, notifier):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {"errcode": 0, "errmsg": "ok"}
        ).encode("utf-8")
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = notifier.send_text("测试消息", mentioned_list=["@all"])
        assert result["errcode"] == 0

        # 验证请求体中包含 mentioned_list
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        body = json.loads(request.data.decode("utf-8"))
        assert body["text"]["mentioned_list"] == ["@all"]

    def test_send_text_disabled(self, disabled_notifier):
        result = disabled_notifier.send_text("测试消息")
        assert result["errcode"] == 0
        assert result["errmsg"] == "disabled"


class TestSendMarkdown:
    @patch("quant_agent.utils.notifier.urllib.request.urlopen")
    def test_send_markdown_success(self, mock_urlopen, notifier):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {"errcode": 0, "errmsg": "ok"}
        ).encode("utf-8")
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = notifier.send_markdown("# 标题\n内容")
        assert result["errcode"] == 0

        # 验证请求体格式
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        body = json.loads(request.data.decode("utf-8"))
        assert body["msgtype"] == "markdown"
        assert "# 标题" in body["markdown"]["content"]


class TestSendBacktestReport:
    @patch("quant_agent.utils.notifier.urllib.request.urlopen")
    def test_send_report(self, mock_urlopen, notifier, sample_metrics):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {"errcode": 0, "errmsg": "ok"}
        ).encode("utf-8")
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = notifier.send_backtest_report(sample_metrics)
        assert result["errcode"] == 0

        # 验证消息内容包含关键信息
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        body = json.loads(request.data.decode("utf-8"))
        content = body["markdown"]["content"]
        assert "回测报告" in content
        assert "1,000,000" in content
        assert "夏普比率" in content
        # 应标注为历史回测 + 非实盘
        assert "历史回测" in content
        assert "非实盘" in content or "仅供" in content
        # 应包含北京时间标注
        assert "北京时间" in content
        # 应标注数据来源
        assert "数据来源" in content

    @patch("quant_agent.utils.notifier.urllib.request.urlopen")
    def test_report_with_data_source(self, mock_urlopen, notifier, sample_metrics):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {"errcode": 0, "errmsg": "ok"}
        ).encode("utf-8")
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = notifier.send_backtest_report(sample_metrics, data_source="csv")
        assert result["errcode"] == 0

        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        body = json.loads(request.data.decode("utf-8"))
        content = body["markdown"]["content"]
        assert "CSV" in content

    @patch("quant_agent.utils.notifier.urllib.request.urlopen")
    def test_negative_return_report(self, mock_urlopen, notifier):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {"errcode": 0, "errmsg": "ok"}
        ).encode("utf-8")
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        metrics = {
            "initial_capital": 1000000.0,
            "final_equity": 950000.0,
            "total_return": -0.05,
            "total_pnl": -50000.0,
            "sharpe_ratio": -0.5,
            "max_drawdown": 0.1,
            "total_trades": 10,
            "buy_trades": 5,
            "sell_trades": 5,
            "winning_trades": 2,
            "losing_trades": 3,
            "win_rate": 0.4,
            "annualized_return": -0.1,
            "annual_volatility": 0.2,
            "sortino_ratio": -0.3,
            "calmar_ratio": -1.0,
        }
        result = notifier.send_backtest_report(metrics)
        assert result["errcode"] == 0

        # 验证负收益显示红色
        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        body = json.loads(request.data.decode("utf-8"))
        content = body["markdown"]["content"]
        assert 'color="red"' in content


class TestSendSignalAlert:
    @patch("quant_agent.utils.notifier.urllib.request.urlopen")
    def test_send_buy_signal(self, mock_urlopen, notifier, sample_analysis):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {"errcode": 0, "errmsg": "ok"}
        ).encode("utf-8")
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = notifier.send_signal_alert(sample_analysis)
        assert result["errcode"] == 0

        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        body = json.loads(request.data.decode("utf-8"))
        content = body["markdown"]["content"]
        assert "000001.SZ" in content
        assert "买入" in content
        assert "MA_Crossover" in content
        # 应包含北京时间和市场状态
        assert "北京时间" in content
        assert "市场状态" in content

    @patch("quant_agent.utils.notifier.urllib.request.urlopen")
    def test_send_sell_signal(self, mock_urlopen, notifier):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {"errcode": 0, "errmsg": "ok"}
        ).encode("utf-8")
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        analysis = {
            "symbol": "600519.SH",
            "latest_price": 1800.0,
            "signal_type": "sell",
            "signal_strength": -0.7,
            "strategy_signals": [],
        }
        result = notifier.send_signal_alert(analysis)
        assert result["errcode"] == 0

    @patch("quant_agent.utils.notifier.urllib.request.urlopen")
    def test_signal_with_synthetic_data_shows_reference_only(self, mock_urlopen, notifier, sample_analysis):
        """合成数据的信号应标注为仅供参考。"""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {"errcode": 0, "errmsg": "ok"}
        ).encode("utf-8")
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = notifier.send_signal_alert(sample_analysis, data_source="synthetic")
        assert result["errcode"] == 0

        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        body = json.loads(request.data.decode("utf-8"))
        content = body["markdown"]["content"]
        # 非实盘数据应标注为仅供参考
        assert "仅供参考" in content or "非实盘" in content


class TestSendErrorAlert:
    @patch("quant_agent.utils.notifier.urllib.request.urlopen")
    def test_send_error(self, mock_urlopen, notifier):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {"errcode": 0, "errmsg": "ok"}
        ).encode("utf-8")
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = notifier.send_error_alert("数据获取超时", "MarketDataProvider.get_data")
        assert result["errcode"] == 0

        call_args = mock_urlopen.call_args
        request = call_args[0][0]
        body = json.loads(request.data.decode("utf-8"))
        content = body["markdown"]["content"]
        assert "异常告警" in content
        assert "数据获取超时" in content
        assert "北京时间" in content


class TestErrorHandling:
    @patch("quant_agent.utils.notifier.urllib.request.urlopen")
    def test_network_error(self, mock_urlopen, notifier):
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError("网络不可达")
        result = notifier.send_text("测试")
        assert result["errcode"] == -1

    @patch("quant_agent.utils.notifier.urllib.request.urlopen")
    def test_api_error_response(self, mock_urlopen, notifier):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {"errcode": 93000, "errmsg": "invalid webhook url"}
        ).encode("utf-8")
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        result = notifier.send_text("测试")
        assert result["errcode"] == 93000


class TestAgentIntegration:
    """测试通知功能与 TradingAgent 的集成。"""

    def test_agent_has_notifier(self):
        from quant_agent.core.agent import TradingAgent
        agent = TradingAgent(notify_enabled=False)
        assert hasattr(agent, "notifier")
        assert isinstance(agent.notifier, WeChatNotifier)
        assert agent.notifier.enabled is False

    def test_agent_custom_webhook(self):
        from quant_agent.core.agent import TradingAgent
        agent = TradingAgent(
            webhook_url="https://custom.webhook.url",
            notify_enabled=False,
        )
        assert agent.notifier.webhook_url == "https://custom.webhook.url"

    def test_agent_config_webhook(self):
        from quant_agent.core.agent import TradingAgent
        config = {
            "notification": {
                "webhook_url": "https://from-config.webhook.url",
            }
        }
        agent = TradingAgent(config=config, notify_enabled=False)
        assert agent.notifier.webhook_url == "https://from-config.webhook.url"

    @patch("quant_agent.utils.notifier.urllib.request.urlopen")
    def test_backtest_sends_notification(self, mock_urlopen):
        """回测完成后应发送通知。"""
        from quant_agent.core.agent import TradingAgent

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {"errcode": 0, "errmsg": "ok"}
        ).encode("utf-8")
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        agent = TradingAgent(notify_enabled=True)
        agent.setup_default_strategies()
        result = agent.run_backtest(
            symbols=["000001.SZ"],
            start_date="2024-01-01",
            end_date="2024-06-30",
        )

        # 验证 urlopen 被调用（发送了通知）
        assert mock_urlopen.called

    def test_backtest_works_when_notify_disabled(self):
        """通知禁用时回测仍应正常工作。"""
        from quant_agent.core.agent import TradingAgent

        agent = TradingAgent(notify_enabled=False)
        agent.setup_default_strategies()
        result = agent.run_backtest(
            symbols=["000001.SZ"],
            start_date="2024-01-01",
            end_date="2024-06-30",
        )
        assert result is not None
        assert "total_return" in result.metrics
