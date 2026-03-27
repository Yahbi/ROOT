/* panels-autonomy.js — Goals, Directives, Action Chains, Curiosity */

// ── Goals & Tasks Panel ──────────────────────────────────────
async function loadGoals() {
    const [allGoals, queueStats] = await Promise.all([
        api('/api/autonomy/goals?limit=200'),
        api('/api/autonomy/queue/stats'),
    ]);

    if (allGoals?.goals) {
        const gs = allGoals.goals;
        _setText('goals-active', gs.filter(g => g.status === 'active').length);
        _setText('goals-completed', gs.filter(g => g.status === 'completed').length);
        _setText('goals-stalled', gs.filter(g => g.status === 'stalled').length);
    }
    if (queueStats && !queueStats.error) {
        const bs = queueStats.by_status || {};
        _setText('tasks-pending', bs.pending || 0);
    }

    const goals = allGoals;
    const gl = document.getElementById('goals-list');
    if (gl && goals?.goals?.length) {
        const active = goals.goals.filter(g => g.status === 'active' || g.status === 'stalled');
        const other = goals.goals.filter(g => g.status !== 'active' && g.status !== 'stalled');

        gl.innerHTML = active.length ? active.map(g => _renderGoalItem(g)).join('') :
            '<div class="empty-state" style="padding:20px">No active goals. Create one above.</div>';

        const otherEl = document.getElementById('goals-other-list');
        if (otherEl) {
            otherEl.innerHTML = other.length ? other.map(g => _renderGoalItem(g)).join('') :
                '<div class="empty-state" style="padding:12px">No completed or paused goals</div>';
        }
    } else if (gl) {
        gl.innerHTML = '<div class="empty-state" style="padding:20px">No active goals. Create one above.</div>';
    }

    // Goal status chart
    const _byStatus = {};
    if (allGoals?.goals) allGoals.goals.forEach(g => { _byStatus[g.status] = (_byStatus[g.status] || 0) + 1; });
    if (typeof Chart !== 'undefined' && Object.keys(_byStatus).length) {
        const bs = _byStatus;
        const statuses = Object.keys(bs);
        const colors = { active: 'var(--accent-green)', completed: 'var(--accent-cyan)', stalled: 'var(--accent-orange)', abandoned: 'var(--accent-red)', paused: 'var(--text-muted)' };
        _renderChart('chart-goals', {
            type: 'doughnut',
            data: {
                labels: statuses,
                datasets: [{ data: statuses.map(s => bs[s]), backgroundColor: statuses.map(s => colors[s] || 'var(--accent)'), borderWidth: 0 }],
            },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom', labels: { color: 'var(--text-muted)', font: { size: 10 } } } } },
        });
    }
}

function _renderGoalItem(g) {
    const statusColors = { active: 'var(--accent-green)', completed: 'var(--accent-cyan)', stalled: 'var(--accent-orange)', abandoned: 'var(--accent-red)', paused: 'var(--text-muted)' };
    const statusColor = statusColors[g.status] || 'var(--text-muted)';
    const isActive = g.status === 'active';
    const isPaused = g.status === 'paused';
    const isStalled = g.status === 'stalled';

    return `<div class="list-item" style="padding:10px;border-bottom:1px solid var(--border)">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px">
            <div style="flex:1;min-width:0">
                <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
                    <span style="background:${statusColor}22;color:${statusColor};padding:2px 8px;border-radius:10px;font-size:11px">${g.status}</span>
                    <span style="font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${escHtml(g.title)}</span>
                </div>
                <div style="font-size:11px;color:var(--text-muted)">${escHtml(g.category || 'general')} · priority ${g.priority || 5}${g.created_at ? ' · ' + formatTime(g.created_at) : ''}</div>
            </div>
            <div style="display:flex;align-items:center;gap:6px;flex-shrink:0">
                <div style="text-align:right;margin-right:8px">
                    <div class="progress-bar" style="width:80px;height:6px;background:var(--border);border-radius:3px;overflow:hidden">
                        <div style="width:${(g.progress || 0) * 100}%;height:100%;background:var(--accent-green);border-radius:3px"></div>
                    </div>
                    <div style="font-size:10px;color:var(--text-muted);margin-top:2px">${Math.round((g.progress || 0) * 100)}%</div>
                </div>
                ${isActive || isStalled ? `<button class="btn-sm" onclick="pauseGoal('${escHtml(g.id)}')" title="Pause">⏸</button>` : ''}
                ${isPaused ? `<button class="btn-sm" onclick="resumeGoal('${escHtml(g.id)}')" title="Resume">▶</button>` : ''}
                ${isActive ? `<button class="btn-sm" onclick="decomposeGoal('${escHtml(g.id)}')" title="Decompose into tasks">⚡</button>` : ''}
                <button class="btn-sm" onclick="showGoalProgressModal('${escHtml(g.id)}', ${g.progress || 0})" title="Update progress">📊</button>
                <button class="btn-sm" onclick="showGoalDetail('${escHtml(g.id)}')" title="View details">👁</button>
            </div>
        </div>
    </div>`;
}

