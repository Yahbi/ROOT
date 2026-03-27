/* panels-intelligence.js — MiRo, Predictions, Memory, Interest */

// ── Memory ──────────────────────────────────────────────────
async function loadMemories() {
    const [stats, recent] = await Promise.all([
        api('/api/memory/stats'),
        api('/api/memory/recent?limit=50'),
    ]);
    const recentItems = recent?.data ?? recent;
    const totalEl = document.getElementById('memory-total');
    if (totalEl) totalEl.textContent = (stats.total || 0).toLocaleString();

    const typeStats = document.getElementById('memory-type-stats');
    if (typeStats && stats.by_type) {
        const colors = {
            fact: 'var(--accent-blue)', learning: 'var(--accent-purple)',
            observation: 'var(--accent-green)', preference: 'var(--accent-orange)',
            goal: 'var(--accent-pink)', reflection: 'var(--accent-gold)',
            skill: 'var(--accent-cyan)', error: 'var(--accent-red)',
        };
        typeStats.innerHTML = Object.entries(stats.by_type).map(([type, info]) =>
            `<div class="stat-card" style="padding:10px">
                <div class="stat-value" style="font-size:16px;color:${colors[type] || 'var(--accent)'}">${info.count}</div>
                <div class="stat-label">${escHtml(type)}</div>
            </div>`
        ).join('');
    }
    renderMemoryList(document.getElementById('memory-list'), recentItems);
}

async function searchMemories() {
    const q = document.getElementById('memory-search').value.trim();
    if (!q) { await loadMemories(); return; }
    const results = await api('/api/memory/search', { method: 'POST', body: { query: q, limit: 50 } });
    const items = Array.isArray(results) ? results : (results?.data ?? []);
    renderMemoryList(document.getElementById('memory-list'), items);
}

function renderMemoryList(el, items) {
    if (!el) return;
    if (Array.isArray(items) && items.length) {
        el.innerHTML = items.map(m => {
            const pct = Math.round((m.confidence || 0) * 100);
            const clr = pct > 70 ? 'var(--accent-green)' : pct > 40 ? 'var(--accent-orange)' : 'var(--accent-red)';
            const memId = m.id || '';
            return `<div class="memory-item">
                <span class="memory-type-badge">${escHtml(m.memory_type)}</span>
                <div class="memory-content">${escHtml(m.content)}
                    <div class="memory-meta">${escHtml(m.source || '')} &middot; ${formatTime(m.created_at)} &middot; ${m.access_count || 0}x</div>
                </div>
                <div style="display:flex;flex-direction:column;align-items:flex-end;gap:4px;flex-shrink:0">
                    <div class="confidence-bar"><div class="confidence-fill" style="width:${pct}%;background:${clr}"></div></div>
                    ${memId ? `<div style="display:flex;gap:4px">
                        <button class="btn-sm" onclick="strengthenMemory('${escHtml(memId)}')" title="Strengthen">+</button>
                        <button class="btn-sm" onclick="deleteMemory('${escHtml(memId)}')" title="Delete" style="color:var(--accent-red)">×</button>
                    </div>` : ''}
                </div>
            </div>`;
        }).join('');
    } else {
        el.innerHTML = '<div class="empty-state">No memories found.</div>';
    }
}

function showCreateMemoryModal() {
    showModal({
        title: 'Create Memory',
        fields: [
            { key: 'content', label: 'Content', type: 'textarea', placeholder: 'Memory content...', required: true },
            { key: 'memory_type', label: 'Type', type: 'select', options: ['fact', 'learning', 'observation', 'preference', 'goal', 'reflection', 'skill', 'error'], value: 'fact' },
            { key: 'source', label: 'Source', type: 'text', placeholder: 'Source (e.g. manual, research)', value: 'manual' },
            { key: 'tags', label: 'Tags', type: 'tags', placeholder: 'tag1, tag2, tag3' },
            { key: 'confidence', label: 'Confidence', type: 'range', min: 0, max: 100, step: 5, value: 80 },
        ],
        submitLabel: 'Create',
        onSubmit: async (vals) => {
            await api('/api/memory', {
                method: 'POST',
                body: {
                    content: vals.content,
                    memory_type: vals.memory_type,
                    source: vals.source || 'manual',
                    tags: vals.tags || [],
                    confidence: vals.confidence / 100,
                },
            });
            closeModal();
            loadMemories();
        },
    });
}

