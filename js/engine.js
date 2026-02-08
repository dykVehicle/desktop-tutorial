/**
 * 量化交易智能体 — 纯浏览器端回测引擎
 *
 * 包含: 技术指标 / 三大策略 / 信号融合 / 回测执行
 * 完全在客户端运行，无需后端。
 */

// ═══════════════════════════════════════════════════
//  技术指标
// ═══════════════════════════════════════════════════

const Indicators = {
    sma(data, period) {
        const result = new Array(data.length).fill(null);
        for (let i = period - 1; i < data.length; i++) {
            let sum = 0;
            for (let j = i - period + 1; j <= i; j++) sum += data[j];
            result[i] = sum / period;
        }
        return result;
    },

    ema(data, period) {
        const result = new Array(data.length).fill(null);
        const k = 2 / (period + 1);
        result[0] = data[0];
        for (let i = 1; i < data.length; i++) {
            result[i] = data[i] * k + result[i - 1] * (1 - k);
        }
        return result;
    },

    rsi(data, period = 14) {
        const result = new Array(data.length).fill(null);
        const gains = [], losses = [];
        for (let i = 1; i < data.length; i++) {
            const diff = data[i] - data[i - 1];
            gains.push(diff > 0 ? diff : 0);
            losses.push(diff < 0 ? -diff : 0);
        }
        // EMA of gains/losses
        let avgGain = 0, avgLoss = 0;
        for (let i = 0; i < period; i++) { avgGain += gains[i]; avgLoss += losses[i]; }
        avgGain /= period; avgLoss /= period;
        result[period] = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss);
        for (let i = period; i < gains.length; i++) {
            avgGain = (avgGain * (period - 1) + gains[i]) / period;
            avgLoss = (avgLoss * (period - 1) + losses[i]) / period;
            result[i + 1] = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss);
        }
        return result;
    },

    macd(data, fast = 12, slow = 26, signal = 9) {
        const emaFast = this.ema(data, fast);
        const emaSlow = this.ema(data, slow);
        const macdLine = data.map((_, i) =>
            emaFast[i] != null && emaSlow[i] != null ? emaFast[i] - emaSlow[i] : null
        );
        const validMacd = macdLine.map(v => v ?? 0);
        const signalLine = this.ema(validMacd, signal);
        const histogram = macdLine.map((v, i) =>
            v != null && signalLine[i] != null ? v - signalLine[i] : null
        );
        return { macdLine, signalLine, histogram };
    },
};

// ═══════════════════════════════════════════════════
//  策略信号生成
// ═══════════════════════════════════════════════════

const Strategies = {
    /** MA均线交叉 (含趋势过滤) */
    maCrossover(closes, shortW = 10, longW = 30) {
        const shortMA = Indicators.sma(closes, shortW);
        const longMA = Indicators.sma(closes, longW);
        const trendMA = Indicators.sma(closes, Math.max(longW * 2, 60));
        const signals = new Array(closes.length).fill(0);

        for (let i = 1; i < closes.length; i++) {
            if (shortMA[i] == null || longMA[i] == null || shortMA[i-1] == null || longMA[i-1] == null) continue;
            const prevDiff = shortMA[i-1] - longMA[i-1];
            const currDiff = shortMA[i] - longMA[i];
            let strength = Math.min(Math.abs(currDiff) / closes[i] * 50, 1);

            const hasTrend = trendMA[i] != null;
            const isUptrend = hasTrend && closes[i] > trendMA[i];
            const isDowntrend = hasTrend && closes[i] < trendMA[i];

            if (prevDiff <= 0 && currDiff > 0) {
                if (hasTrend && !isUptrend) strength *= 0.3;
                signals[i] = strength;
            } else if (prevDiff >= 0 && currDiff < 0) {
                if (hasTrend && !isDowntrend) strength *= 0.3;
                signals[i] = -strength;
            }
        }
        return { signals, shortMA, longMA };
    },

    /** RSI超买超卖 */
    rsiStrategy(closes, period = 14, ob = 70, os = 30) {
        const rsi = Indicators.rsi(closes, period);
        const signals = new Array(closes.length).fill(0);

        for (let i = 1; i < closes.length; i++) {
            if (rsi[i] == null || rsi[i-1] == null) continue;
            if (rsi[i-1] <= os && rsi[i] > os) {
                signals[i] = Math.min(Math.max((os - Math.min(rsi[i-1], os)) / os, 0.3), 1);
            } else if (rsi[i-1] >= ob && rsi[i] < ob) {
                signals[i] = -Math.min(Math.max((Math.max(rsi[i-1], ob) - ob) / (100 - ob), 0.3), 1);
            }
        }
        return { signals, rsi };
    },

    /** MACD柱状图交叉 */
    macdStrategy(closes, fast = 12, slow = 26, sig = 9) {
        const { macdLine, signalLine, histogram } = Indicators.macd(closes, fast, slow, sig);
        const signals = new Array(closes.length).fill(0);

        // 计算柱状图std用于归一化
        const validHist = histogram.filter(v => v != null);
        const histStd = validHist.length > 0 ? Math.sqrt(validHist.reduce((s, v) => s + v * v, 0) / validHist.length) : 1;

        for (let i = 1; i < closes.length; i++) {
            if (histogram[i] == null || histogram[i-1] == null) continue;
            const strength = Math.min(Math.abs(histogram[i]) / (histStd || 1), 1);
            if (histogram[i-1] <= 0 && histogram[i] > 0) signals[i] = strength;
            else if (histogram[i-1] >= 0 && histogram[i] < 0) signals[i] = -strength;
        }
        return { signals, macdLine, signalLine, histogram };
    },
};

