/**
 * 量化交易智能体 — 静态前端应用
 * 所有计算在浏览器端完成，无需后端。
 */
let eqChart=null, prChart=null, rsiCh=null;

document.addEventListener('DOMContentLoaded',()=>{
    initNav(); initClock();
    document.getElementById('bt-form').addEventListener('submit',e=>{e.preventDefault();doBT()});
    document.getElementById('az-form').addEventListener('submit',e=>{e.preventDefault();doAZ()});
});

// ── 导航 ──
function initNav(){
    document.querySelectorAll('.nav li').forEach(li=>{
        li.addEventListener('click',()=>{
            document.querySelectorAll('.nav li').forEach(n=>n.classList.remove('on'));li.classList.add('on');
            document.querySelectorAll('.pg').forEach(p=>p.classList.remove('on'));
            document.getElementById('pg-'+li.dataset.p).classList.add('on');
        });
    });
}

// ── 时钟 ──
function initClock(){
    const tick=()=>{
        const now=new Date();
        const bj=new Date(now.getTime()+(now.getTimezoneOffset()+480)*60000);
        const h=bj.getHours(),d=bj.getDay();
        const trading=(d>=1&&d<=5)&&((h>=9&&h<11)||(h===11&&bj.getMinutes()<=30)||(h>=13&&h<15));
        const badge=document.getElementById('mkt-st');
        if(d===0||d===6){badge.textContent='休市';badge.className='badge rd';}
        else if(trading){badge.textContent='交易中';badge.className='badge gn';}
        else{badge.textContent=h<9?'盘前':h>=15?'已收盘':'午休';badge.className='badge rd';}
        document.getElementById('clock').textContent=bj.toLocaleString('zh-CN',{hour12:false});
    };tick();setInterval(tick,1000);
}

// ── 回测 ──
function doBT(){
    const btn=document.getElementById('btn-bt');btn.disabled=true;btn.textContent='⏳ 运行中...';
    const syms=[];document.querySelectorAll('#sym-cb input:checked').forEach(c=>syms.push(c.value));
    if(syms.length===0){alert('请至少选择一个标的');btn.disabled=false;btn.textContent='🚀 运行回测';return;}

    setTimeout(()=>{
        try{
            const result=runBacktest({
                symbols:syms,
                startDate:document.getElementById('bt-s').value,
                endDate:document.getElementById('bt-e').value,
                initialCapital:+document.getElementById('bt-cap').value,
                signalThreshold:+document.getElementById('bt-th').value,
                stopLossPct:+document.getElementById('bt-sl').value,
                takeProfitPct:+document.getElementById('bt-tp').value,
                maShort:+(document.getElementById('c-ms')?.value||10),
                maLong:+(document.getElementById('c-ml')?.value||30),
                rsiPeriod:+(document.getElementById('c-rp')?.value||14),
                maWeight:(+(document.getElementById('c-mw')?.value||40))/100,
                rsiWeight:(+(document.getElementById('c-rw')?.value||30))/100,
                macdWeight:(+(document.getElementById('c-mcw')?.value||30))/100,
            });
            showBT(result);
        }catch(e){alert('回测出错: '+e.message);}
        btn.disabled=false;btn.textContent='🚀 运行回测';
    },50);
}

function showBT(r){
    document.getElementById('bt-res').style.display='block';
    const m=r.metrics;
    const items=[
        {l:'总收益率',v:pct(m.totalReturn),c:m.totalReturn>=0?'pos':'neg'},
        {l:'最终权益',v:money(m.finalEquity),c:''},
        {l:'年化收益',v:pct(m.annualReturn),c:m.annualReturn>=0?'pos':'neg'},
        {l:'夏普比率',v:num(m.sharpe),c:m.sharpe>0?'pos':'neg'},
        {l:'最大回撤',v:pct(m.maxDD),c:'neg'},
        {l:'胜率',v:pct(m.winRate),c:m.winRate>=0.5?'pos':'neg'},
        {l:'盈亏比',v:m.profitRatio>0?num(m.profitRatio):'-',c:m.profitRatio>=1?'pos':'neg'},
        {l:'交易笔数',v:m.totalTrades,c:''},
    ];
    document.getElementById('bt-m').innerHTML=items.map(i=>`<div class="mi"><span class="ml">${i.l}</span><span class="mv ${i.c}">${i.v}</span></div>`).join('');

    // 权益曲线
    const ctx=document.getElementById('eq-chart').getContext('2d');
    if(eqChart)eqChart.destroy();
    const step=Math.max(1,Math.floor(r.equityCurve.length/120));
    const filtered=r.equityCurve.filter((_,i)=>i%step===0);
    eqChart=new Chart(ctx,{type:'line',data:{labels:filtered.map(d=>d.date),datasets:[{label:'权益曲线',data:filtered.map(d=>d.equity),borderColor:'#6366f1',backgroundColor:'rgba(99,102,241,.08)',fill:true,tension:.3,pointRadius:0,borderWidth:2}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{labels:{color:'#8b90a8',font:{size:11}}}},scales:{x:{ticks:{color:'#5c6080',maxTicksLimit:12,font:{size:9}},grid:{color:'rgba(42,46,74,.5)'}},y:{ticks:{color:'#5c6080',font:{size:10},callback:v=>(v/10000).toFixed(0)+'万'},grid:{color:'rgba(42,46,74,.5)'}}},interaction:{intersect:false,mode:'index'}}});

    // 交易表
    const tb=document.querySelector('#bt-tb tbody');
    tb.innerHTML=r.trades.map((t,i)=>{
        const sc=t.side==='buy'?'tb':'ts';const st=t.side==='buy'?'买入':'卖出';
        let pnl='-';if(t.pnl!=null){const pc=t.pnl>=0?'tb':'ts';pnl=`<span class="${pc}">${t.pnl>=0?'+':''}${t.pnl.toFixed(2)}</span>`;}
        return `<tr><td>${i+1}</td><td>${t.date}</td><td>${t.symbol}</td><td><span class="${sc}">${st}</span></td><td>${t.qty}</td><td>${t.price.toFixed(2)}</td><td>${t.comm.toFixed(2)}</td><td>${pnl}</td><td style="font-size:11px;color:var(--t3)">${t.reason||''}</td></tr>`;
    }).join('');
}

