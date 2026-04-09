/* ROOT v1.1.0 — Core: state, API, WebSocket, nav, theme, chat, streaming, utilities */
/* Panel loaders split into: panels-system.js, panels-agents.js, panels-autonomy.js,
   panels-trading.js, panels-intelligence.js */

const API = '';
const state = { activePanel: 'chat', loading: false, agents: [], theme: 'nebula' };
const messageQueue = [];
let processingQueue = false;

// ── HTML Sanitization ──────────────────────────────────────
// Use sanitizeHTML() instead of raw innerHTML for any user/agent content
function sanitizeHTML(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
function safeSetHTML(el, html) {
    // For trusted HTML (our own templates) — strips script tags and event handlers
    if (!el) return;
    const cleaned = html
        .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')
        .replace(/\bon\w+\s*=\s*["'][^"']*["']/gi, '')
        .replace(/javascript\s*:/gi, '');
    el.innerHTML = cleaned;
}

// Dynamic unique colors per agent — golden angle for max visual separation
const _agentColorCache = {};
let _agentColorIndex = 0;
function getAgentColor(agentId) {
    // Sync from Neural Galaxy if available
    if (window._neuralAgentColors && window._neuralAgentColors[agentId]) {
        _agentColorCache[agentId] = window._neuralAgentColors[agentId];
        return _agentColorCache[agentId];
    }
    if (_agentColorCache[agentId]) return _agentColorCache[agentId];
    const hue = (_agentColorIndex * 137.508) % 360;
    const sat = 65 + (_agentColorIndex % 3) * 10;
    const lit = 55 + (_agentColorIndex % 4) * 5;
    _agentColorIndex++;
    const color = `hsl(${hue.toFixed(0)}, ${sat}%, ${lit}%)`;
    _agentColorCache[agentId] = color;
    return color;
}

// Legacy compat — still used in process cards
const AGENT_COLORS = new Proxy({}, { get: (_, id) => getAgentColor(id) });

// ── Mobile Menu ──────────────────────────────────────────────
function toggleMobileMenu() {
    const sidebar = document.querySelector('.sidebar');
    const overlay = document.querySelector('.mobile-overlay');
    sidebar.classList.toggle('open');
    overlay.classList.toggle('active');
}

const AGENT_ICONS = {
    astra: 'A', root: 'R', hermes: 'H', miro: 'M', swarm: 'S',
    builder: 'B', researcher: 'Rs', coder: 'C', writer: 'W',
    analyst: 'An', guardian: 'G',
};

// ── WebSocket Manager ──────────────────────────────────────
const ws = {
    conn: null,
    reconnectDelay: 1000,
    maxReconnectDelay: 30000,
    handlers: {},
    connected: false,

    connect() {
        const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const url = `${proto}//${location.host}/api/ws`;
        try {
            this.conn = new WebSocket(url);
        } catch (e) {
            console.warn('WebSocket connection failed:', e);
            this._scheduleReconnect();
            return;
        }

        this.conn.onopen = () => {
            this.connected = true;
            this.reconnectDelay = 1000;
            console.log('WebSocket connected');
            // Subscribe to ALL topics for full Neural Galaxy + dashboard coverage
            this.conn.send(JSON.stringify({
                subscribe: [
                    'system.*', 'agent.*', 'collab.*', 'network.*',
                    'memory.*', 'goal.*', 'trade.*', 'prediction.*',
                    'experiment.*', 'directive.*', 'cost.*', 'skill.*',
                    'sandbox.*', 'experience.*', 'approval.*', 'revenue.*',
                    'plugin.*', 'intelligence.*', 'swarm.*', 'research.*'
                ]
            }));
            this._updateStatus(true);
        };

        this.conn.onmessage = (evt) => {
            try {
                const msg = JSON.parse(evt.data);
                if (msg.type === 'event') {
                    this._dispatch(msg.topic, msg.data);
                }
            } catch (e) {
                console.warn('WebSocket parse error:', e);
            }
        };

        this.conn.onclose = () => {
            this.connected = false;
            this._updateStatus(false);
            this._scheduleReconnect();
        };

        this.conn.onerror = () => {
            this.connected = false;
        };

        // Heartbeat every 30s (clear previous to prevent leaks on reconnect)
        if (this._heartbeat) clearInterval(this._heartbeat);
        this._heartbeat = setInterval(() => {
            if (this.conn && this.conn.readyState === WebSocket.OPEN) {
                this.conn.send(JSON.stringify({ ping: true }));
            }
        }, 30000);
    },

    _scheduleReconnect() {
        setTimeout(() => {
            if (!this.connected) {
                this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxReconnectDelay);
                this.connect();
            }
        }, this.reconnectDelay);
    },

    _updateStatus(online) {
        const gs = document.getElementById('global-status');
        if (gs) gs.classList.toggle('offline', !online);
        const mt = document.getElementById('mode-text');
        if (mt) mt.textContent = online ? 'Live' : 'Reconnecting...';
    },

    on(topic, handler) {
        if (!this.handlers[topic]) this.handlers[topic] = [];
        this.handlers[topic].push(handler);
    },

    _dispatch(topic, data) {
        // Exact match handlers
        const exact = this.handlers[topic] || [];
        exact.forEach(h => h(data, topic));
        // Wildcard handlers
        Object.keys(this.handlers).forEach(pattern => {
            if (pattern.endsWith('.*')) {
                const prefix = pattern.slice(0, -2);
                if (topic.startsWith(prefix + '.') || topic === prefix) {
                    this.handlers[pattern].forEach(h => h(data, topic));
                }
            }
        });
    }
};

// ── Streaming Chat Helper ──────────────────────────────────
async function _processMessageStreaming(msg) {
    state.loading = true;
    document.getElementById('btn-send').disabled = true;

    const qs = document.getElementById('quick-suggestions');
    if (qs) qs.style.display = 'none';
    document.querySelectorAll('.followup-chips').forEach(el => el.remove());
    const wm = document.querySelector('.welcome-msg');
    if (wm) wm.style.display = 'none';

    if (!processingQueue) {
        appendMsg('user', 'Yohan', msg);
    }
    const indicators = document.querySelectorAll('.queue-indicator');
    if (indicators.length > 0 && processingQueue) indicators[0].remove();

    const thinkId = appendThinking();
    const startTime = Date.now();
    let responseText = '';
    let msgEl = null;
    let msgId = null;
    let agentFindings = [];
    let routeInfo = null;

    try {
        const modePrefix = MODE_PROMPTS[_currentMode] || '';
        const resp = await fetch('/api/chat/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: modePrefix + msg,
                model_tier: _currentModelTier !== 'default' ? _currentModelTier : undefined,
            }),
        });

        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            let eventType = null;
            for (const line of lines) {
                if (line.startsWith('event: ')) {
                    eventType = line.slice(7).trim();
                } else if (line.startsWith('data: ') && eventType) {
                    const data = JSON.parse(line.slice(6));
                    _handleStreamEvent(eventType, data, thinkId, startTime, {
                        get responseText() { return responseText; },
                        set responseText(v) { responseText = v; },
                        get msgEl() { return msgEl; },
                        set msgEl(v) { msgEl = v; },
                        get msgId() { return msgId; },
                        set msgId(v) { msgId = v; },
                        agentFindings,
                        get routeInfo() { return routeInfo; },
                        set routeInfo(v) { routeInfo = v; },
                    });
                    eventType = null;
                }
            }
        }
    } catch (e) {
        const thinkEl = document.getElementById(thinkId);
        if (thinkEl) thinkEl.remove();
        if (!msgId) {
            appendMsg('assistant', 'ROOT', `Connection error: ${e.message}`);
        }
    }

    state.loading = false;
    document.getElementById('btn-send').disabled = false;
    scrollChat();

    if (messageQueue.length > 0) {
        const next = messageQueue.shift();
        updateQueueBadge();
        processingQueue = true;
        setTimeout(() => _processMessage(next.msg, next.file), 300);
    } else {
        processingQueue = false;
    }
}

function _handleStreamEvent(type, data, thinkId, startTime, ctx) {
    const thinkEl = document.getElementById(thinkId);

    switch (type) {
        case 'thinking':
            if (thinkEl) {
                const label = thinkEl.querySelector('.thinking-label');
                if (label) {
                    label.textContent = data.stage === 'routing' ? 'Routing' : 'Synthesizing';
                }
            }
            break;

        case 'routing':
            ctx.routeInfo = data;
            if (thinkEl) {
                const bar = thinkEl.querySelector('.thinking-bar-fill');
                if (bar) bar.style.width = '40%';
                const label = thinkEl.querySelector('.thinking-label');
                if (label) label.textContent = 'Dispatching';
            }
            break;

        case 'agent_start': {
            if (thinkEl) {
                const agentId = data.agent_id || 'root';
                const agentName = getAgentName(agentId);
                const agentColor = getAgentColor(agentId);
                const initial = (AGENT_ICONS[agentId] || agentName[0] || 'A').toString()[0].toUpperCase();
                const avatar = thinkEl.querySelector('.msg-avatar');
                if (avatar) { avatar.textContent = initial; avatar.style.background = agentColor; }
                const nameEl = thinkEl.querySelector('.msg-name');
                if (nameEl) nameEl.textContent = agentName;
                const bar = thinkEl.querySelector('.thinking-bar-fill');
                if (bar) { bar.style.width = '70%'; bar.style.background = agentColor; }
                const label = thinkEl.querySelector('.thinking-label');
                if (label) { label.textContent = escHtml(agentName); label.style.color = agentColor; }
            }
            break;
        }

        case 'agent_result':
            ctx.agentFindings.push(data);
            break;

        case 'token':
            // First token — remove thinking, create message element
            if (!ctx.msgEl) {
                if (thinkEl) thinkEl.remove();
                ctx.msgId = appendMsg('assistant', 'ROOT', '', false, 'root');
                ctx.msgEl = document.getElementById(ctx.msgId);
            }
            ctx.responseText += data.text;
            if (ctx.msgEl) {
                const contentEl = ctx.msgEl.querySelector('.msg-content');
                if (contentEl) contentEl.innerHTML = renderMarkdown(ctx.responseText);
            }
            scrollChat();
            break;

        case 'done':
            if (thinkEl) thinkEl.remove();
            const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);

            // Show process card if agents were used
            if (data.agents_used && data.agents_used.length > 0) {
                appendProcessCard(data, elapsed);
            }

            // Create or update the final message
            if (!ctx.msgEl) {
                const agentId = data.agent_id || 'root';
                const agentName = getAgentName(agentId);
                ctx.msgId = appendMsg('assistant', agentName, data.content || '', false, agentId);
                ctx.msgEl = document.getElementById(ctx.msgId);
            } else {
                // Update with final content
                const contentEl = ctx.msgEl.querySelector('.msg-content');
                if (contentEl) contentEl.innerHTML = renderMarkdown(data.content || ctx.responseText);
            }

            // Add route badge
            if (data.route && data.route !== 'direct' && ctx.msgEl) {
                const badge = document.createElement('span');
                badge.className = `msg-route-badge ${data.route}`;
                badge.textContent = data.route === 'multi' ? 'Multi-Agent' : 'Delegated';
                const header = ctx.msgEl.querySelector('.msg-header');
                if (header) header.appendChild(badge);
            }

            // Add process footer
            if (ctx.msgEl) {
                const tokenEst = Math.round((data.content || '').length / 4);
                addProcessFooter(ctx.msgEl, data, elapsed, tokenEst);
            }
            // Auto-open artifacts panel if response contains code blocks
            if (data.content) _checkForArtifacts(data.content);
            // Generate session title after first exchange
            if (data.session_id && !_activeChatSession) {
                _activeChatSession = data.session_id;
                const firstMsg = document.querySelector('#chat-scroll .msg.user .msg-content')?.textContent || '';
                _generateSessionTitle(data.session_id, firstMsg);
            }
            // Smart follow-up suggestions (Perplexity-style)
            if (data.content) _showFollowUpSuggestions(data.content);
            scrollChat();
            break;
    }
}

// ── API Helper ──────────────────────────────────────────────
async function api(path, opts = {}) {
    const config = { headers: { 'Content-Type': 'application/json' }, ...opts };
    if (opts.body && typeof opts.body === 'object') config.body = JSON.stringify(opts.body);
    try {
        const resp = await fetch(`${API}${path}`, config);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return await resp.json();
    } catch (e) {
        console.error(`API error: ${path}`, e);
        return { error: e.message };
    }
}

// ── Theme ───────────────────────────────────────────────────
const THEME_DOTS = {
    nebula: '#2a9d8f',
    dark: '#00d4ff',
    claude: '#da7756',
    midnight: '#4a9eff',
    light: '#e0e0de',
};

