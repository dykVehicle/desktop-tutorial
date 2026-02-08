/**
 * 量化交易智能体 - 前端应用
 */

// ── 全局状态 ──
let equityChart = null;
let priceChart = null;
let rsiChart = null;

// ── 初始化 ──
document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    initClock();
    loadStatus();
    initBacktestForm();
    initAnalyzeForm();
});

// ── 导航 ──
function initNavigation() {
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', () => {
            const page = item.dataset.page;
            document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
            item.classList.add('active');
            document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
            document.getElementById(`page-${page}`).classList.add('active');
        });
    });
}

// ── 时钟 ──
function initClock() {
    function tick() {
        const now = new Date();
        const bjOffset = 8 * 60;
        const utc = now.getTime() + now.getTimezoneOffset() * 60000;
        const bj = new Date(utc + bjOffset * 60000);
        const timeStr = bj.toLocaleTimeString('zh-CN', { hour12: false });
        const dateStr = bj.toLocaleDateString('zh-CN');
        document.getElementById('clock').textContent = `${dateStr} ${timeStr}`;
    }
    tick();
    setInterval(tick, 1000);
}

// ── 系统状态 ──
async function loadStatus() {
    try {
        const res = await fetch('/api/status');
        const data = await res.json();
        const badge = document.getElementById('market-status');
        badge.textContent = data.market_status;
        if (data.is_trading) {
            badge.className = 'status-badge trading';
        } else {
            badge.className = 'status-badge closed';
        }
    } catch (e) {
        console.error('加载状态失败', e);
    }
}

// ── 回测引擎 ──
function initBacktestForm() {
    document.getElementById('backtest-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        await runBacktest();
    });
}

async function runBacktest() {
    const btn = document.getElementById('btn-backtest');
    btn.disabled = true;
    btn.querySelector('.btn-text').style.display = 'none';
    btn.querySelector('.btn-loading').style.display = 'inline';

    const symbols = [];
    document.querySelectorAll('#symbol-checkboxes input:checked').forEach(cb => {
        symbols.push(cb.value);
    });

    const payload = {
        symbols: symbols,
        start_date: document.getElementById('bt-start').value,
        end_date: document.getElementById('bt-end').value,
        initial_capital: parseFloat(document.getElementById('bt-capital').value),
        signal_threshold: parseFloat(document.getElementById('bt-threshold').value),
        stop_loss_pct: parseFloat(document.getElementById('bt-stoploss').value),
        take_profit_pct: parseFloat(document.getElementById('bt-takeprofit').value),
        ma_short: parseInt(document.getElementById('cfg-ma-short')?.value || 10),
        ma_long: parseInt(document.getElementById('cfg-ma-long')?.value || 30),
        rsi_period: parseInt(document.getElementById('cfg-rsi-period')?.value || 14),
        ma_weight: parseFloat(document.getElementById('cfg-ma-weight')?.value || 40) / 100,
        rsi_weight: parseFloat(document.getElementById('cfg-rsi-weight')?.value || 30) / 100,
        macd_weight: parseFloat(document.getElementById('cfg-macd-weight')?.value || 30) / 100,
    };

    try {
        const res = await fetch('/api/backtest', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        const data = await res.json();

        if (data.success) {
            displayBacktestResults(data);
        } else {
            alert('回测失败: ' + (data.error || '未知错误'));
        }
    } catch (e) {
        alert('请求失败: ' + e.message);
    } finally {
        btn.disabled = false;
        btn.querySelector('.btn-text').style.display = 'inline';
        btn.querySelector('.btn-loading').style.display = 'none';
    }
}

function displayBacktestResults(data) {
    const panel = document.getElementById('backtest-results');
    panel.style.display = 'block';

    const m = data.metrics;

    // 指标卡
    const metricsEl = document.getElementById('bt-metrics');
    const metricItems = [
        { label: '总收益率', value: fmtPct(m.total_return), cls: m.total_return >= 0 ? 'positive' : 'negative' },
        { label: '最终权益', value: fmtMoney(m.final_equity), cls: '' },
        { label: '年化收益率', value: fmtPct(m.annualized_return), cls: m.annualized_return >= 0 ? 'positive' : 'negative' },
        { label: '夏普比率', value: fmtNum(m.sharpe_ratio), cls: m.sharpe_ratio > 0 ? 'positive' : 'negative' },
        { label: '最大回撤', value: fmtPct(m.max_drawdown), cls: 'negative' },
        { label: '胜率', value: fmtPct(m.win_rate), cls: m.win_rate >= 0.5 ? 'positive' : 'negative' },
        { label: '总交易', value: m.total_trades, cls: '' },
        { label: '盈利 / 亏损', value: `${m.winning_trades} / ${m.losing_trades}`, cls: '' },
    ];

    metricsEl.innerHTML = metricItems.map(i =>
        `<div class="metric-item">
            <span class="metric-label">${i.label}</span>
            <span class="metric-value ${i.cls}">${i.value}</span>
        </div>`
    ).join('');

    // 权益曲线
    renderEquityChart(data.equity_curve);

    // 交易表格
    const tbody = document.querySelector('#trades-table tbody');
    tbody.innerHTML = data.trades.map((t, idx) => {
        const sideClass = t.side === 'buy' ? 'tag-buy' : 'tag-sell';
        const sideText = t.side === 'buy' ? '买入' : '卖出';
        let pnlHtml = '-';
        if (t.pnl !== null) {
            const pnlClass = t.pnl >= 0 ? 'pnl-positive' : 'pnl-negative';
            pnlHtml = `<span class="${pnlClass}">${t.pnl >= 0 ? '+' : ''}${t.pnl.toFixed(2)}</span>`;
        }
        return `<tr>
            <td>${idx + 1}</td>
            <td>${t.date}</td>
            <td>${t.symbol}</td>
            <td><span class="${sideClass}">${sideText}</span></td>
            <td>${t.quantity}</td>
            <td>${t.price.toFixed(2)}</td>
            <td>${t.commission.toFixed(2)}</td>
            <td>${pnlHtml}</td>
        </tr>`;
    }).join('');
}

function renderEquityChart(equityData) {
    const ctx = document.getElementById('equity-chart').getContext('2d');
    if (equityChart) equityChart.destroy();

    const labels = equityData.filter((_, i) => i % 5 === 0).map(d => d.date);
    const values = equityData.filter((_, i) => i % 5 === 0).map(d => d.equity);

    equityChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: '权益曲线',
                data: values,
                borderColor: '#6366f1',
                backgroundColor: 'rgba(99,102,241,0.1)',
                fill: true,
                tension: 0.3,
                pointRadius: 0,
                borderWidth: 2,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { labels: { color: '#8b8fa3', font: { size: 12 } } },
            },
            scales: {
                x: { ticks: { color: '#5a5e72', maxRotation: 45, font: { size: 10 }, maxTicksLimit: 15 }, grid: { color: 'rgba(42,47,69,0.5)' } },
                y: { ticks: { color: '#5a5e72', font: { size: 11 }, callback: v => (v/10000).toFixed(0) + '万' }, grid: { color: 'rgba(42,47,69,0.5)' } },
            },
            interaction: { intersect: false, mode: 'index' },
        }
    });
}

