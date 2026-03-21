// ==================== CNC Office - Frontend App ====================
const API_BASE = '/api';
const AUTH_BASE = `${API_BASE}/users`;

let currentUser = null;
let currentView = 'files';
let currentFolder = null;
let allFolders = [];
let authToken = localStorage.getItem('cnc_auth_token');

// DOM Elements
const filesGrid = document.getElementById('filesGrid');
const loadingState = document.getElementById('loadingState');
const emptyState = document.getElementById('emptyState');
const pageTitle = document.getElementById('pageTitle');
const uploadModal = document.getElementById('uploadModal');
const loginModal = document.getElementById('loginModal');
const uploadBtn = document.getElementById('uploadBtn');
const logoutBtn = document.getElementById('logoutBtn');
const uploadForm = document.getElementById('uploadForm');
const loginForm = document.getElementById('loginForm');
const registerForm = document.getElementById('registerForm');
const navItems = document.querySelectorAll('.nav-item');

// ✅ Инициализация
document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 App initialized');
    checkAuth();
    setupEventListeners();
    setupDragAndDrop();
});

// ✅ Заголовки с токеном
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

// ✅ Проверка авторизации
async function checkAuth() {
    authToken = localStorage.getItem('cnc_auth_token');
    if (!authToken) { showLoginModal(); return; }
    try {
        const res = await fetch(`${AUTH_BASE}/me/`, { headers: getAuthHeaders() });
        if (res.status === 200) {
            currentUser = await res.json();
            document.getElementById('username').textContent = currentUser.username;
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
        const res = await fetch(`${AUTH_BASE}/login/`, {
            method: 'POST', headers: getAuthHeaders(), body: JSON.stringify({ username, password })
        });
        const data = await res.json();
        if (res.ok && data.token) {
            authToken = data.token;
            localStorage.setItem('cnc_auth_token', data.token);
            localStorage.setItem('cnc_username', data.user?.username || username);
            currentUser = data.user || { username };
            document.getElementById('username').textContent = currentUser.username;
            hideModal('loginModal'); loadView('files');
        } else alert(`Ошибка: ${data.detail || 'Неверный логин или пароль'}`);
    } catch (e) { console.error('Login error:', e); alert('Ошибка подключения к серверу'); }
}

// ✅ Регистрация
async function handleRegister(e) {
    if (e) e.preventDefault();
    const username = document.getElementById('registerUsername')?.value;
    const email = document.getElementById('registerEmail')?.value;
    const password = document.getElementById('registerPassword')?.value;
    const password2 = document.getElementById('registerPassword2')?.value;
    if (!username || !email || !password || !password2) { alert('Заполните все поля'); return; }
    if (password !== password2) { alert('Пароли не совпадают'); return; }
    if (password.length < 8) { alert('Пароль минимум 8 символов'); return; }
    try {
        const res = await fetch(`${AUTH_BASE}/register/`, {
            method: 'POST', headers: getAuthHeaders(), body: JSON.stringify({ username, email, password, password2 })
        });
        const data = await res.json();
        if (res.ok || res.status === 201) {
            if (data.token) {
                authToken = data.token;
                localStorage.setItem('cnc_auth_token', data.token);
                localStorage.setItem('cnc_username', data.user?.username || username);
                currentUser = data.user || { username };
                document.getElementById('username').textContent = currentUser.username;
                hideModal('loginModal'); loadView('files');
            } else {
                alert('✅ Регистрация успешна! Войдите в систему.');
                if (registerForm) registerForm.classList.add('hidden');
                if (loginForm) loginForm.classList.remove('hidden');
            }
        } else alert(`Ошибка: ${data.detail || JSON.stringify(data)}`);
    } catch (e) { console.error('Register error:', e); alert('Ошибка подключения к серверу'); }
}

async function logout() { clearAuth(); location.reload(); }

// ✅ Event Listeners
function setupEventListeners() {
    if (uploadBtn) uploadBtn.addEventListener('click', () => {
        if (currentView === 'files') { loadFoldersForDropdown(); showModal(uploadModal); }
        else if (currentView === 'folders') createFolder();
    });
    if (logoutBtn) logoutBtn.addEventListener('click', logout);
    if (uploadForm) uploadForm.addEventListener('submit', handleUpload);
    if (loginForm) loginForm.addEventListener('submit', handleLogin);
    if (registerForm) registerForm.addEventListener('submit', handleRegister);
    const tR = document.getElementById('toggleToRegister');
    if (tR) tR.addEventListener('click', e => { e.preventDefault(); showRegisterModal(); });
    const tL = document.getElementById('toggleToLogin');
    if (tL) tL.addEventListener('click', e => { e.preventDefault(); showLoginModal(); });
    navItems.forEach(item => item.addEventListener('click', e => {
        e.preventDefault();
        navItems.forEach(n => n.classList.remove('active'));
        item.classList.add('active');
        currentFolder = null; loadView(item.getAttribute('data-view'));
    }));
    [uploadModal, loginModal].forEach(m => {
        if (m) m.addEventListener('click', e => { if (e.target === m) hideModal(m); });
    });
    const closeBtn = document.getElementById('closeModal');
    if (closeBtn) closeBtn.addEventListener('click', () => hideModal('uploadModal'));
}

// ✅ Загрузка видов
async function loadView(view) {
    currentView = view;
    if (uploadBtn) {
        uploadBtn.style.display = view === 'files' ? 'inline-flex' : view === 'folders' ? 'inline-flex' : 'none';
        uploadBtn.innerHTML = view === 'folders' ? '📁 Создать папку' : '📤 Загрузить файл';
    }
    const titles = { files: 'Мои файлы', folders: 'Папки', shared: 'Общий доступ', logs: 'Журнал аудита' };
    if (pageTitle) pageTitle.textContent = titles[view] || 'CNC Office';
    navItems.forEach(n => n.classList.toggle('active', n.getAttribute('data-view') === view));
    updateBreadcrumb(); showLoading();
    switch(view) {
        case 'files': await loadFiles(); break;
        case 'folders': await loadFolders(); break;
        case 'shared': await loadShared(); break;
        case 'logs': await loadLogs(); break;
        default: await loadFiles();
    }
}

function updateBreadcrumb() {
    let bc = document.querySelector('.breadcrumb'); if (bc) bc.remove();
    if (currentView !== 'files') return;
    bc = document.createElement('div'); bc.className = 'breadcrumb';
    bc.style.cssText = 'margin-bottom:1rem;padding:.5rem 1rem;background:#f3f4f6;border-radius:.5rem;font-size:.9rem;';
    let html = `<a href="#" onclick="navigateToFolder(null);return false;" style="color:#4F46E5;text-decoration:none;font-weight:500;">📁 Корень</a>`;
    if (currentFolder) html += ` <span style="color:#6B7280;margin:0 .25rem;">/</span> <span style="font-weight:600;">${escapeHtml(currentFolder.name)}</span>`;
    bc.innerHTML = html;
    if (pageTitle?.parentNode) pageTitle.parentNode.insertBefore(bc, pageTitle.nextSibling);
}

async function navigateToFolder(folderId) {
    currentFolder = folderId === null ? null : allFolders.find(f => f.id === folderId);
    updateBreadcrumb(); await loadFiles();
}

// ✅ Drag & Drop
function setupDragAndDrop() {
    const dz = document.querySelector('.content-area') || document.querySelector('.main-content') || document.body;
    if (!dz) return;
    ['dragenter','dragover','dragleave','drop'].forEach(ev => dz.addEventListener(ev, e => { e.preventDefault(); e.stopPropagation(); }, false));
    ['dragenter','dragover'].forEach(ev => dz.addEventListener(ev, () => { dz.style.border='3px dashed #4F46E5'; dz.style.borderRadius='12px'; dz.style.backgroundColor='rgba(79,70,229,0.05)'; }, false));
    ['dragleave','drop'].forEach(ev => dz.addEventListener(ev, () => { dz.style.border=''; dz.style.borderRadius=''; dz.style.backgroundColor=''; }, false));
    dz.addEventListener('drop', e => { if (currentView === 'files' && e.dataTransfer.files[0]) uploadFile(e.dataTransfer.files[0]); }, false);
}

// ✅ Загрузка списка файлов
async function loadFiles() {
    showLoading();
    try {
        let url = `${API_BASE}/files/?`;
        if (currentFolder) url += `folder=${currentFolder.id}`;
        const res = await fetch(url, { headers: getAuthHeaders() });
        console.log('📦 Files response status:', res.status);
        if (res.status === 200) {
            const data = await res.json();
            console.log('📦 Files data:', data);
            renderFiles(data);
        } else if (res.status === 401 || res.status === 403) { hideLoading(); clearAuth(); showLoginModal(); }
        else { const text = await res.text(); console.error('❌ Files error:', res.status, text); showEmpty(); }
    } catch (e) { console.error('❌ Load files error:', e); showEmpty(); }
}

function renderFiles(files) {
    hideLoading();
    if (!files?.length) { showEmpty(); return; }
    hideEmpty(); filesGrid.innerHTML = '';
    files.forEach((f, i) => { if (f) filesGrid.appendChild(createFileCard(f, i)); });
}

function createFileCard(file, index) {
    const card = document.createElement('div');
    card.className = 'file-card'; card.style.animationDelay = `${index * 0.1}s`;
    const icon = getFileIcon(file.mime_type);
    let name = file.file_name || (file.file?.split('/')?.pop?.() || 'Без имени');
    try { name = decodeURIComponent(name); } catch {}
    const size = file.size_mb ? `${file.size_mb} MB` : file.size ? `${(file.size/1024/1024).toFixed(2)} MB` : '0 MB';
    const date = file.uploaded_at ? new Date(file.uploaded_at).toLocaleDateString('ru-RU') : '';
    const canDl = file.owner === currentUser?.username;
    card.innerHTML = `
        <div class="file-icon">${icon}</div>
        <div class="file-name" title="${escapeHtml(name)}">${escapeHtml(name)}</div>
        <div class="file-meta"><span>${size}</span><span>${date}</span></div>
        <div class="file-actions">
            ${canDl ? `<button class="file-action-btn" onclick="downloadFile(${file.id})" title="Скачать">⬇️</button>` : ''}
            ${canDl ? `<button class="file-action-btn" onclick="shareFile(${file.id})" title="Поделиться">🔗</button>` : ''}
            ${canDl ? `<button class="file-action-btn" onclick="deleteFile(${file.id})" title="Удалить">🗑️</button>` : ''}
        </div>`;
    return card;
}

function getFileIcon(mt) {
    if (!mt) return '📁';
    if (mt.includes('image')) return '🖼️'; if (mt.includes('pdf')) return '📄';
    if (mt.includes('video')) return '🎬'; if (mt.includes('audio')) return '🎵';
    if (mt.includes('text')) return '📝'; if (mt.includes('zip') || mt.includes('archive')) return '📦';
    return '📁';
}

// ✅ ЗАГРУЗКА ФАЙЛА (ИСПРАВЛЕНО!)
async function uploadFile(file) {
    console.log('📤 Uploading file:', file.name);
    const fd = new FormData(); fd.append('file', file);
    if (currentFolder) fd.append('folder', currentFolder.id);
    else { const fs = document.getElementById('folderSelect'); if (fs?.value) fd.append('folder', fs.value); }
    try {
        console.log('📤 Sending request to', `${API_BASE}/files/`);
        const res = await fetch(`${API_BASE}/files/`, {
            method: 'POST',
            headers: getAuthHeaders(false), // ❗ Не JSON для FormData
            body: fd
        });
        console.log('📤 Response status:', res.status);
        const data = await res.json().catch(() => ({}));
        console.log('📤 Response data:', data);
        if (res.ok || res.status === 201) {
            hideModal('uploadModal');
            if (uploadForm) uploadForm.reset();
            await loadFiles(); // ✅ Перезагружаем список!
        } else {
            const errMsg = data.detail || data.file?.[0] || data.error || 'Неизвестная ошибка';
            console.error('❌ Upload failed:', res.status, errMsg);
            alert(`Ошибка загрузки: ${errMsg}`);
        }
    } catch (e) {
        console.error('❌ Upload error:', e);
        alert('Ошибка подключения к серверу: ' + e.message);
    }
}

async function handleUpload(e) {
    e.preventDefault();
    console.log('📤 Form submitted');
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
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a'); a.href = url; a.download = `file_${fileId}`;
            document.body.appendChild(a); a.click(); URL.revokeObjectURL(url); document.body.removeChild(a);
        } else if (res.status === 401 || res.status === 403) { alert('Ошибка авторизации. Войдите снова.'); clearAuth(); showLoginModal(); }
        else { const err = await res.json().catch(()=>({})); alert(`Ошибка: ${err.detail || 'Не удалось скачать'}`); }
    } catch (e) { console.error('Download error:', e); alert('Ошибка подключения к серверу'); }
}

