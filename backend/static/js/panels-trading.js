/* panels-trading.js — Trading, Backtesting, Strategies, Polymarket, Money/Council */

// ── Portfolio Allocation Pie Chart ───────────────────────────
function _renderPortfolioAllocation(positions, equity) {
    if (typeof Chart === 'undefined') return;
    const canvas = document.getElementById('chart-portfolio-allocation');
    if (!canvas) return;

    if (!positions || !positions.length) {
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        const parent = canvas.parentElement;
        const msg = parent.querySelector('.alloc-empty') || document.createElement('div');
        msg.className = 'alloc-empty';
        msg.style.cssText = 'position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:12px;color:var(--text-muted)';
        msg.textContent = 'No open positions';
        parent.style.position = 'relative';
        parent.appendChild(msg);
        return;
    }

    const cs = getComputedStyle(document.documentElement);
    const colors = [
        cs.getPropertyValue('--accent').trim(),
        cs.getPropertyValue('--accent-green').trim(),
        cs.getPropertyValue('--accent-cyan').trim(),
        cs.getPropertyValue('--accent-gold').trim(),
        cs.getPropertyValue('--accent-blue').trim(),
        cs.getPropertyValue('--accent-purple').trim(),
        cs.getPropertyValue('--accent-orange').trim(),
        cs.getPropertyValue('--accent-red').trim(),
    ];
    const textMuted = cs.getPropertyValue('--text-muted').trim();

    const labels = positions.map(p => p.symbol);
    const values = positions.map(p => Math.abs(p.market_value || p.qty * (p.current_price || p.avg_entry_price || 1)));
    const cashValue = Math.max(0, (equity || 0) - values.reduce((a, b) => a + b, 0));
    if (cashValue > 0) { labels.push('Cash'); values.push(cashValue); }

    _renderChart('chart-portfolio-allocation', {
        type: 'doughnut',
        data: {
            labels,
            datasets: [{
                data: values,
                backgroundColor: colors.map(c => c + 'bb'),
                borderColor: colors,
                borderWidth: 1.5,
                hoverOffset: 6,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'right',
                    labels: { color: textMuted, font: { size: 10 }, boxWidth: 10, padding: 8 },
                },
                tooltip: {
                    callbacks: {
                        label: ctx => {
                            const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
                            const pct = total > 0 ? ((ctx.parsed / total) * 100).toFixed(1) : '0';
                            return ` ${ctx.label}: $${ctx.parsed.toLocaleString(undefined, {maximumFractionDigits:0})} (${pct}%)`;
                        },
                    },
                },
            },
        },
    });
}

// ── P&L Timeline Chart ───────────────────────────────────────
function _renderPnLTimeline(trades) {
    if (typeof Chart === 'undefined') return;
    const canvas = document.getElementById('chart-pnl-timeline');
    if (!canvas) return;

    const cs = getComputedStyle(document.documentElement);
    const textMuted = cs.getPropertyValue('--text-muted').trim();
    const border = cs.getPropertyValue('--border').trim();

    // Build cumulative P&L from closed trades
    const closed = (trades || []).filter(t => t.pnl !== undefined || t.profit_loss !== undefined || t.exit_price)
        .sort((a, b) => new Date(a.created_at || a.exit_time || 0) - new Date(b.created_at || b.exit_time || 0));

    if (!closed.length) {
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        return;
    }

    let cumulative = 0;
    const points = closed.map(t => {
        const pnl = t.pnl || t.profit_loss || ((t.exit_price || 0) - (t.avg_entry_price || t.entry_price || 0)) * (t.qty || 1);
        cumulative += pnl;
        return cumulative;
    });

    const labels = closed.map(t => {
        const d = new Date(t.created_at || t.exit_time || Date.now());
        return `${d.getMonth()+1}/${d.getDate()}`;
    });

    const finalPnl = points[points.length - 1] || 0;
    const lineColor = finalPnl >= 0 ? cs.getPropertyValue('--accent-green').trim() : cs.getPropertyValue('--accent-red').trim();

    _renderChart('chart-pnl-timeline', {
        type: 'line',
        data: {
            labels,
            datasets: [{
                label: 'Cumulative P&L',
                data: points,
                borderColor: lineColor,
                backgroundColor: lineColor + '18',
                fill: true,
                tension: 0.3,
                pointRadius: closed.length > 20 ? 0 : 3,
                pointHoverRadius: 4,
                borderWidth: 2,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: ctx => ` P&L: $${ctx.parsed.y.toFixed(2)}`,
                    },
                },
            },
            scales: {
                x: { ticks: { color: textMuted, font: { size: 9 }, maxTicksLimit: 8 }, grid: { color: border + '30' } },
                y: {
                    ticks: { color: textMuted, font: { size: 9 }, callback: v => '$' + v.toFixed(0) },
                    grid: { color: border + '30' },
                    // Zero baseline
                    afterDataLimits: scale => { scale.min = Math.min(scale.min, 0); },
                },
            },
        },
    });
}

