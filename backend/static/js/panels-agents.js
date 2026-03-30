/* panels-agents.js — Agents, Plugins, Skills, Civilization, Network */

// ── Skills ──────────────────────────────────────────────────
async function loadSkills() {
    const data = await api('/api/dashboard/skills');
    const container = document.getElementById('skills-list');
    if (!container) return;
    if (data.error) { container.innerHTML = `<div class="empty-state" style="color:var(--accent-red)">Error: ${escHtml(data.error)}</div>`; return; }
    const cats = Object.entries(data);
    if (!cats.length) { container.innerHTML = '<div class="empty-state">No skills loaded.</div>'; return; }
    const totalSkills = cats.reduce((sum, [, skills]) => sum + skills.length, 0);
    const subEl = document.getElementById('skills-subtitle');
    if (subEl) subEl.textContent = `${totalSkills} skills across ${cats.length} categories`;
    container.innerHTML = cats.map(([cat, skills]) => `
        <div class="card">
            <div class="card-title">${escHtml(cat)} <span style="font-weight:400;color:var(--text-muted)">(${skills.length})</span></div>
            ${skills.map(s => `
                <div style="padding:8px 0;border-bottom:1px solid var(--border)">
                    <div style="display:flex;align-items:center;gap:8px">
                        <span style="font-weight:600;font-size:13px">${escHtml(s.name)}</span>
                        <span style="font-size:10px;color:var(--text-muted);background:var(--bg-hover);padding:1px 6px;border-radius:3px">v${escHtml(s.version)}</span>
                    </div>
                    <div style="font-size:12px;color:var(--text-secondary);margin-top:3px">${escHtml(s.description)}</div>
                </div>
            `).join('')}
        </div>
    `).join('');
}

// ── Agents ──────────────────────────────────────────────────
let _agentViewMode = 'core';

async function loadAgents() {
    const [raw, divisions] = await Promise.all([
        api('/api/agents'),
        api('/api/civilization/agents/divisions'),
    ]);
    const agents = raw?.data ?? raw;
    const subEl = document.getElementById('agents-subtitle');
    const totalCiv = divisions?.total_agents || 0;
    const totalCore = Array.isArray(agents) ? agents.length : 0;
    if (subEl) subEl.textContent = `${totalCore + totalCiv} agents total — ${totalCore} core + ${totalCiv} civilization`;

    const statsEl = document.getElementById('agents-stats');
    if (statsEl) {
        const online = Array.isArray(agents) ? agents.filter(a => ['online','available','internal'].includes(a.health?.status)).length : 0;
        const divCount = Object.keys(divisions?.divisions || {}).length;
        statsEl.innerHTML = `
            <div class="stat-card"><div class="stat-value" style="color:var(--accent)">${totalCore}</div><div class="stat-label">Core Agents</div></div>
            <div class="stat-card"><div class="stat-value" style="color:var(--accent-blue)">${totalCiv}</div><div class="stat-label">Civilization</div></div>
            <div class="stat-card"><div class="stat-value" style="color:var(--accent-green)">${online}</div><div class="stat-label">Online</div></div>
            <div class="stat-card"><div class="stat-value" style="color:var(--accent-purple)">${divCount}</div><div class="stat-label">Divisions</div></div>`;
    }

    const container = document.getElementById('agents-list');
    if (container && Array.isArray(agents)) {
        container.innerHTML = agents.map(a => {
            const h = a.health?.status || 'unknown';
            const color = AGENT_COLORS[a.id] || 'var(--accent)';
            const isAstra = a.id === 'astra';
            const isMiro = a.id === 'miro';
            const isCustom = a.metadata?.custom;
            const badge = isAstra ? '<span style="font-size:10px;color:var(--accent-green);font-weight:600">TEAM LEAD</span>' :
                          isMiro ? '<span style="font-size:10px;color:var(--accent-gold);font-weight:600">POTENTIALITY</span>' :
                          isCustom ? '<span style="font-size:10px;color:var(--accent-cyan);font-weight:600">CUSTOM</span>' : '';
            return `<div class="agent-card" style="cursor:pointer" onclick="showAgentDetail('${escHtml(a.id)}')">
                <div style="display:flex;justify-content:space-between;align-items:start">
                    <div style="display:flex;align-items:center;gap:10px">
                        <div class="agent-avatar" style="background:${color}">${a.name[0]}</div>
                        <div>
                            <div class="agent-name">${escHtml(a.name)} ${badge}</div>
                            <div class="agent-role">${escHtml(a.role)} &middot; Tier ${a.tier} &middot; ${a.tasks_completed} tasks</div>
                        </div>
                    </div>
                    <div style="display:flex;align-items:center;gap:6px">
                        <span class="status-pill ${h}">${escHtml(h)}</span>
                        ${isCustom ? `<button class="btn-sm" onclick="event.stopPropagation();deleteCustomAgent('${escHtml(a.id)}')" style="color:var(--accent-red)" title="Delete">✕</button>` : ''}
                    </div>
                </div>
                <p style="font-size:12px;color:var(--text-secondary);margin:10px 0">${escHtml(a.description)}</p>
                <div class="agent-caps">${a.capabilities.map(c => `<span class="cap-tag" title="${escHtml(c.description)}">${escHtml(c.name)}</span>`).join('')}</div>
            </div>`;
        }).join('');
    }

    const civEl = document.getElementById('agents-civilization');
    if (civEl && divisions?.divisions) {
        const divColors = [
            'var(--accent)', 'var(--accent-blue)', 'var(--accent-cyan)',
            'var(--accent-purple)', 'var(--accent-green)', 'var(--accent-gold)',
            'var(--accent-orange)', 'var(--accent-pink)', '#a87bd4', 'var(--accent-red)',
        ];
        civEl.innerHTML = Object.entries(divisions.divisions).map(([name, agts], i) => {
            const color = divColors[i % divColors.length];
            const agentList = Array.isArray(agts) ? agts : [];
            return `<div class="card" style="margin-bottom:12px">
                <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">
                    <div style="width:10px;height:10px;border-radius:50%;background:${color}"></div>
                    <div class="card-title" style="margin:0">${escHtml(name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()))}</div>
                    <span style="margin-left:auto;font-size:11px;color:${color};font-weight:600">${agentList.length} agents</span>
                </div>
                <div class="agent-caps">
                    ${agentList.map(a => {
                        const n = typeof a === 'string' ? a : (a.name || a.id || '');
                        const desc = typeof a === 'object' ? (a.role || a.description || '') : '';
                        return `<span class="cap-tag" style="border-color:${color}40" title="${escHtml(desc)}">${escHtml(n)}</span>`;
                    }).join('')}
                </div>
            </div>`;
        }).join('');
    }

    switchAgentView(_agentViewMode);
}