function setTheme(theme) {
    state.theme = theme;
    document.documentElement.setAttribute('data-theme', theme);
    document.querySelectorAll('.theme-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.theme === theme);
    });
    document.querySelectorAll('.theme-opt').forEach(b => {
        b.classList.toggle('active', b.dataset.theme === theme);
    });
    const dot = document.getElementById('theme-picker-dot');
    if (dot) dot.style.background = THEME_DOTS[theme] || '#888';
    try { localStorage.setItem('root-theme-v2', theme); } catch {}
}

function pickTheme(theme) {
    setTheme(theme);
    toggleThemePicker(false);
}

function toggleThemePicker(force) {
    const dd = document.getElementById('theme-picker-dropdown');
    if (!dd) return;
    const open = force !== undefined ? force : !dd.classList.contains('open');
    dd.classList.toggle('open', open);
}

// Close theme picker on outside click
document.addEventListener('click', e => {
    const wrap = document.getElementById('theme-picker-wrap');
    if (wrap && !wrap.contains(e.target)) {
        toggleThemePicker(false);
    }
});

// ── Navigation ──────────────────────────────────────────────
function switchPanel(panel) {
    state.activePanel = panel;
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    document.querySelectorAll('.channel-item').forEach(n => n.classList.remove('active'));
    const el = document.getElementById(`panel-${panel}`);
    if (el) el.classList.add('active');
    const nav = document.querySelector(`.nav-item[data-panel="${panel}"]`);
    if (nav) nav.classList.add('active');
    const chan = document.querySelector(`.channel-item[data-panel="${panel}"]`);
    if (chan) chan.classList.add('active');

    const titles = {
        chat: ['ROOT', 'Personal AI System'],
        dashboard: ['Dashboard', 'System Overview'],
        memory: ['Memory', 'Persistent Knowledge Store'],
        skills: ['Skills', 'Capability Library'],
        agents: ['Agents', '162+ Agent Civilization'],
        plugins: ['Plugins', 'Tool Ecosystem'],
        interest: ['Interest', 'Decision Assessment'],
        money: ['Strategies', 'Money Strategy Council'],
        builder: ['Builder', 'Self-Improvement Engine'],
        evolution: ['Evolution', 'Growth Timeline'],
        reflections: ['Reflections', 'Introspective Insights'],
        neural: ['Neural Galaxy', 'Agent Ecosystem Visualization'],
        analytics: ['Analytics', 'Charts, Metrics & Intelligence'],
        goals: ['Goals & Tasks', 'Autonomous Goal Management'],
        trading: ['Trading', 'Hedge Fund Operations'],
        curiosity: ['Curiosity', 'ROOT\'s Desire to Learn'],
        diagnostics: ['Diagnostics', 'Full System Health Check'],
        strategies: ['Backtester', 'Autonomous Backtest → Promote Pipeline'],
        settings: ['Settings', 'System Configuration'],
        miro: ['MiRo', 'Potentiality Engine — Predictions, Council Debates & Intelligence'],
        civilization: ['Civilization', '162+ Agent Civilization — Divisions & Operations'],
        directives: ['Directives', 'Autonomous Strategic Decisions'],
        network: ['Network', 'Agent Knowledge Network'],
        predictions: ['Predictions', 'Prediction Ledger — Calibration & Accuracy Tracking'],
        backtesting: ['Backtesting', 'Strategy Backtesting & Monte Carlo Simulation'],
        polymarket: ['Polymarket', 'Prediction Market Trading & Position Management'],
        chains: ['Action Chains', 'Reactive Pipelines — Automated Action Orchestration'],
        sandbox: ['Sandbox Gate', 'External Access Control — Approval & Notification Policies'],
    };
    const [t, s] = titles[panel] || ['ROOT', ''];
    document.getElementById('topbar-title').textContent = t;
    document.getElementById('topbar-subtitle').textContent = s;

    // Manage Neural Galaxy lifecycle
    if (panel === 'neural') {
        if (typeof NeuralGalaxy !== 'undefined') {
            setTimeout(() => NeuralGalaxy.init('neural-galaxy-container'), 200);
        }
    } else {
        if (typeof NeuralGalaxy !== 'undefined' && state._neuralActive) {
            NeuralGalaxy.destroy();
            state._neuralActive = false;
        }
    }
    if (panel === 'neural') state._neuralActive = true;

    // Panel loaders — functions defined in panels-*.js files
    // All wrapped in _safeLoader to prevent panel errors from crashing the app
    const loaders = {
        dashboard: _safeLoader(loadDashboard), memory: _safeLoader(loadMemories), skills: _safeLoader(loadSkills),
        agents: _safeLoader(loadAgents), money: _safeLoader(loadMoney), evolution: _safeLoader(loadEvolution),
        reflections: _safeLoader(loadReflections), plugins: _safeLoader(loadPlugins),
        builder: _safeLoader(loadBuilder), interest: _safeLoader(loadInterest),
        analytics: _safeLoader(loadAnalytics), goals: _safeLoader(loadGoals), trading: _safeLoader(loadTrading),
        curiosity: _safeLoader(loadCuriosity), diagnostics: _safeLoader(loadDiagnostics),
        strategies: _safeLoader(loadStrategies), settings: _safeLoader(loadSettings),
        miro: _safeLoader(loadMiro), civilization: _safeLoader(loadCivilization),
        directives: _safeLoader(loadDirectives), network: _safeLoader(loadNetwork),
        predictions: _safeLoader(loadPredictions), backtesting: _safeLoader(loadBacktesting),
        polymarket: _safeLoader(loadPolymarket), chains: _safeLoader(loadActionChains),
        sandbox: _safeLoader(loadSandbox),
    };
    if (loaders[panel]) loaders[panel]();
}

// ── Markdown Renderer ───────────────────────────────────────
// Code copy buffer (avoids complex attribute encoding)
const _codeBuf = {};
let _codeBufIdx = 0;

function copyCodeBlock(btn) {
    const key = btn.dataset.key;
    const code = _codeBuf[key] || '';
    navigator.clipboard.writeText(code).then(() => {
        btn.textContent = 'Copied!';
        btn.style.color = 'var(--accent-green)';
        setTimeout(() => { btn.textContent = 'Copy'; btn.style.color = ''; }, 1500);
    }).catch(() => {
        // Fallback
        const ta = document.createElement('textarea');
        ta.value = code;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        ta.remove();
        btn.textContent = 'Copied!';
        setTimeout(() => btn.textContent = 'Copy', 1500);
    });
}

function _highlightCode(code, lang) {
    if (typeof hljs === 'undefined') return escHtml(code);
    try {
        if (lang && hljs.getLanguage(lang)) {
            return hljs.highlight(code, { language: lang, ignoreIllegals: true }).value;
        }
        return hljs.highlightAuto(code, { subset: ['python','javascript','typescript','bash','json','sql','html','css','go','rust','java'] }).value;
    } catch {
        return escHtml(code);
    }
}

function _renderMarkdownCore(text) {
    if (!text) return '';

    // Detect raw JSON responses — format as code block instead of raw text
    const trimmed = text.trim();
    if (trimmed.startsWith('{') && trimmed.endsWith('}')) {
        try {
            const parsed = JSON.parse(trimmed);
            // If it looks like routing/task JSON (not a real response), show it nicely
            if (parsed.route || parsed.task || parsed.agent_ids || parsed.subtasks) {
                const formatted = JSON.stringify(parsed, null, 2);
                return `<div class="code-block-wrap"><div class="code-block-hdr"><span class="code-lang-tag">json</span></div><pre class="hljs"><code>${escHtml(formatted)}</code></pre></div><p><em>Note: This appears to be raw routing data. The agents may have timed out — try sending your message again.</em></p>`;
            }
        } catch (e) { /* not JSON, continue normally */ }
    }

    // Extract code blocks before HTML-escaping (to preserve code content)
    const blocks = [];
    let processed = text.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) => {
        const key = `cb_${_codeBufIdx++}`;
        _codeBuf[key] = code.trim();
        blocks.push({ key, lang: lang || '', code: code.trim() });
        return `\x00CODE_BLOCK_${blocks.length - 1}\x00`;
    });

    // HTML-escape the non-code parts
    let html = escHtml(processed);

    // Re-insert highlighted code blocks
    html = html.replace(/\x00CODE_BLOCK_(\d+)\x00/g, (_, i) => {
        const { key, lang, code } = blocks[parseInt(i)];
        const highlighted = _highlightCode(code, lang);
        const langLabel = lang ? `<span class="code-lang-tag">${escHtml(lang)}</span>` : '';
        return `<div class="code-block-wrap">
            <div class="code-block-hdr">${langLabel}<button class="code-copy-btn" data-key="${key}" onclick="copyCodeBlock(this)">Copy</button></div>
            <pre class="hljs"><code>${highlighted}</code></pre>
        </div>`;
    });

    // Inline code
    html = html.replace(/`([^`\n]+)`/g, '<code class="inline-code">$1</code>');
    // Headers
    html = html.replace(/^#### (.+)$/gm, '<h4>$1</h4>');
    html = html.replace(/^### (.+)$/gm, '<h4>$1</h4>');
    html = html.replace(/^## (.+)$/gm, '<h3>$1</h3>');
    html = html.replace(/^# (.+)$/gm, '<h2>$1</h2>');
    // Bold, italic
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
    // Lists
    html = html.replace(/^- (.+)$/gm, '<li>$1</li>');
    html = html.replace(/^(\d+)\. (.+)$/gm, '<li>$2</li>');
    // HR
    html = html.replace(/^---$/gm, '<hr>');
    // Paragraphs
    html = html.replace(/\n\n/g, '</p><p>');
    html = html.replace(/\n/g, '<br>');
    return `<p>${html}</p>`;
}

// ── File Upload ─────────────────────────────────────────────
let pendingFile = null;

function handleFileSelect(event) {
    const file = event.target.files[0];
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) {
        alert('File too large (max 10MB)');
        event.target.value = '';
        return;
    }
    pendingFile = file;
    const preview = document.getElementById('file-preview');
    document.getElementById('file-name').textContent = file.name;
    const sizeKB = (file.size / 1024).toFixed(1);
    const sizeStr = file.size > 1024 * 1024 ? (file.size / 1024 / 1024).toFixed(1) + ' MB' : sizeKB + ' KB';
    document.getElementById('file-size').textContent = sizeStr;
    preview.style.display = 'block';
}

function removeFile() {
    pendingFile = null;
    document.getElementById('file-preview').style.display = 'none';
    document.getElementById('file-input').value = '';
}

// ── Chat ────────────────────────────────────────────────────
function quickSend(text) {
    document.getElementById('chat-input').value = text;
    sendMessage();
}

function sendMessage() {
    const input = document.getElementById('chat-input');
    const msg = input.value.trim();
    const hasFile = !!pendingFile;
    if (!msg && !hasFile) return;

    // Capture file before clearing
    const file = hasFile ? pendingFile : null;
    input.value = '';
    input.style.height = 'auto';
    if (hasFile) removeFile();

    // If already processing, queue the message
    if (state.loading) {
        messageQueue.push({ msg, file });
        updateQueueBadge();
        // Show queued user message immediately
        const displayMsg = file ? `${msg || 'Uploaded file'}\n\u{1F4CE} ${file.name}` : msg;
        appendMsg('user', 'Yohan', displayMsg);
        appendQueuedIndicator(msg);
        return;
    }

    // Process immediately
    _processMessage(msg, file);
}

function updateQueueBadge() {
    const badge = document.getElementById('queue-badge');
    if (!badge) return;
    if (messageQueue.length > 0) {
        badge.textContent = messageQueue.length;
        badge.style.display = 'inline-block';
    } else {
        badge.style.display = 'none';
    }
}

function appendQueuedIndicator(msg) {
    const container = document.getElementById('chat-scroll');
    const div = document.createElement('div');
    div.className = 'queue-indicator';
    div.innerHTML = `<span>Queued — will process after current request</span>`;
    container.appendChild(div);
    scrollChat();
}

async function _processMessage(msg, file) {
    // Use streaming for non-file messages
    if (!file) {
        return _processMessageStreaming(msg);
    }

    state.loading = true;
    document.getElementById('btn-send').disabled = true;

    // Hide welcome/suggestions
    const qs = document.getElementById('quick-suggestions');
    if (qs) qs.style.display = 'none';
    document.querySelectorAll('.followup-chips').forEach(el => el.remove());
    const wm = document.querySelector('.welcome-msg');
    if (wm) wm.style.display = 'none';

    // User message (only if not already shown by queue)
    if (!processingQueue) {
        const displayMsg = file ? `${msg || 'Uploaded file'}\n\u{1F4CE} ${file.name}` : msg;
        appendMsg('user', 'Yohan', displayMsg);
    }

    // Remove any queue indicator for this message
    const indicators = document.querySelectorAll('.queue-indicator');
    if (indicators.length > 0 && processingQueue) indicators[0].remove();

    // Show ASTRA thinking with live status
    const thinkId = appendThinking();
    const startTime = Date.now();

    try {
        let data;
        if (file) {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('message', msg);
            const resp = await fetch('/api/chat/upload', { method: 'POST', body: formData });
            if (!resp.ok) throw new Error(`Upload failed: HTTP ${resp.status}`);
            data = await resp.json();
        } else {
            data = await api('/api/chat', {
                method: 'POST',
                body: { message: msg },
            });
        }

        // Remove thinking
        const thinkEl = document.getElementById(thinkId);
        if (thinkEl) thinkEl.remove();

        if (data.error) {
            appendMsg('assistant', 'ROOT', `Error: ${data.error}`);
        } else {
            const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
            const tokenEst = Math.round((data.content || '').length / 4);

            // Show full process card if agents were used
            if (data.agents_used && data.agents_used.length > 0) {
                appendProcessCard(data, elapsed);
            }

            // Show synthesized response
            const agentId = data.agent_id || 'root';
            const agentName = getAgentName(agentId);
            const msgId = appendMsg('assistant', agentName, data.content || '', false, agentId);

            // Add route badge
            if (data.route && data.route !== 'direct') {
                const el = document.getElementById(msgId);
                if (el) {
                    const badge = document.createElement('span');
                    badge.className = `msg-route-badge ${data.route}`;
                    badge.textContent = data.route === 'multi' ? 'Multi-Agent' : 'Delegated';
                    el.querySelector('.msg-header').appendChild(badge);
                }
            }

            // Add process summary footer
            const el = document.getElementById(msgId);
            if (el) {
                addProcessFooter(el, data, elapsed, tokenEst);
            }
            if (data.response) _showFollowUpSuggestions(data.response);
        }
    } catch (e) {
        const thinkEl = document.getElementById(thinkId);
        if (thinkEl) thinkEl.remove();
        appendMsg('assistant', 'ROOT', `Connection error: ${e.message}`);
    }

    state.loading = false;
    document.getElementById('btn-send').disabled = false;
    scrollChat();

    // Process next queued message if any
    if (messageQueue.length > 0) {
        const next = messageQueue.shift();
        updateQueueBadge();
        processingQueue = true;
        // Small delay so user sees the response before next request
        setTimeout(() => _processMessage(next.msg, next.file), 300);
    } else {
        processingQueue = false;
    }
}

function _appendMsgCore(role, name, content, isThinking = false, agentId = null) {
    const container = document.getElementById('chat-scroll');
    const id = `msg-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
    const aid = agentId || name.toLowerCase().replace(/[^a-z]/g, '');
    const avatarColor = AGENT_COLORS[aid] || 'var(--accent)';
    const initial = AGENT_ICONS[aid] || (name || 'R')[0].toUpperCase();
    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    const div = document.createElement('div');
    div.className = `msg ${role}`;
    div.id = id;
    div.innerHTML = `
        <div class="msg-avatar" style="background:${role === 'user' ? 'var(--accent)' : avatarColor}">${initial}</div>
        <div class="msg-body">
            <div class="msg-header">
                <span class="msg-name">${escHtml(name)}</span>
                <span class="msg-time">${time}</span>
            </div>
            <div class="msg-content">${
                isThinking
                    ? '<div class="thinking-dots"><span></span><span></span><span></span></div>'
                    : (role === 'user' ? escHtml(content) : renderMarkdown(content))
            }</div>
            ${role === 'assistant' && !isThinking ? `
            <div class="msg-actions">
                <button class="msg-action-btn" onclick="reactMsg(this)" title="Helpful">&#128077;</button>
                <button class="msg-action-btn" onclick="reactMsg(this)" title="Not helpful">&#128078;</button>
                <button class="msg-action-btn" onclick="copyMsg(this)" title="Copy">&#128203;</button>
                <button class="msg-action-btn" onclick="pinMsg(this)" title="Pin to Memory">&#128204;</button>
                <button class="msg-action-btn" onclick="starMsg(this)" title="Star">&#9734;</button>
            </div>` : ''}
        </div>`;
    container.appendChild(div);
    scrollChat();
    return id;
}

