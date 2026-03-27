/* miro-panel.js — Enhanced MiRo panel features:
   - Manual prediction form (full fields)
   - Council debate deep-dive with agent perspectives
   - Confidence adjustment slider
   - What-If Scenario Lab
   - Prediction tournament (source comparison)
   - Calibration trend chart
*/

// ── Manual Prediction Form ──────────────────────────────────
function showManualPredictionModal() {
    showModal({
        title: 'Create Manual Prediction',
        fields: [
            { key: 'symbol', label: 'Symbol', type: 'text', placeholder: 'AAPL, BTC-USD, SPY...', required: true },
            { key: 'direction', label: 'Direction', type: 'select', options: [
                { value: 'long', label: 'Long (Bullish)' },
                { value: 'short', label: 'Short (Bearish)' },
                { value: 'hold', label: 'Hold (Neutral)' },
            ], required: true },
            { key: 'confidence', label: 'Confidence %', type: 'range', min: 30, max: 95, step: 5, value: 70 },
            { key: 'target_price', label: 'Target Price (optional)', type: 'number', placeholder: '0.00' },
            { key: 'reasoning', label: 'Reasoning', type: 'textarea', placeholder: 'Why do you expect this move?', required: true },
            { key: 'deadline_hours', label: 'Deadline (hours)', type: 'number', value: 24, min: 1, max: 720 },
            { key: 'source', label: 'Source', type: 'select', options: [
                { value: 'manual', label: 'Manual' },
                { value: 'miro', label: 'MiRo' },
                { value: 'swarm', label: 'Swarm' },
                { value: 'directive', label: 'Directive' },
            ] },
        ],
        submitLabel: 'Create Prediction',
        onSubmit: async (vals) => {
            await api('/api/predictions/manual', {
                method: 'POST',
                body: {
                    symbol: vals.symbol,
                    direction: vals.direction,
                    confidence: (vals.confidence || 70) / 100,
                    target_price: vals.target_price ? parseFloat(vals.target_price) : null,
                    reasoning: vals.reasoning,
                    deadline_hours: parseInt(vals.deadline_hours) || 24,
                    source: vals.source || 'manual',
                },
            });
            closeModal();
            loadMiro();
        },
    });
}

// ── Confidence Adjustment ───────────────────────────────────
function showAdjustConfidenceModal(predictionId, currentConf) {
    showModal({
        title: 'Adjust Confidence',
        fields: [
            { key: 'confidence', label: 'New Confidence %', type: 'range', min: 10, max: 95, step: 5, value: Math.round(currentConf * 100) },
        ],
        submitLabel: 'Update',
        onSubmit: async (vals) => {
            await api(`/api/predictions/${predictionId}/confidence`, {
                method: 'PATCH',
                body: { confidence: (vals.confidence || 50) / 100 },
            });
            closeModal();
            loadMiro();
        },
    });
}

// ── Resolve Prediction (enhanced) ───────────────────────────
function showResolvePrediction(predictionId) {
    showModal({
        title: 'Resolve Prediction',
        fields: [
            { key: 'accurate', label: 'Outcome', type: 'select', options: [
                { value: 'true', label: 'Correct (Hit)' },
                { value: 'false', label: 'Incorrect (Miss)' },
            ], required: true },
            { key: 'actual_outcome', label: 'What happened?', type: 'textarea', placeholder: 'Describe the actual outcome...', required: true },
        ],
        submitLabel: 'Resolve',
        onSubmit: async (vals) => {
            await api(`/api/predictions/${predictionId}/resolve`, {
                method: 'POST',
                body: { accurate: vals.accurate === 'true', actual_outcome: vals.actual_outcome },
            });
            closeModal();
            loadMiro();
        },
    });
}

