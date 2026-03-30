/* panels-system.js — Dashboard, Diagnostics, Settings, Analytics, Evolution, Reflections, Builder */

// ── Dashboard ───────────────────────────────────────────────
async function loadDashboard() {
    const raw = await api('/api/dashboard/status');
    const data = raw?.data ?? raw;
    if (data.error) return;

    const totalMemories = data.memory?.total || 0;
    const totalSkills = data.skills?.total || 0;
    const agentCount = data.agents?.length || 0;
    const maturity = data.self_dev?.maturity_score || 0;
    const maturityLevel = data.self_dev?.maturity_level || 'unknown';
    const evolutions = data.self_dev?.evolution_count || 0;
    const pluginCount = data.plugins?.total_plugins || 0;

    animateValue('stat-memories', totalMemories);
    animateValue('stat-skills', totalSkills);
    animateValue('stat-agents', agentCount);
    _setText('stat-maturity', Math.round(maturity * 100) + '%');
    animateValue('stat-evolutions', evolutions);
    animateValue('stat-plugins', pluginCount);

    _setText('ts-agents', agentCount);
    _setText('ts-memories', totalMemories);
    _setText('ts-plugins', pluginCount);

    updateMaturityDisplay(maturity, maturityLevel);
    updateSidebarAgents(data.agents || []);

    const agentsList = document.getElementById('dashboard-agents');
    if (agentsList) {
        agentsList.innerHTML = (data.agents || []).map(a => {
            const h = a.health?.status || 'unknown';
            const color = ['online', 'available', 'internal'].includes(h) ? 'var(--accent-green)' : h === 'offline' ? 'var(--accent-red)' : 'var(--accent-orange)';
            return `<div style="display:flex;align-items:center;gap:8px;padding:6px 0;font-size:12px">
                <span style="width:6px;height:6px;border-radius:50%;background:${color};flex-shrink:0"></span>
                <span>${escHtml(a.name)}</span>
                <span style="margin-left:auto"><span class="status-pill ${h}">${escHtml(h)}</span></span>
            </div>`;
        }).join('');
    }

    const gapsEl = document.getElementById('dashboard-gaps');
    const gaps = data.self_dev?.capability_gaps || [];
    if (gapsEl) {
        if (gaps.length) {
            gapsEl.innerHTML = gaps.slice(0, 8).map(g =>
                `<div style="padding:8px 0;border-bottom:1px solid var(--border);font-size:12px">
                    <div style="color:var(--accent-orange);font-weight:500">${escHtml(g.description)}</div>
                    <div style="color:var(--text-muted);font-size:11px;margin-top:2px">${escHtml(g.suggestion)}</div>
                </div>`
            ).join('');
        } else {
            gapsEl.innerHTML = '<div style="padding:20px;text-align:center;color:var(--accent-green);font-size:13px">No capability gaps detected</div>';
        }
    }

    // Load dashboard extras (non-blocking, fire-and-forget)
    loadDashboardDigests();
    loadDashboardPatterns();
    loadDashboardApprovals();
    loadActivityTimeline();
    loadDashboardAGIStatus();
    loadActivityFeed();
    loadPerpetualStatus();
    loadSwarmStatus();
    loadResearchFeed();

    // Load digest + providers in parallel
    const [digestData, provData] = await Promise.all([
        api('/api/conversations/digest/latest?digest_type=daily').catch(() => null),
        api('/api/dashboard/providers').catch(() => null),
    ]);

    // Render daily digest
    const digestCard = document.getElementById('digest-card');
    const digestEl = document.getElementById('digest-content');
    if (digestCard && digestEl && digestData?.digest) {
        digestCard.style.display = '';
        digestEl.textContent = digestData.digest.content || '';
    }

    // Render provider status
    const provEl = document.getElementById('dashboard-providers');
    if (provEl && provData) {
        const providers = provData.providers || {};
        const registered = provData.registered || [];
        if (registered.length === 0) {
            provEl.innerHTML = '<div style="padding:16px;text-align:center;color:var(--accent-red);font-size:13px">No LLM providers — offline mode</div>';
        } else {
            const active = provData.active_provider || 'unknown';
            const failovers = provData.failovers || 0;
            provEl.innerHTML = `
                <div style="padding:6px 0;font-size:11px;color:var(--text-muted)">
                    Active: <strong style="color:var(--accent-green)">${escHtml(active)}</strong>
                    &middot; ${registered.length} providers &middot; ${failovers} failovers
                </div>
                ${registered.map(name => {
                    const p = providers[name] || {};
                    const avail = p.available !== false;
                    const color = avail ? 'var(--accent-green)' : 'var(--accent-red)';
                    const label = p.circuit_open ? 'circuit open' : avail ? 'ready' : 'down';
                    const cost = name === 'ollama' ? 'FREE' : name === 'groq' ? 'FREE tier' : name === 'together' ? 'FREE/cheap' : name === 'deepseek' ? '$0.14/M' : name === 'openai' ? '$2.50/M' : '$3/M';
                    return `<div style="display:flex;align-items:center;gap:8px;padding:5px 0;font-size:12px">
                        <span style="width:6px;height:6px;border-radius:50%;background:${color};flex-shrink:0"></span>
                        <span style="font-weight:500">${escHtml(name)}</span>
                        <span style="color:var(--text-muted);font-size:10px">${cost}</span>
                        <span style="margin-left:auto"><span class="status-pill ${avail ? 'online' : 'offline'}">${label}</span></span>
                    </div>`;
                }).join('')}`;
        }
    }
}

async function generateDigest() {
    const el = document.getElementById('digest-content');
    if (el) el.textContent = 'Generating brief…';
    try {
        const data = await api('/api/conversations/digest/generate', { method: 'POST' });
        if (el && data?.digest?.content) {
            el.textContent = data.digest.content;
            document.getElementById('digest-card').style.display = '';
        }
    } catch (e) {
        if (el) el.textContent = 'Failed to generate: ' + e.message;
    }
}

function updateMaturityDisplay(score, level) {
    const pct = Math.round(score * 100);
    const pctEl = document.getElementById('maturity-pct');
    const lvlEl = document.getElementById('maturity-level');
    const ring = document.getElementById('maturity-ring');
    if (pctEl) pctEl.textContent = pct + '%';
    if (lvlEl) lvlEl.textContent = level;
    if (ring) ring.style.strokeDashoffset = 169.6 - (score * 169.6);
}

function updateSidebarAgents(agents) {
    state.agents = agents;
    const countEl = document.getElementById('agent-count');
    if (countEl) countEl.textContent = agents.length;
    const c = document.getElementById('sidebar-agents');
    if (!c) return;
    c.innerHTML = agents.map(a => {
        const h = a.health?.status || 'unknown';
        const dotClass = ['online', 'available', 'internal'].includes(h) ? 'online' : h === 'offline' ? 'offline' : 'idle';
        const color = AGENT_COLORS[a.id] || 'var(--accent)';
        const isAstra = a.id === 'astra';
        return `<div class="dm-item" onclick="delegateToAgent('${a.id}')">
            <div class="dm-avatar" style="background:${color}">${a.name[0]}</div>
            <span class="dm-name">${escHtml(a.name)}${isAstra ? ' <span class="lead-badge">LEAD</span>' : ''}</span>
            <span class="dm-status ${dotClass}"></span>
        </div>`;
    }).join('');
}