function showCreateAgentModal() {
    showModal({
        title: 'Create Custom Agent',
        fields: [
            { key: 'name', label: 'Agent Name', type: 'text', placeholder: 'e.g. DataMiner', required: true },
            { key: 'role', label: 'Role', type: 'text', placeholder: 'e.g. Data Collection Specialist', required: true },
            { key: 'description', label: 'Description', type: 'textarea', placeholder: 'What does this agent do?' },
            { key: 'tier', label: 'Tier (1=Authority, 2=Worker)', type: 'select', options: [{value: '2', label: 'Worker (Tier 2)'}, {value: '1', label: 'Authority (Tier 1)'}] },
            { key: 'capabilities', label: 'Capabilities (comma-separated)', type: 'text', placeholder: 'data_analysis, web_search' },
        ],
        submitLabel: 'Create Agent',
        onSubmit: async (vals) => {
            const caps = vals.capabilities ? vals.capabilities.split(',').map(c => c.trim()).filter(Boolean).map(c => ({ name: c, description: c })) : [];
            await api('/api/agents/custom', {
                method: 'POST',
                body: {
                    name: vals.name,
                    role: vals.role,
                    description: vals.description || '',
                    tier: parseInt(vals.tier) || 2,
                    capabilities: caps,
                },
            });
            closeModal();
            loadAgents();
        },
    });
}

async function deleteCustomAgent(agentId) {
    showConfirmModal({
        title: 'Delete Custom Agent',
        message: `Remove agent "${agentId}"? Only custom agents can be deleted.`,
        danger: true,
        onConfirm: async () => {
            await api(`/api/agents/custom/${agentId}`, { method: 'DELETE' });
            loadAgents();
        },
    });
}

function switchAgentView(view) {
    _agentViewMode = view;
    const coreEl = document.getElementById('agents-list');
    const civEl = document.getElementById('agents-civilization');
    const coreBtn = document.getElementById('view-core');
    const civBtn = document.getElementById('view-civilization');
    if (view === 'core') {
        if (coreEl) coreEl.style.display = '';
        if (civEl) civEl.style.display = 'none';
        if (coreBtn) coreBtn.classList.add('active');
        if (civBtn) civBtn.classList.remove('active');
    } else {
        if (coreEl) coreEl.style.display = 'none';
        if (civEl) civEl.style.display = '';
        if (coreBtn) coreBtn.classList.remove('active');
        if (civBtn) civBtn.classList.add('active');
    }
}

// ── Plugins ─────────────────────────────────────────────────
async function loadPlugins() {
    const [plugins, stats] = await Promise.all([api('/api/plugins'), api('/api/plugins/stats')]);
    const statsEl = document.getElementById('plugins-stats');
    if (statsEl && stats && !stats.error) {
        statsEl.innerHTML = `
            <div class="stat-card"><div class="stat-value" style="color:var(--accent-cyan)">${stats.total_plugins || 0}</div><div class="stat-label">Plugins</div></div>
            <div class="stat-card"><div class="stat-value" style="color:var(--accent-green)">${stats.total_tools || 0}</div><div class="stat-label">Tools</div></div>
            <div class="stat-card"><div class="stat-value" style="color:var(--accent-gold)">${stats.total_invocations || 0}</div><div class="stat-label">Invocations</div></div>`;
    }

    // Store plugins for tool testing
    window._pluginData = plugins;

    const listEl = document.getElementById('plugins-list');
    if (!listEl) return;
    if (!Array.isArray(plugins) || !plugins.length) { listEl.innerHTML = '<div class="empty-state">No plugins loaded.</div>'; return; }
    listEl.innerHTML = plugins.map(p => {
        const isActive = p.status === 'active';
        return `<div class="agent-card" style="margin-bottom:10px">
            <div style="display:flex;justify-content:space-between;align-items:start">
                <div><div class="agent-name">${escHtml(p.name)}</div><div class="agent-role">${escHtml(p.category || 'general')} &middot; v${p.version || '1.0'}</div></div>
                <div style="display:flex;align-items:center;gap:8px">
                    <span class="status-pill ${isActive ? 'online' : 'offline'}">${escHtml(p.status)}</span>
                    <button class="btn-secondary" style="padding:4px 10px;font-size:11px" onclick="togglePlugin('${escHtml(p.id)}','${escHtml(p.status)}')">${isActive ? 'Disable' : 'Enable'}</button>
                </div>
            </div>
            <p style="font-size:12px;color:var(--text-secondary);margin:10px 0">${escHtml(p.description)}</p>
            <div class="agent-caps">${(p.tools || []).map(t => `<span class="cap-tag" title="${escHtml(t.description)}">${escHtml(t.name)}</span>`).join('')}</div>
        </div>`;
    }).join('');
}

async function togglePlugin(pluginId, currentStatus) {
    const action = currentStatus === 'active' ? 'disable' : 'enable';
    await api(`/api/plugins/${pluginId}/${action}`, { method: 'POST' });
    loadPlugins();
}

