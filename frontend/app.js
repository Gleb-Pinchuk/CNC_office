// ==================== CNC Office - Frontend App v20.0 ====================
const API_BASE = '/api';
let currentUser = null;
let currentFolder = null;
let currentView = 'files';
let currentDocument = null;
let currentSectionType = null;
let authToken = localStorage.getItem('cnc_auth_token');

// DOM Elements
let filesGrid, loadingState, emptyState, pageTitle, uploadModal, loginModal;
let previewModal, documentModal, createDocumentModalEl, uploadBtn, logoutBtn;
let uploadForm, loginForm, registerForm, usernameSpan, folderSelect, navItems;

// ✅ Инициализация
document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 App initialized v20.0');

    // Кэшируем элементы
    filesGrid = document.getElementById('filesGrid');
    loadingState = document.getElementById('loadingState');
    emptyState = document.getElementById('emptyState');
    pageTitle = document.getElementById('pageTitle');
    uploadModal = document.getElementById('uploadModal');
    loginModal = document.getElementById('loginModal');
    previewModal = document.getElementById('previewModal');
    documentModal = document.getElementById('documentModal');
    createDocumentModalEl = document.getElementById('createDocumentModal');
    uploadBtn = document.getElementById('uploadBtn');
    logoutBtn = document.getElementById('logoutBtn');
    uploadForm = document.getElementById('uploadForm');
    loginForm = document.getElementById('loginForm');
    registerForm = document.getElementById('registerForm');
    usernameSpan = document.getElementById('username');
    folderSelect = document.getElementById('folderSelect');
    navItems = document.querySelectorAll('.nav-item');

    setupEventListeners();
    checkAuth();
});

// ✅ Заголовки для API
function getAuthHeaders(isJson = true) {
    const headers = { 'Accept': 'application/json' };
    if (authToken) headers['Authorization'] = `Token ${authToken}`;
    if (isJson) headers['Content-Type'] = 'application/json';
    return headers;
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
    authToken = null;
    currentUser = null;
}

// ✅ Проверка авторизации
async function checkAuth() {
    authToken = localStorage.getItem('cnc_auth_token');
    if (!authToken) { showLoginModal(); return; }
    try {
        const res = await fetch(`${API_BASE}/users/me/`, { headers: getAuthHeaders() });
        if (res.ok) {
            currentUser = await res.json();
            if (usernameSpan) usernameSpan.textContent = currentUser.username;
            loadView('files');
        } else {
            clearAuth();
            showLoginModal();
        }
    } catch (e) {
        console.error('Auth error:', e);
        showLoginModal();
    }
}

// ✅ Показать модальное окно
function showModal(modal) {
    const el = typeof modal === 'string' ? document.getElementById(modal) : modal;
    if (el) {
        el.classList.add('show');
        el.style.setProperty('display', 'flex', 'important');
        document.body.style.overflow = 'hidden';
    }
}

// ✅ Скрыть модальное окно
function hideModal(modal) {
    const el = typeof modal === 'string' ? document.getElementById(modal) : modal;
    if (el) {
        if (el.id === 'documentModal' && currentDocument) saveDocumentSilent();
        el.classList.remove('show');
        el.style.display = 'none';
        document.body.style.overflow = '';
        const form = el.querySelector('form');
        if (form) form.reset();
    }
}

function showLoginModal() {
    if (loginForm) loginForm.classList.remove('hidden');
    if (registerForm) registerForm.classList.add('hidden');
    showModal('loginModal');
}

function showRegisterModal() {
    if (registerForm) registerForm.classList.remove('hidden');
    if (loginForm) loginForm.classList.add('hidden');
    showModal('loginModal');
}

