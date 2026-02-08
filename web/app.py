"""
量化交易智能体 Web 应用

基于 FastAPI 的 Web 服务，提供：
- 仪表盘：实时查看系统状态
- 回测引擎：运行策略回测并查看结果
- 信号分析：分析标的并查看各策略信号
- 策略配置：在线调整策略参数
"""

import os
import sys

# 确保能找到项目模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from quant_agent.core.agent import TradingAgent
from quant_agent.data.market_data import MarketDataProvider
from quant_agent.data.indicators import TechnicalIndicators
from quant_agent.utils.timezone import beijing_str, get_market_status, is_trading_hours

app = FastAPI(title="量化交易智能体", version="0.1.0")

# CORS - 允许公网访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件和模板
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# 全局数据提供者
data_provider = MarketDataProvider(source="synthetic")


# ── 请求模型 ──────────────────────────────────────

class BacktestRequest(BaseModel):
    symbols: list[str] = ["000001.SZ", "600519.SH"]
    start_date: str = "2024-01-01"
    end_date: str = "2025-06-30"
    initial_capital: float = 1000000.0
    signal_threshold: float = 0.15
    stop_loss_pct: float = 0.07
    take_profit_pct: float = 0.10
    ma_short: int = 10
    ma_long: int = 30
    rsi_period: int = 14
    ma_weight: float = 0.4
    rsi_weight: float = 0.3
    macd_weight: float = 0.3


class AnalyzeRequest(BaseModel):
    symbol: str = "000001.SZ"
    start_date: str = "2024-01-01"
    end_date: str = "2025-06-30"


# ── 页面路由 ──────────────────────────────────────

@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# ── API 路由 ──────────────────────────────────────

@app.get("/api/status")
async def get_status():
    """获取系统状态"""
    return {
        "time": beijing_str(),
        "market_status": get_market_status(),
        "is_trading": is_trading_hours(),
        "data_source": "synthetic",
        "version": "0.1.0",
    }


@app.get("/api/symbols")
async def get_symbols():
    """获取可用标的列表"""
    symbols = [
        {"code": "000001.SZ", "name": "平安银行"},
        {"code": "600519.SH", "name": "贵州茅台"},
        {"code": "000858.SZ", "name": "五粮液"},
        {"code": "601318.SH", "name": "中国平安"},
        {"code": "000333.SZ", "name": "美的集团"},
        {"code": "600036.SH", "name": "招商银行"},
    ]
    return {"symbols": symbols}


@app.post("/api/backtest")
async def run_backtest(req: BacktestRequest):
    """运行回测"""
    try:
        config = {
            "engine": {
                "initial_capital": req.initial_capital,
                "commission_rate": 0.001,
                "slippage": 0.001,
            },
            "data": {"source": "synthetic"},
            "risk": {
                "max_position_pct": 0.25,
                "max_total_position_pct": 0.7,
                "stop_loss_pct": req.stop_loss_pct,
                "take_profit_pct": req.take_profit_pct,
                "max_drawdown_pct": 0.20,
            },
            "agent": {"signal_threshold": req.signal_threshold},
            "strategies": {
                "ma_crossover": {
                    "short_window": req.ma_short,
                    "long_window": req.ma_long,
                    "weight": req.ma_weight,
                },
                "rsi": {"period": req.rsi_period, "weight": req.rsi_weight},
                "macd": {"weight": req.macd_weight},
            },
        }

        agent = TradingAgent(
            config=config,
            signal_threshold=req.signal_threshold,
            notify_enabled=False,
        )
        agent.setup_default_strategies()

        result = agent.run_backtest(
            symbols=req.symbols,
            start_date=req.start_date,
            end_date=req.end_date,
        )

        # 权益曲线
        equity_data = []
        if not result.equity_curve.empty:
            for _, row in result.equity_curve.iterrows():
                equity_data.append({
                    "date": str(row["date"])[:10],
                    "equity": round(row["equity"], 2),
                })

        # 交易明细
        trades = []
        for t in result.trades:
            trades.append({
                "date": str(t["date"])[:10],
                "symbol": t["symbol"],
                "side": t["side"],
                "quantity": t["quantity"],
                "price": round(t["price"], 2),
                "commission": round(t["commission"], 2),
                "pnl": round(t["pnl"], 2) if t["side"] == "sell" else None,
            })

        return {
            "success": True,
            "metrics": result.metrics,
            "equity_curve": equity_data,
            "trades": trades,
        }

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)},
        )


@app.post("/api/analyze")
async def analyze_symbol(req: AnalyzeRequest):
    """分析单个标的"""
    try:
        agent = TradingAgent(signal_threshold=0.15, notify_enabled=False)
        agent.setup_default_strategies()

        data = data_provider.get_data(req.symbol, req.start_date, req.end_date)
        analysis = agent.analyze_symbol(req.symbol, data)

        # K线数据（最近60天）
        recent = data.tail(60)
        kline = []
        for idx, row in recent.iterrows():
            kline.append({
                "date": str(idx)[:10],
                "open": round(row["open"], 2),
                "high": round(row["high"], 2),
                "low": round(row["low"], 2),
                "close": round(row["close"], 2),
                "volume": int(row["volume"]),
            })

        # 技术指标
        enriched = TechnicalIndicators.compute_all(data)
        recent_ind = enriched.tail(60)
        indicators = {
            "sma_10": [round(v, 2) if not __import__("pandas").isna(v) else None for v in recent_ind["sma_10"]],
            "sma_30": [round(v, 2) if not __import__("pandas").isna(v) else None for v in recent_ind["sma_30"]],
            "rsi": [round(v, 2) if not __import__("pandas").isna(v) else None for v in recent_ind["rsi"]],
            "macd": [round(v, 4) if not __import__("pandas").isna(v) else None for v in recent_ind["macd"]],
            "macd_signal": [round(v, 4) if not __import__("pandas").isna(v) else None for v in recent_ind["macd_signal"]],
            "macd_hist": [round(v, 4) if not __import__("pandas").isna(v) else None for v in recent_ind["macd_hist"]],
        }

        return {
            "success": True,
            "analysis": analysis,
            "kline": kline,
            "indicators": indicators,
        }

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)},
        )


@app.get("/api/market_data/{symbol}")
async def get_market_data(symbol: str, start_date: str = "2024-01-01", end_date: str = "2025-06-30"):
    """获取市场数据"""
    try:
        data = data_provider.get_data(symbol, start_date, end_date)
        records = []
        for idx, row in data.iterrows():
            records.append({
                "date": str(idx)[:10],
                "open": round(row["open"], 2),
                "high": round(row["high"], 2),
                "low": round(row["low"], 2),
                "close": round(row["close"], 2),
                "volume": int(row["volume"]),
            })
        return {"success": True, "data": records, "count": len(records)}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)},
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