// ── 信号分析 ──
function initAnalyzeForm() {
    document.getElementById('analyze-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        await runAnalysis();
    });
}

async function runAnalysis() {
    const btn = document.getElementById('btn-analyze');
    btn.disabled = true;
    btn.querySelector('.btn-text').style.display = 'none';
    btn.querySelector('.btn-loading').style.display = 'inline';

    const payload = {
        symbol: document.getElementById('az-symbol').value,
        start_date: document.getElementById('az-start').value,
        end_date: document.getElementById('az-end').value,
    };

    try {
        const res = await fetch('/api/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (data.success) {
            displayAnalysisResults(data);
        } else {
            alert('分析失败: ' + (data.error || '未知错误'));
        }
    } catch (e) {
        alert('请求失败: ' + e.message);
    } finally {
        btn.disabled = false;
        btn.querySelector('.btn-text').style.display = 'inline';
        btn.querySelector('.btn-loading').style.display = 'none';
    }
}

function displayAnalysisResults(data) {
    const panel = document.getElementById('analysis-results');
    panel.style.display = 'block';

    const a = data.analysis;
    document.getElementById('az-title').textContent = `${a.symbol} 分析结果`;

    // 信号摘要
    const typeMap = { buy: ['买入', 'buy'], sell: ['卖出', 'sell'], hold: ['观望', 'hold'] };
    const [typeText, typeCls] = typeMap[a.signal_type] || ['未知', 'hold'];
    const colorMap = { buy: '#22c55e', sell: '#ef4444', hold: '#8b8fa3' };

    let html = `
        <div class="signal-card ${typeCls}">
            <div class="signal-label">综合信号</div>
            <div class="signal-value" style="color:${colorMap[a.signal_type]}">${typeText}</div>
        </div>
        <div class="signal-card">
            <div class="signal-label">最新价格</div>
            <div class="signal-value">${a.latest_price.toFixed(2)}</div>
        </div>
        <div class="signal-card">
            <div class="signal-label">信号强度</div>
            <div class="signal-value">${a.signal_strength.toFixed(4)}</div>
        </div>
    `;
    html += `<div class="signal-detail" style="flex-basis:100%">`;
    a.strategy_signals.forEach(s => {
        const sc = colorMap[s.type] || '#8b8fa3';
        html += `<div class="sig-item">
            <span>${s.strategy}</span>
            <span style="color:${sc};font-weight:600">${s.type} (${s.strength.toFixed(4)})</span>
            <span style="color:var(--text-muted);font-size:12px">${s.reason}</span>
        </div>`;
    });
    html += `</div>`;
    document.getElementById('az-summary').innerHTML = html;

    // 价格走势图 + 均线
    renderPriceChart(data.kline, data.indicators);
    renderRSIChart(data.kline, data.indicators);
}