function appendThinking() {
    const container = document.getElementById('chat-scroll');
    const id = `think-${Date.now()}`;
    const div = document.createElement('div');
    div.className = 'msg assistant';
    div.id = id;
    div.innerHTML = `
        <div class="msg-avatar" style="background:${AGENT_COLORS.astra}">A</div>
        <div class="msg-body">
            <div class="msg-header">
                <span class="msg-name">ASTRA</span>
                <span class="msg-time">${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
            </div>
            <div class="msg-content">
                <div class="thinking-animation">
                    <div class="thinking-bar"><div class="thinking-bar-fill"></div></div>
                    <span class="thinking-label">Routing</span>
                </div>
            </div>
        </div>`;
    container.appendChild(div);
    scrollChat();
    return id;
}

// ── Process Card — Shows full agent communication details ───
function appendProcessCard(data, elapsed) {
    const container = document.getElementById('chat-scroll');
    const findings = data.agent_findings || [];
    const agents = data.agents_used || [];
    const totalMsgs = data.total_messages_exchanged || 0;
    const totalTools = data.total_tools_executed || 0;
    const reasoning = data.routing_reasoning || '';

    // Build per-agent detail rows
    const agentRows = findings.map(f => {
        const color = AGENT_COLORS[f.agent_id] || 'var(--accent)';
        const initial = AGENT_ICONS[f.agent_id] || (f.agent_name || f.agent_id)[0].toUpperCase();
        const statusClass = f.status === 'completed' ? 'completed' : 'failed';
        const duration = f.duration_seconds ? `${f.duration_seconds.toFixed(1)}s` : '';
        const msgs = f.messages_exchanged || 0;
        const tools = f.tools_executed || 0;
        const toolNames = (f.tools_used || []).map(t => formatToolName(t));
        const resultPreview = (f.result || '').slice(0, 300);

        const processParts = [];
        if (msgs > 0) processParts.push(`${msgs} message${msgs !== 1 ? 's' : ''}`);
        if (tools > 0) processParts.push(`executed ${tools} tool${tools !== 1 ? 's' : ''}`);
        const processLine = processParts.length
            ? `exchanged ${processParts.join(' and ')}`
            : 'direct response';

        return `
            <div class="process-agent">
                <div class="process-agent-header">
                    <div class="process-agent-left">
                        <div class="process-agent-avatar" style="background:${color}">${initial}</div>
                        <div>
                            <div class="process-agent-name">${escHtml(f.agent_name || f.agent_id)}</div>
                            <div class="process-agent-task">${escHtml(f.task || '')}</div>
                        </div>
                    </div>
                    <div class="process-agent-right">
                        <span class="process-status ${statusClass}">${escHtml(f.status)}</span>
                        ${duration ? `<span class="process-duration">${duration}</span>` : ''}
                    </div>
                </div>
                <div class="process-agent-activity">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
                    <span class="process-summary-text">${escHtml(f.agent_name)} ${processLine}</span>
                </div>
                ${toolNames.length > 0 ? `
                <div class="process-tools-row">
                    ${toolNames.map(t => `<span class="process-tool-tag">${escHtml(t)}</span>`).join('')}
                </div>` : ''}
                ${resultPreview ? `
                <details class="process-result-details">
                    <summary>View findings</summary>
                    <div class="process-result-content">${escHtml(resultPreview)}${f.result && f.result.length > 300 ? '...' : ''}</div>
                </details>` : ''}
            </div>`;
    }).join('');

    // Header summary
    const headerParts = [];
    if (totalMsgs > 0) headerParts.push(`${totalMsgs} messages`);
    if (totalTools > 0) headerParts.push(`${totalTools} tools`);

    const div = document.createElement('div');
    div.className = 'process-card';
    div.innerHTML = `
        <div class="process-header">
            <div class="process-header-left">
                <div class="process-icon">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M22 12h-4l-3 9L9 3l-3 9H2"/>
                    </svg>
                </div>
                <div>
                    <div class="process-title">ASTRA dispatched ${agents.length} agent${agents.length !== 1 ? 's' : ''}</div>
                    ${reasoning ? `<div class="process-reasoning">${escHtml(reasoning)}</div>` : ''}
                </div>
            </div>
            <div class="process-header-stats">
                ${headerParts.map(p => `<span class="process-stat">${p}</span>`).join('')}
                <span class="process-stat">${elapsed}s</span>
            </div>
        </div>
        <div class="process-agents">${agentRows}</div>
        <div class="process-footer">
            <span class="process-route">Route: ${escHtml(data.route || 'direct')}</span>
            <span class="process-total">${agents.length} agent${agents.length !== 1 ? 's' : ''} &middot; ${headerParts.join(' &middot; ')}</span>
        </div>`;
    container.appendChild(div);
    scrollChat();
}

// ── Process Footer on message (like Nebula's timing/token bar) ──
function addProcessFooter(el, data, elapsed, tokenEst) {
    const totalMsgs = data.total_messages_exchanged || 0;
    const totalTools = data.total_tools_executed || 0;
    const agents = data.agents_used || [];

    const parts = [];
    parts.push(`${elapsed}s`);
    parts.push(`~${tokenEst.toLocaleString()} tokens`);
    if (agents.length > 0) parts.push(`${agents.length} agent${agents.length !== 1 ? 's' : ''}`);
    if (totalMsgs > 0) parts.push(`${totalMsgs} messages`);
    if (totalTools > 0) parts.push(`${totalTools} tools`);

    const metaDiv = document.createElement('div');
    metaDiv.className = 'msg-meta';
    metaDiv.innerHTML = parts.map(p => `<span>${p}</span>`).join('');
    el.querySelector('.msg-body').appendChild(metaDiv);
}

function formatToolName(name) {
    return name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function getAgentName(id) {
    const agent = state.agents.find(a => a.id === id);
    if (agent) return agent.name;
    const names = {
        root: 'ROOT', astra: 'ASTRA', hermes: 'HERMES', miro: 'MiRo',
        swarm: 'Trading Swarm', builder: 'Builder', researcher: 'Researcher',
        coder: 'Coder', writer: 'Writer', analyst: 'Analyst', guardian: 'Guardian',
    };
    return names[id] || id;
}

function reactMsg(btn) {
    btn.classList.toggle('active');
    const isHelpful = btn.title === 'Helpful';
    const msgBody = btn.closest('.msg-body');
    const content = msgBody ? msgBody.querySelector('.msg-content').innerText.slice(0, 500) : '';
    // Deactivate the opposite button
    const sibling = isHelpful ? btn.nextElementSibling : btn.previousElementSibling;
    if (sibling && sibling.classList.contains('active')) sibling.classList.remove('active');
    // Send feedback to backend
    if (btn.classList.contains('active')) {
        const msgEl = btn.closest('.msg');
        const allMsgs = Array.from(document.querySelectorAll('#chat-scroll .msg'));
        const idx = allMsgs.indexOf(msgEl);
        api('/api/chat/feedback', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message_index: idx >= 0 ? idx : -1,
                feedback: isHelpful ? 'helpful' : 'not_helpful',
            }),
        });
    }
}
function copyMsg(btn) {
    const content = btn.closest('.msg-body').querySelector('.msg-content').innerText;
    navigator.clipboard.writeText(content).then(() => {
        btn.textContent = '\u2713';
        setTimeout(() => { btn.innerHTML = '&#128203;'; }, 1500);
    });
}
function starMsg(btn) {
    btn.classList.toggle('active');
    btn.innerHTML = btn.classList.contains('active') ? '&#9733;' : '&#9734;';
}
function scrollChat() {
    const c = document.getElementById('chat-scroll');
    c.scrollTop = c.scrollHeight;
}

// ── Utilities ───────────────────────────────────────────────
function escHtml(s) {
    if (!s) return '';
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}

function formatTime(iso) {
    if (!iso) return '';
    try {
        const d = new Date(iso);
        const diff = (Date.now() - d) / 1000;
        if (diff < 60) return 'just now';
        if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
        if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
        if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
        return d.toLocaleDateString();
    } catch { return iso; }
}

function _setText(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
}

/** Safe DOM element getter — returns element or null without crash */
function _el(id) { return document.getElementById(id); }