// ✅ ЛОГИН
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
            if (usernameSpan) usernameSpan.textContent = currentUser.username;
            hideModal('loginModal');
            loadView('files');
        } else {
            alert('❌ ' + (data.detail || 'Ошибка входа'));
        }
    } catch (e) {
        alert('Ошибка подключения');
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
        const data = await res.json();
        if (res.ok || res.status === 201) {
            if (data.token) {
                authToken = data.token;
                localStorage.setItem('cnc_auth_token', data.token);
                currentUser = data.user || { username };
                if (usernameSpan) usernameSpan.textContent = currentUser.username;
                hideModal('loginModal');
                loadView('files');
            } else {
                alert('✅ Регистрация успешна! Теперь войдите.');
                if (registerForm) registerForm.classList.add('hidden');
                if (loginForm) loginForm.classList.remove('hidden');
            }
        } else {
            alert('❌ Ошибка: ' + JSON.stringify(data));
        }
    } catch (e) {
        alert('Ошибка: ' + e.message);
    }
}

async function logout() { clearAuth(); location.reload(); }

// ✅ ЗАГРУЗКА ВИДА
async function loadView(view) {
    currentView = view;
    if (navItems) navItems.forEach(n => n.classList.toggle('active', n.getAttribute('data-view') === view));

    const titles = {
        'files': 'Мои файлы', 'folders': 'Папки', 'documents': 'Документы',
        'section-attendance': '📊 Посещаемость', 'section-rangers': '🤖 Рейнджеры',
        'section-statements': '📋 Ведомости', 'shared': 'Общий доступ', 'logs': 'Журнал'
    };
    if (pageTitle) pageTitle.textContent = titles[view] || 'CNC Office';

    if (uploadBtn) {
        if (view === 'files') {
            uploadBtn.style.display = 'inline-flex';
            uploadBtn.innerHTML = '📤 Загрузить файл';
            uploadBtn.onclick = () => { loadFoldersForDropdown(); showModal('uploadModal'); };
        } else if (view === 'folders') {
            uploadBtn.style.display = 'inline-flex';
            uploadBtn.innerHTML = '📁 Создать папку';
            uploadBtn.onclick = createFolder;
        } else if (view === 'documents' || view?.startsWith('section-')) {
            uploadBtn.style.display = 'inline-flex';
            uploadBtn.innerHTML = '📄 Создать таблицу';
            uploadBtn.onclick = view === 'documents' ? openCreateDocumentModal :
                () => openCreateSectionTableModal(view?.replace('section-', ''));
        } else {
            uploadBtn.style.display = 'none';
        }
    }

    showLoading();
    switch(view) {
        case 'files': await loadFiles(); break;
        case 'folders': await loadFolders(); break;
        case 'documents': await loadDocuments(); break;
        case 'section-attendance': case 'section-rangers': case 'section-statements':
            await loadSectionTable(view?.replace('section-', '')); break;
        case 'shared': await loadShared(); break;
        case 'logs': await loadLogs(); break;
        default: await loadFiles();
    }
}

// ✅ ЗАГРУЗКА ФАЙЛОВ
async function loadFiles() {
    try {
        let url = `${API_BASE}/files/`;
        if (currentFolder) url += `?folder=${currentFolder.id}`;
        const res = await fetch(url, { headers: getAuthHeaders() });
        if (res.status === 200) {
            const data = await res.json();
            renderFiles(data.results || data || []);
        } else if (res.status === 401 || res.status === 403) {
            clearAuth(); showLoginModal();
        } else {
            hideLoading(); showEmpty('Не удалось загрузить');
        }
    } catch (e) {
        console.error('Load files error:', e);
        hideLoading(); showEmpty('Ошибка подключения');
    }
}