async function createGoal() {
    const title = document.getElementById('goal-title')?.value;
    const desc = document.getElementById('goal-desc')?.value;
    const priority = parseInt(document.getElementById('goal-priority')?.value || '5');
    const category = document.getElementById('goal-category')?.value || 'general';
    if (!title) return;

    await api('/api/autonomy/goals', {
        method: 'POST',
        body: { title, description: desc, priority, category },
    });
    document.getElementById('goal-title').value = '';
    document.getElementById('goal-desc').value = '';
    loadGoals();
}

async function pauseGoal(goalId) {
    await api(`/api/autonomy/goals/${goalId}/pause`, { method: 'POST' });
    loadGoals();
}

async function resumeGoal(goalId) {
    await api(`/api/autonomy/goals/${goalId}/resume`, { method: 'POST' });
    loadGoals();
}

async function decomposeGoal(goalId) {
    const btn = event?.target;
    if (btn) { btn.disabled = true; btn.textContent = '…'; }
    try {
        const result = await api(`/api/autonomy/goals/${goalId}/decompose`, { method: 'POST' });
        const count = result?.tasks_created || 0;
        if (btn) { btn.textContent = `${count} tasks`; setTimeout(() => { btn.textContent = '⚡'; btn.disabled = false; }, 2000); }
        loadGoals();
    } catch (e) {
        if (btn) { btn.textContent = '⚡'; btn.disabled = false; }
    }
}

function showGoalProgressModal(goalId, currentProgress) {
    showModal({
        title: 'Update Goal Progress',
        fields: [
            { key: 'progress', label: 'Progress', type: 'range', min: 0, max: 100, step: 5, value: Math.round(currentProgress * 100) },
            { key: 'note', label: 'Note (optional)', type: 'text', placeholder: 'Progress update note' },
        ],
        submitLabel: 'Update',
        onSubmit: async (vals) => {
            await api(`/api/autonomy/goals/${goalId}/progress`, {
                method: 'POST',
                body: { progress: vals.progress / 100, note: vals.note || '' },
            });
            closeModal();
            loadGoals();
        },
    });
}

async function showGoalDetail(goalId) {
    const data = await api(`/api/autonomy/goals/${goalId}`);
    if (!data || data.error) return;
    const events = (data.events || []).slice(0, 10);
    const milestones = data.milestones || [];
    const completedMs = data.completed_milestones || [];
    showDetailModal({
        title: escHtml(data.title),
        content: `
            <div style="margin-bottom:12px">
                <div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:12px">
                    <span style="font-size:12px;color:var(--text-muted)">Status: <strong>${escHtml(data.status)}</strong></span>
                    <span style="font-size:12px;color:var(--text-muted)">Priority: <strong>${data.priority}</strong></span>
                    <span style="font-size:12px;color:var(--text-muted)">Category: <strong>${escHtml(data.category)}</strong></span>
                    <span style="font-size:12px;color:var(--text-muted)">Progress: <strong>${Math.round((data.progress || 0) * 100)}%</strong></span>
                    <span style="font-size:12px;color:var(--text-muted)">Tasks: <strong>${data.tasks_completed || 0}/${data.tasks_generated || 0}</strong></span>
                </div>
                ${data.description ? `<p style="font-size:13px;color:var(--text-secondary)">${escHtml(data.description)}</p>` : ''}
            </div>
            ${milestones.length ? `<div style="margin-bottom:12px"><div style="font-weight:600;font-size:13px;margin-bottom:6px">Milestones</div>
                ${milestones.map(m => `<div style="padding:4px 0;font-size:12px">${completedMs.includes(m) ? '<span style="color:var(--accent-green)">✓</span>' : '<span style="color:var(--text-muted)">○</span>'} ${escHtml(m)}</div>`).join('')}
            </div>` : ''}
            ${events.length ? `<div><div style="font-weight:600;font-size:13px;margin-bottom:6px">Recent Events</div>
                ${events.map(e => `<div style="padding:4px 0;font-size:12px;border-bottom:1px solid var(--border)">${escHtml(JSON.stringify(e).slice(0, 200))}</div>`).join('')}
            </div>` : ''}`,
    });
}

