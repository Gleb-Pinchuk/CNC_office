
// API Configuration
const BASE_URL = window.location.origin;
const API_BASE = `${BASE_URL}/api`;
const AUTH_BASE = `${BASE_URL}/api-auth`;

// State
let currentUser = null;
let currentView = 'files';
let currentFolder = null;
let allFolders = [];

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
const navItems = document.querySelectorAll('.nav-item');

document.addEventListener('DOMContentLoaded', () => {
    checkAuth();
    setupEventListeners();
    setupDragAndDrop();
});

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

async function checkAuth() {
    const savedUsername = localStorage.getItem('cnc_username');

    try {
        const response = await fetch(`${API_BASE}/files/`, {
            credentials: 'include',
            headers: { 'Accept': 'application/json' }
        });

        if (response.status === 200) {
            const username = savedUsername || 'Пользователь';
            currentUser = { username: username };
            document.getElementById('username').textContent = username;
            loadView('files');
        } else {
            localStorage.removeItem('cnc_username');
            showLoginModal();
        }
    } catch (error) {
        console.error('Auth check error:', error);
        if (savedUsername) {
            currentUser = { username: savedUsername };
            document.getElementById('username').textContent = savedUsername;
            loadView('files');
        } else {
            showLoginModal();
        }
    }
}

async function handleLogin(e) {
    e.preventDefault();

    const username = document.getElementById('loginUsername').value;
    const password = document.getElementById('loginPassword').value;

    if (!username || !password) {
        alert('Введите логин и пароль');
        return;
    }

    try {
        const formData = new FormData();
        formData.append('username', username);
        formData.append('password', password);

        const csrftoken = getCookie('csrftoken');

        const response = await fetch(`${AUTH_BASE}/login/`, {
            method: 'POST',
            credentials: 'include',
            headers: {
                'Accept': 'application/json',
                'X-CSRFToken': csrftoken
            },
            body: formData
        });

        if (response.ok || response.status === 302) {
            localStorage.setItem('cnc_username', username);
            currentUser = { username: username };
            document.getElementById('username').textContent = username;
            hideModal(loginModal);
            loadView('files');
        } else {
            alert('Ошибка входа: Неверный логин или пароль');
        }
    } catch (error) {
        console.error('Login error:', error);
        alert('Ошибка подключения к серверу');
    }
}

async function logout() {
    try {
        const csrftoken = getCookie('csrftoken');
        await fetch(`${AUTH_BASE}/logout/`, {
            method: 'POST',
            credentials: 'include',
            headers: { 'X-CSRFToken': csrftoken }
        });
    } catch (error) {
        console.error('Logout error:', error);
    }
    localStorage.removeItem('cnc_username');
    currentUser = null;
    currentFolder = null;
    location.reload();
}

function showLoginModal() {
    showModal(loginModal);
}

function setupEventListeners() {
    if (uploadBtn) {
        uploadBtn.addEventListener('click', () => {
            if (currentView === 'files') {
                loadFoldersForDropdown();
                showModal(uploadModal);
            } else if (currentView === 'folders') {
                createFolder();
            }
        });
    }

    if (logoutBtn) {
        logoutBtn.addEventListener('click', logout);
    }

    if (uploadForm) {
        uploadForm.addEventListener('submit', handleUpload);
    }
    if (loginForm) {
        loginForm.addEventListener('submit', handleLogin);
    }

    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            navItems.forEach(nav => nav.classList.remove('active'));
            item.classList.add('active');
            const view = item.getAttribute('data-view');
            currentFolder = null;
            loadView(view);
        });
    });

    [uploadModal, loginModal].forEach(modal => {
        if (modal) {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) hideModal(modal);
            });
        }
    });

    const closeModalBtn = document.getElementById('closeModal');
    if (closeModalBtn) {
        closeModalBtn.addEventListener('click', () => {
            hideModal(uploadModal);
        });
    }
}

