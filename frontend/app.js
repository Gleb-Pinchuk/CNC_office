// ==================== CNC Office - Frontend App v21.0 ====================
const API_BASE = '/api';
let currentUser = null, currentFolder = null, currentView = 'files';
let currentDocument = null, authToken = localStorage.getItem('cnc_auth_token');

document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 App v21.0 initialized');
    setupEventListeners();
    checkAuth();
});

function getAuthHeaders(isJson = true) {
    const headers = { 'Accept': 'application/json' };
    if (authToken) headers['Authorization'] = `Token ${authToken}`;
    if (isJson) headers['Content-Type'] = 'application/json';
    return headers;
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function clearAuth() {
    localStorage.removeItem('cnc_auth_token');
    localStorage.removeItem('cnc_username');
    authToken = null;
    currentUser = null;
}

async function checkAuth() {
    authToken = localStorage.getItem('cnc_auth_token');
    if (!authToken) { showLoginModal(); return; }
    try {
        const res = await fetch(`${API_BASE}/users/me/`, { headers: getAuthHeaders() });
        if (res.ok) {
            currentUser = await res.json();
            const usernameSpan = document.getElementById('username');
            if (usernameSpan) usernameSpan.textContent = currentUser.username;
            loadView('files');
        } else { clearAuth(); showLoginModal(); }
    } catch (e) { showLoginModal(); }
}

function showModal(modal) {
    const el = typeof modal === 'string' ? document.getElementById(modal) : modal;
    if (el) {
        el.classList.add('show');
        el.style.setProperty('display', 'flex', 'important');
        document.body.style.overflow = 'hidden';
    }
}

function hideModal(modal) {
    const el = typeof modal === 'string' ? document.getElementById(modal) : modal;
    if (el) {
        if (el.id === 'documentModal' && currentDocument) saveDocumentSilent();
        el.classList.remove('show');
        el.style.display = 'none';
        document.body.style.overflow = '';
    }
}

function showLoginModal() {
    const loginForm = document.getElementById('loginForm');
    if (loginForm) loginForm.classList.remove('hidden');
    showModal('loginModal');
}

async function handleLogin(e) {
    e.preventDefault();
    const username = document.getElementById('loginUsername')?.value?.trim();
    const password = document.getElementById('loginPassword')?.value;
    if (!username || !password) { alert('Введите логин и пароль'); return; }
    try {
        const res = await fetch(`${API_BASE}/users/login/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        const data = await res.json();
        if (res.ok && data.token) {
            authToken = data.token;
            localStorage.setItem('cnc_auth_token', data.token);
            localStorage.setItem('cnc_username', data.user?.username || username);
            currentUser = data.user || { username };
            const usernameSpan = document.getElementById('username');
            if (usernameSpan) usernameSpan.textContent = currentUser.username;
            hideModal('loginModal');
            loadView('files');
        } else { alert('❌ Ошибка входа'); }
    } catch (e) { alert('Ошибка подключения'); }
}

async function logout() { clearAuth(); location.reload(); }

async function loadView(view) {
    currentView = view;
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(n => n.classList.toggle('active', n.getAttribute('data-view') === view));

    const titles = {
        'files': 'Мои файлы', 'folders': 'Папки', 'documents': 'Документы',
        'section-attendance': '📊 Посещаемость', 'section-rangers': '🤖 Рейнджеры',
        'section-statements': '📋 Ведомости', 'shared': 'Общий доступ', 'logs': 'Журнал'
    };
    const pageTitle = document.getElementById('pageTitle');
    if (pageTitle) pageTitle.textContent = titles[view] || 'CNC Office';

    const uploadBtn = document.getElementById('uploadBtn');
    if (uploadBtn) {
        if (view === 'files') {
            uploadBtn.style.display = 'inline-flex';
            uploadBtn.innerHTML = '📤 Загрузить файл';
            uploadBtn.onclick = () => { loadFoldersForDropdown(); showModal('uploadModal'); };
        } else if (view === 'folders') {
            uploadBtn.style.display = 'inline-flex';
            uploadBtn.innerHTML = '📁 Создать папку';
            uploadBtn.onclick = createFolder;
        } else if (view === 'documents') {
            uploadBtn.style.display = 'inline-flex';
            uploadBtn.innerHTML = '📄 Создать таблицу';
            uploadBtn.onclick = openCreateDocumentModal;
        } else {
            uploadBtn.style.display = 'none';
        }
    }

    showLoading();
    if (view === 'files') await loadFiles();
    else if (view === 'folders') await loadFolders();
    else if (view === 'documents') await loadDocuments();
}

async function loadFiles() {
    try {
        let url = `${API_BASE}/files/`;
        if (currentFolder) url += `?folder=${currentFolder.id}`;
        const res = await fetch(url, { headers: getAuthHeaders() });
        if (res.status === 200) {
            const data = await res.json();
            renderFiles(data.results || data || []);
        } else { hideLoading(); showEmpty('Не удалось загрузить'); }
    } catch (e) {
        console.error('Load files error:', e);
        hideLoading(); showEmpty('Ошибка подключения');
    }
}

function renderFiles(files) {
    hideLoading();
    if (!files?.length) { showEmpty('Нет файлов'); return; }
    hideEmpty();
    const filesGrid = document.getElementById('filesGrid');
    if (filesGrid) {
        filesGrid.innerHTML = '';
        files.forEach(f => {
            if (!f) return;
            const card = document.createElement('div');
            card.className = 'file-card';
            card.style.cursor = 'pointer';
            const icon = getFileIcon(f.mime_type);
            const name = f.file_name || (f.file ? f.file.split('/').pop() : 'File');
            const size = f.size_mb ? `${f.size_mb} MB` : '0 MB';
            const date = f.uploaded_at ? new Date(f.uploaded_at).toLocaleDateString('ru-RU') : '';
            card.innerHTML = `
                <div class="file-icon">${icon}</div>
                <div class="file-name" title="${escapeHtml(name)}">${escapeHtml(name)}</div>
                <div class="file-meta"><span>${size}</span><span>${date}</span></div>`;
            card.onclick = () => showPreviewModal(f);
            filesGrid.appendChild(card);
        });
    }
}

function getFileIcon(mt) {
    if (!mt) return '📄';
    const m = mt.toLowerCase();
    if (m.includes('excel') || m.includes('spreadsheet')) return '📊';
    if (m.includes('word') || m.includes('.doc')) return '📝';
    if (m.includes('pdf')) return '📄';
    if (m.includes('image')) return '🖼️';
    if (m.includes('video')) return '🎬';
    if (m.includes('audio')) return '🎵';
    if (m.includes('zip')) return '📦';
    return '📄';
}

async function uploadFile(file) {
    const fd = new FormData();
    fd.append('file', file);
    if (currentFolder) fd.append('folder', currentFolder.id);
    try {
        const headers = getAuthHeaders(false);
        delete headers['Content-Type'];
        const res = await fetch(`${API_BASE}/files/`, { method: 'POST', headers, body: fd });
        const data = await res.json();
        if (res.ok || res.status === 201) {
            hideModal('uploadModal');
            await loadFiles();
        } else { alert('Ошибка: ' + (data.detail || data.error || 'Неизвестная ошибка')); }
    } catch (e) { alert('Ошибка подключения: ' + e.message); }
}

async function handleUpload(e) {
    e.preventDefault();
    const fi = document.getElementById('fileInput');
    if (!fi?.files[0]) { alert('Выберите файл'); return; }
    await uploadFile(fi.files[0]);
}

async function downloadFile(fileId) {
    try {
        const res = await fetch(`${API_BASE}/files/${fileId}/download/`, { headers: getAuthHeaders() });
        if (res.ok) {
            const blob = await res.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url; a.download = `file_${fileId}`;
            document.body.appendChild(a); a.click();
            window.URL.revokeObjectURL(url); document.body.removeChild(a);
        } else { alert('Не удалось скачать'); }
    } catch (e) { alert('Ошибка подключения'); }
}

function showPreviewModal(file) {
    const mt = (file.mime_type || '').toLowerCase();
    const ext = (file.file_name || '').split('.').pop().toLowerCase();
    const url = `${API_BASE}/files/${file.id}/download/`;
    if (mt.includes('pdf') || ext === 'pdf') { window.open(url, '_blank'); return; }
    const previewModal = document.getElementById('previewModal');
    if (!previewModal) { downloadFile(file.id); return; }
    const content = document.getElementById('previewContent');
    const title = document.getElementById('previewTitle');
    if (!content || !title) { downloadFile(file.id); return; }
    title.textContent = file.file_name || 'Файл';
    if (mt.includes('image')) {
        fetch(url, { headers: getAuthHeaders() }).then(r => r.blob()).then(blob => {
            const imgUrl = URL.createObjectURL(blob);
            content.innerHTML = `<div style="text-align:center;"><img src="${imgUrl}" style="max-width:100%;max-height:80vh;border-radius:8px;"></div>`;
            showModal('previewModal');
        }).catch(() => { content.innerHTML = '<p style="color:#ff4466;">Ошибка</p>'; showModal('previewModal'); });
    } else { downloadFile(file.id); }
}

async function loadFolders() {
    try {
        hideLoading();
        const res = await fetch(`${API_BASE}/folders/`, { headers: getAuthHeaders() });
        if (res.status === 200) {
            const data = await res.json();
            renderFolders(data.results || data || []);
        } else { hideLoading(); showEmpty('Нет папок'); }
    } catch (e) { console.error('Folders error:', e); hideLoading(); showEmpty('Ошибка'); }
}

function renderFolders(folders) {
    hideLoading();
    if (!folders?.length) { showEmpty('Нет папок'); return; }
    hideEmpty();
    const filesGrid = document.getElementById('filesGrid');
    if (filesGrid) {
        filesGrid.innerHTML = '';
        folders.forEach(f => {
            const card = document.createElement('div');
            card.className = 'file-card';
            card.style.cursor = 'pointer';
            const date = f.created_at ? new Date(f.created_at).toLocaleDateString('ru-RU') : '';
            card.innerHTML = `
                <div class="file-icon">📁</div>
                <div class="file-name">${escapeHtml(f.name)}</div>
                <div class="file-meta"><span>${f.files_count||0} файлов</span><span>${date}</span></div>`;
            card.onclick = () => { currentFolder = f; loadView('files'); };
            filesGrid.appendChild(card);
        });
    }
}

async function createFolder() {
    const name = prompt('Имя папки:');
    if (!name?.trim()) return;
    try {
        const res = await fetch(`${API_BASE}/folders/`, {
            method: 'POST', headers: getAuthHeaders(),
            body: JSON.stringify({ name: name.trim() })
        });
        if (res.ok) await loadFolders();
        else alert('Ошибка создания');
    } catch (e) { alert('Ошибка'); }
}

async function loadFoldersForDropdown() {
    const folderSelect = document.getElementById('folderSelect');
    if (!folderSelect) return;
    folderSelect.innerHTML = '<option value="">Корневая папка</option>';
    try {
        const res = await fetch(`${API_BASE}/folders/`, { headers: getAuthHeaders() });
        if (res.status === 200) {
            const data = await res.json();
            (data.results || data || []).forEach(folder => {
                const opt = document.createElement('option');
                opt.value = folder.id; opt.textContent = folder.name;
                folderSelect.appendChild(opt);
            });
        }
    } catch (e) {}
}

async function loadDocuments() {
    try {
        hideLoading();
        const res = await fetch(`${API_BASE}/documents/`, { headers: getAuthHeaders() });
        if (res.status === 200) {
            const data = await res.json();
            renderDocuments(data.results || data || []);
        } else { hideLoading(); showEmpty('Нет документов'); }
    } catch (e) { console.error('Documents error:', e); hideLoading(); showEmpty('Ошибка'); }
}

function renderDocuments(docs) {
    hideLoading();
    if (!docs?.length) { showEmpty('Нет документов'); return; }
    hideEmpty();
    const filesGrid = document.getElementById('filesGrid');
    if (filesGrid) {
        filesGrid.innerHTML = '';
        docs.forEach(doc => {
            const card = document.createElement('div');
            card.className = 'file-card';
            card.style.cursor = 'pointer';
            const icon = doc.doc_type === 'spreadsheet' ? '📊' : '📝';
            const date = doc.updated_at ? new Date(doc.updated_at).toLocaleString('ru-RU') : '';
            card.innerHTML = `
                <div class="file-icon">${icon}</div>
                <div class="file-name">${escapeHtml(doc.title)}</div>
                <div class="file-meta"><span>${doc.doc_type==='spreadsheet'?'Таблица':'Текст'}</span><span>${date}</span></div>`;
            card.onclick = () => openDocument(doc.id);
            filesGrid.appendChild(card);
        });
    }
}

async function openDocument(docId) {
    try {
        const res = await fetch(`${API_BASE}/documents/${docId}/`, { headers: getAuthHeaders() });
        if (res.ok) {
            currentDocument = await res.json();
            showDocumentEditor(currentDocument);
        } else { alert('Ошибка открытия'); }
    } catch (e) { console.error('Open error:', e); alert('Ошибка: ' + e.message); }
}

function showDocumentEditor(doc) {
    console.log('📝 Opening:', doc.title);
    const title = document.getElementById('documentTitle');
    if (title) title.textContent = doc.title || 'Таблица';
    currentDocument = doc;
    const modal = document.getElementById('documentModal');
    if (modal) {
        modal.classList.add('show');
        modal.style.setProperty('display', 'flex', 'important');
        modal.style.width = '100%'; modal.style.height = '100%';
        modal.style.maxWidth = 'none'; modal.style.maxHeight = 'none';
        document.body.style.overflow = 'hidden';
    }
    setTimeout(() => {
        const container = document.getElementById('luckysheet-container');
        if (container) {
            container.style.setProperty('display', 'block', 'important');
            container.style.height = 'calc(100vh - 60px)';
            container.style.width = '100%';
        }
        if (doc.doc_type === 'spreadsheet') initLuckysheet(doc);
    }, 300);
}

function initLuckysheet(doc) {
    console.log('🔍 [LUCKY] init start');
    const container = document.getElementById('luckysheet-container');
    if (!container) { console.error('❌ Container not found'); return; }
    if (typeof window.luckysheet === 'undefined') {
        console.error('❌ Luckysheet undefined');
        container.innerHTML = '<div style="padding:2rem;color:#fff;">⚠️ Редактор не загрузился</div>';
        return;
    }
    try {
        container.innerHTML = '';
        container.style.display = 'block';
        container.style.height = 'calc(100vh - 80px)';
        container.style.width = '100%';

        setTimeout(() => {
            let sheetData = doc.content?.luckysheet;
            if (!sheetData || !Array.isArray(sheetData) || sheetData.length === 0) {
                sheetData = [{
                    name: 'Sheet1', status: '1', order: '0',
                    data: Array(50).fill(null).map(() => Array(30).fill(null)),
                    rowCount: 50, columnCount: 30
                }];
            }

            window.luckysheet.create({
                container: 'luckysheet-container',
                lang: 'ru',
                data: sheetData,
                showtoolbar: true,
                showtoolbarConfig: { undoRedo: true, image: false, print: false, exportXlsx: true }
            });
            console.log('✅ [LUCKY] created');
            setTimeout(() => { if (window.luckysheet?.refresh) window.luckysheet.refresh(); }, 200);
        }, 100);
    } catch (e) {
        console.error('❌ [LUCKY] error:', e);
        container.innerHTML = `<div style="padding:2rem;color:#fff;">⚠️ ${e.message}</div>`;
    }
}

async function saveDocumentSilent() {
    if (!currentDocument || typeof window.luckysheet === 'undefined') return;
    try {
        const sheetData = window.luckysheet.getAllSheets();
        if (!sheetData) return;
        await fetch(`${API_BASE}/documents/${currentDocument.id}/save_content/`, {
            method: 'POST', headers: getAuthHeaders(),
            body: JSON.stringify({ content: { luckysheet: sheetData } })
        });
        currentDocument.content = { luckysheet: sheetData };
    } catch (e) { console.error('Save error:', e); }
}

async function saveDocument() {
    if (!currentDocument || typeof window.luckysheet === 'undefined') { alert('Нет данных'); return; }
    try {
        const sheetData = window.luckysheet.getAllSheets();
        const res = await fetch(`${API_BASE}/documents/${currentDocument.id}/save_content/`, {
            method: 'POST', headers: getAuthHeaders(),
            body: JSON.stringify({ content: { luckysheet: sheetData } })
        });
        if (res.ok) { currentDocument.content = { luckysheet: sheetData }; alert('✅ Сохранено'); }
        else alert('Ошибка сохранения');
    } catch (e) { alert('Ошибка подключения'); }
}

async function exportToExcel() {
    if (typeof window.luckysheet === 'undefined') { alert('Нет данных'); return; }
    try {
        const sheetData = window.luckysheet.getSheetData();
        let csv = [];
        if (sheetData?.length) {
            sheetData.forEach(row => {
                const csvRow = row.map(cell => cell?.v !== undefined ? `"${String(cell.v).replace(/"/g,'""')}"` : '""');
                csv.push(csvRow.join(';'));
            });
        }
        const blob = new Blob(['\ufeff'+csv.join('\n')], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a'); a.href = url; a.download = `${currentDocument?.title||'table'}.csv`;
        document.body.appendChild(a); a.click(); document.body.removeChild(a);
        URL.revokeObjectURL(url);
    } catch (e) { alert('Ошибка экспорта'); }
}