// ── 信号分析 ──
function doAZ(){
    const sym=document.getElementById('az-sym').value;
    const result=analyzeSymbol(sym,document.getElementById('az-s').value,document.getElementById('az-e').value);
    if(!result){alert('无数据');return;}
    showAZ(result);
}

function showAZ(a){
    document.getElementById('az-res').style.display='block';
    document.getElementById('az-title').textContent=`${a.symbol} ${a.name} 分析结果`;

    const cm={buy:'#22c55e',sell:'#ef4444',hold:'#8b90a8'};
    const tm={buy:'买入',sell:'卖出',hold:'观望'};
    let h=`<div class="ssc ${a.signalType}"><div class="ssl">综合信号</div><div class="ssv" style="color:${cm[a.signalType]}">${tm[a.signalType]}</div></div>`;
    h+=`<div class="ssc"><div class="ssl">最新价格</div><div class="ssv">${a.latestPrice.toFixed(2)}</div></div>`;
    h+=`<div class="ssc"><div class="ssl">信号强度</div><div class="ssv">${a.signalStrength.toFixed(4)}</div></div>`;
    h+='<div class="sd" style="flex-basis:100%">';
    a.strategies.forEach(s=>{h+=`<div class="sdi"><span>${s.name}</span><span style="color:${cm[s.type]};font-weight:600">${tm[s.type]} (${s.strength.toFixed(4)})</span></div>`;});
    h+='</div>';
    document.getElementById('az-sum').innerHTML=h;

    // 价格图
    const ctx1=document.getElementById('pr-chart').getContext('2d');if(prChart)prChart.destroy();
    const labels=a.kline.map(d=>d.d);const closes=a.kline.map(d=>d.c);
    const ds=[{label:'收盘价',data:closes,borderColor:'#e8eaf4',borderWidth:1.5,pointRadius:0,tension:.2}];
    if(a.indicators.sma10)ds.push({label:'SMA10',data:a.indicators.sma10,borderColor:'#f59e0b',borderWidth:1,pointRadius:0,borderDash:[4,2],tension:.3});
    if(a.indicators.sma30)ds.push({label:'SMA30',data:a.indicators.sma30,borderColor:'#6366f1',borderWidth:1,pointRadius:0,borderDash:[4,2],tension:.3});
    prChart=new Chart(ctx1,{type:'line',data:{labels,datasets:ds},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{labels:{color:'#8b90a8',font:{size:10}}}},scales:{x:{ticks:{color:'#5c6080',maxTicksLimit:10,font:{size:9}},grid:{color:'rgba(42,46,74,.4)'}},y:{ticks:{color:'#5c6080',font:{size:10}},grid:{color:'rgba(42,46,74,.4)'}}},interaction:{intersect:false,mode:'index'}}});

    // RSI图
    const ctx2=document.getElementById('rsi-chart').getContext('2d');if(rsiCh)rsiCh.destroy();
    rsiCh=new Chart(ctx2,{type:'line',data:{labels,datasets:[{label:'RSI',data:a.indicators.rsi,borderColor:'#a855f7',borderWidth:1.5,pointRadius:0,tension:.3}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{labels:{color:'#8b90a8',font:{size:10}}}},scales:{x:{ticks:{color:'#5c6080',maxTicksLimit:10,font:{size:9}},grid:{color:'rgba(42,46,74,.3)'}},y:{min:0,max:100,ticks:{color:'#5c6080',font:{size:10},stepSize:20},grid:{color:'rgba(42,46,74,.3)'}}}},
    plugins:[{id:'rz',beforeDraw(chart){const{ctx,chartArea:ca,scales:sc}=chart;if(!ca)return;const y70=sc.y.getPixelForValue(70),y30=sc.y.getPixelForValue(30);ctx.fillStyle='rgba(239,68,68,.06)';ctx.fillRect(ca.left,ca.top,ca.width,y70-ca.top);ctx.fillStyle='rgba(34,197,94,.06)';ctx.fillRect(ca.left,y30,ca.width,ca.bottom-y30);ctx.strokeStyle='rgba(239,68,68,.3)';ctx.setLineDash([4,4]);ctx.beginPath();ctx.moveTo(ca.left,y70);ctx.lineTo(ca.right,y70);ctx.stroke();ctx.strokeStyle='rgba(34,197,94,.3)';ctx.beginPath();ctx.moveTo(ca.left,y30);ctx.lineTo(ca.right,y30);ctx.stroke();ctx.setLineDash([]);}}]});
}

// ── 工具 ──
function pct(v){return v!=null?(v*100).toFixed(2)+'%':'-';}
function num(v){return v!=null?v.toFixed(4):'-';}
function money(v){return v!=null?'¥'+Math.round(v).toLocaleString():'-';}