function showToolTestModal() {
    const plugins = window._pluginData || [];
    const allTools = [];
    plugins.forEach(p => {
        (p.tools || []).forEach(t => {
            allTools.push({ value: t.name, label: `${t.name} (${p.name})` });
        });
    });
    if (!allTools.length) {
        alert('No tools available. Load plugins first.');
        return;
    }
    showModal({
        title: 'Test Plugin Tool',
        fields: [
            { key: 'tool_name', label: 'Tool', type: 'select', options: allTools, required: true },
            { key: 'args', label: 'Arguments (JSON)', type: 'textarea', placeholder: '{"key": "value"}', value: '{}' },
        ],
        submitLabel: 'Invoke',
        onSubmit: async (vals) => {
            let args = {};
            try { args = JSON.parse(vals.args || '{}'); } catch (e) { alert('Invalid JSON'); return; }
            closeModal();
            const resultEl = document.getElementById('plugin-tool-result');
            if (resultEl) resultEl.innerHTML = '<div style="padding:12px;color:var(--accent)">Invoking...</div>';
            try {
                const result = await api('/api/plugins/invoke', {
                    method: 'POST',
                    body: { tool_name: vals.tool_name, args },
                });
                if (resultEl) {
                    resultEl.innerHTML = `<div class="card" style="margin-bottom:12px">
                        <div class="card-title" style="display:flex;justify-content:space-between">
                            <span>Tool Result: ${escHtml(vals.tool_name)}</span>
                            <button class="btn-sm" onclick="document.getElementById('plugin-tool-result').innerHTML=''">✕</button>
                        </div>
                        <pre style="font-size:12px;color:var(--text-secondary);white-space:pre-wrap;word-break:break-word;max-height:300px;overflow:auto">${escHtml(JSON.stringify(result, null, 2))}</pre>
                    </div>`;
                }
            } catch (e) {
                if (resultEl) resultEl.innerHTML = `<div class="card" style="border-color:var(--accent-red);margin-bottom:12px"><div style="color:var(--accent-red);padding:8px">${escHtml(e.message)}</div></div>`;
            }
        },
    });
}

async function showPluginLogs() {
    const logs = await api('/api/plugins/log');
    const logData = Array.isArray(logs) ? logs : (logs?.data || logs?.logs || []);
    showDetailModal({
        title: 'Plugin Invocation Logs',
        content: logData.length ? `<div class="table-wrap" style="max-height:400px;overflow:auto"><table><thead><tr>
            <th>Tool</th><th>Status</th><th>Time</th><th>Duration</th>
            </tr></thead><tbody>` +
            logData.slice(0, 50).map(l => `<tr>
                <td>${escHtml(l.tool_name || l.tool || '')}</td>
                <td style="color:${l.status === 'success' ? 'var(--accent-green)' : 'var(--accent-red)'}">${escHtml(l.status || '')}</td>
                <td>${formatTime(l.timestamp || l.created_at)}</td>
                <td>${l.duration_ms ? l.duration_ms + 'ms' : '\u2014'}</td>
            </tr>`).join('') + '</tbody></table></div>' :
            '<div class="empty-state">No plugin logs yet</div>',
    });
}