// ── Position Risk Heatmap ────────────────────────────────────
function _renderRiskHeatmap(positions) {
    const el = document.getElementById('risk-heatmap');
    if (!el) return;

    if (!positions || !positions.length) {
        el.innerHTML = '<div style="padding:20px;text-align:center;color:var(--text-muted);font-size:12px">No open positions to assess</div>';
        return;
    }

    const totalEquity = positions.reduce((s, p) => s + Math.abs(p.market_value || p.qty * (p.current_price || p.avg_entry_price || 1)), 0) || 1;

    el.innerHTML = positions.map(p => {
        const mv = Math.abs(p.market_value || p.qty * (p.current_price || p.avg_entry_price || 1));
        const allocation = mv / totalEquity;
        const unrealizedPct = p.avg_entry_price ? ((p.current_price || p.avg_entry_price) - p.avg_entry_price) / p.avg_entry_price : 0;
        const pnl = p.unrealized_pl || 0;

        // Risk score: high allocation + negative P&L = high risk
        const riskScore = allocation * (1 + Math.max(0, -unrealizedPct * 5));
        const riskPct = Math.min(100, Math.round(riskScore * 100));

        let riskColor, riskLabel;
        if (riskPct > 70) { riskColor = 'var(--accent-red)'; riskLabel = 'HIGH'; }
        else if (riskPct > 40) { riskColor = 'var(--accent-orange)'; riskLabel = 'MED'; }
        else { riskColor = 'var(--accent-green)'; riskLabel = 'LOW'; }

        const pnlColor = pnl >= 0 ? 'var(--accent-green)' : 'var(--accent-red)';
        const allocPct = (allocation * 100).toFixed(1);

        return `<div style="padding:8px 10px;border-bottom:1px solid var(--border);display:grid;grid-template-columns:80px 1fr 60px 60px 50px;align-items:center;gap:8px;font-size:12px">
            <span style="font-weight:700">${escHtml(p.symbol)}</span>
            <div>
                <div style="background:var(--bg-secondary);border-radius:3px;height:6px;overflow:hidden">
                    <div style="width:${allocPct}%;height:100%;background:${riskColor};transition:width 0.6s;border-radius:3px"></div>
                </div>
                <span style="font-size:10px;color:var(--text-muted)">${allocPct}% alloc</span>
            </div>
            <span style="color:${pnlColor};font-weight:600;text-align:right">${pnl >= 0 ? '+' : ''}$${pnl.toFixed(0)}</span>
            <span style="color:${riskColor};font-weight:700;text-align:center;font-size:11px">${riskLabel}</span>
            <span style="color:var(--text-muted);font-size:10px;text-align:right">${riskPct}%</span>
        </div>`;
    }).join('');
}

// ── Trading Panel ────────────────────────────────────────────
async function loadTrading() {
    const [portfolio, signals, trades] = await Promise.all([
        api('/api/hedge-fund/portfolio'),
        api('/api/hedge-fund/signals?limit=10'),
        api('/api/hedge-fund/trades?limit=20'),
    ]);

    if (portfolio && !portfolio.error) {
        _setText('trade-equity', '$' + (portfolio.equity || 0).toLocaleString(undefined, {maximumFractionDigits: 0}));
        _setText('trade-daily-pl', '$' + (portfolio.daily_pl || 0).toLocaleString(undefined, {maximumFractionDigits: 0}));
        _setText('trade-positions', portfolio.positions?.length || 0);

        // Positions list with close buttons
        const pl = document.getElementById('positions-list');
        if (pl && portfolio.positions?.length) {
            pl.innerHTML = portfolio.positions.map(p => `
                <div class="list-item" style="padding:8px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center">
                    <div>
                        <span style="font-weight:600">${escHtml(p.symbol)}</span>
                        <span style="font-size:11px;color:var(--text-muted)">${p.qty} shares @ $${(p.avg_entry_price || p.entry_price || 0).toFixed(2)}</span>
                    </div>
                    <div style="display:flex;align-items:center;gap:8px">
                        <span style="color:${p.unrealized_pl >= 0 ? 'var(--accent-green)' : 'var(--accent-red)'}">$${(p.unrealized_pl || 0).toFixed(2)}</span>
                        <button class="btn-sm" onclick="closePosition('${escHtml(p.trade_id || p.id || '')}', ${p.current_price || 0})" title="Close position">✕</button>
                    </div>
                </div>
            `).join('');
        } else if (pl) {
            pl.innerHTML = '<div class="empty-state" style="padding:16px">No open positions</div>';
        }
    }

    if (signals?.signals) {
        _setText('trade-signals', signals.signals.length);
        const sl = document.getElementById('signals-list');
        if (sl && signals.signals.length) {
            sl.innerHTML = signals.signals.slice(0, 8).map(s => `
                <div class="list-item" style="padding:8px;border-bottom:1px solid var(--border)">
                    <div style="display:flex;justify-content:space-between;align-items:center">
                        <div>
                            <span style="font-weight:600">${escHtml(s.symbol || '?')}</span>
                            <span style="font-size:11px;padding:2px 6px;border-radius:3px;background:${s.direction === 'buy' || s.direction === 'long' ? 'var(--accent-green)' : 'var(--accent-red)'}20;color:${s.direction === 'buy' || s.direction === 'long' ? 'var(--accent-green)' : 'var(--accent-red)'}">${escHtml(s.direction || '?')}</span>
                        </div>
                        <div style="display:flex;gap:6px;align-items:center">
                            <span style="font-size:11px;color:var(--text-muted)">${((s.confidence || 0) * 100).toFixed(0)}%</span>
                            <button class="btn-sm" onclick="executeSignal('${escHtml(s.id || '')}')" title="Execute signal">▶</button>
                        </div>
                    </div>
                    <div style="font-size:11px;color:var(--text-muted)">${escHtml(s.source || '')} · ${formatTime(s.created_at)}</div>
                </div>
            `).join('');
        } else if (sl) {
            sl.innerHTML = '<div class="empty-state" style="padding:16px">No active signals</div>';
        }
    }

    // Trading autonomy status
    loadTradingAutonomy();
    loadMarketAnalysis();
    loadTradingIntelFeed();

    // Portfolio equity chart (existing)
    if (typeof Chart !== 'undefined' && portfolio?.snapshots?.length) {
        _renderChart('chart-portfolio', {
            type: 'line',
            data: {
                labels: portfolio.snapshots.map(s => s.date?.slice(5) || ''),
                datasets: [{
                    data: portfolio.snapshots.map(s => s.equity || 0),
                    borderColor: 'var(--accent-green)',
                    backgroundColor: 'rgba(76, 175, 80, 0.1)',
                    fill: true, tension: 0.3, pointRadius: 1,
                }],
            },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { display: false }, y: { ticks: { color: 'var(--text-muted)', font: { size: 10 } } } } },
        });
    }

    // NEW: Portfolio Allocation Pie
    const positions = portfolio?.positions || [];
    const equity = portfolio?.equity || 0;
    _renderPortfolioAllocation(positions, equity);

    // NEW: P&L Timeline (from trade history)
    const tradeList = trades?.trades || (Array.isArray(trades) ? trades : []);
    _renderPnLTimeline(tradeList);

    // NEW: Position Risk Heatmap
    _renderRiskHeatmap(positions);
}