// ── Directives Panel ─────────────────────────────────────────
async function loadDirectives() {
    const [dirData, escData, trigData] = await Promise.all([
        api('/api/autonomy/directives'),
        api('/api/autonomy/escalation'),
        api('/api/autonomy/triggers'),
    ]);

    const histList = dirData?.history ?? [];
    const activeList = dirData?.active ?? [];
    const s = dirData?.stats ?? {};

    document.getElementById('dir-total').textContent = (histList.length + activeList.length) || s.total || 0;
    document.getElementById('dir-executed').textContent = histList.filter(d => d.status === 'completed').length || s.executed || 0;
    document.getElementById('dir-chained').textContent = histList.filter(d => d.chained_from).length || s.chained || 0;
    const completedCount = histList.filter(d => d.status === 'completed').length;
    document.getElementById('dir-success-rate').textContent = s.success_rate ? (s.success_rate * 100).toFixed(0) + '%' :
        (histList.length > 0 ? Math.round(completedCount / histList.length * 100) + '%' : '\u2014');

    const histEl = document.getElementById('dir-history');
    const allDirs = [...activeList.map(d => ({...d, _status: 'active'})), ...histList];
    if (histEl) {
        if (allDirs.length) {
            histEl.innerHTML = allDirs.map(d => {
                const status = d._status || d.status || 'pending';
                const statusColor = status === 'executed' || status === 'completed' ? 'var(--accent-green)' :
                    status === 'failed' ? 'var(--accent-red)' : status === 'active' ? 'var(--accent-blue)' : 'var(--text-muted)';
                const isChained = !!(d.chained_from || d.parent_id);
                const title = d.title || d.directive || d.content || d.description || '';
                const rationale = d.rationale || d.reasoning || '';
                const outcome = d.outcome || '';
                return `<div style="padding:10px 0;border-bottom:1px solid var(--border);position:relative">
                    <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
                        <span style="color:${statusColor};font-size:11px;background:${statusColor}22;padding:2px 8px;border-radius:10px">${status}</span>
                        ${isChained ? `<span style="font-size:11px;color:var(--accent-cyan);background:var(--accent-cyan)22;padding:2px 6px;border-radius:8px">\u21B3 chained</span>` : ''}
                        <span style="margin-left:auto;font-size:11px;color:var(--text-muted)">${formatTime(d.created_at || d.timestamp)}</span>
                    </div>
                    <div style="font-size:13px;font-weight:500;margin-bottom:3px;line-height:1.4">${escHtml(title)}</div>
                    ${rationale ? `<div style="font-size:12px;color:var(--text-secondary)">${escHtml(rationale.slice(0, 200))}${rationale.length > 200 ? '...' : ''}</div>` : ''}
                    ${outcome ? `<div style="font-size:12px;color:var(--accent-green);margin-top:4px">\u2713 ${escHtml(outcome.slice(0, 150))}</div>` : ''}
                    <button class="btn-sm" style="position:absolute;top:10px;right:0;color:var(--accent-red);font-size:10px" onclick="deleteDirective('${escHtml(d.id || '')}')" title="Delete">✕</button>
                </div>`;
            }).join('');
        } else {
            histEl.innerHTML = '<div class="empty-state">No directives yet — ROOT makes autonomous strategic decisions every 15 minutes</div>';
        }
    }

    // Escalation decisions
    const escEl = document.getElementById('dir-escalation');
    if (escEl && escData && !escData.error) {
        const decisions = escData.recent_decisions || [];
        const escStats = escData.stats || {};
        if (decisions.length) {
            escEl.innerHTML = `
                <div style="font-size:12px;color:var(--text-muted);margin-bottom:8px">
                    Total: ${escStats.total || 0} · Auto: ${escStats.auto_approved || 0} · Escalated: ${escStats.escalated || 0}
                </div>` +
                decisions.map(d => {
                    const wasAuto = d.auto_approved || d.level === 'low';
                    return `<div style="padding:8px 0;border-bottom:1px solid var(--border)">
                        <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
                            <span style="font-size:11px;padding:2px 8px;border-radius:10px;background:${wasAuto ? 'var(--accent-green)22' : 'var(--accent-orange)22'};color:${wasAuto ? 'var(--accent-green)' : 'var(--accent-orange)'}">${wasAuto ? 'auto' : 'escalated'}</span>
                            <span style="font-size:13px;font-weight:500">${escHtml(d.action || d.description || d.id || '')}</span>
                            <span style="margin-left:auto;font-size:11px;color:var(--text-muted)">${formatTime(d.created_at || d.timestamp)}</span>
                        </div>
                        <div style="display:flex;gap:6px;margin-top:4px">
                            <button class="btn-sm" onclick="recordEscalationOutcome('${escHtml(d.id || '')}', true)">👍 Positive</button>
                            <button class="btn-sm" onclick="recordEscalationOutcome('${escHtml(d.id || '')}', false)">👎 Negative</button>
                            <button class="btn-sm" onclick="overrideEscalation('${escHtml(d.id || '')}')">Override</button>
                        </div>
                    </div>`;
                }).join('');
        } else {
            escEl.innerHTML = '<div style="color:var(--text-muted);padding:12px">No escalation decisions yet</div>';
        }
    }

    // Trigger rules
    const trigEl = document.getElementById('dir-triggers');
    if (trigEl && trigData && !trigData.error) {
        const rules = trigData.rules || [];
        if (rules.length) {
            trigEl.innerHTML = rules.map(r => {
                const enabled = r.enabled !== false;
                return `<div style="display:flex;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid var(--border)">
                    <span style="width:8px;height:8px;border-radius:50%;background:${enabled ? 'var(--accent-green)' : 'var(--accent-red)'};flex-shrink:0"></span>
                    <div style="flex:1;min-width:0">
                        <div style="font-size:13px;font-weight:500">${escHtml(r.name || r.id || '')}</div>
                        <div style="font-size:11px;color:var(--text-muted)">${escHtml(r.trigger_type || '')} → ${escHtml(r.action_type || '')} · fired ${r.fire_count || 0}x</div>
                    </div>
                    <button class="btn-sm" onclick="toggleTrigger('${escHtml(r.id || '')}', ${enabled})">${enabled ? 'Disable' : 'Enable'}</button>
                    <button class="btn-sm" onclick="deleteTrigger('${escHtml(r.id || '')}')" title="Delete" style="color:var(--accent-red)">✕</button>
                </div>`;
            }).join('');
        } else {
            trigEl.innerHTML = '<div style="color:var(--text-muted);padding:12px">No trigger rules configured</div>';
        }
    }
}