// ── Council Deep-Dive ───────────────────────────────────────
let _councilDebating = false;
async function triggerMiroCouncil() {
    if (_councilDebating) return;
    const topic = document.getElementById('miro-topic')?.value?.trim();
    const symbols = document.getElementById('miro-symbols')?.value?.trim() || '';
    if (!topic) { alert('Enter a topic for the council debate'); return; }
    _councilDebating = true;
    const btn = document.getElementById('btn-miro-council');
    if (btn) { btn.disabled = true; btn.textContent = 'Debating...'; }
    const resultEl = document.getElementById('miro-council-result');
    if (resultEl) {
        resultEl.innerHTML = '<div style="color:var(--accent);padding:12px;text-align:center">MiRo is convening the council... <span class="thinking-dots"><span></span><span></span><span></span></span></div>';
    }
    try {
        const data = await api('/api/councils/debate', {
            method: 'POST',
            body: { topic, symbols },
        });
        if (resultEl) {
            const verdict = data.result || '';
            const entities = data.entities || '';
            const scenarios = data.scenarios || '';
            resultEl.innerHTML = `
                <div style="margin-bottom:12px">
                    <div style="font-weight:600;color:var(--accent);margin-bottom:6px">Council Verdict</div>
                    <div style="font-size:13px;line-height:1.6;color:var(--text-primary)">${renderMarkdown(verdict)}</div>
                </div>
                ${entities ? `<div style="margin-bottom:12px">
                    <div style="font-weight:600;color:var(--accent-cyan);margin-bottom:6px;font-size:12px">Entity Map (GraphRAG)</div>
                    <div style="font-size:12px;color:var(--text-secondary);background:var(--bg-elevated);padding:8px;border-radius:6px;font-family:monospace;white-space:pre-wrap">${escHtml(entities)}</div>
                </div>` : ''}
                ${scenarios ? `<div style="margin-bottom:12px">
                    <div style="font-weight:600;color:var(--accent-gold);margin-bottom:6px;font-size:12px">Parallel Scenarios</div>
                    <div style="font-size:12px;color:var(--text-secondary)">${renderMarkdown(scenarios)}</div>
                </div>` : ''}
                ${data.debate_id ? `<div style="font-size:11px;color:var(--text-muted);margin-top:8px">Debate ID: ${escHtml(data.debate_id)} &middot; Session: ${escHtml(data.market_session || '')}</div>` : ''}`;
        }
        loadCouncilHistory();
        loadMiro();
    } catch (e) {
        if (resultEl) resultEl.innerHTML = `<div style="color:var(--accent-red);padding:12px">Council failed: ${escHtml(e.message || String(e))}</div>`;
    }
    _councilDebating = false;
    if (btn) { btn.disabled = false; btn.textContent = 'Convene Council'; }
}

async function loadCouncilHistory() {
    const el = document.getElementById('miro-council-history');
    if (!el) return;
    try {
        const data = await api('/api/councils?limit=10');
        const debates = data?.debates || [];
        if (debates.length) {
            el.innerHTML = debates.map(d => `
                <div style="padding:8px 0;border-bottom:1px solid var(--border);cursor:pointer" onclick="showCouncilDetail('${escHtml(d.id)}')">
                    <div style="display:flex;align-items:center;gap:8px;margin-bottom:3px">
                        <span style="font-size:11px;background:var(--bg-elevated);padding:2px 6px;border-radius:4px;color:var(--accent)">${d.perspective_count || 0} agents</span>
                        <span style="font-size:11px;color:var(--text-muted)">${formatTime(d.created_at)}</span>
                    </div>
                    <div style="font-size:12px;font-weight:500">${escHtml(d.topic || '')}</div>
                    ${d.symbols ? `<div style="font-size:11px;color:var(--accent-cyan);margin-top:2px">${escHtml(d.symbols)}</div>` : ''}
                </div>
            `).join('');
        } else {
            el.innerHTML = '<div style="color:var(--text-muted);padding:12px">No debates yet</div>';
        }
    } catch {
        el.innerHTML = '<div style="color:var(--text-muted);padding:12px">No debates yet</div>';
    }
}

