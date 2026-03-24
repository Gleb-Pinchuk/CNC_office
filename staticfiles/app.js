// API Configuration
const API_BASE = 'http://localhost:8000/api';

// State
let currentUser = null;
let currentFiles = [];

// DOM Elements
const filesGrid = document.getElementById('filesGrid');
const loadingState = document.getElementById('loadingState');
const emptyState = document.getElementById('emptyState');
const uploadModal = document.getElementById('uploadModal');
const loginModal = document.getElementById('loginModal');
const uploadBtn = document.getElementById('uploadBtn');
const logoutBtn = document.getElementById('logoutBtn');
const uploadForm = document.getElementById('uploadForm');
const loginForm = document.getElementById('loginForm');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    checkAuth();
    setupEventListeners();
});

// Check Authentication
async function checkAuth() {
    try {
        const response = await fetch(`${API_BASE}/files/`, {
            credentials: 'include'
        });

        if (response.status === 401 || response.status === 403) {
            showLoginModal();
        } else {
            currentUser = 'authenticated';
            document.getElementById('username').textContent = 'Пользователь';
            loadFiles();
        }
    } catch (error) {
        showLoginModal();
    }
}

// Setup Event Listeners
function setupEventListeners() {
    uploadBtn.addEventListener('click', () => showModal(uploadModal));
    logoutBtn.addEventListener('click', logout);
    uploadForm.addEventListener('submit', handleUpload);
    loginForm.addEventListener('submit', handleLogin);

    // Close modal on click outside
    [uploadModal, loginModal].forEach(modal => {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) hideModal(modal);
        });
    });

    // Close buttons
    document.getElementById('closeModal').addEventListener('click', () => {
        hideModal(uploadModal);
    });
}

// Modal Functions
function showModal(modal) {
    modal.classList.add('show');
}

function hideModal(modal) {
    modal.classList.remove('show');
}

// Login
async function handleLogin(e) {
    e.preventDefault();

    const username = document.getElementById('loginUsername').value;
    const password = document.getElementById('loginPassword').value;

    try {
        const formData = new FormData();
        formData.append('username', username);
        formData.append('password', password);

        const response = await fetch(`${API_BASE}/api-auth/login/`, {
            method: 'POST',
            credentials: 'include',
            body: formData
        });

        if (response.ok) {
            currentUser = username;
            document.getElementById('username').textContent = username;
            hideModal(loginModal);
            loadFiles();
        } else {
            alert('Ошибка входа. Проверьте логин и пароль.');
        }
    } catch (error) {
        alert('Ошибка подключения к серверу');
    }
}

// Logout
async function logout() {
    try {
        await fetch(`${API_BASE}/api-auth/logout/`, {
            method: 'POST',
            credentials: 'include'
        });
    } catch (error) {
        console.error('Logout error:', error);
    }

    currentUser = null;
    showLoginModal();
}

function showLoginModal() {
    showModal(loginModal);
}

// Load Files
async function loadFiles() {
    showLoading();

    try {
        const response = await fetch(`${API_BASE}/files/`, {
            credentials: 'include'
        });

        if (response.ok) {
            currentFiles = await response.json();
            renderFiles(currentFiles);
        } else {
            showEmpty();
        }
    } catch (error) {
        console.error('Error loading files:', error);
        showEmpty();
    }
}

// Render Files
function renderFiles(files) {
    hideLoading();

    if (files.length === 0) {
        showEmpty();
        return;
    }

    hideEmpty();
    filesGrid.innerHTML = '';

    files.forEach((file, index) => {
        const card = createFileCard(file, index);
        filesGrid.appendChild(card);
    });
}

// Create File Card
function createFileCard(file, index) {
    const card = document.createElement('div');
    card.className = 'file-card';
    card.style.animationDelay = `${index * 0.1}s`;

    const icon = getFileIcon(file.mime_type);
    const sizeMB = (file.size / (1024 * 1024)).toFixed(2);

    card.innerHTML = `
        <div class="file-icon">${icon}</div>
        <div class="file-name">${file.file.split('/').pop()}</div>
        <div class="file-meta">
            <span>${sizeMB} MB</span>
            <span>${new Date(file.uploaded_at).toLocaleDateString()}</span>
        </div>
        <div class="file-actions">
            <button class="file-action-btn" onclick="downloadFile(${file.id})" title="Скачать">⬇️</button>
            <button class="file-action-btn" onclick="shareFile(${file.id})" title="Поделиться">🔗</button>
            <button class="file-action-btn" onclick="deleteFile(${file.id})" title="Удалить">🗑️</button>
        </div>
    `;

    return card;
}

// File Icon by MIME Type
function getFileIcon(mimeType) {
    if (mimeType.includes('image')) return '🖼️';
    if (mimeType.includes('pdf')) return '📄';
    if (mimeType.includes('video')) return '🎬';
    if (mimeType.includes('audio')) return '🎵';
    if (mimeType.includes('text')) return '📝';
    if (mimeType.includes('zip') || mimeType.includes('archive')) return '📦';
    return '📁';
}

// Upload File
async function handleUpload(e) {
    e.preventDefault();

    const formData = new FormData(uploadForm);

    try {
        const response = await fetch(`${API_BASE}/files/`, {
            method: 'POST',
            credentials: 'include',
            body: formData
        });

        if (response.ok) {
            hideModal(uploadModal);
            uploadForm.reset();
            loadFiles();
        } else {
            const error = await response.json();
            alert(`Ошибка загрузки: ${JSON.stringify(error)}`);
        }
    } catch (error) {
        alert('Ошибка подключения к серверу');
    }
}

// Download File
async function downloadFile(fileId) {
    window.open(`${API_BASE}/files/${fileId}/`, '_blank');
}

// Share File
async function shareFile(fileId) {
    const username = prompt('Введите имя пользователя для доступа:');
    if (!username) return;

    try {
        const response = await fetch(`${API_BASE}/permissions/`, {
            method: 'POST',
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                file: fileId,
                user: username, // В реальном проекте нужно ID пользователя
                permission: 'read'
            })
        });

        if (response.ok) {
            alert('Доступ предоставлен!');
        } else {
            alert('Ошибка предоставления доступа');
        }
    } catch (error) {
        alert('Ошибка подключения к серверу');
    }
}

// Delete File
async function deleteFile(fileId) {
    if (!confirm('Вы уверены, что хотите удалить этот файл?')) return;

    try {
        const response = await fetch(`${API_BASE}/files/${fileId}/`, {
            method: 'DELETE',
            credentials: 'include'
        });

        if (response.ok) {
            loadFiles();
        } else {
            alert('Ошибка удаления файла');
        }
    } catch (error) {
        alert('Ошибка подключения к серверу');
    }
}

// State Functions
function showLoading() {
    loadingState.classList.add('show');
    emptyState.classList.remove('show');
    filesGrid.style.display = 'none';
}

function hideLoading() {
    loadingState.classList.remove('show');
    filesGrid.style.display = 'grid';
}

function showEmpty() {
    emptyState.classList.add('show');
    filesGrid.style.display = 'none';
}

function hideEmpty() {
    emptyState.classList.remove('show');
}