function renderFiles(files) {
    hideLoading();
    if (!files?.length) { showEmpty('Нет файлов'); return; }
    hideEmpty();
    if (filesGrid) {
        filesGrid.innerHTML = '';
        files.forEach((f, i) => {
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

// ✅ ЗАГРУЗКА ФАЙЛА
async function uploadFile(file) {
    const fd = new FormData();
    fd.append('file', file);
    if (currentFolder) fd.append('folder', currentFolder.id);
    else if (folderSelect?.value) fd.append('folder', folderSelect.value);
    try {
        const headers = getAuthHeaders(false);
        delete headers['Content-Type'];
        const res = await fetch(`${API_BASE}/files/`, { method: 'POST', headers, body: fd });
        const data = await res.json();
        if (res.ok || res.status === 201) {
            hideModal('uploadModal');
            if (uploadForm) uploadForm.reset();
            await loadFiles();
        } else {
            alert('Ошибка: ' + (data.detail || data.error || 'Неизвестная ошибка'));
        }
    } catch (e) {
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
            a.href = url; a.download = filename;
            document.body.appendChild(a); a.click();
            window.URL.revokeObjectURL(url); document.body.removeChild(a);
        } else {
            alert('Не удалось скачать');
        }
    } catch (e) {
        alert('Ошибка подключения');
    }
}

// ✅ ПРЕДПРОСМОТР
function showPreviewModal(file) {
    const mt = (file.mime_type || '').toLowerCase();
    const ext = (file.file_name || '').split('.').pop().toLowerCase();
    const url = `${API_BASE}/files/${file.id}/download/`;
    if (mt.includes('pdf') || ext === 'pdf') { window.open(url, '_blank'); return; }
    if (!previewModal) { downloadFile(file.id); return; }
    const content = document.getElementById('previewContent');
    const title = document.getElementById('previewTitle');
    if (!content || !title) { downloadFile(file.id); return; }
    title.textContent = file.file_name || 'Файл';
    if (mt.includes('image') || ['jpg','jpeg','png','gif','bmp','svg','webp'].includes(ext)) {
        fetch(url, { headers: getAuthHeaders() }).then(r => r.blob()).then(blob => {
            const imgUrl = URL.createObjectURL(blob);
            content.innerHTML = `<div style="text-align:center;"><img src="${imgUrl}" style="max-width:100%;max-height:80vh;border-radius:8px;"></div>`;
            showModal('previewModal');
        }).catch(() => {
            content.innerHTML = `<p style="color:#ff4466;">Не удалось загрузить</p>`;
            showModal('previewModal');
        });
    } else if (mt.includes('text') || ['txt','json','csv','xml','md','log','py','js','html','css','sql'].includes(ext)) {
        fetch(url, { headers: getAuthHeaders() }).then(r => r.text()).then(text => {
            content.innerHTML = `<pre style="background:#1a1a25;padding:1rem;border-radius:8px;overflow:auto;max-height:80vh;color:#fff;white-space:pre-wrap;font-family:monospace;font-size:13px;">${escapeHtml(text)}</pre>`;
            showModal('previewModal');
        }).catch(() => {
            content.innerHTML = `<p style="color:#ff4466;">Ошибка</p>`;
            showModal('previewModal');
        });
    } else if (mt.includes('video') || ['mp4','avi','mkv','mov','webm','flv'].includes(ext)) {
        content.innerHTML = `<div style="text-align:center;"><video controls style="max-width:100%;max-height:80vh;"><source src="${url}" type="${mt||'video/mp4'}"></video></div>`;
        showModal('previewModal');
    } else if (mt.includes('audio') || ['mp3','wav','ogg','flac','m4a'].includes(ext)) {
        content.innerHTML = `<div style="text-align:center;padding:2rem;"><audio controls style="width:100%;max-width:600px;"><source src="${url}" type="${mt||'audio/mp3'}"></audio></div>`;
        showModal('previewModal');
    } else {
        downloadFile(file.id);
    }
}

// ✅ ЗАГРУЗКА ПАПОК
async function loadFolders() {
    try {
        hideLoading();
        const res = await fetch(`${API_BASE}/folders/`, { headers: getAuthHeaders() });
        if (res.status === 200) {
            const data = await res.json();
            renderFolders(data.results || data || []);
        } else {
            hideLoading(); showEmpty('Нет папок');
        }
    } catch (e) {
        console.error('Folders error:', e);
        hideLoading(); showEmpty('Ошибка');
    }
}

function renderFolders(folders) {
    hideLoading();
    if (!folders?.length) { showEmpty('Нет папок'); return; }
    hideEmpty();
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

// ✅ ЗАГРУЗКА ДОКУМЕНТОВ
async function loadDocuments() {
    try {
        hideLoading();
        const res = await fetch(`${API_BASE}/documents/`, { headers: getAuthHeaders() });
        if (res.status === 200) {
            const data = await res.json();
            renderDocuments(data.results || data || []);
        } else {
            hideLoading(); showEmpty('Нет документов');
        }
    } catch (e) {
        console.error('Documents error:', e);
        hideLoading(); showEmpty('Ошибка');
    }
}

function renderDocuments(docs) {
    hideLoading();
    if (!docs?.length) { showEmpty('Нет документов'); return; }
    hideEmpty();
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
        } else {
            alert('Ошибка открытия');
        }
    } catch (e) {
        console.error('Open error:', e);
        alert('Ошибка: ' + e.message);
    }
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
        else initTextEditor(doc);
    }, 300);
}