async function runTradeCycle() {
    const btn = document.querySelector('[onclick="runTradeCycle()"]');
    if (btn) { btn.disabled = true; btn.textContent = 'Running...'; }
    try {
        await api('/api/hedge-fund/cycle', { method: 'POST' });
        loadTrading();
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = 'Run Trade Cycle'; }
    }
}

async function scanMarkets() {
    const btn = document.querySelector('[onclick="scanMarkets()"]');
    if (btn) { btn.disabled = true; btn.textContent = 'Scanning...'; }
    try {
        await api('/api/hedge-fund/scan', { method: 'POST' });
        loadTrading();
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = 'Scan Markets'; }
    }
}

function showManualSignalModal() {
    showModal({
        title: 'Submit Manual Signal',
        fields: [
            { key: 'symbol', label: 'Symbol', type: 'text', placeholder: 'e.g. AAPL, TSLA, SPY', required: true },
            { key: 'direction', label: 'Direction', type: 'select', options: ['long', 'short'], value: 'long' },
            { key: 'confidence', label: 'Confidence', type: 'range', min: 0, max: 100, step: 5, value: 70 },
            { key: 'timeframe', label: 'Timeframe', type: 'select', options: ['intraday', 'swing', 'position'], value: 'swing' },
            { key: 'reasoning', label: 'Reasoning', type: 'textarea', placeholder: 'Why this trade?' },
        ],
        submitLabel: 'Submit Signal',
        onSubmit: async (vals) => {
            await api('/api/hedge-fund/signals', {
                method: 'POST',
                body: {
                    symbol: vals.symbol.toUpperCase(),
                    direction: vals.direction,
                    confidence: vals.confidence / 100,
                    timeframe: vals.timeframe,
                    reasoning: vals.reasoning || '',
                },
            });
            closeModal();
            loadTrading();
        },
    });
}

async function executeSignal(signalId) {
    if (!signalId) return;
    const btn = event?.target;
    if (btn) { btn.disabled = true; btn.textContent = '…'; }
    try {
        await api(`/api/hedge-fund/execute?signal_id=${encodeURIComponent(signalId)}`, { method: 'POST' });
        if (btn) { btn.textContent = '✓'; }
        setTimeout(() => loadTrading(), 1000);
    } catch (e) {
        if (btn) { btn.textContent = '✕'; btn.disabled = false; }
    }
}

async function closePosition(tradeId, currentPrice) {
    if (!tradeId) return;
    showConfirmModal({
        title: 'Close Position',
        message: `Close this position at current price $${currentPrice.toFixed(2)}?`,
        danger: true,
        confirmLabel: 'Close Position',
        onConfirm: async () => {
            await api('/api/hedge-fund/trades/close', {
                method: 'POST',
                body: { trade_id: tradeId, exit_price: currentPrice },
            });
            closeModal();
            loadTrading();
        },
    });
}

async function showRiskLimits() {
    const data = await api('/api/hedge-fund/risk-limits');
    const infoEl = document.getElementById('trading-extra-info');
    if (infoEl && data && !data.error) {
        infoEl.innerHTML = `<div class="card" style="margin-bottom:12px">
            <div class="card-title" style="display:flex;justify-content:space-between"><span>Risk Limits</span><button class="btn-sm" onclick="document.getElementById('trading-extra-info').innerHTML=''">✕</button></div>
            <div class="grid-3" style="margin-top:8px">
                ${Object.entries(data).map(([k, v]) => `<div style="padding:8px;background:var(--bg-elevated);border-radius:6px">
                    <div style="font-size:14px;font-weight:700;color:var(--accent)">${typeof v === 'number' ? (v < 1 ? (v * 100).toFixed(0) + '%' : v) : v}</div>
                    <div style="font-size:11px;color:var(--text-muted)">${escHtml(k.replace(/_/g, ' '))}</div>
                </div>`).join('')}
            </div>
        </div>`;
    }
}

async function showPerformance() {
    const data = await api('/api/hedge-fund/performance');
    const infoEl = document.getElementById('trading-extra-info');
    if (infoEl && data && !data.error) {
        infoEl.innerHTML = `<div class="card" style="margin-bottom:12px">
            <div class="card-title" style="display:flex;justify-content:space-between"><span>Performance Stats</span><button class="btn-sm" onclick="document.getElementById('trading-extra-info').innerHTML=''">✕</button></div>
            <div class="grid-3" style="margin-top:8px">
                ${Object.entries(data).map(([k, v]) => `<div style="padding:8px;background:var(--bg-elevated);border-radius:6px">
                    <div style="font-size:14px;font-weight:700;color:var(--accent-cyan)">${typeof v === 'number' ? (Math.abs(v) < 1 && v !== 0 ? (v * 100).toFixed(1) + '%' : '$' + v.toLocaleString(undefined, {maximumFractionDigits: 2})) : escHtml(String(v))}</div>
                    <div style="font-size:11px;color:var(--text-muted)">${escHtml(k.replace(/_/g, ' '))}</div>
                </div>`).join('')}
            </div>
        </div>`;
    }
}

// ── Market Analysis ─────────────────────────────────────────
async function loadMarketAnalysis() {
    const el = document.getElementById('market-analysis-content');
    if (!el) return;
    const data = await api('/api/agi/status').catch(() => null);
    if (!data?.data) { el.innerHTML = '<div style="color:var(--text-muted)">Market analysis unavailable</div>'; return; }

    const agi = data.data;
    const tc = agi.trading_autonomy || {};
    const se = agi.skill_executor || {};
    const or = agi.outcome_registry || {};

    el.innerHTML = `
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px">
            <div class="stat-card"><div class="stat-value" style="color:var(--accent)">${or.total_outcomes || 0}</div><div class="stat-label">Trade Outcomes</div></div>
            <div class="stat-card"><div class="stat-value" style="color:var(--accent-green)">${((or.avg_quality || 0) * 100).toFixed(0)}%</div><div class="stat-label">Avg Quality</div></div>
            <div class="stat-card"><div class="stat-value" style="color:var(--accent-blue)">${tc.total_decisions || 0}</div><div class="stat-label">Auto Decisions</div></div>
        </div>
        <div style="margin-top:12px;padding:10px;background:var(--bg-hover);border-radius:6px">
            <div style="font-weight:600;margin-bottom:6px">Intelligence Pipeline</div>
            <div style="display:flex;align-items:center;gap:4px;font-size:11px;color:var(--text-secondary)">
                <span style="padding:2px 6px;background:var(--accent-green);color:#000;border-radius:3px">Market Data</span>
                →
                <span style="padding:2px 6px;background:var(--accent-blue);color:#fff;border-radius:3px">Consensus</span>
                →
                <span style="padding:2px 6px;background:var(--accent-purple);color:#fff;border-radius:3px">12 Investors</span>
                →
                <span style="padding:2px 6px;background:var(--accent);color:#000;border-radius:3px">Auto/Manual</span>
            </div>
        </div>
    `;
}