async function loadView(view) {
    currentView = view;

    if (uploadBtn) {
        uploadBtn.style.display = 'inline-flex';
        if (view === 'folders') {
            uploadBtn.innerHTML = '<span>📁</span> Создать папку';
        } else if (view === 'files') {
            uploadBtn.innerHTML = '<span>📤</span> Загрузить файл';
        } else {
            uploadBtn.style.display = 'none';
        }
    }

    const titles = {
        'files': 'Мои файлы',
        'folders': 'Папки',
        'shared': 'Общий доступ',
        'logs': 'Журнал аудита'
    };

    if (pageTitle) {
        pageTitle.textContent = titles[view] || 'CNC Office';
    }

    updateBreadcrumb();
    showLoading();

    switch(view) {
        case 'files':
            await loadFiles();
            break;
        case 'folders':
            await loadFolders();
            break;
        case 'shared':
            await loadShared();
            break;
        case 'logs':
            await loadLogs();
            break;
        default:
            loadFiles();
    }
}

function updateBreadcrumb() {
    let breadcrumb = document.querySelector('.breadcrumb');
    if (breadcrumb) {
        breadcrumb.remove();
    }

    if (currentView !== 'files') return;

    breadcrumb = document.createElement('div');
    breadcrumb.className = 'breadcrumb';
    breadcrumb.style.cssText = 'margin-bottom: 1rem; padding: 0.5rem; background: #f3f4f6; border-radius: 0.5rem;';

    let html = '<a href="#" onclick="navigateToFolder(null); return false;" style="color: #4F46E5; text-decoration: none;">📁 Корень</a>';

    if (currentFolder) {
        html += ` <span style="color: #6B7280;">/</span> <span style="font-weight: 600;">${currentFolder.name}</span>`;
    }

    breadcrumb.innerHTML = html;

    if (pageTitle) {
        pageTitle.parentNode.insertBefore(breadcrumb, pageTitle.nextSibling);
    }
}

async function navigateToFolder(folderId) {
    if (folderId === null) {
        currentFolder = null;
    } else {
        const folder = allFolders.find(f => f.id === folderId);
        currentFolder = folder;
    }
    updateBreadcrumb();
    await loadFiles();
}

function showModal(modal) {
    if (modal) modal.classList.add('show');
}

function hideModal(modal) {
    if (modal) modal.classList.remove('show');
}

function setupDragAndDrop() {
    const dropZone = document.querySelector('.content-area') || document.querySelector('.main-content') || document.body;
    if (!dropZone) return;

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, highlight, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, unhighlight, false);
    });

    function highlight(e) {
        dropZone.style.border = '3px dashed #4F46E5';
        dropZone.style.borderRadius = '12px';
        dropZone.style.backgroundColor = 'rgba(79, 70, 229, 0.05)';
    }

    function unhighlight(e) {
        dropZone.style.border = '';
        dropZone.style.borderRadius = '';
        dropZone.style.backgroundColor = '';
    }

    dropZone.addEventListener('drop', handleDrop, false);
}

function handleDrop(e) {
    if (currentView !== 'files') return;
    const dt = e.dataTransfer;
    const files = dt.files;
    if (files.length > 0) {
        uploadFile(files[0]);
    }
}

async function loadFiles() {
    showLoading();
    try {
        let url = `${API_BASE}/files/?`;
        if (currentFolder) {
            url += `folder=${currentFolder.id}`;
        } else {
            url += `folder=`;
        }

        const response = await fetch(url, {
            credentials: 'include',
            headers: { 'Accept': 'application/json' }
        });

        if (response.status === 200) {
            const files = await response.json();
            renderFiles(files);
        } else if (response.status === 401 || response.status === 403) {
            hideLoading();
            showLoginModal();
        } else {
            showEmpty();
        }
    } catch (error) {
        console.error('Error loading files:', error);
        showEmpty();
    }
}

function renderFiles(files) {
    hideLoading();
    if (!files || files.length === 0) {
        showEmpty();
        return;
    }
    hideEmpty();
    filesGrid.innerHTML = '';
    files.forEach((file, index) => {
        if (!file) return;
        const card = createFileCard(file, index);
        filesGrid.appendChild(card);
    });
}