// ═══════════════════════════════════════════════════
//  回测引擎
// ═══════════════════════════════════════════════════

function runBacktest(params) {
    const {
        symbols, startDate, endDate,
        initialCapital = 1000000,
        signalThreshold = 0.15,
        stopLossPct = 0.07,
        takeProfitPct = 0.10,
        maShort = 10, maLong = 30,
        rsiPeriod = 14,
        maWeight = 0.4, rsiWeight = 0.3, macdWeight = 0.3,
    } = params;

    // 准备数据
    const allBars = {};
    symbols.forEach(sym => {
        if (!MARKET_DATA[sym]) return;
        allBars[sym] = MARKET_DATA[sym].data.filter(b => b.d >= startDate && b.d <= endDate);
    });

    // 所有日期
    const dateSet = new Set();
    Object.values(allBars).forEach(bars => bars.forEach(b => dateSet.add(b.d)));
    const allDates = [...dateSet].sort();
    if (allDates.length === 0) return { metrics: { error: '无数据' }, equityCurve: [], trades: [] };

    // 计算各策略信号
    const stratSignals = {};
    Object.entries(allBars).forEach(([sym, bars]) => {
        const closes = bars.map(b => b.c);
        const ma = Strategies.maCrossover(closes, maShort, maLong);
        const rsi = Strategies.rsiStrategy(closes, rsiPeriod);
        const macd = Strategies.macdStrategy(closes);

        const dateMap = {};
        bars.forEach((b, i) => {
            dateMap[b.d] = {
                price: b.c,
                ma: ma.signals[i], rsi: rsi.signals[i], macd: macd.signals[i],
                rsiVal: rsi.rsi[i], shortMA: ma.shortMA[i], longMA: ma.longMA[i],
                macdLine: macd.macdLine[i], macdSignal: macd.signalLine[i], macdHist: macd.histogram[i],
            };
        });
        stratSignals[sym] = dateMap;
    });

    // 模拟交易
    let cash = initialCapital;
    const positions = {}; // sym -> { qty, avgPrice }
    const posHigh = {};   // sym -> highest price
    const lastTrade = {};  // sym -> date index
    const cooldown = 10;
    const trades = [];
    const equityCurve = [];
    const commRate = 0.001, slippage = 0.001;

    allDates.forEach((date, dateIdx) => {
        // 获取当日价格
        const prices = {};
        Object.keys(allBars).forEach(sym => {
            const s = stratSignals[sym][date];
            if (s) prices[sym] = s.price;
        });

        // 更新持仓最高价
        Object.entries(prices).forEach(([sym, p]) => {
            if (positions[sym]) posHigh[sym] = Math.max(posHigh[sym] || p, p);
        });

        // 止损止盈检查
        Object.keys({...positions}).forEach(sym => {
            if (!prices[sym] || !positions[sym]) return;
            const pos = positions[sym];
            const price = prices[sym];
            const lossPct = (pos.avgPrice - price) / pos.avgPrice;
            const profitPct = (price - pos.avgPrice) / pos.avgPrice;
            const highest = posHigh[sym] || price;
            const pullback = (highest - price) / highest;
            const trailingActive = (highest - pos.avgPrice) / pos.avgPrice >= 0.03;

            let shouldSell = false, reason = '';
            if (lossPct >= stopLossPct) { shouldSell = true; reason = `止损 ${(lossPct*100).toFixed(1)}%`; }
            else if (trailingActive && pullback >= 0.05) { shouldSell = true; reason = `移动止损 从高点回撤${(pullback*100).toFixed(1)}%`; }
            else if (profitPct >= takeProfitPct) { shouldSell = true; reason = `止盈 ${(profitPct*100).toFixed(1)}%`; }

            if (shouldSell) {
                const sellPrice = +(price * (1 - slippage)).toFixed(2);
                const comm = +(pos.qty * sellPrice * commRate).toFixed(2);
                const pnl = +((sellPrice - pos.avgPrice) * pos.qty - comm).toFixed(2);
                cash += pos.qty * sellPrice - comm;
                trades.push({ date, symbol: sym, side: 'sell', qty: pos.qty, price: sellPrice, comm, pnl, reason });
                delete positions[sym]; delete posHigh[sym];
                lastTrade[sym] = dateIdx;
            }
        });

        // 信号融合 + 交易
        Object.keys(allBars).forEach(sym => {
            if (!prices[sym]) return;
            // 冷却期
            if (lastTrade[sym] != null && dateIdx - lastTrade[sym] < cooldown) return;

            // 近5天信号窗口
            let combined = 0, totalW = 0, buyCount = 0, sellCount = 0;
            for (let lookback = 0; lookback < 5; lookback++) {
                const ld = allDates[Math.max(0, dateIdx - lookback)];
                const s = stratSignals[sym][ld];
                if (!s) continue;
                // 取最近有信号的一天
                if (s.ma !== 0 && !totalW) { combined += s.ma * maWeight; totalW += maWeight; s.ma > 0 ? buyCount++ : sellCount++; }
                if (s.rsi !== 0 && totalW < maWeight + rsiWeight) { combined += s.rsi * rsiWeight; totalW += rsiWeight; s.rsi > 0 ? buyCount++ : sellCount++; }
                if (s.macd !== 0 && totalW < maWeight + rsiWeight + macdWeight) { combined += s.macd * macdWeight; totalW += macdWeight; s.macd > 0 ? buyCount++ : sellCount++; }
                if (totalW >= maWeight + rsiWeight + macdWeight - 0.01) break;
            }
            if (totalW > 0) combined /= totalW;

            const consensus = (buyCount >= 2 && combined > 0) || (sellCount >= 2 && combined < 0);
            if (Math.abs(combined) < signalThreshold || !consensus) return;

            const price = prices[sym];

            if (combined > 0 && !positions[sym]) {
                const posSize = Math.abs(combined) * 0.25;
                const equity = cash + Object.entries(positions).reduce((s, [k, v]) => s + v.qty * (prices[k] || v.avgPrice), 0);
                const qty = Math.floor(equity * posSize / price);
                if (qty <= 0) return;
                const buyPrice = +(price * (1 + slippage)).toFixed(2);
                const comm = +(qty * buyPrice * commRate).toFixed(2);
                const cost = qty * buyPrice + comm;
                if (cost > cash) return;
                cash -= cost;
                positions[sym] = { qty, avgPrice: buyPrice };
                posHigh[sym] = buyPrice;
                lastTrade[sym] = dateIdx;
                trades.push({ date, symbol: sym, side: 'buy', qty, price: buyPrice, comm, pnl: null, reason: '信号买入' });
            } else if (combined < 0 && positions[sym]) {
                const pos = positions[sym];
                const sellPrice = +(price * (1 - slippage)).toFixed(2);
                const comm = +(pos.qty * sellPrice * commRate).toFixed(2);
                const pnl = +((sellPrice - pos.avgPrice) * pos.qty - comm).toFixed(2);
                cash += pos.qty * sellPrice - comm;
                trades.push({ date, symbol: sym, side: 'sell', qty: pos.qty, price: sellPrice, comm, pnl, reason: '信号卖出' });
                delete positions[sym]; delete posHigh[sym];
                lastTrade[sym] = dateIdx;
            }
        });

        // 权益
        const posValue = Object.entries(positions).reduce((s, [k, v]) => s + v.qty * (prices[k] || v.avgPrice), 0);
        equityCurve.push({ date, equity: +(cash + posValue).toFixed(2) });
    });

    // 计算绩效
    const finalEquity = equityCurve.length > 0 ? equityCurve[equityCurve.length - 1].equity : initialCapital;
    const totalReturn = (finalEquity - initialCapital) / initialCapital;
    const sellTrades = trades.filter(t => t.side === 'sell');
    const winning = sellTrades.filter(t => t.pnl > 0);
    const losing = sellTrades.filter(t => t.pnl <= 0);
    const winRate = sellTrades.length > 0 ? winning.length / sellTrades.length : 0;

    // 日收益率
    const dailyRet = [];
    for (let i = 1; i < equityCurve.length; i++) {
        dailyRet.push(equityCurve[i].equity / equityCurve[i-1].equity - 1);
    }
    const avgDailyRet = dailyRet.length > 0 ? dailyRet.reduce((a, b) => a + b, 0) / dailyRet.length : 0;
    const stdDailyRet = dailyRet.length > 1 ? Math.sqrt(dailyRet.reduce((s, r) => s + (r - avgDailyRet) ** 2, 0) / (dailyRet.length - 1)) : 0;
    const annualReturn = (1 + totalReturn) ** (252 / Math.max(dailyRet.length, 1)) - 1;
    const annualVol = stdDailyRet * Math.sqrt(252);
    const sharpe = annualVol > 0 ? (annualReturn - 0.03) / annualVol : 0;

    // 最大回撤
    let peak = 0, maxDD = 0;
    equityCurve.forEach(e => { peak = Math.max(peak, e.equity); maxDD = Math.max(maxDD, (peak - e.equity) / peak); });

    const avgWin = winning.length > 0 ? winning.reduce((s, t) => s + t.pnl, 0) / winning.length : 0;
    const avgLoss = losing.length > 0 ? losing.reduce((s, t) => s + t.pnl, 0) / losing.length : 0;
    const profitRatio = losing.length > 0 && avgLoss !== 0 ? Math.abs(avgWin / avgLoss) : 0;

    return {
        metrics: {
            initialCapital, finalEquity, totalReturn, annualReturn, annualVol, sharpe, maxDD,
            totalTrades: trades.length, buyTrades: trades.filter(t => t.side === 'buy').length,
            sellTrades: sellTrades.length, winningTrades: winning.length, losingTrades: losing.length,
            winRate, avgWin, avgLoss, profitRatio,
            totalCommission: +trades.reduce((s, t) => s + t.comm, 0).toFixed(2),
        },
        equityCurve,
        trades,
    };
}