// ── Trading Intelligence Feed ───────────────────────────────
async function loadTradingIntelFeed() {
    const el = document.getElementById('trading-intel-content');
    if (!el) return;
    const [outcomes, perpetual] = await Promise.all([
        api('/api/agi/outcomes?limit=10').catch(() => ({data:[]})),
        api('/api/perpetual/status').catch(() => ({data:{}})),
    ]);

    const outcomeList = outcomes?.data || [];
    const tradeOutcomes = (Array.isArray(outcomeList) ? outcomeList : []).filter(
        o => o.action_type === 'proactive' && (o.intent || '').toLowerCase().includes('trade')
    );

    const p = perpetual?.data?.perpetual || {};

    el.innerHTML = `
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:12px">
            <div class="stat-card"><div class="stat-value" style="color:var(--accent)">${p.trades_evaluated || 0}</div><div class="stat-label">Trades Evaluated</div></div>
            <div class="stat-card"><div class="stat-value" style="color:var(--accent-green)">${p.analysis_insights || 0}</div><div class="stat-label">Analysis Done</div></div>
            <div class="stat-card"><div class="stat-value" style="color:var(--accent-purple)">${p.research_findings || 0}</div><div class="stat-label">Research Findings</div></div>
        </div>
        <div style="font-weight:600;margin-bottom:8px;font-size:13px">Intelligence Pipeline</div>
        <div style="display:flex;flex-wrap:wrap;gap:4px;font-size:11px;margin-bottom:12px">
            <span style="padding:3px 8px;background:var(--accent-cyan);color:#000;border-radius:4px">Market Data</span>
            <span style="padding:3px 8px;background:var(--accent-blue);color:#fff;border-radius:4px">Bull/Bear Debate</span>
            <span style="padding:3px 8px;background:var(--accent-purple);color:#fff;border-radius:4px">12 Investors</span>
            <span style="padding:3px 8px;background:var(--accent-green);color:#000;border-radius:4px">Auto/Manual</span>
            <span style="padding:3px 8px;background:var(--accent-gold);color:#000;border-radius:4px">Execute</span>
        </div>
        ${tradeOutcomes.length ? `<div style="font-weight:600;margin-bottom:6px;font-size:12px">Recent Evaluations</div>` +
            tradeOutcomes.slice(0, 5).map(o => `
                <div style="padding:6px 0;border-bottom:1px solid var(--border);font-size:11px">
                    <span style="color:${o.quality_score >= 0.7 ? 'var(--accent-green)' : 'var(--accent)'}">${(o.quality_score * 100).toFixed(0)}%</span>
                    ${escHtml((o.intent || '').substring(0, 80))}
                </div>`).join('') : '<div style="color:var(--text-muted)">Trading intelligence warming up...</div>'}`;
}

// ── Trading Autonomy Status ─────────────────────────────────
async function loadTradingAutonomy() {
    const el = document.getElementById('trading-autonomy-status');
    if (!el) return;
    try {
        const raw = await api('/api/agi/trading-autonomy');
        const data = raw?.data ?? raw;
        if (!data || data.error) {
            el.innerHTML = '<div style="color:var(--text-muted);font-size:12px;padding:8px">Trading autonomy unavailable</div>';
            return;
        }

        const level = data.autonomy_level || data.level || 'unknown';
        const enabled = data.enabled !== false;
        const maxRisk = data.max_risk_pct || data.max_position_risk || 0;
        const dailyLimit = data.daily_trade_limit || data.max_daily_trades || 0;
        const totalTrades = data.total_autonomous_trades || data.trades_today || 0;
        const approval = data.requires_approval !== false;

        const levelColors = {
            manual: 'var(--text-muted)', assisted: 'var(--accent-blue)',
            semi_auto: 'var(--accent-gold)', autonomous: 'var(--accent-green)',
            full_auto: 'var(--accent-cyan)', unknown: 'var(--text-muted)',
        };
        const levelColor = levelColors[level] || 'var(--accent)';

        el.innerHTML = `
            <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
                <div style="display:flex;align-items:center;gap:6px">
                    <span style="width:8px;height:8px;border-radius:50%;background:${enabled ? 'var(--accent-green)' : 'var(--accent-red)'}"></span>
                    <span style="font-size:12px;font-weight:600;color:${levelColor};text-transform:uppercase">${escHtml(level.replace(/_/g, ' '))}</span>
                </div>
                <span style="font-size:11px;color:var(--text-muted)">Risk: ${typeof maxRisk === 'number' && maxRisk < 1 ? (maxRisk * 100).toFixed(0) + '%' : maxRisk}</span>
                <span style="font-size:11px;color:var(--text-muted)">Limit: ${dailyLimit}/day</span>
                <span style="font-size:11px;color:var(--text-muted)">Traded: ${totalTrades}</span>
                ${approval ? '<span style="font-size:10px;background:var(--accent-orange)22;color:var(--accent-orange);padding:2px 6px;border-radius:8px">Approval req</span>' : ''}
            </div>`;
    } catch {
        el.innerHTML = '<div style="color:var(--text-muted);font-size:12px;padding:8px">Trading autonomy unavailable</div>';
    }
}

