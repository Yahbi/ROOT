/* ROOT — Generic Modal Manager
   Renders forms, confirmations, and detail views into #root-modal.
   All user-supplied text is escaped via escHtml() (defined in root.js). */

// ── Form Modal ──────────────────────────────────────────────
function showModal({ title, fields, onSubmit, submitLabel = 'Save' }) {
    const container = document.getElementById('root-modal');
    if (!container) return;

    const fieldRows = fields.map(f => _renderField(f)).join('');

    container.innerHTML = `
        <div class="modal-overlay" onclick="closeModal()">
            <div class="modal-card" onclick="event.stopPropagation()">
                <div class="modal-header">
                    <h3 class="modal-title">${escHtml(title)}</h3>
                    <button class="modal-close" onclick="closeModal()" aria-label="Close">&times;</button>
                </div>
                <div class="modal-body">
                    <form id="modal-form" class="modal-form" onsubmit="return false">
                        ${fieldRows}
                    </form>
                </div>
                <div class="modal-footer">
                    <button class="btn-secondary" onclick="closeModal()">Cancel</button>
                    <button class="btn-primary" id="modal-submit-btn">${escHtml(submitLabel)}</button>
                </div>
            </div>
        </div>`;

    container.style.display = 'block';

    const submitBtn = document.getElementById('modal-submit-btn');
    submitBtn.addEventListener('click', () => {
        const values = _collectFormValues(fields);
        if (!values) return; // validation failed
        if (typeof onSubmit === 'function') onSubmit(values);
    });

    // Focus first non-readonly input
    const firstInput = container.querySelector('input:not([readonly]), textarea:not([readonly]), select');
    if (firstInput) setTimeout(() => firstInput.focus(), 60);

    // Escape key closes modal
    container._escHandler = (e) => { if (e.key === 'Escape') closeModal(); };
    document.addEventListener('keydown', container._escHandler);
}

// ── Confirm Modal ───────────────────────────────────────────
function showConfirmModal({ title, message, danger = false, onConfirm, confirmLabel = 'Confirm' }) {
    const container = document.getElementById('root-modal');
    if (!container) return;

    const btnClass = danger ? 'btn-danger' : 'btn-primary';

    container.innerHTML = `
        <div class="modal-overlay" onclick="closeModal()">
            <div class="modal-card modal-card--sm" onclick="event.stopPropagation()">
                <div class="modal-header">
                    <h3 class="modal-title">${escHtml(title)}</h3>
                    <button class="modal-close" onclick="closeModal()" aria-label="Close">&times;</button>
                </div>
                <div class="modal-body">
                    <p class="modal-message">${escHtml(message)}</p>
                </div>
                <div class="modal-footer">
                    <button class="btn-secondary" onclick="closeModal()">Cancel</button>
                    <button class="${btnClass}" id="modal-confirm-btn">${escHtml(confirmLabel)}</button>
                </div>
            </div>
        </div>`;

    container.style.display = 'block';

    document.getElementById('modal-confirm-btn').addEventListener('click', () => {
        if (typeof onConfirm === 'function') onConfirm();
    });

    container._escHandler = (e) => { if (e.key === 'Escape') closeModal(); };
    document.addEventListener('keydown', container._escHandler);
}

// ── Detail Modal ────────────────────────────────────────────
function showDetailModal({ title, content }) {
    const container = document.getElementById('root-modal');
    if (!container) return;

    container.innerHTML = `
        <div class="modal-overlay" onclick="closeModal()">
            <div class="modal-card" onclick="event.stopPropagation()">
                <div class="modal-header">
                    <h3 class="modal-title">${escHtml(title)}</h3>
                    <button class="modal-close" onclick="closeModal()" aria-label="Close">&times;</button>
                </div>
                <div class="modal-body modal-body--detail">
                    ${content}
                </div>
                <div class="modal-footer">
                    <button class="btn-secondary" onclick="closeModal()">Close</button>
                </div>
            </div>
        </div>`;

    container.style.display = 'block';

    container._escHandler = (e) => { if (e.key === 'Escape') closeModal(); };
    document.addEventListener('keydown', container._escHandler);
}