function renderPriceChart(kline, indicators) {
    const ctx = document.getElementById('price-chart').getContext('2d');
    if (priceChart) priceChart.destroy();

    const labels = kline.map(d => d.date);
    const closes = kline.map(d => d.close);

    const datasets = [
        { label: '收盘价', data: closes, borderColor: '#e4e6f0', borderWidth: 1.5, pointRadius: 0, tension: 0.2 },
    ];
    if (indicators.sma_10) {
        datasets.push({ label: 'SMA10', data: indicators.sma_10, borderColor: '#f59e0b', borderWidth: 1, pointRadius: 0, borderDash: [4, 2], tension: 0.3 });
    }
    if (indicators.sma_30) {
        datasets.push({ label: 'SMA30', data: indicators.sma_30, borderColor: '#6366f1', borderWidth: 1, pointRadius: 0, borderDash: [4, 2], tension: 0.3 });
    }

    priceChart = new Chart(ctx, {
        type: 'line',
        data: { labels, datasets },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { labels: { color: '#8b8fa3', font: { size: 11 } } } },
            scales: {
                x: { ticks: { color: '#5a5e72', maxTicksLimit: 12, font: { size: 10 } }, grid: { color: 'rgba(42,47,69,0.5)' } },
                y: { ticks: { color: '#5a5e72', font: { size: 11 } }, grid: { color: 'rgba(42,47,69,0.5)' } },
            },
            interaction: { intersect: false, mode: 'index' },
        }
    });
}

function renderRSIChart(kline, indicators) {
    const ctx = document.getElementById('rsi-chart').getContext('2d');
    if (rsiChart) rsiChart.destroy();

    const labels = kline.map(d => d.date);

    rsiChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [{
                label: 'RSI',
                data: indicators.rsi,
                borderColor: '#a855f7',
                borderWidth: 1.5,
                pointRadius: 0,
                tension: 0.3,
            }]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: {
                legend: { labels: { color: '#8b8fa3', font: { size: 11 } } },
                annotation: {}
            },
            scales: {
                x: { ticks: { color: '#5a5e72', maxTicksLimit: 12, font: { size: 10 } }, grid: { color: 'rgba(42,47,69,0.3)' } },
                y: {
                    min: 0, max: 100,
                    ticks: { color: '#5a5e72', font: { size: 11 }, stepSize: 20 },
                    grid: { color: 'rgba(42,47,69,0.3)' },
                },
            },
        },
        plugins: [{
            id: 'rsiZones',
            beforeDraw(chart) {
                const { ctx, chartArea, scales } = chart;
                if (!chartArea) return;
                const y70 = scales.y.getPixelForValue(70);
                const y30 = scales.y.getPixelForValue(30);
                // 超买区
                ctx.fillStyle = 'rgba(239,68,68,0.06)';
                ctx.fillRect(chartArea.left, chartArea.top, chartArea.width, y70 - chartArea.top);
                // 超卖区
                ctx.fillStyle = 'rgba(34,197,94,0.06)';
                ctx.fillRect(chartArea.left, y30, chartArea.width, chartArea.bottom - y30);
                // 参考线
                ctx.strokeStyle = 'rgba(239,68,68,0.3)';
                ctx.setLineDash([4, 4]);
                ctx.beginPath(); ctx.moveTo(chartArea.left, y70); ctx.lineTo(chartArea.right, y70); ctx.stroke();
                ctx.strokeStyle = 'rgba(34,197,94,0.3)';
                ctx.beginPath(); ctx.moveTo(chartArea.left, y30); ctx.lineTo(chartArea.right, y30); ctx.stroke();
                ctx.setLineDash([]);
            }
        }]
    });
}

// ── 工具函数 ──
function fmtPct(v) { return v != null ? (v * 100).toFixed(2) + '%' : '-'; }
function fmtNum(v) { return v != null ? v.toFixed(4) : '-'; }
function fmtMoney(v) { return v != null ? '¥' + Math.round(v).toLocaleString() : '-'; }