async function showCouncilDetail(debateId) {
    try {
        const data = await api(`/api/councils/${debateId}`);
        const stanceColors = { bullish: 'var(--accent-green)', bearish: 'var(--accent-red)', neutral: 'var(--accent-blue)' };
        const perspectives = (data.perspectives || []).map(p => {
            const color = stanceColors[p.stance] || 'var(--text-secondary)';
            return `<div style="padding:10px;background:var(--bg-elevated);border-radius:6px;margin-bottom:8px;border-left:3px solid ${color}">
                <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
                    <span style="font-weight:600;font-size:13px;color:${color}">${escHtml(p.agent_role || p.agent_id)}</span>
                    <span style="font-size:11px;padding:2px 6px;border-radius:8px;background:${color}22;color:${color}">${escHtml(p.stance)}</span>
                    <span style="font-size:11px;color:var(--text-muted);margin-left:auto">${Math.round(p.confidence * 100)}% conf</span>
                </div>
                <div style="font-size:12px;color:var(--text-secondary);line-height:1.5">${escHtml(p.reasoning)}</div>
                ${p.key_points && p.key_points.length ? `<div style="margin-top:6px">${p.key_points.map(kp => `<span style="font-size:10px;background:var(--bg-card);padding:2px 6px;border-radius:4px;margin-right:4px">${escHtml(kp)}</span>`).join('')}</div>` : ''}
            </div>`;
        }).join('');

        showDetailModal({
            title: `Council Debate: ${(data.topic || '').slice(0, 60)}`,
            content: `
                <div style="margin-bottom:12px">
                    <div style="font-size:11px;color:var(--text-muted)">${escHtml(data.symbols || 'General')} &middot; ${formatTime(data.created_at)}</div>
                </div>
                <div style="margin-bottom:16px">
                    <div style="font-weight:600;color:var(--accent);margin-bottom:6px">Agent Perspectives</div>
                    ${perspectives || '<div style="color:var(--text-muted)">No perspectives recorded</div>'}
                </div>
                <div style="margin-bottom:12px">
                    <div style="font-weight:600;color:var(--accent-gold);margin-bottom:6px">Verdict</div>
                    <div style="font-size:13px;line-height:1.6">${renderMarkdown(data.verdict || 'No verdict')}</div>
                </div>
                ${data.consensus ? `<div>
                    <div style="font-weight:600;color:var(--text-secondary);margin-bottom:6px;font-size:12px">Consensus</div>
                    <div style="font-size:12px;color:var(--text-secondary)">${escHtml(data.consensus)}</div>
                </div>` : ''}`,
        });
    } catch (e) {
        alert('Failed to load debate: ' + (e.message || e));
    }
}