// ── Civilization Panel ───────────────────────────────────────
async function loadCivilization() {
    const [divisions, civStatus, expStats, expLabStats, revenueSnap, experiments, codeProposals, dashStatus] = await Promise.all([
        api('/api/civilization/agents/divisions'),
        api('/api/civilization/status'),
        api('/api/civilization/experience/stats'),
        api('/api/civilization/experiments/stats'),
        api('/api/civilization/revenue/snapshot'),
        api('/api/civilization/experiments?limit=10'),
        api('/api/civilization/code-proposals?limit=10'),
        api('/api/dashboard/status').catch(() => ({})),
    ]);

    const divData = divisions?.divisions || {};
    const cs = civStatus?.civilization || civStatus || {};
    const exp = expStats?.data ?? expStats ?? {};
    const exl = expLabStats?.data ?? expLabStats ?? {};
    const rev = revenueSnap?.data ?? revenueSnap ?? {};

    // Stats cards
    _setText('civ-total-agents', cs.total_agents || divisions?.total_agents || 0);
    _setText('civ-total-divisions', cs.total_divisions || Object.keys(divData).length || 0);
    _setText('civ-experiences', exp.total || 0);
    _setText('civ-experiments', exl.total || 0);
    const monthly = rev.estimated_monthly_revenue || rev.monthly_total || 0;
    _setText('civ-revenue', '$' + Math.round(monthly).toLocaleString());

    // Pipeline Activity card
    const pipeEl = document.getElementById('civ-pipeline');
    if (pipeEl) {
        const bgLoops = dashStatus?.background_loops || dashStatus?.loops || {};
        const loopNames = {
            proactive: 'Proactive Engine', autonomous: 'Auto-Improve', builder: 'Builder',
            directive: 'Directives', reflection: 'Reflection', learning: 'Learning',
            curiosity: 'Curiosity', network: 'Agent Network', triggers: 'Triggers',
            decay: 'Memory Decay', actuator: 'Actuator',
        };
        const expMem = civStatus?.experience_memory || {};
        const expLab = civStatus?.experiment_lab || {};
        const swc = civStatus?.self_writing_code || {};
        const revData = civStatus?.revenue || {};

        pipeEl.innerHTML = `
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px">
                <div class="card" style="padding:10px">
                    <div style="font-weight:600;font-size:12px;margin-bottom:8px;text-transform:uppercase;letter-spacing:0.5px;color:var(--text-muted)">Background Loops</div>
                    <div style="display:flex;flex-wrap:wrap;gap:4px">
                        ${Object.entries(loopNames).map(([k, label]) => {
                            const running = bgLoops[k]?.running ?? bgLoops[k] ?? true;
                            return `<span style="background:${running ? 'var(--accent-green)' : 'var(--accent-red)'}15;color:${running ? 'var(--accent-green)' : 'var(--accent-red)'};padding:3px 8px;border-radius:10px;font-size:10px">${escHtml(label)}</span>`;
                        }).join('')}
                    </div>
                </div>
                <div class="card" style="padding:10px">
                    <div style="font-weight:600;font-size:12px;margin-bottom:8px;text-transform:uppercase;letter-spacing:0.5px;color:var(--text-muted)">System Pipeline</div>
                    <div style="font-size:12px;display:grid;gap:4px">
                        <div style="display:flex;justify-content:space-between"><span>Experiences</span><span style="font-weight:600">${expMem.total_experiences || exp.total || 0}</span></div>
                        <div style="display:flex;justify-content:space-between"><span>Experiments</span><span style="font-weight:600">${expLab.total_experiments || exl.total || 0} (${(expLab.by_status || {}).running || 0} running)</span></div>
                        <div style="display:flex;justify-content:space-between"><span>Code Proposals</span><span style="font-weight:600">${swc.total_proposals || 0} (${(swc.by_status || {}).proposed || 0} pending)</span></div>
                        <div style="display:flex;justify-content:space-between"><span>Revenue Streams</span><span style="font-weight:600">${revData.total_products || 0} products</span></div>
                        <div style="display:flex;justify-content:space-between"><span>Profit</span><span style="font-weight:600;color:${(revData.profit || 0) >= 0 ? 'var(--accent-green)' : 'var(--accent-red)'}">$${Math.round(revData.profit || 0)}</span></div>
                    </div>
                </div>
            </div>`;
    }

    // Divisions — expandable with agent details
    const divEl = document.getElementById('civ-divisions');
    if (divEl) {
        const divEntries = Object.entries(divData);
        if (divEntries.length) {
            const divColors = [
                'var(--accent)', 'var(--accent-blue)', 'var(--accent-cyan)',
                'var(--accent-purple)', 'var(--accent-green)', 'var(--accent-gold)',
                'var(--accent-orange)', 'var(--accent-pink)', '#a87bd4', 'var(--accent-red)',
            ];
            divEl.innerHTML = divEntries.map(([name, agents], i) => {
                const color = divColors[i % divColors.length];
                const agentList = Array.isArray(agents) ? agents : [];
                const count = agentList.length;
                const divId = `div-${name.replace(/[^a-z0-9]/gi, '_')}`;
                return `<div class="card" style="margin-bottom:8px;cursor:pointer" onclick="toggleDivision('${divId}')">
                    <div style="display:flex;align-items:center;gap:10px">
                        <div style="width:10px;height:10px;border-radius:50%;background:${color};flex-shrink:0"></div>
                        <div style="font-weight:700;font-size:13px">${escHtml(name)}</div>
                        <span style="margin-left:auto;background:${color}22;color:${color};padding:2px 8px;border-radius:10px;font-size:11px">${count} agents</span>
                        <span style="color:var(--text-muted);font-size:10px" id="${divId}-arrow">&#9654;</span>
                    </div>
                    <div id="${divId}" style="display:none;margin-top:10px;border-top:1px solid var(--border);padding-top:8px">
                        ${agentList.map(a => {
                            const n = typeof a === 'string' ? a : (a.name || a.id || '');
                            const role = typeof a === 'object' ? (a.role || '') : '';
                            const tier = typeof a === 'object' ? (a.tier ?? '') : '';
                            const caps = typeof a === 'object' && Array.isArray(a.capabilities) ? a.capabilities : [];
                            return `<div style="display:flex;align-items:center;gap:8px;padding:4px 0;border-bottom:1px solid var(--border)">
                                <span style="font-size:12px;font-weight:600;min-width:140px">${escHtml(n)}</span>
                                ${tier !== '' ? `<span style="background:var(--accent)22;color:var(--accent);padding:1px 6px;border-radius:8px;font-size:10px;font-weight:600">T${tier}</span>` : ''}
                                <span style="font-size:11px;color:var(--text-secondary);flex:1">${escHtml(role)}</span>
                                ${caps.length ? `<span style="font-size:10px;color:var(--text-muted)">${caps.length} caps</span>` : ''}
                            </div>`;
                        }).join('')}
                    </div>
                </div>`;
            }).join('');
        } else {
            divEl.innerHTML = '<div class="empty-state">No divisions loaded</div>';
        }
    }

    // Experience breakdown — clickable types for drill-down
    const expEl = document.getElementById('civ-experience');
    if (expEl) {
        const byType = exp.by_type || {};
        if (Object.keys(byType).length) {
            const typeColors = { success: 'var(--accent-green)', failure: 'var(--accent-red)', strategy: 'var(--accent-blue)', lesson: 'var(--accent-purple)' };
            expEl.innerHTML = `<div class="grid-4" style="margin-bottom:12px">
                ${Object.entries(byType).map(([t, c]) => {
                    const count = typeof c === 'object' ? (c.count || 0) : c;
                    return `<div class="stat-card" style="padding:10px;cursor:pointer" onclick="drillExperience('${escHtml(t)}')">
                        <div class="stat-value" style="font-size:18px;color:${typeColors[t] || 'var(--accent)'}">${count}</div>
                        <div class="stat-label">${escHtml(t)}</div>
                    </div>`;
                }).join('')}
            </div>
            <div id="civ-experience-drill" style="display:none"></div>`;
        } else {
            expEl.innerHTML = '<div style="color:var(--text-muted);padding:12px">Recording experiences as agents operate...</div>';
        }
    }

    // Experiments detail
    const expLabEl = document.getElementById('civ-experiment-list');
    if (expLabEl) {
        const expList = experiments?.data ?? experiments?.experiments ?? (Array.isArray(experiments) ? experiments : []);
        if (expList.length) {
            expLabEl.innerHTML = expList.map(e => {
                const statusColor = e.status === 'completed' ? 'var(--accent-green)' : e.status === 'approved' ? 'var(--accent-green)' : e.status === 'running' ? 'var(--accent-blue)' : e.status === 'failed' ? 'var(--accent-red)' : e.status === 'rejected' ? 'var(--accent-red)' : 'var(--text-muted)';
                return `<div style="padding:8px 0;border-bottom:1px solid var(--border)">
                    <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
                        <span style="background:${statusColor}22;color:${statusColor};padding:2px 8px;border-radius:10px;font-size:11px">${escHtml(e.status || 'proposed')}</span>
                        <span style="font-size:13px;font-weight:500">${escHtml(e.title || e.hypothesis || e.id || '')}</span>
                        ${e.status === 'proposed' ? `<div style="margin-left:auto;display:flex;gap:4px">
                            <button class="btn-sm" style="color:var(--accent-green)" onclick="approveExperiment('${escHtml(e.id || '')}')">Approve</button>
                            <button class="btn-sm" style="color:var(--accent-red)" onclick="rejectExperiment('${escHtml(e.id || '')}')">Reject</button>
                            <button class="btn-sm" onclick="startExperiment('${escHtml(e.id || '')}')">Start</button>
                        </div>` : ''}
                    </div>
                    <div style="font-size:12px;color:var(--text-secondary)">${escHtml((e.hypothesis || e.description || '').slice(0, 200))}</div>
                </div>`;
            }).join('');
        } else {
            const byStatus = exl.by_status || {};
            expLabEl.innerHTML = Object.entries(byStatus).map(([s, c]) => {
                const color = s === 'completed' ? 'var(--accent-green)' : s === 'running' ? 'var(--accent-blue)' : s === 'failed' ? 'var(--accent-red)' : 'var(--text-muted)';
                return `<span style="background:${color}22;color:${color};padding:4px 12px;border-radius:12px;font-size:12px;font-weight:500;margin:4px">${escHtml(s)}: ${c}</span>`;
            }).join('') || '<span style="color:var(--text-muted)">No experiments yet</span>';
        }
    }

    // Code proposals
    const codeEl = document.getElementById('civ-code-proposals');
    if (codeEl) {
        const proposals = codeProposals?.data ?? codeProposals?.proposals ?? (Array.isArray(codeProposals) ? codeProposals : []);
        if (proposals.length) {
            const pendingIds = proposals.filter(p => p.status === 'pending_approval' || (p.status !== 'approved' && p.status !== 'rejected' && p.status !== 'deployed')).map(p => p.id);
            const approveAllBtn = pendingIds.length > 1
                ? `<div style="margin-bottom:8px"><button class="btn-sm" style="color:var(--accent-green);border:1px solid var(--accent-green);padding:4px 12px" onclick="approveAllCodeProposals()">Approve All (${pendingIds.length})</button></div>`
                : '';
            codeEl.innerHTML = approveAllBtn + proposals.map(p => {
                const approved = p.status === 'approved' || p.status === 'deployed';
                const rejected = p.status === 'rejected';
                const pending = !approved && !rejected;
                const filePath = p.file ? `<span style="font-size:11px;color:var(--text-muted);font-family:monospace">${escHtml(p.file)}</span>` : '';
                const scopeBadge = p.scope ? `<span style="font-size:10px;color:var(--text-muted);text-transform:uppercase">[${escHtml(p.scope)}]</span>` : '';
                const changePreview = p.proposed_change ? `<details style="margin-top:4px"><summary style="font-size:11px;color:var(--accent);cursor:pointer">View proposed change</summary><pre style="font-size:11px;background:var(--bg-secondary);padding:6px;border-radius:4px;overflow-x:auto;max-height:200px;margin-top:4px">${escHtml(p.proposed_change.slice(0, 500))}</pre></details>` : '';
                return `<div style="padding:8px 0;border-bottom:1px solid var(--border)">
                    <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
                        <span style="background:${approved ? 'var(--accent-green)' : rejected ? 'var(--accent-red)' : 'var(--accent-orange)'}22;color:${approved ? 'var(--accent-green)' : rejected ? 'var(--accent-red)' : 'var(--accent-orange)'};padding:2px 8px;border-radius:10px;font-size:11px">${escHtml(p.status || 'pending')}</span>
                        <span style="font-size:13px;font-weight:500">${escHtml(p.title || p.description || p.id || '')}</span>
                        ${scopeBadge}
                        ${pending ? `<div style="margin-left:auto;display:flex;gap:4px">
                            <button class="btn-sm" style="color:var(--accent-green)" onclick="approveCodeProposal('${escHtml(p.id || '')}')">Approve</button>
                            <button class="btn-sm" style="color:var(--accent-red)" onclick="rejectCodeProposal('${escHtml(p.id || '')}')">Reject</button>
                        </div>` : ''}
                    </div>
                    ${filePath}
                    <div style="font-size:12px;color:var(--text-secondary);margin-top:2px">${escHtml((p.description || p.rationale || '').slice(0, 300))}</div>
                    ${changePreview}
                </div>`;
            }).join('');
        } else {
            codeEl.innerHTML = '<div style="color:var(--text-muted);padding:12px">No code proposals yet</div>';
        }
    }
}