async function recordEscalationOutcome(recordId, positive) {
    const btn = event?.target;
    try {
        await api(`/api/autonomy/escalation/${recordId}/outcome`, {
            method: 'POST', body: { positive },
        });
        if (btn) { btn.textContent = 'Recorded'; btn.disabled = true; }
    } catch (e) {
        if (btn) { btn.textContent = 'Error'; }
        console.error('recordEscalationOutcome failed:', e);
    }
}

async function overrideEscalation(recordId) {
    const btn = event?.target;
    try {
        await api(`/api/autonomy/escalation/${recordId}/override`, {
            method: 'POST', body: { action: 'user_override' },
        });
        if (btn) { btn.textContent = 'Overridden'; btn.disabled = true; }
    } catch (e) {
        if (btn) { btn.textContent = 'Error'; }
        console.error('overrideEscalation failed:', e);
    }
}

async function toggleTrigger(ruleId, currentlyEnabled) {
    const action = currentlyEnabled ? 'disable' : 'enable';
    await api(`/api/autonomy/triggers/${ruleId}/${action}`, { method: 'POST' });
    loadDirectives();
}

function showCreateDirectiveModal() {
    showModal({
        title: 'Create Strategic Directive',
        fields: [
            { key: 'title', label: 'Title', type: 'text', placeholder: 'Directive title', required: true },
            { key: 'rationale', label: 'Rationale', type: 'textarea', placeholder: 'Why this directive?' },
            { key: 'category', label: 'Category', type: 'select', options: ['trading', 'research', 'learning', 'automation', 'product', 'health', 'general'] },
            { key: 'priority', label: 'Priority (1=critical, 9=background)', type: 'number', min: 1, max: 9, value: 5 },
            { key: 'collab_pattern', label: 'Collaboration Pattern', type: 'select', options: ['delegate', 'pipeline', 'fanout', 'council'] },
            { key: 'task_description', label: 'Task Description', type: 'textarea', placeholder: 'What should the assigned agents do?' },
            { key: 'assigned_agents', label: 'Agents (comma-separated)', type: 'text', placeholder: 'researcher, analyst' },
        ],
        submitLabel: 'Create Directive',
        onSubmit: async (vals) => {
            const agents = vals.assigned_agents ? vals.assigned_agents.split(',').map(a => a.trim()).filter(Boolean) : [];
            await api('/api/autonomy/directives', {
                method: 'POST',
                body: {
                    title: vals.title,
                    rationale: vals.rationale || '',
                    category: vals.category || 'general',
                    priority: parseInt(vals.priority) || 5,
                    collab_pattern: vals.collab_pattern || 'delegate',
                    task_description: vals.task_description || '',
                    assigned_agents: agents,
                },
            });
            closeModal();
            loadDirectives();
        },
    });
}

