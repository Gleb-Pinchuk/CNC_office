// ==================== CNC Office - Frontend App v19.4 (Landing overlay + nav polish) ====================
const API_BASE = '/api';
let currentUser = null;
let currentFolder = null;
let currentView = 'files';
let currentDocument = null;
let currentSectionType = null;
let authToken = localStorage.getItem('cnc_auth_token');
let hotInstance = null;
let sheetEditor = null;
let workbookBaseSnapshot = null;
let sheetDirtySince = 0;
const VIEW_STORAGE_KEY = 'cnc_current_view';
const EDITOR_STATE_KEY = 'cnc_editor_state_v2';
const PRESENCE_PING_MS = 1200;
const HASH_EDITOR_KEY = 'editor';
let realtimeSaveTimer = null;
let sheetPresenceInterval = null;
let lastPresenceKey = '';
let currentPresenceItems = [];
let livePresenceLayer = null;

// DOM Elements
const filesGrid = document.getElementById('filesGrid');
const loadingState = document.getElementById('loadingState');
const emptyState = document.getElementById('emptyState');
const pageTitle = document.getElementById('pageTitle');
const uploadModal = document.getElementById('uploadModal');
const loginModal = document.getElementById('loginModal');
const previewModal = document.getElementById('previewModal');
const documentModal = document.getElementById('documentModal');
const createDocumentModalEl = document.getElementById('createDocumentModal');
const uploadBtn = document.getElementById('uploadBtn');
const logoutBtn = document.getElementById('logoutBtn');
const uploadForm = document.getElementById('uploadForm');
const loginForm = document.getElementById('loginForm');
const registerForm = document.getElementById('registerForm');
const usernameSpan = document.getElementById('username');
const folderSelect = document.getElementById('folderSelect');
const navItems = document.querySelectorAll('.nav-item');

// ✅ Инициализация
document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 App initialized v19.3');
    setupEventListeners();
    setAuthUI(!!authToken);
    checkAuth();
});

function setAuthUI(isAuthed) {
    if (logoutBtn) logoutBtn.style.display = isAuthed ? 'inline-flex' : 'none';
    const userProfile = document.querySelector('.user-profile');
    if (userProfile) userProfile.style.display = isAuthed ? 'flex' : 'none';
    const sidebar = document.querySelector('.sidebar');
    if (sidebar) sidebar.style.display = isAuthed ? 'flex' : 'none';
    const header = document.querySelector('.header');
    if (header) header.style.display = isAuthed ? 'flex' : 'none';
}

// ✅ Заголовки для API-запросов
function getAuthHeaders(isJson = true) {
    const headers = { 'Accept': 'application/json' };
    if (authToken) headers['Authorization'] = `Token ${authToken}`;
    if (isJson) headers['Content-Type'] = 'application/json';
    return headers;
}

/** Таблицы разделов — отдельный API; иначе после «Сохранить» данные не попадали в SectionTable. */
function isCurrentSectionTable() {
    return !!(currentDocument && currentDocument.isSectionTable);
}

function getSaveContentUrl() {
    if (!currentDocument) return null;
    if (isCurrentSectionTable()) {
        return `${API_BASE}/section-tables/${currentDocument.id}/save_content/`;
    }
    return `${API_BASE}/documents/${currentDocument.id}/save_content/`;
}

function getShareUrl() {
    if (!currentDocument) return null;
    if (isCurrentSectionTable()) {
        return `${API_BASE}/section-tables/${currentDocument.id}/share/`;
    }
    return `${API_BASE}/documents/${currentDocument.id}/share/`;
}

function deepClone(value) {
    try {
        return JSON.parse(JSON.stringify(value));
    } catch (_) {
        return null;
    }
}

function markSheetDirty() {
    sheetDirtySince = Date.now();
    scheduleRealtimeSheetSave();
}

function clearSheetDirty() {
    sheetDirtySince = 0;
}

function hasPendingSheetChanges() {
    return !!sheetDirtySince;
}

function scheduleRealtimeSheetSave() {
    if (realtimeSaveTimer) clearTimeout(realtimeSaveTimer);
    realtimeSaveTimer = setTimeout(() => {
        realtimeSaveTimer = null;
        if (currentDocument && sheetEditor && !currentDocument.is_readonly) {
            saveDocumentSilent();
        }
    }, 400);
}

function getPresenceUrl() {
    if (!currentDocument) return null;
    if (isCurrentSectionTable()) {
        return `${API_BASE}/section-tables/${currentDocument.id}/presence/`;
    }
    return `${API_BASE}/documents/${currentDocument.id}/presence/`;
}

function clearEditorState() {
    localStorage.removeItem(EDITOR_STATE_KEY);
    clearEditorHashState();
}

function _buildEditorHashValue(payload) {
    const t = payload?.isSectionTable ? 'section_table' : 'document';
    const id = Number(payload?.id);
    const sel = payload?.selection || {};
    const si = Number(sel.activeSheetIndex ?? 0);
    const r = Number(sel.row ?? 0);
    const c = Number(sel.col ?? 0);
    if (!Number.isFinite(id) || id <= 0) return '';
    return `${t}:${id}:${Number.isFinite(si) ? si : 0}:${Number.isFinite(r) ? r : 0}:${Number.isFinite(c) ? c : 0}`;
}