async function startExperiment(experimentId) {
    const btn = event?.target;
    if (btn) { btn.disabled = true; btn.textContent = '...'; }
    try {
        await api(`/api/civilization/experiments/${experimentId}/start`, { method: 'POST' });
        if (btn) { btn.textContent = 'Started'; }
        setTimeout(() => loadCivilization(), 1000);
    } catch (e) {
        if (btn) { btn.textContent = 'Error'; btn.disabled = false; }
    }
}

async function approveAllCodeProposals() {
    const btn = event?.target;
    if (btn) { btn.disabled = true; btn.textContent = 'Approving all...'; }
    try {
        const res = await api('/api/civilization/code-proposals?limit=50');
        const proposals = res?.proposals ?? res?.data ?? [];
        const pending = proposals.filter(p => p.status === 'pending_approval' || (p.status !== 'approved' && p.status !== 'rejected' && p.status !== 'deployed'));
        let approved = 0;
        for (const p of pending) {
            try {
                await api(`/api/civilization/code-proposals/${p.id}/approve`, { method: 'POST' });
                approved++;
            } catch (_) { /* skip failed */ }
        }
        if (btn) { btn.textContent = `Approved ${approved}`; btn.style.color = 'var(--accent-green)'; }
        pushActivity('Bulk approved', `${approved} code proposals`, 'civilization', 'coder');
        setTimeout(() => loadCivilization(), 800);
    } catch (e) {
        if (btn) { btn.textContent = 'Error'; btn.disabled = false; }
    }
}