async function deleteDirective(directiveId) {
    showConfirmModal({
        title: 'Delete Directive',
        message: 'Are you sure you want to delete this directive?',
        danger: true,
        onConfirm: async () => {
            await api(`/api/autonomy/directives/${directiveId}`, { method: 'DELETE' });
            loadDirectives();
        },
    });
}

function showCreateTriggerModal() {
    showModal({
        title: 'Create Trigger Rule',
        fields: [
            { key: 'name', label: 'Name', type: 'text', placeholder: 'Trigger name', required: true },
            { key: 'trigger_type', label: 'Trigger Type', type: 'select', options: ['webhook', 'schedule', 'condition', 'file_watch'] },
            { key: 'action_type', label: 'Action Type', type: 'select', options: ['enqueue', 'delegate', 'proactive', 'custom'] },
            { key: 'config', label: 'Trigger Config (JSON)', type: 'textarea', placeholder: '{"hour": 9, "minute": 0}', value: '{}' },
            { key: 'action_config', label: 'Action Config (JSON)', type: 'textarea', placeholder: '{"goal": "...", "priority": 5}', value: '{}' },
        ],
        submitLabel: 'Create Trigger',
        onSubmit: async (vals) => {
            let config = {}, actionConfig = {};
            try { config = JSON.parse(vals.config || '{}'); } catch (e) { alert('Invalid trigger config JSON'); return; }
            try { actionConfig = JSON.parse(vals.action_config || '{}'); } catch (e) { alert('Invalid action config JSON'); return; }
            await api('/api/autonomy/triggers', {
                method: 'POST',
                body: {
                    name: vals.name,
                    trigger_type: vals.trigger_type || 'webhook',
                    action_type: vals.action_type || 'enqueue',
                    config,
                    action_config: actionConfig,
                },
            });
            closeModal();
            loadDirectives();
        },
    });
}

async function deleteTrigger(ruleId) {
    showConfirmModal({
        title: 'Delete Trigger',
        message: 'Are you sure you want to delete this trigger rule?',
        danger: true,
        onConfirm: async () => {
            await api(`/api/autonomy/triggers/${ruleId}`, { method: 'DELETE' });
            loadDirectives();
        },
    });
}

async function runDirectiveCycle() {
    const btn = document.getElementById('btn-dir-cycle');
    if (btn) { btn.disabled = true; btn.textContent = 'Running...'; }
    try {
        await api('/api/autonomy/directives/cycle', { method: 'POST' });
        await loadDirectives();
    } catch (e) {
        alert('Directive cycle failed: ' + e.message);
    }
    if (btn) { btn.disabled = false; btn.textContent = 'Run Directive Cycle'; }
}