/** Wrap any async loader in try/catch so panel errors never crash the app */
function _safeLoader(fn) {
    return async function (...args) {
        try {
            return await fn.apply(this, args);
        } catch (err) {
            console.error(`[${fn.name || 'loader'}] Panel load failed:`, err);
        }
    };
}

/** Client-side API cache — avoids redundant fetches for rarely-changing data */
const _apiCache = {};
async function cachedApi(path, ttlMs = 30000) {
    const now = Date.now();
    const cached = _apiCache[path];
    if (cached && now - cached.ts < ttlMs) return cached.data;
    const data = await api(path);
    _apiCache[path] = { data, ts: now };
    return data;
}
function invalidateCache(path) {
    if (path) { delete _apiCache[path]; } else { Object.keys(_apiCache).forEach(k => delete _apiCache[k]); }
}

/** Debounce — delays execution until input settles (for search fields) */
function debounce(fn, ms = 300) {
    let t;
    return function (...args) { clearTimeout(t); t = setTimeout(() => fn.apply(this, args), ms); };
}

/** Show inline panel error when API fails */
function showPanelError(containerId, message) {
    const el = document.getElementById(containerId);
    if (el) el.innerHTML = `<div style="text-align:center;padding:24px;color:var(--text-muted);font-size:13px;">${escHtml(message || 'Failed to load data. Retrying...')}</div>`;
}

// ── Notification Center ─────────────────────────────────────
let _notifOpen = false;

async function loadNotifications() {
    const data = await api('/api/notifications?limit=50');
    if (!data || data.error) return;

    const badge = document.getElementById('notif-badge');
    if (badge) {
        if (data.unread > 0) {
            badge.textContent = data.unread > 99 ? '99+' : data.unread;
            badge.style.display = '';
        } else {
            badge.style.display = 'none';
        }
    }

    const list = document.getElementById('notif-list');
    if (!list) return;
    if (!data.notifications?.length) {
        list.innerHTML = '<div class="empty-state" style="padding:20px">No notifications</div>';
        return;
    }
    list.innerHTML = data.notifications.map(n => `
        <div class="notif-item ${n.read ? '' : 'unread'}">
            <div class="notif-item-header">
                <span><span class="notif-level ${n.level}">${n.level}</span><span class="notif-title">${escHtml(n.title)}</span></span>
                <span class="notif-time">${formatTime(n.created_at)}</span>
            </div>
            <div class="notif-body">${escHtml(n.body)}</div>
        </div>
    `).join('');
}

async function toggleNotifications() {
    const dd = document.getElementById('notif-dropdown');
    if (!dd) return;
    _notifOpen = !_notifOpen;
    dd.style.display = _notifOpen ? 'flex' : 'none';
    if (_notifOpen) await loadNotifications();
}

async function markAllNotificationsRead() {
    await api('/api/notifications/read-all', { method: 'POST' });
    await loadNotifications();
}

// Close notification dropdown on outside click
document.addEventListener('click', e => {
    const dd = document.getElementById('notif-dropdown');
    const bell = document.querySelector('.notification-bell');
    if (_notifOpen && dd && bell && !dd.contains(e.target) && !bell.contains(e.target)) {
        _notifOpen = false;
        dd.style.display = 'none';
    }
});

// ── Command Palette ─────────────────────────────────────────
const CMD_ITEMS = [
    { name: 'Chat', desc: 'Open chat panel', icon: '\u{1F4AC}', action: () => switchPanel('chat'), shortcut: 'Ctrl+1' },
    { name: 'Dashboard', desc: 'System overview', icon: '\u{1F4CA}', action: () => switchPanel('dashboard'), shortcut: 'Ctrl+2' },
    { name: 'Memory', desc: 'Knowledge base', icon: '\u{1F9E0}', action: () => switchPanel('memory'), shortcut: 'Ctrl+3' },
    { name: 'Agents', desc: 'Agent registry', icon: '\u{1F465}', action: () => switchPanel('agents') },
    { name: 'Analytics', desc: 'Charts and metrics', icon: '\u{1F4C8}', action: () => switchPanel('analytics') },
    { name: 'Settings', desc: 'Configuration', icon: '\u2699', action: () => switchPanel('settings') },
    { name: 'Strategies', desc: 'Money & opportunities', icon: '\u{1F4B0}', action: () => switchPanel('money') },
    { name: 'Neural Galaxy', desc: '3D agent visualization', icon: '\u{1F310}', action: () => switchPanel('neural') },
    { name: 'Plugins', desc: 'Plugin management', icon: '\u{1F50C}', action: () => switchPanel('plugins') },
    { name: 'Skills', desc: 'Skill catalog', icon: '#', action: () => switchPanel('skills') },
    { name: 'Builder', desc: 'Self-improvement', icon: '\u{1F528}', action: () => switchPanel('builder') },
    { name: 'Evolution', desc: 'Maturity tracking', icon: '\u{1F9EC}', action: () => switchPanel('evolution') },
    { name: 'Reflections', desc: 'Autonomous insights', icon: '\u{1F52E}', action: () => switchPanel('reflections') },
    { name: 'Interest', desc: 'Opportunity assessment', icon: '\u{1F3AF}', action: () => switchPanel('interest') },
    { name: 'Goals', desc: 'Goal management', icon: '\u{1F3AF}', action: () => switchPanel('goals') },
    { name: 'Trading', desc: 'Hedge fund ops', icon: '\u{1F4C8}', action: () => switchPanel('trading') },
    { name: 'Predictions', desc: 'Prediction ledger & calibration', icon: '\u{1F3AF}', action: () => switchPanel('predictions') },
    { name: 'Backtesting', desc: 'Strategy backtesting & Monte Carlo', icon: '\u{1F4C9}', action: () => switchPanel('backtesting') },
    { name: 'Polymarket', desc: 'Prediction market trading', icon: '\u{1F52E}', action: () => switchPanel('polymarket') },
    { name: 'Action Chains', desc: 'Reactive automation pipelines', icon: '\u26D3', action: () => switchPanel('chains') },
    { name: 'Sandbox Gate', desc: 'External access control & approvals', icon: '\uD83D\uDD12', action: () => switchPanel('sandbox') },
    { name: 'Market Scan', desc: 'Scan trading opportunities', icon: '\u{1F4E1}', action: () => { switchPanel('chat'); quickSend('Scan the market for trading opportunities'); } },
    { name: 'System Status', desc: 'Check agent health', icon: '\u{1F50B}', action: () => { switchPanel('chat'); quickSend('Show system status and agent health'); } },
    { name: 'Convene Council', desc: 'Strategy council session', icon: '\u{1F451}', action: () => { switchPanel('money'); setTimeout(conveneCouncil, 300); } },
    { name: 'Run Build Cycle', desc: 'Trigger builder agent', icon: '\u{1F3D7}', action: () => { switchPanel('builder'); setTimeout(triggerBuild, 300); } },
    { name: 'Trigger Reflection', desc: 'Force reflection cycle', icon: '\u{1F4AD}', action: () => { switchPanel('reflections'); setTimeout(triggerReflection, 300); } },
];

let _cmdSelectedIdx = 0;
let _cmdFiltered = [...CMD_ITEMS];

function openCmdPalette() {
    const overlay = document.getElementById('cmd-overlay');
    if (!overlay) return;
    overlay.style.display = 'flex';
    const input = document.getElementById('cmd-input');
    if (input) { input.value = ''; input.focus(); }
    _cmdFiltered = [...CMD_ITEMS];
    _cmdSelectedIdx = 0;
    renderCmdResults();
}

function closeCmdPalette() {
    const overlay = document.getElementById('cmd-overlay');
    if (overlay) overlay.style.display = 'none';
}

function filterCmdPalette(query) {
    const q = query.toLowerCase();
    _cmdFiltered = q ? CMD_ITEMS.filter(item =>
        item.name.toLowerCase().includes(q) || item.desc.toLowerCase().includes(q)
    ) : [...CMD_ITEMS];
    _cmdSelectedIdx = 0;
    renderCmdResults();
}

function renderCmdResults() {
    const container = document.getElementById('cmd-results');
    if (!container) return;
    container.innerHTML = _cmdFiltered.map((item, i) => `
        <div class="cmd-item ${i === _cmdSelectedIdx ? 'active' : ''}"
             onclick="executeCmdItem(${i})" onmouseenter="_cmdSelectedIdx=${i};renderCmdResults()">
            <div class="cmd-item-icon">${item.icon}</div>
            <div class="cmd-item-text">
                <div class="cmd-item-name">${escHtml(item.name)}</div>
                <div class="cmd-item-desc">${escHtml(item.desc)}</div>
            </div>
            ${item.shortcut ? `<span class="cmd-item-shortcut">${item.shortcut}</span>` : ''}
        </div>
    `).join('');
}

function executeCmdItem(idx) {
    if (_cmdFiltered[idx]) {
        closeCmdPalette();
        _cmdFiltered[idx].action();
    }
}

// ── Keyboard Shortcuts ──────────────────────────────────────
document.addEventListener('keydown', e => {
    // Command palette: Ctrl+K
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        const overlay = document.getElementById('cmd-overlay');
        if (overlay && overlay.style.display === 'flex') {
            closeCmdPalette();
        } else {
            openCmdPalette();
        }
        return;
    }

    // Keyboard shortcuts panel: Ctrl+/
    if ((e.ctrlKey || e.metaKey) && e.key === '/') {
        e.preventDefault();
        const so = document.getElementById('shortcuts-overlay');
        if (so && so.classList.contains('open')) closeShortcutsPanel();
        else openShortcutsPanel();
        return;
    }

    // Message search in chat: Ctrl+F (when chat panel active)
    if ((e.ctrlKey || e.metaKey) && e.key === 'f' && state.activePanel === 'chat') {
        e.preventDefault();
        const so = document.getElementById('msg-search-overlay');
        if (so && so.classList.contains('open')) closeMsgSearch();
        else openMsgSearch();
        return;
    }

    // New chat: Ctrl+N
    if ((e.ctrlKey || e.metaKey) && e.key === 'n' && state.activePanel === 'chat') {
        e.preventDefault();
        startNewChat();
        return;
    }

    // Export conversation: Ctrl+E (chat panel)
    if ((e.ctrlKey || e.metaKey) && e.key === 'e' && state.activePanel === 'chat') {
        e.preventDefault();
        exportConversation();
        return;
    }

    // Escape to close command palette / shortcuts / msg search
    if (e.key === 'Escape') {
        const so = document.getElementById('shortcuts-overlay');
        if (so && so.classList.contains('open')) { closeShortcutsPanel(); return; }
        const ms = document.getElementById('msg-search-overlay');
        if (ms && ms.classList.contains('open')) { closeMsgSearch(); return; }
        const overlay = document.getElementById('cmd-overlay');
        if (overlay && overlay.style.display === 'flex') {
            closeCmdPalette();
            return;
        }
        // Cancel reply
        if (_replyTarget) { cancelReply(); return; }
    }

    // Arrow navigation in command palette
    const overlay = document.getElementById('cmd-overlay');
    if (overlay && overlay.style.display === 'flex') {
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            _cmdSelectedIdx = Math.min(_cmdSelectedIdx + 1, _cmdFiltered.length - 1);
            renderCmdResults();
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            _cmdSelectedIdx = Math.max(_cmdSelectedIdx - 1, 0);
            renderCmdResults();
        } else if (e.key === 'Enter') {
            e.preventDefault();
            executeCmdItem(_cmdSelectedIdx);
        }
        return;
    }

    // Panel shortcuts: Ctrl+1..9
    const panels = ['chat', 'dashboard', 'memory', 'agents', 'analytics', 'settings', 'plugins', 'money', 'neural', 'goals', 'trading'];
    if ((e.ctrlKey || e.metaKey) && e.key >= '1' && e.key <= '9') {
        const idx = parseInt(e.key) - 1;
        if (idx < panels.length) { e.preventDefault(); switchPanel(panels[idx]); }
    }

    // Focus chat: /
    if (e.key === '/' && !e.ctrlKey && !e.metaKey && document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA') {
        e.preventDefault();
        switchPanel('chat');
        document.getElementById('chat-input')?.focus();
    }
});

// ── Auto-resize textarea ────────────────────────────────────
function autoResize(el) {
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}

// ── Conversation History ─────────────────────────────────────
let _activeChatSession = null;