function delegateToAgent(agentId) {
    switchPanel('chat');
    const agent = state.agents.find(a => a.id === agentId);
    const name = agent?.name || agentId;
    document.getElementById('chat-input').value = `@${name} `;
    document.getElementById('chat-input').focus();
}

function animateValue(id, target) {
    const el = document.getElementById(id);
    if (!el) return;
    const current = parseInt(el.textContent) || 0;
    if (current === target) { el.textContent = target.toLocaleString(); return; }
    const step = Math.max(1, Math.floor(Math.abs(target - current) / 15));
    let val = current;
    const interval = setInterval(() => {
        val += (target > current) ? step : -step;
        if ((target > current && val >= target) || (target < current && val <= target)) {
            val = target;
            clearInterval(interval);
        }
        el.textContent = val.toLocaleString();
    }, 30);
}

// ── Analytics Panel ──────────────────────────────────────────
const _charts = {};

async function loadAnalytics() {
    const [pulse, memData, costData, agentData, routingData, expData, proactiveData, revenueData] = await Promise.all([
        api('/api/analytics/system-pulse'),
        api('/api/analytics/memory-growth?days=30'),
        api('/api/analytics/cost-trend?days=30'),
        api('/api/analytics/agent-activity?days=7'),
        api('/api/analytics/routing-weights'),
        api('/api/analytics/experience-summary'),
        api('/api/autonomous/proactive/stats'),
        api('/api/civilization/revenue/snapshot'),
    ]);

    // Pulse stats
    const pulseEl = document.getElementById('analytics-pulse');
    if (pulseEl && pulse && !pulse.error) {
        pulseEl.innerHTML = `
            <div class="stat-card"><div class="stat-value" style="color:var(--accent-cyan)">${pulse.total_llm_calls || 0}</div><div class="stat-label">LLM Calls</div></div>
            <div class="stat-card"><div class="stat-value" style="color:var(--accent-green)">$${(pulse.cost_today_usd || 0).toFixed(2)}</div><div class="stat-label">Cost Today</div></div>
            <div class="stat-card"><div class="stat-value" style="color:var(--accent-gold)">${pulse.total_interactions || 0}</div><div class="stat-label">Interactions</div></div>`;
    }

    // Charts (only if Chart.js loaded)
    if (typeof Chart === 'undefined') return;

    const chartStyle = getComputedStyle(document.documentElement);
    const accent = chartStyle.getPropertyValue('--accent').trim();
    const accentGreen = chartStyle.getPropertyValue('--accent-green').trim();
    const accentCyan = chartStyle.getPropertyValue('--accent-cyan').trim();
    const accentGold = chartStyle.getPropertyValue('--accent-gold').trim();
    const textMuted = chartStyle.getPropertyValue('--text-muted').trim();
    const border = chartStyle.getPropertyValue('--border').trim();

    const chartDefaults = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
            x: { ticks: { color: textMuted, font: { size: 10 } }, grid: { color: border + '40' } },
            y: { ticks: { color: textMuted, font: { size: 10 } }, grid: { color: border + '40' } },
        },
    };

    // Memory growth chart
    if (memData?.data?.length) {
        _renderChart('chart-memory', {
            type: 'line',
            data: {
                labels: memData.data.map(d => d.date.slice(5)),
                datasets: [{
                    data: memData.data.map(d => d.total),
                    borderColor: accent,
                    backgroundColor: accent + '20',
                    fill: true, tension: 0.3, pointRadius: 2,
                }],
            },
            options: chartDefaults,
        });
    }

    // Cost trend chart
    if (costData?.data?.length) {
        _renderChart('chart-cost', {
            type: 'bar',
            data: {
                labels: (costData.data || []).map(d => (d.date || '').slice(5)),
                datasets: [{
                    data: (costData.data || []).map(d => d.cost_usd || d.total_cost || 0),
                    backgroundColor: accentGold + '80',
                    borderColor: accentGold,
                    borderWidth: 1, borderRadius: 3,
                }],
            },
            options: chartDefaults,
        });
    }

    // Agent activity chart
    if (agentData?.data?.length) {
        const allAgents = {};
        agentData.data.forEach(d => d.agents.forEach(a => { allAgents[a.agent] = (allAgents[a.agent] || 0) + a.count; }));
        const topAgents = Object.entries(allAgents).sort((a, b) => b[1] - a[1]).slice(0, 8);
        _renderChart('chart-agents', {
            type: 'bar',
            data: {
                labels: topAgents.map(([a]) => a.length > 12 ? a.slice(0, 12) + '..' : a),
                datasets: [{
                    data: topAgents.map(([, c]) => c),
                    backgroundColor: [accent, accentGreen, accentCyan, accentGold, '#a87bd4', '#d47ba8', '#5b9bd5', '#e8993a'].map(c => c + '80'),
                    borderColor: [accent, accentGreen, accentCyan, accentGold, '#a87bd4', '#d47ba8', '#5b9bd5', '#e8993a'],
                    borderWidth: 1, borderRadius: 3,
                }],
            },
            options: { ...chartDefaults, indexAxis: 'y' },
        });
    }

    // Routing weights (radar chart)
    if (routingData?.data?.length) {
        _renderChart('chart-routing', {
            type: 'radar',
            data: {
                labels: routingData.data.map(d => d.agent.length > 10 ? d.agent.slice(0, 10) + '..' : d.agent),
                datasets: [{
                    data: routingData.data.map(d => d.weight),
                    borderColor: accentCyan,
                    backgroundColor: accentCyan + '20',
                    pointBackgroundColor: accentCyan, pointRadius: 3,
                }],
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: { r: { ticks: { color: textMuted, font: { size: 9 } }, grid: { color: border + '40' }, pointLabels: { color: textMuted, font: { size: 10 } } } },
            },
        });
    }

    // Experience breakdown
    const expEl = document.getElementById('analytics-experience');
    if (expEl && expData?.data) {
        const s = expData.data;
        const types = s.by_type || {};
        expEl.innerHTML = `
            <div class="grid-4" style="margin-top:8px">
                ${Object.entries(types).map(([t, c]) => `
                    <div class="stat-card" style="padding:10px">
                        <div class="stat-value" style="font-size:18px">${c}</div>
                        <div class="stat-label">${escHtml(t)}</div>
                    </div>
                `).join('')}
            </div>
            <div style="font-size:12px;color:var(--text-muted);margin-top:8px">Total: ${s.total || 0} experiences across ${Object.keys(s.by_domain || {}).length} domains</div>`;
    }

    // Proactive actions chart
    if (proactiveData && !proactiveData.error) {
        const actions = proactiveData.actions || proactiveData.data?.actions || [];
        const sorted = [...actions].filter(a => a.run_count > 0).sort((a, b) => b.run_count - a.run_count).slice(0, 10);
        if (sorted.length) {
            _renderChart('chart-proactive', {
                type: 'bar',
                data: {
                    labels: sorted.map(a => (a.name || '').length > 14 ? a.name.slice(0, 14) + '..' : a.name),
                    datasets: [{
                        data: sorted.map(a => a.run_count),
                        backgroundColor: accentCyan + '80',
                        borderColor: accentCyan,
                        borderWidth: 1, borderRadius: 3,
                    }],
                },
                options: { ...chartDefaults, indexAxis: 'y' },
            });
        }
    }

    // Revenue streams chart
    if (revenueData && !revenueData.error) {
        const streams = revenueData.streams || revenueData.data?.streams || [];
        if (streams.length) {
            _renderChart('chart-revenue', {
                type: 'doughnut',
                data: {
                    labels: streams.map(s => s.name || s.stream || 'Unknown'),
                    datasets: [{
                        data: streams.map(s => s.revenue || s.total || 0),
                        backgroundColor: [accent + '80', accentGreen + '80', accentCyan + '80', accentGold + '80', '#a87bd480'],
                        borderColor: [accent, accentGreen, accentCyan, accentGold, '#a87bd4'],
                        borderWidth: 1,
                    }],
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    plugins: { legend: { position: 'right', labels: { color: textMuted, font: { size: 10 } } } },
                },
            });
        }
    }
}