// ── Action Chains Panel ──────────────────────────────────────
async function loadActionChains() {
    const [chains, execs, stats] = await Promise.all([
        api('/api/action-chains'),
        api('/api/action-chains/executions?limit=30'),
        api('/api/action-chains/stats'),
    ]);

    const s = stats?.data || stats || {};
    document.getElementById('chains-total').textContent = s.total_chains || (Array.isArray(chains?.data) ? chains.data.length : 0);
    document.getElementById('chains-executions').textContent = s.total_executions || 0;
    document.getElementById('chains-success').textContent = s.success_rate ? (s.success_rate * 100).toFixed(0) + '%' : '\u2014';
    document.getElementById('chains-active').textContent = s.active_chains || 0;

    const chainData = Array.isArray(chains) ? chains : (chains?.data || chains?.chains || []);
    const chainEl = document.getElementById('chains-list');
    if (chainData.length) {
        chainEl.innerHTML = chainData.map(c => `
            <div class="card" style="margin-bottom:10px">
                <div style="display:flex;justify-content:space-between;align-items:center">
                    <strong>${escHtml(c.name || c.id || '\u2014')}</strong>
                    <div style="display:flex;gap:6px;align-items:center">
                        <span style="font-size:11px;color:var(--text-muted)">${escHtml(c.trigger_action || '')} → ${escHtml(c.follow_up_action || '')}</span>
                        <span style="width:8px;height:8px;border-radius:50%;background:${c.enabled !== false ? 'var(--accent-green)' : 'var(--accent-red)'}"></span>
                        <button class="btn-sm" onclick="triggerChain('${escHtml(c.id || '')}')">Trigger</button>
                        <button class="btn-sm" onclick="deleteChain('${escHtml(c.id || '')}')" style="color:var(--accent-red)" title="Delete">✕</button>
                    </div>
                </div>
                <div style="font-size:12px;color:var(--text-secondary);margin-top:4px">${escHtml(c.description || '')}</div>
                <div style="font-size:11px;color:var(--text-muted);margin-top:6px">
                    Priority: ${c.priority || 0} · Cooldown: ${c.cooldown_minutes || 5}min
                </div>
            </div>`).join('');
    } else {
        chainEl.innerHTML = '<div class="empty-state">No action chains configured</div>';
    }

    const execData = Array.isArray(execs) ? execs : (execs?.data || execs?.executions || []);
    const execEl = document.getElementById('chains-executions-list');
    if (execData.length) {
        execEl.innerHTML = '<div class="table-wrap"><table><thead><tr>' +
            '<th>Chain</th><th>Status</th><th>Steps Done</th><th>Time</th>' +
            '</tr></thead><tbody>' +
            execData.map(e => {
                const col = e.status === 'completed' ? 'var(--accent-green)' : e.status === 'failed' ? 'var(--accent-red)' : 'var(--accent-gold)';
                return `<tr>
                    <td>${escHtml(e.chain_id || e.chain_name || '\u2014')}</td>
                    <td style="color:${col}">${e.status || '\u2014'}</td>
                    <td>${e.steps_completed || 0} / ${e.total_steps || 0}</td>
                    <td>${e.started_at ? formatTime(e.started_at) : '\u2014'}</td>
                </tr>`;
            }).join('') + '</tbody></table></div>';
    } else {
        execEl.innerHTML = '<div class="empty-state">No executions yet</div>';
    }
}

async function triggerChain(chainId) {
    if (!chainId) return;
    try {
        const result = await api(`/api/action-chains/${chainId}/trigger`, { method: 'POST' });
        const msg = result?.message || result?.status || 'Triggered';
        const el = event?.target;
        if (el) { el.textContent = msg; setTimeout(() => { el.textContent = 'Trigger'; }, 2000); }
        setTimeout(() => loadActionChains(), 1500);
    } catch (e) {
        console.error('Chain trigger error:', e);
    }
}