async function approveCodeProposal(proposalId) {
    const btn = event?.target;
    if (btn) { btn.disabled = true; btn.textContent = 'Approving...'; }
    try {
        await api(`/api/civilization/code-proposals/${proposalId}/approve`, { method: 'POST' });
        if (btn) { btn.textContent = 'Approved'; btn.style.color = 'var(--accent-green)'; }
        pushActivity('Approved', `Code proposal ${proposalId.slice(0, 8)}`, 'civilization', 'coder');
        setTimeout(() => loadCivilization(), 800);
    } catch (e) {
        if (btn) { btn.textContent = 'Error'; btn.disabled = false; }
    }
}

async function rejectCodeProposal(proposalId) {
    const btn = event?.target;
    if (btn) { btn.disabled = true; btn.textContent = 'Rejecting...'; }
    try {
        await api(`/api/civilization/code-proposals/${proposalId}/reject`, { method: 'POST' });
        if (btn) { btn.textContent = 'Rejected'; btn.style.color = 'var(--accent-red)'; }
        pushActivity('Rejected', `Code proposal ${proposalId.slice(0, 8)}`, 'civilization', 'coder');
        setTimeout(() => loadCivilization(), 800);
    } catch (e) {
        if (btn) { btn.textContent = 'Error'; btn.disabled = false; }
    }
}

async function approveExperiment(experimentId) {
    const btn = event?.target;
    if (btn) { btn.disabled = true; btn.textContent = 'Approving...'; }
    try {
        await api(`/api/civilization/experiments/${experimentId}/approve`, { method: 'POST' });
        if (btn) { btn.textContent = 'Approved'; btn.style.color = 'var(--accent-green)'; }
        pushActivity('Approved', `Experiment ${experimentId.slice(0, 8)}`, 'civilization', 'analyst');
        setTimeout(() => loadCivilization(), 800);
    } catch (e) {
        if (btn) { btn.textContent = 'Error'; btn.disabled = false; }
    }
}

async function rejectExperiment(experimentId) {
    const btn = event?.target;
    if (btn) { btn.disabled = true; btn.textContent = 'Rejecting...'; }
    try {
        await api(`/api/civilization/experiments/${experimentId}/reject`, { method: 'POST' });
        if (btn) { btn.textContent = 'Rejected'; btn.style.color = 'var(--accent-red)'; }
        pushActivity('Rejected', `Experiment ${experimentId.slice(0, 8)}`, 'civilization', 'analyst');
        setTimeout(() => loadCivilization(), 800);
    } catch (e) {
        if (btn) { btn.textContent = 'Error'; btn.disabled = false; }
    }
}

function toggleDivision(divId) {
    const el = document.getElementById(divId);
    const arrow = document.getElementById(divId + '-arrow');
    if (!el) return;
    const visible = el.style.display !== 'none';
    el.style.display = visible ? 'none' : 'block';
    if (arrow) arrow.innerHTML = visible ? '&#9654;' : '&#9660;';
}

async function drillExperience(type) {
    const drillEl = document.getElementById('civ-experience-drill');
    if (!drillEl) return;
    if (drillEl.style.display !== 'none' && drillEl.dataset.type === type) {
        drillEl.style.display = 'none';
        return;
    }
    drillEl.dataset.type = type;
    drillEl.style.display = 'block';
    drillEl.innerHTML = '<div style="color:var(--text-muted);padding:8px;font-size:12px">Loading...</div>';
    try {
        const data = await api(`/api/civilization/experience?type=${encodeURIComponent(type)}&limit=5`);
        const records = data?.data ?? data?.experiences ?? (Array.isArray(data) ? data : []);
        if (!records.length) {
            drillEl.innerHTML = `<div style="color:var(--text-muted);padding:8px;font-size:12px">No ${escHtml(type)} experiences recorded yet</div>`;
            return;
        }
        const typeColors = { success: 'var(--accent-green)', failure: 'var(--accent-red)', strategy: 'var(--accent-blue)', lesson: 'var(--accent-purple)' };
        const color = typeColors[type] || 'var(--accent)';
        drillEl.innerHTML = `<div style="font-weight:600;font-size:12px;margin-bottom:6px;color:${color}">Recent ${escHtml(type)} experiences</div>` +
            records.map(r => `<div style="padding:6px 0;border-bottom:1px solid var(--border);font-size:12px">
                <div style="display:flex;align-items:center;gap:8px;margin-bottom:3px">
                    <span style="font-weight:600">${escHtml(r.title || r.domain || '')}</span>
                    <span style="color:var(--text-muted);font-size:10px">${escHtml(r.domain || '')}</span>
                    ${r.confidence != null ? `<span style="margin-left:auto;font-size:10px;color:${color}">${(r.confidence * 100).toFixed(0)}%</span>` : ''}
                </div>
                <div style="color:var(--text-secondary)">${escHtml((r.description || r.outcome || '').slice(0, 200))}</div>
                ${r.created_at ? `<div style="font-size:10px;color:var(--text-muted);margin-top:2px">${formatTime(r.created_at)}</div>` : ''}
            </div>`).join('');
    } catch (e) {
        drillEl.innerHTML = '<div style="color:var(--accent-red);padding:8px;font-size:12px">Failed to load experiences</div>';
    }
}