function _renderChart(canvasId, config) {
    if (_charts[canvasId]) _charts[canvasId].destroy();
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    _charts[canvasId] = new Chart(canvas.getContext('2d'), config);
}

// ── Diagnostics Panel ───────────────────────────────────────
let _diagRunning = false;
async function runDiagnostics() {
    if (_diagRunning) return;
    _diagRunning = true;
    const btn = document.getElementById('btn-run-diag');
    if (btn) { btn.textContent = 'Running...'; btn.disabled = true; }

    try {
        const report = await api('/api/diagnostics/full');
        if (!report) return;
        const s = report.summary || {};

        document.getElementById('diag-total').textContent = s.total || 0;
        document.getElementById('diag-passed').textContent = s.passed || 0;
        document.getElementById('diag-failed').textContent = s.failed || 0;
        document.getElementById('diag-warnings').textContent = s.warnings || 0;

        // Health bar
        const pct = s.health_pct || 0;
        const barColor = pct >= 80 ? '#4caf50' : pct >= 50 ? '#ff9800' : '#f44336';
        document.getElementById('diag-health-bar').innerHTML = `
            <div class="card" style="padding:12px">
                <div style="display:flex;justify-content:space-between;margin-bottom:6px">
                    <span style="font-weight:600">System Health</span>
                    <span style="font-weight:700;color:${barColor}">${pct}%</span>
                </div>
                <div style="background:var(--bg-secondary);border-radius:6px;height:12px;overflow:hidden">
                    <div style="width:${pct}%;height:100%;background:${barColor};border-radius:6px;transition:width 0.5s"></div>
                </div>
                <div style="font-size:11px;color:var(--text-secondary);margin-top:4px">
                    ${s.passed} passed · ${s.failed} failed · ${s.warnings} warnings · ${s.skipped || 0} skipped · ${report.duration_ms}ms
                </div>
            </div>`;

        // Failures section
        const failures = report.failures || [];
        const warnings = report.warnings || [];
        let alertHtml = '';
        if (failures.length) {
            alertHtml += `<div class="card" style="border-left:3px solid #f44336;margin-bottom:8px">
                <div class="card-title" style="color:#f44336">Failures (${failures.length})</div>
                ${failures.map(f => `<div style="padding:4px 0;font-size:13px"><strong>${escHtml(f.name)}</strong> <span style="color:var(--text-secondary)">[${f.category}]</span> — ${escHtml(f.message)}</div>`).join('')}
            </div>`;
        }
        if (warnings.length) {
            alertHtml += `<div class="card" style="border-left:3px solid #ff9800">
                <div class="card-title" style="color:#ff9800">Warnings (${warnings.length})</div>
                ${warnings.map(w => `<div style="padding:4px 0;font-size:13px"><strong>${escHtml(w.name)}</strong> <span style="color:var(--text-secondary)">[${w.category}]</span> — ${escHtml(w.message)}</div>`).join('')}
            </div>`;
        }
        document.getElementById('diag-failures').innerHTML = alertHtml;

        // Per-category breakdown
        const statusIcon = { pass: '\u2713', fail: '\u2717', warn: '\u26A0', skip: '\u25CB' };
        const statusColor = { pass: '#4caf50', fail: '#f44336', warn: '#ff9800', skip: '#888' };
        const checks = report.checks || [];
        const categories = [...new Set(checks.map(c => c.category))];

        document.getElementById('diag-categories').innerHTML = categories.map(cat => {
            const catChecks = checks.filter(c => c.category === cat);
            const catStats = report.by_category?.[cat] || {};
            return `
                <div class="card" style="margin-bottom:8px">
                    <div class="card-title" style="display:flex;justify-content:space-between;align-items:center">
                        <span>${escHtml(cat.toUpperCase())}</span>
                        <span style="font-size:12px;font-weight:400;color:var(--text-secondary)">
                            ${catStats.pass || 0} pass · ${catStats.fail || 0} fail · ${catStats.warn || 0} warn
                        </span>
                    </div>
                    ${catChecks.map(c => `
                        <div style="display:flex;align-items:center;gap:8px;padding:4px 0;border-bottom:1px solid var(--border);font-size:13px">
                            <span style="color:${statusColor[c.status]};font-weight:700;width:16px;text-align:center">${statusIcon[c.status]}</span>
                            <span style="font-weight:500;min-width:180px">${escHtml(c.name)}</span>
                            <span style="color:var(--text-secondary);flex:1">${escHtml(c.message)}</span>
                            ${c.duration_ms ? `<span style="color:var(--text-secondary);font-size:11px">${c.duration_ms}ms</span>` : ''}
                        </div>
                    `).join('')}
                </div>`;
        }).join('');
    } catch (e) {
        document.getElementById('diag-categories').innerHTML = `<div class="card" style="color:#f44336">Diagnostic failed: ${escHtml(e.message || String(e))}</div>`;
    } finally {
        _diagRunning = false;
        if (btn) { btn.textContent = 'Run Full Diagnostic'; btn.disabled = false; }
    }
}

function loadDiagnostics() {
    // Auto-run on panel open if no results yet
    if (document.getElementById('diag-total').textContent === '\u2014') {
        runDiagnostics();
    }
}