// ── Strategies Panel ────────────────────────────────────────
function _sharpeColor(sharpe) {
    if (sharpe >= 1.5) return 'var(--accent-green)';
    if (sharpe >= 1.0) return 'var(--accent-gold)';
    return 'var(--accent-red)';
}

async function loadStrategies() {
    const [stats, promoted, recent] = await Promise.all([
        api('/api/strategies/stats'),
        api('/api/strategies/promoted?limit=20'),
        api('/api/strategies/recent?limit=30'),
    ]);

    const total = stats.total || 0;
    const prom = stats.promoted || 0;
    const fail = stats.failed || 0;
    const rate = total > 0 ? (prom / total * 100).toFixed(1) : '0';
    document.getElementById('strat-total').textContent = total;
    document.getElementById('strat-promoted').textContent = prom;
    document.getElementById('strat-failed').textContent = fail;
    document.getElementById('strat-rate').textContent = total > 0 ? rate + '%' : '-';

    // Summary insight card
    const summaryEl = document.getElementById('strat-summary');
    const promStrats = promoted.strategies || [];
    if (summaryEl) {
        if (promStrats.length) {
            const best = promStrats.reduce((a, b) => (b.sharpe_ratio || 0) > (a.sharpe_ratio || 0) ? b : a, promStrats[0]);
            const bestSharpe = (best.sharpe_ratio || 0).toFixed(2);
            summaryEl.innerHTML = `<div class="card" style="margin-bottom:16px;background:linear-gradient(135deg, var(--bg-card), var(--accent)08);border-left:3px solid var(--accent-green)">
                <div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap">
                    <div style="flex:1;min-width:200px">
                        <div style="font-size:13px;font-weight:600;color:var(--text-primary)">${total} strategies tested, <span style="color:var(--accent-green)">${prom} promoted</span> (${rate}% rate)</div>
                        <div style="font-size:12px;color:var(--text-secondary);margin-top:4px">Best performer: <strong style="color:var(--accent)">${escHtml(best.strategy_name || '?')}</strong> on ${escHtml(best.symbol || '?')} with <span style="color:${_sharpeColor(best.sharpe_ratio || 0)}">${bestSharpe} Sharpe</span></div>
                    </div>
                    <div style="display:flex;gap:12px">
                        <div style="text-align:center"><div style="font-size:22px;font-weight:800;color:var(--accent-green)">${prom}</div><div style="font-size:10px;color:var(--text-muted)">LIVE-READY</div></div>
                        <div style="text-align:center"><div style="font-size:22px;font-weight:800;color:${_sharpeColor(best.sharpe_ratio || 0)}">${bestSharpe}</div><div style="font-size:10px;color:var(--text-muted)">BEST SHARPE</div></div>
                    </div>
                </div>
            </div>`;
        } else {
            summaryEl.innerHTML = `<div class="card" style="margin-bottom:16px;border-left:3px solid var(--accent-orange)">
                <div style="font-size:13px;color:var(--text-secondary)">No promoted strategies yet. Run a full scan to discover winning strategies and backtest them.</div>
            </div>`;
        }
    }

    const promEl = document.getElementById('strat-promoted-list');
    if (promStrats.length > 0) {
        promEl.innerHTML = '<div style="font-weight:700;font-size:13px;color:var(--accent-green);margin-bottom:8px">Promoted (Live-Ready)</div>' +
            promStrats.map(s => {
                const sharpe = s.sharpe_ratio || 0;
                const ret = s.total_return_pct || 0;
                return `<div class="card" style="margin-bottom:8px;border-left:3px solid var(--accent-green);padding:12px;cursor:pointer" onclick="this.querySelector('.strat-detail').style.display=this.querySelector('.strat-detail').style.display==='none'?'block':'none'">
                    <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
                        <span style="font-weight:700;font-size:13px">${escHtml(s.strategy_name)}</span>
                        <span style="font-size:11px;color:var(--text-muted)">${escHtml(s.symbol)}</span>
                        <span style="background:${_sharpeColor(sharpe)}22;color:${_sharpeColor(sharpe)};padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600">Sharpe ${sharpe.toFixed(2)}</span>
                        <span style="color:${ret >= 0 ? 'var(--accent-green)' : 'var(--accent-red)'};font-size:12px;font-weight:600">${ret >= 0 ? '+' : ''}${ret.toFixed(1)}%</span>
                        <span style="margin-left:auto;font-size:11px;color:var(--text-muted)">Win ${(s.win_rate||0).toFixed(0)}% · DD ${(s.max_drawdown_pct||0).toFixed(1)}%</span>
                    </div>
                    <div class="strat-detail" style="display:none;margin-top:10px;padding-top:8px;border-top:1px solid var(--border)">
                        <div class="grid-4" style="gap:8px;margin-bottom:8px">
                            <div style="text-align:center"><div style="font-size:14px;font-weight:700;color:${_sharpeColor(sharpe)}">${sharpe.toFixed(2)}</div><div style="font-size:10px;color:var(--text-muted)">Sharpe</div></div>
                            <div style="text-align:center"><div style="font-size:14px;font-weight:700;color:${ret >= 0 ? 'var(--accent-green)' : 'var(--accent-red)'}">${ret.toFixed(1)}%</div><div style="font-size:10px;color:var(--text-muted)">Return</div></div>
                            <div style="text-align:center"><div style="font-size:14px;font-weight:700">${(s.win_rate||0).toFixed(0)}%</div><div style="font-size:10px;color:var(--text-muted)">Win Rate</div></div>
                            <div style="text-align:center"><div style="font-size:14px;font-weight:700;color:var(--accent-red)">${(s.max_drawdown_pct||0).toFixed(1)}%</div><div style="font-size:10px;color:var(--text-muted)">Max DD</div></div>
                        </div>
                        ${s.monte_carlo_p5 ? `<div style="font-size:11px;color:var(--text-muted)">Monte Carlo P5: $${(s.monte_carlo_p5).toLocaleString()}</div>` : ''}
                    </div>
                </div>`;
            }).join('');
    } else {
        promEl.innerHTML = '<div class="empty-state">No promoted strategies yet. Run a scan to discover winners.</div>';
    }

    const recEl = document.getElementById('strat-recent-list');
    const recStrats = recent.validations || [];
    if (recStrats.length > 0) {
        recEl.innerHTML = '<div style="font-weight:700;font-size:13px;margin-bottom:8px">Recent Validations</div>' +
            recStrats.map(s => {
                const passed = s.status === 'passed';
                const failed = s.status === 'failed';
                const borderColor = passed ? 'var(--accent-green)' : failed ? 'var(--accent-red)' : 'var(--border)';
                const statusLabel = passed ? '<span style="color:var(--accent-green);font-weight:600">PASS</span>'
                    : failed ? '<span style="color:var(--accent-red);font-weight:600">FAIL</span>'
                    : '<span style="color:var(--text-muted)">ERR</span>';
                const sharpe = s.sharpe_ratio || 0;
                return `<div style="padding:8px 12px;border-left:3px solid ${borderColor};background:var(--bg-card);border-radius:0 6px 6px 0;margin-bottom:6px">
                    <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
                        ${statusLabel}
                        <span style="font-weight:600;font-size:12px">${escHtml(s.strategy_name)}</span>
                        <span style="font-size:11px;color:var(--text-muted)">${escHtml(s.symbol)}</span>
                        <span style="color:${_sharpeColor(sharpe)};font-size:11px;font-weight:600">Sharpe ${sharpe.toFixed(2)}</span>
                        <span style="color:${(s.total_return_pct||0) >= 0 ? 'var(--accent-green)' : 'var(--accent-red)'};font-size:11px">${(s.total_return_pct||0).toFixed(1)}%</span>
                        ${s.lesson ? `<span style="margin-left:auto;font-size:11px;color:var(--text-muted);max-width:250px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${escHtml(s.lesson)}">${escHtml(s.lesson)}</span>` : ''}
                    </div>
                </div>`;
            }).join('');
    } else {
        recEl.innerHTML = '<div class="empty-state">No validations yet.</div>';
    }
}

