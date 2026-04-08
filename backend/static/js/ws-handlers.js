/* ROOT — Extended WebSocket Handlers + Toast Notifications
   Extends the ws object in root.js with additional topic subscriptions
   and provides domain-specific event routing.

   Enhanced features (v1.1):
   - Reconnection with exponential backoff (1s → 2s → 4s → 8s, max 30s)
   - Connection state management (connecting / connected / disconnected / error)
   - Offline message queue (flushed on reconnect)
   - Heartbeat (ping every 30s, stale-connection detection via pong timeout)
   - Event deduplication (skip duplicate messages within 1s)
   - Subscription management (subscribe / unsubscribe per topic)
   - Visual connection status indicator with state-aware animation
*/

// ── Extended Topics ─────────────────────────────────────────
const WS_TOPICS = [
    'system.*', 'agent.*', 'collab.*', 'network.*',
    'memory.*', 'goal.*', 'trade.*', 'prediction.*',
    'experiment.*', 'directive.*', 'cost.*', 'skill.*',
    'sandbox.*', 'experience.*', 'approval.*', 'revenue.*', 'plugin.*',
    'intelligence.*', 'swarm.*', 'research.*'
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
    plugin:     'plugins',
    intelligence: 'dashboard',
    swarm:      'agents',
    research:   'dashboard',
};

// Topics that trigger a toast notification
const TOAST_TOPICS = new Set([
    'approval', 'trade', 'experiment', 'directive', 'revenue', 'sandbox',
    'intelligence', 'swarm'
]);

// ── Connection State Machine ────────────────────────────────
// States: 'connecting' | 'connected' | 'disconnected' | 'error'
const WsState = Object.freeze({
    CONNECTING:   'connecting',
    CONNECTED:    'connected',
    DISCONNECTED: 'disconnected',
    ERROR:        'error',
});

let _wsCurrentState = WsState.DISCONNECTED;

function _setWsState(newState) {
    if (_wsCurrentState === newState) return;
    const prev = _wsCurrentState;
    _wsCurrentState = newState;
    _updateConnectionIndicator(newState);
    // Notify any registered state-change listeners
    _wsStateListeners.forEach(fn => { try { fn(newState, prev); } catch (e) { console.warn('[ws] state listener error', e); } });
}

const _wsStateListeners = [];

/**
 * Register a callback that fires whenever the WS connection state changes.
 * @param {function(newState: string, prevState: string): void} fn
 */
function onWsStateChange(fn) {
    _wsStateListeners.push(fn);
}

/** Read-only view of the current connection state. */
function getWsState() { return _wsCurrentState; }

// ── Visual Connection Status Indicator ─────────────────────
// Updates #global-status and #mode-text with state-aware classes + text.
// States map to CSS classes: connected / connecting / disconnected / error

const _STATE_TEXT = {
    [WsState.CONNECTING]:   'Connecting…',
    [WsState.CONNECTED]:    'Live',
    [WsState.DISCONNECTED]: 'Reconnecting…',
    [WsState.ERROR]:        'Error',
};

function _updateConnectionIndicator(state) {
    const dot  = document.getElementById('global-status');
    const text = document.getElementById('mode-text');

    if (dot) {
        // Remove all state classes then apply the current one.
        dot.classList.remove('offline', 'connecting', 'error');
        if (state === WsState.CONNECTED) {
            // Default class (green pulse) — no extra class needed.
        } else if (state === WsState.CONNECTING) {
            dot.classList.add('connecting');
        } else if (state === WsState.ERROR) {
            dot.classList.add('offline', 'error');
        } else {
            // disconnected
            dot.classList.add('offline');
        }
    }

    if (text) {
        text.textContent = _STATE_TEXT[state] || state;
    }
}

// ── Offline Message Queue ───────────────────────────────────
// Messages sent while disconnected are queued and flushed on reconnect.
const _offlineQueue = [];
const OFFLINE_QUEUE_MAX = 100;