async function strengthenMemory(memoryId) {
    if (!memoryId) return;
    const btn = event?.target;
    if (btn) { btn.disabled = true; }
    try {
        await api(`/api/memory/${memoryId}/strengthen`, { method: 'POST' });
        if (btn) { btn.textContent = '✓'; }
        setTimeout(() => loadMemories(), 500);
    } catch (e) {
        if (btn) { btn.textContent = '+'; btn.disabled = false; }
    }
}

async function deleteMemory(memoryId) {
    if (!memoryId) return;
    showConfirmModal({
        title: 'Delete Memory',
        message: 'Are you sure you want to delete this memory?',
        danger: true,
        confirmLabel: 'Delete',
        onConfirm: async () => {
            await api(`/api/memory/${memoryId}`, { method: 'DELETE' });
            closeModal();
            loadMemories();
        },
    });
}

// ── Interest Assessment ─────────────────────────────────────
async function loadInterest() {
    const [stats, historyRaw] = await Promise.all([api('/api/interest/stats'), api('/api/interest/history?limit=20')]);
    const history = Array.isArray(historyRaw) ? historyRaw : (historyRaw?.data ?? []);
    const te = document.getElementById('interest-total');
    if (te) te.textContent = stats.total_assessments || 0;
    const ae = document.getElementById('interest-aligned');
    if (ae) ae.textContent = (stats.aligned_pct || 0) + '%';
    const av = document.getElementById('interest-avg');
    if (av) av.textContent = (stats.avg_score || 0).toFixed(2);
    const historyEl = document.getElementById('interest-history');
    if (!historyEl) return;
    if (Array.isArray(history) && history.length) {
        historyEl.innerHTML = history.map(a => `
            <div style="padding:10px 0;border-bottom:1px solid var(--border)">
                <div style="display:flex;justify-content:space-between;align-items:center">
                    <span style="font-weight:600;font-size:13px">${escHtml(a.subject)}</span>
                    <span class="verdict-badge verdict-${escHtml(a.verdict)}">${escHtml(a.verdict.replace(/_/g, ' '))}</span>
                </div>
                <div style="font-size:12px;color:var(--text-secondary);margin-top:4px">${escHtml(a.recommendation || '')}</div>
                <div class="score-meter"><div class="score-meter-fill" style="width:${Math.round((a.score + 1) / 2 * 100)}%;background:${a.score > 0.2 ? 'var(--accent-green)' : a.score > -0.1 ? 'var(--accent-gold)' : 'var(--accent-red)'}"></div></div>
                <div style="font-size:10px;color:var(--text-muted)">${formatTime(a.timestamp)}</div>
            </div>
        `).join('');
    } else {
        historyEl.innerHTML = '<div class="empty-state">No assessments yet.</div>';
    }
}

async function assessInterest(useLlm) {
    const subject = document.getElementById('interest-subject').value.trim();
    if (!subject) return;
    const resultEl = document.getElementById('interest-result');
    if (!resultEl) return;
    resultEl.innerHTML = '<div style="text-align:center;padding:20px"><span class="spinner"></span> Assessing...</div>';
    const body = {
        subject,
        context: document.getElementById('interest-context').value.trim(),
        financial_impact: parseFloat(document.getElementById('interest-financial').value) || 0,
        time_cost_hours: parseFloat(document.getElementById('interest-time').value) || 0,
        risk_level: document.getElementById('interest-risk').value,
        use_llm: useLlm,
    };
    const data = await api('/api/interest/assess', { method: 'POST', body });
    if (data.error) { resultEl.innerHTML = `<div class="card" style="border-color:var(--accent-red)"><p style="color:var(--accent-red)">${escHtml(data.error)}</p></div>`; return; }
    const scoreColor = data.score > 0.2 ? 'var(--accent-green)' : data.score > -0.1 ? 'var(--accent-gold)' : 'var(--accent-red)';
    const scorePct = Math.round((data.score + 1) / 2 * 100);
    resultEl.innerHTML = `
        <div class="card" style="border-color:${scoreColor}30;margin-top:12px">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
                <span class="verdict-badge verdict-${escHtml(data.verdict)}">${escHtml(data.verdict.replace(/_/g, ' '))}</span>
                <span style="font-size:22px;font-weight:800;color:${scoreColor}">${data.score > 0 ? '+' : ''}${data.score.toFixed(2)}</span>
            </div>
            <div class="score-meter" style="margin-bottom:16px"><div class="score-meter-fill" style="width:${scorePct}%;background:${scoreColor}"></div></div>
            <p style="font-size:14px;font-weight:600;margin-bottom:8px">${escHtml(data.recommendation)}</p>
            <div style="font-size:13px;color:var(--text-secondary);margin-bottom:12px">${escHtml(data.reasoning)}</div>
        </div>`;
    loadInterest();
}

