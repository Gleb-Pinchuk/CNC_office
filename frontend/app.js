// ==================== CNC Office - Frontend App ====================
// ✅ Полная версия с токеновой аутентификацией

// ==================== API Configuration ====================
const BASE_URL = window.location.origin;
const API_BASE = `${BASE_URL}/api`;
const AUTH_BASE = `${API_BASE}/users`;  // ✅ /api/users/login/, /api/users/register/

// ==================== State ====================
let currentUser = null;
let currentView = 'files';
let currentFolder = null;
let allFolders = [];
let authToken = localStorage.getItem('cnc_auth_token');  // ✅ Токен из localStorage

// ==================== DOM Elements ====================
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

// ==================== Init ====================
document.addEventListener('DOMContentLoaded', () => {
    checkAuth();
    setupEventListeners();
    setupDragAndDrop();
});

// ==================== Helpers ====================

// ✅ Получение заголовков с токеном авторизации
function getAuthHeaders(isJson = true) {
    const headers = {
        'Accept': 'application/json',
    };
    
    if (authToken) {
        headers['Authorization'] = `Token ${authToken}`;
    }
    
    // CSRF токен для совместимости (опционально)
    const csrftoken = getCookie('csrftoken');
    if (csrftoken) {
        headers['X-CSRFToken'] = csrftoken;
    }
    
    if (isJson) {
        headers['Content-Type'] = 'application/json';
    }
    // Для FormData Content-Type НЕ устанавливаем — браузер сам добавит boundary
    
    return headers;
}

// ✅ Получение cookie по имени
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

// ✅ Экранирование HTML для защиты от XSS
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

// ✅ Проверка авторизации при загрузке страницы
async function checkAuth() {
    const savedUsername = localStorage.getItem('cnc_username');
    authToken = localStorage.getItem('cnc_auth_token');

    // Если нет токена — показываем модалку входа
    if (!authToken) {
        showLoginModal();
        return;
    }

    try {
        // Проверяем токен, запрашивая профиль текущего пользователя
        const response = await fetch(`${AUTH_BASE}/me/`, {
            headers: getAuthHeaders()
        });

        if (response.status === 200) {
            const user = await response.json();
            currentUser = user;
            document.getElementById('username').textContent = user.username || savedUsername;
            loadView('files');
        } else {
            // Токен невалиден — очищаем и показываем логин
            clearAuth();
            showLoginModal();
        }
    } catch (error) {
        console.error('Auth check error:', error);
        clearAuth();
        showLoginModal();
    }
}

// ==================== Modal Functions ====================

function showModal(modal) {
    if (modal) {
        modal.classList.add('show');
        modal.style.display = 'flex';
    }
}

function hideModal(modal) {
    if (modal) {
        modal.classList.remove('show');
        modal.style.display = 'none';
        // Сбрасываем формы при закрытии
        if (modal === loginModal && loginForm) loginForm.reset();
        if (modal === uploadModal && uploadForm) uploadForm.reset();
        if (registerForm) registerForm.reset();
    }
}

function showLoginModal() {
    // Показываем форму логина, скрываем регистрацию
    if (loginForm) loginForm.classList.remove('hidden');
    if (registerForm) registerForm.classList.add('hidden');
    showModal(loginModal);
}

function showRegisterModal() {
    // Показываем форму регистрации, скрываем логин
    if (registerForm) registerForm.classList.remove('hidden');
    if (loginForm) loginForm.classList.add('hidden');
    showModal(loginModal);
}

// ==================== Authentication ====================

// ✅ Вход в систему
async function handleLogin(e) {
    e.preventDefault();

    const username = document.getElementById('loginUsername')?.value;
    const password = document.getElementById('loginPassword')?.value;

    if (!username || !password) {
        alert('Введите логин и пароль');
        return;
    }

    try {
        const response = await fetch(`${AUTH_BASE}/login/`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({
                username: username,
                password: password
            })
        });

        const data = await response.json();

        if (response.ok && data.token) {
            // ✅ Сохраняем токен и данные пользователя
            authToken = data.token;
            localStorage.setItem('cnc_auth_token', data.token);
            localStorage.setItem('cnc_username', data.user?.username || username);
            
            currentUser = data.user || { username: username };
            document.getElementById('username').textContent = currentUser.username;
            
            hideModal(loginModal);
            loadView('files');
        } else {
            const errorMsg = data.detail || data.error || data.non_field_errors?.[0] || 'Неверный логин или пароль';
            alert(`Ошибка входа: ${errorMsg}`);
        }
    } catch (error) {
        console.error('Login error:', error);
        alert('Ошибка подключения к серверу');
    }
}

