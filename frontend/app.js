// ==================== CNC Office - Frontend App v4.0 ====================
const API_BASE = '/api';
let currentUser = null;
let currentFolder = null;
let currentView = 'files';
let currentDocument = null;
let authToken = localStorage.getItem('cnc_auth_token');

// DOM Elements
const filesGrid = document.getElementById('filesGrid');
const loadingState = document.getElementById('loadingState');
const emptyState = document.getElementById('emptyState');
const pageTitle = document.getElementById('pageTitle');
const uploadModal = document.getElementById('uploadModal');
const loginModal = document.getElementById('loginModal');
const previewModal = document.getElementById('previewModal');
const documentModal = document.getElementById('documentModal');
const createDocumentModal = document.getElementById('createDocumentModal');
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
    console.log('🚀 App initialized v4.0');
    setupEventListeners();
    checkAuth();
});

// ✅ Заголовки с токеном
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
        } else { clearAuth(); showLoginModal(); }
    } catch (e) { console.error('Auth check failed:', e); clearAuth(); showLoginModal(); }
}

// ✅ Модалки
function showModal(modal) {
    if (modal) { modal.classList.add('show'); modal.style.display = 'flex'; document.body.style.overflow = 'hidden'; }
}
function hideModal(modal) {
    const el = typeof modal === 'string' ? document.getElementById(modal) : modal;
    if (el) {
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

// ✅ Вход
async function handleLogin(e) {
    e.preventDefault();
    const username = document.getElementById('loginUsername')?.value;
    const password = document.getElementById('loginPassword')?.value;
    if (!username || !password) { alert('Введите логин и пароль'); return; }
    try {
        const res = await fetch(`${API_BASE}/users/login/`, {
            method: 'POST', headers: getAuthHeaders(),
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
        } else { alert(`Ошибка: ${data.detail || 'Неверный логин или пароль'}`); }
    } catch (e) { console.error('Login error:', e); alert('Ошибка подключения к серверу'); }
}

// ✅ Регистрация
async function handleRegister(e) {
    e.preventDefault();
    const username = document.getElementById('registerUsername')?.value;
    const email = document.getElementById('registerEmail')?.value;
    const password = document.getElementById('registerPassword')?.value;
    const password2 = document.getElementById('registerPassword2')?.value;
    if (!username || !email || !password || !password2) { alert('Заполните все поля'); return; }
    if (password !== password2) { alert('Пароли не совпадают'); return; }
    if (password.length < 8) { alert('Пароль минимум 8 символов'); return; }
    try {
        const res = await fetch(`${API_BASE}/users/register/`, {
            method: 'POST', headers: getAuthHeaders(),
            body: JSON.stringify({ username, email, password, password2 })
        });
        const data = await res.json();
        if (res.ok || res.status === 201) {
            if (data.token) {
                authToken = data.token;
                localStorage.setItem('cnc_auth_token', data.token);
                localStorage.setItem('cnc_username', data.user?.username || username);
                currentUser = data.user || { username };
                if (usernameSpan) usernameSpan.textContent = currentUser.username;
                hideModal('loginModal');
                loadView('files');
            } else {
                alert('✅ Регистрация успешна! Теперь войдите в систему.');
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
    } catch (e) { console.error('Register error:', e); alert('Ошибка подключения: ' + e.message); }
}

// ✅ Выход
async function logout() { clearAuth(); location.reload(); }

// ✅ Навигация по вкладкам
async function loadView(view) {
    currentView = view;
    navItems.forEach(n => n.classList.toggle('active', n.getAttribute('data-view') === view));
    const titles = { files: 'Мои файлы', folders: 'Папки', documents: 'Документы', shared: 'Общий доступ', logs: 'Журнал аудита' };
    if (pageTitle) pageTitle.textContent = titles[view] || 'CNC Office';

    if (uploadBtn) {
        if (view === 'files') {
            uploadBtn.style.display = 'inline-flex';
            uploadBtn.innerHTML = '📤 Загрузить файл';
            uploadBtn.onclick = () => { loadFoldersForDropdown(); showModal(uploadModal); };
        } else if (view === 'folders') {
            uploadBtn.style.display = 'inline-flex';
            uploadBtn.innerHTML = '📁 Создать папку';
            uploadBtn.onclick = createFolder;
        } else if (view === 'documents') {
            uploadBtn.style.display = 'inline-flex';
            uploadBtn.innerHTML = '📄 Создать документ';
            uploadBtn.onclick = createDocumentModal;
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
        case 'shared': await loadShared(); break;
        case 'logs': await loadLogs(); break;
        default: await loadFiles();
    }
}

// ==================== ФАЙЛЫ ====================
async function loadFiles() {
    console.log('🔄 Loading files...');
    try {
        let url = `${API_BASE}/files/`;
        if (currentFolder) url += `?folder=${currentFolder.id}`;
        const res = await fetch(url, { headers: getAuthHeaders() });
        console.log('📦 Response status:', res.status);
        if (res.status === 200) {
            const data = await res.json();
            const files = data.results || data || [];
            renderFiles(files);
        } else if (res.status === 401 || res.status === 403) { clearAuth(); showLoginModal(); }
        else { const text = await res.text(); console.error('❌ Files error:', res.status, text); showEmpty('Не удалось загрузить файлы'); }
    } catch (e) { console.error('❌ Load files error:', e); showEmpty('Ошибка подключения'); }
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
    card.onclick = (e) => { if (!e.target.closest('.file-actions')) { const mt = (file.mime_type||'').toLowerCase(); if(mt.includes('image')||mt.includes('pdf')||mt.includes('text')||mt.includes('json')) showPreviewModal(file); else downloadFile(file.id); } };
    const icon = getFileIcon(file.mime_type);
    let name = file.file_name || (file.file ? file.file.split('/').pop() : 'Без имени');
    try { name = decodeURIComponent(name); } catch {}
    const size = file.size_mb ? `${file.size_mb} MB` : file.size ? `${(file.size/1024/1024).toFixed(2)} MB` : '0 MB';
    const date = file.uploaded_at ? new Date(file.uploaded_at).toLocaleDateString('ru-RU') : '';
    const canAct = file.owner === currentUser?.username;
    card.innerHTML = `
        <div class="file-icon">${icon}</div>
        <div class="file-name" title="${escapeHtml(name)}">${escapeHtml(name)}</div>
        <div class="file-meta"><span>${size}</span><span>${date}</span></div>
        <div class="file-actions">
            ${canAct ? `<button class="file-action-btn" onclick="event.stopPropagation();downloadFile(${file.id})" title="Скачать">⬇️</button>` : ''}
            ${canAct ? `<button class="file-action-btn" onclick="event.stopPropagation();shareFile(${file.id})" title="Поделиться">🔗</button>` : ''}
            ${canAct ? `<button class="file-action-btn" onclick="event.stopPropagation();deleteFile(${file.id})" title="Удалить">🗑️</button>` : ''}
        </div>`;
    return card;
}

function getFileIcon(mimeType) {
    if (!mimeType) return '📄';
    const mt = mimeType.toLowerCase();
    if (mt.includes('excel')||mt.includes('spreadsheet')||mt.includes('ms-excel')||mt.includes('.xls')||mt.includes('.xlsx')) return '📊';
    if (mt.includes('word')||mt.includes('.doc')||mt.includes('.docx')) return '📝';
    if (mt.includes('powerpoint')||mt.includes('.ppt')||mt.includes('.pptx')) return '📽️';
    if (mt.includes('pdf')) return '📄';
    if (mt.includes('image')) return '🖼️';
    if (mt.includes('video')) return '🎬';
    if (mt.includes('audio')) return '🎵';
    if (mt.includes('text')) return '📝';
    if (mt.includes('zip')||mt.includes('archive')) return '📦';
    return '📄';
}

async function uploadFile(file) {
    console.log('📤 Uploading:', file.name);
    const fd = new FormData();
    fd.append('file', file);
    if (currentFolder) fd.append('folder', currentFolder.id);
    else if (folderSelect?.value) fd.append('folder', folderSelect.value);
    try {
        const res = await fetch(`${API_BASE}/files/`, { method: 'POST', headers: getAuthHeaders(false), body: fd });
        console.log('📤 Response:', res.status);
        const data = await res.json().catch(() => ({}));
        if (res.ok || res.status === 201) { hideModal('uploadModal'); if (uploadForm) uploadForm.reset(); await loadFiles(); }
        else { const err = data.detail || data.file?.[0] || data.error || 'Неизвестная ошибка'; console.error('❌ Upload failed:', err); alert(`Ошибка: ${err}`); }
    } catch (e) { console.error('❌ Upload error:', e); alert('Ошибка подключения: ' + e.message); }
}

async function handleUpload(e) { e.preventDefault(); const fi = document.getElementById('fileInput'); if (!fi?.files[0]) { alert('Выберите файл'); return; } await uploadFile(fi.files[0]); }

async function downloadFile(fileId) {
    try {
        const res = await fetch(`${API_BASE}/files/${fileId}/download/`, { headers: getAuthHeaders() });
        if (res.ok) {
            const blob = await res.blob();
            const disposition = res.headers.get('Content-Disposition');
            let filename = `file_${fileId}`;
            if (disposition) {
                const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
                const normalMatch = disposition.match(/filename="([^"]+)"/i);
                if (utf8Match && utf8Match[1]) filename = decodeURIComponent(utf8Match[1]);
                else if (normalMatch && normalMatch[1]) filename = normalMatch[1];
            }
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a'); a.href = url; a.download = filename;
            document.body.appendChild(a); a.click();
            window.URL.revokeObjectURL(url); document.body.removeChild(a);
        } else if (res.status === 401 || res.status === 403) { clearAuth(); showLoginModal(); }
        else { const err = await res.json().catch(() => ({})); alert(`Ошибка: ${err.detail || 'Не удалось скачать'}`); }
    } catch (e) { console.error('Download error:', e); alert('Ошибка подключения'); }
}

async function shareFile(fileId) {
    const username = prompt('Имя пользователя:'); if (!username) return;
    try {
        const res = await fetch(`${API_BASE}/files/${fileId}/share/`, { method: 'POST', headers: getAuthHeaders(), body: JSON.stringify({ username, permission: 'read' }) });
        const data = await res.json().catch(() => ({}));
        alert(res.ok ? `✅ Доступ предоставлен ${username}` : `❌ ${data.detail || 'Ошибка'}`);
    } catch { alert('Ошибка подключения'); }
}

async function deleteFile(fileId) {
    if (!confirm('Удалить файл?')) return;
    try {
        const res = await fetch(`${API_BASE}/files/${fileId}/`, { method: 'DELETE', headers: getAuthHeaders() });
        if (res.ok || res.status === 204) await loadFiles(); else alert('Ошибка удаления');
    } catch { alert('Ошибка подключения'); }
}

// ✅ Предпросмотр файлов
function showPreviewModal(file) {
    const mt = (file.mime_type || '').toLowerCase();
    if (mt.includes('pdf')) { downloadFile(file.id); return; }
    if (!previewModal) { downloadFile(file.id); return; }
    const previewContent = document.getElementById('previewContent');
    const previewTitle = document.getElementById('previewTitle');
    if (!previewContent || !previewTitle) { downloadFile(file.id); return; }
    previewTitle.textContent = file.file_name || 'Файл';
    const downloadUrl = `${API_BASE}/files/${file.id}/download/`;
    if (mt.includes('image')) {
        fetch(downloadUrl, { headers: getAuthHeaders() }).then(res => res.blob()).then(blob => {
            const imgUrl = URL.createObjectURL(blob);
            previewContent.innerHTML = `<div style="text-align:center;"><img src="${imgUrl}" style="max-width:100%;max-height:80vh;border-radius:8px;" alt="${escapeHtml(file.file_name)}"></div>`;
            showModal(previewModal);
        }).catch(() => { previewContent.innerHTML = `<div style="text-align:center;padding:2rem;"><p style="color:#ff4466;">Не удалось загрузить</p><button class="btn btn-primary" onclick="downloadFile(${file.id});hideModal('previewModal');" style="margin-top:1rem;">⬇️ Скачать</button></div>`; showModal(previewModal); });
    } else if (mt.includes('text')||mt.includes('json')||mt.includes('xml')||mt.includes('plain')) {
        fetch(downloadUrl, { headers: getAuthHeaders() }).then(res => res.text()).then(text => {
            previewContent.innerHTML = `<pre style="background:#1a1a25;padding:1rem;border-radius:8px;overflow:auto;max-height:80vh;color:#fff;white-space:pre-wrap;word-wrap:break-word;">${escapeHtml(text)}</pre>`;
            showModal(previewModal);
        }).catch(() => { previewContent.innerHTML = `<div style="text-align:center;padding:2rem;"><p style="color:#ff4466;">Не удалось загрузить</p><button class="btn btn-primary" onclick="downloadFile(${file.id});hideModal('previewModal');" style="margin-top:1rem;">⬇️ Скачать</button></div>`; showModal(previewModal); });
    } else { downloadFile(file.id); }
}

// ==================== ПАПКИ ====================
async function loadFoldersForDropdown() {
    if (!folderSelect) return;
    folderSelect.innerHTML = '<option value="">Корневая папка</option>';
    try {
        const res = await fetch(`${API_BASE}/folders/`, { headers: getAuthHeaders() });
        if (res.status === 200) {
            const data = await res.json();
            const folders = data.results || data || [];
            folders.forEach(folder => { const option = document.createElement('option'); option.value = folder.id; option.textContent = folder.name; folderSelect.appendChild(option); });
            console.log('📁 Folders loaded:', folders.length);
        }
    } catch (e) { console.error('❌ Load folders for dropdown error:', e); }
}

async function loadFolders() {
    console.log('📁 Loading folders...');
    try {
        const res = await fetch(`${API_BASE}/folders/`, { headers: getAuthHeaders() });
        if (res.status === 200) { const data = await res.json(); const folders = data.results || data || []; renderFolders(folders); }
        else if (res.status === 401 || res.status === 403) { clearAuth(); showLoginModal(); }
        else { showEmpty('Не удалось загрузить папки'); }
    } catch (e) { console.error('❌ Load folders error:', e); showEmpty('Ошибка подключения'); }
}

function renderFolders(folders) {
    hideLoading();
    if (!folders?.length) { showEmpty('Нет папок'); return; }
    hideEmpty();
    if (filesGrid) { filesGrid.innerHTML = ''; folders.forEach((f, i) => filesGrid.appendChild(createFolderCard(f, i))); }
}

function createFolderCard(folder, index) {
    const card = document.createElement('div');
    card.className = 'file-card';
    card.style.animationDelay = `${index * 0.1}s`;
    card.style.cursor = 'pointer';
    card.onclick = (e) => { if (!e.target.closest('.file-actions')) { currentFolder = folder; currentView = 'files'; loadView('files'); } };
    const date = folder.created_at ? new Date(folder.created_at).toLocaleDateString('ru-RU') : '';
    card.innerHTML = `
        <div class="file-icon">📁</div>
        <div class="file-name" title="${escapeHtml(folder.name)}">${escapeHtml(folder.name)}</div>
        <div class="file-meta"><span>${folder.files_count || 0} файлов</span><span>${date}</span></div>
        <div class="file-actions"><button class="file-action-btn" onclick="event.stopPropagation();deleteFolder(${folder.id})" title="Удалить">🗑️</button></div>`;
    return card;
}

async function createFolder() {
    const name = prompt('Имя папки:'); if (!name?.trim()) return;
    try {
        const res = await fetch(`${API_BASE}/folders/`, { method: 'POST', headers: getAuthHeaders(), body: JSON.stringify({ name: name.trim() }) });
        if (res.ok) { await loadFolders(); } else { const err = await res.json().catch(() => ({})); alert(`Ошибка: ${err.detail || err.name?.[0] || 'Неизвестная ошибка'}`); }
    } catch (e) { console.error('Create folder error:', e); alert('Ошибка подключения'); }
}

async function deleteFolder(id) {
    if (!confirm('Удалить папку?')) return;
    try {
        const res = await fetch(`${API_BASE}/folders/${id}/`, { method: 'DELETE', headers: getAuthHeaders() });
        if (res.ok || res.status === 204) await loadFolders(); else alert('Ошибка удаления');
    } catch { alert('Ошибка подключения'); }
}

// ==================== ДОКУМЕНТЫ ====================
async function loadDocuments() {
    console.log('📄 Loading documents...');
    try {
        const res = await fetch(`${API_BASE}/documents/`, { headers: getAuthHeaders() });
        if (res.status === 200) { const data = await res.json(); const docs = data.results || data || []; renderDocuments(docs); }
        else { showEmpty('Не удалось загрузить документы'); }
    } catch (e) { console.error('❌ Load documents error:', e); showEmpty('Ошибка подключения'); }
}

function renderDocuments(docs) {
    hideLoading();
    if (!docs?.length) { showEmpty('Нет документов'); return; }
    hideEmpty();
    if (filesGrid) { filesGrid.innerHTML = ''; docs.forEach((d, i) => filesGrid.appendChild(createDocumentCard(d, i))); }
}

function createDocumentCard(doc, index) {
    const card = document.createElement('div');
    card.className = 'file-card';
    card.style.animationDelay = `${index * 0.1}s`;
    card.style.cursor = 'pointer';
    card.onclick = (e) => { if (!e.target.closest('.file-actions')) openDocument(doc.id); };
    const icon = doc.doc_type === 'spreadsheet' ? '📊' : '📝';
    const date = doc.updated_at ? new Date(doc.updated_at).toLocaleString('ru-RU') : '';
    const canEdit = doc.is_editable || doc.owner_username === currentUser?.username;
    card.innerHTML = `
        <div class="file-icon">${icon}</div>
        <div class="file-name" title="${escapeHtml(doc.title)}">${escapeHtml(doc.title)}</div>
        <div class="file-meta"><span>${doc.doc_type === 'spreadsheet' ? 'Таблица' : 'Текст'}</span><span>${date}</span></div>
        <div class="file-actions">
            ${canEdit ? `<button class="file-action-btn" onclick="event.stopPropagation();openDocument(${doc.id})" title="Открыть">✏️</button>` : ''}
            ${canEdit ? `<button class="file-action-btn" onclick="event.stopPropagation();shareDocument(${doc.id})" title="Поделиться">🔗</button>` : ''}
        </div>`;
    return card;
}

async function openDocument(docId) {
    try {
        const res = await fetch(`${API_BASE}/documents/${docId}/`, { headers: getAuthHeaders() });
        if (res.ok) { currentDocument = await res.json(); showDocumentEditor(currentDocument); }
        else { alert('Ошибка открытия документа'); }
    } catch (e) { console.error('Open document error:', e); alert('Ошибка подключения'); }
}

function showDocumentEditor(doc) {
    const editor = document.getElementById('documentEditor');
    const title = document.getElementById('documentTitle');
    if (!editor || !title) return;
    title.textContent = doc.title;
    if (doc.doc_type === 'spreadsheet') {
        editor.innerHTML = `<div style="overflow:auto;"><table id="docTable" style="border-collapse:collapse;width:100%;"><tbody>${renderTable(doc.content)}</tbody></table></div>`;
        makeTableEditable();
    } else {
        editor.innerHTML = `<textarea id="docText" style="width:100%;height:100%;padding:1rem;font-family:monospace;font-size:14px;border:1px solid #ddd;border-radius:4px;">${doc.content?.text || ''}</textarea>`;
    }
    showModal('documentModal');
}

function renderTable(content) {
    const data = content?.cells || [['', '', '', '', ''], ['', '', '', '', ''], ['', '', '', '', '']];
    return data.map(row => `<tr>${row.map(cell => `<td style="border:1px solid #ddd;padding:8px;min-width:100px;"><div contenteditable="true">${cell || ''}</div></td>`).join('')}</tr>`).join('');
}

function makeTableEditable() {
    const table = document.getElementById('docTable');
    if (!table) return;
    const cells = table.querySelectorAll('td div[contenteditable]');
    cells.forEach(cell => { cell.addEventListener('input', () => {}); });
}

async function saveDocument() {
    if (!currentDocument) return;
    let content = {};
    if (currentDocument.doc_type === 'spreadsheet') {
        const table = document.getElementById('docTable');
        if (table) {
            const rows = table.querySelectorAll('tr');
            const cells = [];
            rows.forEach(row => { const rowData = []; row.querySelectorAll('td div').forEach(cell => rowData.push(cell.textContent)); cells.push(rowData); });
            content = { cells };
        }
    } else {
        const text = document.getElementById('docText');
        if (text) content = { text: text.value };
    }
    try {
        const res = await fetch(`${API_BASE}/documents/${currentDocument.id}/save_content/`, {
            method: 'POST', headers: getAuthHeaders(), body: JSON.stringify({ content })
        });
        if (res.ok) { alert('✅ Сохранено'); currentDocument.content = content; }
        else { alert('Ошибка сохранения'); }
    } catch (e) { console.error('Save error:', e); alert('Ошибка подключения'); }
}

function createDocumentModal() {
    document.getElementById('newDocTitle').value = '';
    document.getElementById('newDocType').value = 'spreadsheet';
    showModal('createDocumentModal');
}

async function createDocument() {
    const title = document.getElementById('newDocTitle').value || 'Без названия';
    const docType = document.getElementById('newDocType').value;
    try {
        const res = await fetch(`${API_BASE}/documents/`, {
            method: 'POST', headers: getAuthHeaders(), body: JSON.stringify({ title, doc_type: docType, content: {} })
        });
        if (res.ok) { hideModal('createDocumentModal'); await loadDocuments(); }
        else { const err = await res.json().catch(() => ({})); alert(`Ошибка: ${err.detail || 'Неизвестная ошибка'}`); }
    } catch (e) { console.error('Create document error:', e); alert('Ошибка подключения'); }
}

async function shareDocument(docId) {
    const username = prompt('Имя пользователя:'); if (!username) return;
    try {
        const res = await fetch(`${API_BASE}/documents/${docId}/share/`, {
            method: 'POST', headers: getAuthHeaders(), body: JSON.stringify({ username, permission: 'write' })
        });
        const data = await res.json().catch(() => ({}));
        alert(res.ok ? `✅ Доступ предоставлен ${username}` : `❌ ${data.detail || 'Ошибка'}`);
    } catch { alert('Ошибка подключения'); }
}

// ==================== ОБЩИЙ ДОСТУП ====================
async function loadShared() {
    console.log('🔗 Loading shared...');
    try {
        const res = await fetch(`${API_BASE}/permissions/`, { headers: getAuthHeaders() });
        if (res.status === 200) { const data = await res.json(); const perms = data.results || data || []; renderShared(perms); }
        else if (res.status === 401 || res.status === 403) { clearAuth(); showLoginModal(); }
        else { showEmpty('Не удалось загрузить'); }
    } catch (e) { console.error('❌ Load shared error:', e); showEmpty('Ошибка подключения'); }
}

function renderShared(perms) {
    hideLoading();
    if (!perms?.length) { showEmpty('Нет общего доступа'); return; }
    hideEmpty();
    if (filesGrid) { filesGrid.innerHTML = ''; perms.forEach((p, i) => filesGrid.appendChild(createSharedCard(p, i))); }
}

function createSharedCard(perm, index) {
    const card = document.createElement('div');
    card.className = 'file-card';
    card.style.animationDelay = `${index * 0.1}s`;
    card.style.cursor = 'pointer';
    card.onclick = (e) => { if (!e.target.closest('.file-actions')) downloadFile(perm.file); };
    const name = perm.file_name || `Файл #${perm.file}`;
    const user = perm.user?.username || 'Неизвестно';
    const badge = perm.permission === 'write' ? '<span style="background:#10B981;color:#fff;padding:2px 8px;border-radius:12px;font-size:0.75rem">✏️ Запись</span>' : '<span style="background:#6B7280;color:#fff;padding:2px 8px;border-radius:12px;font-size:0.75rem">👁️ Чтение</span>';
    card.innerHTML = `
        <div class="file-icon">🔗</div>
        <div class="file-name" title="${escapeHtml(name)}">${escapeHtml(name)}</div>
        <div class="file-meta">${badge}<span>${user}</span></div>
        <div class="file-actions">
            <button class="file-action-btn" onclick="event.stopPropagation();downloadFile(${perm.file})" title="Скачать">⬇️</button>
            <button class="file-action-btn" onclick="event.stopPropagation();revokePermission(${perm.id})" title="Отозвать">❌</button>
        </div>`;
    return card;
}

async function revokePermission(id) {
    if (!confirm('Отозвать доступ?')) return;
    try {
        const res = await fetch(`${API_BASE}/permissions/${id}/`, { method: 'DELETE', headers: getAuthHeaders() });
        if (res.ok || res.status === 204) await loadShared(); else alert('Ошибка');
    } catch { alert('Ошибка подключения'); }
}

// ==================== ЛОГИ ====================
async function loadLogs() {
    console.log('📋 Loading logs...');
    try {
        const res = await fetch(`${API_BASE}/audit-logs/`, { headers: getAuthHeaders() });
        if (res.status === 200) { const data = await res.json(); const logs = data.results || data || []; renderLogs(logs); }
        else if (res.status === 401 || res.status === 403) { clearAuth(); showLoginModal(); }
        else { showEmpty('Не удалось загрузить'); }
    } catch (e) { console.error('❌ Load logs error:', e); showEmpty('Ошибка подключения'); }
}

function renderLogs(logs) {
    hideLoading();
    if (!logs?.length) { showEmpty('Нет записей в логах'); return; }
    hideEmpty();
    if (filesGrid) { filesGrid.innerHTML = ''; logs.forEach((l, i) => filesGrid.appendChild(createLogCard(l, i))); }
}

function createLogCard(log, index) {
    const card = document.createElement('div');
    card.className = 'file-card';
    card.style.animationDelay = `${index * 0.1}s`;
    const icons = { upload: '📤', download: '⬇️', delete: '🗑️', share: '🔗', login: '🔑', logout: '🚪', create_folder: '📁' };
    const icon = icons[log.action] || '📝';
    const date = log.timestamp ? new Date(log.timestamp).toLocaleString('ru-RU') : '';
    const user = log.user_username || log.user?.username || 'Система';
    card.innerHTML = `
        <div class="file-icon">${icon}</div>
        <div class="file-name">${escapeHtml(log.action)}</div>
        <div class="file-meta"><span>${user}</span><span>${date}</span></div>
        ${log.details ? `<div style="margin-top:0.5rem;font-size:0.75rem;color:var(--text-muted);">${escapeHtml(log.details)}</div>` : ''}`;
    return card;
}

// ==================== UI Helpers ====================
function showLoading() { if (loadingState) { loadingState.classList.add('show'); loadingState.style.display = 'flex'; } if (emptyState) emptyState.classList.remove('show'); if (filesGrid) filesGrid.style.display = 'none'; }
function hideLoading() { if (loadingState) { loadingState.classList.remove('show'); loadingState.style.display = 'none'; } if (filesGrid) filesGrid.style.display = 'grid'; }
function showEmpty(msg) { if (emptyState) { emptyState.classList.add('show'); emptyState.style.display = 'flex'; const p = emptyState.querySelector('p'); if (p && msg) p.textContent = msg; } if (filesGrid) filesGrid.style.display = 'none'; if (loadingState) loadingState.style.display = 'none'; }
function hideEmpty() { if (emptyState) { emptyState.classList.remove('show'); emptyState.style.display = 'none'; } }

// ==================== Event Listeners ====================
function setupEventListeners() {
    if (uploadBtn) {
        uploadBtn.onclick = () => {
            if (currentView === 'files') { loadFoldersForDropdown(); showModal(uploadModal); }
            else if (currentView === 'folders') { createFolder(); }
            else if (currentView === 'documents') { createDocumentModal(); }
        };
    }
    if (logoutBtn) logoutBtn.onclick = logout;
    if (uploadForm) uploadForm.onsubmit = handleUpload;
    if (loginForm) loginForm.onsubmit = handleLogin;
    if (registerForm) registerForm.onsubmit = handleRegister;
    const tR = document.getElementById('toggleToRegister'); if (tR) tR.onclick = (e) => { e.preventDefault(); showRegisterModal(); };
    const tL = document.getElementById('toggleToLogin'); if (tL) tL.onclick = (e) => { e.preventDefault(); showLoginModal(); };
    navItems.forEach(item => { item.onclick = (e) => { e.preventDefault(); const view = item.getAttribute('data-view'); if (view) loadView(view); }; });
    [uploadModal, loginModal, previewModal, documentModal, createDocumentModal].forEach(modal => { if (modal) modal.onclick = (e) => { if (e.target === modal) hideModal(modal); }; });
    const closeBtn = document.getElementById('closeModal'); if (closeBtn) closeBtn.onclick = () => hideModal('uploadModal');
    const dz = document.querySelector('.content-area') || document.body;
    if (dz) {
        ['dragenter','dragover','dragleave','drop'].forEach(ev => dz.addEventListener(ev, e => { e.preventDefault(); e.stopPropagation(); }, false));
        ['dragenter','dragover'].forEach(ev => dz.addEventListener(ev, () => { dz.style.border='3px dashed var(--primary-color)'; dz.style.borderRadius='12px'; }, false));
        ['dragleave','drop'].forEach(ev => dz.addEventListener(ev, () => { dz.style.border=''; dz.style.borderRadius=''; }, false));
        dz.addEventListener('drop', e => { if (currentView === 'files' && e.dataTransfer.files[0]) uploadFile(e.dataTransfer.files[0]); }, false);
    }
}