/**
 * Send a message through the WebSocket.
 * If disconnected the payload is queued and sent when the connection is restored.
 * @param {object|string} payload
 */
function wsSend(payload) {
    const raw = typeof payload === 'string' ? payload : JSON.stringify(payload);
    if (ws && ws.conn && ws.conn.readyState === WebSocket.OPEN) {
        ws.conn.send(raw);
    } else {
        if (_offlineQueue.length < OFFLINE_QUEUE_MAX) {
            _offlineQueue.push(raw);
        } else {
            console.warn('[ws] offline queue full — dropping message');
        }
    }
}

function _flushOfflineQueue() {
    if (!ws || !ws.conn || ws.conn.readyState !== WebSocket.OPEN) return;
    while (_offlineQueue.length > 0) {
        const raw = _offlineQueue.shift();
        try { ws.conn.send(raw); } catch (e) { console.warn('[ws] flush error', e); }
    }
}

// ── Subscription Manager ────────────────────────────────────
// Tracks which wildcard topics are currently subscribed so we can
// efficiently re-subscribe after reconnect and support runtime
// subscribe/unsubscribe calls.

const _activeSubscriptions = new Set(WS_TOPICS);

/**
 * Subscribe to one or more topic patterns (e.g. 'agent.*', 'trade.fill').
 * Sends a subscribe message immediately if connected, else queues it.
 * @param {...string} topics
 */
function wsSubscribe(...topics) {
    const added = topics.filter(t => !_activeSubscriptions.has(t));
    if (added.length === 0) return;
    added.forEach(t => _activeSubscriptions.add(t));
    wsSend({ subscribe: added });
}

/**
 * Unsubscribe from one or more topic patterns.
 * @param {...string} topics
 */
function wsUnsubscribe(...topics) {
    const removed = topics.filter(t => _activeSubscriptions.has(t));
    if (removed.length === 0) return;
    removed.forEach(t => _activeSubscriptions.delete(t));
    wsSend({ unsubscribe: removed });
}

/** Re-send full subscription list — called after every (re)connect. */
function _resubscribeAll() {
    if (_activeSubscriptions.size === 0) return;
    wsSend({ subscribe: [..._activeSubscriptions] });
}

// ── Heartbeat ───────────────────────────────────────────────
// Sends a ping every 30s. If the server does not echo a pong within
// HEARTBEAT_TIMEOUT ms the connection is considered stale and is closed
// so the reconnect logic takes over.

const HEARTBEAT_INTERVAL  = 30_000;   // 30 s
const HEARTBEAT_TIMEOUT   = 10_000;   // 10 s pong window

let _hbInterval  = null;
let _hbTimeout   = null;
let _hbMissed    = 0;
const HEARTBEAT_MAX_MISSED = 2;

function _startHeartbeat() {
    _stopHeartbeat();
    _hbInterval = setInterval(_sendPing, HEARTBEAT_INTERVAL);
}

function _stopHeartbeat() {
    if (_hbInterval) { clearInterval(_hbInterval); _hbInterval = null; }
    if (_hbTimeout)  { clearTimeout(_hbTimeout);   _hbTimeout  = null; }
    _hbMissed = 0;
}

function _sendPing() {
    if (!ws || !ws.conn || ws.conn.readyState !== WebSocket.OPEN) return;
    ws.conn.send(JSON.stringify({ ping: true }));

    // Arm a timeout — if no pong arrives within HEARTBEAT_TIMEOUT
    // the connection is stale; force-close it so reconnect fires.
    _hbTimeout = setTimeout(() => {
        _hbMissed++;
        if (_hbMissed >= HEARTBEAT_MAX_MISSED) {
            console.warn('[ws] heartbeat timeout — forcing reconnect');
            _hbMissed = 0;
            try { ws.conn.close(); } catch (e) { /* ignore */ }
        }
    }, HEARTBEAT_TIMEOUT);
}

