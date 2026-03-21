// ==================== CNC Office - Frontend App ====================
const API_BASE = '/api';
let currentUser = null;
let currentFolder = null;
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
const usernameSpan = document.getElementById('username');

// ✅ Инициализация
document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 App initialized');
    setupEventListeners();
    checkAuth();
});

// ✅ Заголовки с токеном
function getAuthHeaders(isJson = true) {
    const headers = {};
    if (authToken) {
        headers['Authorization'] = `Token ${authToken}`;
    }
    if (isJson) {
        headers['Content-Type'] = 'application/json';
    }
    headers['Accept'] = 'application/json';
    return headers;
}

// ✅ Проверка авторизации
async function checkAuth() {
    authToken = localStorage.getItem('cnc_auth_token');
    if (!authToken) {
        showLoginModal();
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/users/me/`, {
            headers: getAuthHeaders()
        });

        if (response.ok) {
            currentUser = await response.json();
            if (usernameSpan) {
                usernameSpan.textContent = currentUser.username;
            }
            loadFiles();
        } else {
            clearAuth();
            showLoginModal();
        }
    } catch (error) {
        console.error('Auth check failed:', error);
        clearAuth();
        showLoginModal();
    }
}

function clearAuth() {
    localStorage.removeItem('cnc_auth_token');
    localStorage.removeItem('cnc_username');
    authToken = null;
    currentUser = null;
}

// ✅ Модалки
function showModal(modal) {
    if (modal) {
        modal.classList.add('show');
        modal.style.display = 'flex';
        document.body.style.overflow = 'hidden';
    }
}

function hideModal(modal) {
    const el = typeof modal === 'string' ? document.getElementById(modal) : modal;
    if (el) {
        el.classList.remove('show');
        setTimeout(() => {
            el.style.display = 'none';
        }, 200);
        document.body.style.overflow = '';
        const form = el.querySelector('form');
        if (form) form.reset();
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
async function handleLogin(event) {
    event.preventDefault();

    const usernameInput = document.getElementById('loginUsername');
    const passwordInput = document.getElementById('loginPassword');
    const username = usernameInput?.value;
    const password = passwordInput?.value;

    if (!username || !password) {
        alert('Введите логин и пароль');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/users/login/`, {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({
                username: username,
                password: password
            })
        });

        const data = await response.json();

        if (response.ok && data.token) {
            authToken = data.token;
            localStorage.setItem('cnc_auth_token', data.token);
            localStorage.setItem('cnc_username', data.user?.username || username);
            currentUser = data.user || { username };

            if (usernameSpan) {
                usernameSpan.textContent = currentUser.username;
            }

            hideModal('loginModal');
            loadFiles(); // ✅ ЗАГРУЖАЕМ ФАЙЛЫ ПОСЛЕ ВХОДА!
        } else {
            const errorMsg = data.detail || data.error || 'Неверный логин или пароль';
            alert(`Ошибка входа: ${errorMsg}`);
        }
    } catch (error) {
        console.error('Login error:', error);
        alert('Ошибка подключения к серверу');
    }
}

// ✅ Регистрация
async function handleRegister(event) {
    event.preventDefault();

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
        const response = await fetch(`${API_BASE}/users/register/`, {
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
            if (data.token) {
                authToken = data.token;
                localStorage.setItem('cnc_auth_token', data.token);
                localStorage.setItem('cnc_username', data.user?.username || username);
                currentUser = data.user || { username };

                if (usernameSpan) {
                    usernameSpan.textContent = currentUser.username;
                }

                hideModal('loginModal');
                loadFiles();
            } else {
                alert('✅ Регистрация успешна! Теперь войдите в систему.');
                if (registerForm) registerForm.classList.add('hidden');
                if (loginForm) loginForm.classList.remove('hidden');
            }
        } else {
            let errorMessage = '❌ Ошибка регистрации:\n';
            if (typeof data === 'object' && data !== null) {
                for (const [key, value] of Object.entries(data)) {
                    if (Array.isArray(value)) {
                        errorMessage += `${key}: ${value.join(', ')}\n`;
                    } else if (typeof value === 'string') {
                        errorMessage += `${value}\n`;
                    }
                }
            }
            alert(errorMessage || 'Неизвестная ошибка');
        }
    } catch (error) {
        console.error('Register error:', error);
        alert('⚠️ Ошибка подключения к серверу: ' + error.message);
    }
}

// ✅ Выход
async function logout() {
    clearAuth();
    location.reload();
}