// ✅ Регистрация нового пользователя
async function handleRegister(e) {
    if (e) e.preventDefault();

    const username = document.getElementById('registerUsername')?.value;
    const email = document.getElementById('registerEmail')?.value;
    const password = document.getElementById('registerPassword')?.value;
    const password2 = document.getElementById('registerPassword2')?.value;

    if (!username || !email || !password || !password2) {
        alert('Заполните все поля');
        return;
    }

    if (password !== password2) {
        alert('Пароли не совпадают');
        return;
    }

    if (password.length < 8) {
        alert('Пароль должен содержать минимум 8 символов');
        return;
    }

    try {
        const response = await fetch(`${AUTH_BASE}/register/`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({
                username: username,
                email: email,
                password: password,
                password2: password2
            })
        });

        const data = await response.json();

        if (response.ok || response.status === 201) {
            // ✅ Если сервер вернул токен — авто-вход
            if (data.token) {
                authToken = data.token;
                localStorage.setItem('cnc_auth_token', data.token);
                localStorage.setItem('cnc_username', data.user?.username || username);
                currentUser = data.user || { username: username };
                document.getElementById('username').textContent = currentUser.username;
                hideModal(loginModal);
                loadView('files');
            } else {
                alert('✅ Регистрация успешна! Теперь войдите в систему.');
                // Переключаем на форму логина
                if (registerForm) registerForm.classList.add('hidden');
                if (loginForm) loginForm.classList.remove('hidden');
            }
        } else {
            // Показываем ошибки валидации
            const errors = [];
            if (data.username) errors.push(`Логин: ${Array.isArray(data.username) ? data.username.join(', ') : data.username}`);
            if (data.email) errors.push(`Email: ${Array.isArray(data.email) ? data.email.join(', ') : data.email}`);
            if (data.password) errors.push(`Пароль: ${Array.isArray(data.password) ? data.password.join(', ') : data.password}`);
            if (data.password2) errors.push(`Подтверждение: ${Array.isArray(data.password2) ? data.password2.join(', ') : data.password2}`);
            if (data.detail) errors.push(data.detail);
            if (data.non_field_errors) errors.push(data.non_field_errors.join(', '));
            
            alert(`Ошибка регистрации:\n${errors.join('\n') || 'Неизвестная ошибка'}`);
        }
    } catch (error) {
        console.error('Register error:', error);
        alert('Ошибка подключения к серверу');
    }
}

// ✅ Выход из системы
async function logout() {
    // Уведомляем сервер о выходе (опционально)
    if (authToken) {
        try {
            await fetch(`${AUTH_BASE}/logout/`, {
                method: 'POST',
                headers: getAuthHeaders()
            });
        } catch (e) {
            console.error('Logout notify error:', e);
        }
    }
    
    clearAuth();
    location.reload();
}

// ==================== Event Listeners ====================

function setupEventListeners() {
    // Кнопка загрузки/создания папки
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

    // Кнопка выхода
    if (logoutBtn) {
        logoutBtn.addEventListener('click', logout);
    }

    // Форма загрузки файла
    if (uploadForm) {
        uploadForm.addEventListener('submit', handleUpload);
    }
    
    // Форма входа
    if (loginForm) {
        loginForm.addEventListener('submit', handleLogin);
    }
    
    // Форма регистрации
    if (registerForm) {
        registerForm.addEventListener('submit', handleRegister);
    }

    // Переключение между "Войти" и "Зарегистрироваться"
    const toggleToRegister = document.getElementById('toggleToRegister');
    if (toggleToRegister) {
        toggleToRegister.addEventListener('click', (e) => {
            e.preventDefault();
            showRegisterModal();
        });
    }

    const toggleToLogin = document.getElementById('toggleToLogin');
    if (toggleToLogin) {
        toggleToLogin.addEventListener('click', (e) => {
            e.preventDefault();
            showLoginModal();
        });
    }

    // Навигация по разделам
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

    // Закрытие модалок по клику вне контента
    [uploadModal, loginModal].forEach(modal => {
        if (modal) {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) hideModal(modal);
            });
        }
    });

    // Кнопка закрытия модалки
    const closeModalBtn = document.getElementById('closeModal');
    if (closeModalBtn) {
        closeModalBtn.addEventListener('click', () => {
            hideModal(uploadModal);
        });
    }
}

// ==================== View Loading ====================