// ✅ ИНИЦИАЛИЗАЦИЯ LUCKYSHEET
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

function initTextEditor(doc) {
    const container = document.getElementById('luckysheet-container');
    if (!container) return;
    container.innerHTML = `<textarea style="width:100%;height:100%;padding:1rem;font-family:monospace;font-size:14px;border:none;resize:none;background:#1a1a25;color:#fff;">${doc.content?.text||''}</textarea>`;
}

// ✅ СОХРАНЕНИЕ
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

// ✅ ЭКСПОРТ В EXCEL
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

// ✅ СОЗДАНИЕ ДОКУМЕНТА
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

async function deleteDocument(docId) {
    if (!confirm('Удалить?')) return;
    try {
        const res = await fetch(`${API_BASE}/documents/${docId}/`, { method: 'DELETE', headers: getAuthHeaders() });
        if (res.ok || res.status === 204) await loadDocuments();
        else alert('Ошибка');
    } catch { alert('Ошибка подключения'); }
}

// ✅ РАЗДЕЛЫ (таблицы)
async function loadSectionTable(sectionType) {
    try {
        hideLoading();
        const res = await fetch(`${API_BASE}/section-tables/?section_type=${sectionType}`, { headers: getAuthHeaders() });
        if (res.status === 200) {
            const data = await res.json();
            renderSectionTables(data.results || data || [], sectionType);
        } else { hideLoading(); showEmpty('Нет таблиц'); }
    } catch (e) { console.error('Section error:', e); hideLoading(); showEmpty('Ошибка'); }
}

function renderSectionTables(tables, sectionType) {
    hideLoading();
    if (!tables?.length) { showEmpty('Нет таблиц'); return; }
    hideEmpty();
    if (filesGrid) {
        filesGrid.innerHTML = '';
        tables.forEach(t => {
            const card = document.createElement('div');
            card.className = 'file-card'; card.style.cursor = 'pointer';
            const date = t.updated_at ? new Date(t.updated_at).toLocaleString('ru-RU') : '';
            card.innerHTML = `<div class="file-icon">📊</div><div class="file-name">${escapeHtml(t.title)}</div><div class="file-meta"><span>${sectionType}</span><span>${date}</span></div>`;
            card.onclick = () => openSectionTable(t.id);
            filesGrid.appendChild(card);
        });
    }
}

function openCreateSectionTableModal(sectionType) {
    currentSectionType = sectionType;
    const titleInput = document.getElementById('newDocTitle');
    if (titleInput) titleInput.value = '';
    showModal('createDocumentModal');
}

async function createSectionTable() {
    const title = document.getElementById('newDocTitle')?.value || 'Без названия';
    const sectionType = currentSectionType || 'attendance';
    try {
        const res = await fetch(`${API_BASE}/section-tables/`, {
            method: 'POST', headers: getAuthHeaders(),
            body: JSON.stringify({ title, section_type: sectionType, content: { luckysheet: [] } })
        });
        if (res.ok) { hideModal('createDocumentModal'); await loadSectionTable(sectionType); }
        else alert('Ошибка создания');
    } catch (e) { alert('Ошибка подключения'); }
}

async function openSectionTable(tableId) {
    try {
        const res = await fetch(`${API_BASE}/section-tables/${tableId}/`, { headers: getAuthHeaders() });
        if (res.ok) {
            currentDocument = await res.json();
            currentDocument.doc_type = 'spreadsheet';
            showDocumentEditor(currentDocument);
        } else alert('Ошибка открытия');
    } catch (e) { console.error('Open table error:', e); alert('Ошибка'); }
}