// ✅ Загрузка файлов
async function loadFiles() {
    console.log('🔄 Loading files...');
    showLoading();

    try {
        let url = `${API_BASE}/files/`;

        const response = await fetch(url, {
            headers: getAuthHeaders()
        });

        console.log('📦 Response status:', response.status);

        if (response.status === 200) {
            const data = await response.json();
            console.log('📦 Files data:', data);

            // Обработка ответа - может быть объект с results или просто массив
            const files = data.results || data || [];
            renderFiles(files);
        } else if (response.status === 401 || response.status === 403) {
            hideLoading();
            clearAuth();
            showLoginModal();
        } else {
            const errorText = await response.text();
            console.error('❌ Files error:', response.status, errorText);
            showEmpty();
        }
    } catch (error) {
        console.error('❌ Load files error:', error);
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

    if (filesGrid) {
        filesGrid.innerHTML = '';
        files.forEach((file, index) => {
            if (file) {
                const card = createFileCard(file, index);
                filesGrid.appendChild(card);
            }
        });
    }
}

function createFileCard(file, index) {
    const card = document.createElement('div');
    card.className = 'file-card';
    card.style.animationDelay = `${index * 0.1}s`;

    const icon = getFileIcon(file.mime_type);
    let name = file.file_name || (file.file ? file.file.split('/').pop() : 'Без имени');

    try {
        name = decodeURIComponent(name);
    } catch (e) {
        // ignore
    }

    const size = file.size_mb ? `${file.size_mb} MB` :
                 file.size ? `${(file.size / 1024 / 1024).toFixed(2)} MB` : '0 MB';

    const date = file.uploaded_at ? new Date(file.uploaded_at).toLocaleDateString('ru-RU') : '';

    const canDownload = file.owner === currentUser?.username;

    card.innerHTML = `
        <div class="file-icon">${icon}</div>
        <div class="file-name" title="${escapeHtml(name)}">${escapeHtml(name)}</div>
        <div class="file-meta">
            <span>${size}</span>
            <span>${date}</span>
        </div>
        <div class="file-actions">
            ${canDownload ? `<button class="file-action-btn" onclick="downloadFile(${file.id})" title="Скачать">⬇️</button>` : ''}
            ${canDownload ? `<button class="file-action-btn" onclick="shareFile(${file.id})" title="Поделиться">🔗</button>` : ''}
            ${canDownload ? `<button class="file-action-btn" onclick="deleteFile(${file.id})" title="Удалить">🗑️</button>` : ''}
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

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ✅ Загрузка файла
async function uploadFile(file) {
    console.log('📤 Uploading file:', file.name);

    const formData = new FormData();
    formData.append('file', file);

    if (currentFolder) {
        formData.append('folder', currentFolder.id);
    }

    try {
        console.log('📤 Sending request to', `${API_BASE}/files/`);

        const response = await fetch(`${API_BASE}/files/`, {
            method: 'POST',
            headers: getAuthHeaders(false), // Не JSON для FormData
            body: formData
        });

        console.log('📤 Response status:', response.status);

        const data = await response.json().catch(() => ({}));
        console.log('📤 Response data:', data);

        if (response.ok || response.status === 201) {
            hideModal('uploadModal');
            if (uploadForm) uploadForm.reset();
            await loadFiles(); // ✅ Перезагружаем список!
        } else {
            const errorMsg = data.detail || data.file?.[0] || data.error || 'Неизвестная ошибка';
            console.error('❌ Upload failed:', response.status, errorMsg);
            alert(`Ошибка загрузки: ${errorMsg}`);
        }
    } catch (error) {
        console.error('❌ Upload error:', error);
        alert('Ошибка подключения к серверу: ' + error.message);
    }
}

async function handleUpload(event) {
    event.preventDefault();
    console.log('📤 Form submitted');

    const fileInput = document.getElementById('fileInput');
    if (!fileInput?.files[0]) {
        alert('Выберите файл');
        return;
    }

    await uploadFile(fileInput.files[0]);
}

// ✅ Скачивание файла
async function downloadFile(fileId) {
    try {
        const response = await fetch(`${API_BASE}/files/${fileId}/download/`, {
            headers: getAuthHeaders()
        });

        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `file_${fileId}`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        } else if (response.status === 401 || response.status === 403) {
            alert('Ошибка авторизации. Войдите снова.');
            clearAuth();
            showLoginModal();
        } else {
            const error = await response.json().catch(() => ({}));
            alert(`Ошибка: ${error.detail || 'Не удалось скачать'}`);
        }
    } catch (error) {
        console.error('Download error:', error);
        alert('Ошибка подключения к серверу');
    }
}

// ✅ Поделиться файлом
async function shareFile(fileId) {
    const username = prompt('Введите имя пользователя:');
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

        if (response.ok) {
            alert(`✅ Доступ предоставлен пользователю ${username}`);
        } else {
            alert(`❌ ${data.detail || 'Ошибка'}`);
        }
    } catch (error) {
        console.error('Share error:', error);
        alert('Ошибка подключения к серверу');
    }
}

// ✅ Удаление файла
async function deleteFile(fileId) {
    if (!confirm('Вы уверены, что хотите удалить этот файл?')) return;

    try {
        const response = await fetch(`${API_BASE}/files/${fileId}/`, {
            method: 'DELETE',
            headers: getAuthHeaders()
        });

        if (response.ok || response.status === 204) {
            await loadFiles();
        } else {
            alert('Ошибка удаления файла');
        }
    } catch (error) {
        console.error('Delete error:', error);
        alert('Ошибка подключения к серверу');
    }
}

// ✅ UI Helpers
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

// ✅ Event Listeners
function setupEventListeners() {
    // Кнопка загрузки
    if (uploadBtn) {
        uploadBtn.addEventListener('click', () => {
            showModal(uploadModal);
        });
    }

    // Кнопка выхода
    if (logoutBtn) {
        logoutBtn.addEventListener('click', logout);
    }

    // Формы
    if (uploadForm) {
        uploadForm.addEventListener('submit', handleUpload);
    }

    if (loginForm) {
        loginForm.addEventListener('submit', handleLogin);
    }

    if (registerForm) {
        registerForm.addEventListener('submit', handleRegister);
    }

    // Переключение между входом и регистрацией
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

    // Закрытие модалок по клику на фон
    [uploadModal, loginModal].forEach(modal => {
        if (modal) {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    hideModal(modal);
                }
            });
        }
    });

    // Кнопка закрытия модалки
    const closeModalBtn = document.getElementById('closeModal');
    if (closeModalBtn) {
        closeModalBtn.addEventListener('click', () => {
            hideModal('uploadModal');
        });
    }
}