function createFileCard(file, index) {
    const card = document.createElement('div');
    card.className = 'file-card';
    card.style.animationDelay = `${index * 0.1}s`;

    const icon = getFileIcon(file.mime_type);

    // Безопасное получение имени файла
    let fileName = 'Без имени';
    if (file.file_name) {
        fileName = file.file_name;
    } else if (file.file && typeof file.file === 'string') {
        try {
            fileName = file.file.split('/').pop();
            fileName = decodeURIComponent(fileName);
        } catch (e) {
            fileName = 'Без имени';
        }
    }

    // Безопасное получение размера
    const sizeMB = file.size_mb ? `${file.size_mb} MB` : (file.size ? `${(file.size / (1024 * 1024)).toFixed(2)} MB` : '0 MB');

    // Безопасное получение даты
    const uploadedDate = file.uploaded_at ? new Date(file.uploaded_at).toLocaleDateString('ru-RU') : '';

    // Проверяем, есть ли download_url и является ли пользователь владельцем
    const canDownload = file.download_url || file.owner === currentUser?.username;
    const isOwner = file.owner === currentUser?.username;

    card.innerHTML = `
        <div class="file-icon">${icon}</div>
        <div class="file-name" title="${escapeHtml(fileName)}">${escapeHtml(fileName)}</div>
        <div class="file-meta">
            <span>${sizeMB}</span>
            <span>${uploadedDate}</span>
        </div>
        <div class="file-actions">
            ${canDownload ? `<button class="file-action-btn" onclick="downloadFile(${file.id})" title="Скачать">⬇️</button>` : ''}
            ${isOwner ? `<button class="file-action-btn" onclick="shareFile(${file.id})" title="Поделиться">🔗</button>` : ''}
            ${isOwner ? `<button class="file-action-btn" onclick="deleteFile(${file.id})" title="Удалить">🗑️</button>` : ''}
        </div>
    `;

    return card;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function getFileIcon(mimeType) {
    if (!mimeType) return '📁';
    if (mimeType.includes('image')) return '🖼️';
    if (mimeType.includes('pdf')) return '📄';
    if (mimeType.includes('video')) return '🎬';
    if (mimeType.includes('audio')) return '🎵';
    if (mimeType.includes('text')) return '📝';
    if (mimeType.includes('zip') || mimeType.includes('archive')) return '📦';
    return '📁';
}

async function loadFoldersForDropdown() {
    const folderSelect = document.getElementById('folderSelect');
    if (!folderSelect) return;
    folderSelect.innerHTML = '<option value="">Корневая папка</option>';
    try {
        const response = await fetch(`${API_BASE}/folders/`, {
            credentials: 'include',
            headers: { 'Accept': 'application/json' }
        });
        if (response.status === 200) {
            allFolders = await response.json();
            allFolders.forEach(folder => {
                const option = document.createElement('option');
                option.value = folder.id;
                option.textContent = folder.name;
                folderSelect.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Error loading folders:', error);
    }
}

async function uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);
    if (currentFolder) {
        formData.append('folder', currentFolder.id);
    } else {
        const folderSelect = document.getElementById('folderSelect');
        if (folderSelect && folderSelect.value) {
            formData.append('folder', folderSelect.value);
        }
    }
    try {
        const csrftoken = getCookie('csrftoken');
        const response = await fetch(`${API_BASE}/files/`, {
            method: 'POST',
            credentials: 'include',
            headers: { 'X-CSRFToken': csrftoken },
            body: formData
        });
        if (response.ok) {
            hideModal(uploadModal);
            if (uploadForm) uploadForm.reset();
            loadFiles();
        } else {
            const error = await response.json().catch(() => ({}));
            alert(`Ошибка: ${error.detail || error.file?.[0] || 'Неизвестная ошибка'}`);
        }
    } catch (error) {
        console.error('Upload error:', error);
        alert('Ошибка подключения к серверу');
    }
}

async function handleUpload(e) {
    e.preventDefault();
    const fileInput = document.getElementById('fileInput');
    if (!fileInput || !fileInput.files[0]) {
        alert('Выберите файл для загрузки');
        return;
    }
    await uploadFile(fileInput.files[0]);
}

function downloadFile(fileId) {
    // Открываем файл в новой вкладке для скачивания
    window.open(`${API_BASE}/files/${fileId}/`, '_blank');
}

async function shareFile(fileId) {
    const username = prompt('Введите имя пользователя для предоставления доступа:');
    if (!username) return;

    try {
        const csrftoken = getCookie('csrftoken');

        const response = await fetch(`${API_BASE}/files/${fileId}/share/`, {
            method: 'POST',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrftoken,
                'Accept': 'application/json'
            },
            body: JSON.stringify({
                username: username,
                permission: 'read'
            })
        });

        let data;
        try {
            data = await response.json();
        } catch (e) {
            data = {};
        }

        if (response.ok || response.status === 201) {
            alert(`✅ Доступ предоставлен пользователю ${username}`);
        } else {
            // Показываем детальную ошибку
            const errorMessage = data.detail || data.error || JSON.stringify(data) || 'Неизвестная ошибка';
            alert(`❌ Ошибка предоставления доступа:\n${errorMessage}`);
            console.error('Share error:', data);
        }
    } catch (error) {
        console.error('Share error:', error);
        alert(`❌ Ошибка подключения к серверу: ${error.message}`);
    }
}

async function deleteFile(fileId) {
    if (!confirm('Вы уверены, что хотите удалить этот файл?')) return;
    try {
        const csrftoken = getCookie('csrftoken');
        const response = await fetch(`${API_BASE}/files/${fileId}/`, {
            method: 'DELETE',
            credentials: 'include',
            headers: { 'X-CSRFToken': csrftoken }
        });
        if (response.ok || response.status === 204) {
            loadFiles();
        } else {
            alert('Ошибка удаления');
        }
    } catch (error) {
        alert('Ошибка подключения к серверу');
    }
}

async function loadFolders() {
    showLoading();
    try {
        const response = await fetch(`${API_BASE}/folders/`, {
            credentials: 'include',
            headers: { 'Accept': 'application/json' }
        });
        if (response.status === 200) {
            const folders = await response.json();
            renderFolders(folders);
        } else {
            showEmpty();
        }
    } catch (error) {
        console.error('Error loading folders:', error);
        showEmpty();
    }
}

function renderFolders(folders) {
    hideLoading();
    if (!folders || folders.length === 0) {
        showEmpty();
        return;
    }
    hideEmpty();
    filesGrid.innerHTML = '';
    folders.forEach((folder, index) => {
        const card = createFolderCard(folder, index);
        filesGrid.appendChild(card);
    });
}

function createFolderCard(folder, index) {
    const card = document.createElement('div');
    card.className = 'file-card';
    card.style.animationDelay = `${index * 0.1}s`;
    card.style.cursor = 'pointer';

    card.addEventListener('click', (e) => {
        if (!e.target.closest('.file-actions')) {
            currentFolder = folder;
            currentView = 'files';
            navItems.forEach(nav => nav.classList.remove('active'));
            document.querySelector('[data-view="files"]')?.classList.add('active');
            loadView('files');
        }
    });

    card.innerHTML = `
        <div class="file-icon">📁</div>
        <div class="file-name" title="${escapeHtml(folder.name)}">${escapeHtml(folder.name)}</div>
        <div class="file-meta">
            <span>${folder.files_count || 0} файлов</span>
            <span>${new Date(folder.created_at).toLocaleDateString('ru-RU')}</span>
        </div>
        <div class="file-actions">
            <button class="file-action-btn" onclick="deleteFolder(${folder.id})" title="Удалить">🗑️</button>
        </div>
    `;
    return card;
}

async function createFolder() {
    const name = prompt('Введите имя папки:');
    if (!name) return;
    try {
        const csrftoken = getCookie('csrftoken');
        const response = await fetch(`${API_BASE}/folders/`, {
            method: 'POST',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrftoken
            },
            body: JSON.stringify({ name: name })
        });
        if (response.ok) {
            loadFolders();
        } else {
            alert('Ошибка создания папки');
        }
    } catch (error) {
        alert('Ошибка подключения к серверу');
    }
}