async function deleteSectionTable(tableId) {
    if (!confirm('Удалить?')) return;
    try {
        const res = await fetch(`${API_BASE}/section-tables/${tableId}/`, { method: 'DELETE', headers: getAuthHeaders() });
        if (res.ok || res.status === 204) await loadSectionTable(currentSectionType || 'attendance');
        else alert('Ошибка');
    } catch { alert('Ошибка подключения'); }
}

// ✅ ОБЩИЙ ДОСТУП
async function loadShared() {
    try {
        hideLoading();
        const res = await fetch(`${API_BASE}/permissions/`, { headers: getAuthHeaders() });
        if (res.status === 200) {
            const data = await res.json();
            renderShared(data.results || data || []);
        } else { hideLoading(); showEmpty('Нет доступа'); }
    } catch (e) { console.error('Shared error:', e); hideLoading(); showEmpty('Ошибка'); }
}

function renderShared(perms) {
    hideLoading();
    if (!perms?.length) { showEmpty('Нет общего доступа'); return; }
    hideEmpty();
    if (filesGrid) {
        filesGrid.innerHTML = '';
        perms.forEach(p => {
            const card = document.createElement('div');
            card.className = 'file-card'; card.style.cursor = 'pointer';
            const name = p.file_name || `Файл #${p.file}`;
            const user = p.user?.username || 'Неизвестно';
            card.innerHTML = `<div class="file-icon">🔗</div><div class="file-name">${escapeHtml(name)}</div><div class="file-meta"><span>${user}</span></div>`;
            card.onclick = () => downloadFile(p.file);
            filesGrid.appendChild(card);
        });
    }
}

// ✅ ЛОГИ
async function loadLogs() {
    try {
        hideLoading();
        const res = await fetch(`${API_BASE}/audit-logs/`, { headers: getAuthHeaders() });
        if (res.status === 200) {
            const data = await res.json();
            renderLogs(data.results || data || []);
        } else { hideLoading(); showEmpty('Нет записей'); }
    } catch (e) { console.error('Logs error:', e); hideLoading(); showEmpty('Ошибка'); }
}

function renderLogs(logs) {
    hideLoading();
    if (!logs?.length) { showEmpty('Нет записей'); return; }
    hideEmpty();
    if (filesGrid) {
        filesGrid.innerHTML = '';
        const icons = { upload:'📤', download:'⬇️', delete:'🗑️', share:'🔗', login:'🔑', logout:'🚪' };
        logs.forEach(l => {
            const card = document.createElement('div');
            card.className = 'file-card';
            const icon = icons[l.action] || '📝';
            const date = l.timestamp ? new Date(l.timestamp).toLocaleString('ru-RU') : '';
            const user = l.user_username || l.user?.username || 'Система';
            card.innerHTML = `<div class="file-icon">${icon}</div><div class="file-name">${escapeHtml(l.action)}</div><div class="file-meta"><span>${user}</span><span>${date}</span></div>`;
            filesGrid.appendChild(card);
        });
    }
}

// ✅ УТИЛИТЫ
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

// ✅ СОБЫТИЯ
function setupEventListeners() {
    if (logoutBtn) logoutBtn.onclick = logout;
    if (uploadForm) uploadForm.onsubmit = handleUpload;
    if (loginForm) loginForm.onsubmit = handleLogin;
    if (registerForm) registerForm.onsubmit = handleRegister;

    const tR = document.getElementById('toggleToRegister');
    if (tR) tR.onclick = (e) => { e.preventDefault(); showRegisterModal(); };
    const tL = document.getElementById('toggleToLogin');
    if (tL) tL.onclick = (e) => { e.preventDefault(); showLoginModal(); };

    if (navItems) navItems.forEach(item => {
        item.onclick = (e) => {
            e.preventDefault();
            const view = item.getAttribute('data-view');
            if (view) loadView(view);
        };
    });

    [uploadModal, loginModal, previewModal, documentModal, createDocumentModalEl].forEach(modal => {
        if (modal) modal.onclick = (e) => { if (e.target === modal) hideModal(modal); };
    });
}