// ═══════════════════════════════════════════════════
//  标的分析
// ═══════════════════════════════════════════════════

function analyzeSymbol(symbol, startDate, endDate) {
    if (!MARKET_DATA[symbol]) return null;
    const bars = MARKET_DATA[symbol].data.filter(b => b.d >= startDate && b.d <= endDate);
    if (bars.length === 0) return null;
    const closes = bars.map(b => b.c);

    const ma = Strategies.maCrossover(closes);
    const rsi = Strategies.rsiStrategy(closes);
    const macd = Strategies.macdStrategy(closes);

    // 最新信号
    const last = bars.length - 1;
    const maStr = ma.signals[last] || 0;
    const rsiStr = rsi.signals[last] || 0;
    const macdStr = macd.signals[last] || 0;
    const combined = (maStr * 0.4 + rsiStr * 0.3 + macdStr * 0.3);
    const signalType = combined >= 0.15 ? 'buy' : combined <= -0.15 ? 'sell' : 'hold';

    // 最近60天数据
    const recent = bars.slice(-60);
    const recentCloses = closes.slice(-60);

    return {
        symbol,
        name: MARKET_DATA[symbol].name,
        latestPrice: closes[last],
        signalType,
        signalStrength: combined,
        strategies: [
            { name: 'MA交叉', strength: maStr, type: maStr > 0.01 ? 'buy' : maStr < -0.01 ? 'sell' : 'hold' },
            { name: 'RSI', strength: rsiStr, type: rsiStr > 0.01 ? 'buy' : rsiStr < -0.01 ? 'sell' : 'hold' },
            { name: 'MACD', strength: macdStr, type: macdStr > 0.01 ? 'buy' : macdStr < -0.01 ? 'sell' : 'hold' },
        ],
        kline: recent,
        indicators: {
            sma10: Indicators.sma(recentCloses, 10),
            sma30: Indicators.sma(recentCloses, Math.min(30, recentCloses.length)),
            rsi: Indicators.rsi(recentCloses, 14),
            macdLine: Indicators.macd(recentCloses).macdLine,
            macdSignal: Indicators.macd(recentCloses).signalLine,
            macdHist: Indicators.macd(recentCloses).histogram,
        },
    };
}