// ── What-If Scenario Lab ────────────────────────────────────
let _simulating = false;
async function runScenarioSimulation() {
    if (_simulating) return;
    const hypothesis = document.getElementById('scenario-hypothesis')?.value?.trim();
    if (!hypothesis) { alert('Enter a hypothesis for the simulation'); return; }
    const symbols = document.getElementById('scenario-symbols')?.value?.trim() || '';
    const horizon = document.getElementById('scenario-horizon')?.value || '1 week';
    const agents = parseInt(document.getElementById('scenario-agents')?.value || '5');

    _simulating = true;
    const btn = document.getElementById('btn-run-scenario');
    if (btn) { btn.disabled = true; btn.textContent = 'Simulating...'; }
    const resultEl = document.getElementById('scenario-result');
    if (resultEl) {
        resultEl.innerHTML = '<div style="color:var(--accent);padding:20px;text-align:center">Running parallel agent simulation... <span class="thinking-dots"><span></span><span></span><span></span></span></div>';
    }

    try {
        const data = await api('/api/scenarios/simulate', {
            method: 'POST',
            body: { hypothesis, symbols, time_horizon: horizon, agent_count: agents, synthesis_rounds: 1 },
        });
        if (resultEl) {
            const pm = data.potentiality_map || {};
            const bull = pm.bull || {};
            const base = pm.base || {};
            const bear = pm.bear || {};
            const perspectives = data.agent_perspectives || {};

            resultEl.innerHTML = `
                <div style="margin-bottom:16px">
                    <div style="font-weight:700;color:var(--accent);margin-bottom:8px;font-size:14px">Potentiality Map</div>
                    <div class="grid-3" style="gap:10px">
                        <div style="background:var(--accent-green)11;border:1px solid var(--accent-green)33;border-radius:8px;padding:12px">
                            <div style="font-weight:700;color:var(--accent-green);font-size:20px;margin-bottom:4px">${Math.round((bull.probability || 0) * 100)}%</div>
                            <div style="font-weight:600;color:var(--accent-green);font-size:12px;margin-bottom:6px">BULL CASE</div>
                            <div style="font-size:11px;color:var(--text-secondary);line-height:1.4">${escHtml(bull.scenario || 'N/A')}</div>
                        </div>
                        <div style="background:var(--accent-blue)11;border:1px solid var(--accent-blue)33;border-radius:8px;padding:12px">
                            <div style="font-weight:700;color:var(--accent-blue);font-size:20px;margin-bottom:4px">${Math.round((base.probability || 0) * 100)}%</div>
                            <div style="font-weight:600;color:var(--accent-blue);font-size:12px;margin-bottom:6px">BASE CASE</div>
                            <div style="font-size:11px;color:var(--text-secondary);line-height:1.4">${escHtml(base.scenario || 'N/A')}</div>
                        </div>
                        <div style="background:var(--accent-red)11;border:1px solid var(--accent-red)33;border-radius:8px;padding:12px">
                            <div style="font-weight:700;color:var(--accent-red);font-size:20px;margin-bottom:4px">${Math.round((bear.probability || 0) * 100)}%</div>
                            <div style="font-weight:600;color:var(--accent-red);font-size:12px;margin-bottom:6px">BEAR CASE</div>
                            <div style="font-size:11px;color:var(--text-secondary);line-height:1.4">${escHtml(bear.scenario || 'N/A')}</div>
                        </div>
                    </div>
                </div>
                ${Object.keys(perspectives).length ? `
                <div style="margin-bottom:16px">
                    <div style="font-weight:600;color:var(--text-secondary);margin-bottom:8px;font-size:12px">Agent Perspectives (${Object.keys(perspectives).length} agents)</div>
                    ${Object.entries(perspectives).map(([agent, text]) => {
                        const agentColors = { bull: 'var(--accent-green)', bear: 'var(--accent-red)', quant: 'var(--accent-cyan)', contrarian: 'var(--accent-purple)', macro: 'var(--accent-gold)', sentiment: 'var(--accent-orange)', industry: 'var(--accent-blue)' };
                        const color = agentColors[agent] || 'var(--accent)';
                        return `<div style="padding:8px;background:var(--bg-elevated);border-radius:6px;margin-bottom:6px;border-left:3px solid ${color}">
                            <div style="font-weight:600;font-size:12px;color:${color};margin-bottom:4px;text-transform:uppercase">${escHtml(agent)}</div>
                            <div style="font-size:12px;color:var(--text-secondary);line-height:1.4">${escHtml(String(text).slice(0, 400))}${String(text).length > 400 ? '...' : ''}</div>
                        </div>`;
                    }).join('')}
                </div>` : ''}
                <div>
                    <div style="font-weight:600;color:var(--accent);margin-bottom:6px;font-size:12px">Synthesis</div>
                    <div style="font-size:12px;color:var(--text-secondary);line-height:1.5">${renderMarkdown(data.synthesis || '')}</div>
                </div>
                <div style="font-size:11px;color:var(--text-muted);margin-top:8px">Scenario ID: ${escHtml(data.id || '')} &middot; ${formatTime(data.created_at)}</div>`;
        }
        loadScenarioHistory();
    } catch (e) {
        if (resultEl) resultEl.innerHTML = `<div style="color:var(--accent-red);padding:12px">Simulation failed: ${escHtml(e.message || String(e))}</div>`;
    }
    _simulating = false;
    if (btn) { btn.disabled = false; btn.textContent = 'Run Simulation'; }
}

async function loadScenarioHistory() {
    const el = document.getElementById('scenario-history');
    if (!el) return;
    try {
        const data = await api('/api/scenarios?limit=10');
        const scenarios = data?.scenarios || [];
        if (scenarios.length) {
            el.innerHTML = scenarios.map(s => `
                <div style="padding:8px 0;border-bottom:1px solid var(--border);cursor:pointer" onclick="showScenarioDetail('${escHtml(s.id)}')">
                    <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px">
                        <span style="font-size:11px;color:var(--accent-green)">${Math.round((s.bull_probability || 0) * 100)}%B</span>
                        <span style="font-size:11px;color:var(--accent-blue)">${Math.round((s.base_probability || 0) * 100)}%</span>
                        <span style="font-size:11px;color:var(--accent-red)">${Math.round((s.bear_probability || 0) * 100)}%B</span>
                        <span style="font-size:11px;color:var(--text-muted);margin-left:auto">${formatTime(s.created_at)}</span>
                    </div>
                    <div style="font-size:12px;font-weight:500">${escHtml((s.hypothesis || '').slice(0, 80))}</div>
                    ${s.symbols ? `<div style="font-size:11px;color:var(--accent-cyan);margin-top:2px">${escHtml(s.symbols)}</div>` : ''}
                </div>
            `).join('');
        } else {
            el.innerHTML = '<div style="color:var(--text-muted);padding:12px">No simulations yet</div>';
        }
    } catch {
        el.innerHTML = '<div style="color:var(--text-muted);padding:12px">No simulations yet</div>';
    }
}