/** Call when a pong (or any server message) is received to cancel the timeout. */
function _resetHeartbeatTimeout() {
    if (_hbTimeout) { clearTimeout(_hbTimeout); _hbTimeout = null; }
    _hbMissed = 0;
}

// ── Event Deduplication ─────────────────────────────────────
// Skip identical messages that arrive within DEDUP_WINDOW_MS of each other.
// Key = topic + stable JSON of data payload.

const DEDUP_WINDOW_MS = 1000;   // 1 s
const _seenEvents = new Map();  // key -> timestamp

function _isDuplicate(topic, data) {
    let key;
    try {
        key = topic + '|' + JSON.stringify(data);
    } catch (e) {
        return false; // Can't serialize — pass through
    }
    const now = Date.now();
    const last = _seenEvents.get(key);
    if (last !== undefined && now - last < DEDUP_WINDOW_MS) return true;
    _seenEvents.set(key, now);
    // Prune old entries periodically to prevent unbounded growth
    if (_seenEvents.size > 500) {
        for (const [k, ts] of _seenEvents) {
            if (now - ts > DEDUP_WINDOW_MS * 2) _seenEvents.delete(k);
        }
    }
    return false;
}

// ── Subscribe to Extended Topics ────────────────────────────
function wsSubscribeExtended() {
    if (!ws || !ws.conn || ws.conn.readyState !== WebSocket.OPEN) return;
    ws.conn.send(JSON.stringify({ subscribe: WS_TOPICS }));
}

