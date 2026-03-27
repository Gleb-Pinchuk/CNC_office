// ==================== CNC Office - Frontend App v19.1 (Luckysheet Fixed) ====================
const API_BASE = '/api';
let currentUser = null;
let currentFolder = null;
let currentView = 'files';
let currentDocument = null;
let currentSectionType = null;
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
    console.log('🚀 App initialized v19.1 with Luckysheet');
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
        console.error('Auth check failed:', e);
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
    }
}

// ✅ Скрыть модальное окно
function hideModal(modal) {
    const el = typeof modal === 'string' ? document.getElementById(modal) : modal;
    if (el) {
        if (el.id === 'documentModal') {
            if (currentDocument) saveDocumentSilent();
            if (typeof window.luckysheet !== 'undefined') {
                try { window.luckysheet.destroy(); } catch(e) {}
            }
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

// ✅ ЛОГИН
async function handleLogin(e) {
    e.preventDefault();
    const username = document.getElementById('loginUsername')?.value?.trim();
    const password = document.getElementById('loginPassword')?.value;

    if (!username || !password) { alert('Введите логин и пароль'); return; }

    try {
        const res = await fetch(`${API_BASE}/users/login/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
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
            loadView('files');
        } else {
            const errorMsg = data.detail || data.non_field_errors?.[0] || 'Неверный логин или пароль';
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
                loadView('files');
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
    navItems.forEach(n => n.classList.toggle('active', n.getAttribute('data-view') === view));

    const titles = {
        'files': 'Мои файлы',
        'folders': 'Папки',
        'documents': 'Документы',
        'section-attendance': '📊 Посещаемость',
        'section-rangers': '🤖 Цифровые рейнджеры',
        'section-statements': '📋 Ведомости',
        'shared': 'Общий доступ',
        'logs': 'Журнал аудита'
    };
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
        } else if (view === 'documents' || view?.startsWith('section-')) {
            uploadBtn.style.display = 'inline-flex';
            uploadBtn.innerHTML = '📄 Создать таблицу';
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
}

// ✅ ЗАГРУЗКА ФАЙЛОВ
async function loadFiles() {
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
            ${canAct ? `<button class="file-action-btn" onclick="event.stopPropagation();downloadFile(${file.id})">⬇️</button>` : ''}
            ${canAct ? `<button class="file-action-btn" onclick="event.stopPropagation();shareFile(${file.id})">🔗</button>` : ''}
            ${canAct ? `<button class="file-action-btn" onclick="event.stopPropagation();deleteFile(${file.id})">🗑️</button>` : ''}
        </div>`;
    return card;
}

function getFileIcon(mimeType) {
    if (!mimeType) return '📄';
    const mt = mimeType.toLowerCase();
    if (mt.includes('excel')||mt.includes('spreadsheet')) return '📊';
    if (mt.includes('word')||mt.includes('.doc')) return '📝';
    if (mt.includes('pdf')) return '📄';
    if (mt.includes('image')) return '🖼️';
    if (mt.includes('video')) return '🎬';
    if (mt.includes('audio')) return '🎵';
    if (mt.includes('zip')) return '📦';
    return '📄';
}

// ✅ ЗАГРУЗКА ФАЙЛА
async function uploadFile(file) {
    console.log('📤 Uploading:', file.name, file.size, 'bytes');
    const fd = new FormData();
    fd.append('file', file);
    if (currentFolder) fd.append('folder', currentFolder.id);
    else if (folderSelect?.value) fd.append('folder', folderSelect.value);

    try {
        const headers = getAuthHeaders(false);
        delete headers['Content-Type'];

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
    try {
        const res = await fetch(`${API_BASE}/files/${fileId}/share/`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({ username, permission: 'read' })
        });
        const data = await res.json().catch(() => ({}));
        alert(res.ok ? `✅ Доступ предоставлен ${username}` : `❌ ${data.detail || 'Ошибка'}`);
    } catch {
        alert('Ошибка подключения');
    }
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
                previewContent.innerHTML = `<p style="color:#ff4466;">Не удалось загрузить</p><button class="btn btn-primary" onclick="downloadFile(${file.id})">⬇️ Скачать</button>`;
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
                previewContent.innerHTML = `<p style="color:#ff4466;">Не удалось загрузить</p><button class="btn btn-primary" onclick="downloadFile(${file.id})">⬇️ Скачать</button>`;
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
    else {
        downloadFile(file.id);
    }
}

// ✅ ЭКСПОРТ В EXCEL (из Luckysheet)
async function exportToExcel() {
    if (typeof window.luckysheet === 'undefined') {
        alert('Нет данных для экспорта');
        return;
    }
    try {
        const sheetData = window.luckysheet.getSheetData();

        let csv = [];
        if (sheetData && sheetData.length > 0) {
            sheetData.forEach(row => {
                const csvRow = row.map(cell => {
                    if (cell && cell.v !== undefined) {
                        return `"${String(cell.v).replace(/"/g, '""')}"`;
                    }
                    return '""';
                });
                csv.push(csvRow.join(';'));
            });
        }

        const csvContent = '\ufeff' + csv.join('\n');
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `${currentDocument?.title || 'table'}.csv`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
        console.log('✅ Exported to Excel (CSV)');
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
        <div class="file-icon">📁</div>
        <div class="file-name" title="${escapeHtml(folder.name)}">${escapeHtml(folder.name)}</div>
        <div class="file-meta"><span>${folder.files_count || 0} файлов</span><span>${date}</span></div>
        <div class="file-actions"><button class="file-action-btn" onclick="event.stopPropagation();deleteFolder(${folder.id})">🗑️</button></div>`;
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

    const icon = doc.doc_type === 'spreadsheet' ? '📊' : '📝';
    const date = doc.updated_at ? new Date(doc.updated_at).toLocaleString('ru-RU') : '';
    const canEdit = doc.is_editable || doc.owner_username === currentUser?.username;

    card.innerHTML = `
        <div class="file-icon">${icon}</div>
        <div class="file-name" title="${escapeHtml(doc.title)}">${escapeHtml(doc.title)}</div>
        <div class="file-meta"><span>${doc.doc_type === 'spreadsheet' ? 'Таблица' : 'Текст'}</span><span>${date}</span></div>
        <div class="file-actions">
            ${canEdit ? `<button class="file-action-btn" onclick="event.stopPropagation();openDocument(${doc.id})">✏️</button>` : ''}
            <button class="file-action-btn" onclick="event.stopPropagation();deleteDocument(${doc.id})">🗑️</button>
        </div>`;
    return card;
}

async function openDocument(docId) {
    try {
        const res = await fetch(`${API_BASE}/documents/${docId}/`, { headers: getAuthHeaders() });
        if (res.ok) { currentDocument = await res.json(); showDocumentEditor(currentDocument); }
        else { alert('Ошибка открытия'); }
    } catch (e) { console.error('Open document error:', e); alert('Ошибка'); }
}

function showDocumentEditor(doc) {
    console.log('📝 [DEBUG] showDocumentEditor called');
    console.log('📝 [DEBUG] doc:', doc);
    console.log('📝 [DEBUG] doc.doc_type:', doc?.doc_type);

    const title = document.getElementById('documentTitle');
    if (title) title.textContent = doc.title || 'Таблица';

    currentDocument = doc;

    // Показываем модалку
    showModal('documentModal');
    console.log('📝 [DEBUG] showModal called');

    // Ждём пока модалка отрисуется
    setTimeout(() => {
        console.log('📝 [DEBUG] setTimeout triggered');
        console.log('📝 [DEBUG] window.luckysheet:', typeof window.luckysheet);
        console.log('📝 [DEBUG] container:', document.getElementById('luckysheet-container'));

        const container = document.getElementById('luckysheet-container');
        if (container) {
            console.log('📝 [DEBUG] container.style.display:', container.style.display);
            container.style.display = 'block';
            container.style.height = 'calc(100vh - 60px)';
        }

        if (doc.doc_type === 'spreadsheet') {
            console.log('📝 [DEBUG] Calling initLuckysheet...');
            initLuckysheet(doc);
        } else {
            console.log('📝 [DEBUG] Calling initTextEditor...');
            initTextEditor(doc);
        }
    }, 500); // Увеличил задержку для надёжности
}

function initLuckysheet(doc) {
    console.log('🔍 [LUCKYSHEET] initLuckysheet START');

    const container = document.getElementById('luckysheet-container');
    if (!container) {
        console.error('❌ [LUCKYSHEET] Container #luckysheet-container NOT FOUND');
        return;
    }
    console.log('🔍 [LUCKYSHEET] Container found:', container);

    if (typeof window.luckysheet === 'undefined') {
        console.error('❌ [LUCKYSHEET] window.luckysheet is UNDEFINED');
        container.innerHTML = '<div style="padding:2rem;color:#fff;">⚠️ Luckysheet не загружен</div>';
        return;
    }
    console.log('🔍 [LUCKYSHEET] Luckysheet object exists');

    try {
        container.innerHTML = '';
        container.style.display = 'block';
        container.style.height = 'calc(100vh - 60px)';

        let sheetData = doc.content?.luckysheet;
        if (!sheetData || !Array.isArray(sheetData) || sheetData.length === 0) {
            sheetData = [{
                name: 'Sheet1',
                color: '',
                status: '1',
                order: '0',
                data: Array(50).fill(null).map(() => Array(30).fill(null)),
                rowCount: 50,
                columnCount: 30,
                defaultRowHeight: 19,
                defaultColWidth: 73
            }];
        }

        window.luckysheet.create({
            container: 'luckysheet-container',
            lang: 'ru',
            showtoolbarConfig: {
                image: true,
                print: true,
                exportXlsx: true
            },
            data: sheetData,
            allowUpdate: true,
            userInfo: currentUser?.username || 'User',
            myFolderUrl: '/',
            showConfigWindowResize: true,
            enableAddRow: true,
            enableAddBackTop: true,
            rowHeaderWidth: 45,
            defaultRowHeight: 19,
            defaultColWidth: 73,
            contextMenu: true,
            hook: {
                workbookCreatedAfter: function() {
                    console.log('✅ Luckysheet initialized');
                }
            }
        });

        console.log('✅ Luckysheet created successfully');
    } catch (e) {
        console.error('❌ Luckysheet error:', e);
        container.innerHTML = `<div style="padding:2rem;color:#000;">⚠️ Ошибка: ${e.message}</div>`;
    }
}

function initTextEditor(doc) {
    const container = document.getElementById('luckysheet-container');
    if (!container) return;
    container.innerHTML = `<textarea id="docText" style="width:100%;height:100%;padding:1rem;font-family:monospace;font-size:14px;border:none;resize:none;background:#1a1a25;color:#fff;">${doc.content?.text || ''}</textarea>`;
}

// ✅ ТИХОЕ СОХРАНЕНИЕ
async function saveDocumentSilent() {
    if (!currentDocument || typeof window.luckysheet === 'undefined') return;
    try {
        const sheetData = window.luckysheet.getAllSheets();
        const content = { luckysheet: sheetData };

        await fetch(`${API_BASE}/documents/${currentDocument.id}/save_content/`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({ content })
        });
        currentDocument.content = content;
        console.log('✅ Auto-saved silently');
    } catch (e) {
        console.error('❌ Silent save failed:', e);
    }
}

// ✅ СОХРАНЕНИЕ ПО КНОПКЕ
async function saveDocument() {
    if (!currentDocument || typeof window.luckysheet === 'undefined') {
        alert('Нет данных для сохранения');
        return;
    }
    try {
        const sheetData = window.luckysheet.getAllSheets();
        const content = { luckysheet: sheetData };

        const res = await fetch(`${API_BASE}/documents/${currentDocument.id}/save_content/`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({ content })
        });

        if (res.ok) {
            currentDocument.content = content;
            alert('✅ Сохранено!');
        } else {
            const err = await res.json().catch(() => ({}));
            alert(`Ошибка: ${err.detail || 'Не удалось сохранить'}`);
        }
    } catch (e) {
        console.error('❌ Save error:', e);
        alert('Ошибка подключения');
    }
}

function openCreateDocumentModal() {
    const titleInput = document.getElementById('newDocTitle');
    const typeSelect = document.getElementById('newDocType');
    if (titleInput) titleInput.value = '';
    if (typeSelect) typeSelect.value = 'spreadsheet';
    showModal('createDocumentModal');
}

async function createDocument() {
    const title = document.getElementById('newDocTitle')?.value || 'Без названия';
    const docType = document.getElementById('newDocType')?.value;
    try {
        const res = await fetch(`${API_BASE}/documents/`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({ title, doc_type: docType, content: {} })
        });
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
        const res = await fetch(`${API_BASE}/documents/${currentDocument.id}/share/`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({ username, permission: 'write' })
        });
        const data = await res.json().catch(() => ({}));
        alert(res.ok ? `✅ Доступ предоставлен ${username}` : `❌ ${data.detail || 'Ошибка'}`);
    } catch { alert('Ошибка подключения'); }
}

// ✅ ЗАГРУЗКА ТАБЛИЦ РАЗДЕЛОВ
async function loadSectionTable(sectionType) {
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
        <div class="file-icon">📊</div>
        <div class="file-name" title="${escapeHtml(table.title)}">${escapeHtml(table.title)}</div>
        <div class="file-meta"><span>${sectionType}</span><span>${date}</span></div>
        <div class="file-actions">
            <button class="file-action-btn" onclick="event.stopPropagation();openSectionTable(${table.id})">✏️</button>
            <button class="file-action-btn" onclick="event.stopPropagation();deleteSectionTable(${table.id})">🗑️</button>
        </div>
    `;
    return card;
}

function openCreateSectionTableModal(sectionType) {
    const titleInput = document.getElementById('newDocTitle');
    if (titleInput) titleInput.value = '';
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
                content: { luckysheet: [] }
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

async function openSectionTable(tableId) {
    try {
        const res = await fetch(`${API_BASE}/section-tables/${tableId}/`, { headers: getAuthHeaders() });
        if (res.ok) {
            currentDocument = await res.json();
            currentDocument.doc_type = 'spreadsheet';
            showDocumentEditor(currentDocument);
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

// ✅ ЗАГРУЗКА ОБЩЕГО ДОСТУПА
async function loadShared() {
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
    card.onclick = (e) => { if (!e.target.closest('.file-actions')) downloadFile(perm.file); };
    const name = perm.file_name || `Файл #${perm.file}`;
    const user = perm.user?.username || 'Неизвестно';
    const badge = perm.permission === 'write' ? '<span style="background:#10B981;color:#fff;padding:2px 8px;border-radius:12px;font-size:0.75rem">✏️</span>' : '<span style="background:#6B7280;color:#fff;padding:2px 8px;border-radius:12px;font-size:0.75rem">👁️</span>';
    card.innerHTML = `
        <div class="file-icon">🔗</div>
        <div class="file-name" title="${escapeHtml(name)}">${escapeHtml(name)}</div>
        <div class="file-meta">${badge}<span>${user}</span></div>
        <div class="file-actions"><button class="file-action-btn" onclick="event.stopPropagation();downloadFile(${perm.file})">⬇️</button></div>`;
    return card;
}

// ✅ ЗАГРУЗКА ЛОГОВ
async function loadLogs() {
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
    const icons = { upload: '📤', download: '⬇️', delete: '🗑️', share: '🔗', login: '🔑', logout: '🚪' };
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
}

// ✅ Toast уведомления
function showToast(message) {
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => {
        toast.remove();
    }, 3000);
}