async function showScenarioDetail(scenarioId) {
    try {
        const data = await api(`/api/scenarios/${scenarioId}`);
        const perspectives = data.agent_perspectives || {};
        const agentColors = { bull: 'var(--accent-green)', bear: 'var(--accent-red)', quant: 'var(--accent-cyan)', contrarian: 'var(--accent-purple)', macro: 'var(--accent-gold)', sentiment: 'var(--accent-orange)', industry: 'var(--accent-blue)' };

        showDetailModal({
            title: `Scenario: ${(data.hypothesis || '').slice(0, 50)}`,
            content: `
                <div style="margin-bottom:12px">
                    <div style="font-size:12px;color:var(--text-muted)">${escHtml(data.symbols || 'General')} &middot; ${escHtml(data.time_horizon || '')} &middot; ${formatTime(data.created_at)}</div>
                    <div style="font-size:13px;margin-top:6px">${escHtml(data.hypothesis)}</div>
                </div>
                <div class="grid-3" style="gap:8px;margin-bottom:16px">
                    <div style="background:var(--accent-green)11;padding:10px;border-radius:6px;text-align:center">
                        <div style="font-size:18px;font-weight:700;color:var(--accent-green)">${Math.round((data.bull_probability || 0) * 100)}%</div>
                        <div style="font-size:11px;color:var(--accent-green)">BULL</div>
                        <div style="font-size:11px;color:var(--text-secondary);margin-top:4px">${escHtml((data.bull_scenario || '').slice(0, 120))}</div>
                    </div>
                    <div style="background:var(--accent-blue)11;padding:10px;border-radius:6px;text-align:center">
                        <div style="font-size:18px;font-weight:700;color:var(--accent-blue)">${Math.round((data.base_probability || 0) * 100)}%</div>
                        <div style="font-size:11px;color:var(--accent-blue)">BASE</div>
                        <div style="font-size:11px;color:var(--text-secondary);margin-top:4px">${escHtml((data.base_scenario || '').slice(0, 120))}</div>
                    </div>
                    <div style="background:var(--accent-red)11;padding:10px;border-radius:6px;text-align:center">
                        <div style="font-size:18px;font-weight:700;color:var(--accent-red)">${Math.round((data.bear_probability || 0) * 100)}%</div>
                        <div style="font-size:11px;color:var(--accent-red)">BEAR</div>
                        <div style="font-size:11px;color:var(--text-secondary);margin-top:4px">${escHtml((data.bear_scenario || '').slice(0, 120))}</div>
                    </div>
                </div>
                ${Object.keys(perspectives).length ? `<div style="margin-bottom:12px">
                    <div style="font-weight:600;font-size:12px;margin-bottom:6px">Agent Perspectives</div>
                    ${Object.entries(perspectives).map(([a, t]) => `<div style="padding:6px 8px;background:var(--bg-elevated);border-radius:4px;margin-bottom:4px;border-left:3px solid ${agentColors[a] || 'var(--accent)'}"><span style="font-weight:600;font-size:11px;color:${agentColors[a] || 'var(--accent)'};text-transform:uppercase">${escHtml(a)}</span><div style="font-size:11px;color:var(--text-secondary);margin-top:2px">${escHtml(String(t).slice(0, 300))}</div></div>`).join('')}
                </div>` : ''}
                <div>
                    <div style="font-weight:600;font-size:12px;margin-bottom:6px">Synthesis</div>
                    <div style="font-size:12px;color:var(--text-secondary);line-height:1.5">${renderMarkdown(data.synthesis || '')}</div>
                </div>`,
        });
    } catch (e) {
        alert('Failed to load scenario: ' + (e.message || e));
    }
}