function showRecordExperienceModal() {
    showModal({
        title: 'Record Experience',
        fields: [
            { key: 'type', label: 'Type', type: 'select', options: ['success', 'failure', 'strategy', 'lesson'], required: true },
            { key: 'domain', label: 'Domain', type: 'text', placeholder: 'e.g. trading, engineering, research', required: true },
            { key: 'title', label: 'Title', type: 'text', placeholder: 'Brief title', required: true },
            { key: 'description', label: 'Description', type: 'textarea', placeholder: 'What happened?', required: true },
            { key: 'outcome', label: 'Outcome', type: 'text', placeholder: 'Result or impact' },
            { key: 'confidence', label: 'Confidence', type: 'range', min: 0, max: 100, step: 5, value: 70 },
        ],
        submitLabel: 'Record',
        onSubmit: async (vals) => {
            await api('/api/civilization/experience', {
                method: 'POST',
                body: {
                    type: vals.type,
                    domain: vals.domain,
                    title: vals.title,
                    description: vals.description,
                    outcome: vals.outcome || '',
                    confidence: vals.confidence / 100,
                },
            });
            closeModal();
            loadCivilization();
        },
    });
}

function showProposeExperimentModal() {
    showModal({
        title: 'Propose Experiment',
        fields: [
            { key: 'title', label: 'Title', type: 'text', placeholder: 'Experiment name', required: true },
            { key: 'hypothesis', label: 'Hypothesis', type: 'textarea', placeholder: 'What do you expect to happen?', required: true },
            { key: 'category', label: 'Category', type: 'select', options: ['saas', 'marketing', 'trading', 'pricing', 'content', 'automation', 'other'] },
            { key: 'variables', label: 'Variables (comma-separated)', type: 'tags', placeholder: 'price, audience, channel' },
        ],
        submitLabel: 'Propose',
        onSubmit: async (vals) => {
            await api('/api/civilization/experiments', {
                method: 'POST',
                body: {
                    title: vals.title,
                    hypothesis: vals.hypothesis,
                    category: vals.category || 'other',
                    variables: vals.variables || [],
                },
            });
            closeModal();
            loadCivilization();
        },
    });
}

function showAddRevenueProductModal() {
    showModal({
        title: 'Add Revenue Product',
        fields: [
            { key: 'name', label: 'Product Name', type: 'text', required: true },
            { key: 'stream', label: 'Revenue Stream', type: 'select', options: ['automation_agency', 'micro_saas', 'content_network', 'data_products', 'ai_consulting'] },
            { key: 'description', label: 'Description', type: 'textarea' },
            { key: 'price', label: 'Price ($)', type: 'number', min: 0, step: 0.01 },
            { key: 'recurring', label: 'Recurring (monthly)?', type: 'select', options: [{value: 'true', label: 'Yes'}, {value: 'false', label: 'No'}] },
        ],
        submitLabel: 'Add Product',
        onSubmit: async (vals) => {
            await api('/api/civilization/revenue/products', {
                method: 'POST',
                body: {
                    name: vals.name,
                    stream: vals.stream,
                    description: vals.description || '',
                    price: vals.price || 0,
                    recurring: vals.recurring === 'true',
                },
            });
            closeModal();
            loadCivilization();
        },
    });
}

// ── Network Panel ─────────────────────────────────────────────
async function loadNetwork() {
    const [stats, graphData] = await Promise.all([
        api('/api/autonomy/network/stats'),
        api('/api/autonomy/network'),
    ]);

    const s = stats?.data ?? stats ?? {};
    document.getElementById('net-nodes').textContent = s.nodes || s.total_agents || s.total_insights || 0;
    document.getElementById('net-connections').textContent = s.connections || s.total_connections || s.total_effects || 0;
    document.getElementById('net-propagations').textContent = s.propagations || s.propagation_cycles || 0;
    document.getElementById('net-knowledge').textContent = s.total_knowledge_shared || s.active_insights || 0;

    const g = graphData?.data ?? graphData ?? {};
    const nodes = g.nodes || [];
    const recentInsights = g.recent_insights || [];

    const graphEl = document.getElementById('net-graph');
    if (graphEl && nodes.length) {
        graphEl.innerHTML = nodes.slice(0, 20).map(n => {
            const activity = n.activity || n.connections || 0;
            const size = Math.max(8, Math.min(24, 8 + activity * 2));
            const color = getAgentColor(n.id || n.agent_id || n.name);
            return `<div style="display:inline-flex;flex-direction:column;align-items:center;gap:4px;margin:8px;cursor:pointer" onclick="showNetworkInsight('${escHtml(n.id || '')}')">
                <div style="width:${size}px;height:${size}px;border-radius:50%;background:${color};box-shadow:0 0 ${Math.round(size/2)}px ${color}40"></div>
                <div style="font-size:10px;color:var(--text-muted);max-width:60px;text-align:center;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${escHtml(n.name || n.id || '')}</div>
            </div>`;
        }).join('');
    } else if (graphEl) {
        graphEl.innerHTML = '<div class="empty-state">Agent network data loading...</div>';
    }

    // Recent insights list
    const riEl = document.getElementById('net-recent-insights');
    if (riEl) {
        if (recentInsights.length) {
            riEl.innerHTML = recentInsights.slice(0, 10).map(i => `
                <div style="padding:6px 0;border-bottom:1px solid var(--border);font-size:12px">
                    <div style="display:flex;align-items:center;gap:8px;margin-bottom:3px">
                        <span style="font-weight:600;color:${getAgentColor(i.source_agent)}">${escHtml(i.source_agent || '')}</span>
                        <span style="color:var(--text-muted)">${escHtml(i.domain || '')}</span>
                        <span style="margin-left:auto;font-size:10px;color:var(--text-muted)">${formatTime(i.created_at)}</span>
                    </div>
                    <div style="color:var(--text-secondary)">${escHtml((i.content || '').slice(0, 200))}</div>
                </div>`).join('');
        } else {
            riEl.innerHTML = '<div style="color:var(--text-muted);padding:12px">No insights shared yet</div>';
        }
    }
}