// ── Settings Panel ──────────────────────────────────────────
async function loadSettings() {
    const [schema, current] = await Promise.all([
        api('/api/settings/schema'),
        api('/api/settings'),
    ]);
    const container = document.getElementById('settings-groups');
    if (!container || !schema?.groups) return;
    const settings = current?.settings || {};

    container.innerHTML = schema.groups.map(group => `
        <div class="settings-group">
            <div class="settings-group-header">${escHtml(group.label)}</div>
            ${group.fields.map(f => {
                const val = settings[f.key] ?? f.default;
                let input = '';
                if (f.type === 'toggle') {
                    input = `<label class="toggle-switch">
                        <input type="checkbox" ${val ? 'checked' : ''} onchange="updateSetting('${f.key}', this.checked)">
                        <span class="toggle-slider"></span>
                    </label>`;
                } else if (f.type === 'select') {
                    input = `<select onchange="updateSetting('${f.key}', this.value)">
                        ${f.options.map(o => `<option value="${o}" ${val === o ? 'selected' : ''}>${o}</option>`).join('')}
                    </select>`;
                } else if (f.type === 'number') {
                    input = `<input type="number" value="${val}" step="${f.step || 1}" style="width:120px" onchange="updateSetting('${f.key}', parseFloat(this.value))">`;
                } else {
                    input = `<input type="text" value="${escHtml(String(val))}" style="width:200px" onchange="updateSetting('${f.key}', this.value)">`;
                }
                return `<div class="settings-field">
                    <span class="settings-field-label">${escHtml(f.label)}</span>
                    <div class="settings-field-input">${input}</div>
                </div>`;
            }).join('')}
        </div>
    `).join('');
}

async function updateSetting(key, value) {
    await api('/api/settings', {
        method: 'PATCH',
        body: { [key]: value },
    });
}

async function resetSettings() {
    await api('/api/settings/reset', { method: 'POST' });
    loadSettings();
}

// ── Evolution ───────────────────────────────────────────────
async function loadEvolution() {
    const [assessment, log] = await Promise.all([api('/api/dashboard/assessment'), api('/api/dashboard/evolution?limit=30')]);
    const ae = document.getElementById('evolution-assessment');
    if (ae && assessment && !assessment.error) {
        const matPct = Math.round(assessment.maturity_score * 100);
        ae.innerHTML = `
            <div class="grid-3" style="margin-bottom:16px">
                <div class="stat-card"><div class="stat-value" style="font-size:20px;color:var(--accent-gold)">${matPct}%</div><div class="stat-label">${escHtml(assessment.maturity_level)}</div></div>
                <div class="stat-card"><div class="stat-value" style="font-size:20px;color:var(--accent-cyan)">${assessment.memories?.total || 0}</div><div class="stat-label">Memories</div></div>
                <div class="stat-card"><div class="stat-value" style="font-size:20px;color:var(--accent-green)">${assessment.skills?.total || 0}</div><div class="stat-label">Skills</div></div>
            </div>`;
    }
    const le = document.getElementById('evolution-log');
    if (!le) return;
    if (Array.isArray(log) && log.length) {
        le.innerHTML = log.map(e => `
            <div style="padding:10px 0;border-bottom:1px solid var(--border);font-size:12px">
                <div style="display:flex;align-items:center;gap:8px">
                    <span class="memory-type-badge">${escHtml(e.action_type)}</span>
                    <span style="color:var(--text-muted);font-size:10px;margin-left:auto">${formatTime(e.timestamp)}</span>
                </div>
                <div style="margin-top:4px;font-size:13px">${escHtml(e.description)}</div>
            </div>
        `).join('');
    } else {
        le.innerHTML = '<div class="empty-state">No evolution entries yet.</div>';
    }
}

// ── Reflections ─────────────────────────────────────────────
async function loadReflections() {
    const raw = await api('/api/dashboard/status');
    const data = raw?.data ?? raw;
    const c = document.getElementById('reflections-list');
    if (!c) return;
    if (data.reflections?.length) {
        c.innerHTML = data.reflections.map(r => `
            <div class="reflection-card">
                <div class="reflection-insight">${escHtml(r.insight)}</div>
                ${r.observation ? `<p style="font-size:12px;color:var(--text-secondary);margin:6px 0">${escHtml(r.observation)}</p>` : ''}
                ${r.action ? `<div class="reflection-action">Action: ${escHtml(r.action)}</div>` : ''}
                <div class="reflection-meta">Trigger: ${escHtml(r.trigger)} &middot; ${formatTime(r.created_at)}</div>
            </div>
        `).join('');
    } else {
        c.innerHTML = '<div class="empty-state">No reflections yet. ROOT reflects periodically or when triggered.</div>';
    }
}

async function triggerReflection() {
    const btn = document.getElementById('btn-reflect');
    if (btn) { btn.disabled = true; btn.textContent = 'Reflecting...'; }
    await api('/api/dashboard/reflect', { method: 'POST' });
    await loadReflections();
    if (btn) { btn.disabled = false; btn.textContent = 'Trigger Reflection'; }
}

// ── Builder ─────────────────────────────────────────────────
async function loadBuilder() {
    const [status, history] = await Promise.all([api('/api/builder/status'), api('/api/builder/history?limit=20')]);
    const statsEl = document.getElementById('builder-stats');
    if (statsEl && status && !status.error) {
        statsEl.innerHTML = `
            <div class="stat-card"><div class="stat-value" style="color:var(--accent-cyan)">${status.total_tasks || 0}</div><div class="stat-label">Total Tasks</div></div>
            <div class="stat-card"><div class="stat-value" style="color:var(--accent-green)">${status.completed || 0}</div><div class="stat-label">Completed</div></div>
            <div class="stat-card"><div class="stat-value" style="color:var(--accent-gold)">${status.cycles || 0}</div><div class="stat-label">Cycles</div></div>`;
    }
    const historyEl = document.getElementById('builder-history');
    if (!historyEl) return;
    if (Array.isArray(history) && history.length) {
        historyEl.innerHTML = history.map(t => {
            const sColor = t.status === 'completed' ? 'var(--accent-green)' : t.status === 'failed' ? 'var(--accent-red)' : 'var(--accent-orange)';
            return `<div style="padding:10px 0;border-bottom:1px solid var(--border);font-size:12px">
                <div style="display:flex;justify-content:space-between;align-items:center">
                    <span style="font-weight:600;font-size:13px">${escHtml(t.type || t.task_type || 'task')}</span>
                    <span class="status-pill" style="background:${sColor}15;color:${sColor}">${t.status}</span>
                </div>
                <div style="color:var(--text-secondary);margin-top:4px">${escHtml(t.description)}</div>
                <div style="color:var(--text-muted);font-size:10px;margin-top:4px">${formatTime(t.completed_at || t.created_at)}</div>
            </div>`;
        }).join('');
    } else {
        historyEl.innerHTML = '<div class="empty-state">No build history yet.</div>';
    }
}

async function triggerBuild() {
    const btn = document.getElementById('btn-build');
    if (btn) { btn.disabled = true; btn.textContent = 'Building...'; }
    await api('/api/builder/run', { method: 'POST' });
    await loadBuilder();
    if (btn) { btn.disabled = false; btn.textContent = 'Run Build Cycle'; }
}