async function loadView(view) {
    currentView = view;

    // Обновляем кнопку действия
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

    // Обновляем заголовок страницы
    const titles = {
        'files': 'Мои файлы',
        'folders': 'Папки',
        'shared': 'Общий доступ',
        'logs': 'Журнал аудита'
    };
    if (pageTitle) {
        pageTitle.textContent = titles[view] || 'CNC Office';
    }

    // Обновляем навигацию
    navItems.forEach(nav => {
        if (nav.getAttribute('data-view') === view) {
            nav.classList.add('active');
        } else {
            nav.classList.remove('active');
        }
    });

    updateBreadcrumb();
    showLoading();

    // Загружаем контент в зависимости от раздела
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
            await loadFiles();
    }
}

// ==================== Breadcrumb ====================

function updateBreadcrumb() {
    // Удаляем старый хлебные крошки
    let breadcrumb = document.querySelector('.breadcrumb');
    if (breadcrumb) {
        breadcrumb.remove();
    }

    // Показываем только для раздела "Файлы"
    if (currentView !== 'files') return;

    breadcrumb = document.createElement('div');
    breadcrumb.className = 'breadcrumb';
    breadcrumb.style.cssText = 'margin-bottom: 1rem; padding: 0.5rem 1rem; background: #f3f4f6; border-radius: 0.5rem; font-size: 0.9rem;';

    let html = '<a href="#" onclick="navigateToFolder(null); return false;" style="color: #4F46E5; text-decoration: none; font-weight: 500;">📁 Корень</a>';

    if (currentFolder) {
        html += ` <span style="color: #6B7280; margin: 0 0.25rem;">/</span> <span style="font-weight: 600; color: #374151;">${escapeHtml(currentFolder.name)}</span>`;
    }

    breadcrumb.innerHTML = html;

    // Вставляем после заголовка
    if (pageTitle && pageTitle.parentNode) {
        pageTitle.parentNode.insertBefore(breadcrumb, pageTitle.nextSibling);
    }
}

// ✅ Навигация по папкам
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

// ==================== Drag & Drop ====================