async function showNetworkInsight(agentId) {
    if (!agentId) return;
    const data = await api(`/api/autonomy/network/insights/${agentId}`);
    const el = document.getElementById('net-insight');
    if (el && data) {
        const insights = data.insights || data.data || data;
        el.innerHTML = `<div class="card" style="margin-top:12px">
            <div class="card-title">Insights: ${escHtml(agentId)}</div>
            ${Array.isArray(insights) && insights.length ? insights.map(i =>
                `<div style="padding:6px 0;border-bottom:1px solid var(--border);font-size:12px">
                    <div style="display:flex;align-items:center;gap:8px;margin-bottom:3px">
                        <span style="font-size:11px;background:var(--bg-elevated);padding:2px 6px;border-radius:4px">${escHtml(i.insight_type || i.type || '')}</span>
                        <span style="color:var(--text-muted)">${escHtml(i.domain || '')}</span>
                        <span style="margin-left:auto;font-size:11px;color:var(--accent)">${i.confidence ? (i.confidence * 100).toFixed(0) + '%' : ''}</span>
                    </div>
                    <div style="color:var(--text-secondary)">${escHtml((i.content || '').slice(0, 300))}</div>
                </div>`
            ).join('') : `<div style="font-size:12px;color:var(--text-muted)">No insights for this agent</div>`}
        </div>`;
    }
}

// ── Agent Detail Drill-Down ──────────────────────────────────
async function showAgentDetail(agentId) {
    try {
        const [agentData, learningData] = await Promise.all([
            api(`/api/agents/${agentId}`),
            api(`/api/agents/${agentId}/stats`).catch(() => null),
        ]);
        const agent = agentData?.data || agentData || {};
        const stats = learningData?.data || learningData || {};
        const color = AGENT_COLORS[agentId] || 'var(--accent)';
        const h = agent.health?.status || 'unknown';
        const isCustom = agent.metadata?.custom;

        const successRate = stats.success_rate !== undefined ? (stats.success_rate * 100).toFixed(0) + '%' : '\u2014';
        const totalTasks = stats.total_tasks || agent.tasks_completed || 0;
        const routingWeight = stats.routing_weight !== undefined ? stats.routing_weight.toFixed(3) : '\u2014';

        const caps = (agent.capabilities || []).map(c =>
            `<span class="cap-tag" title="${escHtml(c.description || '')}">${escHtml(c.name)}</span>`
        ).join('');

        const recentTasks = (stats.recent_tasks || []).slice(0, 10);
        const taskList = recentTasks.length ? recentTasks.map(t => {
            const statusColor = t.status === 'completed' ? 'var(--accent-green)' : t.status === 'failed' ? 'var(--accent-red)' : 'var(--accent-blue)';
            return `<div style="padding:6px 0;border-bottom:1px solid var(--border);font-size:12px">
                <div style="display:flex;justify-content:space-between;align-items:center">
                    <span style="color:var(--text-primary)">${escHtml((t.description || t.task || '').slice(0, 80))}</span>
                    <span style="color:${statusColor};font-size:11px">${escHtml(t.status || '')}</span>
                </div>
                <div style="font-size:11px;color:var(--text-muted);margin-top:2px">${formatTime(t.completed_at || t.created_at || '')}</div>
            </div>`;
        }).join('') : '<div style="font-size:12px;color:var(--text-muted);padding:8px">No recent tasks recorded</div>';

        showDetailModal({
            title: `${agent.name || agentId}`,
            content: `
                <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">
                    <div class="agent-avatar" style="background:${color};width:48px;height:48px;font-size:20px;display:flex;align-items:center;justify-content:center;border-radius:12px;color:white">${(agent.name || '?')[0]}</div>
                    <div>
                        <div style="font-weight:700;font-size:16px">${escHtml(agent.name || agentId)}</div>
                        <div style="font-size:12px;color:var(--text-secondary)">${escHtml(agent.role || '')} &middot; Tier ${agent.tier || '?'}</div>
                        <div style="display:flex;gap:6px;margin-top:4px">
                            <span class="status-pill ${h}">${escHtml(h)}</span>
                            ${isCustom ? '<span style="font-size:10px;color:var(--accent-cyan);font-weight:600">CUSTOM</span>' : ''}
                        </div>
                    </div>
                </div>
                <div style="font-size:13px;color:var(--text-secondary);margin-bottom:16px">${escHtml(agent.description || '')}</div>
                <div class="grid-4" style="margin-bottom:16px">
                    <div class="stat-card"><div class="stat-value" style="font-size:16px">${totalTasks}</div><div class="stat-label">Tasks</div></div>
                    <div class="stat-card"><div class="stat-value" style="font-size:16px;color:var(--accent-green)">${successRate}</div><div class="stat-label">Success Rate</div></div>
                    <div class="stat-card"><div class="stat-value" style="font-size:16px">${routingWeight}</div><div class="stat-label">Routing Weight</div></div>
                    <div class="stat-card"><div class="stat-value" style="font-size:16px">${escHtml(agent.connector_type || 'internal')}</div><div class="stat-label">Connector</div></div>
                </div>
                <div style="margin-bottom:12px">
                    <div style="font-weight:600;font-size:12px;margin-bottom:6px">Capabilities</div>
                    <div class="agent-caps">${caps || '<span style="font-size:12px;color:var(--text-muted)">None</span>'}</div>
                </div>
                <div>
                    <div style="font-weight:600;font-size:12px;margin-bottom:6px">Recent Tasks</div>
                    ${taskList}
                </div>`,
        });
    } catch (e) {
        console.error('Agent detail error:', e);
    }
}

async function shareNetworkInsight() {
    const content = document.getElementById('net-content')?.value?.trim();
    if (!content) return;
    const sourceAgent = document.getElementById('net-source-agent')?.value || 'researcher';
    const insightType = document.getElementById('net-insight-type')?.value || 'discovery';
    const domain = document.getElementById('net-domain')?.value || 'research';
    try {
        await api('/api/autonomy/network/share', {
            method: 'POST',
            body: {
                source_agent: sourceAgent,
                insight_type: insightType,
                domain: domain,
                content: content,
                confidence: 0.7,
                ttl_hours: 48,
            },
        });
        document.getElementById('net-content').value = '';
        loadNetwork();
    } catch (e) {
        console.error('Share insight failed:', e);
    }
}