function writeEditorHashState(payload) {
    const value = _buildEditorHashValue(payload);
    if (!value) return;
    const hash = new URLSearchParams(window.location.hash.replace(/^#/, ''));
    hash.set(HASH_EDITOR_KEY, value);
    history.replaceState(null, '', `${window.location.pathname}${window.location.search}#${hash.toString()}`);
}

function clearEditorHashState() {
    const hash = new URLSearchParams(window.location.hash.replace(/^#/, ''));
    if (!hash.has(HASH_EDITOR_KEY)) return;
    hash.delete(HASH_EDITOR_KEY);
    const tail = hash.toString();
    history.replaceState(null, '', `${window.location.pathname}${window.location.search}${tail ? `#${tail}` : ''}`);
}

function readEditorHashState() {
    const hash = new URLSearchParams(window.location.hash.replace(/^#/, ''));
    const raw = hash.get(HASH_EDITOR_KEY);
    if (!raw) return null;
    const parts = raw.split(':');
    if (parts.length < 2) return null;
    const t = parts[0] === 'section_table' ? 'section_table' : 'document';
    const id = Number(parts[1]);
    if (!Number.isFinite(id) || id <= 0) return null;
    const activeSheetIndex = Number(parts[2] ?? 0);
    const row = Number(parts[3] ?? 0);
    const col = Number(parts[4] ?? 0);
    return {
        isSectionTable: t === 'section_table',
        id,
        selection: {
            activeSheetIndex: Number.isFinite(activeSheetIndex) ? activeSheetIndex : 0,
            row: Number.isFinite(row) ? row : 0,
            col: Number.isFinite(col) ? col : 0,
        },
        ts: Date.now(),
    };
}

function saveEditorState() {
    if (!currentDocument || !sheetEditor) return;
    const sel = sheetEditor.getSelectionMeta ? sheetEditor.getSelectionMeta() : null;
    const payload = {
        view: currentView,
        isSectionTable: !!currentDocument.isSectionTable,
        id: currentDocument.id,
        selection: sel,
        ts: Date.now(),
    };
    localStorage.setItem(EDITOR_STATE_KEY, JSON.stringify(payload));
    writeEditorHashState(payload);
}

function readEditorState() {
    try {
        const raw = localStorage.getItem(EDITOR_STATE_KEY);
        if (!raw) return null;
        const parsed = JSON.parse(raw);
        if (!parsed || typeof parsed !== 'object' || !parsed.id) return null;
        return parsed;
    } catch (_) {
        return null;
    }
}

async function restoreEditorStateAfterReload() {
    const st = readEditorHashState() || readEditorState();
    if (!st || !st.id) return;
    const ageMs = Date.now() - Number(st.ts || 0);
    if (ageMs > 1000 * 60 * 30) return;
    if (st.view && st.view !== currentView) {
        await loadView(st.view);
    }
    if (st.isSectionTable) {
        await openSectionTable(st.id, st.selection || null);
    } else {
        await openDocument(st.id, st.selection || null);
    }
}

function collectChangedCells(baseWorkbook, currentWorkbook) {
    if (!baseWorkbook || !currentWorkbook) return null;
    const base = migrateWorkbookPayload(baseWorkbook);
    const cur = migrateWorkbookPayload(currentWorkbook);
    if (!Array.isArray(base.sheets) || !Array.isArray(cur.sheets)) return null;
    if (base.sheets.length !== cur.sheets.length) return null;

    const changed = [];
    for (let s = 0; s < cur.sheets.length; s++) {
        const b = normalizeSheetPayload(base.sheets[s] || {});
        const c = normalizeSheetPayload(cur.sheets[s] || {});
        if ((b.name || '').trim().toLowerCase() !== (c.name || '').trim().toLowerCase()) return null;

        const bStyles = JSON.stringify(b.styles || {});
        const cStyles = JSON.stringify(c.styles || {});
        const bCF = JSON.stringify(b.columnFilters || {});
        const cCF = JSON.stringify(c.columnFilters || {});
        const bCW = JSON.stringify(b.colWidths || []);
        const cCW = JSON.stringify(c.colWidths || []);
        const bRH = JSON.stringify(b.rowHeights || []);
        const cRH = JSON.stringify(c.rowHeights || []);
        if (bStyles !== cStyles || bCF !== cCF || bCW !== cCW || bRH !== cRH) return null;

        const rows = Math.max(b.data.length, c.data.length);
        const cols = Math.max(b.data[0]?.length || 0, c.data[0]?.length || 0);
        for (let r = 0; r < rows; r++) {
            for (let col = 0; col < cols; col++) {
                const beforeVal = String((b.data[r] && b.data[r][col]) ?? '');
                const nowVal = String((c.data[r] && c.data[r][col]) ?? '');
                if (beforeVal !== nowVal) {
                    changed.push({ sheet_name: c.name || `Лист${s + 1}`, row: r, col, value: nowVal });
                }
            }
        }
    }
    return changed;
}

function buildSpreadsheetSavePayload() {
    if (!sheetEditor) return null;
    const currentWorkbook = sheetEditor.export();
    const body = { content: { custom_sheet: currentWorkbook } };
    if (workbookBaseSnapshot) {
        const changedCells = collectChangedCells(workbookBaseSnapshot, currentWorkbook);
        if (changedCells && changedCells.length > 0) {
            body.changed_cells = changedCells;
        } else if (changedCells && changedCells.length === 0) {
            return { skip: true, workbook: currentWorkbook, body };
        }
        if (changedCells) {
            body.base_updated_at = currentDocument?.updated_at || null;
        }
    }
    return { skip: false, workbook: currentWorkbook, body };
}

// ✅ Экранирование HTML
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ✅ Очистка авторизации
function clearAuth() {
    localStorage.removeItem('cnc_auth_token');
    localStorage.removeItem('cnc_username');
    clearEditorState();
    authToken = null;
    currentUser = null;
    setAuthUI(false);
}

// ✅ Проверка авторизации
async function checkAuth() {
    authToken = localStorage.getItem('cnc_auth_token');
    if (!authToken) { setAuthUI(false); showLoginModal(); return; }

    try {
        const res = await fetch(`${API_BASE}/users/me/`, { headers: getAuthHeaders() });
        if (res.ok) {
            currentUser = await res.json();
            if (usernameSpan) usernameSpan.textContent = currentUser.username;
            setAuthUI(true);
            const savedView = localStorage.getItem(VIEW_STORAGE_KEY) || 'files';
            await loadView(savedView);
            await restoreEditorStateAfterReload();
        } else {
            clearAuth();
            showLoginModal();
        }
    } catch (e) {
        console.error('Auth check failed:', e);
        setAuthUI(false);
        showLoginModal();
    }
}

// ✅ Показать модальное окно
function showModal(modal) {
    const el = typeof modal === 'string' ? document.getElementById(modal) : modal;
    if (el) {
        el.classList.add('show');
        el.style.display = 'flex';
        document.body.style.overflow = 'hidden';
        setTimeout(() => {
            if (sheetEditor) sheetEditor.focus();
        }, 100);
    }
}

// Совместимость с landing: глобальные функции openModal/closeModal
function openModal(modalId) {
    showModal(modalId);
}

function closeModal(modalId) {
    hideModal(modalId);
}

async function sendPresenceLeave() {
    const url = getPresenceUrl();
    if (!url || !authToken) return;
    try {
        await fetch(url, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({ editing: false }),
        });
    } catch (_) {
        // noop
    }
}

function stopSheetPresenceLoop() {
    if (sheetPresenceInterval) {
        clearInterval(sheetPresenceInterval);
        sheetPresenceInterval = null;
    }
    lastPresenceKey = '';
    currentPresenceItems = [];
    const container = document.getElementById('handsontable-container');
    if (!container) return;
    container.querySelectorAll('.sheet-cell.live-editing-cell').forEach((el) => {
        el.classList.remove('live-editing-cell');
        el.style.removeProperty('--live-color');
    });
    if (livePresenceLayer) {
        livePresenceLayer.innerHTML = '';
    }
}

function _presenceColor(username) {
    const palette = ['#0ea5e9', '#14b8a6', '#f97316', '#ef4444', '#8b5cf6', '#ec4899', '#22c55e'];
    let hash = 0;
    const s = String(username || '');
    for (let i = 0; i < s.length; i++) hash = ((hash << 5) - hash) + s.charCodeAt(i);
    return palette[Math.abs(hash) % palette.length];
}

function ensureLivePresenceLayer() {
    if (livePresenceLayer && document.body.contains(livePresenceLayer)) {
        return livePresenceLayer;
    }
    livePresenceLayer = document.getElementById('livePresenceLayer');
    if (!livePresenceLayer) {
        livePresenceLayer = document.createElement('div');
        livePresenceLayer.id = 'livePresenceLayer';
        livePresenceLayer.className = 'live-presence-layer';
        document.body.appendChild(livePresenceLayer);
    }
    return livePresenceLayer;
}

function applyLivePresence(items) {
    const container = document.getElementById('handsontable-container');
    if (!container || !sheetEditor) return;
    const layer = ensureLivePresenceLayer();
    const own = String(currentUser?.username || '').toLowerCase();
    const active = sheetEditor.getSelectionMeta ? sheetEditor.getSelectionMeta() : null;
    const activeSheet = String(active?.sheetName || '').trim().toLowerCase();

    container.querySelectorAll('.sheet-cell.live-editing-cell').forEach((el) => {
        el.classList.remove('live-editing-cell');
        el.style.removeProperty('--live-color');
    });
    layer.innerHTML = '';

    (items || []).forEach((p) => {
        const username = String(p?.username || '');
        if (!username || username.toLowerCase() === own) return;
        const sheetName = String(p?.sheet_name || '').trim().toLowerCase();
        if (!activeSheet || sheetName !== activeSheet) return;
        const row = Number(p?.row);
        const col = Number(p?.col);
        if (!Number.isFinite(row) || !Number.isFinite(col) || row < 0 || col < 0) return;
        const cell = container.querySelector(`.sheet-cell[data-r="${row}"][data-c="${col}"]`);
        if (!cell) return;
        const color = _presenceColor(username);
        cell.classList.add('live-editing-cell');
        cell.style.setProperty('--live-color', color);
        const rect = cell.getBoundingClientRect();
        const badge = document.createElement('div');
        badge.className = 'live-presence-badge';
        badge.textContent = username;
        badge.style.setProperty('--live-color', color);
        const top = Math.max(8, rect.top - 32);
        const left = Math.max(8, rect.left + 2);
        badge.style.top = `${top}px`;
        badge.style.left = `${left}px`;
        layer.appendChild(badge);
    });
}

function startSheetPresenceLoop() {
    stopSheetPresenceLoop();
    if (!sheetEditor || !currentDocument) return;
    const tick = async () => {
        if (!sheetEditor || !currentDocument) {
            stopSheetPresenceLoop();
            return;
        }
        const meta = sheetEditor.getSelectionMeta ? sheetEditor.getSelectionMeta() : null;
        if (!meta) return;
        const payload = {
            sheet_name: meta.sheetName || '',
            row: meta.row,
            col: meta.col,
            editing: true,
        };
        const nextKey = `${payload.sheet_name}:${payload.row}:${payload.col}`;
        saveEditorState();
        try {
            const url = getPresenceUrl();
            if (!url) return;
            const canEdit = !currentDocument.is_readonly;
            const shouldPing = nextKey !== lastPresenceKey || !currentPresenceItems.length;
            const method = (canEdit && shouldPing) ? 'POST' : 'GET';
            const res = await fetch(url, {
                method,
                headers: getAuthHeaders(),
                body: method === 'POST' ? JSON.stringify(payload) : undefined,
            });
            if (!res.ok) return;
            const data = await res.json().catch(() => ({}));
            currentPresenceItems = Array.isArray(data?.presence) ? data.presence : [];
            lastPresenceKey = nextKey;
            applyLivePresence(currentPresenceItems);
        } catch (_) {
            // noop
        }
    };
    tick();
    sheetPresenceInterval = setInterval(tick, PRESENCE_PING_MS);
}

// ✅ Скрыть модальное окно
function hideModal(modal) {
    const el = typeof modal === 'string' ? document.getElementById(modal) : modal;
    if (el) {
        if (el.id === 'documentModal') {
            if (currentDocument && (hotInstance || sheetEditor)) saveDocumentSilent();
            if (sheetEditor) { sheetEditor.destroy(); sheetEditor = null; }
            if (hotInstance) { hotInstance.destroy(); hotInstance = null; }
            if (window._sheetSyncInterval) {
                clearInterval(window._sheetSyncInterval);
                window._sheetSyncInterval = null;
            }
            if (window._sheetRefreshInterval) {
                clearInterval(window._sheetRefreshInterval);
                window._sheetRefreshInterval = null;
            }
            stopSheetPresenceLoop();
            sendPresenceLeave();
            if (realtimeSaveTimer) {
                clearTimeout(realtimeSaveTimer);
                realtimeSaveTimer = null;
            }
            workbookBaseSnapshot = null;
            clearSheetDirty();
            clearEditorState();
            currentDocument = null;
        }
        el.classList.remove('show');
        setTimeout(() => { el.style.display = 'none'; }, 200);
        document.body.style.overflow = '';
        const form = el.querySelector('form'); if (form) form.reset();
    }
}

function showLoginModal() {
    if (loginForm) loginForm.classList.remove('hidden');
    if (registerForm) registerForm.classList.add('hidden');
    showModal(loginModal);
}

function showRegisterModal() {
    if (registerForm) registerForm.classList.remove('hidden');
    if (loginForm) loginForm.classList.add('hidden');
    showModal(loginModal);
}

// ✅ ЛОГИН (ИСПРАВЛЕНО: без Authorization заголовка)
async function handleLogin(e) {
    e.preventDefault();
    const username = document.getElementById('loginUsername')?.value?.trim();
    const password = document.getElementById('loginPassword')?.value;

    if (!username || !password) { alert('Введите логин и пароль'); return; }

    try {
        const res = await fetch(`${API_BASE}/users/login/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify({ username, password })
        });

        const data = await res.json().catch(() => ({}));

        if (res.ok && data.token) {
            authToken = data.token;
            localStorage.setItem('cnc_auth_token', data.token);
            localStorage.setItem('cnc_username', data.user?.username || username);
            currentUser = data.user || { username };
            if (usernameSpan) usernameSpan.textContent = currentUser.username;
            hideModal('loginModal');
            await loadView(localStorage.getItem(VIEW_STORAGE_KEY) || 'files');
            await restoreEditorStateAfterReload();
        } else {
            const errorMsg = data.detail ||
                           data.non_field_errors?.[0] ||
                           'Неверный логин или пароль';
            alert(`❌ ${errorMsg}`);
        }
    } catch (e) {
        console.error('Login error:', e);
        alert('Ошибка подключения к серверу');
    }
}

// ✅ РЕГИСТРАЦИЯ
async function handleRegister(e) {
    e.preventDefault();
    const username = document.getElementById('registerUsername')?.value?.trim();
    const email = document.getElementById('registerEmail')?.value?.trim();
    const password = document.getElementById('registerPassword')?.value;
    const password2 = document.getElementById('registerPassword2')?.value;

    if (!username || !email || !password || !password2) { alert('Заполните все поля'); return; }
    if (password !== password2) { alert('Пароли не совпадают'); return; }
    if (password.length < 8) { alert('Пароль минимум 8 символов'); return; }

    try {
        const res = await fetch(`${API_BASE}/users/register/`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({ username, email, password, password2 })
        });
        const data = await res.json().catch(() => ({}));

        if (res.ok || res.status === 201) {
            if (data.token) {
                authToken = data.token;
                localStorage.setItem('cnc_auth_token', data.token);
                localStorage.setItem('cnc_username', data.user?.username || username);
                currentUser = data.user || { username };
                if (usernameSpan) usernameSpan.textContent = currentUser.username;
                hideModal('loginModal');
                await loadView(localStorage.getItem(VIEW_STORAGE_KEY) || 'files');
                await restoreEditorStateAfterReload();
            } else {
                alert('✅ Регистрация успешна! Теперь войдите.');
                if (registerForm) registerForm.classList.add('hidden');
                if (loginForm) loginForm.classList.remove('hidden');
            }
        } else {
            let msg = '❌ Ошибка:\n';
            if (typeof data === 'object') {
                for (const [k, v] of Object.entries(data)) {
                    msg += `${k}: ${Array.isArray(v) ? v.join(', ') : v}\n`;
                }
            }
            alert(msg || 'Неизвестная ошибка');
        }
    } catch (e) {
        console.error('Register error:', e);
        alert('Ошибка: ' + e.message);
    }
}

async function logout() { clearAuth(); location.reload(); }

// ✅ ЗАГРУЗКА ВИДА
async function loadView(view) {
    currentView = view;
    localStorage.setItem(VIEW_STORAGE_KEY, view);
    navItems.forEach(n => n.classList.toggle('active', n.getAttribute('data-view') === view));
    if (window._listAutoRefreshInterval) {
        clearInterval(window._listAutoRefreshInterval);
        window._listAutoRefreshInterval = null;
    }

    const titles = {
        'files': 'Мои файлы',
        'folders': 'Папки',
        'documents': 'Документы',
        'section-attendance': 'Посещаемость',
        'section-rangers': 'Цифровые рейнджеры',
        'section-statements': 'Ведомости',
        'shared': 'Общий доступ',
        'logs': 'Журнал аудита'
    };
    if (pageTitle) pageTitle.textContent = titles[view] || 'CNC Office';

    if (uploadBtn) {
        if (view === 'files') {
            uploadBtn.style.display = 'inline-flex';
                uploadBtn.innerHTML = 'Загрузить файл';
            uploadBtn.onclick = () => { loadFoldersForDropdown(); showModal(uploadModal); };
        } else if (view === 'folders') {
            uploadBtn.style.display = 'inline-flex';
                uploadBtn.innerHTML = 'Создать папку';
            uploadBtn.onclick = createFolder;
        } else if (view === 'documents' || view?.startsWith('section-')) {
            uploadBtn.style.display = 'inline-flex';
                uploadBtn.innerHTML = 'Создать таблицу';
            uploadBtn.onclick = view === 'documents' ? openCreateDocumentModal :
                () => openCreateSectionTableModal(view?.replace('section-', ''));
        } else {
            uploadBtn.style.display = 'none';
            uploadBtn.onclick = null;
        }
    }

    showLoading();
    switch(view) {
        case 'files': await loadFiles(); break;
        case 'folders': await loadFolders(); break;
        case 'documents': await loadDocuments(); break;
        case 'section-attendance':
        case 'section-rangers':
        case 'section-statements':
            await loadSectionTable(view?.replace('section-', ''));
            break;
        case 'shared': await loadShared(); break;
        case 'logs': await loadLogs(); break;
        default: await loadFiles();
    }

    if (view === 'documents' || view?.startsWith('section-')) {
        window._listAutoRefreshInterval = setInterval(() => {
            if (currentView === 'documents') loadDocuments();
            if (currentView?.startsWith('section-')) loadSectionTable(currentView.replace('section-', ''));
        }, 10000);
    }
}

// ✅ ЗАГРУЗКА ФАЙЛОВ
async function loadFiles() {
    console.log('🔄 Loading files...');
    try {
        let url = `${API_BASE}/files/`;
        if (currentFolder) url += `?folder=${currentFolder.id}`;
        const res = await fetch(url, { headers: getAuthHeaders() });
        if (res.status === 200) {
            const data = await res.json();
            const files = data.results || data || [];
            renderFiles(files);
        } else if (res.status === 401 || res.status === 403) {
            clearAuth(); showLoginModal();
        } else {
            showEmpty('Не удалось загрузить файлы');
        }
    } catch (e) {
        console.error('❌ Load files error:', e);
        showEmpty('Ошибка подключения');
    }
}

function renderFiles(files) {
    hideLoading();
    if (!files?.length) { showEmpty('Нет файлов'); return; }
    hideEmpty();
    if (filesGrid) {
        filesGrid.innerHTML = '';
        files.forEach((f, i) => { if (f) filesGrid.appendChild(createFileCard(f, i)); });
    }
}

function createFileCard(file, index) {
    const card = document.createElement('div');
    card.className = 'file-card';
    card.style.animationDelay = `${index * 0.1}s`;
    card.style.cursor = 'pointer';
    card.onclick = (e) => { if (!e.target.closest('.file-actions')) { showPreviewModal(file); } };

    const icon = getFileIcon(file.mime_type);
    let name = file.file_name || (file.file ? file.file.split('/').pop() : 'Без имени');
    try { name = decodeURIComponent(name); } catch {}
    const size = file.size_mb ? `${file.size_mb} MB` : file.size ? `${(file.size/1024/1024).toFixed(2)} MB` : '0 MB';
    const date = file.uploaded_at ? new Date(file.uploaded_at).toLocaleDateString('ru-RU') : '';
    const canAct = file.owner?.username === currentUser?.username;

    card.innerHTML = `
        <div class="file-icon">${icon}</div>
        <div class="file-name" title="${escapeHtml(name)}">${escapeHtml(name)}</div>
        <div class="file-meta"><span>${size}</span><span>${date}</span></div>
        <div class="file-actions">
            ${canAct ? `<button class="file-action-btn" title="Download" onclick="event.stopPropagation();downloadFile(${file.id})">${iconGlyph('download')}</button>` : ''}
            ${canAct ? `<button class="file-action-btn" title="Share" onclick="event.stopPropagation();shareFile(${file.id})">${iconGlyph('share')}</button>` : ''}
            ${canAct ? `<button class="file-action-btn" title="Delete" onclick="event.stopPropagation();deleteFile(${file.id})">${iconGlyph('trash')}</button>` : ''}
        </div>`;
    return card;
}

function iconGlyph(name) {
    const map = {
        file: '<svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path stroke-width="1.8" d="M14 2H7a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7z"/><path stroke-width="1.8" d="M14 2v5h5"/></svg>',
        table: '<svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor"><rect x="3" y="4" width="18" height="16" rx="2" stroke-width="1.8"/><path stroke-width="1.8" d="M3 10h18M9 4v16M15 4v16"/></svg>',
        text: '<svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path stroke-width="1.8" d="M4 5h16M4 10h16M4 15h11"/></svg>',
        image: '<svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor"><rect x="3" y="4" width="18" height="16" rx="2" stroke-width="1.8"/><circle cx="9" cy="10" r="2" stroke-width="1.8"/><path stroke-width="1.8" d="m21 16-4.8-4.8a1 1 0 0 0-1.4 0L8 18"/></svg>',
        video: '<svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor"><rect x="3" y="5" width="14" height="14" rx="2" stroke-width="1.8"/><path stroke-width="1.8" d="m17 10 4-2v8l-4-2z"/></svg>',
        audio: '<svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path stroke-width="1.8" d="M9 18V6l10-2v12"/><circle cx="6" cy="18" r="3" stroke-width="1.8"/><circle cx="16" cy="16" r="3" stroke-width="1.8"/></svg>',
        archive: '<svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor"><rect x="3" y="4" width="18" height="5" rx="1" stroke-width="1.8"/><path stroke-width="1.8" d="M4 9h16v10a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2z"/><path stroke-width="1.8" d="M10 13h4"/></svg>',
        folder: '<svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path stroke-width="1.8" d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v8a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3z"/></svg>',
        link: '<svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path stroke-width="1.8" d="M10 13a5 5 0 0 0 7.1 0l2.8-2.8a5 5 0 0 0-7.1-7.1L10 5"/><path stroke-width="1.8" d="M14 11a5 5 0 0 0-7.1 0l-2.8 2.8a5 5 0 0 0 7.1 7.1L14 19"/></svg>',
        download: '<svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path stroke-width="1.8" d="M12 3v12"/><path stroke-width="1.8" d="m7 10 5 5 5-5"/><path stroke-width="1.8" d="M4 21h16"/></svg>',
        share: '<svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="18" cy="5" r="3" stroke-width="1.8"/><circle cx="6" cy="12" r="3" stroke-width="1.8"/><circle cx="18" cy="19" r="3" stroke-width="1.8"/><path stroke-width="1.8" d="m8.6 13.5 6.8 4M15.4 6.5l-6.8 4"/></svg>',
        trash: '<svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path stroke-width="1.8" d="M3 6h18"/><path stroke-width="1.8" d="M8 6V4h8v2"/><path stroke-width="1.8" d="M19 6l-1 14H6L5 6"/><path stroke-width="1.8" d="M10 11v6M14 11v6"/></svg>',
        pencil: '<svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path stroke-width="1.8" d="m4 20 4.2-1 9.7-9.7a2.1 2.1 0 0 0 0-3l-.2-.2a2.1 2.1 0 0 0-3 0L5 15.8z"/><path stroke-width="1.8" d="m13.5 7.5 3 3"/></svg>',
        shield: '<svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path stroke-width="1.8" d="M12 3 4 6v6c0 5 3.4 8.8 8 10 4.6-1.2 8-5 8-10V6z"/></svg>',
        login: '<svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path stroke-width="1.8" d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/><path stroke-width="1.8" d="m10 17 5-5-5-5"/><path stroke-width="1.8" d="M15 12H3"/></svg>',
        logout: '<svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path stroke-width="1.8" d="M10 17l-5-5 5-5"/><path stroke-width="1.8" d="M5 12h12"/><path stroke-width="1.8" d="M14 3h5a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-5"/></svg>',
    };
    return map[name] || map.file;
}
function getFileIcon(mimeType) {
    if (!mimeType) return iconGlyph('file');
    const mt = mimeType.toLowerCase();
    if (mt.includes('excel') || mt.includes('spreadsheet')) return iconGlyph('table');
    if (mt.includes('word') || mt.includes('.doc') || mt.includes('text')) return iconGlyph('text');
    if (mt.includes('pdf')) return iconGlyph('file');
    if (mt.includes('image')) return iconGlyph('image');
    if (mt.includes('video')) return iconGlyph('video');
    if (mt.includes('audio')) return iconGlyph('audio');
    if (mt.includes('zip')) return iconGlyph('archive');
    return iconGlyph('file');
}

// ✅ ЗАГРУЗКА ФАЙЛА (ИСПРАВЛЕНО: FormData без Content-Type)
async function uploadFile(file) {
    console.log('📤 Uploading:', file.name, file.size, 'bytes');
    const fd = new FormData();
    fd.append('file', file);
    if (currentFolder) fd.append('folder', currentFolder.id);
    else if (folderSelect?.value) fd.append('folder', folderSelect.value);

    try {
        const headers = getAuthHeaders(false);
        delete headers['Content-Type']; // ✅ Важно для FormData

        const res = await fetch(`${API_BASE}/files/`, {
            method: 'POST',
            headers: headers,
            body: fd
        });
        const data = await res.json().catch(() => ({}));
        if (res.ok || res.status === 201) {
            hideModal('uploadModal');
            if (uploadForm) uploadForm.reset();
            await loadFiles();
        } else {
            alert(`Ошибка: ${data.detail || data.file?.[0] || data.error || 'Неизвестная ошибка'}`);
        }
    } catch (e) {
        console.error('❌ Upload error:', e);
        alert('Ошибка подключения: ' + e.message);
    }
}

async function handleUpload(e) {
    e.preventDefault();
    const fi = document.getElementById('fileInput');
    if (!fi?.files[0]) { alert('Выберите файл'); return; }
    await uploadFile(fi.files[0]);
}

// ✅ СКАЧИВАНИЕ ФАЙЛА
async function downloadFile(fileId) {
    try {
        const res = await fetch(`${API_BASE}/files/${fileId}/download/`, { headers: getAuthHeaders() });
        if (res.ok) {
            const blob = await res.blob();
            let filename = `file_${fileId}`;
            const disposition = res.headers.get('Content-Disposition');
            if (disposition) {
                const m = disposition.match(/filename\*=UTF-8''([^;]+)/i) || disposition.match(/filename="([^"]+)"/i);
                if (m && m[1]) filename = decodeURIComponent(m[1]);
            }
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        } else if (res.status === 401 || res.status === 403) {
            clearAuth(); showLoginModal();
        } else {
            alert('Не удалось скачать');
        }
    } catch (e) {
        console.error('Download error:', e);
        alert('Ошибка подключения');
    }
}

// ✅ ПОДЕЛИТЬСЯ ФАЙЛОМ
async function shareFile(fileId) {
    const username = prompt('Имя пользователя:');
    if (!username) return;
    const canWrite = confirm('Разрешить редактирование?\n\nОК = чтение и запись\nОтмена = только чтение');
    try {
        const res = await fetch(`${API_BASE}/files/${fileId}/share/`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({ username, permission: canWrite ? 'write' : 'read' })
        });
        const data = await res.json().catch(() => ({}));
        alert(res.ok ? `✅ Доступ предоставлен ${username}` : `❌ ${data.detail || 'Ошибка'}`);
    } catch {
        alert('Ошибка подключения');
    }
}

async function updatePermission(permId, permission) {
    try {
        const res = await fetch(`${API_BASE}/permissions/${permId}/`, {
            method: 'PATCH',
            headers: getAuthHeaders(),
            body: JSON.stringify({ permission })
        });
        if (res.ok) {
            await loadShared();
        } else {
            const err = await res.json().catch(() => ({}));
            alert(`❌ ${err.detail || 'Не удалось обновить доступ'}`);
        }
    } catch { alert('Ошибка подключения'); }
}

async function revokePermission(permId) {
    if (!confirm('Снять доступ?')) return;
    try {
        const res = await fetch(`${API_BASE}/permissions/${permId}/`, { method: 'DELETE', headers: getAuthHeaders(false) });
        if (res.ok || res.status === 204) await loadShared();
        else {
            const err = await res.json().catch(() => ({}));
            alert(`❌ ${err.detail || 'Не удалось снять доступ'}`);
        }
    } catch { alert('Ошибка подключения'); }
}

// ✅ УДАЛЕНИЕ ФАЙЛА
async function deleteFile(fileId) {
    if (!confirm('Удалить файл?')) return;
    try {
        const res = await fetch(`${API_BASE}/files/${fileId}/`, { method: 'DELETE', headers: getAuthHeaders() });
        if (res.ok || res.status === 204) await loadFiles();
        else alert('Ошибка удаления');
    } catch {
        alert('Ошибка подключения');
    }
}

// ✅ ПРЕДПРОСМОТР ФАЙЛОВ
function showPreviewModal(file) {
    const mt = (file.mime_type || '').toLowerCase();
    const fileExt = (file.file_name || '').split('.').pop().toLowerCase();
    const downloadUrl = `${API_BASE}/files/${file.id}/download/`;

    if (mt.includes('pdf') || fileExt === 'pdf') {
        window.open(downloadUrl, '_blank');
        return;
    }

    if (!previewModal) { downloadFile(file.id); return; }
    const previewContent = document.getElementById('previewContent');
    const previewTitle = document.getElementById('previewTitle');
    if (!previewContent || !previewTitle) { downloadFile(file.id); return; }

    previewTitle.textContent = file.file_name || 'Файл';

    if (mt.includes('image') || ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg', 'webp'].includes(fileExt)) {
        fetch(downloadUrl, { headers: getAuthHeaders() })
            .then(res => res.blob())
            .then(blob => {
                const imgUrl = URL.createObjectURL(blob);
                previewContent.innerHTML = `<div style="text-align:center;"><img src="${imgUrl}" style="max-width:100%;max-height:80vh;border-radius:8px;"></div>`;
                showModal(previewModal);
            })
            .catch(() => {
                previewContent.innerHTML = `<p style="color:#ff4466;">Не удалось загрузить</p><button class="btn btn-primary" onclick="downloadFile(${file.id})">Скачать</button>`;
                showModal(previewModal);
            });
    }
    else if (mt.includes('text') || ['txt', 'json', 'csv', 'xml', 'md', 'log', 'py', 'js', 'html', 'css', 'sql'].includes(fileExt)) {
        fetch(downloadUrl, { headers: getAuthHeaders() })
            .then(res => res.text())
            .then(text => {
                previewContent.innerHTML = `<pre style="background:#1a1a25;padding:1rem;border-radius:8px;overflow:auto;max-height:80vh;color:#fff;white-space:pre-wrap;word-wrap:break-word;font-family:monospace;font-size:13px;">${escapeHtml(text)}</pre>`;
                showModal(previewModal);
            })
            .catch(() => {
                previewContent.innerHTML = `<p style="color:#ff4466;">Не удалось загрузить</p><button class="btn btn-primary" onclick="downloadFile(${file.id})">Скачать</button>`;
                showModal(previewModal);
            });
    }
    else if (mt.includes('video') || ['mp4', 'avi', 'mkv', 'mov', 'webm', 'flv'].includes(fileExt)) {
        previewContent.innerHTML = `<div style="text-align:center;"><video controls style="max-width:100%;max-height:80vh;border-radius:8px;background:#000;"><source src="${downloadUrl}" type="${mt || 'video/mp4'}">Ваш браузер не поддерживает видео</video></div>`;
        showModal(previewModal);
    }
    else if (mt.includes('audio') || ['mp3', 'wav', 'ogg', 'flac', 'm4a'].includes(fileExt)) {
        previewContent.innerHTML = `<div style="text-align:center;padding:2rem;"><audio controls style="width:100%;max-width:600px;"><source src="${downloadUrl}" type="${mt || 'audio/mp3'}">Ваш браузер не поддерживает аудио</audio></div>`;
        showModal(previewModal);
    }
    else if (mt.includes('excel') || mt.includes('spreadsheet') || ['xls', 'xlsx', 'csv'].includes(fileExt)) {
        previewContent.innerHTML = `
            <div style="text-align:center;padding:2rem;">
                <div style="font-size:4rem;margin-bottom:1rem;display:flex;justify-content:center;">${iconGlyph('table')}</div>
                <h3>Excel файл</h3>
                <p style="color:#888;margin:1rem 0;">${file.file_name || 'Файл'}</p>
                <button class="btn btn-primary" onclick="downloadFile(${file.id})">Скачать</button>
            </div>
        `;
        showModal(previewModal);
    }
    else {
        downloadFile(file.id);
    }
}

// ✅ ЭКСПОРТ В EXCEL (CSV)
async function exportToExcel() {
    if ((!hotInstance && !sheetEditor) || !currentDocument) {
        alert('Нет данных для экспорта');
        return;
    }
    try {
        // Prefer real XLSX export from backend (keeps sheets + basic formatting).
        if (currentDocument.doc_type === 'spreadsheet') {
            const base = isCurrentSectionTable()
                ? `${API_BASE}/section-tables/${currentDocument.id}/export_xlsx/`
                : `${API_BASE}/documents/${currentDocument.id}/export_xlsx/`;
            const res = await fetch(base, { headers: getAuthHeaders(false) });
            if (!res.ok) throw new Error(`export_xlsx failed: ${res.status}`);
            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = `${currentDocument.title || 'table'}.xlsx`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(url);
            return;
        }

        // Fallback for non-spreadsheets: CSV
        const data = sheetEditor ? (sheetEditor.getActiveGridData ? sheetEditor.getActiveGridData() : sheetEditor.export().data) : hotInstance.getData();
        const headers = data[0] ? data[0].map((_, i) => String.fromCharCode(65 + (i % 26))) : [];
        let csv = [];
        if (headers && headers.length > 0) csv.push(headers.map(h => `"${h || ''}"`).join(';'));
        data.forEach(row => csv.push(row.map(cell => `"${cell || ''}"`).join(';')));
        const blob = new Blob(['\ufeff' + csv.join('\n')], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `${currentDocument.title || 'table'}.csv`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    } catch (e) {
        console.error('❌ Export error:', e);
        alert('Ошибка экспорта: ' + e.message);
    }
}

// ✅ ЗАГРУЗКА ПАПОК ДЛЯ DROPDOWN
async function loadFoldersForDropdown() {
    if (!folderSelect) return;
    folderSelect.innerHTML = '<option value="">Корневая папка</option>';
    try {
        const res = await fetch(`${API_BASE}/folders/`, { headers: getAuthHeaders() });
        if (res.status === 200) {
            const data = await res.json();
            const folders = data.results || data || [];
            folders.forEach(folder => {
                const option = document.createElement('option');
                option.value = folder.id;
                option.textContent = folder.name;
                folderSelect.appendChild(option);
            });
        }
    } catch (e) {}
}

// ✅ ЗАГРУЗКА ПАПОК
async function loadFolders() {
    console.log('📁 Loading folders...');
    try {
        const res = await fetch(`${API_BASE}/folders/`, { headers: getAuthHeaders() });
        if (res.status === 200) {
            const data = await res.json();
            const folders = data.results || data || [];
            renderFolders(folders);
        } else {
            showEmpty('Не удалось загрузить папки');
        }
    } catch (e) {
        console.error('❌ Load folders error:', e);
        showEmpty('Ошибка');
    }
}

function renderFolders(folders) {
    hideLoading();
    if (!folders?.length) { showEmpty('Нет папок'); return; }
    hideEmpty();
    if (filesGrid) {
        filesGrid.innerHTML = '';
        folders.forEach((f, i) => filesGrid.appendChild(createFolderCard(f, i)));
    }
}

function createFolderCard(folder, index) {
    const card = document.createElement('div');
    card.className = 'file-card';
    card.style.animationDelay = `${index * 0.1}s`;
    card.style.cursor = 'pointer';
    card.onclick = (e) => { if (!e.target.closest('.file-actions')) { currentFolder = folder; currentView = 'files'; loadView('files'); } };
    const date = folder.created_at ? new Date(folder.created_at).toLocaleDateString('ru-RU') : '';
    card.innerHTML = `
        <div class="file-icon">${iconGlyph('folder')}</div>
        <div class="file-name" title="${escapeHtml(folder.name)}">${escapeHtml(folder.name)}</div>
        <div class="file-meta"><span>${folder.files_count || 0} файлов</span><span>${date}</span></div>
        <div class="file-actions"><button class="file-action-btn" onclick="event.stopPropagation();deleteFolder(${folder.id})">${iconGlyph('trash')}</button></div>`;
    return card;
}

async function createFolder() {
    const name = prompt('Имя папки:');
    if (!name?.trim()) return;
    try {
        const res = await fetch(`${API_BASE}/folders/`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({ name: name.trim() })
        });
        if (res.ok) { await loadFolders(); }
        else { alert('Ошибка создания'); }
    } catch (e) {
        console.error('Create folder error:', e);
        alert('Ошибка');
    }
}

async function deleteFolder(id) {
    if (!confirm('Удалить папку?')) return;
    try {
        const res = await fetch(`${API_BASE}/folders/${id}/`, { method: 'DELETE', headers: getAuthHeaders() });
        if (res.ok || res.status === 204) await loadFolders();
        else alert('Ошибка');
    } catch {
        alert('Ошибка подключения');
    }
}

// ✅ ЗАГРУЗКА ДОКУМЕНТОВ
async function loadDocuments() {
    console.log('📄 Loading documents...');
    try {
        const res = await fetch(`${API_BASE}/documents/`, { headers: getAuthHeaders() });
        if (res.status === 200) {
            const data = await res.json();
            const docs = data.results || data || [];
            renderDocuments(docs);
        } else {
            showEmpty('Не удалось загрузить');
        }
    } catch (e) {
        console.error('❌ Load documents error:', e);
        showEmpty('Ошибка');
    }
}

function renderDocuments(docs) {
    hideLoading();
    if (!docs?.length) { showEmpty('Нет документов'); return; }
    hideEmpty();
    if (filesGrid) {
        filesGrid.innerHTML = '';
        docs.forEach((d, i) => filesGrid.appendChild(createDocumentCard(d, i)));
    }
}

function createDocumentCard(doc, index) {
    const card = document.createElement('div');
    card.className = 'file-card';
    card.style.animationDelay = `${index * 0.1}s`;
    card.style.cursor = 'pointer';
    card.onclick = (e) => { if (!e.target.closest('.file-actions')) openDocument(doc.id); };

    const icon = doc.doc_type === 'spreadsheet' ? iconGlyph('table') : iconGlyph('text');
    const date = doc.updated_at ? new Date(doc.updated_at).toLocaleString('ru-RU') : '';
    const canEdit = doc.is_editable || doc.owner_username === currentUser?.username;

    card.innerHTML = `
        <div class="file-icon">${icon}</div>
        <div class="file-name" title="${escapeHtml(doc.title)}">${escapeHtml(doc.title)}</div>
        <div class="file-meta"><span>${doc.doc_type === 'spreadsheet' ? 'Таблица' : 'Текст'}</span><span>${date}</span></div>
        <div class="file-actions">
            ${canEdit ? `<button class="file-action-btn" onclick="event.stopPropagation();openDocument(${doc.id})">${iconGlyph('pencil')}</button>` : ''}
            <button class="file-action-btn" onclick="event.stopPropagation();deleteDocument(${doc.id})">${iconGlyph('trash')}</button>
        </div>`;
    return card;
}

async function openDocument(docId, restoredSelection = null, sharedPermission = null) {
    try {
        const res = await fetch(`${API_BASE}/documents/${docId}/`, { headers: getAuthHeaders() });
        if (res.ok) {
            currentDocument = await res.json();
            if (sharedPermission) currentDocument.shared_permission = sharedPermission;
            delete currentDocument.isSectionTable;
            showDocumentEditor(currentDocument, restoredSelection);
        }
        else { alert('Ошибка открытия'); }
    } catch (e) { console.error('Open document error:', e); alert('Ошибка'); }
}

function showDocumentEditor(doc, restoredSelection = null) {
    console.log('📝 Opening document:', doc.title, doc.doc_type);
    const title = document.getElementById('documentTitle');
    if (!title) return;
    title.textContent = doc.title;
    currentDocument = doc;
    // Read-only mode for shared access.
    currentDocument.is_readonly = currentDocument.shared_permission === 'read';
    showModal('documentModal');
    setTimeout(() => {
        setRibbonTab('home');
        if (doc.doc_type === 'spreadsheet') { initHandsontable(doc, restoredSelection); }
        else { initTextEditor(doc); }
    }, 400);
}

function normalizeSheetPayload(sh) {
    const data = Array.isArray(sh?.data) ? sh.data : [];
    const rows = Math.max(sh?.rows || data.length || 20, 20);
    let cols = sh?.cols || 0;
    for (const row of data) if (Array.isArray(row)) cols = Math.max(cols, row.length);
    cols = Math.max(cols || 10, 10);
    const grid = Array.from({ length: rows }, (_, r) => {
        const row = Array.isArray(data[r]) ? data[r] : [];
        return Array.from({ length: cols }, (_, c) => String(row[c] ?? ''));
    });
    const cf = {};
    if (sh?.columnFilters && typeof sh.columnFilters === 'object') {
        Object.entries(sh.columnFilters).forEach(([k, v]) => {
            if (Array.isArray(v)) cf[k] = v.slice();
        });
    }
    return {
        name: sh?.name || 'Лист',
        rows: grid.length,
        cols: grid[0]?.length || cols,
        data: grid,
        styles: sh?.styles && typeof sh.styles === 'object' ? { ...sh.styles } : {},
        colWidths: Array.isArray(sh?.colWidths) ? sh.colWidths.slice() : [],
        rowHeights: Array.isArray(sh?.rowHeights) ? sh.rowHeights.slice() : [],
        columnFilters: cf,
    };
}

function migrateWorkbookPayload(raw) {
    if (!raw || typeof raw !== 'object') raw = {};
    if (Array.isArray(raw.sheets) && raw.sheets.length) {
        const sheets = raw.sheets.map(normalizeSheetPayload);
        const ai = Math.min(Math.max(0, raw.activeSheetIndex || 0), sheets.length - 1);
        return { version: 2, activeSheetIndex: ai, sheets };
    }
    return {
        version: 2,
        activeSheetIndex: 0,
        sheets: [normalizeSheetPayload(raw)],
    };
}

class CustomSheetEditor {
    constructor(container, payload, onDirty = null) {
        this.container = container;
        this.onDirty = onDirty;
        this.undoStack = [];
        this.redoStack = [];
        this.selection = { r1: 0, c1: 0, r2: 0, c2: 0 };
        this.isSelecting = false;
        this.fillDrag = null;
        this._onGlobalMouseUp = () => { this.isSelecting = false; };
        this._onFillEnd = () => {
            if (this.fillDrag) {
                this._applyFillDrag();
                this.fillDrag = null;
                this.render();
            }
        };
        window.addEventListener('mouseup', this._onGlobalMouseUp);
        window.addEventListener('blur', this._onGlobalMouseUp);
        window.addEventListener('mouseup', this._onFillEnd);

        this._onKeyDown = (e) => {
            const key = String(e.key || '').toLowerCase();
            const hasMod = e.ctrlKey || e.metaKey;
            const isUndo = hasMod && !e.shiftKey && key === 'z';
            const isRedo = (hasMod && key === 'y') || (hasMod && e.shiftKey && key === 'z');
            const isDeleteKey = key === 'backspace' || key === 'delete';
            const activeEl = document.activeElement;
            const modalOpen = documentModal?.classList?.contains('show');
            const insideEditor = !!(activeEl && this.container.contains(activeEl));
            const isTypingInput = !!(activeEl && (
                activeEl.tagName === 'INPUT' ||
                activeEl.tagName === 'TEXTAREA' ||
                activeEl.tagName === 'SELECT'
            ));
            const canHandleSheetHotkeys = modalOpen && (!isTypingInput || insideEditor);
            if (!canHandleSheetHotkeys) return;
            if (isUndo) {
                e.preventDefault();
                this.undo();
            } else if (isRedo) {
                e.preventDefault();
                this.redo();
            } else if (isDeleteKey) {
                const isEditingCell = !!this.editingCellKey;
                if (!isEditingCell && insideEditor) {
                    e.preventDefault();
                    this.clearSelectedCells();
                }
            }
        };
        document.addEventListener('keydown', this._onKeyDown, true);

        const norm = normalizeSheetPayload(payload || {});
        this.sheetName = norm.name;
        this.data = norm.data.map((row) => row.slice());
        this.styles = norm.styles;
        this.colWidths = norm.colWidths;
        this.rowHeights = norm.rowHeights;
        this.editingCellKey = null;
        this.formatPainter = { armed: false, sourceKey: null, sourceStyle: null };
        this.formulaHintEl = null;
        this.formulaFns = ['SUM', 'СУММ', 'AVERAGE', 'MIN', 'MAX'];
        this.columnFilters = {};
        Object.entries(norm.columnFilters).forEach(([k, v]) => { this.columnFilters[k] = v.slice(); });
        this.render();
    }

    _cellKey(r, c) { return `${r}:${c}`; }
    _colName(idx) {
        let n = idx;
        let s = '';
        while (n >= 0) { s = String.fromCharCode((n % 26) + 65) + s; n = Math.floor(n / 26) - 1; }
        return s;
    }
    _normalizeSelection() {
        const { r1, c1, r2, c2 } = this.selection;
        return { r1: Math.min(r1, r2), r2: Math.max(r1, r2), c1: Math.min(c1, c2), c2: Math.max(c1, c2) };
    }
    getSelectionAnchor() {
        const s = this._normalizeSelection();
        return { row: s.r1, col: s.c1 };
    }
    setSelectionAnchor(row, col) {
        const maxR = Math.max(0, this.data.length - 1);
        const maxC = Math.max(0, (this.data[0]?.length || 1) - 1);
        const r = Math.max(0, Math.min(Number(row) || 0, maxR));
        const c = Math.max(0, Math.min(Number(col) || 0, maxC));
        this._setSelection(r, c);
        const el = this.container.querySelector(`.sheet-cell[data-r="${r}"][data-c="${c}"]`);
        if (el) el.focus();
    }
    _pushUndo() {
        this._syncActiveCellFromDom();
        this.undoStack.push(JSON.stringify({
            data: this.data,
            styles: this.styles,
            columnFilters: this.columnFilters,
            colWidths: this.colWidths,
            rowHeights: this.rowHeights,
        }));
        if (this.undoStack.length > 50) this.undoStack.shift();
        this.redoStack = [];
        this._markDirty();
    }
    _markDirty() {
        if (typeof this.onDirty === 'function') this.onDirty();
    }
    _syncActiveCellFromDom() {
        const active = document.activeElement;
        if (!active || !this.container.contains(active) || !active.classList.contains('sheet-cell')) return;
        if (active.getAttribute('contenteditable') !== 'true') return;
        const r = Number(active.dataset.r);
        const c = Number(active.dataset.c);
        if (!Number.isFinite(r) || !Number.isFinite(c)) return;
        this.data[r][c] = active.textContent || '';
    }
    _applySnapshot(snapshot) {
        const parsed = JSON.parse(snapshot);
        this.data = parsed.data || this.data;
        this.styles = parsed.styles || {};
        this.colWidths = Array.isArray(parsed.colWidths) ? parsed.colWidths.slice() : this.colWidths;
        this.rowHeights = Array.isArray(parsed.rowHeights) ? parsed.rowHeights.slice() : this.rowHeights;
        this.columnFilters = {};
        if (parsed.columnFilters && typeof parsed.columnFilters === 'object') {
            Object.entries(parsed.columnFilters).forEach(([k, v]) => {
                if (Array.isArray(v)) this.columnFilters[k] = v.slice();
            });
        }
        this.render();
    }
    _isRowFiltered(r) {
        if (r === 0) return false;
        const f = this.columnFilters || {};
        for (const colStr of Object.keys(f)) {
            const allowed = f[colStr];
            if (!Array.isArray(allowed) || !allowed.length) continue;
            const c = Number(colStr);
            const v = String(this.data[r]?.[c] ?? '').trim();
            if (!allowed.includes(v)) return true;
        }
        return false;
    }
    _setSelection(r, c, keepAnchor = false) {
        if (!keepAnchor) { this.selection = { r1: r, c1: c, r2: r, c2: c }; }
        else { this.selection.r2 = r; this.selection.c2 = c; }
        this._paintSelection();
    }
    _forEachSelectedCell(cb) {
        const s = this._normalizeSelection();
        for (let r = s.r1; r <= s.r2; r++) for (let c = s.c1; c <= s.c2; c++) cb(r, c);
    }
    _paintSelection() {
        this.container.querySelectorAll('.sheet-cell').forEach(el => el.classList.remove('selected', 'active-row', 'active-col'));
        this.container.querySelectorAll('[data-col-header], [data-row-header]').forEach(el => {
            el.classList.remove('active-row', 'active-col');
        });
        const s = this._normalizeSelection();
        this._forEachSelectedCell((r, c) => {
            const el = this.container.querySelector(`[data-r="${r}"][data-c="${c}"]`);
            if (el) el.classList.add('selected');
        });
        const anchorRow = s.r1;
        const anchorCol = s.c1;
        this.container.querySelectorAll(`.sheet-cell[data-r="${anchorRow}"]`).forEach((el) => el.classList.add('active-row'));
        this.container.querySelectorAll(`.sheet-cell[data-c="${anchorCol}"]`).forEach((el) => el.classList.add('active-col'));
        const rowHeader = this.container.querySelector(`[data-row-header="${anchorRow}"]`);
        if (rowHeader) rowHeader.classList.add('active-row');
        const colHeader = this.container.querySelector(`[data-col-header="${anchorCol}"]`);
        if (colHeader) colHeader.classList.add('active-col');
        this._positionFillHandle();
        this._emitToolbarState();
    }
    _applyCellStyle(el, styleObj) {
        el.style.fontWeight = styleObj?.bold ? '700' : '400';
        el.style.fontStyle = styleObj?.italic ? 'italic' : 'normal';
        el.style.textAlign = styleObj?.align || 'left';
        el.style.verticalAlign = styleObj?.vAlign || 'middle';
        el.style.color = styleObj?.textColor || '#111111';
        el.style.backgroundColor = styleObj?.fillColor || '#ffffff';
        el.style.fontFamily = styleObj?.fontFamily || "'Segoe UI', system-ui, sans-serif";
        const fs = styleObj?.fontSize;
        el.style.fontSize = fs ? `${Number(fs)}px` : '14px';
    }
    _isFormulaValue(value) {
        return typeof value === 'string' && value.trim().startsWith('=');
    }
    _parseCellRef(ref) {
        const m = /^([A-Za-z]+)(\d+)$/i.exec(String(ref || '').trim());
        if (!m) return null;
        const letters = m[1].toUpperCase();
        const row = Number(m[2]) - 1;
        if (!Number.isFinite(row) || row < 0) return null;
        let col = 0;
        for (let i = 0; i < letters.length; i++) {
            col = col * 26 + (letters.charCodeAt(i) - 64);
        }
        col -= 1;
        if (col < 0) return null;
        return { row, col };
    }
    _toNumberSafe(value) {
        if (value === null || value === undefined) return null;
        const raw = String(value).trim().replace(/\s+/g, '').replace(',', '.');
        if (!raw) return null;
        const n = Number(raw);
        return Number.isFinite(n) ? n : null;
    }
    _formatComputedNumber(n) {
        if (!Number.isFinite(n)) return '#ERROR!';
        if (Math.abs(n - Math.round(n)) < 1e-10) return String(Math.round(n));
        return String(Number(n.toFixed(10)));
    }
    _evaluateCell(r, c, memo = new Map(), visiting = new Set()) {
        const key = this._cellKey(r, c);
        if (memo.has(key)) return memo.get(key);
        if (visiting.has(key)) return { text: '#CYCLE!', numeric: null };
        visiting.add(key);
        const raw = String(this.data[r]?.[c] ?? '');
        let result = { text: raw, numeric: this._toNumberSafe(raw) };
        if (this._isFormulaValue(raw)) {
            result = this._evaluateFormula(raw, memo, visiting);
        }
        visiting.delete(key);
        memo.set(key, result);
        return result;
    }
    _collectFormulaNumbers(arg, memo, visiting) {
        const token = String(arg || '').trim();
        if (!token) return [];
        const rangeMatch = /^([A-Za-z]+\d+)\s*:\s*([A-Za-z]+\d+)$/i.exec(token);
        if (rangeMatch) {
            const from = this._parseCellRef(rangeMatch[1]);
            const to = this._parseCellRef(rangeMatch[2]);
            if (!from || !to) return [];
            const r1 = Math.min(from.row, to.row);
            const r2 = Math.max(from.row, to.row);
            const c1 = Math.min(from.col, to.col);
            const c2 = Math.max(from.col, to.col);
            const out = [];
            for (let r = r1; r <= r2; r++) {
                for (let c = c1; c <= c2; c++) {
                    const evaluated = this._evaluateCell(r, c, memo, visiting);
                    if (evaluated?.numeric !== null && evaluated?.numeric !== undefined) out.push(evaluated.numeric);
                }
            }
            return out;
        }
        const ref = this._parseCellRef(token);
        if (ref) {
            const evaluated = this._evaluateCell(ref.row, ref.col, memo, visiting);
            return evaluated?.numeric !== null && evaluated?.numeric !== undefined ? [evaluated.numeric] : [];
        }
        if (/[+\-*/()]/.test(token)) {
            const exprVal = this._evaluateExpression(token, memo, visiting);
            return exprVal === null ? [] : [exprVal];
        }
        const n = this._toNumberSafe(token);
        return n === null ? [] : [n];
    }
    _evaluateExpression(expression, memo, visiting) {
        let expr = String(expression || '').trim();
        if (!expr) return null;
        const refs = expr.match(/[A-Za-z]+\d+/g) || [];
        refs.forEach((refToken) => {
            const ref = this._parseCellRef(refToken);
            const val = ref ? (this._evaluateCell(ref.row, ref.col, memo, visiting)?.numeric ?? 0) : 0;
            expr = expr.replace(new RegExp(`\\b${refToken}\\b`, 'g'), String(val));
        });
        if (!/^[\d+\-*/().,\s]+$/.test(expr)) return null;
        expr = expr.replace(/,/g, '.');
        try {
            const out = Function(`"use strict"; return (${expr});`)();
            return Number.isFinite(out) ? Number(out) : null;
        } catch (_) {
            return null;
        }
    }
    _evaluateFormula(raw, memo, visiting) {
        const match = /^\s*=\s*([A-Za-zА-Яа-яЁё]+)\s*\((.*)\)\s*$/.exec(String(raw || ''));
        if (!match) {
            const direct = String(raw || '').replace(/^\s*=\s*/, '');
            const computed = this._evaluateExpression(direct, memo, visiting);
            if (computed === null) return { text: '#ERROR!', numeric: null };
            return { text: this._formatComputedNumber(computed), numeric: computed };
        }
        const fn = match[1].trim().toUpperCase();
        const argsText = match[2] || '';
        const args = argsText.split(/[;,]/).map((p) => p.trim()).filter(Boolean);
        const nums = [];
        args.forEach((arg) => {
            this._collectFormulaNumbers(arg, memo, visiting).forEach((n) => nums.push(n));
        });
        const aliases = {
            SUM: 'SUM',
            'СУММ': 'SUM',
            AVERAGE: 'AVERAGE',
            MIN: 'MIN',
            MAX: 'MAX',
        };
        const normalized = aliases[fn];
        if (!normalized) return { text: '#NAME?', numeric: null };
        if (!nums.length) return { text: '0', numeric: 0 };
        let value = 0;
        if (normalized === 'SUM') value = nums.reduce((acc, n) => acc + n, 0);
        if (normalized === 'AVERAGE') value = nums.reduce((acc, n) => acc + n, 0) / nums.length;
        if (normalized === 'MIN') value = Math.min(...nums);
        if (normalized === 'MAX') value = Math.max(...nums);
        if (!Number.isFinite(value)) return { text: '#ERROR!', numeric: null };
        return { text: this._formatComputedNumber(value), numeric: value };
    }
    _getDisplayedValue(r, c, memo = new Map()) {
        const value = this._evaluateCell(r, c, memo, new Set());
        return String(value?.text ?? '');
    }
    _styleFromObject(rawStyle) {
        const src = rawStyle && typeof rawStyle === 'object' ? rawStyle : {};
        const next = {};
        if (src.bold) next.bold = true;
        if (src.italic) next.italic = true;
        if (src.align) next.align = src.align;
        if (src.vAlign) next.vAlign = src.vAlign;
        if (src.textColor) next.textColor = src.textColor;
        if (src.fillColor) next.fillColor = src.fillColor;
        if (src.fontFamily) next.fontFamily = src.fontFamily;
        if (src.fontSize) next.fontSize = src.fontSize;
        return next;
    }
    _emitToolbarState() {
        const state = this.getSelectionStyleState();
        document.dispatchEvent(new CustomEvent('sheet:toolbar-state', { detail: state }));
    }
    getSelectionStyleState() {
        const s = this._normalizeSelection();
        const key = this._cellKey(s.r1, s.c1);
        const style = this.styles[key] || {};
        return {
            bold: !!style.bold,
            italic: !!style.italic,
            align: style.align || 'left',
            vAlign: style.vAlign || 'middle',
            formatPainterArmed: !!this.formatPainter?.armed,
        };
    }
    armFormatPainter() {
        const s = this._normalizeSelection();
        const key = this._cellKey(s.r1, s.c1);
        this.formatPainter = {
            armed: true,
            sourceKey: key,
            sourceStyle: this._styleFromObject(this.styles[key] || {}),
        };
        this._emitToolbarState();
    }
    clearFormatPainter() {
        this.formatPainter = { armed: false, sourceKey: null, sourceStyle: null };
        this._emitToolbarState();
    }
    _applyFormatPainterToCell(r, c) {
        if (!this.formatPainter?.armed) return false;
        const key = this._cellKey(r, c);
        this._pushUndo();
        const copy = this._styleFromObject(this.formatPainter.sourceStyle || {});
        if (Object.keys(copy).length) this.styles[key] = copy;
        else delete this.styles[key];
        this.clearFormatPainter();
        this.render();
        return true;
    }
    _startEditCell(cell, initialText = null, selectAll = false) {
        if (!cell) return;
        if (currentDocument?.is_readonly) return;
        const r = Number(cell.dataset.r);
        const c = Number(cell.dataset.c);
        if (!Number.isFinite(r) || !Number.isFinite(c)) return;
        const key = this._cellKey(r, c);
        const raw = String(this.data[r]?.[c] ?? '');
        this.editingCellKey = key;
        cell.dataset.originalValue = raw;
        cell.setAttribute('contenteditable', 'true');
        cell.classList.add('editing');
        cell.textContent = initialText !== null ? String(initialText) : raw;
        cell.focus();
        const sel = window.getSelection();
        if (sel) {
            sel.removeAllRanges();
            const range = document.createRange();
            range.selectNodeContents(cell);
            if (!selectAll) range.collapse(false);
            sel.addRange(range);
        }
        this._showFormulaHints(cell);
    }
    _commitEditCell(cell, { cancel = false } = {}) {
        if (!cell) return;
        const r = Number(cell.dataset.r);
        const c = Number(cell.dataset.c);
        if (!Number.isFinite(r) || !Number.isFinite(c)) return;
        const key = this._cellKey(r, c);
        const before = String(cell.dataset.originalValue ?? this.data[r][c] ?? '');
        const after = cancel ? before : String(cell.textContent || '');
        cell.classList.remove('editing');
        cell.setAttribute('contenteditable', 'false');
        delete cell.dataset.originalValue;
        this.editingCellKey = null;
        if (after !== before) {
            this._pushUndo();
            this.data[r][c] = after;
            this._markDirty();
            this._hideFormulaHints();
            this.render();
            return;
        }
        this.data[r][c] = before;
        const display = this._getDisplayedValue(r, c);
        cell.textContent = display;
        this._hideFormulaHints();
    }
    isEditing() {
        if (this.editingCellKey) return true;
        const active = document.activeElement;
        return !!(active && this.container.contains(active) && active.getAttribute('contenteditable') === 'true');
    }
    clearSelectedCells() {
        const s = this._normalizeSelection();
        let changed = false;
        for (let r = s.r1; r <= s.r2; r++) {
            for (let c = s.c1; c <= s.c2; c++) {
                if (String(this.data[r][c] ?? '') !== '') {
                    changed = true;
                    break;
                }
            }
            if (changed) break;
        }
        if (!changed) return;
        this._pushUndo();
        for (let r = s.r1; r <= s.r2; r++) {
            for (let c = s.c1; c <= s.c2; c++) {
                this.data[r][c] = '';
            }
        }
        this.render();
    }
    _getEditingCellEl() {
        if (!this.editingCellKey) return null;
        const [r, c] = this.editingCellKey.split(':').map(Number);
        if (!Number.isFinite(r) || !Number.isFinite(c)) return null;
        return this.container.querySelector(`.sheet-cell[data-r="${r}"][data-c="${c}"]`);
    }
    _hideFormulaHints() {
        if (this.formulaHintEl) {
            this.formulaHintEl.remove();
            this.formulaHintEl = null;
        }
    }
    _insertCellRefIntoFormula(refText) {
        const editingEl = this._getEditingCellEl();
        if (!editingEl) return false;
        const raw = String(editingEl.textContent || '');
        if (!raw.trim().startsWith('=')) return false;
        editingEl.textContent = `${raw}${refText}`;
        editingEl.focus();
        const sel = window.getSelection();
        if (sel) {
            sel.removeAllRanges();
            const range = document.createRange();
            range.selectNodeContents(editingEl);
            range.collapse(false);
            sel.addRange(range);
        }
        this._showFormulaHints(editingEl);
        return true;
    }
    _showFormulaHints(cell) {
        if (!cell || cell.getAttribute('contenteditable') !== 'true') {
            this._hideFormulaHints();
            return;
        }
        const text = String(cell.textContent || '');
        if (!text.trim().startsWith('=')) {
            this._hideFormulaHints();
            return;
        }
        const tokenMatch = /^\s*=\s*([A-Za-zА-Яа-яЁё]*)/.exec(text);
        const typed = (tokenMatch?.[1] || '').toUpperCase();
        const variants = this.formulaFns.filter((fn) => fn.toUpperCase().startsWith(typed)).slice(0, 5);
        if (!variants.length) {
            this._hideFormulaHints();
            return;
        }
        if (!this.formulaHintEl) {
            this.formulaHintEl = document.createElement('div');
            this.formulaHintEl.className = 'sheet-formula-hint';
            document.body.appendChild(this.formulaHintEl);
        }
        const hints = {
            SUM: 'Сумма диапазона: SUM(A1:A10)',
            'СУММ': 'Сумма диапазона: СУММ(A1:A10)',
            AVERAGE: 'Среднее значение: AVERAGE(A1:A10)',
            MIN: 'Минимум по диапазону: MIN(A1:A10)',
            MAX: 'Максимум по диапазону: MAX(A1:A10)',
        };
        this.formulaHintEl.innerHTML = variants.map((fn) => `<button type="button" class="sheet-formula-item" data-fn="${fn}">${fn}<span>${hints[fn]}</span></button>`).join('');
        this.formulaHintEl.querySelectorAll('.sheet-formula-item').forEach((btn) => {
            btn.addEventListener('mousedown', (e) => e.preventDefault());
            btn.addEventListener('click', () => {
                const fn = btn.dataset.fn || 'SUM';
                cell.textContent = `=${fn}()`;
                cell.focus();
                const sel = window.getSelection();
                if (sel) {
                    sel.removeAllRanges();
                    const range = document.createRange();
                    const textNode = cell.firstChild;
                    const pos = Math.max(0, String(cell.textContent).length - 1);
                    if (textNode) range.setStart(textNode, pos);
                    else range.selectNodeContents(cell);
                    range.collapse(true);
                    sel.addRange(range);
                }
                this._showFormulaHints(cell);
            });
        });
        const rect = cell.getBoundingClientRect();
        this.formulaHintEl.style.left = `${Math.max(12, rect.left)}px`;
        this.formulaHintEl.style.top = `${Math.max(12, rect.bottom + 6)}px`;
    }

    render() {
        this._hideFormulaHints();
        const rows = this.data.length;
        const cols = this.data[0]?.length || 0;
        const displayMemo = new Map();
        let html = '<div class="sheet-wrap"><table class="sheet-table"><thead><tr><th class="corner"></th>';
        for (let c = 0; c < cols; c++) {
            const w = this.colWidths[c] || 90;
            const hasF = Array.isArray(this.columnFilters[String(c)]) && this.columnFilters[String(c)].length > 0;
            const filtMark = hasF ? ' <span class="sheet-filter-dot" title="Активен фильтр">🔽</span>' : '';
            html += `<th data-col-header="${c}" style="width:${w}px;min-width:${w}px;max-width:${w}px;" title="Двойной клик — фильтр столбца">${this._colName(c)}${filtMark}<span class="col-resizer" data-col-resizer="${c}"></span></th>`;
        }
        html += '</tr></thead><tbody>';
        for (let r = 0; r < rows; r++) {
            const h = this.rowHeights[r] || 28;
            const hid = this._isRowFiltered(r) ? ' filter-hidden' : '';
            html += `<tr class="sheet-row${hid}" style="height:${h}px;"><th data-row-header="${r}" style="height:${h}px;min-height:${h}px;max-height:${h}px;">${r + 1}<span class="row-resizer" data-row-resizer="${r}"></span></th>`;
            for (let c = 0; c < cols; c++) {
                const w = this.colWidths[c] || 90;
                const shown = this._getDisplayedValue(r, c, displayMemo);
                html += `<td class="sheet-cell" contenteditable="false" data-r="${r}" data-c="${c}" style="width:${w}px;min-width:${w}px;max-width:${w}px;height:${h}px;">${escapeHtml(shown)}</td>`;
            }
            html += '</tr>';
        }
        html += '</tbody></table></div>';
        this.container.innerHTML = html;
        this.wrapEl = this.container.querySelector('.sheet-wrap');

        this.container.querySelectorAll('.sheet-cell').forEach((cell) => {
            const r = Number(cell.dataset.r); const c = Number(cell.dataset.c);
            const styleObj = this.styles[this._cellKey(r, c)] || {};
            this._applyCellStyle(cell, styleObj);

            cell.addEventListener('focus', () => this._setSelection(r, c));
            cell.addEventListener('click', () => {
                this._setSelection(r, c);
                this._emitToolbarState();
            });
            cell.addEventListener('mousedown', (e) => {
                if (e.button !== 0) return;
                if (this.editingCellKey && this.editingCellKey !== this._cellKey(r, c)) {
                    const ref = `${this._colName(c)}${r + 1}`;
                    if (this._insertCellRefIntoFormula(ref)) {
                        e.preventDefault();
                        e.stopPropagation();
                        return;
                    }
                }
                if (this._applyFormatPainterToCell(r, c)) return;
                this.isSelecting = true;
                this._setSelection(r, c);
                cell.focus();
            });
            cell.addEventListener('dblclick', () => {
                this._setSelection(r, c);
                this._startEditCell(cell);
            });
            cell.addEventListener('keydown', (e) => {
                const key = String(e.key || '');
                const isEditing = cell.getAttribute('contenteditable') === 'true';
                if (!isEditing) {
                    if (key === 'Enter' || key === 'F2') {
                        e.preventDefault();
                        this._startEditCell(cell);
                        return;
                    }
                    if (key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
                        e.preventDefault();
                        this._startEditCell(cell, key);
                        return;
                    }
                    if (key === 'Backspace' || key === 'Delete') {
                        e.preventDefault();
                        this._startEditCell(cell, '');
                    }
                    return;
                }
                if (key === 'Escape') {
                    e.preventDefault();
                    this._commitEditCell(cell, { cancel: true });
                    return;
                }
                if (key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this._commitEditCell(cell);
                    const nextR = Math.min(this.data.length - 1, r + 1);
                    this._setSelection(nextR, c);
                    const next = this.container.querySelector(`.sheet-cell[data-r="${nextR}"][data-c="${c}"]`);
                    if (next) next.focus();
                }
            });
            cell.addEventListener('input', () => {
                if (cell.getAttribute('contenteditable') === 'true') {
                    this._showFormulaHints(cell);
                }
            });
            cell.addEventListener('paste', (e) => {
                // Excel-копирование: tab-separated + newline-separated.
                // Перекладываем содержимое по ячейкам, начиная с текущего выделения.
                try {
                    const dt = e.clipboardData;
                    if (!dt) return;
                    const text = dt.getData('text/plain') || '';
                    const html = dt.getData('text/html') || '';
                    if (!text && !html) return;

                    e.preventDefault();
                    this._pushUndo();

                    const start = this._normalizeSelection();
                    const startR = start.r1;
                    const startC = start.c1;

                    // 1) Values: parse text/plain
                    const lines = text.replace(/\r/g, '').split('\n');
                    let matrix = lines.map((ln) => ln.split('\t'));
                    // Убираем пустые хвостовые строки (часто Excel добавляет trailing \n)
                    while (matrix.length > 1) {
                        const last = matrix[matrix.length - 1];
                        const allEmpty = !last || last.every((v) => String(v ?? '').trim() === '');
                        if (!allEmpty) break;
                        matrix.pop();
                    }
                    const maxCols = matrix.reduce((m, row) => Math.max(m, row.length), 0);
                    const neededRows = startR + matrix.length;
                    const neededCols = startC + maxCols;

                    // Ensure grid size
                    while (this.data.length < neededRows) {
                        const rowLen = this.data[0]?.length || neededCols;
                        this.data.push(Array.from({ length: rowLen }, () => ''));
                    }
                    if (this.data[0] && this.data[0].length < neededCols) {
                        const add = neededCols - this.data[0].length;
                        this.data.forEach((row) => {
                            for (let i = 0; i < add; i++) row.push('');
                        });
                    }

                    // Apply values
                    for (let rr = 0; rr < matrix.length; rr++) {
                        for (let cc = 0; cc < maxCols; cc++) {
                            const val = (matrix[rr] && matrix[rr][cc] !== undefined) ? String(matrix[rr][cc] ?? '') : '';
                            this.data[startR + rr][startC + cc] = val;
                        }
                    }

                    // 2) Styles: try parse HTML table (best-effort)
                    if (html && html.toLowerCase().includes('<table')) {
                        const doc = new DOMParser().parseFromString(html, 'text/html');
                        const tbl = doc.querySelector('table');
                        if (tbl) {
                            const trList = Array.from(tbl.querySelectorAll('tr'));
                            for (let rr = 0; rr < trList.length; rr++) {
                                const cells = Array.from(trList[rr].querySelectorAll('td,th'));
                                for (let cc = 0; cc < cells.length; cc++) {
                                    const el = cells[cc];
                                    const styleText = el.getAttribute('style') || '';
                                    if (!styleText) continue;

                                    const styleMap = {};
                                    styleText.split(';').forEach((p) => {
                                        const idx = p.indexOf(':');
                                        if (idx === -1) return;
                                        const key = p.slice(0, idx).trim().toLowerCase();
                                        const val = p.slice(idx + 1).trim();
                                        if (key && val) styleMap[key] = val;
                                    });

                                    const st = {};
                                    const fw = styleMap['font-weight'];
                                    if (fw && (fw.toLowerCase() === 'bold' || Number(fw) >= 600)) st.bold = true;
                                    const fs = styleMap['font-style'];
                                    if (fs && fs.toLowerCase() === 'italic') st.italic = true;
                                    const ta = styleMap['text-align'];
                                    if (ta) {
                                        const low = ta.toLowerCase();
                                        if (low.includes('center')) st.align = 'center';
                                        else if (low.includes('right')) st.align = 'right';
                                        else st.align = 'left';
                                    }
                                    const va = styleMap['vertical-align'];
                                    if (va) {
                                        const low = va.toLowerCase();
                                        if (low.includes('top')) st.vAlign = 'top';
                                        else if (low.includes('bottom')) st.vAlign = 'bottom';
                                        else st.vAlign = 'middle';
                                    }
                                    const color = styleMap['color'];
                                    if (color) st.textColor = color;
                                    const bg = styleMap['background-color'] || styleMap['background'];
                                    if (bg) st.fillColor = bg;
                                    const ff = styleMap['font-family'];
                                    if (ff) st.fontFamily = ff;
                                    const size = styleMap['font-size'];
                                    if (size) {
                                        const n = Number(String(size).replace('px', '').trim());
                                        if (Number.isFinite(n)) st.fontSize = n;
                                    }
                                    if (Object.keys(st).length) {
                                        this.styles[this._cellKey(startR + rr, startC + cc)] = st;
                                    }
                                }
                            }
                        }
                    }

                    this.selection = {
                        r1: startR,
                        c1: startC,
                        r2: startR + matrix.length - 1,
                        c2: startC + maxCols - 1,
                    };
                    this.render();
                } catch (err) {
                    console.error('❌ Paste error:', err);
                }
            });
            cell.addEventListener('mouseenter', (e) => {
                if (this.fillDrag) {
                    this.fillDrag.target = { r, c };
                    this._paintFillTarget();
                    return;
                }
                if (this.isSelecting && (e.buttons & 1)) this._setSelection(r, c, true);
            });
            cell.addEventListener('blur', () => {
                if (cell.getAttribute('contenteditable') === 'true') {
                    this._commitEditCell(cell);
                }
                this._hideFormulaHints();
            });
        });
        this._bindResizers();
        this._bindColumnHeaderFilters();
        this._bindHeaderSelection();
        this._ensureFillHandle();
        this._paintSelection();
        applyLivePresence(currentPresenceItems);
    }
    _bindHeaderSelection() {
        // Click on column header: select whole column. Click on row header: select whole row.
        this.container.querySelectorAll('[data-col-header]').forEach((th) => {
            th.addEventListener('click', (e) => {
                if (e.target.closest('.col-resizer')) return;
                const c = Number(th.dataset.colHeader);
                if (!Number.isFinite(c)) return;
                this.isSelecting = true;
                this.selection = { r1: 0, c1: c, r2: this.data.length - 1, c2: c };
                this._paintSelection();
            });
        });
        this.container.querySelectorAll('[data-row-header]').forEach((th) => {
            th.addEventListener('click', (e) => {
                if (e.target.closest('.row-resizer')) return;
                const r = Number(th.dataset.rowHeader);
                if (!Number.isFinite(r)) return;
                this.isSelecting = true;
                this.selection = { r1: r, c1: 0, r2: r, c2: (this.data[0]?.length || 1) - 1 };
                this._paintSelection();
            });
        });
    }
    _bindColumnHeaderFilters() {
        this.container.querySelectorAll('[data-col-header]').forEach((th) => {
            th.addEventListener('dblclick', (e) => {
                if (e.target.closest('.col-resizer')) return;
                const col = Number(th.dataset.colHeader);
                if (Number.isFinite(col)) this.openColumnFilter(col);
            });
        });
    }
    openFilterForSelection() {
        const s = this._normalizeSelection();
        this.openColumnFilter(s.c1);
    }
    openColumnFilter(colIdx) {
        const uniques = new Set();
        for (let r = 1; r < this.data.length; r++) {
            uniques.add(String(this.data[r][colIdx] ?? '').trim());
        }
        const allVals = [...uniques].sort((a, b) => a.localeCompare(b, 'ru'));
        const key = String(colIdx);
        const prev = this.columnFilters[key];
        const overlay = document.createElement('div');
        overlay.className = 'sheet-filter-overlay';
        overlay.innerHTML = `
            <div class="sheet-filter-dialog">
                <h4>Фильтр: столбец ${this._colName(colIdx)}</h4>
                <p class="sheet-filter-hint">Как в Excel: снимите галочки со значений, которые нужно скрыть.</p>
                <div class="sheet-filter-list" id="sheetFilterList"></div>
                <div class="sheet-filter-actions">
                    <button type="button" class="btn btn-secondary btn-sm" id="sheetFilterAll">Выделить все</button>
                    <button type="button" class="btn btn-secondary btn-sm" id="sheetFilterNone">Убрать галочки</button>
                    <button type="button" class="btn btn-secondary btn-sm" id="sheetFilterClear">Сбросить фильтр</button>
                    <button type="button" class="btn btn-primary btn-sm" id="sheetFilterOk">Применить</button>
                </div>
            </div>`;
        document.body.appendChild(overlay);
        const listEl = overlay.querySelector('#sheetFilterList');
        const selectedSet = prev && prev.length ? new Set(prev) : new Set(allVals);
        allVals.forEach((val) => {
            const row = document.createElement('label');
            row.className = 'sheet-filter-item';
            row.setAttribute('data-val', val);
            const cb = document.createElement('input');
            cb.type = 'checkbox';
            cb.checked = selectedSet.has(val);
            const display = val === '' ? '(пусто)' : val;
            row.appendChild(cb);
            row.appendChild(document.createTextNode(` ${display}`));
            listEl.appendChild(row);
        });
        const close = () => overlay.remove();
        overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
        overlay.querySelector('#sheetFilterAll').onclick = () => {
            listEl.querySelectorAll('input[type=checkbox]').forEach((c) => { c.checked = true; });
        };
        overlay.querySelector('#sheetFilterNone').onclick = () => {
            listEl.querySelectorAll('input[type=checkbox]').forEach((c) => { c.checked = false; });
        };
        overlay.querySelector('#sheetFilterClear').onclick = () => {
            this._pushUndo();
            delete this.columnFilters[key];
            close();
            this.render();
        };
        overlay.querySelector('#sheetFilterOk').onclick = () => {
            const allowed = [];
            listEl.querySelectorAll('label.sheet-filter-item').forEach((lab) => {
                const cb = lab.querySelector('input');
                if (cb?.checked) allowed.push(lab.getAttribute('data-val') ?? '');
            });
            this._pushUndo();
            if (!allowed.length || allowed.length === allVals.length) delete this.columnFilters[key];
            else this.columnFilters[key] = allowed;
            close();
            this.render();
        };
    }
    clearAllColumnFilters() {
        this._pushUndo();
        this.columnFilters = {};
        this.render();
    }
    _bindResizers() {
        this.container.querySelectorAll('[data-col-resizer]').forEach((el) => {
            el.addEventListener('mousedown', (e) => {
                e.preventDefault();
                e.stopPropagation();
                this._pushUndo();
                const col = Number(el.dataset.colResizer);
                const startX = e.clientX;
                const startW = this.colWidths[col] || 90;
                const onMove = (ev) => {
                    const w = Math.max(50, startW + (ev.clientX - startX));
                    this.colWidths[col] = w;
                    this.render();
                };
                const onUp = () => {
                    window.removeEventListener('mousemove', onMove);
                    window.removeEventListener('mouseup', onUp);
                };
                window.addEventListener('mousemove', onMove);
                window.addEventListener('mouseup', onUp);
            });
        });
        this.container.querySelectorAll('[data-row-resizer]').forEach((el) => {
            el.addEventListener('mousedown', (e) => {
                e.preventDefault();
                e.stopPropagation();
                this._pushUndo();
                const row = Number(el.dataset.rowResizer);
                const startY = e.clientY;
                const startH = this.rowHeights[row] || 28;
                const onMove = (ev) => {
                    const h = Math.max(22, startH + (ev.clientY - startY));
                    this.rowHeights[row] = h;
                    this.render();
                };
                const onUp = () => {
                    window.removeEventListener('mousemove', onMove);
                    window.removeEventListener('mouseup', onUp);
                };
                window.addEventListener('mousemove', onMove);
                window.addEventListener('mouseup', onUp);
            });
        });
    }
    _ensureFillHandle() {
        if (!this.wrapEl) return;
        const handle = document.createElement('div');
        handle.className = 'sheet-fill-handle';
        handle.title = 'Протяните для автозаполнения';
        handle.addEventListener('mousedown', (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.fillDrag = { base: this._normalizeSelection(), target: null };
        });
        this.wrapEl.appendChild(handle);
        this.fillHandle = handle;
    }
    _positionFillHandle() {
        if (!this.fillHandle || !this.wrapEl) return;
        const s = this._normalizeSelection();
        const endCell = this.container.querySelector(`[data-r="${s.r2}"][data-c="${s.c2}"]`);
        if (!endCell) { this.fillHandle.style.display = 'none'; return; }
        this.fillHandle.style.display = 'block';
        const r1 = this.wrapEl.getBoundingClientRect();
        const r2 = endCell.getBoundingClientRect();
        const left = Math.max(0, r2.right - r1.left + this.wrapEl.scrollLeft - 6);
        const top = Math.max(0, r2.bottom - r1.top + this.wrapEl.scrollTop - 6);
        this.fillHandle.style.left = `${left}px`;
        this.fillHandle.style.top = `${top}px`;
    }
    _paintFillTarget() {
        this.container.querySelectorAll('.sheet-cell').forEach(el => el.classList.remove('fill-target'));
        if (!this.fillDrag?.target) return;
        const b = this.fillDrag.base;
        const t = this.fillDrag.target;
        const area = {
            r1: Math.min(b.r1, t.r),
            r2: Math.max(b.r2, t.r),
            c1: Math.min(b.c1, t.c),
            c2: Math.max(b.c2, t.c),
        };
        for (let r = area.r1; r <= area.r2; r++) for (let c = area.c1; c <= area.c2; c++) {
            if (r >= b.r1 && r <= b.r2 && c >= b.c1 && c <= b.c2) continue;
            const el = this.container.querySelector(`[data-r="${r}"][data-c="${c}"]`);
            if (el) el.classList.add('fill-target');
        }
    }
    _applyFillDrag() {
        if (!this.fillDrag?.target) return;
        this._pushUndo();
        const b = this.fillDrag.base;
        const t = this.fillDrag.target;
        const area = {
            r1: Math.min(b.r1, t.r),
            r2: Math.max(b.r2, t.r),
            c1: Math.min(b.c1, t.c),
            c2: Math.max(b.c2, t.c),
        };
        const baseRows = b.r2 - b.r1 + 1;
        const baseCols = b.c2 - b.c1 + 1;
        const oneCol = baseCols === 1;
        const oneRow = baseRows === 1;
        let step = null;
        if (oneCol && baseRows >= 2) {
            const a = Number(this.data[b.r1][b.c1]); const z = Number(this.data[b.r1 + 1][b.c1]);
            if (Number.isFinite(a) && Number.isFinite(z)) step = z - a;
        }
        if (oneRow && baseCols >= 2) {
            const a = Number(this.data[b.r1][b.c1]); const z = Number(this.data[b.r1][b.c1 + 1]);
            if (Number.isFinite(a) && Number.isFinite(z)) step = z - a;
        }
        for (let r = area.r1; r <= area.r2; r++) for (let c = area.c1; c <= area.c2; c++) {
            if (r >= b.r1 && r <= b.r2 && c >= b.c1 && c <= b.c2) continue;
            let sr = b.r1 + ((r - b.r1) % baseRows + baseRows) % baseRows;
            let sc = b.c1 + ((c - b.c1) % baseCols + baseCols) % baseCols;
            let val = this.data[sr][sc];
            if (step !== null && oneCol) {
                const idx = r - b.r1;
                const start = Number(this.data[b.r1][b.c1]);
                if (Number.isFinite(start)) val = String(start + step * idx);
            } else if (step !== null && oneRow) {
                const idx = c - b.c1;
                const start = Number(this.data[b.r1][b.c1]);
                if (Number.isFinite(start)) val = String(start + step * idx);
            }
            this.data[r][c] = val;
            const srcStyle = this.styles[this._cellKey(sr, sc)];
            if (srcStyle) this.styles[this._cellKey(r, c)] = { ...srcStyle };
        }
    }

    focus() {
        const s = this._normalizeSelection();
        const el = this.container.querySelector(`[data-r="${s.r1}"][data-c="${s.c1}"]`);
        if (el) el.focus();
    }
    destroy() {
        this._hideFormulaHints();
        window.removeEventListener('mouseup', this._onGlobalMouseUp);
        window.removeEventListener('blur', this._onGlobalMouseUp);
        document.removeEventListener('keydown', this._onKeyDown, true);
        if (this._onFillEnd) {
            window.removeEventListener('mouseup', this._onFillEnd);
            this._onFillEnd = null;
        }
        this.container.innerHTML = '';
    }
    exportSheet() {
        this._syncActiveCellFromDom();
        const cf = {};
        Object.entries(this.columnFilters || {}).forEach(([k, v]) => {
            if (Array.isArray(v) && v.length) cf[k] = v.slice();
        });
        return {
            name: this.sheetName || 'Лист',
            rows: this.data.length,
            cols: this.data[0]?.length || 0,
            data: this.data.map((row) => row.slice()),
            styles: { ...this.styles },
            colWidths: this.colWidths.slice(),
            rowHeights: this.rowHeights.slice(),
            columnFilters: cf,
        };
    }
    export() {
        return this.exportSheet();
    }

    toggleBold() {
        this._pushUndo();
        this._forEachSelectedCell((r, c) => {
            const k = this._cellKey(r, c);
            const s = { ...(this.styles[k] || {}) };
            s.bold = !s.bold;
            this.styles[k] = s;
        });
        this.render();
    }
    toggleItalic() {
        this._pushUndo();
        this._forEachSelectedCell((r, c) => {
            const k = this._cellKey(r, c);
            const s = { ...(this.styles[k] || {}) };
            s.italic = !s.italic;
            this.styles[k] = s;
        });
        this.render();
    }
    setAlign(align) {
        this._pushUndo();
        this._forEachSelectedCell((r, c) => {
            const k = this._cellKey(r, c);
            const s = { ...(this.styles[k] || {}) };
            s.align = align;
            this.styles[k] = s;
        });
        this.render();
    }
    setVAlign(vAlign) {
        this._pushUndo();
        this._forEachSelectedCell((r, c) => {
            const k = this._cellKey(r, c);
            const s = { ...(this.styles[k] || {}) };
            s.vAlign = vAlign;
            this.styles[k] = s;
        });
        this.render();
    }
    setTextColor(color) {
        this._pushUndo();
        this._forEachSelectedCell((r, c) => {
            const k = this._cellKey(r, c);
            const s = { ...(this.styles[k] || {}) };
            s.textColor = color;
            this.styles[k] = s;
        });
        this.render();
    }
    setFillColor(color) {
        this._pushUndo();
        this._forEachSelectedCell((r, c) => {
            const k = this._cellKey(r, c);
            const s = { ...(this.styles[k] || {}) };
            s.fillColor = color;
            this.styles[k] = s;
        });
        this.render();
    }
    setFontFamily(family) {
        if (!family) return;
        this._pushUndo();
        this._forEachSelectedCell((r, c) => {
            const k = this._cellKey(r, c);
            const s = { ...(this.styles[k] || {}) };
            s.fontFamily = family;
            this.styles[k] = s;
        });
        this.render();
    }
    setFontSize(px) {
        const n = Number(px);
        if (!Number.isFinite(n) || n < 8 || n > 72) return;
        this._pushUndo();
        this._forEachSelectedCell((r, c) => {
            const k = this._cellKey(r, c);
            const s = { ...(this.styles[k] || {}) };
            s.fontSize = n;
            this.styles[k] = s;
        });
        this.render();
    }
    insertRowBelow() {
        this._pushUndo();
        const s = this._normalizeSelection();
        const idx = s.r2 + 1;
        this.data.splice(idx, 0, Array.from({ length: this.data[0].length }, () => ''));
        const shifted = {};
        Object.entries(this.styles).forEach(([k, v]) => {
            const [r, c] = k.split(':').map(Number);
            shifted[`${r >= idx ? r + 1 : r}:${c}`] = v;
        });
        this.styles = shifted;
        this.render();
    }
    insertColRight() {
        this._pushUndo();
        const s = this._normalizeSelection();
        const idx = s.c2 + 1;
        this.data.forEach(row => row.splice(idx, 0, ''));
        const shifted = {};
        Object.entries(this.styles).forEach(([k, v]) => {
            const [r, c] = k.split(':').map(Number);
            shifted[`${r}:${c >= idx ? c + 1 : c}`] = v;
        });
        this.styles = shifted;
        this.render();
    }
    undo() {
        if (!this.undoStack.length) return;
        this.redoStack.push(JSON.stringify({
            data: this.data,
            styles: this.styles,
            columnFilters: this.columnFilters,
            colWidths: this.colWidths,
            rowHeights: this.rowHeights,
        }));
        this._applySnapshot(this.undoStack.pop());
    }
    redo() {
        if (!this.redoStack.length) return;
        this.undoStack.push(JSON.stringify({
            data: this.data,
            styles: this.styles,
            columnFilters: this.columnFilters,
            colWidths: this.colWidths,
            rowHeights: this.rowHeights,
        }));
        this._applySnapshot(this.redoStack.pop());
    }
}

class MultiSheetWorkbook {
    constructor(gridContainer, tabContainer, rawPayload, onDirty = null) {
        this.gridContainer = gridContainer;
        this.tabContainer = tabContainer;
        this.onDirty = onDirty;
        const wb = migrateWorkbookPayload(rawPayload);
        this.activeIndex = wb.activeSheetIndex;
        this.sheets = wb.sheets;
        this._editor = null;
        this._renderTabs();
        this._switchSheet(this.activeIndex, true);
    }
    _syncActive() {
        if (this._editor) {
            const s = this._editor.exportSheet();
            this.sheets[this.activeIndex] = normalizeSheetPayload(s);
        }
    }
    _switchSheet(i, skipSync = false) {
        if (!skipSync) this._syncActive();
        this.activeIndex = Math.max(0, Math.min(i, this.sheets.length - 1));
        if (this._editor) {
            this._editor.destroy();
            this._editor = null;
        }
        const sh = this.sheets[this.activeIndex];
        this._editor = new CustomSheetEditor(this.gridContainer, sh, this.onDirty);
        this._renderTabs();
        saveEditorState();
        applyLivePresence(currentPresenceItems);
    }
    _renderTabs() {
        if (!this.tabContainer) return;
        this.tabContainer.innerHTML = '';
        this.sheets.forEach((sh, idx) => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'sheet-tab' + (idx === this.activeIndex ? ' active' : '');
            btn.textContent = sh.name || `Лист${idx + 1}`;
            btn.onclick = () => this._switchSheet(idx);
            const delBtn = document.createElement('span');
            delBtn.className = 'sheet-tab-del';
            delBtn.innerHTML = '&times;';
            delBtn.title = 'Удалить лист';
            delBtn.onclick = (e) => {
                e.stopPropagation();
                if (this.sheets.length <= 1) { alert('Нельзя удалить единственный лист'); return; }
                if (confirm(`Удалить лист "${sh.name || 'Лист'}"?`)) this.deleteSheet(idx);
            };
            btn.appendChild(delBtn);
            btn.ondblclick = () => {
                const oldName = (this.sheets[idx]?.name || `Лист${idx + 1}`).trim();
                const next = prompt('Переименовать лист', oldName);
                if (!next) return;
                const cleaned = String(next).trim().slice(0, 40);
                if (!cleaned) return;
                // Ensure unique sheet names (case-insensitive).
                const existing = new Set(this.sheets.map(s => String(s.name || '').trim().toLowerCase()).filter(Boolean));
                let finalName = cleaned;
                let suffix = 2;
                while (existing.has(finalName.toLowerCase()) && finalName.toLowerCase() !== oldName.toLowerCase()) {
                    finalName = `${cleaned} (${suffix++})`;
                }
                this.sheets[idx].name = finalName;
                // Important: keep active editor state in sync with new sheet name.
                if (idx === this.activeIndex && this._editor) {
                    this._editor.sheetName = finalName;
                    this._syncActive();
                }
                if (typeof this.onDirty === 'function') this.onDirty();
                this._renderTabs();
            };
            this.tabContainer.appendChild(btn);
        });
        const addBtn = document.createElement('button');
        addBtn.type = 'button';
        addBtn.className = 'sheet-tab sheet-tab-add';
        addBtn.textContent = '+';
        addBtn.title = 'Добавить лист';
        addBtn.onclick = () => this.addSheet();
        this.tabContainer.appendChild(addBtn);
    }
    addSheet() {
        this._syncActive();
        const n = this.sheets.length + 1;
        const cols = this.sheets[this.activeIndex]?.data[0]?.length || 10;
        const blank = Array(20).fill(null).map(() => Array(cols).fill(''));
        const newSheet = normalizeSheetPayload({
            name: `Лист${n}`,
            data: blank,
            styles: {},
        });
        this.sheets.push(newSheet);
        if (typeof this.onDirty === 'function') this.onDirty();
        this._switchSheet(this.sheets.length - 1, true);
    }
    deleteSheet(idx) {
        this.sheets.splice(idx, 1);
        if (this.activeIndex >= this.sheets.length) this.activeIndex = this.sheets.length - 1;
        if (typeof this.onDirty === 'function') this.onDirty();
        this._switchSheet(this.activeIndex, true);
    }
    renameActiveSheet(name) {
        const cleaned = String(name || '').trim();
        if (!cleaned) return;
        this.sheets[this.activeIndex].name = cleaned.slice(0, 40);
        if (typeof this.onDirty === 'function') this.onDirty();
        this._renderTabs();
    }
    export() {
        this._syncActive();
        return {
            version: 2,
            activeSheetIndex: this.activeIndex,
            sheets: this.sheets.map((s) => ({
                ...normalizeSheetPayload(s),
                data: s.data.map((row) => row.slice()),
            })),
        };
    }
    getActiveGridData() {
        this._syncActive();
        const sh = this.sheets[this.activeIndex];
        return sh.data.map((row) => row.slice());
    }
    getSelectionMeta() {
        const sh = this.sheets[this.activeIndex];
        const anchor = this._editor?.getSelectionAnchor ? this._editor.getSelectionAnchor() : { row: 0, col: 0 };
        return {
            activeSheetIndex: this.activeIndex,
            sheetName: sh?.name || '',
            row: anchor.row,
            col: anchor.col,
        };
    }
    setSelectionMeta(meta) {
        if (!meta || typeof meta !== 'object') return;
        let idx = Number(meta.activeSheetIndex);
        if (!Number.isFinite(idx)) {
            const target = String(meta.sheetName || '').trim().toLowerCase();
            idx = this.sheets.findIndex((s) => String(s?.name || '').trim().toLowerCase() === target);
        }
        if (!Number.isFinite(idx) || idx < 0) idx = this.activeIndex;
        this._switchSheet(idx, false);
        if (this._editor?.setSelectionAnchor) {
            this._editor.setSelectionAnchor(meta.row, meta.col);
        }
    }
    focus() { if (this._editor) this._editor.focus(); }
    destroy() {
        if (this._editor) {
            this._editor.destroy();
            this._editor = null;
        }
        if (this.gridContainer) this.gridContainer.innerHTML = '';
        if (this.tabContainer) this.tabContainer.innerHTML = '';
    }
    toggleBold() { if (this._editor) this._editor.toggleBold(); }
    toggleItalic() { if (this._editor) this._editor.toggleItalic(); }
    setAlign(a) { if (this._editor) this._editor.setAlign(a); }
    setVAlign(a) { if (this._editor) this._editor.setVAlign(a); }
    setTextColor(c) { if (this._editor) this._editor.setTextColor(c); }
    setFillColor(c) { if (this._editor) this._editor.setFillColor(c); }
    setFontFamily(f) { if (this._editor) this._editor.setFontFamily(f); }
    setFontSize(px) { if (this._editor) this._editor.setFontSize(px); }
    armFormatPainter() { if (this._editor) this._editor.armFormatPainter(); }
    clearFormatPainter() { if (this._editor) this._editor.clearFormatPainter(); }
    getSelectionStyleState() { return this._editor ? this._editor.getSelectionStyleState() : null; }
    isEditing() { return this._editor ? this._editor.isEditing() : false; }
    insertRowBelow() { if (this._editor) this._editor.insertRowBelow(); }
    insertColRight() { if (this._editor) this._editor.insertColRight(); }
    undo() { if (this._editor) this._editor.undo(); }
    redo() { if (this._editor) this._editor.redo(); }
    openFilterForSelection() { if (this._editor) this._editor.openFilterForSelection(); }
    clearAllColumnFilters() { if (this._editor) this._editor.clearAllColumnFilters(); }
}

// ✅ ИНИЦИАЛИЗАЦИЯ ВСТРОЕННОГО РЕДАКТОРА ТАБЛИЦ (книга с листами)
function initHandsontable(doc, restoredSelection = null) {
    console.log('🔍 init sheet workbook');
    const container = document.getElementById('handsontable-container');
    const tabBar = document.getElementById('sheet-tab-bar');
    if (!container) { console.error('❌ Container not found'); return; }
    hotInstance = null;
    if (sheetEditor) { sheetEditor.destroy(); sheetEditor = null; }
    if (window._sheetSyncInterval) {
        clearInterval(window._sheetSyncInterval);
        window._sheetSyncInterval = null;
    }
    if (window._sheetRefreshInterval) {
        clearInterval(window._sheetRefreshInterval);
        window._sheetRefreshInterval = null;
    }

    let payload = doc?.content?.custom_sheet;
    if (!payload) {
        const legacy = Array.isArray(doc?.content?.handsontable) ? doc.content.handsontable : [];
        payload = { data: legacy, rows: legacy.length || 20, cols: (legacy[0]?.length || 10), styles: {} };
    }
    sheetEditor = new MultiSheetWorkbook(container, tabBar, payload, markSheetDirty);
    if (restoredSelection && sheetEditor?.setSelectionMeta) {
        sheetEditor.setSelectionMeta(restoredSelection);
    }
    refreshSheetToolbarState();
    workbookBaseSnapshot = sheetEditor ? deepClone(sheetEditor.export()) : null;
    clearSheetDirty();
    saveEditorState();
    startSheetPresenceLoop();
    if (doc?.is_readonly && container) {
        // Disable editing for shared read-only.
        setTimeout(() => {
            container.querySelectorAll('.sheet-cell').forEach((cell) => {
                cell.setAttribute('contenteditable', 'false');
            });
        }, 0);
    }
    if (doc && !doc.is_readonly) {
        // Периодическое сохранение (только для write)
        window._sheetSyncInterval = setInterval(() => {
            if (currentDocument && currentDocument.id === doc.id && sheetEditor) {
                saveDocumentSilent();
            } else {
                clearInterval(window._sheetSyncInterval);
                window._sheetSyncInterval = null;
            }
        }, 5000);
    }
    // Периодическое обновление контента (для всех: write/read)
    window._sheetRefreshInterval = setInterval(async () => {
        if (!currentDocument || currentDocument.id !== doc.id || !sheetEditor) {
            clearInterval(window._sheetRefreshInterval);
            window._sheetRefreshInterval = null;
            return;
        }
        if (hasPendingSheetChanges() || (sheetEditor?.isEditing && sheetEditor.isEditing())) return;
        try {
            const endpoint = isCurrentSectionTable()
                ? `${API_BASE}/section-tables/${currentDocument.id}/`
                : `${API_BASE}/documents/${currentDocument.id}/`;
            const res = await fetch(endpoint, { headers: getAuthHeaders() });
            if (!res.ok) return;
            const fresh = await res.json();
            if (!fresh?.updated_at || fresh.updated_at === currentDocument.updated_at) return;
            const payloadFresh = fresh?.content?.custom_sheet || null;
            if (!payloadFresh) return;
            const restoreSel = sheetEditor?.getSelectionMeta ? sheetEditor.getSelectionMeta() : null;
            currentDocument.updated_at = fresh.updated_at;
            currentDocument.content = fresh.content || {};
            if (sheetEditor) {
                sheetEditor.destroy();
            }
            sheetEditor = new MultiSheetWorkbook(container, tabBar, payloadFresh, markSheetDirty);
            if (restoreSel && sheetEditor?.setSelectionMeta) {
                sheetEditor.setSelectionMeta(restoreSel);
            }
            refreshSheetToolbarState();
            if (currentDocument?.is_readonly && container) {
                setTimeout(() => {
                    container.querySelectorAll('.sheet-cell').forEach((cell) => {
                        cell.setAttribute('contenteditable', 'false');
                    });
                }, 0);
            }
            workbookBaseSnapshot = sheetEditor ? deepClone(sheetEditor.export()) : null;
            clearSheetDirty();
            saveEditorState();
            applyLivePresence(currentPresenceItems);
        } catch (e) {
            console.debug('Sheet refresh skip:', e?.message || e);
        }
    }, 1000);
}

function toggleSelectionBold() {
    if (sheetEditor) sheetEditor.toggleBold();
}

function toggleSelectionItalic() {
    if (sheetEditor) sheetEditor.toggleItalic();
}

function setSelectionAlign(align) {
    if (sheetEditor) sheetEditor.setAlign(align);
}
function setSelectionVAlign(vAlign) {
    if (sheetEditor) sheetEditor.setVAlign(vAlign);
}
function toggleFormatPainter() {
    if (!sheetEditor) return;
    const state = sheetEditor.getSelectionStyleState ? sheetEditor.getSelectionStyleState() : null;
    if (state?.formatPainterArmed) sheetEditor.clearFormatPainter();
    else sheetEditor.armFormatPainter();
}
function setSelectionTextColor(color) {
    if (sheetEditor) sheetEditor.setTextColor(color);
}
function setSelectionFillColor(color) {
    if (sheetEditor) sheetEditor.setFillColor(color);
}
function setRibbonTab(tabName) {
    document.querySelectorAll('.sheet-ribbon-tab').forEach((el) => {
        el.classList.toggle('active', el.dataset.tab === tabName);
    });
    document.querySelectorAll('.sheet-ribbon-panel').forEach((panel) => {
        panel.classList.toggle('active', panel.dataset.panel === tabName);
    });
}

function setSelectionFontFamily(font) {
    if (sheetEditor && sheetEditor.setFontFamily) sheetEditor.setFontFamily(font);
}

function setSelectionFontSize(px) {
    if (sheetEditor && sheetEditor.setFontSize) sheetEditor.setFontSize(px);
}

function openColumnFilterForSelection() {
    if (sheetEditor && sheetEditor.openFilterForSelection) sheetEditor.openFilterForSelection();
}

function clearSheetColumnFilters() {
    if (sheetEditor && sheetEditor.clearAllColumnFilters) sheetEditor.clearAllColumnFilters();
}

function undoTableEdit() {
    if (sheetEditor) sheetEditor.undo();
}

function redoTableEdit() {
    if (sheetEditor) sheetEditor.redo();
}
function refreshSheetToolbarState(state) {
    const current = state || (sheetEditor?.getSelectionStyleState ? sheetEditor.getSelectionStyleState() : null);
    if (!current) return;
    const boldBtn = document.getElementById('sheetBoldBtn');
    const italicBtn = document.getElementById('sheetItalicBtn');
    const painterBtn = document.getElementById('sheetFormatPainterBtn');
    if (boldBtn) boldBtn.classList.toggle('active', !!current.bold);
    if (italicBtn) italicBtn.classList.toggle('active', !!current.italic);
    if (painterBtn) painterBtn.classList.toggle('active', !!current.formatPainterArmed);
    document.querySelectorAll('[data-align-btn]').forEach((el) => {
        el.classList.toggle('active', el.dataset.alignBtn === current.align);
    });
    document.querySelectorAll('[data-valign-btn]').forEach((el) => {
        el.classList.toggle('active', el.dataset.valignBtn === current.vAlign);
    });
}
document.addEventListener('sheet:toolbar-state', (event) => {
    refreshSheetToolbarState(event?.detail || null);
});

function insertRowBelow() {
    if (sheetEditor) sheetEditor.insertRowBelow();
}

function insertColRight() {
    if (sheetEditor) sheetEditor.insertColRight();
}

function initTextEditor(doc) {
    const container = document.getElementById('handsontable-container');
    if (!container) return;
    container.innerHTML = `<textarea id="docText" style="width:100%;height:100%;padding:1rem;font-family:monospace;font-size:14px;border:none;resize:none;background:#1a1a25;color:#fff;">${doc.content?.text || ''}</textarea>`;
}

// ✅ ТИХОЕ СОХРАНЕНИЕ
async function saveDocumentSilent() {
    if (!currentDocument) return;
    if (currentDocument.is_readonly) return;
    let content = {};
    let body = null;
    let savedWorkbook = null;
    if (currentDocument.doc_type === 'spreadsheet' && (sheetEditor || hotInstance)) {
        try {
            if (sheetEditor) {
                const payload = buildSpreadsheetSavePayload();
                if (!payload || payload.skip) return;
                body = payload.body;
                savedWorkbook = payload.workbook;
                content = body.content;
            } else {
                const data = hotInstance.getData();
                content = { handsontable: data };
                body = { content };
            }
        } catch(e) { console.error('❌ Silent save error:', e); return; }
    } else if (currentDocument.doc_type === 'text') {
        const textEl = document.getElementById('docText');
        if (textEl) content = { text: textEl.value };
        body = { content };
    }
    const url = getSaveContentUrl();
    if (!url) return;
    try {
        const res = await fetch(url, {
            method: 'POST', headers: getAuthHeaders(), body: JSON.stringify(body || { content })
        });
        if (!res.ok) return;
        const data = await res.json().catch(() => ({}));
        currentDocument.content = data.content || content;
        if (data.updated_at) currentDocument.updated_at = data.updated_at;
        if (savedWorkbook) workbookBaseSnapshot = deepClone(savedWorkbook);
        clearSheetDirty();
        console.log('✅ Auto-saved silently');
    } catch (e) { console.error('❌ Silent save failed:', e); }
}

// ✅ СОХРАНЕНИЕ ПО КНОПКЕ
async function saveDocument() {
    if (!currentDocument) return;
    if (currentDocument.is_readonly) { alert('Только чтение: нет прав на сохранение'); return; }
    let content = {};
    let body = null;
    let savedWorkbook = null;
    if (currentDocument.doc_type === 'spreadsheet' && (sheetEditor || hotInstance)) {
        try {
            if (sheetEditor) {
                const payload = buildSpreadsheetSavePayload();
                if (!payload) { alert('Ошибка подготовки данных'); return; }
                if (payload.skip) { alert('Нет изменений для сохранения'); return; }
                body = payload.body;
                savedWorkbook = payload.workbook;
                content = body.content;
            } else {
                const data = hotInstance.getData();
                content = { handsontable: data };
                body = { content };
            }
            console.log('💾 Saving spreadsheet');
        } catch(e) { console.error('❌ Save error:', e); alert('Ошибка сохранения'); return; }
    } else if (currentDocument.doc_type === 'text') {
        const textEl = document.getElementById('docText');
        if (textEl) content = { text: textEl.value };
        body = { content };
    }
    const url = getSaveContentUrl();
    if (!url) return;
    try {
        const res = await fetch(url, {
            method: 'POST', headers: getAuthHeaders(), body: JSON.stringify(body || { content })
        });
        if (res.ok) {
            const data = await res.json().catch(() => ({}));
            currentDocument.content = data.content || content;
            if (data.updated_at) currentDocument.updated_at = data.updated_at;
            if (savedWorkbook) workbookBaseSnapshot = deepClone(savedWorkbook);
            clearSheetDirty();
            alert('✅ Сохранено!');
        }
        else { const err = await res.json().catch(() => ({})); alert(`Ошибка: ${err.detail || 'Не удалось сохранить'}`); }
    } catch (e) { console.error('❌ Save error:', e); alert('Ошибка подключения'); }
}

function openCreateDocumentModal() {
    const titleInput = document.getElementById('newDocTitle');
    const typeSelect = document.getElementById('newDocType');
    if (titleInput) titleInput.value = '';
    if (typeSelect) typeSelect.value = 'spreadsheet';
    currentSectionType = null;
    showModal('createDocumentModal');
}

async function createDocument() {
    // If opened from section, create section table instead of common document.
    if (currentSectionType) {
        return createSectionTable();
    }
    const title = document.getElementById('newDocTitle')?.value || 'Без названия';
    const docType = document.getElementById('newDocType')?.value;
    try {
        const res = await fetch(`${API_BASE}/documents/`, { method: 'POST', headers: getAuthHeaders(), body: JSON.stringify({ title, doc_type: docType, content: {} }) });
        if (res.ok) { hideModal('createDocumentModal'); await loadDocuments(); }
        else { const err = await res.json().catch(() => ({})); alert(`Ошибка: ${err.detail || 'Неизвестная ошибка'}`); }
    } catch (e) { console.error('Create document error:', e); alert('Ошибка подключения'); }
}

async function deleteDocument(docId) {
    if (!confirm('Удалить документ?')) return;
    try {
        const res = await fetch(`${API_BASE}/documents/${docId}/`, { method: 'DELETE', headers: getAuthHeaders() });
        if (res.ok || res.status === 204) await loadDocuments();
        else alert('Ошибка');
    } catch { alert('Ошибка подключения'); }
}

async function shareCurrentDocument() {
    if (!currentDocument) return;
    const username = prompt('Имя пользователя:');
    if (!username) return;
    try {
        const shareUrl = getShareUrl();
        if (!shareUrl) return;
        const res = await fetch(shareUrl, { method: 'POST', headers: getAuthHeaders(), body: JSON.stringify({ username, permission: 'write' }) });
        const data = await res.json().catch(() => ({}));
        alert(res.ok ? `✅ Доступ предоставлен ${username}` : `❌ ${data.detail || 'Ошибка'}`);
    } catch { alert('Ошибка подключения'); }
}

// ✅ ЗАГРУЗКА ТАБЛИЦ РАЗДЕЛОВ (ИСПРАВЛЕНО: таблицы создаются в разделах)
async function loadSectionTable(sectionType) {
    console.log(`📊 Loading ${sectionType} tables...`);
    currentSectionType = sectionType;
    try {
        const res = await fetch(`${API_BASE}/section-tables/?section_type=${sectionType}`, { headers: getAuthHeaders() });
        if (res.status === 200) {
            const data = await res.json();
            const tables = data.results || data || [];
            renderSectionTables(tables, sectionType);
        } else { showEmpty('Не удалось загрузить таблицы'); }
    } catch (e) { console.error('❌ Load section tables error:', e); showEmpty('Ошибка подключения'); }
}

function renderSectionTables(tables, sectionType) {
    hideLoading();
    if (!tables?.length) {
        showEmpty(`Нет таблиц в разделе. Создайте первую!`);
        return;
    }
    hideEmpty();
    if (filesGrid) {
        filesGrid.innerHTML = '';
        tables.forEach((t, i) => filesGrid.appendChild(createSectionTableCard(t, i, sectionType)));
    }
}

function createSectionTableCard(table, index, sectionType) {
    const card = document.createElement('div');
    card.className = 'file-card';
    card.style.animationDelay = `${index * 0.1}s`;
    card.style.cursor = 'pointer';
    card.onclick = (e) => { if (!e.target.closest('.file-actions')) openSectionTable(table.id); };
    const date = table.updated_at ? new Date(table.updated_at).toLocaleString('ru-RU') : '';
    card.innerHTML = `
        <div class="file-icon">${iconGlyph('table')}</div>
        <div class="file-name" title="${escapeHtml(table.title)}">${escapeHtml(table.title)}</div>
        <div class="file-meta"><span>${sectionType}</span><span>${date}</span></div>
        <div class="file-actions">
            <button class="file-action-btn" onclick="event.stopPropagation();openSectionTable(${table.id})">${iconGlyph('pencil')}</button>
            <button class="file-action-btn" onclick="event.stopPropagation();deleteSectionTable(${table.id})">${iconGlyph('trash')}</button>
        </div>
    `;
    return card;
}

function openCreateSectionTableModal(sectionType) {
    const titleInput = document.getElementById('newDocTitle');
    const typeSelect = document.getElementById('newDocType');
    if (titleInput) titleInput.value = '';
    if (typeSelect) typeSelect.value = 'spreadsheet';
    currentSectionType = sectionType;
    showModal('createDocumentModal');
}

async function createSectionTable() {
    const title = document.getElementById('newDocTitle')?.value || 'Без названия';
    const sectionType = currentSectionType || 'attendance';
    try {
        const res = await fetch(`${API_BASE}/section-tables/`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({
                title,
                section_type: sectionType,
                content: { custom_sheet: { rows: 20, cols: 10, data: Array(20).fill(null).map(() => Array(10).fill('')), styles: {} } }
            })
        });
        if (res.ok) {
            hideModal('createDocumentModal');
            await loadSectionTable(sectionType);
        } else {
            const err = await res.json().catch(() => ({}));
            alert(`Ошибка: ${err.detail || 'Неизвестная ошибка'}`);
        }
    } catch (e) { console.error('Create section table error:', e); alert('Ошибка подключения'); }
}

async function openSectionTable(tableId, restoredSelection = null, sharedPermission = null) {
    try {
        const res = await fetch(`${API_BASE}/section-tables/${tableId}/`, { headers: getAuthHeaders() });
        if (res.ok) {
            currentDocument = await res.json();
            if (sharedPermission) currentDocument.shared_permission = sharedPermission;
            currentDocument.doc_type = 'spreadsheet';
            currentDocument.isSectionTable = true;
            showDocumentEditor(currentDocument, restoredSelection);
        } else { alert('Ошибка открытия'); }
    } catch (e) { console.error('Open section table error:', e); alert('Ошибка'); }
}

async function deleteSectionTable(tableId) {
    if (!confirm('Удалить таблицу?')) return;
    try {
        const res = await fetch(`${API_BASE}/section-tables/${tableId}/`, { method: 'DELETE', headers: getAuthHeaders() });
        if (res.ok || res.status === 204) {
            await loadSectionTable(currentSectionType || 'attendance');
        } else { alert('Ошибка'); }
    } catch { alert('Ошибка подключения'); }
}

// ✅ ЗАГРУЗКА ОБЩЕГО ДОСТУПА (ИСПРАВЛЕНО: показывает файлы и таблицы)
async function loadShared() {
    console.log('🔗 Loading shared...');
    try {
        const res = await fetch(`${API_BASE}/permissions/`, { headers: getAuthHeaders() });
        if (res.status === 200) {
            const data = await res.json();
            const perms = data.results || data || [];
            renderShared(perms);
        } else { showEmpty('Не удалось загрузить'); }
    } catch (e) { console.error('❌ Load shared error:', e); showEmpty('Ошибка'); }
}

function renderShared(perms) {
    hideLoading();
    if (!perms?.length) { showEmpty('Нет общего доступа'); return; }
    hideEmpty();
    if (filesGrid) {
        filesGrid.innerHTML = '';
        perms.forEach((p, i) => filesGrid.appendChild(createSharedCard(p, i)));
    }
}

function createSharedCard(perm, index) {
    const card = document.createElement('div');
    card.className = 'file-card';
    card.style.animationDelay = `${index * 0.1}s`;
    card.style.cursor = 'pointer';
    const fileId = perm.file_id ?? perm.file;
    const fileType = perm.file_type || 'storage_file';
    const canWrite = perm.permission === 'write';
    const canManage = !!perm.can_manage;
    const openShared = async () => {
        if (!fileId) return;
        if (fileType === 'storage_file') return downloadFile(fileId);
        if (fileType === 'document') {
            await openDocument(fileId, null, perm.permission);
            return;
        }
        if (fileType === 'section_table') {
            await openSectionTable(fileId, null, perm.permission);
        }
    };
    card.onclick = (e) => { if (!e.target.closest('.file-actions')) openShared(); };
    const name = perm.file_name || `Объект #${fileId}`;
    const user = perm.user?.username || 'Неизвестно';
    const canWriteBadge = perm.permission === 'write';
    const badge = `<span class="perm-badge ${canWriteBadge ? 'write' : 'read'}">${canWriteBadge ? 'WRITE' : 'READ'}</span>`;
    card.innerHTML = `
        <div class="file-icon">${iconGlyph('link')}</div>
        <div class="file-name" title="${escapeHtml(name)}">${escapeHtml(name)}</div>
        <div class="file-meta shared-perm-meta">${badge}<span class="shared-perm-user">${escapeHtml(user)}</span></div>
        <div class="file-actions"></div>`;
    const actions = card.querySelector('.file-actions');
    if (actions) {
        const btn = document.createElement('button');
        btn.className = 'file-action-btn';
        btn.innerHTML = fileType === 'storage_file' ? iconGlyph('download') : (canWrite ? iconGlyph('pencil') : iconGlyph('shield'));
        btn.onclick = (e) => { e.stopPropagation(); openShared(); };
        actions.appendChild(btn);

        if (canManage) {
            const toggle = document.createElement('button');
            toggle.className = 'file-action-btn';
            toggle.title = 'Переключить read/write';
            toggle.innerHTML = canWrite ? iconGlyph('shield') : iconGlyph('pencil');
            toggle.onclick = (e) => {
                e.stopPropagation();
                updatePermission(perm.id, canWrite ? 'read' : 'write');
            };
            actions.appendChild(toggle);

            const del = document.createElement('button');
            del.className = 'file-action-btn';
            del.title = 'Снять доступ';
            del.innerHTML = iconGlyph('trash');
            del.onclick = (e) => { e.stopPropagation(); revokePermission(perm.id); };
            actions.appendChild(del);
        }
    }
    return card;
}

// ✅ ЗАГРУЗКА ЛОГОВ
async function loadLogs() {
    console.log('📋 Loading logs...');
    try {
        const res = await fetch(`${API_BASE}/audit-logs/`, { headers: getAuthHeaders() });
        if (res.status === 200) {
            const data = await res.json();
            const logs = data.results || data || [];
            renderLogs(logs);
        } else { showEmpty('Не удалось загрузить'); }
    } catch (e) { console.error('❌ Load logs error:', e); showEmpty('Ошибка'); }
}

function renderLogs(logs) {
    hideLoading();
    if (!logs?.length) { showEmpty('Нет записей'); return; }
    hideEmpty();
    if (filesGrid) {
        filesGrid.innerHTML = '';
        logs.forEach((l, i) => filesGrid.appendChild(createLogCard(l, i)));
    }
}

function createLogCard(log, index) {
    const card = document.createElement('div');
    card.className = 'file-card';
    card.style.animationDelay = `${index * 0.1}s`;
    const iconMap = { upload: 'file', download: 'download', delete: 'trash', share: 'share', login: 'login', logout: 'logout', update: 'pencil', create: 'table' };
    const icon = iconGlyph(iconMap[log.action] || 'file');
    const date = log.timestamp ? new Date(log.timestamp).toLocaleString('ru-RU') : '';
    const user = log.user_username || log.user?.username || 'Система';
    card.innerHTML = `
        <div class="file-icon">${icon}</div>
        <div class="file-name">${escapeHtml(log.action)}</div>
        <div class="file-meta"><span>${user}</span><span>${date}</span></div>
        ${log.details ? `<div style="margin-top:0.5rem;font-size:0.75rem;color:var(--text-muted);">${escapeHtml(log.details)}</div>` : ''}`;
    return card;
}

function showLoading() {
    if (loadingState) { loadingState.classList.add('show'); loadingState.style.display = 'flex'; }
    if (emptyState) emptyState.classList.remove('show');
    if (filesGrid) filesGrid.style.display = 'none';
}

function hideLoading() {
    if (loadingState) { loadingState.classList.remove('show'); loadingState.style.display = 'none'; }
    if (filesGrid) filesGrid.style.display = 'grid';
}

function showEmpty(msg) {
    if (emptyState) {
        emptyState.classList.add('show');
        emptyState.style.display = 'flex';
        const p = emptyState.querySelector('p');
        if (p && msg) p.textContent = msg;
    }
    if (filesGrid) filesGrid.style.display = 'none';
    if (loadingState) loadingState.style.display = 'none';
}

function hideEmpty() {
    if (emptyState) { emptyState.classList.remove('show'); emptyState.style.display = 'none'; }
}

// ✅ НАСТРОЙКА СОБЫТИЙ
function setupEventListeners() {
    if (uploadBtn) {
        uploadBtn.onclick = () => {
            if (currentView === 'files') { loadFoldersForDropdown(); showModal(uploadModal); }
            else if (currentView === 'folders') { createFolder(); }
            else if (currentView === 'documents' || currentView?.startsWith('section-')) {
                currentView === 'documents' ? openCreateDocumentModal() : openCreateSectionTableModal(currentView.replace('section-', ''));
            }
        };
    }
    if (logoutBtn) logoutBtn.onclick = logout;
    if (uploadForm) uploadForm.onsubmit = handleUpload;
    if (loginForm) loginForm.onsubmit = handleLogin;
    if (registerForm) registerForm.onsubmit = handleRegister;

    const tR = document.getElementById('toggleToRegister');
    if (tR) tR.onclick = (e) => { e.preventDefault(); showRegisterModal(); };
    const tL = document.getElementById('toggleToLogin');
    if (tL) tL.onclick = (e) => { e.preventDefault(); showLoginModal(); };

    navItems.forEach(item => {
        item.onclick = (e) => {
            e.preventDefault();
            const view = item.getAttribute('data-view');
            if (view) loadView(view);
        };
    });

    [uploadModal, loginModal, previewModal, documentModal, createDocumentModalEl].forEach(modal => {
        if (modal) modal.onclick = (e) => { if (e.target === modal) hideModal(modal); };
    });

    window.addEventListener('beforeunload', () => {
        saveEditorState();
        sendPresenceLeave();
    });
    window.addEventListener('resize', () => {
        if (currentPresenceItems.length) applyLivePresence(currentPresenceItems);
    });
    window.addEventListener('scroll', () => {
        if (currentPresenceItems.length) applyLivePresence(currentPresenceItems);
    }, true);
}




