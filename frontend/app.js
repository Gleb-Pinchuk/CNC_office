// ==================== CNC Office - Frontend App v19.1 (Custom Sheet Editor) ====================
const API_BASE = '/api';
let currentUser = null;
let currentFolder = null;
let currentView = 'files';
let currentDocument = null;
let currentSectionType = null;
let authToken = localStorage.getItem('cnc_auth_token');
let hotInstance = null;
let sheetEditor = null;

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
    console.log('🚀 App initialized v19.1');
    setupEventListeners();
    checkAuth();
});

// ✅ Заголовки для API-запросов
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
        setTimeout(() => {
            if (sheetEditor) sheetEditor.focus();
        }, 100);
    }
}

// ✅ Скрыть модальное окно
function hideModal(modal) {
    const el = typeof modal === 'string' ? document.getElementById(modal) : modal;
    if (el) {
        if (el.id === 'documentModal') {
            if (currentDocument && (hotInstance || sheetEditor)) saveDocumentSilent();
            if (sheetEditor) { sheetEditor.destroy(); sheetEditor = null; }
            if (hotInstance) { hotInstance.destroy(); hotInstance = null; }
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
            loadView('files');
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
    else if (mt.includes('excel') || mt.includes('spreadsheet') || ['xls', 'xlsx', 'csv'].includes(fileExt)) {
        previewContent.innerHTML = `
            <div style="text-align:center;padding:2rem;">
                <div style="font-size:4rem;margin-bottom:1rem;">📊</div>
                <h3>Excel файл</h3>
                <p style="color:#888;margin:1rem 0;">${file.file_name || 'Файл'}</p>
                <button class="btn btn-primary" onclick="downloadFile(${file.id})">⬇️ Скачать</button>
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
        const data = sheetEditor ? sheetEditor.export().data : hotInstance.getData();
        const headers = data[0] ? data[0].map((_, i) => String.fromCharCode(65 + (i % 26))) : [];
        let csv = [];
        if (headers && headers.length > 0) {
            csv.push(headers.map(h => `"${h || ''}"`).join(';'));
        }
        data.forEach(row => {
            csv.push(row.map(cell => `"${cell || ''}"`).join(';'));
        });
        const csvContent = csv.join('\n');
        const blob = new Blob(['\ufeff' + csvContent], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `${currentDocument.title || 'table'}.csv`;
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
    console.log('📝 Opening document:', doc.title, doc.doc_type);
    const title = document.getElementById('documentTitle');
    if (!title) return;
    title.textContent = doc.title;
    currentDocument = doc;
    showModal('documentModal');
    setTimeout(() => {
        if (doc.doc_type === 'spreadsheet') { initHandsontable(doc); }
        else { initTextEditor(doc); }
    }, 400);
}

class CustomSheetEditor {
    constructor(container, payload) {
        this.container = container;
        this.undoStack = [];
        this.redoStack = [];
        this.selection = { r1: 0, c1: 0, r2: 0, c2: 0 };
        this.isSelecting = false;
        this.fillDrag = null;
        this.colWidths = Array.isArray(payload?.colWidths) ? payload.colWidths.slice() : [];
        this.rowHeights = Array.isArray(payload?.rowHeights) ? payload.rowHeights.slice() : [];
        this._onGlobalMouseUp = () => { this.isSelecting = false; };
        this._onGlobalMouseMove = () => {};
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

        const data = Array.isArray(payload?.data) ? payload.data : [];
        const rows = Math.max(payload?.rows || data.length || 20, 20);
        let detectedCols = payload?.cols || 0;
        for (const row of data) if (Array.isArray(row)) detectedCols = Math.max(detectedCols, row.length);
        const cols = Math.max(detectedCols || 10, 10);

        this.data = Array.from({ length: rows }, (_, r) => {
            const row = Array.isArray(data[r]) ? data[r] : [];
            return Array.from({ length: cols }, (_, c) => String(row[c] ?? ''));
        });
        this.styles = payload?.styles && typeof payload.styles === 'object' ? payload.styles : {};
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
    _pushUndo() {
        this.undoStack.push(JSON.stringify({ data: this.data, styles: this.styles }));
        if (this.undoStack.length > 50) this.undoStack.shift();
        this.redoStack = [];
    }
    _applySnapshot(snapshot) {
        const parsed = JSON.parse(snapshot);
        this.data = parsed.data || this.data;
        this.styles = parsed.styles || {};
        this.render();
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
        this.container.querySelectorAll('.sheet-cell').forEach(el => el.classList.remove('selected'));
        const s = this._normalizeSelection();
        this._forEachSelectedCell((r, c) => {
            const el = this.container.querySelector(`[data-r="${r}"][data-c="${c}"]`);
            if (el) el.classList.add('selected');
        });
        this._positionFillHandle();
    }
    _applyCellStyle(el, styleObj) {
        el.style.fontWeight = styleObj?.bold ? '700' : '400';
        el.style.fontStyle = styleObj?.italic ? 'italic' : 'normal';
        el.style.textAlign = styleObj?.align || 'left';
        el.style.color = styleObj?.textColor || '#111111';
        el.style.backgroundColor = styleObj?.fillColor || '#ffffff';
    }

    render() {
        const rows = this.data.length;
        const cols = this.data[0]?.length || 0;
        let html = '<div class="sheet-wrap"><table class="sheet-table"><thead><tr><th class="corner"></th>';
        for (let c = 0; c < cols; c++) {
            const w = this.colWidths[c] || 90;
            html += `<th data-col-header="${c}" style="width:${w}px;min-width:${w}px;max-width:${w}px;">${this._colName(c)}<span class="col-resizer" data-col-resizer="${c}"></span></th>`;
        }
        html += '</tr></thead><tbody>';
        for (let r = 0; r < rows; r++) {
            const h = this.rowHeights[r] || 28;
            html += `<tr style="height:${h}px;"><th data-row-header="${r}" style="height:${h}px;min-height:${h}px;max-height:${h}px;">${r + 1}<span class="row-resizer" data-row-resizer="${r}"></span></th>`;
            for (let c = 0; c < cols; c++) {
                const w = this.colWidths[c] || 90;
                html += `<td class="sheet-cell" contenteditable="true" data-r="${r}" data-c="${c}" style="width:${w}px;min-width:${w}px;max-width:${w}px;height:${h}px;">${escapeHtml(this.data[r][c])}</td>`;
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
            cell.addEventListener('mousedown', (e) => { e.preventDefault(); this.isSelecting = true; this._setSelection(r, c); cell.focus(); });
            cell.addEventListener('mouseenter', (e) => {
                if (this.fillDrag) {
                    this.fillDrag.target = { r, c };
                    this._paintFillTarget();
                    return;
                }
                if (this.isSelecting && (e.buttons & 1)) this._setSelection(r, c, true);
            });
            cell.addEventListener('input', () => { this.data[r][c] = cell.textContent || ''; });
            cell.addEventListener('blur', () => { this.data[r][c] = cell.textContent || ''; });
        });
        this._bindResizers();
        this._ensureFillHandle();
        this._paintSelection();
    }
    _bindResizers() {
        this.container.querySelectorAll('[data-col-resizer]').forEach((el) => {
            el.addEventListener('mousedown', (e) => {
                e.preventDefault();
                e.stopPropagation();
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
        if (!endCell) return;
        const r1 = this.wrapEl.getBoundingClientRect();
        const r2 = endCell.getBoundingClientRect();
        this.fillHandle.style.left = `${r2.right - r1.left + this.wrapEl.scrollLeft - 4}px`;
        this.fillHandle.style.top = `${r2.bottom - r1.top + this.wrapEl.scrollTop - 4}px`;
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
        window.removeEventListener('mouseup', this._onGlobalMouseUp);
        window.removeEventListener('blur', this._onGlobalMouseUp);
        if (this._onFillEnd) {
            window.removeEventListener('mouseup', this._onFillEnd);
            this._onFillEnd = null;
        }
        this.container.innerHTML = '';
    }
    export() {
        return {
            rows: this.data.length,
            cols: this.data[0]?.length || 0,
            data: this.data,
            styles: this.styles,
            colWidths: this.colWidths,
            rowHeights: this.rowHeights,
        };
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
        this.redoStack.push(JSON.stringify({ data: this.data, styles: this.styles }));
        this._applySnapshot(this.undoStack.pop());
    }
    redo() {
        if (!this.redoStack.length) return;
        this.undoStack.push(JSON.stringify({ data: this.data, styles: this.styles }));
        this._applySnapshot(this.redoStack.pop());
    }
}

// ✅ ИНИЦИАЛИЗАЦИЯ ВСТРОЕННОГО РЕДАКТОРА ТАБЛИЦ
function initHandsontable(doc) {
    console.log('🔍 init custom sheet editor');
    const container = document.getElementById('handsontable-container');
    if (!container) { console.error('❌ Container not found'); return; }
    hotInstance = null;
    if (sheetEditor) { sheetEditor.destroy(); sheetEditor = null; }

    let payload = doc?.content?.custom_sheet;
    if (!payload) {
        const legacy = Array.isArray(doc?.content?.handsontable) ? doc.content.handsontable : [];
        payload = { data: legacy, rows: legacy.length || 20, cols: (legacy[0]?.length || 10), styles: {} };
    }
    sheetEditor = new CustomSheetEditor(container, payload);
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
}

function undoTableEdit() {
    if (sheetEditor) sheetEditor.undo();
}

function redoTableEdit() {
    if (sheetEditor) sheetEditor.redo();
}

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
    let content = {};
    if (currentDocument.doc_type === 'spreadsheet' && (sheetEditor || hotInstance)) {
        try {
            if (sheetEditor) {
                content = { custom_sheet: sheetEditor.export() };
            } else {
                const data = hotInstance.getData();
                content = { handsontable: data };
            }
        } catch(e) { console.error('❌ Silent save error:', e); return; }
    } else if (currentDocument.doc_type === 'text') {
        const textEl = document.getElementById('docText');
        if (textEl) content = { text: textEl.value };
    }
    try {
        await fetch(`${API_BASE}/documents/${currentDocument.id}/save_content/`, {
            method: 'POST', headers: getAuthHeaders(), body: JSON.stringify({ content })
        });
        currentDocument.content = content;
        console.log('✅ Auto-saved silently');
    } catch (e) { console.error('❌ Silent save failed:', e); }
}

// ✅ СОХРАНЕНИЕ ПО КНОПКЕ
async function saveDocument() {
    if (!currentDocument) return;
    let content = {};
    if (currentDocument.doc_type === 'spreadsheet' && (sheetEditor || hotInstance)) {
        try {
            if (sheetEditor) {
                content = { custom_sheet: sheetEditor.export() };
            } else {
                const data = hotInstance.getData();
                content = { handsontable: data };
            }
            console.log('💾 Saving spreadsheet');
        } catch(e) { console.error('❌ Save error:', e); alert('Ошибка сохранения'); return; }
    } else if (currentDocument.doc_type === 'text') {
        const textEl = document.getElementById('docText');
        if (textEl) content = { text: textEl.value };
    }
    try {
        const res = await fetch(`${API_BASE}/documents/${currentDocument.id}/save_content/`, {
            method: 'POST', headers: getAuthHeaders(), body: JSON.stringify({ content })
        });
        if (res.ok) { currentDocument.content = content; alert('✅ Сохранено!'); }
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
        const res = await fetch(`${API_BASE}/documents/${currentDocument.id}/share/`, { method: 'POST', headers: getAuthHeaders(), body: JSON.stringify({ username, permission: 'write' }) });
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