async function runStrategyValidation() {
    const btn = document.getElementById('btn-run-strat');
    btn.disabled = true;
    btn.textContent = 'Scanning...';
    try {
        const result = await api('/api/strategies/validate');
        btn.textContent = `Done: ${result.promoted_count} promoted / ${result.total_tested} tested`;
        setTimeout(() => {
            btn.textContent = 'Run Full Scan';
            btn.disabled = false;
        }, 5000);
        loadStrategies();
    } catch (e) {
        btn.textContent = 'Error — retry';
        btn.disabled = false;
    }
}

// ── Backtesting Panel ────────────────────────────────────────
async function loadBacktesting() {
    const results = await api('/api/backtesting/results?limit=30');
    const resData = results?.data || results?.results || (Array.isArray(results) ? results : []);

    const listEl = document.getElementById('bt-results-list');
    if (resData.length) {
        listEl.innerHTML = '<div class="table-wrap"><table><thead><tr>' +
            '<th>Strategy</th><th>Symbol</th><th>Sharpe</th><th>Return</th><th>Win%</th><th>Max DD</th><th>Status</th><th>Action</th>' +
            '</tr></thead><tbody>' +
            resData.map(r => {
                const statusIcon = r.status === 'passed' ? '<span style="color:var(--accent-green)">PASS</span>'
                    : r.status === 'failed' ? '<span style="color:var(--accent-red)">FAIL</span>'
                    : '<span style="color:var(--text-muted)">' + escHtml(r.status || '\u2014') + '</span>';
                return `<tr>
                    <td><strong>${escHtml(r.strategy_name || '\u2014')}</strong></td>
                    <td>${escHtml(r.symbol || '\u2014')}</td>
                    <td>${(r.sharpe_ratio || 0).toFixed(2)}</td>
                    <td>${(r.total_return_pct || 0).toFixed(1)}%</td>
                    <td>${(r.win_rate || 0).toFixed(0)}%</td>
                    <td>${(r.max_drawdown_pct || 0).toFixed(1)}%</td>
                    <td>${statusIcon}</td>
                    <td style="display:flex;gap:4px">
                        <button class="btn-sm" onclick="showBacktestDetail('${escHtml(r.id || '')}')">View</button>
                        <button class="btn-sm" onclick="runMonteCarlo('${escHtml(r.id || '')}')">MC</button>
                    </td>
                </tr>`;
            }).join('') + '</tbody></table></div>';
    } else {
        listEl.innerHTML = '<div class="empty-state">No backtest results yet. Run a backtest to see results.</div>';
    }
}

async function runBacktest() {
    const strategy = document.getElementById('bt-strategy')?.value?.trim();
    const symbol = document.getElementById('bt-symbol')?.value?.trim() || 'SPY';
    const start = document.getElementById('bt-start')?.value;
    const end = document.getElementById('bt-end')?.value;
    if (!strategy) { alert('Enter a strategy name'); return; }
    const btn = document.getElementById('btn-bt-run');
    btn.disabled = true; btn.textContent = 'Running...';
    try {
        const result = await api('/api/backtesting/run', { method: 'POST',
            body: JSON.stringify({ strategy_name: strategy, symbol, start_date: start, end_date: end }) });
        btn.textContent = `Done: Sharpe ${(result?.sharpe_ratio || 0).toFixed(2)}`;
        setTimeout(() => { btn.disabled = false; btn.textContent = 'Run Backtest'; }, 4000);
        loadBacktesting();
    } catch (e) {
        btn.disabled = false; btn.textContent = 'Error — retry';
    }
}

