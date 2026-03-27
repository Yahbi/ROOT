/* ROOT — Extended WebSocket Handlers + Toast Notifications
   Extends the ws object in root.js with additional topic subscriptions
   and provides domain-specific event routing. */

// ── Extended Topics ─────────────────────────────────────────
const WS_TOPICS = [
    'system.*', 'agent.*', 'collab.*', 'network.*',
    'memory.*', 'goal.*', 'trade.*', 'prediction.*',
    'experiment.*', 'directive.*', 'cost.*', 'skill.*',
    'sandbox.*', 'experience.*', 'approval.*', 'revenue.*', 'plugin.*'
];

// Map topic prefix -> panel name for auto-refresh
const TOPIC_PANEL_MAP = {
    system:     'dashboard',
    agent:      'agents',
    collab:     'agents',
    network:    'network',
    memory:     'memory',
    goal:       'goals',
    trade:      'trading',
    prediction: 'miro',
    experiment: 'civilization',
    directive:  'directives',
    cost:       'analytics',
    skill:      'agents',
    sandbox:    null,
    experience: 'civilization',
    approval:   'dashboard',
    revenue:    'civilization',
    plugin:     'plugins'
};

// Topics that trigger a toast notification
const TOAST_TOPICS = new Set([
    'approval', 'trade', 'experiment', 'directive', 'revenue', 'sandbox'
]);

// ── Subscribe to Extended Topics ────────────────────────────
function wsSubscribeExtended() {
    if (!ws || !ws.conn || ws.conn.readyState !== WebSocket.OPEN) return;
    ws.conn.send(JSON.stringify({ subscribe: WS_TOPICS }));
}

// ── Domain Event Handler ────────────────────────────────────
function handleWsEvent(topic, data) {
    const prefix = _topicPrefix(topic);
    const action = _topicAction(topic);

    // Auto-refresh active panel if it matches the domain
    const panelName = TOPIC_PANEL_MAP[prefix];
    if (panelName && state.activePanel === panelName) {
        _refreshPanel(panelName);
    }

    // Sandbox badge update
    if (prefix === 'sandbox') {
        updateSandboxBadge();
    }

    // Toast for important events
    if (TOAST_TOPICS.has(prefix)) {
        const msg = _formatEventMessage(prefix, action, data);
        const type = _eventToastType(prefix, action);
        showToast(msg, type);
    }

    // Store in activity feed
    _pushToActivityFeed(topic, data);
}

// ── Toast Notification System ───────────────────────────────
const TOAST_COLORS = {
    info:    { bg: 'var(--accent)',       border: 'var(--accent-hover)' },
    success: { bg: 'var(--accent-green)', border: '#2bb87a' },
    warning: { bg: 'var(--accent-gold)',  border: '#e5a800' },
    error:   { bg: 'var(--accent-red)',   border: '#e04040' },
    live:    { bg: 'var(--accent-red)',   border: '#e04040' }
};

let _toastCounter = 0;

function showToast(message, type = 'info', duration = 4000) {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const id = `toast-${++_toastCounter}`;
    const colors = TOAST_COLORS[type] || TOAST_COLORS.info;
    const pulseClass = type === 'live' ? ' toast--live' : '';

    const toast = document.createElement('div');
    toast.id = id;
    toast.className = `toast toast--${type}${pulseClass}`;
    toast.setAttribute('role', 'alert');
    toast.innerHTML = `
        <span class="toast-message">${escHtml(message)}</span>
        <button class="toast-dismiss" onclick="_dismissToast('${id}')" aria-label="Dismiss">&times;</button>`;

    container.appendChild(toast);

    // Trigger entrance animation
    requestAnimationFrame(() => toast.classList.add('toast--visible'));

    // Auto-dismiss
    if (duration > 0) {
        setTimeout(() => _dismissToast(id), duration);
    }
}

function _dismissToast(id) {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.remove('toast--visible');
    el.classList.add('toast--exit');
    setTimeout(() => { if (el.parentNode) el.parentNode.removeChild(el); }, 300);
}

// ── Activity Feed (last N events) ───────────────────────────
const _activityFeed = [];
const ACTIVITY_FEED_MAX = 50;

function _pushToActivityFeed(topic, data) {
    const entry = {
        topic,
        data,
        timestamp: Date.now()
    };
    _activityFeed.unshift(entry);
    if (_activityFeed.length > ACTIVITY_FEED_MAX) {
        _activityFeed.length = ACTIVITY_FEED_MAX;
    }
}

function getActivityFeed() {
    return [..._activityFeed];
}

// ── Private Helpers ─────────────────────────────────────────
function _topicPrefix(topic) {
    const dot = topic.indexOf('.');
    return dot > 0 ? topic.substring(0, dot) : topic;
}

function _topicAction(topic) {
    const dot = topic.indexOf('.');
    return dot > 0 ? topic.substring(dot + 1) : '';
}

function _formatEventMessage(prefix, action, data) {
    const label = prefix.charAt(0).toUpperCase() + prefix.slice(1);
    const detail = (data && data.message) || (data && data.name) || action || 'update';
    return `${label}: ${detail}`;
}

function _eventToastType(prefix, action) {
    if (prefix === 'approval') return 'warning';
    if (prefix === 'trade') return action === 'error' ? 'error' : 'info';
    if (prefix === 'experiment' && action === 'completed') return 'success';
    if (prefix === 'sandbox') return 'warning';
    if (prefix === 'revenue') return 'success';
    return 'info';
}

function _refreshPanel(panelName) {
    // Calls existing panel loaders defined in root.js
    const loaders = {
        dashboard:    typeof loadDashboard === 'function' ? loadDashboard : null,
        agents:       typeof loadAgents === 'function' ? loadAgents : null,
        memory:       typeof loadMemory === 'function' ? loadMemory : null,
        goals:        typeof loadGoals === 'function' ? loadGoals : null,
        trading:      typeof loadTrading === 'function' ? loadTrading : null,
        miro:         typeof loadMiro === 'function' ? loadMiro : null,
        civilization: typeof loadCivilization === 'function' ? loadCivilization : null,
        directives:   typeof loadDirectives === 'function' ? loadDirectives : null,
        network:      typeof loadNetwork === 'function' ? loadNetwork : null,
        plugins:      typeof loadPlugins === 'function' ? loadPlugins : null,
        analytics:    typeof loadAnalytics === 'function' ? loadAnalytics : null
    };
    const loader = loaders[panelName];
    if (loader) loader();
}

// ── Wire into existing ws object ────────────────────────────
// This runs after root.js has initialized ws.
// We register a catch-all handler for all extended topics.
(function _wireWsHandlers() {
    if (typeof ws === 'undefined' || !ws.on) {
        // Retry after root.js loads
        setTimeout(_wireWsHandlers, 200);
        return;
    }

    // Re-subscribe with full topic list when connection opens
    if (typeof ws.connect === 'function') {
        const origConnect = ws.connect.bind(ws);
        ws.connect = function() {
            origConnect();
            // Chain onopen to also subscribe to extended topics
            if (ws.conn) {
                const origOnOpen = ws.conn.onopen;
                ws.conn.onopen = function(evt) {
                    if (origOnOpen) origOnOpen.call(this, evt);
                    wsSubscribeExtended();
                };
            }
        };
    }

    // Register handlers for all extended topic prefixes
    for (const prefix of Object.keys(TOPIC_PANEL_MAP)) {
        ws.on(`${prefix}.*`, (data, topic) => handleWsEvent(topic, data));
    }
})();