// ── Close ───────────────────────────────────────────────────
function closeModal() {
    const container = document.getElementById('root-modal');
    if (!container) return;
    if (container._escHandler) {
        document.removeEventListener('keydown', container._escHandler);
        container._escHandler = null;
    }
    container.style.display = 'none';
    container.innerHTML = '';
}

// ── Field Renderer (private) ────────────────────────────────
function _renderField(f) {
    const id = `modal-field-${f.key}`;
    const req = f.required ? ' required' : '';
    const ph = f.placeholder ? ` placeholder="${escHtml(f.placeholder)}"` : '';
    const val = f.value != null ? f.value : '';
    const label = `<label class="modal-label" for="${id}">${escHtml(f.label)}</label>`;

    switch (f.type) {
        case 'textarea':
            return `<div class="modal-field">${label}
                <textarea id="${id}" class="modal-input modal-textarea" data-key="${f.key}"${ph}${req}>${escHtml(String(val))}</textarea>
            </div>`;

        case 'number':
            return `<div class="modal-field">${label}
                <input id="${id}" class="modal-input" type="number" data-key="${f.key}" value="${escHtml(String(val))}"
                    ${f.min != null ? ` min="${f.min}"` : ''}${f.max != null ? ` max="${f.max}"` : ''}
                    ${f.step != null ? ` step="${f.step}"` : ''}${ph}${req}>
            </div>`;

        case 'select': {
            const opts = (f.options || []).map(o => {
                const optVal = typeof o === 'object' ? o.value : o;
                const optLabel = typeof o === 'object' ? o.label : o;
                const sel = String(optVal) === String(val) ? ' selected' : '';
                return `<option value="${escHtml(String(optVal))}"${sel}>${escHtml(String(optLabel))}</option>`;
            }).join('');
            return `<div class="modal-field">${label}
                <select id="${id}" class="modal-input modal-select" data-key="${f.key}"${req}>${opts}</select>
            </div>`;
        }

        case 'range':
            return `<div class="modal-field">${label}
                <div class="modal-range-wrap">
                    <input id="${id}" class="modal-range" type="range" data-key="${f.key}"
                        value="${escHtml(String(val))}"
                        ${f.min != null ? ` min="${f.min}"` : ' min="0"'}
                        ${f.max != null ? ` max="${f.max}"` : ' max="100"'}
                        ${f.step != null ? ` step="${f.step}"` : ''}
                        oninput="document.getElementById('${id}-val').textContent=this.value">
                    <span id="${id}-val" class="modal-range-val">${escHtml(String(val))}</span>
                </div>
            </div>`;

        case 'date':
            return `<div class="modal-field">${label}
                <input id="${id}" class="modal-input" type="date" data-key="${f.key}" value="${escHtml(String(val))}"${req}>
            </div>`;

        case 'tags':
            return `<div class="modal-field">${label}
                <input id="${id}" class="modal-input" type="text" data-key="${f.key}" data-type="tags"
                    value="${escHtml(Array.isArray(val) ? val.join(', ') : String(val))}"${ph}${req}>
                <span class="modal-hint">Comma-separated values</span>
            </div>`;

        case 'readonly':
            return `<div class="modal-field">${label}
                <input id="${id}" class="modal-input modal-readonly" type="text" data-key="${f.key}" value="${escHtml(String(val))}" readonly>
            </div>`;

        default: // text
            return `<div class="modal-field">${label}
                <input id="${id}" class="modal-input" type="text" data-key="${f.key}" value="${escHtml(String(val))}"${ph}${req}>
            </div>`;
    }
}

// ── Value Collector (private) ───────────────────────────────
function _collectFormValues(fields) {
    const values = {};
    for (const f of fields) {
        if (f.type === 'readonly') {
            values[f.key] = f.value;
            continue;
        }
        const el = document.querySelector(`[data-key="${f.key}"]`);
        if (!el) continue;

        let v = el.value;

        if (f.type === 'number' || f.type === 'range') {
            v = v === '' ? null : Number(v);
        } else if (el.dataset.type === 'tags') {
            v = v.split(',').map(s => s.trim()).filter(Boolean);
        }

        if (f.required && (v === '' || v == null)) {
            el.classList.add('modal-input--error');
            el.focus();
            return null;
        }
        el.classList.remove('modal-input--error');
        values[f.key] = v;
    }
    return values;
}