function openCreateDocumentModal() {
    const titleInput = document.getElementById('newDocTitle');
    if (titleInput) titleInput.value = '';
    showModal('createDocumentModal');
}

async function createDocument() {
    const title = document.getElementById('newDocTitle')?.value || 'Без названия';
    try {
        const res = await fetch(`${API_BASE}/documents/`, {
            method: 'POST', headers: getAuthHeaders(),
            body: JSON.stringify({ title, doc_type: 'spreadsheet', content: {} })
        });
        if (res.ok) { hideModal('createDocumentModal'); await loadDocuments(); }
        else alert('Ошибка создания');
    } catch (e) { alert('Ошибка подключения'); }
}

function showLoading() {
    const loadingState = document.getElementById('loadingState');
    const emptyState = document.getElementById('emptyState');
    const filesGrid = document.getElementById('filesGrid');
    if (loadingState) { loadingState.classList.add('show'); loadingState.style.display = 'flex'; }
    if (emptyState) emptyState.classList.remove('show');
    if (filesGrid) filesGrid.style.display = 'none';
}

function hideLoading() {
    const loadingState = document.getElementById('loadingState');
    const filesGrid = document.getElementById('filesGrid');
    if (loadingState) { loadingState.classList.remove('show'); loadingState.style.display = 'none'; }
    if (filesGrid) filesGrid.style.display = 'grid';
}

function showEmpty(msg) {
    const emptyState = document.getElementById('emptyState');
    const filesGrid = document.getElementById('filesGrid');
    const loadingState = document.getElementById('loadingState');
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
    const emptyState = document.getElementById('emptyState');
    if (emptyState) { emptyState.classList.remove('show'); emptyState.style.display = 'none'; }
}

function setupEventListeners() {
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) logoutBtn.onclick = logout;

    const uploadForm = document.getElementById('uploadForm');
    if (uploadForm) uploadForm.onsubmit = handleUpload;

    const loginForm = document.getElementById('loginForm');
    if (loginForm) loginForm.onsubmit = handleLogin;

    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(item => {
        item.onclick = (e) => {
            e.preventDefault();
            const view = item.getAttribute('data-view');
            if (view) loadView(view);
        };
    });

    [document.getElementById('uploadModal'), document.getElementById('loginModal'),
     document.getElementById('previewModal'), document.getElementById('documentModal'),
     document.getElementById('createDocumentModal')].forEach(modal => {
        if (modal) modal.onclick = (e) => { if (e.target === modal) hideModal(modal); };
    });
}