// ── Dashboard Extras ────────────────────────────────────────
async function loadDashboardDigests() {
    const digestsEl = document.getElementById('dashboard-digests');
    if (!digestsEl) return;
    digestsEl.innerHTML = '<div style="color:var(--text-muted);padding:8px">Loading digests...</div>';
    try {
        const data = await api('/api/autonomy/digests?limit=5');
        const digests = data?.digests || [];
        if (digests.length) {
            digestsEl.innerHTML = digests.map(d => `
                <div style="padding:8px 0;border-bottom:1px solid var(--border)">
                    <div style="display:flex;align-items:center;gap:8px;margin-bottom:3px">
                        <span style="font-size:11px;background:var(--accent-cyan)22;color:var(--accent-cyan);padding:2px 8px;border-radius:10px">${escHtml(d.type || 'daily')}</span>
                        <span style="font-size:13px;font-weight:500">${escHtml(d.title || 'Digest')}</span>
                        <span style="margin-left:auto;font-size:11px;color:var(--text-muted)">${formatTime(d.created_at)}</span>
                    </div>
                    ${d.highlights?.length ? `<div style="font-size:12px;color:var(--text-secondary)">${d.highlights.slice(0, 3).map(h => escHtml(h)).join(' · ')}</div>` : ''}
                </div>
            `).join('');
        } else {
            digestsEl.innerHTML = '<div style="color:var(--text-muted);padding:12px">No digests yet. <button class="btn-sm" onclick="generateAutonomyDigest()">Generate</button></div>';
        }
    } catch (e) {
        digestsEl.innerHTML = '<div style="color:var(--text-muted);padding:12px">Digests unavailable</div>';
    }
}

async function generateAutonomyDigest() {
    try {
        await api('/api/autonomy/digests/generate?digest_type=daily', { method: 'POST' });
        loadDashboardDigests();
    } catch (e) {
        console.error('Generate digest failed:', e);
    }
}

async function loadDashboardPatterns() {
    const patternsEl = document.getElementById('dashboard-patterns');
    if (!patternsEl) return;
    try {
        const data = await api('/api/autonomy/patterns');
        if (data && !data.error) {
            const topics = data.top_topics || [];
            const hours = data.active_hours || [];
            const recurring = data.recurring || [];
            patternsEl.innerHTML = `
                ${topics.length ? `<div style="margin-bottom:8px"><div style="font-size:12px;font-weight:600;margin-bottom:4px">Top Topics</div>
                    <div style="display:flex;flex-wrap:wrap;gap:4px">${topics.slice(0, 10).map(t => `<span style="background:var(--bg-elevated);padding:3px 8px;border-radius:12px;font-size:11px;color:var(--text-secondary)">${escHtml(typeof t === 'string' ? t : t.topic || t.name || '')}</span>`).join('')}</div>
                </div>` : ''}
                ${hours.length ? `<div style="margin-bottom:8px"><div style="font-size:12px;font-weight:600;margin-bottom:4px">Active Hours</div>
                    <div style="font-size:12px;color:var(--text-secondary)">${hours.join(', ')}</div>
                </div>` : ''}
                ${recurring.length ? `<div><div style="font-size:12px;font-weight:600;margin-bottom:4px">Recurring Patterns</div>
                    ${recurring.slice(0, 5).map(r => `<div style="font-size:12px;color:var(--text-secondary);padding:2px 0">${escHtml(typeof r === 'string' ? r : r.pattern || r.description || JSON.stringify(r).slice(0, 100))}</div>`).join('')}
                </div>` : ''}
                ${!topics.length && !hours.length && !recurring.length ? '<div style="color:var(--text-muted);padding:12px">Still learning your patterns...</div>' : ''}`;
        } else {
            patternsEl.innerHTML = '<div style="color:var(--text-muted);padding:12px">Pattern engine initializing...</div>';
        }
    } catch {
        patternsEl.innerHTML = '<div style="color:var(--text-muted);padding:12px">Patterns unavailable</div>';
    }
}

async function loadDashboardApprovals() {
    const appEl = document.getElementById('dashboard-approvals');
    if (!appEl) return;
    try {
        const data = await api('/api/autonomy/escalation');
        const decisions = (data?.recent_decisions || []).filter(d => !d.resolved && !d.auto_approved);
        if (decisions.length) {
            appEl.innerHTML = decisions.slice(0, 5).map(d => `
                <div style="padding:8px 0;border-bottom:1px solid var(--border)">
                    <div style="font-size:13px;font-weight:500">${escHtml(d.action || d.description || d.id || 'Pending decision')}</div>
                    <div style="font-size:11px;color:var(--text-muted);margin:4px 0">${formatTime(d.created_at || d.timestamp)}</div>
                    <div style="display:flex;gap:6px">
                        <button class="btn-sm" style="color:var(--accent-green)" onclick="recordEscalationOutcome('${escHtml(d.id || '')}', true)">Approve</button>
                        <button class="btn-sm" style="color:var(--accent-red)" onclick="recordEscalationOutcome('${escHtml(d.id || '')}', false)">Reject</button>
                    </div>
                </div>
            `).join('');
        } else {
            appEl.innerHTML = '<div style="color:var(--text-muted);padding:12px">No pending approvals</div>';
        }
    } catch {
        appEl.innerHTML = '<div style="color:var(--text-muted);padding:12px">Approval queue unavailable</div>';
    }
}

// ── Activity Timeline ───────────────────────────────────────
async function loadActivityTimeline() {
    const el = document.getElementById('dashboard-activity');
    if (!el) return;
    try {
        // Gather recent events from multiple sources in parallel
        const [escalation, directives, predictions, collab] = await Promise.all([
            api('/api/autonomy/escalation').catch(() => ({})),
            api('/api/autonomy/directives?limit=5').catch(() => ({})),
            api('/api/predictions?limit=5').catch(() => ({})),
            api('/api/autonomous/collab/history?limit=5').catch(() => ({})),
        ]);

        const events = [];

        // Escalation decisions
        (escalation?.recent_decisions || []).slice(0, 5).forEach(d => {
            events.push({
                time: d.created_at || d.timestamp || '',
                type: 'escalation',
                icon: '\u26A0',
                color: 'var(--accent-orange)',
                text: escHtml(d.action || d.description || 'Escalation decision'),
            });
        });

        // Directives
        const dirs = directives?.directives || directives?.data || [];
        (Array.isArray(dirs) ? dirs : []).slice(0, 5).forEach(d => {
            events.push({
                time: d.created_at || '',
                type: 'directive',
                icon: '\u2192',
                color: 'var(--accent-purple)',
                text: escHtml(d.title || 'Strategic directive'),
            });
        });

        // Predictions
        (predictions?.predictions || []).slice(0, 5).forEach(p => {
            const status = p.hit === 1 ? '\u2713' : p.hit === 0 ? '\u2717' : '\u22EF';
            events.push({
                time: p.created_at || '',
                type: 'prediction',
                icon: status,
                color: p.hit === 1 ? 'var(--accent-green)' : p.hit === 0 ? 'var(--accent-red)' : 'var(--accent-blue)',
                text: `${escHtml(p.source || '')} ${escHtml(p.symbol || '')} ${escHtml(p.direction || '')}`,
            });
        });

        // Collaborations
        const collabList = collab?.data ?? collab ?? [];
        (Array.isArray(collabList) ? collabList : []).slice(0, 5).forEach(c => {
            events.push({
                time: c.created_at || c.timestamp || '',
                type: 'collab',
                icon: '\u21C4',
                color: 'var(--accent-cyan)',
                text: escHtml((c.task || c.topic || c.description || 'Agent collaboration').slice(0, 60)),
            });
        });

        // Sort by time descending
        events.sort((a, b) => (b.time || '').localeCompare(a.time || ''));

        if (events.length) {
            el.innerHTML = events.slice(0, 15).map(e => `
                <div style="display:flex;gap:8px;padding:6px 0;border-bottom:1px solid var(--border);font-size:12px;align-items:flex-start">
                    <span style="color:${e.color};font-size:14px;flex-shrink:0;width:18px;text-align:center">${e.icon}</span>
                    <div style="flex:1">
                        <span style="color:var(--text-primary)">${e.text}</span>
                        <span style="font-size:10px;padding:1px 5px;border-radius:3px;background:var(--bg-elevated);color:${e.color};margin-left:6px">${e.type}</span>
                    </div>
                    <span style="font-size:10px;color:var(--text-muted);flex-shrink:0">${formatTime(e.time)}</span>
                </div>
            `).join('');
        } else {
            el.innerHTML = '<div style="color:var(--text-muted);padding:12px;text-align:center">No recent activity</div>';
        }
    } catch {
        el.innerHTML = '<div style="color:var(--text-muted);padding:12px">Activity timeline unavailable</div>';
    }
}