async function deleteFolder(folderId) {
    if (!confirm('Удалить эту папку?')) return;
    try {
        const csrftoken = getCookie('csrftoken');
        const response = await fetch(`${API_BASE}/folders/${folderId}/`, {
            method: 'DELETE',
            credentials: 'include',
            headers: { 'X-CSRFToken': csrftoken }
        });
        if (response.ok || response.status === 204) {
            loadFolders();
        } else {
            alert('Ошибка удаления папки');
        }
    } catch (error) {
        alert('Ошибка подключения к серверу');
    }
}

async function loadShared() {
    showLoading();
    try {
        const response = await fetch(`${API_BASE}/permissions/`, {
            credentials: 'include',
            headers: { 'Accept': 'application/json' }
        });
        if (response.status === 200) {
            const permissions = await response.json();
            renderShared(permissions);
        } else {
            showEmpty();
        }
    } catch (error) {
        console.error('Error loading shared:', error);
        showEmpty();
    }
}

function renderShared(permissions) {
    hideLoading();
    if (!permissions || permissions.length === 0) {
        showEmpty();
        return;
    }
    hideEmpty();
    filesGrid.innerHTML = '';
    permissions.forEach((perm, index) => {
        const card = createSharedCard(perm, index);
        filesGrid.appendChild(card);
    });
}