// ── Prediction Tournament ───────────────────────────────────
async function loadTournament() {
    const el = document.getElementById('miro-tournament');
    if (!el) return;
    try {
        const data = await api('/api/predictions/tournament');
        const tournament = data?.tournament || {};
        const sources = Object.entries(tournament);
        if (!sources.length) {
            el.innerHTML = '<div class="empty-state">No tournament data yet</div>';
            return;
        }
        el.innerHTML = '<div class="table-wrap"><table><thead><tr>' +
            '<th>Source</th><th>Total</th><th>7d Acc</th><th>30d Acc</th><th>Calibration</th>' +
            '</tr></thead><tbody>' +
            sources.map(([src, info]) => {
                const acc30 = info.accuracy_30d || 0;
                const acc7 = info.accuracy_7d || 0;
                const color30 = acc30 >= 0.7 ? 'var(--accent-green)' : acc30 >= 0.5 ? 'var(--accent-gold)' : 'var(--accent-red)';
                const color7 = acc7 >= 0.7 ? 'var(--accent-green)' : acc7 >= 0.5 ? 'var(--accent-gold)' : 'var(--accent-red)';
                const calBuckets = (info.calibration_buckets || []).map(b =>
                    `<span style="font-size:10px;padding:1px 4px;border-radius:3px;background:var(--bg-elevated)">${Math.round(b.bucket * 100)}%:${b.correct}/${b.total}</span>`
                ).join(' ');
                return `<tr>
                    <td><strong style="text-transform:capitalize">${escHtml(src)}</strong></td>
                    <td>${info.total_predictions || 0}</td>
                    <td style="color:${color7}">${info.total_predictions ? (acc7 * 100).toFixed(0) + '%' : '\u2014'}</td>
                    <td style="color:${color30}">${info.total_predictions ? (acc30 * 100).toFixed(0) + '%' : '\u2014'}</td>
                    <td>${calBuckets || '\u2014'}</td>
                </tr>`;
            }).join('') +
            '</tbody></table></div>';
    } catch {
        el.innerHTML = '<div class="empty-state">Tournament data unavailable</div>';
    }
}

// ── Calibration Trend ───────────────────────────────────────
async function loadCalibrationTrend() {
    const el = document.getElementById('miro-cal-trend');
    if (!el) return;
    try {
        const data = await api('/api/predictions/calibration/trend?weeks=8');
        const trend = data?.trend || [];
        if (!trend.length || trend.every(w => w.total === 0)) {
            el.innerHTML = '<div class="empty-state">Not enough data for calibration trend</div>';
            return;
        }
        const maxTotal = Math.max(...trend.map(w => w.total), 1);
        el.innerHTML = `
            <div style="display:flex;align-items:flex-end;gap:4px;height:80px;padding:8px 0">
                ${trend.map(w => {
                    const h = Math.max(w.total / maxTotal * 70, 2);
                    const accPct = w.total > 0 ? (w.accuracy * 100).toFixed(0) : 0;
                    const color = w.accuracy >= 0.7 ? 'var(--accent-green)' : w.accuracy >= 0.5 ? 'var(--accent-gold)' : 'var(--accent-red)';
                    return `<div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:2px" title="${w.week_start}: ${w.hits}/${w.total} (${accPct}%)">
                        <div style="font-size:9px;color:var(--text-muted)">${accPct}%</div>
                        <div style="width:100%;height:${h}px;background:${w.total > 0 ? color : 'var(--border)'};border-radius:3px"></div>
                        <div style="font-size:8px;color:var(--text-muted)">${w.week_start.slice(5)}</div>
                    </div>`;
                }).join('')}
            </div>`;
    } catch {
        el.innerHTML = '<div class="empty-state">Trend unavailable</div>';
    }
}

// ── Enhanced MiRo Loader ────────────────────────────────────
// Capture the base loadMiro from panels-intelligence.js, then define the
// enhanced version directly as loadMiro (no global reassignment).
const _originalLoadMiro = typeof loadMiro === 'function' ? loadMiro : null;

// Directly define the enhanced loader as loadMiro — avoids fragile global reassignment.
// eslint-disable-next-line no-redeclare
async function loadMiro() {
    // Load base stats + predictions from original loader
    if (_originalLoadMiro) {
        await _originalLoadMiro();
    }
    // Load enhanced sections in parallel
    await Promise.all([
        loadCouncilHistory(),
        loadTournament(),
        loadCalibrationTrend(),
        loadScenarioHistory(),
    ]);
}
