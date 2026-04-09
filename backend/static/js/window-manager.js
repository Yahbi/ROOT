/**
 * WindowManager — Linux desktop-style window management for ROOT
 *
 * Usage: add one <script src="/static/js/window-manager.js"></script>
 * after the existing scripts. The global WindowManager object is exposed
 * automatically and the existing showPanel() function is overridden.
 */
(function (global) {
  'use strict';

  /* ─── constants ─────────────────────────────────────────────── */
  const TASKBAR_HEIGHT   = 48;   // px — must match #desktop-taskbar height
  const MIN_WIDTH        = 400;  // px
  const MIN_HEIGHT       = 300;  // px
  const CASCADE_OFFSET   = 30;   // px offset per successive window
  const ANIM_OPEN_MS     = 150;
  const ANIM_CLOSE_MS    = 100;
  const ANIM_RESIZE_MS   = 200;
  const LS_KEY           = 'wm_window_state';

  /* ─── accent colour (read from CSS or fall back) ─────────────── */
  function accentColor() {
    const v = getComputedStyle(document.documentElement)
                .getPropertyValue('--accent').trim();
    return v || '#7c3aed';
  }

  /* ─── panel metadata ─────────────────────────────────────────── */
  const PANEL_META = {
    'panel-chat':        { title: 'Terminal / Chat',     icon: '💬' },
    'panel-dashboard':   { title: 'System Monitor',      icon: '📊' },
    'panel-agents':      { title: 'Agents',              icon: '🤖' },
    'panel-memory':      { title: 'Memory',              icon: '🧠' },
    'panel-trading':     { title: 'Trading',             icon: '📈' },
    'panel-autonomy':    { title: 'Autonomy',            icon: '⚡' },
    'panel-intelligence':{ title: 'Intelligence',        icon: '🔍' },
    'panel-system':      { title: 'System',              icon: '⚙️'  },
    'panel-miro':        { title: 'MiRo',                icon: '🌀' },
  };

  function getPanelMeta(panelId) {
    return PANEL_META[panelId] || {
      title: panelId.replace(/^panel-/, '').replace(/-/g, ' ')
               .replace(/\b\w/g, c => c.toUpperCase()),
      icon: '🪟'
    };
  }

  /* ══════════════════════════════════════════════════════════════
   *  WindowManager class
   * ══════════════════════════════════════════════════════════════ */
  class WindowManager {
    constructor() {
      /** @type {Map<string, WindowState>} panelId → state */
      this._windows   = new Map();
      this._zTop      = 100;
      this._cascade   = 0;
      this._desktop   = null;
      this._taskbar   = null;
      this._ctxMenu   = null;
      this._savedState = this._loadState();

      /* bind once so we can remove listeners later */
      this._onMouseMove  = this._onMouseMove.bind(this);
      this._onMouseUp    = this._onMouseUp.bind(this);
      this._dragState    = null;   // active drag info
      this._resizeState  = null;   // active resize info

      this._init();
    }

    /* ─── initialisation ─────────────────────────────────────── */
    _init() {
      document.addEventListener('DOMContentLoaded', () => this._setup());
      if (document.readyState !== 'loading') this._setup();
    }

    _setup() {
      if (this._desktop) return; // already set up

      // Only activate window manager when Linux theme is active
      const theme = document.documentElement.getAttribute('data-theme');
      if (theme !== 'linux') {
        // Hide desktop infrastructure if it exists but theme is not linux
        const da = document.getElementById('desktop-area');
        const tb = document.getElementById('desktop-taskbar');
        if (da) da.style.display = 'none';
        if (tb) tb.style.display = 'none';
        return;
      }

      this._desktop = document.getElementById('desktop-area');
      this._taskbar = document.getElementById('desktop-taskbar');

      if (!this._desktop) {
        /* Create desktop area if it does not already exist */
        this._desktop = document.createElement('div');
        this._desktop.id = 'desktop-area';
        Object.assign(this._desktop.style, {
          position: 'fixed', top: '0', left: '0',
          right: '0', bottom: TASKBAR_HEIGHT + 'px',
          overflow: 'hidden', zIndex: '1'
        });
        document.body.appendChild(this._desktop);
      }

      if (!this._taskbar) {
        this._taskbar = document.createElement('div');
        this._taskbar.id = 'desktop-taskbar';
        Object.assign(this._taskbar.style, {
          position: 'fixed', bottom: '0', left: '0', right: '0',
          height: TASKBAR_HEIGHT + 'px',
          background: 'var(--bg-secondary, #1e1e2e)',
          borderTop: '1px solid var(--border, #333)',
          display: 'flex', alignItems: 'center', gap: '4px',
          padding: '0 8px', zIndex: '9999', overflowX: 'auto'
        });
        document.body.appendChild(this._taskbar);
      }

      this._injectStyles();
      this._buildContextMenu();
      this._hookDesktopRightClick();
      this._hookNavItems();
      this._overrideShowPanel();

      /* mouse events for drag / resize */
      document.addEventListener('mousemove', this._onMouseMove);
      document.addEventListener('mouseup',   this._onMouseUp);

      /* Auto-open chat panel maximised */
      setTimeout(() => {
        this.open('panel-chat', true);
      }, 0);
    }

    /* ─── CSS injection ─────────────────────────────────────── */
    _injectStyles() {
      if (document.getElementById('wm-styles')) return;
      const style = document.createElement('style');
      style.id = 'wm-styles';
      style.textContent = `
        .wm-window {
          position: absolute;
          display: flex;
          flex-direction: column;
          background: var(--bg-primary, #13131a);
          border: 1px solid var(--border, #333);
          border-radius: 8px;
          box-shadow: 0 8px 32px rgba(0,0,0,0.6);
          overflow: hidden;
          min-width: ${MIN_WIDTH}px;
          min-height: ${MIN_HEIGHT}px;
          transition: none;
          will-change: transform, opacity;
          box-sizing: border-box;
        }
        .wm-window.wm-animating {
          transition:
            transform ${ANIM_RESIZE_MS}ms ease,
            width ${ANIM_RESIZE_MS}ms ease,
            height ${ANIM_RESIZE_MS}ms ease,
            top ${ANIM_RESIZE_MS}ms ease,
            left ${ANIM_RESIZE_MS}ms ease,
            opacity ${ANIM_OPEN_MS}ms ease;
        }
        .wm-window.wm-opening {
          animation: wmOpen ${ANIM_OPEN_MS}ms ease forwards;
        }
        .wm-window.wm-closing {
          animation: wmClose ${ANIM_CLOSE_MS}ms ease forwards;
        }
        @keyframes wmOpen {
          from { opacity: 0; transform: scale(0.9); }
          to   { opacity: 1; transform: scale(1); }
        }
        @keyframes wmClose {
          from { opacity: 1; transform: scale(1); }
          to   { opacity: 0; transform: scale(0.9); }
        }
        @keyframes wmMinimize {
          from { opacity: 1; transform: scale(1); }
          to   { opacity: 0; transform: scale(0.5) translateY(200px); }
        }

        .wm-titlebar {
          display: flex;
          align-items: center;
          height: 36px;
          min-height: 36px;
          padding: 0 10px;
          background: var(--bg-secondary, #1e1e2e);
          border-bottom: 1px solid var(--border, #333);
          user-select: none;
          cursor: grab;
          flex-shrink: 0;
        }
        .wm-titlebar:active { cursor: grabbing; }

        .wm-dot {
          width: 12px; height: 12px;
          border-radius: 50%;
          margin-right: 8px;
          flex-shrink: 0;
        }

        .wm-title {
          flex: 1;
          font-size: 13px;
          font-weight: 600;
          color: var(--text-primary, #e2e8f0);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          pointer-events: none;
        }

        .wm-btn-group {
          display: flex;
          gap: 4px;
          margin-left: 8px;
          flex-shrink: 0;
        }

        .wm-btn {
          width: 22px; height: 22px;
          border-radius: 4px;
          border: none;
          cursor: pointer;
          font-size: 12px;
          line-height: 22px;
          text-align: center;
          background: transparent;
          color: var(--text-secondary, #94a3b8);
          transition: background 0.15s, color 0.15s;
          padding: 0;
        }
        .wm-btn:hover { background: var(--bg-tertiary, #2a2a3e); color: #fff; }
        .wm-btn.wm-btn-close:hover { background: #e53e3e; color: #fff; }
        .wm-btn.wm-btn-min:hover   { background: #d69e2e; color: #fff; }
        .wm-btn.wm-btn-max:hover   { background: #38a169; color: #fff; }

        .wm-body {
          flex: 1;
          overflow: auto;
          position: relative;
        }
        .wm-body > * { height: 100%; }

        .wm-resize-handle {
          position: absolute;
          background: transparent;
        }
        .wm-resize-e  { right: 0; top: 4px; bottom: 4px; width: 6px; cursor: e-resize; }
        .wm-resize-s  { bottom: 0; left: 4px; right: 4px; height: 6px; cursor: s-resize; }
        .wm-resize-se { right: 0; bottom: 0; width: 12px; height: 12px; cursor: se-resize; }
        .wm-resize-w  { left: 0; top: 4px; bottom: 4px; width: 6px; cursor: w-resize; }
        .wm-resize-n  { top: 0; left: 4px; right: 4px; height: 6px; cursor: n-resize; }
        .wm-resize-sw { left: 0; bottom: 0; width: 12px; height: 12px; cursor: sw-resize; }
        .wm-resize-ne { right: 0; top: 0; width: 12px; height: 12px; cursor: ne-resize; }
        .wm-resize-nw { left: 0; top: 0; width: 12px; height: 12px; cursor: nw-resize; }

        /* taskbar buttons */
        .wm-tb-btn {
          display: flex;
          align-items: center;
          gap: 6px;
          height: 34px;
          padding: 0 10px;
          border-radius: 6px;
          border: 1px solid transparent;
          background: transparent;
          color: var(--text-secondary, #94a3b8);
          font-size: 12px;
          cursor: pointer;
          white-space: nowrap;
          transition: background 0.15s, color 0.15s, border-color 0.15s;
          max-width: 160px;
          overflow: hidden;
          text-overflow: ellipsis;
          flex-shrink: 0;
        }
        .wm-tb-btn:hover {
          background: var(--bg-tertiary, #2a2a3e);
          color: #fff;
        }
        .wm-tb-btn.wm-tb-active {
          border-color: var(--accent, #7c3aed);
          color: #fff;
          background: var(--bg-tertiary, #2a2a3e);
        }
        .wm-tb-btn.wm-tb-minimized {
          opacity: 0.6;
          font-style: italic;
        }

        /* desktop context menu */
        .wm-ctx-menu {
          position: fixed;
          background: var(--bg-secondary, #1e1e2e);
          border: 1px solid var(--border, #333);
          border-radius: 8px;
          padding: 4px 0;
          z-index: 99999;
          min-width: 180px;
          box-shadow: 0 8px 24px rgba(0,0,0,0.5);
          display: none;
        }
        .wm-ctx-menu.visible { display: block; }
        .wm-ctx-item {
          padding: 7px 14px;
          font-size: 13px;
          color: var(--text-primary, #e2e8f0);
          cursor: pointer;
          display: flex;
          align-items: center;
          gap: 8px;
          transition: background 0.1s;
        }
        .wm-ctx-item:hover { background: var(--bg-tertiary, #2a2a3e); }
        .wm-ctx-sep {
          height: 1px;
          background: var(--border, #333);
          margin: 4px 0;
        }
      `;
      document.head.appendChild(style);
    }

    /* ─── context menu ──────────────────────────────────────── */
    _buildContextMenu() {
      const menu = document.createElement('div');
      menu.className = 'wm-ctx-menu';
      menu.id = 'wm-ctx-menu';
      menu.innerHTML = `
        <div class="wm-ctx-item" data-action="tile">🔲 Tile Windows</div>
        <div class="wm-ctx-item" data-action="cascade">🪟 Cascade Windows</div>
        <div class="wm-ctx-item" data-action="show-desktop">🖥️ Show Desktop</div>
        <div class="wm-ctx-sep"></div>
        <div class="wm-ctx-item" data-action="open-chat">💬 Terminal</div>
        <div class="wm-ctx-item" data-action="open-dashboard">📊 System Monitor</div>
      `;
      document.body.appendChild(menu);
      this._ctxMenu = menu;

      menu.addEventListener('click', (e) => {
        const item = e.target.closest('[data-action]');
        if (!item) return;
        const action = item.dataset.action;
        this._hideContextMenu();
        switch (action) {
          case 'tile':         this.tileWindows();           break;
          case 'cascade':      this.cascadeWindows();        break;
          case 'show-desktop': this._minimizeAll();          break;
          case 'open-chat':    this.open('panel-chat');      break;
          case 'open-dashboard': this.open('panel-dashboard'); break;
        }
      });
    }

    _hookDesktopRightClick() {
      document.addEventListener('contextmenu', (e) => {
        /* only fire on the desktop background, not on windows */
        if (e.target.closest('.wm-window')) return;
        e.preventDefault();
        this._showContextMenu(e.clientX, e.clientY);
      });
      document.addEventListener('click', () => this._hideContextMenu());
    }

    _showContextMenu(x, y) {
      const menu = this._ctxMenu;
      menu.classList.add('visible');
      /* keep within viewport */
      const mw = 190, mh = 200;
      menu.style.left = Math.min(x, window.innerWidth  - mw) + 'px';
      menu.style.top  = Math.min(y, window.innerHeight - mh) + 'px';
    }

    _hideContextMenu() {
      this._ctxMenu && this._ctxMenu.classList.remove('visible');
    }

    /* ─── nav hook ───────────────────────────────────────────── */
    _hookNavItems() {
      document.querySelectorAll('[data-panel]').forEach(el => {
        el.addEventListener('click', (e) => {
          e.preventDefault();
          e.stopPropagation();
          const panelId = el.dataset.panel;
          if (panelId) this.open(panelId);
        });
      });

      /* Also observe future nav items (dynamic DOM) */
      const obs = new MutationObserver(() => {
        document.querySelectorAll('[data-panel]:not([data-wm-hooked])').forEach(el => {
          el.dataset.wmHooked = '1';
          el.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            const panelId = el.dataset.panel;
            if (panelId) this.open(panelId);
          });
        });
      });
      obs.observe(document.body, { childList: true, subtree: true });
    }

    _overrideShowPanel() {
      global.showPanel = (panelId) => this.open(panelId);
    }

    /* ══════════════════════════════════════════════════════════════
     *  Public API
     * ══════════════════════════════════════════════════════════════ */

    /**
     * Open (or restore) a panel as a window.
     * @param {string} panelId
     * @param {boolean} [maximized=false]
     */
    open(panelId, maximized = false) {
      if (this._windows.has(panelId)) {
        const state = this._windows.get(panelId);
        if (state.minimized) {
          this._doRestore(panelId);
        } else {
          this.bringToFront(panelId);
        }
        return;
      }

      const panel = document.getElementById(panelId);
      if (!panel) {
        console.warn(`[WindowManager] Panel not found: ${panelId}`);
        return;
      }

      const meta    = getPanelMeta(panelId);
      const saved   = this._savedState[panelId];
      const desktop = this._desktop;
      const dw      = desktop.clientWidth  || window.innerWidth;
      const dh      = desktop.clientHeight || (window.innerHeight - TASKBAR_HEIGHT);

      /* default size */
      const defaultW = Math.max(MIN_WIDTH,  Math.round(dw * 0.65));
      const defaultH = Math.max(MIN_HEIGHT, Math.round(dh * 0.75));

      /* cascade offset */
      const off = (this._cascade % 8) * CASCADE_OFFSET;
      this._cascade++;

      const initX = saved ? saved.x : off + 40;
      const initY = saved ? saved.y : off + 30;
      const initW = saved ? saved.w : defaultW;
      const initH = saved ? saved.h : defaultH;

      /* build window DOM */
      const win = document.createElement('div');
      win.className  = 'wm-window wm-opening';
      win.dataset.wmId = panelId;
      win.style.cssText = `
        left: ${initX}px;
        top:  ${initY}px;
        width:  ${initW}px;
        height: ${initH}px;
        z-index: ${++this._zTop};
      `;

      /* title bar */
      const titlebar = document.createElement('div');
      titlebar.className = 'wm-titlebar';
      titlebar.innerHTML = `
        <span class="wm-dot" style="background:${accentColor()}"></span>
        <span class="wm-title">${meta.icon} ${meta.title}</span>
        <div class="wm-btn-group">
          <button class="wm-btn wm-btn-min"  title="Minimize">&#8212;</button>
          <button class="wm-btn wm-btn-max"  title="Maximize">&#9633;</button>
          <button class="wm-btn wm-btn-close" title="Close">&#215;</button>
        </div>
      `;

      /* body */
      const body = document.createElement('div');
      body.className = 'wm-body';

      /* move panel content in */
      panel.style.display = 'flex';
      panel.style.height  = '100%';
      body.appendChild(panel);

      /* resize handles */
      const handles = ['e','s','se','w','n','sw','ne','nw'];
      const handlesHtml = handles.map(d =>
        `<div class="wm-resize-handle wm-resize-${d}" data-dir="${d}"></div>`
      ).join('');

      win.appendChild(titlebar);
      win.appendChild(body);
      win.insertAdjacentHTML('beforeend', handlesHtml);
      desktop.appendChild(win);

      /* state record */
      const state = {
        panelId, win, titlebar, body,
        x: initX, y: initY, w: initW, h: initH,
        maximized: false, minimized: false,
        preMaxX: initX, preMaxY: initY, preMaxW: initW, preMaxH: initH,
        tbBtn: null
      };
      this._windows.set(panelId, state);

      /* taskbar button */
      this._addTaskbarButton(panelId, meta);

      /* events */
      win.addEventListener('mousedown', () => this.bringToFront(panelId));

      titlebar.addEventListener('mousedown', (e) => {
        if (e.target.closest('.wm-btn')) return;
        this._startDrag(e, panelId);
      });

      titlebar.addEventListener('dblclick', (e) => {
        if (e.target.closest('.wm-btn')) return;
        this.maximize(panelId);
      });

      titlebar.querySelector('.wm-btn-min').addEventListener('click', () => this.minimize(panelId));
      titlebar.querySelector('.wm-btn-max').addEventListener('click', () => this.maximize(panelId));
      titlebar.querySelector('.wm-btn-close').addEventListener('click', () => this.close(panelId));

      win.querySelectorAll('.wm-resize-handle').forEach(h => {
        h.addEventListener('mousedown', (e) => {
          e.stopPropagation();
          this._startResize(e, panelId, h.dataset.dir);
        });
      });

      /* remove opening class after animation */
      win.addEventListener('animationend', () => {
        win.classList.remove('wm-opening');
      }, { once: true });

      if (maximized) {
        /* slight delay so the open animation fires first */
        setTimeout(() => this.maximize(panelId), ANIM_OPEN_MS + 20);
      }

      this._updateTaskbarActive(panelId);
      this._saveState();
    }

    /** Close a window (hide panel, remove taskbar button). */
    close(panelId) {
      const state = this._windows.get(panelId);
      if (!state) return;

      const { win, tbBtn } = state;
      win.classList.add('wm-closing');

      win.addEventListener('animationend', () => {
        /* put the panel back into original DOM position */
        const panel = document.getElementById(panelId);
        if (panel) {
          panel.style.display = 'none';
          document.body.appendChild(panel);
        }
        win.remove();
        if (tbBtn) tbBtn.remove();
        this._windows.delete(panelId);
        this._saveState();
        this._updateTaskbarActive(null);
      }, { once: true });
    }

    /** Minimize a window — hide it, keep taskbar button. */
    minimize(panelId) {
      const state = this._windows.get(panelId);
      if (!state || state.minimized) return;

      const { win, tbBtn } = state;
      state.minimized = true;

      win.style.animation = `wmMinimize ${ANIM_OPEN_MS}ms ease forwards`;
      setTimeout(() => {
        win.style.display = 'none';
        win.style.animation = '';
      }, ANIM_OPEN_MS);

      tbBtn && tbBtn.classList.add('wm-tb-minimized');
      tbBtn && tbBtn.classList.remove('wm-tb-active');
      this._saveState();
    }

    /** Toggle maximize / restore a window. */
    maximize(panelId) {
      const state = this._windows.get(panelId);
      if (!state) return;

      if (state.maximized) {
        this._doRestore(panelId);
      } else {
        this._doMaximize(panelId);
      }
    }

    _doMaximize(panelId) {
      const state = this._windows.get(panelId);
      if (!state || state.maximized) return;

      const { win } = state;
      const dw = this._desktop.clientWidth  || window.innerWidth;
      const dh = this._desktop.clientHeight || (window.innerHeight - TASKBAR_HEIGHT);

      /* save pre-max geometry */
      state.preMaxX = state.x;
      state.preMaxY = state.y;
      state.preMaxW = state.w;
      state.preMaxH = state.h;
      state.maximized = true;

      win.classList.add('wm-animating');
      win.style.left   = '0px';
      win.style.top    = '0px';
      win.style.width  = dw + 'px';
      win.style.height = dh + 'px';

      setTimeout(() => win.classList.remove('wm-animating'), ANIM_RESIZE_MS + 10);

      state.x = 0; state.y = 0; state.w = dw; state.h = dh;
      this.bringToFront(panelId);
      this._saveState();
    }

    _doRestore(panelId) {
      const state = this._windows.get(panelId);
      if (!state) return;

      const { win } = state;

      if (state.minimized) {
        win.style.display = '';
        state.minimized   = false;
        win.classList.add('wm-opening');
        win.addEventListener('animationend', () => win.classList.remove('wm-opening'), { once: true });
        state.tbBtn && state.tbBtn.classList.remove('wm-tb-minimized');
        this.bringToFront(panelId);
        this._saveState();
        return;
      }

      if (state.maximized) {
        state.maximized = false;
        win.classList.add('wm-animating');
        win.style.left   = state.preMaxX + 'px';
        win.style.top    = state.preMaxY + 'px';
        win.style.width  = state.preMaxW + 'px';
        win.style.height = state.preMaxH + 'px';
        state.x = state.preMaxX;
        state.y = state.preMaxY;
        state.w = state.preMaxW;
        state.h = state.preMaxH;
        setTimeout(() => win.classList.remove('wm-animating'), ANIM_RESIZE_MS + 10);
        this._saveState();
      }
    }

    /** Bring a window to the front (highest z-index). */
    bringToFront(panelId) {
      const state = this._windows.get(panelId);
      if (!state) return;
      state.win.style.zIndex = ++this._zTop;
      this._updateTaskbarActive(panelId);
    }

    /** Tile all open (non-minimized) windows in a grid. */
    tileWindows() {
      const open = [...this._windows.values()].filter(s => !s.minimized);
      if (!open.length) return;

      const dw = this._desktop.clientWidth  || window.innerWidth;
      const dh = this._desktop.clientHeight || (window.innerHeight - TASKBAR_HEIGHT);
      const cols = Math.ceil(Math.sqrt(open.length));
      const rows = Math.ceil(open.length / cols);
      const w    = Math.floor(dw / cols);
      const h    = Math.floor(dh / rows);

      open.forEach((state, i) => {
        const col = i % cols;
        const row = Math.floor(i / cols);
        const x   = col * w;
        const y   = row * h;

        state.maximized = false;
        state.x = x; state.y = y;
        state.w = w; state.h = h;

        state.win.classList.add('wm-animating');
        Object.assign(state.win.style, {
          left: x + 'px', top: y + 'px',
          width: w + 'px', height: h + 'px'
        });
        setTimeout(() => state.win.classList.remove('wm-animating'), ANIM_RESIZE_MS + 10);
      });
      this._saveState();
    }

    /** Cascade all open (non-minimized) windows. */
    cascadeWindows() {
      const open = [...this._windows.values()].filter(s => !s.minimized);
      if (!open.length) return;

      const dw = this._desktop.clientWidth  || window.innerWidth;
      const dh = this._desktop.clientHeight || (window.innerHeight - TASKBAR_HEIGHT);
      const w  = Math.round(dw * 0.6);
      const h  = Math.round(dh * 0.7);

      open.forEach((state, i) => {
        const off = i * CASCADE_OFFSET;
        const x = 40 + off;
        const y = 30 + off;

        state.maximized = false;
        state.x = x; state.y = y;
        state.w = w; state.h = h;

        state.win.classList.add('wm-animating');
        Object.assign(state.win.style, {
          left: x + 'px', top: y + 'px',
          width: w + 'px', height: h + 'px'
        });
        state.win.style.zIndex = 100 + i;
        setTimeout(() => state.win.classList.remove('wm-animating'), ANIM_RESIZE_MS + 10);
      });
      this._saveState();
    }

    /* ─── taskbar helpers ────────────────────────────────────── */
    _addTaskbarButton(panelId, meta) {
      const btn = document.createElement('button');
      btn.className = 'wm-tb-btn';
      btn.dataset.wmTbId = panelId;
      btn.textContent    = `${meta.icon} ${meta.title}`;
      btn.title          = meta.title;

      btn.addEventListener('click', () => {
        const state = this._windows.get(panelId);
        if (!state) return;
        if (state.minimized) {
          this._doRestore(panelId);
        } else {
          const isActive = parseInt(state.win.style.zIndex) === this._zTop;
          isActive ? this.minimize(panelId) : this.bringToFront(panelId);
        }
      });

      this._taskbar.appendChild(btn);
      this._windows.get(panelId).tbBtn = btn;
    }

    _updateTaskbarActive(activePanelId) {
      this._windows.forEach((state, pid) => {
        if (!state.tbBtn) return;
        state.tbBtn.classList.toggle('wm-tb-active', pid === activePanelId);
      });
    }

    /* ─── minimize all ───────────────────────────────────────── */
    _minimizeAll() {
      this._windows.forEach((_, pid) => this.minimize(pid));
    }

    /* ─── drag ───────────────────────────────────────────────── */
    _startDrag(e, panelId) {
      e.preventDefault();
      const state = this._windows.get(panelId);
      if (!state || state.maximized) return;

      this.bringToFront(panelId);
      this._dragState = {
        panelId,
        startX: e.clientX,
        startY: e.clientY,
        origX:  state.x,
        origY:  state.y
      };
    }

    /* ─── resize ─────────────────────────────────────────────── */
    _startResize(e, panelId, dir) {
      e.preventDefault();
      const state = this._windows.get(panelId);
      if (!state || state.maximized) return;

      this.bringToFront(panelId);
      this._resizeState = {
        panelId, dir,
        startX: e.clientX,
        startY: e.clientY,
        origX:  state.x,
        origY:  state.y,
        origW:  state.w,
        origH:  state.h
      };
    }

    /* ─── mouse events ───────────────────────────────────────── */
    _onMouseMove(e) {
      if (this._dragState) {
        this._handleDrag(e);
      } else if (this._resizeState) {
        this._handleResize(e);
      }
    }

    _handleDrag(e) {
      const d     = this._dragState;
      const state = this._windows.get(d.panelId);
      if (!state) return;

      const dx = e.clientX - d.startX;
      const dy = e.clientY - d.startY;
      const dw = this._desktop.clientWidth  || window.innerWidth;
      const dh = this._desktop.clientHeight || (window.innerHeight - TASKBAR_HEIGHT);

      let nx = d.origX + dx;
      let ny = d.origY + dy;

      /* constrain so at least the title bar stays visible */
      nx = Math.max(-state.w + 80, Math.min(dw - 80, nx));
      ny = Math.max(0, Math.min(dh - 36, ny));

      state.x = nx;
      state.y = ny;
      state.win.style.left = nx + 'px';
      state.win.style.top  = ny + 'px';
    }

    _handleResize(e) {
      const r     = this._resizeState;
      const state = this._windows.get(r.panelId);
      if (!state) return;

      const dx  = e.clientX - r.startX;
      const dy  = e.clientY - r.startY;
      let   nx  = r.origX, ny = r.origY;
      let   nw  = r.origW, nh = r.origH;

      if (r.dir.includes('e'))  { nw = Math.max(MIN_WIDTH,  r.origW + dx); }
      if (r.dir.includes('s'))  { nh = Math.max(MIN_HEIGHT, r.origH + dy); }
      if (r.dir.includes('w'))  {
        const possible = Math.min(r.origW - MIN_WIDTH, dx);
        nx = r.origX + possible;
        nw = r.origW - possible;
      }
      if (r.dir.includes('n'))  {
        const possible = Math.min(r.origH - MIN_HEIGHT, dy);
        ny = r.origY + possible;
        nh = r.origH - possible;
      }

      state.x = nx; state.y = ny; state.w = nw; state.h = nh;
      Object.assign(state.win.style, {
        left: nx + 'px', top: ny + 'px',
        width: nw + 'px', height: nh + 'px'
      });
    }

    _onMouseUp() {
      if (this._dragState || this._resizeState) {
        this._saveState();
      }
      this._dragState   = null;
      this._resizeState = null;
    }

    /* ─── localStorage persistence ───────────────────────────── */
    _loadState() {
      try {
        return JSON.parse(localStorage.getItem(LS_KEY) || '{}');
      } catch {
        return {};
      }
    }

    _saveState() {
      const out = {};
      this._windows.forEach((state, pid) => {
        out[pid] = { x: state.x, y: state.y, w: state.w, h: state.h };
      });
      try {
        localStorage.setItem(LS_KEY, JSON.stringify(out));
      } catch { /* storage full — ignore */ }
      this._savedState = out;
    }
  }

  /* ─── singleton + global export ─────────────────────────────── */
  const wm = new WindowManager();
  global.WindowManager = wm;

})(window);