function createSharedCard(perm, index) {
    const card = document.createElement('div');
    card.className = 'file-card';
    card.style.animationDelay = `${index * 0.1}s`;

    let fileName = 'Файл';
    if (perm.file_name) {
        fileName = perm.file_name;
    } else if (perm.file && typeof perm.file === 'number') {
        fileName = `Файл #${perm.file}`;
    }

    const permissionBadge = perm.permission === 'write' ? '✏️ Запись' : '👁️ Чтение';
    const grantedDate = perm.granted_at ? new Date(perm.granted_at).toLocaleDateString('ru-RU') : '';

    card.innerHTML = `
        <div class="file-icon">🔗</div>
        <div class="file-name" title="${escapeHtml(fileName)}">${escapeHtml(fileName)}</div>
        <div class="file-meta">
            <span>${permissionBadge}</span>
            <span>${grantedDate}</span>
        </div>
        <div class="file-actions">
            <button class="file-action-btn" onclick="revokePermission(${perm.id})" title="Отозвать">❌</button>
        </div>
    `;
    return card;
}

async function revokePermission(permId) {
    if (!confirm('Отозвать доступ?')) return;
    try {
        const csrftoken = getCookie('csrftoken');
        const response = await fetch(`${API_BASE}/permissions/${permId}/`, {
            method: 'DELETE',
            credentials: 'include',
            headers: { 'X-CSRFToken': csrftoken }
        });
        if (response.ok || response.status === 204) {
            loadShared();
        } else {
            alert('Ошибка отзыва доступа');
        }
    } catch (error) {
        alert('Ошибка подключения к серверу');
    }
}

async function loadLogs() {
    showLoading();
    try {
        const response = await fetch(`${API_BASE}/audit-logs/`, {
            credentials: 'include',
            headers: { 'Accept': 'application/json' }
        });
        if (response.status === 200) {
            const logs = await response.json();
            renderLogs(logs);
        } else {
            showEmpty();
        }
    } catch (error) {
        console.error('Error loading logs:', error);
        showEmpty();
    }
}

function renderLogs(logs) {
    hideLoading();
    if (!logs || logs.length === 0) {
        showEmpty();
        return;
    }
    hideEmpty();
    filesGrid.innerHTML = '';
    logs.forEach((log, index) => {
        const card = createLogCard(log, index);
        filesGrid.appendChild(card);
    });
}

function createLogCard(log, index) {
    const card = document.createElement('div');
    card.className = 'file-card';
    card.style.animationDelay = `${index * 0.1}s`;

    const actionIcons = {
        'upload': '📤',
        'download': '⬇️',
        'delete': '🗑️',
        'share': '🔗',
        'login': '🔑',
        'logout': '🚪'
    };
    const icon = actionIcons[log.action] || '📝';
    const details = log.details ? `<div class="file-meta" style="margin-top: 0.5rem; font-size: 0.75rem;">${escapeHtml(log.details)}</div>` : '';

    card.innerHTML = `
        <div class="file-icon">${icon}</div>
        <div class="file-name">${escapeHtml(log.action)}</div>
        <div class="file-meta">
            <span>${log.user_username || 'Система'}</span>
            <span>${new Date(log.timestamp).toLocaleString('ru-RU')}</span>
        </div>
        ${details}
    `;
    return card;
}

function showLoading() {
    if (loadingState) loadingState.classList.add('show');
    if (emptyState) emptyState.classList.remove('show');
    filesGrid.style.display = 'none';
}

function hideLoading() {
    if (loadingState) loadingState.classList.remove('show');
    filesGrid.style.display = 'grid';
}

function showEmpty() {
    if (emptyState) emptyState.classList.add('show');
    filesGrid.style.display = 'none';
}

function hideEmpty() {
    if (emptyState) emptyState.classList.remove('show');
}