async function _loadConvSessionsCore() {
    const container = document.getElementById('sidebar-conversations');
    if (!container) return;

    try {
        const data = await api('/api/conversations/sessions?limit=20');
        const sessions = Array.isArray(data) ? data : (data?.sessions || data?.data || []);
        if (!sessions.length) {
            container.innerHTML = '<div class="conv-loading">No history yet</div>';
            return;
        }
        container.innerHTML = sessions.map(s => {
            const title = s.title || `Session ${(s.id || '').slice(-6)}`;
            const date = (s.started_at || s.created_at) ? formatTime(s.started_at || s.created_at) : '';
            const msgCount = s.message_count || '';
            const isActive = s.id === _activeChatSession;
            return `<div class="conv-item ${isActive ? 'active' : ''}" onclick="loadSessionMessages('${escHtml(s.id)}', this)">
                <div class="conv-item-title">${escHtml(title.slice(0, 45))}${title.length > 45 ? '\u2026' : ''}</div>
                <div class="conv-item-meta">${date}${msgCount ? ` \u00B7 ${msgCount} msgs` : ''}</div>
            </div>`;
        }).join('');
    } catch (e) {
        container.innerHTML = '<div class="conv-loading">Failed to load</div>';
    }
}

async function loadSessionMessages(sessionId, el) {
    _activeChatSession = sessionId;

    // Switch to chat panel immediately so user sees something happen
    switchPanel('chat');

    // Update active state in sidebar
    document.querySelectorAll('.conv-item').forEach(i => i.classList.remove('active'));
    if (el) el.classList.add('active');

    // Clear current chat
    const chatScroll = document.getElementById('chat-scroll');
    if (!chatScroll) return;

    // Hide welcome message
    const wm = chatScroll.querySelector('.welcome-msg');
    if (wm) wm.style.display = 'none';
    const qs = document.getElementById('quick-suggestions');
    if (qs) qs.style.display = 'none';

    // Remove existing messages (keep welcome-msg hidden)
    chatScroll.querySelectorAll('.msg, .process-card, .queue-indicator').forEach(m => m.remove());

    // Show loading
    const loadingId = `loading-${Date.now()}`;
    const loadEl = document.createElement('div');
    loadEl.id = loadingId;
    loadEl.style.cssText = 'text-align:center;padding:20px;color:var(--text-muted);font-size:12px';
    loadEl.textContent = 'Loading conversation\u2026';
    chatScroll.appendChild(loadEl);

    try {
        const data = await api(`/api/conversations/sessions/${sessionId}`);
        const messages = Array.isArray(data) ? data : (data?.messages || data?.data || []);

        loadEl.remove();

        if (!messages.length) {
            const emptyEl = document.createElement('div');
            emptyEl.style.cssText = 'text-align:center;padding:20px;color:var(--text-muted);font-size:12px';
            emptyEl.textContent = 'Empty conversation';
            chatScroll.appendChild(emptyEl);
            return;
        }

        for (const msg of messages) {
            const role = msg.role === 'user' ? 'user' : 'assistant';
            const name = role === 'user' ? 'Yohan' : (msg.agent_id || 'ROOT');
            appendMsgFromHistory(role, name, msg.content, msg.created_at);
        }

        scrollChat();
    } catch (e) {
        loadEl.textContent = `Failed to load: ${e.message}`;
    }
}