async function runMonteCarlo(resultId) {
    if (!resultId) return;
    const btn = event?.target;
    if (btn) { btn.disabled = true; btn.textContent = '...'; }
    try {
        const data = await api(`/api/backtesting/monte-carlo/${resultId}`, { method: 'POST',
            body: JSON.stringify({ simulations: 1000 }) });
        const p5 = data?.percentile_5 || data?.p5 || 0;
        const p50 = data?.percentile_50 || data?.p50 || 0;
        const p95 = data?.percentile_95 || data?.p95 || 0;
        showDetailModal({
            title: 'Monte Carlo Simulation (1000 runs)',
            content: `
                <div class="grid-3" style="margin:16px 0">
                    <div class="stat-card"><div class="stat-value" style="color:var(--accent-red)">$${p5.toLocaleString()}</div><div class="stat-label">P5 (Worst)</div></div>
                    <div class="stat-card"><div class="stat-value" style="color:var(--accent-gold)">$${p50.toLocaleString()}</div><div class="stat-label">P50 (Median)</div></div>
                    <div class="stat-card"><div class="stat-value" style="color:var(--accent-green)">$${p95.toLocaleString()}</div><div class="stat-label">P95 (Best)</div></div>
                </div>
                <div style="font-size:12px;color:var(--text-muted);text-align:center">
                    Based on 1000 randomized simulations of trade sequences
                </div>`,
        });
    } catch (e) {
        console.error('Monte Carlo error:', e);
    }
    if (btn) { btn.disabled = false; btn.textContent = 'Monte Carlo'; }
}

async function showBacktestDetail(resultId) {
    if (!resultId) return;
    try {
        const data = await api(`/api/backtesting/results/${resultId}`);
        const r = data?.data || data || {};
        const trades = r.trades || [];
        const statusColor = r.status === 'passed' ? 'var(--accent-green)' : r.status === 'failed' ? 'var(--accent-red)' : 'var(--text-muted)';

        // Build equity curve visualization
        const equity = r.equity_curve || [];
        let equityCurve = '';
        if (equity.length > 1) {
            const maxVal = Math.max(...equity.map(e => e.value || e));
            const minVal = Math.min(...equity.map(e => e.value || e));
            const range = maxVal - minVal || 1;
            equityCurve = `<div style="margin-bottom:16px">
                <div style="font-weight:600;font-size:12px;margin-bottom:6px">Equity Curve</div>
                <div style="display:flex;align-items:flex-end;gap:1px;height:80px;background:var(--bg-elevated);border-radius:6px;padding:8px;overflow:hidden">
                    ${equity.slice(-60).map(e => {
                        const v = typeof e === 'number' ? e : (e.value || 0);
                        const h = Math.max(((v - minVal) / range) * 70, 2);
                        const c = v >= equity[0] ? 'var(--accent-green)' : 'var(--accent-red)';
                        return `<div style="flex:1;height:${h}px;background:${c};border-radius:1px;min-width:1px"></div>`;
                    }).join('')}
                </div>
            </div>`;
        }

        // Build trade list
        const tradeList = trades.length ? `<div style="margin-bottom:12px">
            <div style="font-weight:600;font-size:12px;margin-bottom:6px">Trades (${trades.length})</div>
            <div class="table-wrap"><table><thead><tr>
                <th>Symbol</th><th>Dir</th><th>Entry</th><th>Exit</th><th>P&L</th>
            </tr></thead><tbody>
            ${trades.slice(0, 20).map(t => {
                const pnl = t.pnl || t.profit || 0;
                const pnlColor = pnl >= 0 ? 'var(--accent-green)' : 'var(--accent-red)';
                return `<tr>
                    <td>${escHtml(t.symbol || '')}</td>
                    <td>${escHtml(t.direction || t.side || '')}</td>
                    <td>$${(t.entry_price || 0).toFixed(2)}</td>
                    <td>$${(t.exit_price || 0).toFixed(2)}</td>
                    <td style="color:${pnlColor}">${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)}</td>
                </tr>`;
            }).join('')}
            </tbody></table></div>
            ${trades.length > 20 ? `<div style="font-size:11px;color:var(--text-muted);text-align:center;margin-top:4px">Showing 20 of ${trades.length} trades</div>` : ''}
        </div>` : '';

        showDetailModal({
            title: `Backtest: ${r.strategy_name || resultId}`,
            content: `
                <div class="grid-4" style="margin-bottom:16px">
                    <div class="stat-card"><div class="stat-value" style="font-size:16px">${(r.sharpe_ratio || 0).toFixed(2)}</div><div class="stat-label">Sharpe</div></div>
                    <div class="stat-card"><div class="stat-value" style="font-size:16px;color:${(r.total_return_pct || 0) >= 0 ? 'var(--accent-green)' : 'var(--accent-red)'}">${(r.total_return_pct || 0).toFixed(1)}%</div><div class="stat-label">Return</div></div>
                    <div class="stat-card"><div class="stat-value" style="font-size:16px">${(r.win_rate || 0).toFixed(0)}%</div><div class="stat-label">Win Rate</div></div>
                    <div class="stat-card"><div class="stat-value" style="font-size:16px;color:var(--accent-red)">${(r.max_drawdown_pct || 0).toFixed(1)}%</div><div class="stat-label">Max DD</div></div>
                </div>
                <div style="display:flex;gap:12px;margin-bottom:16px;font-size:12px;color:var(--text-secondary)">
                    <span>Symbol: <strong>${escHtml(r.symbol || '')}</strong></span>
                    <span>Status: <strong style="color:${statusColor}">${escHtml(r.status || '')}</strong></span>
                    <span>Trades: <strong>${r.total_trades || trades.length || 0}</strong></span>
                </div>
                ${equityCurve}
                ${tradeList}
                <div style="text-align:center;margin-top:8px">
                    <button class="btn-secondary" onclick="closeModal();runMonteCarlo('${escHtml(resultId)}')">Run Monte Carlo</button>
                </div>`,
        });
    } catch (e) {
        console.error('Backtest detail error:', e);
    }
}