function showCreateChainModal() {
    showModal({
        title: 'Create Action Chain',
        fields: [
            { key: 'trigger_action', label: 'Trigger Action', type: 'text', placeholder: 'e.g. market_scanner', required: true },
            { key: 'follow_up_action', label: 'Follow-up Action', type: 'text', placeholder: 'e.g. auto_trade_cycle', required: true },
            { key: 'description', label: 'Description', type: 'textarea', placeholder: 'What does this chain do?', required: true },
            { key: 'priority', label: 'Priority (0-20)', type: 'number', min: 0, max: 20, value: 5 },
            { key: 'cooldown_minutes', label: 'Cooldown (minutes)', type: 'number', min: 1, max: 1440, value: 5 },
        ],
        submitLabel: 'Create Chain',
        onSubmit: async (vals) => {
            await api('/api/action-chains', {
                method: 'POST',
                body: {
                    trigger_action: vals.trigger_action,
                    follow_up_action: vals.follow_up_action,
                    description: vals.description,
                    priority: parseInt(vals.priority) || 5,
                    cooldown_minutes: parseInt(vals.cooldown_minutes) || 5,
                },
            });
            closeModal();
            loadActionChains();
        },
    });
}

async function deleteChain(chainId) {
    showConfirmModal({
        title: 'Delete Action Chain',
        message: `Delete chain "${chainId}"? This cannot be undone.`,
        danger: true,
        onConfirm: async () => {
            await api(`/api/action-chains/${chainId}`, { method: 'DELETE' });
            loadActionChains();
        },
    });
}

// ── Curiosity Panel ─────────────────────────────────────────
async function loadCuriosity() {
    const [stats, queue, resolved] = await Promise.all([
        api('/api/curiosity/stats'),
        api('/api/curiosity/queue?limit=20'),
        api('/api/curiosity/resolved?limit=20'),
    ]);

    const s = stats?.data ?? stats ?? {};
    const q = (queue?.data ?? queue) || [];
    const r = (resolved?.data ?? resolved) || [];

    document.getElementById('curiosity-cycles').textContent = s.cycles || 0;
    document.getElementById('curiosity-generated').textContent = s.total_questions_generated || 0;
    document.getElementById('curiosity-resolved').textContent = s.total_questions_resolved || 0;
    document.getElementById('curiosity-queue').textContent = s.queue_size || 0;

    const sourceColors = {
        self_assessment: '#f39c12', failed_task: '#e74c3c', knowledge_gap: '#e67e22',
        trending: '#3498db', cross_pollination: '#9b59b6', external: '#2ecc71',
    };

    document.getElementById('curiosity-queue-list').innerHTML = q.length ? q.map(item => `
        <div style="padding:8px 0;border-bottom:1px solid var(--border)">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
                <span style="background:${sourceColors[item.source] || '#666'};color:#fff;padding:2px 8px;border-radius:10px;font-size:11px">${escHtml(item.source)}</span>
                <span style="color:var(--text-secondary);font-size:11px">${escHtml(item.domain)}</span>
                <span style="margin-left:auto;color:var(--text-secondary);font-size:11px">priority: ${(item.priority * 100).toFixed(0)}%</span>
            </div>
            <div style="font-size:13px">${escHtml(item.question)}</div>
        </div>
    `).join('') : '<div style="color:var(--text-secondary);padding:12px">No pending questions — ROOT is satisfied (for now)</div>';

    document.getElementById('curiosity-resolved-list').innerHTML = r.length ? r.map(item => `
        <div style="padding:8px 0;border-bottom:1px solid var(--border)">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
                <span style="background:#2ecc71;color:#fff;padding:2px 8px;border-radius:10px;font-size:11px">learned</span>
                <span style="color:var(--text-secondary);font-size:11px">${escHtml(item.domain)}</span>
            </div>
            <div style="font-size:13px;font-weight:500;margin-bottom:4px">${escHtml(item.question)}</div>
            <div style="font-size:12px;color:var(--text-secondary)">${escHtml(item.resolution || '')}</div>
        </div>
    `).join('') : '<div style="color:var(--text-secondary);padding:12px">Nothing resolved yet — give it a few minutes</div>';
}

async function askCuriosityQuestion() {
    const question = document.getElementById('curiosity-question')?.value?.trim();
    const domain = document.getElementById('curiosity-domain')?.value?.trim() || 'general';
    if (!question) return;
    try {
        await api('/api/curiosity/ask', {
            method: 'POST',
            body: { question, domain, priority: 0.8 },
        });
        document.getElementById('curiosity-question').value = '';
        loadCuriosity();
    } catch (e) {
        console.error('Ask curiosity failed:', e);
    }
}