// ── MiRo Panel ──────────────────────────────────────────────
async function loadMiro() {
    const [stats, preds, calib, collab] = await Promise.all([
        api('/api/predictions/stats'),
        api('/api/predictions?limit=20'),
        api('/api/predictions/calibration'),
        api('/api/autonomous/collab/history?limit=5'),
    ]);

    const s = stats?.data ?? stats ?? {};
    const hitRate = (s.hit_rate || 0);
    const hitPct = (hitRate * 100).toFixed(0);
    const pending = s.pending || 0;
    _setText('miro-total', s.total_predictions || 0);
    _setText('miro-hitrate', hitPct + '%');
    _setText('miro-pending', pending);
    _setText('miro-resolved', s.resolved || 0);

    // Accuracy highlight banner
    const bannerEl = document.getElementById('miro-accuracy-banner');
    if (bannerEl) {
        const accColor = hitRate >= 0.7 ? 'var(--accent-green)' : hitRate >= 0.5 ? 'var(--accent-gold)' : 'var(--accent-red)';
        const trend = s.accuracy_trend || s.trend || null;
        const trendArrow = trend === 'improving' ? ' &#9650;' : trend === 'declining' ? ' &#9660;' : '';
        const trendColor = trend === 'improving' ? 'var(--accent-green)' : trend === 'declining' ? 'var(--accent-red)' : 'var(--text-muted)';
        bannerEl.innerHTML = `<div class="card" style="margin-bottom:16px;border-left:3px solid ${accColor};display:flex;align-items:center;gap:16px;flex-wrap:wrap">
            <div style="display:flex;align-items:center;gap:10px">
                <div style="font-size:28px;font-weight:800;color:${accColor}">${hitPct}%</div>
                <div>
                    <div style="font-size:12px;font-weight:600;color:var(--text-primary)">Prediction Accuracy</div>
                    <div style="font-size:11px;color:var(--text-muted)">${s.resolved || 0} resolved · ${s.total_predictions || 0} total</div>
                </div>
                ${trendArrow ? `<span style="font-size:14px;color:${trendColor}">${trendArrow}</span>` : ''}
            </div>
            ${pending > 0 ? `<div style="margin-left:auto;text-align:center;background:var(--accent-blue)11;padding:8px 16px;border-radius:8px">
                <div style="font-size:20px;font-weight:800;color:var(--accent-blue)">${pending}</div>
                <div style="font-size:10px;color:var(--accent-blue);text-transform:uppercase;font-weight:600">Open Bets</div>
            </div>` : ''}
        </div>`;
    }

    // Latest council verdict card
    const verdictEl = document.getElementById('miro-latest-verdict');
    if (verdictEl) {
        const latestDebate = collab?.data?.[0] ?? (Array.isArray(collab) ? collab[0] : null);
        if (latestDebate) {
            const verdict = latestDebate.result || latestDebate.verdict || latestDebate.task || '';
            verdictEl.innerHTML = `<div class="card" style="margin-bottom:16px;border-left:3px solid var(--accent-purple)">
                <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
                    <span style="font-weight:700;font-size:12px;color:var(--accent-purple)">Latest Council Verdict</span>
                    <span style="font-size:10px;color:var(--text-muted)">${formatTime(latestDebate.created_at || latestDebate.timestamp || '')}</span>
                </div>
                <div style="font-size:13px;color:var(--text-primary);line-height:1.5">${escHtml((verdict).slice(0, 300))}${verdict.length > 300 ? '...' : ''}</div>
                ${latestDebate.participants ? `<div style="font-size:10px;color:var(--text-muted);margin-top:6px">Agents: ${escHtml(latestDebate.participants.join(', '))}</div>` : ''}
            </div>`;
        } else {
            verdictEl.innerHTML = '';
        }
    }

    const bySource = s.by_source || {};
    const srcEl = document.getElementById('miro-sources');
    if (srcEl) {
        if (Object.keys(bySource).length) {
            srcEl.innerHTML = Object.entries(bySource).map(([src, info]) => {
                const hitRate = info.total > 0 ? ((info.hits / info.total) * 100).toFixed(0) : 0;
                const color = hitRate >= 70 ? 'var(--accent-green)' : hitRate >= 50 ? 'var(--accent-gold)' : 'var(--accent-red)';
                return `<div style="display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid var(--border)">
                    <div style="flex:1">
                        <div style="font-weight:600;font-size:13px;text-transform:capitalize">${escHtml(src)}</div>
                        <div style="font-size:11px;color:var(--text-muted)">${info.total} predictions · ${info.hits || 0} hits · ${info.misses || 0} misses</div>
                    </div>
                    <div style="text-align:right">
                        <div style="font-size:16px;font-weight:700;color:${color}">${hitRate}%</div>
                        <div style="font-size:11px;color:var(--text-muted)">accuracy</div>
                    </div>
                    <div style="width:60px;height:6px;background:var(--bg-elevated);border-radius:3px">
                        <div style="width:${hitRate}%;height:100%;background:${color};border-radius:3px"></div>
                    </div>
                </div>`;
            }).join('');
        } else {
            srcEl.innerHTML = '<div style="color:var(--text-muted);padding:12px;text-align:center">No source calibration data yet — MiRo is making its first predictions</div>';
        }
    }

    const predList = (preds?.predictions ?? preds?.data ?? []);
    const predEl = document.getElementById('miro-predictions');
    if (predEl) {
        if (predList.length) {
            predEl.innerHTML = predList.map(p => {
                const conf = Math.round((p.confidence || 0) * 100);
                const confColor = conf >= 80 ? 'var(--accent-green)' : conf >= 60 ? 'var(--accent-gold)' : 'var(--accent-orange)';
                const statusColor = p.status === 'resolved_hit' ? 'var(--accent-green)' :
                    p.status === 'resolved_miss' ? 'var(--accent-red)' : 'var(--accent-blue)';
                const statusLabel = p.status === 'resolved_hit' ? '\u2713 Hit' :
                    p.status === 'resolved_miss' ? '\u2717 Miss' : '\u22EF Pending';
                const isPending = !p.status || p.status === 'pending';
                const deadlineDays = p.deadline_at ? Math.ceil((new Date(p.deadline_at) - Date.now()) / 86400000) : null;
                return `<div style="padding:10px 0;border-bottom:1px solid var(--border)">
                    <div style="display:flex;align-items:flex-start;gap:8px;margin-bottom:4px">
                        <span style="background:${statusColor}22;color:${statusColor};padding:2px 8px;border-radius:10px;font-size:11px;white-space:nowrap">${statusLabel}</span>
                        <span style="font-size:11px;color:var(--text-muted);white-space:nowrap">
                            ${escHtml(p.source || 'unknown')} ·
                            <span style="color:${confColor}">${conf}% conf</span>
                            ${deadlineDays !== null ? ` · ${deadlineDays > 0 ? deadlineDays + 'd left' : Math.abs(deadlineDays) + 'd ago'}` : ''}
                        </span>
                        ${isPending && p.id ? `<button class="btn-sm" style="margin-left:auto" onclick="showResolvePrediction('${escHtml(p.id)}')">Resolve</button>` : ''}
                    </div>
                    <div style="font-size:13px;line-height:1.4">${escHtml(p.prediction || p.content || '')}</div>
                    ${p.reasoning ? `<div style="font-size:12px;color:var(--text-secondary);margin-top:4px;font-style:italic">${escHtml(p.reasoning.slice(0, 150))}${p.reasoning.length > 150 ? '\u2026' : ''}</div>` : ''}
                </div>`;
            }).join('');
        } else {
            predEl.innerHTML = '<div style="color:var(--text-muted);padding:20px;text-align:center">No predictions yet — ask MiRo to analyze a situation</div>';
        }
    }

    const collabList = collab?.data ?? collab ?? [];
    const collabEl = document.getElementById('miro-council-history');
    if (collabEl) {
        if (collabList.length) {
            collabEl.innerHTML = collabList.map(c => {
                const participants = (c.participants || []).join(', ');
                const pattern = c.pattern || c.collaboration_pattern || 'council';
                return `<div style="padding:8px 0;border-bottom:1px solid var(--border)">
                    <div style="display:flex;align-items:center;gap:8px;margin-bottom:3px">
                        <span style="font-size:11px;background:var(--bg-elevated);padding:2px 6px;border-radius:4px;color:var(--accent)">${pattern}</span>
                        <span style="font-size:11px;color:var(--text-muted)">${formatTime(c.created_at || c.timestamp)}</span>
                    </div>
                    <div style="font-size:12px;font-weight:500">${escHtml(c.task || c.topic || c.description || '')}</div>
                    ${participants ? `<div style="font-size:11px;color:var(--text-muted);margin-top:2px">Participants: ${escHtml(participants)}</div>` : ''}
                </div>`;
            }).join('');
        } else {
            collabEl.innerHTML = '<div style="color:var(--text-muted);padding:12px">No debates yet — trigger a council below</div>';
        }
    }
}