// ── Domain Event Handler ────────────────────────────────────
function handleWsEvent(topic, data) {
    // Deduplication guard
    if (_isDuplicate(topic, data)) return;

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

    // Visualize agent communication in Neural Galaxy — ALL events fire signals
    if (window.NeuralGalaxy && typeof NeuralGalaxy.fireSignal === 'function') {
        // Boost organic activity level when real events arrive
        if (typeof NeuralGalaxy._boostActivity === 'function') NeuralGalaxy._boostActivity();
        else if (window._neuralBoostActivity) window._neuralBoostActivity();

        // Fire signals for ALL topic types, not just agent-related
        const _galaxyTopics = new Set(['agent', 'collab', 'directive', 'system', 'skill', 'network', 'trade', 'prediction', 'experiment', 'memory', 'goal', 'approval', 'revenue', 'experience', 'cost', 'plugin', 'intelligence', 'swarm', 'research']);
        if (_galaxyTopics.has(prefix)) {
            // Extract agent IDs from the bus message fields + topic segments
            const payload = (data && data.payload) || data || {};
            const sender  = (data && data.sender) || null;
            const topicParts = topic.split('.');
            // fromAgent: sender field, or payload.from_agent / agent_id
            const fromAgent = sender
                || payload.from_agent || payload.agent_id || payload.source || null;
            // toAgent: payload.to_agent / target_agent / target, or agent id embedded in topic (e.g. "agent.<id>.task")
            const toAgent = payload.to_agent || payload.target_agent || payload.target
                || (prefix === 'agent' && topicParts.length >= 2 ? topicParts[1] : null)
                || null;

            // Color map for different event types
            const _signalColors = {
                intelligence: 0x00FFFF,  // cyan
                swarm: 0x4488FF,         // blue
                trade: 0x00FF88,         // green
                research: 0xFF88FF,      // pink
                directive: 0xFFAA00,     // orange
                agent: 0xFFD700,         // gold
                collab: 0xFF4488,        // magenta
            };
            const signalColor = _signalColors[prefix] || undefined;

            if (fromAgent && toAgent && fromAgent !== toAgent) {
                NeuralGalaxy.fireSignal(fromAgent, toAgent, signalColor);
            } else if (fromAgent) {
                // Single-agent event — pulse the node
                NeuralGalaxy.pulseAgent(fromAgent);
            } else if (toAgent) {
                NeuralGalaxy.pulseAgent(toAgent);
            }
        }
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

    const now = new Date();
    const timeStr = now.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'});

    const toast = document.createElement('div');
    toast.id = id;
    toast.className = `toast toast--${type}${pulseClass}`;
    toast.setAttribute('role', 'alert');
    toast.innerHTML = `
        <div style="display:flex;align-items:start;gap:8px;width:100%">
            <div style="flex:1">
                <span class="toast-message">${escHtml(message)}</span>
                <div style="font-size:10px;color:rgba(255,255,255,0.6);margin-top:2px">${timeStr}</div>
            </div>
            <button class="toast-dismiss" onclick="_dismissToast('${id}')" aria-label="Dismiss">&times;</button>
        </div>`;

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
// Patches ws.connect to:
//   1. Set state → connecting on entry
//   2. Set state → connected / error / disconnected on socket events
//   3. Start / stop heartbeat
//   4. Flush offline queue after (re)connect
//   5. Handle pong to reset heartbeat timeout
//   6. Re-subscribe all tracked topics after reconnect
(function _wireWsHandlers() {
    if (typeof ws === 'undefined' || !ws.on) {
        // Retry after root.js loads
        setTimeout(_wireWsHandlers, 200);
        return;
    }

    // Patch ws.connect — preserve original
    if (typeof ws.connect === 'function') {
        const _origConnect = ws.connect.bind(ws);

        ws.connect = function() {
            _setWsState(WsState.CONNECTING);
            _origConnect();

            // Attach enhanced hooks after the socket has been created
            if (ws.conn) {
                const _origOnOpen = ws.conn.onopen;
                ws.conn.onopen = function(evt) {
                    _setWsState(WsState.CONNECTED);
                    _startHeartbeat();
                    _resubscribeAll();
                    _flushOfflineQueue();
                    if (_origOnOpen) _origOnOpen.call(this, evt);
                };

                const _origOnMessage = ws.conn.onmessage;
                ws.conn.onmessage = function(evt) {
                    // Any message from the server resets the heartbeat timeout
                    _resetHeartbeatTimeout();
                    // Handle pong frames without passing them to the main dispatcher
                    try {
                        const parsed = JSON.parse(evt.data);
                        if (parsed && parsed.pong) return; // pong consumed
                    } catch (e) { /* not JSON — ignore */ }
                    if (_origOnMessage) _origOnMessage.call(this, evt);
                };

                const _origOnClose = ws.conn.onclose;
                ws.conn.onclose = function(evt) {
                    _stopHeartbeat();
                    _setWsState(WsState.DISCONNECTED);
                    if (_origOnClose) _origOnClose.call(this, evt);
                };

                const _origOnError = ws.conn.onerror;
                ws.conn.onerror = function(evt) {
                    _setWsState(WsState.ERROR);
                    if (_origOnError) _origOnError.call(this, evt);
                };
            }
        };
    }

    // Register handlers for all extended topic prefixes
    for (const prefix of Object.keys(TOPIC_PANEL_MAP)) {
        ws.on(`${prefix}.*`, (data, topic) => handleWsEvent(topic, data));
    }
})();

// ── CSS additions for new connection states ─────────────────
// Injected at runtime so no HTML/CSS files need touching.
(function _injectWsStatusStyles() {
    const STYLE_ID = 'ws-handlers-status-styles';
    if (document.getElementById(STYLE_ID)) return;

    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
        /* Connecting state — amber slow blink */
        .status-dot.connecting {
            background: var(--accent-gold, #f59e0b) !important;
            box-shadow: 0 0 4px var(--accent-gold, #f59e0b);
            animation: wsConnectingBlink 1s ease-in-out infinite !important;
        }
        .status-dot.connecting::after { display: none; }

        /* Error state — red, no pulse */
        .status-dot.error {
            background: var(--accent-red, #ef4444) !important;
            box-shadow: none !important;
            animation: none !important;
        }
        .status-dot.error::after { display: none; }

        @keyframes wsConnectingBlink {
            0%, 100% { opacity: 1; }
            50%       { opacity: 0.3; }
        }
    `;
    document.head.appendChild(style);
})();