// ✅ Поделиться / Удалить
async function shareFile(fileId) { const u = prompt('Имя пользователя:'); if (!u) return;
    try { const res = await fetch(`${API_BASE}/files/${fileId}/share/`, { method:'POST', headers:getAuthHeaders(), body:JSON.stringify({username:u,permission:'read'}) });
        const d = await res.json().catch(()=>({})); alert(res.ok ? `✅ Доступ предоставлен ${u}` : `❌ ${d.detail||'Ошибка'}`); } catch { alert('Ошибка подключения'); }}
async function deleteFile(fileId) { if (!confirm('Удалить файл?')) return;
    try { const res = await fetch(`${API_BASE}/files/${fileId}/`, { method:'DELETE', headers:getAuthHeaders() }); if (res.ok||res.status===204) await loadFiles(); else alert('Ошибка удаления'); } catch { alert('Ошибка подключения'); }}

// ✅ Папки
async function loadFoldersForDropdown() { const fs = document.getElementById('folderSelect'); if (!fs) return; fs.innerHTML = '<option value="">Корневая папка</option>';
    try { const res = await fetch(`${API_BASE}/folders/`, { headers:getAuthHeaders() }); if (res.status===200) { allFolders = await res.json(); allFolders.forEach(f => { const o = document.createElement('option'); o.value=f.id; o.textContent=f.name; fs.appendChild(o); }); }} catch {}}