// ── Live Activity Feed ─────────────────────────────────────
async function loadActivityFeed() {
    const el = document.getElementById('activity-feed-list');
    if (!el) return;

    const [outcomes, directives, proactive] = await Promise.all([
        api('/api/agi/outcomes?limit=5').catch(() => ({data:[]})),
        api('/api/autonomy/directives?limit=5').catch(() => ({data:[]})),
        api('/api/autonomous/proactive/stats').catch(() => ({})),
    ]);

    const items = [];

    // Add outcomes
    const outcomeList = outcomes?.data || outcomes || [];
    if (Array.isArray(outcomeList)) {
        for (const o of outcomeList.slice(0, 5)) {
            items.push({
                time: o.created_at || '',
                type: 'outcome',
                icon: o.quality_score >= 0.5 ? '✅' : '⚠️',
                text: `[${o.action_type}] ${o.intent?.substring(0, 80) || ''}`,
                quality: o.quality_score,
            });
        }
    }

    // Add directives
    const dirList = directives?.data?.directives || directives?.data || [];
    if (Array.isArray(dirList)) {
        for (const d of dirList.slice(0, 5)) {
            items.push({
                time: d.created_at || '',
                type: 'directive',
                icon: d.status === 'completed' ? '⚡' : '🔄',
                text: `[${d.category}] ${d.title?.substring(0, 80) || ''}`,
                quality: d.status === 'completed' ? 0.8 : 0.5,
            });
        }
    }

    // Sort by time descending
    items.sort((a, b) => (b.time || '').localeCompare(a.time || ''));

    if (!items.length) {
        el.innerHTML = '<div style="color:var(--text-muted);padding:12px">No recent activity — autonomous loops are warming up...</div>';
        return;
    }

    el.innerHTML = items.slice(0, 10).map(i => `
        <div style="display:flex;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid var(--border)">
            <span style="font-size:14px">${i.icon}</span>
            <div style="flex:1;min-width:0">
                <div style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${escHtml(i.text)}</div>
                <div style="color:var(--text-muted);font-size:10px">${i.time ? new Date(i.time).toLocaleString() : ''}</div>
            </div>
            <div style="font-size:11px;padding:2px 6px;border-radius:4px;background:${i.quality >= 0.7 ? 'var(--accent-green)' : i.quality >= 0.4 ? 'var(--accent)' : 'var(--accent-red)'};color:#000;font-weight:600">${(i.quality * 100).toFixed(0)}%</div>
        </div>
    `).join('');
}

// ── AGI Status Card ────────────────────────────────────────
async function loadDashboardAGIStatus() {
    const el = document.getElementById('dashboard-agi-status');
    if (!el) return;
    el.innerHTML = '<div style="color:var(--text-muted);padding:8px">Loading AGI systems...</div>';
    try {
        const raw = await api('/api/agi/status');
        const data = raw?.data ?? raw;
        if (!data || data.error) {
            el.innerHTML = '<div style="color:var(--text-muted);padding:12px">AGI systems unavailable</div>';
            return;
        }

        const outcomeCount = data.outcome_registry?.total_outcomes || data.outcome_registry?.total || 0;
        const configParams = data.adaptive_config && !data.adaptive_config.error
            ? Object.keys(data.adaptive_config).length : 0;
        const skillCount = data.skill_executor?.total || data.skill_executor?.executable_count || 0;
        const embeddingCount = data.embedding_service?.cached || data.embedding_service?.total_embeddings || 0;

        const emergencyData = data.emergency_protocol || {};
        const emergencyActive = emergencyData.active || emergencyData.triggered || false;
        const emergencyColor = emergencyData.error ? 'var(--text-muted)' :
            emergencyActive ? 'var(--accent-red)' : 'var(--accent-green)';
        const emergencyLabel = emergencyData.error ? 'N/A' :
            emergencyActive ? 'ACTIVE' : 'Clear';

        const planningActive = data.planning_engine?.active || false;
        const teamStats = data.team_formation || {};
        const conflictStats = data.conflict_detector || {};

        el.innerHTML = `
            <div class="grid-3" style="gap:8px;margin-bottom:10px">
                <div style="padding:8px;background:var(--bg-elevated);border-radius:6px;text-align:center">
                    <div style="font-size:16px;font-weight:700;color:var(--accent-cyan)">${outcomeCount}</div>
                    <div style="font-size:10px;color:var(--text-muted)">Outcomes</div>
                </div>
                <div style="padding:8px;background:var(--bg-elevated);border-radius:6px;text-align:center">
                    <div style="font-size:16px;font-weight:700;color:var(--accent-purple)">${configParams}</div>
                    <div style="font-size:10px;color:var(--text-muted)">Adaptive Params</div>
                </div>
                <div style="padding:8px;background:var(--bg-elevated);border-radius:6px;text-align:center">
                    <div style="font-size:16px;font-weight:700;color:var(--accent-gold)">${skillCount}</div>
                    <div style="font-size:10px;color:var(--text-muted)">Exec Skills</div>
                </div>
            </div>
            <div class="grid-3" style="gap:8px">
                <div style="padding:8px;background:var(--bg-elevated);border-radius:6px;text-align:center">
                    <div style="font-size:16px;font-weight:700;color:var(--accent-blue)">${embeddingCount}</div>
                    <div style="font-size:10px;color:var(--text-muted)">Embeddings</div>
                </div>
                <div style="padding:8px;background:var(--bg-elevated);border-radius:6px;text-align:center">
                    <div style="font-size:16px;font-weight:700;color:${emergencyColor}">${emergencyLabel}</div>
                    <div style="font-size:10px;color:var(--text-muted)">Emergency</div>
                </div>
                <div style="padding:8px;background:var(--bg-elevated);border-radius:6px;text-align:center">
                    <div style="font-size:16px;font-weight:700;color:${planningActive ? 'var(--accent-green)' : 'var(--text-muted)'}">${planningActive ? 'Online' : 'Idle'}</div>
                    <div style="font-size:10px;color:var(--text-muted)">Planner</div>
                </div>
            </div>
            ${teamStats && !teamStats.error ? `<div style="font-size:11px;color:var(--text-muted);margin-top:8px">Teams: ${teamStats.total_formed || teamStats.total || 0} formed &middot; Conflicts: ${conflictStats.total_detected || conflictStats.total || 0} detected</div>` : ''}`;
    } catch {
        el.innerHTML = '<div style="color:var(--text-muted);padding:12px">AGI status unavailable</div>';
    }
}