function appendMsgFromHistory(role, name, content, timestamp) {
    const container = document.getElementById('chat-scroll');
    const id = `msg-hist-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
    const aid = name.toLowerCase().replace(/[^a-z]/g, '');
    const avatarColor = AGENT_COLORS[aid] || 'var(--accent)';
    const initial = AGENT_ICONS[aid] || (name || 'R')[0].toUpperCase();
    const time = timestamp
        ? new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        : '';

    const div = document.createElement('div');
    div.className = `msg ${role}`;
    div.id = id;
    div.innerHTML = `
        <div class="msg-avatar" style="background:${role === 'user' ? 'var(--accent)' : avatarColor}">${initial}</div>
        <div class="msg-body">
            <div class="msg-header">
                <span class="msg-name">${escHtml(name)}</span>
                ${time ? `<span class="msg-time">${time}</span>` : ''}
            </div>
            <div class="msg-content">${role === 'user' ? escHtml(content) : renderMarkdown(content || '')}</div>
        </div>`;
    container.appendChild(div);
}

async function loadChatHistory() {
    // Load the most recent session on startup
    try {
        const data = await api('/api/conversations/sessions?limit=1');
        const sessions = Array.isArray(data) ? data : (data?.sessions || data?.data || []);
        if (sessions.length > 0) {
            const latest = sessions[0];
            _activeChatSession = latest.id;
            await loadSessionMessages(latest.id, null);
        }
    } catch (e) {
        // Silently fail — chat starts blank
    }
}

function startNewChat() {
    _activeChatSession = null;
    document.querySelectorAll('.conv-item').forEach(i => i.classList.remove('active'));
    const chatScroll = document.getElementById('chat-scroll');
    if (chatScroll) {
        chatScroll.querySelectorAll('.msg, .process-card, .queue-indicator').forEach(m => m.remove());
        const wm = chatScroll.querySelector('.welcome-msg');
        if (wm) wm.style.display = '';
    }
    const qs = document.getElementById('quick-suggestions');
    if (qs) qs.style.display = '';
    switchPanel('chat');
    document.getElementById('chat-input')?.focus();
}

// ── Chat Mode Pills ──────────────────────────────────────────
const MODE_PROMPTS = {
    default: '',
    code: 'Write clean, well-commented code. Use code blocks with language labels. ',
    search: 'Search for up-to-date information and cite sources. Focus on recent data. ',
    analyze: 'Provide deep analysis with data, trends, and actionable insights. Use tables and structured output. ',
    write: 'Write in a clear, engaging style. Format well with headers and structure. ',
    trade: 'Focus on trading signals, risk/reward, entry/exit points, and market data. Use the hedge fund agents. ',
};
let _currentMode = 'default';
let _currentModelTier = 'default';
let _currentModelLabel = 'Sonnet';

function setMode(mode) {
    _currentMode = mode;
    document.querySelectorAll('.mode-pill').forEach(b => b.classList.remove('active'));
    const btn = document.getElementById(`mode-${mode}`);
    if (btn) btn.classList.add('active');
    const labels = { default:'Chat mode', code:'Code mode', search:'Search mode', analyze:'Analyze mode', write:'Write mode', trade:'Trade mode' };
    const lbl = document.getElementById('active-mode-label');
    if (lbl) lbl.textContent = labels[mode] || 'Chat mode';
    // Update placeholder
    const placeholders = {
        default: 'Ask me anything... (Shift+Enter for multiline)',
        code: 'Describe what code to write...',
        search: 'Search for information...',
        analyze: 'What would you like analyzed?',
        write: 'What should I write?',
        trade: 'Ask about trading signals, strategies, portfolio...',
    };
    const inp = document.getElementById('chat-input');
    if (inp) inp.placeholder = placeholders[mode] || placeholders.default;
}

function toggleModelPicker() {
    const dd = document.getElementById('model-picker-dropdown');
    if (dd) dd.classList.toggle('open');
}

function selectModel(tier, label, modelId) {
    _currentModelTier = tier;
    _currentModelLabel = label;
    const lbl = document.getElementById('model-label');
    if (lbl) lbl.textContent = label;
    document.querySelectorAll('.model-opt').forEach(b => b.classList.remove('active'));
    const dd = document.getElementById('model-picker-dropdown');
    if (dd) {
        dd.classList.remove('open');
        const opts = dd.querySelectorAll('.model-opt');
        const tiers = { fast: 0, default: 1, thinking: 2, gpt4: 3 };
        if (tiers[tier] !== undefined && opts[tiers[tier]]) opts[tiers[tier]].classList.add('active');
        // Highlight Ollama option if selected
        dd.querySelectorAll('.ollama-model-opt').forEach(b => {
            b.classList.toggle('active', b.dataset.model === tier);
        });
    }
}

// ── Ollama Model Fetcher ────────────────────────────────────
function _fetchOllamaModels() {
    fetch('http://localhost:11434/api/tags').then(r => r.json()).then(data => {
        const models = data.models || [];
        const container = document.getElementById('ollama-model-pills');
        const title = document.getElementById('ollama-section-title');
        if (!container) return;
        const filtered = models.filter(m => !m.name.includes('root-'));
        if (filtered.length && title) title.style.display = '';
        container.innerHTML = filtered.map(m => {
            const shortName = m.name.split(':')[0];
            const tier = 'ollama:' + m.name;
            return `<button class="model-opt ollama-model-opt" data-model="${tier}" onclick="selectModel('${tier}','${shortName}','${m.name}')">
                <div>
                    <div class="model-opt-name">${shortName} <span class="model-tag" style="background:#6c5ce7;color:#fff">Local</span></div>
                    <div class="model-opt-desc">Ollama · ${(m.size / 1e9).toFixed(1)}GB · Free</div>
                </div>
            </button>`;
        }).join('');
    }).catch(() => {});
}
// Fetch on load and periodically
_fetchOllamaModels();
setInterval(_fetchOllamaModels, 60000);

// Close model picker on outside click
document.addEventListener('click', e => {
    const wrap = document.querySelector('.model-selector-wrap');
    if (wrap && !wrap.contains(e.target)) {
        const dd = document.getElementById('model-picker-dropdown');
        if (dd) dd.classList.remove('open');
    }
});

// Inject mode prefix into message before sending
const _origSendMessage = typeof sendMessage !== 'undefined' ? sendMessage : null;

// ── Voice Input ──────────────────────────────────────────────
let _recognition = null;
let _isRecording = false;

function toggleVoiceInput() {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
        alert('Voice input not supported in this browser. Use Chrome.');
        return;
    }
    if (_isRecording) {
        if (_recognition) _recognition.stop();
        return;
    }
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    _recognition = new SpeechRecognition();
    _recognition.continuous = false;
    _recognition.interimResults = true;
    _recognition.lang = 'en-US';

    const btn = document.getElementById('voice-btn');
    const inp = document.getElementById('chat-input');

    _recognition.onstart = () => {
        _isRecording = true;
        if (btn) btn.classList.add('recording');
    };
    _recognition.onresult = (evt) => {
        const transcript = Array.from(evt.results).map(r => r[0].transcript).join('');
        if (inp) { inp.value = transcript; autoResize(inp); }
    };
    _recognition.onend = () => {
        _isRecording = false;
        if (btn) btn.classList.remove('recording');
    };
    _recognition.onerror = () => {
        _isRecording = false;
        if (btn) btn.classList.remove('recording');
    };
    _recognition.start();
}

// ── Export Conversation ──────────────────────────────────────
function exportConversation() {
    const msgs = document.querySelectorAll('#chat-scroll .msg');
    if (!msgs.length) { alert('No messages to export.'); return; }
    let md = `# ROOT Conversation Export\n_${new Date().toLocaleString()}_\n\n`;
    msgs.forEach(m => {
        const name = m.querySelector('.msg-name')?.textContent || '';
        const content = m.querySelector('.msg-content')?.innerText || '';
        const time = m.querySelector('.msg-time')?.textContent || '';
        const role = m.classList.contains('user') ? '**You**' : `**${name}**`;
        md += `### ${role} \u00B7 ${time}\n${content}\n\n---\n\n`;
    });
    const blob = new Blob([md], { type: 'text/markdown' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `root-chat-${Date.now()}.md`;
    a.click();
}

// ── Conversation Search ──────────────────────────────────────
function toggleConvSearch() {
    const bar = document.getElementById('conv-search-bar');
    if (!bar) return;
    const open = bar.style.display === 'none' || !bar.style.display;
    bar.style.display = open ? 'flex' : 'none';
    if (open) document.getElementById('conv-search-input')?.focus();
}

async function searchConversations(q) {
    if (!q || q.length < 2) {
        const r = document.getElementById('conv-search-results');
        if (r) r.remove();
        return;
    }
    const data = await api(`/api/conversations/search?q=${encodeURIComponent(q)}&limit=10`);
    const results = Array.isArray(data) ? data : [];
    let el = document.getElementById('conv-search-results');
    if (!el) {
        el = document.createElement('div');
        el.id = 'conv-search-results';
        el.className = 'conv-search-results';
        document.getElementById('conv-search-bar')?.insertAdjacentElement('afterend', el);
    }
    if (!results.length) { el.innerHTML = '<div class="conv-search-result">No results found.</div>'; return; }
    el.innerHTML = results.map(r => `
        <div class="conv-search-result" onclick="loadSessionMessages('${escHtml(r.session_id)}', null)">
            <div class="conv-search-result-title">${escHtml((r.session_title || r.session_id).slice(0, 40))}</div>
            ${escHtml((r.content || '').slice(0, 80))}...
        </div>
    `).join('');
}

// ── Artifacts Panel ──────────────────────────────────────────
let _artifacts = [];
let _activeArtifact = 0;

function openArtifacts(code, lang, title) {
    _artifacts.push({ code, lang, title: title || lang || 'Code' });
    _activeArtifact = _artifacts.length - 1;
    renderArtifacts();
    const panel = document.getElementById('artifacts-panel');
    if (panel) panel.classList.add('open');
}

function renderArtifacts() {
    const tabs = document.getElementById('artifacts-tabs');
    const codeEl = document.getElementById('artifacts-code');
    if (!tabs || !codeEl) return;
    tabs.innerHTML = _artifacts.map((a, i) => `
        <button class="artifact-tab ${i === _activeArtifact ? 'active' : ''}" onclick="switchArtifact(${i})">${escHtml(a.title)}</button>
    `).join('');
    const art = _artifacts[_activeArtifact];
    if (art) codeEl.textContent = art.code;
    const preview = document.getElementById('artifacts-preview');
    if (preview) preview.style.display = 'none';
    codeEl.style.display = '';
}

function switchArtifact(idx) {
    _activeArtifact = idx;
    renderArtifacts();
}

function closeArtifacts() {
    const panel = document.getElementById('artifacts-panel');
    if (panel) panel.classList.remove('open');
    _artifacts = [];
    _activeArtifact = 0;
}

function copyArtifact() {
    const art = _artifacts[_activeArtifact];
    if (art) navigator.clipboard.writeText(art.code).then(() => {
        const btn = document.querySelector('.artifact-action-btn');
        if (btn) { btn.style.color = 'var(--accent-green)'; setTimeout(() => btn.style.color = '', 1500); }
    });
}

function runArtifact() {
    const art = _artifacts[_activeArtifact];
    if (!art) return;
    const preview = document.getElementById('artifacts-preview');
    const codeEl = document.getElementById('artifacts-code');
    if (!preview || !codeEl) return;
    const isHtml = art.lang === 'html' || art.code.trim().startsWith('<');
    if (isHtml) {
        preview.srcdoc = art.code;
        preview.style.display = '';
        codeEl.style.display = 'none';
    } else {
        // For JS, wrap in HTML
        preview.srcdoc = `<html><body><script>${art.code}<\/script></body></html>`;
        preview.style.display = '';
        codeEl.style.display = 'none';
    }
}

// Auto-detect code blocks in assistant messages and offer artifacts
function _checkForArtifacts(content) {
    const codeBlockRegex = /```(\w*)\n([\s\S]+?)```/g;
    let match;
    let found = false;
    while ((match = codeBlockRegex.exec(content)) !== null) {
        const lang = match[1] || 'text';
        const code = match[2];
        if (code.length > 100) { // Only substantial blocks
            if (!found) {
                _artifacts = []; // Reset for new message
                found = true;
            }
            openArtifacts(code, lang, lang.charAt(0).toUpperCase() + lang.slice(1));
        }
    }
}

// ── Char counter ─────────────────────────────────────────────
function updateCharCount() {
    const inp = document.getElementById('chat-input');
    const cnt = document.getElementById('char-count');
    if (!inp || !cnt) return;
    const len = inp.value.length;
    cnt.textContent = len > 500 ? `${len.toLocaleString()} / 20,000` : '';
}

// ── Activity Feed ────────────────────────────────────────────
const _activityIcons = {
    builder: '\u{1F528}', proactive: '\u26A1', reflection: '\u{1F4AD}', autonomous: '\u{1F916}',
    trading: '\u{1F4C8}', memory: '\u{1F9E0}', directive: '\u26A1', network: '\u{1F578}',
    agent: '\u{1F916}', system: '\u{1F4A1}', goal: '\u{1F3AF}', error: '\u26A0',
};

function pushActivity(label, detail, type = 'system', panel = null) {
    const feed = document.getElementById('activity-feed');
    if (!feed) return;
    const icon = _activityIcons[type] || '\u{1F4A1}';
    const item = document.createElement('div');
    item.className = 'activity-item';
    item.innerHTML = `
        <div class="activity-icon">${icon}</div>
        <div class="activity-body">
            <div class="activity-label">${escHtml(label)}</div>
            ${detail ? `<div class="activity-detail">${escHtml(detail.slice(0, 80))}${detail.length > 80 ? '...' : ''}</div>` : ''}
        </div>`;
    if (panel) item.onclick = () => switchPanel(panel);
    feed.appendChild(item);
    // Auto-dismiss after 7s
    setTimeout(() => {
        item.style.opacity = '0';
        item.style.transform = 'translateX(110%)';
        setTimeout(() => item.remove(), 300);
    }, 7000);
    // Max 5 items
    while (feed.children.length > 5) feed.firstChild.remove();
}

function _handleWsActivity(topic, data) {
    const t = topic.split('.')[0];
    if (t === 'system') {
        const msg = data.message || data.description || data.event || '';
        if (msg) pushActivity('System', msg, 'system', 'dashboard');
    } else if (t === 'agent') {
        const name = data.agent_name || data.agent_id || '';
        const action = data.action || data.event || 'active';
        if (name) pushActivity(`${name} ${action}`, data.detail || '', 'agent', 'agents');
    } else if (t === 'collab') {
        pushActivity('Agent collaboration', data.task || data.description || '', 'agent', 'agents');
    }
}

// ── Slash Commands ────────────────────────────────────────────
const SLASH_COMMANDS = [
    { cmd: '/reflect', desc: 'Trigger self-reflection cycle', icon: '\u{1F4AD}', action: () => { api('/api/dashboard/reflect', {method:'POST'}); pushActivity('Reflection', 'Self-reflection cycle started', 'reflection'); } },
    { cmd: '/scan', desc: 'Scan markets for signals', icon: '\u{1F4E1}', action: () => { switchPanel('trading'); runTradeCycle(); } },
    { cmd: '/council', desc: 'Convene money strategy council', icon: '\u{1F3DB}', action: () => { switchPanel('money'); conveneCouncil(); } },
    { cmd: '/agents', desc: 'Open agents panel', icon: '\u{1F916}', action: () => switchPanel('agents') },
    { cmd: '/miro', desc: 'Open MiRo potentiality panel', icon: '\u2B50', action: () => switchPanel('miro') },
    { cmd: '/goals', desc: 'Open goals & tasks', icon: '\u{1F3AF}', action: () => switchPanel('goals') },
    { cmd: '/trading', desc: 'Open trading panel', icon: '\u{1F4C8}', action: () => switchPanel('trading') },
    { cmd: '/memory', desc: 'Open memory panel', icon: '\u{1F9E0}', action: () => switchPanel('memory') },
    { cmd: '/dashboard', desc: 'Open system dashboard', icon: '\u{1F4CA}', action: () => switchPanel('dashboard') },
    { cmd: '/directives', desc: 'Open autonomous directives', icon: '\u26A1', action: () => switchPanel('directives') },
    { cmd: '/sandbox', desc: 'Open sandbox gate controls', icon: '\uD83D\uDD12', action: () => switchPanel('sandbox') },
    { cmd: '/status', desc: 'Get full system status', icon: '\u{1F4A1}', action: () => { switchPanel('chat'); quickSend('Run a full system health check and tell me what needs attention'); } },
    { cmd: '/clear', desc: 'Clear conversation', icon: '\u{1F5D1}', action: () => { api('/api/chat/clear', {method:'POST'}); startNewChat(); } },
    { cmd: '/remember', desc: 'Save to memory: /remember <text>', icon: '\u{1F4CC}', action: (args) => {
        if (args) api('/api/chat/remember', {method:'POST', body:{content:args, memory_type:'fact'}})
            .then(() => pushActivity('Memory saved', args.slice(0,60), 'memory', 'memory'));
    }},
    { cmd: '/goal', desc: 'Create goal: /goal <title>', icon: '\u{1F3AF}', action: (args) => {
        if (args) api('/api/autonomy/goals', {method:'POST', body:{title:args, priority:5, category:'general'}})
            .then(() => { pushActivity('Goal created', args, 'goal', 'goals'); loadConversationSessions(); });
    }},
    { cmd: '/help', desc: 'Show available commands', icon: '\u2753', action: () => {
        const helpText = SLASH_COMMANDS.map(c => `${c.icon} \`${c.cmd}\` \u2014 ${c.desc}`).join('\n');
        appendMsg('assistant', 'ROOT', `**Available Commands**\n\n${helpText}`);
    }},
];

let _slashActive = false;
let _slashSelected = 0;

function _showSlashDropdown(query) {
    const dd = document.getElementById('slash-dropdown');
    const input = document.getElementById('chat-input');
    if (!dd || !input) return;
    const q = query.toLowerCase();
    const matches = SLASH_COMMANDS.filter(c => c.cmd.includes(q) || c.desc.toLowerCase().includes(q));
    if (!matches.length) { dd.style.display = 'none'; _slashActive = false; return; }
    dd.innerHTML = matches.map((c, i) => `
        <div class="slash-item ${i === _slashSelected ? 'selected' : ''}" onclick="executeSlashCommand('${c.cmd.slice(1)}','')">
            <span class="slash-icon">${c.icon}</span>
            <span class="slash-cmd">${c.cmd}</span>
            <span class="slash-desc">${escHtml(c.desc)}</span>
        </div>`).join('');
    // Position above the input
    const rect = input.getBoundingClientRect();
    dd.style.position = 'fixed';
    dd.style.left = rect.left + 'px';
    dd.style.bottom = (window.innerHeight - rect.top + 8) + 'px';
    dd.style.transform = 'none';
    dd.style.width = rect.width + 'px';
    dd.style.display = 'block';
    _slashActive = true;
}

function _hideSlashDropdown() {
    const dd = document.getElementById('slash-dropdown');
    if (dd) dd.style.display = 'none';
    _slashActive = false;
    _slashSelected = 0;
}

function executeSlashCommand(cmdName, args) {
    _hideSlashDropdown();
    const input = document.getElementById('chat-input');
    if (input) { input.value = ''; input.style.height = 'auto'; }
    const cmd = SLASH_COMMANDS.find(c => c.cmd === '/' + cmdName);
    if (cmd) cmd.action(args);
}

function _handleSlashInput(e, input) {
    const val = input.value;
    if (val.startsWith('/') && !val.includes(' ')) {
        _slashSelected = 0;
        _showSlashDropdown(val);
    } else if (val.startsWith('/') && val.includes(' ')) {
        _hideSlashDropdown();
    } else {
        _hideSlashDropdown();
    }
}

function _handleSlashKeydown(e, input) {
    if (!_slashActive) return;
    const dd = document.getElementById('slash-dropdown');
    const items = dd?.querySelectorAll('.slash-item');
    if (!items?.length) return;
    if (e.key === 'ArrowDown') {
        e.preventDefault();
        _slashSelected = Math.min(_slashSelected + 1, items.length - 1);
        items.forEach((el, i) => el.classList.toggle('selected', i === _slashSelected));
    } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        _slashSelected = Math.max(_slashSelected - 1, 0);
        items.forEach((el, i) => el.classList.toggle('selected', i === _slashSelected));
    } else if (e.key === 'Enter' && _slashActive) {
        e.preventDefault();
        const val = input.value;
        const spaceIdx = val.indexOf(' ');
        const cmdName = (spaceIdx > -1 ? val.slice(1, spaceIdx) : val.slice(1));
        const args = spaceIdx > -1 ? val.slice(spaceIdx + 1) : '';
        executeSlashCommand(cmdName, args);
    } else if (e.key === 'Escape') {
        _hideSlashDropdown();
    }
}

// ── Smart Follow-Up Suggestions (Perplexity-style) ───────────
let _suggestionsDebounce = null;
function _showFollowUpSuggestions(responseContent) {
    // Clear previous suggestions chip row
    document.querySelectorAll('.followup-chips').forEach(el => el.remove());
    clearTimeout(_suggestionsDebounce);
    _suggestionsDebounce = setTimeout(async () => {
        try {
            // Extract 3 follow-up questions via Haiku (fast)
            const res = await api('/api/chat', {
                method: 'POST',
                body: {
                    message: `Given this AI response, generate exactly 3 short follow-up questions a user might ask next. Return ONLY a JSON array of 3 strings, nothing else.\n\nResponse: "${responseContent.slice(0, 500)}"`,
                    model_tier: 'fast',
                },
            });
            const raw = (res.response || res.content || '').trim();
            let questions = [];
            try { questions = JSON.parse(raw); } catch {
                // Try to extract array from text
                const match = raw.match(/\[[\s\S]*\]/);
                if (match) try { questions = JSON.parse(match[0]); } catch {}
            }
            if (!Array.isArray(questions) || questions.length === 0) return;
            const container = document.getElementById('chat-scroll');
            if (!container) return;
            const chipsEl = document.createElement('div');
            chipsEl.className = 'followup-chips';
            chipsEl.innerHTML = questions.slice(0, 3).map(q =>
                `<button class="followup-chip" onclick="sendFollowUp(this)">${escHtml(String(q).slice(0, 80))}</button>`
            ).join('');
            container.appendChild(chipsEl);
            scrollChat();
        } catch { /* silent */ }
    }, 800);
}

function sendFollowUp(btn) {
    const text = btn.textContent;
    document.querySelectorAll('.followup-chips').forEach(el => el.remove());
    const input = document.getElementById('chat-input');
    if (input) { input.value = text; sendMessage(); }
}

// ── Session Title Generator ──────────────────────────────────
async function _generateSessionTitle(sessionId, firstMessage) {
    if (!sessionId || !firstMessage) return;
    try {
        await api(`/api/conversations/sessions/${sessionId}/title`, {
            method: 'POST',
            body: { first_message: firstMessage },
        });
        // Refresh sidebar after title generated
        setTimeout(loadConversationSessions, 500);
    } catch { /* silent — titles are cosmetic */ }
}

// ── Memory Pin Modal ─────────────────────────────────────────
function pinMsg(btn) {
    const msgEl = btn.closest('.msg');
    const content = msgEl?.querySelector('.msg-content')?.textContent || '';
    const modal = document.getElementById('pin-modal');
    const ta = document.getElementById('pin-content');
    if (modal && ta) {
        ta.value = content.slice(0, 500);
        modal.style.display = 'flex';
    }
}

function closePinModal() {
    const modal = document.getElementById('pin-modal');
    if (modal) modal.style.display = 'none';
}

async function saveMemoryPin() {
    const content = document.getElementById('pin-content')?.value?.trim();
    const type = document.getElementById('pin-type')?.value || 'fact';
    const tags = (document.getElementById('pin-tags')?.value || '').split(',').map(t => t.trim()).filter(Boolean);
    if (!content) return;
    await api('/api/chat/remember', { method: 'POST', body: { content, memory_type: type, tags } });
    closePinModal();
    pushActivity('Memory pinned', content.slice(0, 60), 'memory', 'memory');
}

// ── Sandbox Badge ───────────────────────────────────────────
async function updateSandboxBadge() {
    const badge = document.getElementById('sandbox-badge');
    if (!badge) return;
    try {
        const res = await api('/api/sandbox/status');
        if (res.error) return;
        const mode = res.global_mode || 'sandbox';
        badge.textContent = mode.toUpperCase();
        badge.className = 'sandbox-badge ' + mode;
    } catch {
        // Endpoint may not exist yet — keep default badge
    }
}

// ══════════════════════════════════════════════════════════════
// FEATURE: Message Search — search visible messages in chat
// ══════════════════════════════════════════════════════════════
let _msgSearchMatches = [];
let _msgSearchIdx = 0;
let _msgSearchOriginals = new Map(); // msgEl.id → original innerHTML backup

function openMsgSearch() {
    const overlay = document.getElementById('msg-search-overlay');
    if (!overlay) return;
    overlay.classList.add('open');
    const inp = document.getElementById('msg-search-input');
    if (inp) { inp.value = ''; inp.focus(); }
    _msgSearchMatches = [];
    _msgSearchIdx = 0;
    _updateMsgSearchCount();
}

function closeMsgSearch() {
    const overlay = document.getElementById('msg-search-overlay');
    if (overlay) overlay.classList.remove('open');
    _clearMsgHighlights();
    _msgSearchMatches = [];
    _msgSearchIdx = 0;
}

function _clearMsgHighlights() {
    document.querySelectorAll('#chat-scroll .msg-content').forEach(el => {
        const backup = _msgSearchOriginals.get(el);
        if (backup !== undefined) el.innerHTML = backup;
    });
    _msgSearchOriginals.clear();
}

function msgSearchQuery(query) {
    _clearMsgHighlights();
    _msgSearchMatches = [];
    _msgSearchIdx = 0;

    if (!query || query.length < 2) {
        _updateMsgSearchCount();
        return;
    }

    const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const regex = new RegExp(`(${escaped})`, 'gi');
    const contentEls = document.querySelectorAll('#chat-scroll .msg-content');

    contentEls.forEach(el => {
        const text = el.textContent || '';
        if (regex.test(text)) {
            _msgSearchOriginals.set(el, el.innerHTML);
            // Walk text nodes to avoid breaking HTML
            _highlightTextInEl(el, regex);
            const marks = el.querySelectorAll('mark.msg-highlight');
            marks.forEach(m => _msgSearchMatches.push(m));
        }
        regex.lastIndex = 0;
    });

    if (_msgSearchMatches.length > 0) {
        _msgSearchIdx = 0;
        _applyCurrentHighlight();
    }
    _updateMsgSearchCount();
}

function _highlightTextInEl(el, regex) {
    // Replace text content in text nodes only, skipping child elements
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, null);
    const textNodes = [];
    let node;
    while ((node = walker.nextNode())) textNodes.push(node);
    textNodes.forEach(tn => {
        const parent = tn.parentNode;
        if (!parent || parent.tagName === 'MARK') return;
        const parts = tn.textContent.split(regex);
        if (parts.length <= 1) return;
        const frag = document.createDocumentFragment();
        parts.forEach((part, i) => {
            if (i % 2 === 0) {
                if (part) frag.appendChild(document.createTextNode(part));
            } else {
                const mark = document.createElement('mark');
                mark.className = 'msg-highlight';
                mark.textContent = part;
                frag.appendChild(mark);
            }
        });
        parent.replaceChild(frag, tn);
    });
}