async function loadFolders() { showLoading(); try { const res = await fetch(`${API_BASE}/folders/`, { headers:getAuthHeaders() }); if (res.status===200) renderFolders(await res.json()); else if (res.status===401||res.status===403) { hideLoading(); clearAuth(); showLoginModal(); } else showEmpty(); } catch { showEmpty(); }}
function renderFolders(folders) { hideLoading(); if (!folders?.length) { showEmpty(); return; } hideEmpty(); filesGrid.innerHTML=''; folders.forEach((f,i)=>filesGrid.appendChild(createFolderCard(f,i))); }
function createFolderCard(folder, index) { const card = document.createElement('div'); card.className='file-card'; card.style.animationDelay=`${index*0.1}s`; card.style.cursor='pointer';
    card.addEventListener('click', e => { if (!e.target.closest('.file-actions')) { currentFolder=folder; currentView='files'; loadView('files'); }});
    card.innerHTML = `<div class="file-icon">📁</div><div class="file-name" title="${escapeHtml(folder.name)}">${escapeHtml(folder.name)}</div><div class="file-meta"><span>${folder.files_count||0} файлов</span><span>${new Date(folder.created_at).toLocaleDateString('ru-RU')}</span></div><div class="file-actions"><button class="file-action-btn" onclick="deleteFolder(${folder.id});event.stopPropagation();" title="Удалить">🗑️</button></div>`; return card; }