let _miroDebating = false;
async function triggerMiroCouncil() {
    if (_miroDebating) return;
    const topic = document.getElementById('miro-topic')?.value?.trim();
    if (!topic) { alert('Enter a topic for the council debate'); return; }
    _miroDebating = true;
    const btn = document.getElementById('btn-miro-council');
    if (btn) { btn.disabled = true; btn.textContent = 'Debating...'; }
    const resultEl = document.getElementById('miro-council-result');
    if (resultEl) {
        resultEl.innerHTML = '<div style="color:var(--accent);padding:12px;text-align:center">MiRo is convening the council... <span class="thinking-dots"><span></span><span></span><span></span></span></div>';
    }
    try {
        const data = await api('/api/autonomous/council', {
            method: 'POST',
            body: { topic, agents: ['miro', 'swarm', 'researcher', 'analyst'] },
        });
        if (resultEl) {
            const consensus = data.consensus || data.result || '';
            const perspectives = data.perspectives || data.responses || [];
            resultEl.innerHTML = `
                <div style="margin-bottom:12px">
                    <div style="font-weight:600;color:var(--accent);margin-bottom:6px">Council Consensus</div>
                    <div style="font-size:13px;line-height:1.6;color:var(--text-primary)">${renderMarkdown(consensus)}</div>
                </div>
                ${perspectives.length ? `
                <div>
                    <div style="font-weight:600;color:var(--text-secondary);margin-bottom:6px;font-size:12px">Agent Perspectives</div>
                    ${perspectives.map(p => `
                        <div style="padding:8px;background:var(--bg-elevated);border-radius:6px;margin-bottom:6px">
                            <div style="font-weight:500;font-size:12px;color:var(--accent);margin-bottom:4px">${escHtml(p.agent || p.name || '')}</div>
                            <div style="font-size:12px;color:var(--text-secondary)">${escHtml((p.response || p.perspective || '').slice(0, 300))}${(p.response || '').length > 300 ? '...' : ''}</div>
                        </div>
                    `).join('')}
                </div>` : ''}`;
        }
        await loadMiro();
    } catch (e) {
        if (resultEl) resultEl.innerHTML = `<div style="color:var(--accent-red);padding:12px">Council failed: ${escHtml(e.message)}</div>`;
    }
    _miroDebating = false;
    if (btn) { btn.disabled = false; btn.textContent = 'Convene Council'; }
}