// ── Perpetual Intelligence + Swarm + Research ──────────────
async function loadPerpetualStatus() {
    const el = document.getElementById('perpetual-content');
    if (!el) return;
    const data = await api('/api/perpetual/status').catch(() => null);
    if (!data?.data) { el.innerHTML = '<div style="color:var(--text-muted)">Initializing...</div>'; return; }
    const p = data.data.perpetual || {};
    const s = data.data.swarm || {};
    el.innerHTML = `
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px">
            <div class="stat-card"><div class="stat-value" style="color:var(--accent)">${p.cycles || 0}</div><div class="stat-label">Cycles</div></div>
            <div class="stat-card"><div class="stat-value" style="color:var(--accent-green)">${p.research_findings || 0}</div><div class="stat-label">Research</div></div>
            <div class="stat-card"><div class="stat-value" style="color:var(--accent-blue)">${p.analysis_insights || 0}</div><div class="stat-label">Analysis</div></div>
            <div class="stat-card"><div class="stat-value" style="color:var(--accent-purple)">${p.trades_evaluated || 0}</div><div class="stat-label">Trades</div></div>
        </div>
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:8px">
            <div class="stat-card"><div class="stat-value" style="color:var(--accent-gold)">${p.code_reviews || 0}</div><div class="stat-label">Code Reviews</div></div>
            <div class="stat-card"><div class="stat-value" style="color:var(--accent-cyan)">${p.vision_plans || 0}</div><div class="stat-label">Vision Plans</div></div>
            <div class="stat-card"><div class="stat-value" style="color:var(--accent-red)">${p.running ? 'ACTIVE' : 'OFF'}</div><div class="stat-label">Status</div></div>
        </div>`;
}

async function loadSwarmStatus() {
    const el = document.getElementById('swarm-content');
    if (!el) return;
    const data = await api('/api/perpetual/swarm/status').catch(() => null);
    if (!data?.data || data.data.error) { el.innerHTML = '<div style="color:var(--text-muted)">Initializing...</div>'; return; }
    const s = data.data;
    el.innerHTML = `
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px">
            <div class="stat-card"><div class="stat-value" style="color:var(--accent)">${s.total_dispatches || 0}</div><div class="stat-label">Tasks Dispatched</div></div>
            <div class="stat-card"><div class="stat-value" style="color:var(--accent-green)">${s.divisions_activated || 0}</div><div class="stat-label">Divisions Active</div></div>
            <div class="stat-card"><div class="stat-value" style="color:var(--accent-purple)">${s.cross_pollinations || 0}</div><div class="stat-label">Cross-Pollinations</div></div>
        </div>`;
}

async function loadResearchFeed() {
    const el = document.getElementById('research-feed-content');
    if (!el) return;
    const data = await api('/api/perpetual/research').catch(() => null);
    if (!data?.data || !data.data.length) { el.innerHTML = '<div style="color:var(--text-muted)">Gathering intelligence...</div>'; return; }
    el.innerHTML = data.data.slice(0, 10).map(r => `
        <div style="padding:8px 0;border-bottom:1px solid var(--border)">
            <div style="display:flex;justify-content:space-between;align-items:start">
                <div style="flex:1;min-width:0">
                    <div style="font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${escHtml(r.content)}</div>
                    <div style="font-size:10px;color:var(--text-muted);margin-top:2px">${r.tags?.join(', ') || ''}</div>
                </div>
                <span style="font-size:10px;padding:2px 6px;border-radius:3px;background:var(--accent-green);color:#000;font-weight:600;white-space:nowrap">${(r.confidence * 100).toFixed(0)}%</span>
            </div>
        </div>
    `).join('');
}

// ── Settings Import/Export ───────────────────────────────────
async function exportSettings() {
    try {
        const data = await api('/api/settings');
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'root-settings-' + new Date().toISOString().slice(0, 10) + '.json';
        a.click();
        URL.revokeObjectURL(url);
    } catch (e) {
        alert('Export failed: ' + (e.message || e));
    }
}

function importSettings() {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.json';
    input.onchange = async (e) => {
        const file = e.target.files?.[0];
        if (!file) return;
        try {
            const text = await file.text();
            const settings = JSON.parse(text);
            if (!settings || typeof settings !== 'object') { alert('Invalid settings file'); return; }
            showConfirmModal({
                title: 'Import Settings',
                message: `Import ${Object.keys(settings).length} settings groups from ${file.name}? This will overwrite current settings.`,
                danger: true,
                confirmLabel: 'Import',
                onConfirm: async () => {
                    // Apply each group
                    const groups = settings.groups || settings;
                    for (const [group, values] of Object.entries(groups)) {
                        if (typeof values === 'object') {
                            await api(`/api/settings/${group}`, { method: 'PATCH', body: values }).catch(() => {});
                        }
                    }
                    closeModal();
                    loadSettings();
                },
            });
        } catch (err) {
            alert('Invalid JSON file: ' + (err.message || err));
        }
    };
    input.click();
}

// ── Sandbox Gate Panel ──────────────────────────────────────

const SANDBOX_SYSTEMS = ['trading', 'notifications', 'code_deploy', 'revenue', 'agents_external', 'proactive', 'plugins', 'file_system'];