function _applyCurrentHighlight() {
    _msgSearchMatches.forEach((m, i) => {
        m.classList.toggle('current', i === _msgSearchIdx);
    });
    const cur = _msgSearchMatches[_msgSearchIdx];
    if (cur) cur.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function msgSearchNav(dir) {
    if (!_msgSearchMatches.length) return;
    _msgSearchIdx = (_msgSearchIdx + dir + _msgSearchMatches.length) % _msgSearchMatches.length;
    _applyCurrentHighlight();
    _updateMsgSearchCount();
}

function _updateMsgSearchCount() {
    const el = document.getElementById('msg-search-count');
    if (!el) return;
    if (_msgSearchMatches.length === 0) {
        el.textContent = '0/0';
    } else {
        el.textContent = `${_msgSearchIdx + 1}/${_msgSearchMatches.length}`;
    }
}


// ══════════════════════════════════════════════════════════════
// FEATURE: Message Reactions — thumbs up/down, star, bookmark
// ══════════════════════════════════════════════════════════════
function bookmarkMsg(btn) {
    btn.classList.toggle('bookmarked');
    const isBookmarked = btn.classList.contains('bookmarked');
    btn.innerHTML = isBookmarked ? '&#128278;' : '&#128279;'; // bookmark vs bookmark outline
    btn.title = isBookmarked ? 'Bookmarked' : 'Bookmark';
    if (isBookmarked) {
        const msgEl = btn.closest('.msg');
        const name = msgEl?.querySelector('.msg-name')?.textContent || '';
        const content = msgEl?.querySelector('.msg-content')?.textContent?.slice(0, 80) || '';
        const time = msgEl?.querySelector('.msg-time')?.textContent || '';
        pushActivity('Message bookmarked', `${name}: ${content}`, 'memory');
    }
}


// ══════════════════════════════════════════════════════════════
// FEATURE: Typing Indicator — enhanced dots shown while AI thinks
//   Already in appendThinking(). The CSS handles animation.
//   This adds a richer inline typing dots version for status area.
// ══════════════════════════════════════════════════════════════
function appendTypingIndicator(agentName) {
    // Used by streaming to show a lightweight "typing" message before tokens arrive
    const container = document.getElementById('chat-scroll');
    if (!container) return null;
    const id = `typing-${Date.now()}`;
    const div = document.createElement('div');
    div.className = 'msg assistant';
    div.id = id;
    div.innerHTML = `
        <div class="msg-avatar" style="background:${AGENT_COLORS.astra}">A</div>
        <div class="msg-body">
            <div class="msg-header">
                <span class="msg-name">${escHtml(agentName || 'ASTRA')}</span>
                <span class="msg-time">${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
            </div>
            <div class="msg-content">
                <div class="typing-dots"><span></span><span></span><span></span></div>
            </div>
        </div>`;
    container.appendChild(div);
    scrollChat();
    return id;
}


// ══════════════════════════════════════════════════════════════
// FEATURE: Message Threading — reply to specific messages
// ══════════════════════════════════════════════════════════════
let _replyTarget = null; // { id, name, preview }

function replyToMsg(btn) {
    const msgEl = btn.closest('.msg');
    if (!msgEl) return;
    const name = msgEl.querySelector('.msg-name')?.textContent || 'message';
    const content = msgEl.querySelector('.msg-content')?.textContent?.slice(0, 100) || '';
    _replyTarget = { id: msgEl.id, name, preview: content };

    const indicator = document.getElementById('reply-compose-indicator');
    const nameEl = document.getElementById('reply-compose-name');
    const previewEl = document.getElementById('reply-compose-preview');
    if (indicator && nameEl && previewEl) {
        nameEl.textContent = name;
        previewEl.textContent = content.length > 60 ? content.slice(0, 60) + '...' : content;
        indicator.style.display = 'flex';
    }
    document.getElementById('chat-input')?.focus();
    // Scroll the target message into view to confirm selection
    msgEl.style.outline = '2px solid var(--accent)';
    msgEl.style.outlineOffset = '2px';
    setTimeout(() => { msgEl.style.outline = ''; msgEl.style.outlineOffset = ''; }, 1000);
}

function cancelReply() {
    _replyTarget = null;
    const indicator = document.getElementById('reply-compose-indicator');
    if (indicator) indicator.style.display = 'none';
}

// Override appendMsg — calls _appendMsgCore and adds reply/bookmark/threading
function appendMsg(role, name, content, isThinking = false, agentId = null) {
    // Stash current reply target and clear before the original call
    const replyCtx = _replyTarget;
    if (role === 'user' && replyCtx) _replyTarget = null;

    const id = _appendMsgCore(role, name, content, isThinking, agentId);
    const msgEl = document.getElementById(id);
    if (!msgEl) return id;

    // Inject reply-to preview inside msg-body if this message is a reply
    if (role === 'user' && replyCtx && msgEl) {
        const body = msgEl.querySelector('.msg-body');
        if (body) {
            const replyDiv = document.createElement('div');
            replyDiv.className = 'msg-reply-preview';
            replyDiv.innerHTML = `<strong>${escHtml(replyCtx.name)}</strong>${escHtml(replyCtx.preview.slice(0, 80))}`;
            replyDiv.title = 'Jump to original message';
            replyDiv.onclick = () => {
                const target = document.getElementById(replyCtx.id);
                if (target) {
                    target.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    target.style.outline = '2px solid var(--accent)';
                    target.style.outlineOffset = '2px';
                    setTimeout(() => { target.style.outline = ''; target.style.outlineOffset = ''; }, 1200);
                }
            };
            const content = body.querySelector('.msg-content');
            if (content) body.insertBefore(replyDiv, content);
        }
    }

    // Add reply + bookmark buttons to assistant action bar
    if (!isThinking && role === 'assistant') {
        const actions = msgEl.querySelector('.msg-actions');
        if (actions) {
            // Insert Reply button at start
            const replyBtn = document.createElement('button');
            replyBtn.className = 'msg-action-btn';
            replyBtn.title = 'Reply';
            replyBtn.innerHTML = '&#8617;';
            replyBtn.onclick = function() { replyToMsg(this); };
            actions.insertBefore(replyBtn, actions.firstChild);

            // Insert Bookmark button after star
            const bookmarkBtn = document.createElement('button');
            bookmarkBtn.className = 'msg-action-btn';
            bookmarkBtn.title = 'Bookmark';
            bookmarkBtn.innerHTML = '&#128279;';
            bookmarkBtn.onclick = function() { bookmarkMsg(this); };
            actions.appendChild(bookmarkBtn);
        }
    }

    // Hide the reply indicator after user sends
    if (role === 'user') cancelReply();

    return id;
}


// ══════════════════════════════════════════════════════════════
// FEATURE: Code Block Execution Preview (JS inline, Python note)
// ══════════════════════════════════════════════════════════════

// Override renderMarkdown — calls _renderMarkdownCore and adds Run buttons
function renderMarkdown(text) {
    let html = _renderMarkdownCore(text);
    // Add run button to code block headers for js/javascript and python
    html = html.replace(
        /(<div class="code-block-hdr">)(<span class="code-lang-tag">(javascript|js|python|py)<\/span>)(.*?)(<button class="code-copy-btn")/g,
        (match, hdrOpen, langSpan, lang, middle, copyBtn) => {
            const isJS = lang === 'javascript' || lang === 'js';
            const isPy = lang === 'python' || lang === 'py';
            const runHtml = `<button class="code-run-btn" onclick="_runCodeBlock(this,'${isJS ? 'js' : 'py'}')">&#9654; Run</button>`;
            return `${hdrOpen}${langSpan}${runHtml}${middle}${copyBtn}`;
        }
    );
    return html;
}

function _runCodeBlock(btn, lang) {
    const wrap = btn.closest('.code-block-wrap');
    if (!wrap) return;
    const codeEl = wrap.querySelector('pre code');
    if (!codeEl) return;

    // Find code from buffer via copy button's key
    const copyBtn = wrap.querySelector('.code-copy-btn');
    const key = copyBtn?.dataset?.key;
    const code = (key && _codeBuf[key]) ? _codeBuf[key] : codeEl.textContent;

    // Remove previous output
    const prev = wrap.querySelector('.code-exec-output');
    if (prev) prev.remove();

    const out = document.createElement('div');
    out.className = 'code-exec-output';

    if (lang === 'js') {
        // Capture console.log output
        const logs = [];
        const origLog = console.log;
        const origError = console.error;
        console.log = (...args) => { logs.push(args.map(String).join(' ')); origLog.apply(console, args); };
        console.error = (...args) => { logs.push('[error] ' + args.map(String).join(' ')); origError.apply(console, args); };
        try {
            // eslint-disable-next-line no-new-func
            const result = new Function(code)();
            console.log = origLog;
            console.error = origError;
            const output = logs.length ? logs.join('\n') : (result !== undefined ? String(result) : '(no output)');
            out.innerHTML = `<span class="exec-ok">&#10003; ${escHtml(output)}</span>`;
        } catch (e) {
            console.log = origLog;
            console.error = origError;
            out.innerHTML = `<span class="exec-error">&#9888; ${escHtml(e.message)}</span>`;
        }
        wrap.appendChild(out);
    } else {
        // Python — show a helpful note (Pyodide integration point)
        out.innerHTML = `<span style="color:var(--text-muted)">Python execution requires a backend sandbox. Use the <strong>/sandbox</strong> panel or copy this code to run locally.</span>`;
        wrap.appendChild(out);
    }

    btn.textContent = 'Ran';
    setTimeout(() => { btn.innerHTML = '&#9654; Run'; }, 3000);
}


// ══════════════════════════════════════════════════════════════
// FEATURE: Drag & Drop File Upload
// ══════════════════════════════════════════════════════════════
function _initDragDrop() {
    const chatMain = document.querySelector('.chat-main');
    const dropZone = document.getElementById('chat-drop-zone');
    if (!chatMain || !dropZone) return;

    let _dragCounter = 0;

    chatMain.addEventListener('dragenter', e => {
        e.preventDefault();
        _dragCounter++;
        dropZone.classList.add('active');
    });
    chatMain.addEventListener('dragleave', e => {
        e.preventDefault();
        _dragCounter--;
        if (_dragCounter <= 0) { _dragCounter = 0; dropZone.classList.remove('active'); }
    });
    chatMain.addEventListener('dragover', e => {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'copy';
    });
    chatMain.addEventListener('drop', e => {
        e.preventDefault();
        _dragCounter = 0;
        dropZone.classList.remove('active');
        const file = e.dataTransfer.files?.[0];
        if (!file) return;
        if (file.size > 10 * 1024 * 1024) {
            pushActivity('File too large', 'Max 10MB allowed', 'error');
            return;
        }
        // Reuse existing file handling
        pendingFile = file;
        const preview = document.getElementById('file-preview');
        if (preview) {
            document.getElementById('file-name').textContent = file.name;
            const sizeKB = (file.size / 1024).toFixed(1);
            const sizeStr = file.size > 1024 * 1024
                ? (file.size / 1024 / 1024).toFixed(1) + ' MB'
                : sizeKB + ' KB';
            document.getElementById('file-size').textContent = sizeStr;
            preview.style.display = 'block';
        }
        pushActivity('File attached', file.name, 'system');
        document.getElementById('chat-input')?.focus();
    });

    // Also support dropping onto the whole window to handle global drags
    document.addEventListener('dragover', e => e.preventDefault());
}


// ══════════════════════════════════════════════════════════════
// FEATURE: Keyboard Shortcuts Panel
// ══════════════════════════════════════════════════════════════
function openShortcutsPanel() {
    const overlay = document.getElementById('shortcuts-overlay');
    if (overlay) overlay.classList.add('open');
}

function closeShortcutsPanel() {
    const overlay = document.getElementById('shortcuts-overlay');
    if (overlay) overlay.classList.remove('open');
}


// ══════════════════════════════════════════════════════════════
// FEATURE: Conversation Bookmarking
// ══════════════════════════════════════════════════════════════
let _bookmarkedSessions = new Set();

function _loadBookmarks() {
    try {
        const stored = JSON.parse(localStorage.getItem('root-bookmarked-sessions') || '[]');
        _bookmarkedSessions = new Set(stored);
    } catch { _bookmarkedSessions = new Set(); }
}

function _saveBookmarks() {
    try {
        localStorage.setItem('root-bookmarked-sessions', JSON.stringify([..._bookmarkedSessions]));
    } catch {}
}

function toggleConvBookmark(sessionId, btn, title) {
    if (_bookmarkedSessions.has(sessionId)) {
        _bookmarkedSessions.delete(sessionId);
        if (btn) { btn.classList.remove('bookmarked'); btn.title = 'Bookmark'; btn.innerHTML = '&#9734;'; }
    } else {
        _bookmarkedSessions.add(sessionId);
        if (btn) { btn.classList.add('bookmarked'); btn.title = 'Remove bookmark'; btn.innerHTML = '&#9733;'; }
        pushActivity('Conversation bookmarked', title || sessionId, 'memory');
    }
    _saveBookmarks();
    _renderBookmarksSidebar();
}

function _renderBookmarksSidebar() {
    const container = document.getElementById('sidebar-bookmarks');
    const section = document.getElementById('bookmarks-section');
    if (!container || !section) return;

    if (_bookmarkedSessions.size === 0) {
        section.style.display = 'none';
        return;
    }
    section.style.display = '';

    // Get session titles from existing conv-items
    const titleMap = {};
    document.querySelectorAll('.conv-item[data-session-id]').forEach(el => {
        const sid = el.dataset.sessionId;
        const title = el.querySelector('.conv-item-title')?.textContent || sid;
        if (sid) titleMap[sid] = title;
    });

    container.innerHTML = [..._bookmarkedSessions].map(sid => {
        const title = titleMap[sid] || `Session ${sid.slice(-6)}`;
        return `<div class="conv-item" data-session-id="${escHtml(sid)}" onclick="loadSessionMessages('${escHtml(sid)}', this)" style="padding:6px 10px">
            <div class="conv-item-main">
                <div class="conv-item-title" style="font-size:12px">&#9733; ${escHtml(title.slice(0, 40))}${title.length > 40 ? '\u2026' : ''}</div>
            </div>
        </div>`;
    }).join('');
}

// Override loadConversationSessions to add bookmark buttons after loading
async function loadConversationSessions() {
    await _loadConvSessionsCore();
    _loadBookmarks();
    // Add bookmark buttons to each conv-item
    const container = document.getElementById('sidebar-conversations');
    if (!container) return;
    container.querySelectorAll('.conv-item').forEach((item, i) => {
        // Inject session ID from onclick attribute (parse it out)
        const onclickStr = item.getAttribute('onclick') || '';
        const match = onclickStr.match(/loadSessionMessages\('([^']+)'/);
        if (!match) return;
        const sessionId = match[1];
        item.dataset.sessionId = sessionId;

        // Wrap existing content in .conv-item-main if not already done
        if (!item.querySelector('.conv-item-main')) {
            const children = [...item.childNodes];
            const main = document.createElement('div');
            main.className = 'conv-item-main';
            children.forEach(c => main.appendChild(c));
            item.appendChild(main);
        }

        if (!item.querySelector('.conv-item-actions')) {
            const actions = document.createElement('div');
            actions.className = 'conv-item-actions';
            const isBookmarked = _bookmarkedSessions.has(sessionId);
            const title = item.querySelector('.conv-item-title')?.textContent || '';
            actions.innerHTML = `<button class="conv-item-action-btn ${isBookmarked ? 'bookmarked' : ''}"
                onclick="event.stopPropagation();toggleConvBookmark('${escHtml(sessionId)}',this,'${escHtml(title)}')"
                title="${isBookmarked ? 'Remove bookmark' : 'Bookmark'}">${isBookmarked ? '&#9733;' : '&#9734;'}</button>`;
            item.appendChild(actions);
        }
    });
    _renderBookmarksSidebar();
}


// ══════════════════════════════════════════════════════════════
// ── Init ────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    try {
        const saved = localStorage.getItem('root-theme-v2');
        setTheme(saved && THEME_DOTS[saved] ? saved : 'nebula');
    } catch { setTheme('nebula'); }

    document.querySelectorAll('.theme-btn').forEach(btn => {
        btn.addEventListener('click', () => setTheme(btn.dataset.theme));
    });

    const chatInput = document.getElementById('chat-input');
    if (chatInput) {
        chatInput.addEventListener('keydown', e => {
            _handleSlashKeydown(e, chatInput);
            if (!_slashActive && e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
        });
        chatInput.addEventListener('input', () => {
            autoResize(chatInput);
            _handleSlashInput(null, chatInput);
            updateCharCount();
        });
    }

    const ms = document.getElementById('memory-search');
    if (ms) ms.addEventListener('keydown', e => { if (e.key === 'Enter') searchMemories(); });

    // Message search input: Enter = next, Shift+Enter = prev, Escape = close
    const msgSearchInp = document.getElementById('msg-search-input');
    if (msgSearchInp) {
        msgSearchInp.addEventListener('keydown', e => {
            if (e.key === 'Enter') { e.preventDefault(); msgSearchNav(e.shiftKey ? -1 : 1); }
            if (e.key === 'Escape') { e.preventDefault(); closeMsgSearch(); }
        });
    }

    document.querySelectorAll('.nav-item[data-panel]').forEach(el => {
        el.addEventListener('click', () => {
            switchPanel(el.dataset.panel);
            if (window.innerWidth <= 768) {
                document.querySelector('.sidebar').classList.remove('open');
                document.querySelector('.mobile-overlay').classList.remove('active');
            }
        });
    });
    document.querySelectorAll('.channel-item[data-panel]').forEach(el => {
        el.addEventListener('click', () => {
            switchPanel(el.dataset.panel);
            if (window.innerWidth <= 768) {
                document.querySelector('.sidebar').classList.remove('open');
                document.querySelector('.mobile-overlay').classList.remove('active');
            }
        });
    });

    // Connect WebSocket for real-time updates
    ws.connect();

    // Auto-refresh dashboard when receiving system events
    ws.on('system.*', (data, topic) => {
        if (state.activePanel === 'dashboard') loadDashboard();
        _handleWsActivity(topic, data);
    });
    ws.on('agent.*', (data, topic) => _handleWsActivity(topic, data));
    ws.on('collab.*', (data, topic) => _handleWsActivity(topic, data));

    // Initial health check
    fetch('/api/health')
        .then(r => r.json())
        .then(data => {
            const gs = document.getElementById('global-status');
            if (gs) gs.classList.remove('offline');
            const mt = document.getElementById('mode-text');
            if (mt) mt.textContent = data.mode === 'online' ? 'Online' : 'Offline';
        })
        .catch(() => {
            const gs = document.getElementById('global-status');
            if (gs) gs.classList.add('offline');
            const mt = document.getElementById('mode-text');
            if (mt) mt.textContent = 'Disconnected';
        });

    loadDashboard();
    loadNotifications();
    loadConversationSessions();
    loadChatHistory();
    updateSandboxBadge();

    // Poll notifications every 60s (clear previous to prevent leaks)
    if (window._notifInterval) clearInterval(window._notifInterval);
    window._notifInterval = setInterval(loadNotifications, 60000);

    // Fallback polling (WebSocket handles most updates, this is backup)
    if (window._fallbackPollInterval) clearInterval(window._fallbackPollInterval);
    window._fallbackPollInterval = setInterval(() => {
        if (state.activePanel === 'dashboard' && !ws.connected) loadDashboard();
    }, 30000);

    switchPanel('chat');

    // Initialize drag & drop
    _initDragDrop();

    // Load bookmarks
    _loadBookmarks();
    _renderBookmarksSidebar();
});