async function createFolder() { const n = prompt('Имя папки:'); if (!n?.trim()) return;
    try { const res = await fetch(`${API_BASE}/folders/`, { method:'POST', headers:getAuthHeaders(), body:JSON.stringify({name:n.trim()}) }); if (res.ok) await loadFolders(); else { const e = await res.json().catch(()=>({})); alert(`Ошибка: ${e.detail||e.name?.[0]||'Неизвестная ошибка'}`); }} catch { alert('Ошибка подключения'); }}
async function deleteFolder(id) { if (!confirm('Удалить папку?')) return;
    try { const res = await fetch(`${API_BASE}/folders/${id}/`, { method:'DELETE', headers:getAuthHeaders() }); if (res.ok||res.status===204) await loadFolders(); else alert('Ошибка'); } catch { alert('Ошибка подключения'); }}

// ✅ Общий доступ / Логи
async function loadShared() { showLoading(); try { const res = await fetch(`${API_BASE}/permissions/`, { headers:getAuthHeaders() }); if (res.status===200) renderShared(await res.json()); else if (res.status===401||res.status===403) { hideLoading(); clearAuth(); showLoginModal(); } else showEmpty(); } catch { showEmpty(); }}
function renderShared(perms) { hideLoading(); if (!perms?.length) { showEmpty(); return; } hideEmpty(); filesGrid.innerHTML=''; perms.forEach((p,i)=>filesGrid.appendChild(createSharedCard(p,i))); }
function createSharedCard(perm, index) { const card = document.createElement('div'); card.className='file-card'; card.style.animationDelay=`${index*0.1}s`;
    const name = perm.file_name || `Файл #${perm.file}`;
    const badge = perm.permission==='write' ? '<span style="background:#10B981;color:white;padding:2px 8px;border-radius:12px;font-size:.75rem">✏️ Запись</span>' : '<span style="background:#6B7280;color:white;padding:2px 8px;border-radius:12px;font-size:.75rem">👁️ Чтение</span>';
    card.innerHTML = `<div class="file-icon">🔗</div><div class="file-name" title="${escapeHtml(name)}">${escapeHtml(name)}</div><div class="file-meta">${badge}<span>${perm.granted_at?new Date(perm.granted_at).toLocaleDateString('ru-RU'):''}</span></div><div class="file-actions"><button class="file-action-btn" onclick="revokePermission(${perm.id})" title="Отозвать">❌</button></div>`; return card; }