async function loadSandbox() {
    const [status, categories, pending, blocked] = await Promise.all([
        api('/api/sandbox/status'),
        api('/api/sandbox/categories'),
        api('/api/sandbox/pending-approvals'),
        api('/api/sandbox/blocked-intents?limit=30'),
    ]);

    // Global mode
    const mode = status?.global_mode || 'sandbox';
    const indicator = document.getElementById('sandbox-mode-indicator');
    const btn = document.getElementById('btn-toggle-mode');
    if (indicator) {
        indicator.textContent = mode.toUpperCase();
        indicator.className = 'sandbox-mode-display ' + mode;
    }
    if (btn) {
        btn.textContent = mode === 'sandbox' ? 'Switch to LIVE' : 'Switch to SANDBOX';
    }
    const updatedAt = document.getElementById('sandbox-updated-at');
    if (updatedAt && status?.updated_at) {
        updatedAt.textContent = 'Updated: ' + new Date(status.updated_at).toLocaleString();
    }

    // Stats
    const stats = status?.stats || {};
    setVal('sandbox-total-decisions', stats.total || 0);
    setVal('sandbox-blocked', stats.sandbox || 0);
    setVal('sandbox-executed', stats.live || 0);

    // Pending count
    const pendingCount = pending?.count || 0;
    setVal('sandbox-pending-count', pendingCount);

    // Subsystem overrides
    const systemsEl = document.getElementById('sandbox-systems-list');
    if (systemsEl) {
        const overrides = status?.system_overrides || {};
        systemsEl.innerHTML = SANDBOX_SYSTEMS.map(sys => {
            const effective = overrides[sys] || mode;
            const isLive = effective === 'live';
            return `<div style="display:flex;align-items:center;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--border)">
                <div>
                    <span style="font-size:13px;font-weight:500">${escHtml(sys)}</span>
                    <span class="sandbox-mode-pill ${effective}" style="margin-left:8px">${effective.toUpperCase()}</span>
                </div>
                <div style="display:flex;gap:6px">
                    <button class="btn-tiny ${!isLive ? 'active' : ''}" onclick="setSandboxSystem('${sys}','sandbox')">Sandbox</button>
                    <button class="btn-tiny ${isLive ? 'active' : ''}" onclick="setSandboxSystem('${sys}','live')">Live</button>
                </div>
            </div>`;
        }).join('');
    }

    // Pending approvals
    const pendingEl = document.getElementById('sandbox-pending-list');
    if (pendingEl) {
        const items = pending?.pending || [];
        if (items.length === 0) {
            pendingEl.innerHTML = '<div style="padding:16px;text-align:center;color:var(--text-muted);font-size:12px">No pending approvals</div>';
        } else {
            pendingEl.innerHTML = items.map(r => `
                <div class="sandbox-approval-card">
                    <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:6px">
                        <div>
                            <span style="font-weight:600;color:var(--text-primary)">${escHtml(r.action)}</span>
                            <span class="sandbox-risk-pill ${r.risk_level}">${escHtml(r.risk_level)}</span>
                        </div>
                        <span style="font-size:10px;color:var(--text-muted)">${escHtml(r.agent_id)}</span>
                    </div>
                    <div style="font-size:12px;color:var(--text-secondary);margin-bottom:6px">${escHtml(r.description)}</div>
                    ${r.reason ? `<div style="font-size:11px;color:var(--text-muted)"><strong>Reason:</strong> ${escHtml(r.reason)}</div>` : ''}
                    ${r.risk_analysis ? `<div style="font-size:11px;color:var(--text-muted)"><strong>Risk:</strong> ${escHtml(r.risk_analysis)}</div>` : ''}
                    <div style="display:flex;gap:8px;margin-top:8px">
                        <button class="btn-approve" onclick="approveSandboxRequest('${escHtml(r.id)}')">Approve</button>
                        <button class="btn-reject" onclick="rejectSandboxRequest('${escHtml(r.id)}')">Reject</button>
                    </div>
                </div>
            `).join('');
        }
    }

    // Categories
    const catsEl = document.getElementById('sandbox-categories-list');
    if (catsEl && categories?.categories) {
        const cats = categories.categories;
        catsEl.innerHTML = Object.entries(cats).map(([name, policy]) => {
            const levelColor = {critical: 'var(--accent-red)', high: 'var(--accent-orange)', medium: 'var(--accent-gold)', low: 'var(--accent-blue)', none: 'var(--text-muted)'}[policy.notification_level] || 'var(--text-muted)';
            return `<div style="display:flex;align-items:center;justify-content:space-between;padding:7px 0;border-bottom:1px solid var(--border);font-size:12px">
                <span style="font-weight:600;text-transform:uppercase;letter-spacing:0.5px">${escHtml(name)}</span>
                <div style="display:flex;gap:12px;align-items:center">
                    <span style="color:${levelColor};font-size:11px">${escHtml(policy.notification_level)}</span>
                    <span style="color:${policy.requires_approval ? 'var(--accent-red)' : 'var(--accent-green)'};font-size:11px;font-weight:500">${policy.requires_approval ? 'APPROVAL' : 'AUTO'}</span>
                </div>
            </div>`;
        }).join('');
    }

    // Blocked intents
    const blockedEl = document.getElementById('sandbox-blocked-list');
    if (blockedEl) {
        const items = blocked?.blocked_intents || [];
        if (items.length === 0) {
            blockedEl.innerHTML = '<div style="padding:16px;text-align:center;color:var(--text-muted);font-size:12px">No blocked intents yet</div>';
        } else {
            blockedEl.innerHTML = items.slice(0, 20).map(d => `
                <div style="padding:8px 0;border-bottom:1px solid var(--border);font-size:12px">
                    <div style="display:flex;justify-content:space-between">
                        <span style="font-weight:500;color:var(--accent-gold)">${escHtml(d.action || 'unknown')}</span>
                        <span style="color:var(--text-muted);font-size:10px">${d.timestamp ? new Date(d.timestamp).toLocaleString() : ''}</span>
                    </div>
                    <div style="color:var(--text-secondary);margin-top:2px">${escHtml(d.description || '')}</div>
                    <div style="color:var(--text-muted);font-size:11px;margin-top:2px">Agent: ${escHtml(d.agent_id || '?')} · System: ${escHtml(d.system_id || '?')}</div>
                </div>
            `).join('');
        }
    }
}

function setVal(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
}

async function toggleSandboxMode() {
    const indicator = document.getElementById('sandbox-mode-indicator');
    const currentMode = indicator?.textContent?.toLowerCase() || 'sandbox';

    if (currentMode === 'sandbox') {
        // Switching to LIVE — show confirmation
        showConfirmModal({
            title: 'Switch to LIVE Mode',
            message: 'WARNING: This gives ROOT autonomous access to external systems. FINANCIAL, COMMUNICATION, and DEPLOYMENT actions will still require your approval. Are you sure?',
            danger: true,
            confirmLabel: 'Go LIVE',
            onConfirm: async () => {
                await api('/api/sandbox/go-live', { method: 'POST', body: { confirm: true } });
                closeModal();
                updateSandboxBadge();
                loadSandbox();
            },
        });
    } else {
        await api('/api/sandbox/mode', { method: 'PATCH', body: { mode: 'sandbox' } });
        updateSandboxBadge();
        loadSandbox();
    }
}

async function setSandboxSystem(systemId, mode) {
    await api('/api/sandbox/system/' + systemId, { method: 'PATCH', body: { mode } });
    loadSandbox();
}

async function approveSandboxRequest(approvalId) {
    await api('/api/sandbox/approve/' + approvalId, { method: 'POST' });
    loadSandbox();
    pushActivity('Approval', 'Request approved: ' + approvalId.slice(0, 12), 'sandbox', 'guardian');
    // After successful approval, dismiss all approval toasts
    document.querySelectorAll('.toast--warning').forEach(t => {
        t.classList.remove('toast--visible');
        t.classList.add('toast--exit');
        setTimeout(() => { if (t.parentNode) t.parentNode.removeChild(t); }, 300);
    });
}

async function rejectSandboxRequest(approvalId) {
    await api('/api/sandbox/reject/' + approvalId, { method: 'POST' });
    loadSandbox();
    pushActivity('Rejection', 'Request rejected: ' + approvalId.slice(0, 12), 'sandbox', 'guardian');
    // After successful rejection, dismiss all approval toasts
    document.querySelectorAll('.toast--warning').forEach(t => {
        t.classList.remove('toast--visible');
        t.classList.add('toast--exit');
        setTimeout(() => { if (t.parentNode) t.parentNode.removeChild(t); }, 300);
    });
}