// ── Polymarket Panel ─────────────────────────────────────────
async function loadPolymarket() {
    const [stats, positions] = await Promise.all([
        api('/api/polymarket/stats'),
        api('/api/polymarket/positions'),
    ]);

    const s = stats?.data || stats || {};
    document.getElementById('poly-volume').textContent = s.total_volume ? '$' + (s.total_volume).toLocaleString() : '\u2014';
    document.getElementById('poly-pnl').textContent = s.total_pnl !== undefined ? '$' + s.total_pnl.toFixed(2) : '\u2014';
    document.getElementById('poly-positions').textContent = s.open_positions || 0;
    document.getElementById('poly-trades').textContent = s.total_trades || 0;

    const posEl = document.getElementById('poly-positions-list');
    const posData = Array.isArray(positions) ? positions : (positions?.data || positions?.positions || []);
    if (posData.length) {
        posEl.innerHTML = '<div class="table-wrap"><table><thead><tr>' +
            '<th>Market</th><th>Direction</th><th>Size</th><th>Entry</th><th>Current</th><th>P&L</th>' +
            '</tr></thead><tbody>' +
            posData.map(p => {
                const pnl = p.pnl || p.unrealized_pnl || 0;
                const pnlColor = pnl >= 0 ? 'var(--accent-green)' : 'var(--accent-red)';
                return `<tr>
                    <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis">${escHtml((p.market || p.condition_id || '\u2014').slice(0, 60))}</td>
                    <td>${escHtml(p.direction || p.side || '\u2014')}</td>
                    <td>$${(p.size || 0).toFixed(2)}</td>
                    <td>${(p.entry_price || 0).toFixed(3)}</td>
                    <td>${(p.current_price || 0).toFixed(3)}</td>
                    <td style="color:${pnlColor}">$${pnl.toFixed(2)}</td>
                </tr>`;
            }).join('') + '</tbody></table></div>';
    } else {
        posEl.innerHTML = '<div class="empty-state">No open positions</div>';
    }
}

async function runPolymarketCycle() {
    const btn = document.getElementById('btn-poly-cycle');
    btn.disabled = true; btn.textContent = 'Running...';
    try {
        const result = await api('/api/polymarket/cycle', { method: 'POST' });
        btn.textContent = result?.message || 'Cycle complete';
        setTimeout(() => { btn.disabled = false; btn.textContent = 'Run Cycle'; }, 4000);
        loadPolymarket();
    } catch (e) {
        btn.disabled = false; btn.textContent = 'Error — retry';
    }
}

async function scanPolymarkets() {
    const btn = document.getElementById('btn-poly-scan');
    btn.disabled = true; btn.textContent = 'Scanning...';
    try {
        const result = await api('/api/polymarket/scan', { method: 'POST' });
        btn.textContent = `Found ${result?.markets_found || result?.count || 0} markets`;
        setTimeout(() => { btn.disabled = false; btn.textContent = 'Scan Markets'; }, 3000);
    } catch (e) {
        btn.disabled = false; btn.textContent = 'Error — retry';
    }
}

// ── Money / Strategy Council ────────────────────────────────
async function loadMoney() {
    const [stats, opps] = await Promise.all([api('/api/money/stats'), api('/api/money/opportunities?limit=10')]);
    const ms = document.getElementById('money-sessions');
    if (ms) ms.textContent = stats.total_sessions || 0;
    const mo = document.getElementById('money-opps');
    if (mo) mo.textContent = stats.total_opportunities || 0;
    const mr = document.getElementById('money-revenue');
    if (mr) mr.textContent = '$' + (stats.total_estimated_monthly || 0).toLocaleString();
    renderOpportunities(opps);
}

async function conveneCouncil() {
    const btn = document.getElementById('btn-council');
    if (btn) { btn.disabled = true; btn.textContent = 'Convening...'; }
    const data = await api('/api/money/council', { method: 'POST' });
    if (btn) { btn.disabled = false; btn.textContent = 'Convene Council'; }
    if (data.error) { const mt = document.getElementById('money-top'); if (mt) mt.innerHTML = `<div class="empty-state" style="color:var(--accent-red)">${escHtml(data.error)}</div>`; return; }
    const mo = document.getElementById('money-opps');
    if (mo) mo.textContent = data.total_opportunities || 0;
    renderOpportunities(data.opportunities || []);
}

function renderOpportunities(opps) {
    const topEl = document.getElementById('money-top');
    const listEl = document.getElementById('money-opportunities');
    if (!topEl || !listEl) return;
    if (!Array.isArray(opps) || !opps.length) {
        topEl.innerHTML = '<div class="empty-state">No opportunities yet. Click "Convene Council".</div>';
        listEl.innerHTML = '';
        return;
    }
    const top = opps[0];
    const riskColors = { low: 'var(--accent-green)', medium: 'var(--accent-orange)', high: 'var(--accent-red)', very_high: 'var(--accent-red)' };
    topEl.innerHTML = `
        <div style="padding:4px 0">
            <div style="font-size:17px;font-weight:700;color:var(--accent-gold)">${escHtml(top.title)}</div>
            <div style="display:flex;gap:16px;margin:8px 0;font-size:12px;flex-wrap:wrap">
                <span style="color:var(--accent-cyan)">Confidence: ${Math.round(top.confidence_score * 100)}%</span>
                <span style="color:${riskColors[top.risk_level] || 'var(--text-muted)'}">Risk: ${escHtml(top.risk_level)}</span>
                ${top.estimated_monthly_revenue ? `<span style="color:var(--accent-green)">$${top.estimated_monthly_revenue.toLocaleString()}/mo</span>` : ''}
            </div>
            <p style="font-size:13px;color:var(--text-secondary);margin:8px 0">${escHtml(top.description)}</p>
        </div>`;
    listEl.innerHTML = opps.slice(1).map(opp => `
        <div style="padding:12px 0;border-bottom:1px solid var(--border)">
            <div style="display:flex;justify-content:space-between;align-items:start">
                <div>
                    <div style="font-weight:600;font-size:13px">${escHtml(opp.title)}</div>
                    <div style="font-size:11px;color:var(--text-muted);margin-top:2px">${escHtml(opp.opportunity_type || '')} | Risk: ${escHtml(opp.risk_level)}</div>
                </div>
                <div style="font-size:16px;font-weight:800;color:var(--accent-cyan)">${Math.round(opp.confidence_score * 100)}%</div>
            </div>
        </div>
    `).join('');
    const totalRev = opps.reduce((sum, o) => sum + (o.estimated_monthly_revenue || 0), 0);
    const mr = document.getElementById('money-revenue');
    if (mr) mr.textContent = '$' + totalRev.toLocaleString();
}