async function revokePermission(id) { if (!confirm('Отозвать доступ?')) return;
    try { const res = await fetch(`${API_BASE}/permissions/${id}/`, { method:'DELETE', headers:getAuthHeaders() }); if (res.ok||res.status===204) await loadShared(); else alert('Ошибка'); } catch { alert('Ошибка подключения'); }}
async function loadLogs() { showLoading(); try { const res = await fetch(`${API_BASE}/audit-logs/`, { headers:getAuthHeaders() }); if (res.status===200) renderLogs(await res.json()); else if (res.status===401||res.status===403) { hideLoading(); clearAuth(); showLoginModal(); } else showEmpty(); } catch { showEmpty(); }}
function renderLogs(logs) { hideLoading(); if (!logs?.length) { showEmpty(); return; } hideEmpty(); filesGrid.innerHTML=''; logs.forEach((l,i)=>filesGrid.appendChild(createLogCard(l,i))); }
function createLogCard(log, index) { const card = document.createElement('div'); card.className='file-card'; card.style.animationDelay=`${index*0.1}s`;
    const icons = {upload:'📤',download:'⬇️',delete:'🗑️',share:'🔗',login:'🔑',logout:'🚪',create_folder:'📁',delete_folder:'🗂️'};
    card.innerHTML = `<div class="file-icon">${icons[log.action]||'📝'}</div><div class="file-name">${escapeHtml(log.action)}</div><div class="file-meta"><span>${log.user_username||'Система'}</span><span>${new Date(log.timestamp).toLocaleString('ru-RU')}</span></div>${log.details?`<div style="margin-top:.5rem;font-size:.75rem;color:#6B7280;">${escapeHtml(log.details)}</div>`:''}`; return card; }

// ✅ UI Helpers
function showLoading() { if (loadingState) { loadingState.classList.add('show'); loadingState.style.display='flex'; } if (emptyState) emptyState.classList.remove('show'); if (filesGrid) filesGrid.style.display='none'; }
function hideLoading() { if (loadingState) { loadingState.classList.remove('show'); loadingState.style.display='none'; } if (filesGrid) filesGrid.style.display='grid'; }
function showEmpty() { if (emptyState) { emptyState.classList.add('show'); emptyState.style.display='flex'; } if (filesGrid) filesGrid.style.display='none'; if (loadingState) loadingState.style.display='none'; }
function hideEmpty() { if (emptyState) { emptyState.classList.remove('show'); emptyState.style.display='none'; } }