function setupDragAndDrop() {
    const dropZone = document.querySelector('.content-area') || 
                     document.querySelector('.main-content') || 
                     document.body;
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

    function highlight() {
        dropZone.style.border = '3px dashed #4F46E5';
        dropZone.style.borderRadius = '12px';
        dropZone.style.backgroundColor = 'rgba(79, 70, 229, 0.05)';
    }

    function unhighlight() {
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

// ==================== Files Loading ====================

async function loadFiles() {
    showLoading();
    try {
        let url = `${API_BASE}/files/?`;
        if (currentFolder) {
            url += `folder=${currentFolder.id}`;
        }

        const response = await fetch(url, {
            headers: getAuthHeaders()  // ✅ Токен в заголовке
        });

        if (response.status === 200) {
            const files = await response.json();
            renderFiles(files);
        } else if (response.status === 401 || response.status === 403) {
            hideLoading();
            clearAuth();
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

    // Размер файла
    const sizeMB = file.size_mb 
        ? `${file.size_mb} MB` 
        : (file.size ? `${(file.size / (1024 * 1024)).toFixed(2)} MB` : '0 MB');

    // Дата загрузки
    const uploadedDate = file.uploaded_at 
        ? new Date(file.uploaded_at).toLocaleDateString('ru-RU') 
        : '';

    // Права доступа
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

// ==================== File Actions ====================

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
        // ✅ Для FormData НЕ указываем Content-Type — браузер добавит boundary автоматически
        const headers = getAuthHeaders(false);  // false = не добавлять Content-Type
        
        const response = await fetch(`${API_BASE}/files/`, {
            method: 'POST',
            headers: headers,
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
        const response = await fetch(`${API_BASE}/files/${fileId}/share/`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({
                username: username,
                permission: 'read'
            })
        });

        const data = await response.json().catch(() => ({}));

        if (response.ok || response.status === 201) {
            alert(`✅ Доступ предоставлен пользователю ${username}`);
        } else {
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
        const response = await fetch(`${API_BASE}/files/${fileId}/`, {
            method: 'DELETE',
            headers: getAuthHeaders()
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

// ==================== Folders Loading ====================

async function loadFoldersForDropdown() {
    const folderSelect = document.getElementById('folderSelect');
    if (!folderSelect) return;
    
    folderSelect.innerHTML = '<option value="">Корневая папка</option>';
    
    try {
        const response = await fetch(`${API_BASE}/folders/`, {
            headers: getAuthHeaders()
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

async function loadFolders() {
    showLoading();
    try {
        const response = await fetch(`${API_BASE}/folders/`, {
            headers: getAuthHeaders()
        });
        
        if (response.status === 200) {
            const folders = await response.json();
            renderFolders(folders);
        } else if (response.status === 401 || response.status === 403) {
            hideLoading();
            clearAuth();
            showLoginModal();
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

    // Клик по карточке — переход в папку
    card.addEventListener('click', (e) => {
        if (!e.target.closest('.file-actions')) {
            currentFolder = folder;
            currentView = 'files';
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
            <button class="file-action-btn" onclick="deleteFolder(${folder.id}); event.stopPropagation();" title="Удалить">🗑️</button>
        </div>
    `;
    
    return card;
}

async function createFolder() {
    const name = prompt('Введите имя папки:');
    if (!name || name.trim() === '') return;
    
    try {
        const response = await fetch(`${API_BASE}/folders/`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({ name: name.trim() })
        });
        
        if (response.ok) {
            loadFolders();
        } else {
            const error = await response.json().catch(() => ({}));
            alert(`Ошибка: ${error.detail || error.name?.[0] || 'Неизвестная ошибка'}`);
        }
    } catch (error) {
        console.error('Create folder error:', error);
        alert('Ошибка подключения к серверу');
    }
}

async function deleteFolder(folderId) {
    if (!confirm('Удалить эту папку? Все файлы в ней также будут удалены.')) return;
    
    try {
        const response = await fetch(`${API_BASE}/folders/${folderId}/`, {
            method: 'DELETE',
            headers: getAuthHeaders()
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

// ==================== Shared Files ====================

async function loadShared() {
    showLoading();
    try {
        const response = await fetch(`${API_BASE}/permissions/`, {
            headers: getAuthHeaders()
        });
        
        if (response.status === 200) {
            const permissions = await response.json();
            renderShared(permissions);
        } else if (response.status === 401 || response.status === 403) {
            hideLoading();
            clearAuth();
            showLoginModal();
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

    const permissionBadge = perm.permission === 'write' 
        ? '<span style="background:#10B981;color:white;padding:2px 8px;border-radius:12px;font-size:0.75rem">✏️ Запись</span>' 
        : '<span style="background:#6B7280;color:white;padding:2px 8px;border-radius:12px;font-size:0.75rem">👁️ Чтение</span>';
    
    const grantedDate = perm.granted_at 
        ? new Date(perm.granted_at).toLocaleDateString('ru-RU') 
        : '';

    card.innerHTML = `
        <div class="file-icon">🔗</div>
        <div class="file-name" title="${escapeHtml(fileName)}">${escapeHtml(fileName)}</div>
        <div class="file-meta">
            ${permissionBadge}
            <span>${grantedDate}</span>
        </div>
        <div class="file-actions">
            <button class="file-action-btn" onclick="revokePermission(${perm.id})" title="Отозвать">❌</button>
        </div>
    `;
    
    return card;
}

async function revokePermission(permId) {
    if (!confirm('Отозвать доступ к этому файлу?')) return;
    
    try {
        const response = await fetch(`${API_BASE}/permissions/${permId}/`, {
            method: 'DELETE',
            headers: getAuthHeaders()
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

// ==================== Audit Logs ====================

async function loadLogs() {
    showLoading();
    try {
        const response = await fetch(`${API_BASE}/audit-logs/`, {
            headers: getAuthHeaders()
        });
        
        if (response.status === 200) {
            const logs = await response.json();
            renderLogs(logs);
        } else if (response.status === 401 || response.status === 403) {
            hideLoading();
            clearAuth();
            showLoginModal();
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
        'logout': '🚪',
        'create_folder': '📁',
        'delete_folder': '🗂️'
    };
    
    const icon = actionIcons[log.action] || '📝';
    
    const details = log.details 
        ? `<div class="file-meta" style="margin-top: 0.5rem; font-size: 0.75rem; color: #6B7280;">${escapeHtml(log.details)}</div>` 
        : '';

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

// ==================== UI Helpers ====================

function showLoading() {
    if (loadingState) {
        loadingState.classList.add('show');
        loadingState.style.display = 'flex';
    }
    if (emptyState) emptyState.classList.remove('show');
    if (filesGrid) filesGrid.style.display = 'none';
}

function hideLoading() {
    if (loadingState) {
        loadingState.classList.remove('show');
        loadingState.style.display = 'none';
    }
    if (filesGrid) filesGrid.style.display = 'grid';
}

function showEmpty() {
    if (emptyState) {
        emptyState.classList.add('show');
        emptyState.style.display = 'flex';
    }
    if (filesGrid) filesGrid.style.display = 'none';
    if (loadingState) loadingState.style.display = 'none';
}

function hideEmpty() {
    if (emptyState) {
        emptyState.classList.remove('show');
        emptyState.style.display = 'none';
    }
}