function showResolvePrediction(predictionId) {
    showModal({
        title: 'Resolve Prediction',
        fields: [
            { key: 'outcome', label: 'Outcome', type: 'select', options: [
                { value: 'correct', label: 'Correct (Hit)' },
                { value: 'incorrect', label: 'Incorrect (Miss)' },
            ], required: true },
            { key: 'notes', label: 'Resolution Notes', type: 'textarea', placeholder: 'What actually happened?' },
        ],
        submitLabel: 'Resolve',
        onSubmit: async (vals) => {
            await api(`/api/predictions/${predictionId}/resolve`, {
                method: 'POST',
                body: { outcome: vals.outcome, notes: vals.notes || '' },
            });
            closeModal();
            loadMiro();
        },
    });
}

// ── Predictions Panel ────────────────────────────────────────
async function loadPredictions() {
    const [stats, preds, calibration] = await Promise.all([
        api('/api/predictions/stats'),
        api('/api/predictions?limit=50'),
        api('/api/predictions/calibration'),
    ]);

    const s = stats?.data || stats || {};
    document.getElementById('pred-total').textContent = s.total || 0;
    document.getElementById('pred-pending').textContent = s.pending || 0;
    document.getElementById('pred-hitrate').textContent =
        s.resolved > 0 ? ((s.correct || 0) / s.resolved * 100).toFixed(1) + '%' : '\u2014';
    document.getElementById('pred-resolved').textContent = s.resolved || 0;

    const calEl = document.getElementById('pred-calibration');
    const calData = Array.isArray(calibration) ? calibration : (calibration?.data || []);
    if (calData.length) {
        calEl.innerHTML = '<div class="table-wrap"><table><thead><tr>' +
            '<th>Source</th><th>Predictions</th><th>Hit Rate</th><th>Avg Confidence</th><th>Score</th>' +
            '</tr></thead><tbody>' +
            calData.map(c => {
                const rate = c.hit_rate || 0;
                const color = rate >= 0.6 ? 'var(--accent-green)' : rate >= 0.4 ? 'var(--accent-gold)' : 'var(--accent-red)';
                return `<tr>
                    <td><strong>${escHtml(c.source || c.agent || '\u2014')}</strong></td>
                    <td>${c.total || c.count || 0}</td>
                    <td style="color:${color}">${(rate * 100).toFixed(1)}%</td>
                    <td>${c.avg_confidence ? (c.avg_confidence * 100).toFixed(0) + '%' : '\u2014'}</td>
                    <td>${c.calibration_score ? c.calibration_score.toFixed(3) : '\u2014'}</td>
                </tr>`;
            }).join('') + '</tbody></table></div>';
    } else {
        calEl.innerHTML = '<div class="empty-state">No calibration data yet</div>';
    }

    const listEl = document.getElementById('pred-list');
    const predData = Array.isArray(preds) ? preds : (preds?.data || preds?.predictions || []);
    if (predData.length) {
        listEl.innerHTML = '<div class="table-wrap"><table><thead><tr>' +
            '<th>Prediction</th><th>Source</th><th>Confidence</th><th>Status</th><th>Deadline</th><th>Action</th>' +
            '</tr></thead><tbody>' +
            predData.map(p => {
                const statusColors = { pending: 'var(--accent-blue)', correct: 'var(--accent-green)', incorrect: 'var(--accent-red)', expired: 'var(--text-muted)', resolved_hit: 'var(--accent-green)', resolved_miss: 'var(--accent-red)' };
                const col = statusColors[p.status] || 'var(--text-muted)';
                const isPending = !p.status || p.status === 'pending';
                return `<tr>
                    <td style="max-width:280px;overflow:hidden;text-overflow:ellipsis">${escHtml((p.prediction || p.text || '\u2014').slice(0, 100))}</td>
                    <td>${escHtml(p.source || '\u2014')}</td>
                    <td>${p.confidence ? (p.confidence * 100).toFixed(0) + '%' : '\u2014'}</td>
                    <td><span style="color:${col}">${p.status || '\u2014'}</span></td>
                    <td>${p.deadline ? formatTime(p.deadline) : '\u2014'}</td>
                    <td>${isPending && p.id ? `<button class="btn-sm" onclick="showResolvePrediction('${escHtml(p.id)}')">Resolve</button>` : '\u2014'}</td>
                </tr>`;
            }).join('') + '</tbody></table></div>';
    } else {
        listEl.innerHTML = '<div class="empty-state">No predictions recorded yet</div>';
    }
}

async function recordPrediction() {
    const text = document.getElementById('pred-input')?.value?.trim();
    const source = document.getElementById('pred-source')?.value || 'manual';
    const conf = parseFloat(document.getElementById('pred-confidence')?.value || '0.7');
    const deadline = document.getElementById('pred-deadline')?.value;
    if (!text) return;
    const btn = document.getElementById('btn-pred-submit');
    btn.disabled = true; btn.textContent = 'Recording...';
    try {
        await api('/api/predictions', { method: 'POST', body: JSON.stringify({
            prediction: text, source, confidence: conf,
            deadline: deadline || null,
        }) });
        document.getElementById('pred-input').value = '';
        btn.textContent = 'Recorded!';
        setTimeout(() => { btn.disabled = false; btn.textContent = 'Record'; }, 2000);
        loadPredictions();
    } catch (e) {
        btn.disabled = false; btn.textContent = 'Error — retry';
    }
}
