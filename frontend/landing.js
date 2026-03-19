// ==================== CNC Office - Landing Page ====================

// ==================== CSRF Token Helper ====================
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

// ==================== Auth Headers Helper ====================
function getAuthHeaders(isJson = true) {
    const headers = {
        'Accept': 'application/json',
    };
    
    // ✅ Добавляем токен, если он есть в localStorage
    const token = localStorage.getItem('cnc_auth_token');
    if (token) {
        headers['Authorization'] = `Token ${token}`;
    }
    
    if (isJson) {
        headers['Content-Type'] = 'application/json';
    }
    
    // CSRF токен для совместимости (опционально)
    const csrftoken = getCookie('csrftoken');
    if (csrftoken) {
        headers['X-CSRFToken'] = csrftoken;
    }
    
    return headers;
}

// ==================== Modal Functions ====================

function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('show');
        modal.style.display = 'flex';
        document.body.style.overflow = 'hidden';
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('show');
        setTimeout(() => {
            modal.style.display = 'none';
        }, 200); // Ждём завершения анимации
        document.body.style.overflow = '';
        // Сбрасываем формы при закрытии
        const form = modal.querySelector('form');
        if (form) form.reset();
    }
}

function switchModal(fromId, toId) {
    closeModal(fromId);
    setTimeout(() => openModal(toId), 200);
}

// Закрытие модалок по клику на фон
document.querySelectorAll('.modal').forEach(modal => {
    modal.addEventListener('click', (e) => {
        if (e.target === modal || e.target.classList.contains('modal-backdrop')) {
            closeModal(modal.id);
        }
    });
});

// Закрытие по Escape
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        document.querySelectorAll('.modal.show').forEach(modal => {
            closeModal(modal.id);
        });
    }
});

// ==================== Auth Functions ====================

// ✅ Вход в систему (токен-аутентификация)
async function handleLogin(event) {
    event.preventDefault();
    
    const username = document.getElementById('loginUsername')?.value;
    const password = document.getElementById('loginPassword')?.value;
    const submitBtn = event.target.querySelector('button[type="submit"]');
    
    if (!username || !password) {
        alert('Введите логин и пароль');
        return;
    }
    
    // Блокируем кнопку, показываем лоадер
    const originalText = submitBtn.innerHTML;
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner-small"></span> Вход...';
    
    try {
        // ✅ Используем JSON, а не FormData
        const response = await fetch('/api/users/login/', {
            method: 'POST',
            headers: getAuthHeaders(),  // ✅ Токен/CSRF в заголовках
            // credentials: 'include',  // ❌ Не нужно для токен-аутентификации
            body: JSON.stringify({
                username: username,
                password: password
            })
        });
        
        const data = await response.json();
        
        if (response.ok && data.token) {
            // ✅ Сохраняем токен и пользователя
            localStorage.setItem('cnc_auth_token', data.token);
            localStorage.setItem('cnc_username', data.user?.username || username);
            
            // Перенаправляем в приложение
            window.location.href = '/app/';
        } else {
            // Показываем ошибку от сервера
            const errorMsg = data.detail || data.error || data.non_field_errors?.[0] || 'Неверный логин или пароль';
            alert(`Ошибка входа: ${errorMsg}`);
        }
    } catch (error) {
        console.error('Login error:', error);
        alert('Ошибка подключения к серверу');
    } finally {
        // Разблокируем кнопку
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalText;
    }
}

// ✅ Регистрация нового пользователя
async function handleRegister(event) {
    event.preventDefault();
    
    const username = document.getElementById('regUsername')?.value;
    const email = document.getElementById('regEmail')?.value;
    const password1 = document.getElementById('regPassword')?.value;
    const password2 = document.getElementById('regPasswordConfirm')?.value;
    const terms = document.querySelector('input[name="terms"]')?.checked;
    const submitBtn = event.target.querySelector('button[type="submit"]');
    
    // Валидация
    if (!username || !email || !password1 || !password2) {
        alert('Заполните все поля');
        return;
    }
    
    if (password1 !== password2) {
        alert('Пароли не совпадают');
        return;
    }
    
    if (password1.length < 8) {
        alert('Пароль должен содержать минимум 8 символов');
        return;
    }
    
    if (!terms) {
        alert('Необходимо согласиться с условиями использования');
        return;
    }
    
    // Блокируем кнопку
    const originalText = submitBtn.innerHTML;
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner-small"></span> Регистрация...';
    
    try {
        // ✅ Отправляем JSON с правильными полями
        const response = await fetch('/api/users/register/', {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({
                username: username,
                email: email,
                password: password1,
                password2: password2  // ✅ Бэкенд ожидает password2, не password_confirm!
            })
        });
        
        const data = await response.json().catch(() => ({}));
        
        if (response.ok || response.status === 201) {
            // ✅ Если сервер вернул токен — авто-вход
            if (data.token) {
                localStorage.setItem('cnc_auth_token', data.token);
                localStorage.setItem('cnc_username', data.user?.username || username);
                window.location.href = '/app/';
            } else {
                alert('✅ Регистрация успешна! Теперь войдите в систему.');
                switchModal('registerModal', 'loginModal');
                // Авто-заполнение логина для удобства
                document.getElementById('loginUsername').value = username;
            }
        } else {
            // Показываем ошибки валидации
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
            if (data.detail) errorMessage += data.detail;
            
            alert(errorMessage || 'Неизвестная ошибка');
        }
    } catch (error) {
        console.error('Register error:', error);
        alert('⚠️ Ошибка подключения к серверу: ' + error.message);
    } finally {
        // Разблокируем кнопку
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalText;
    }
}

// ==================== UI Functions ====================

function scrollToFeatures() {
    document.getElementById('features')?.scrollIntoView({ behavior: 'smooth' });
}

// Анимация навбара при скролле
window.addEventListener('scroll', () => {
    const navbar = document.querySelector('.navbar');
    if (navbar) {
        if (window.scrollY > 50) {
            navbar.classList.add('scrolled');
        } else {
            navbar.classList.remove('scrolled');
        }
    }
});

// Эффект свечения карточек при наведении
document.querySelectorAll('.feature-card').forEach(card => {
    card.addEventListener('mousemove', (e) => {
        const rect = card.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        card.style.setProperty('--mouse-x', `${x}px`);
        card.style.setProperty('--mouse-y', `${y}px`);
    });
});

// ==================== Init ====================
document.addEventListener('DOMContentLoaded', () => {
    // Проверка скролла для навбара
    if (window.scrollY > 50) {
        document.querySelector('.navbar')?.classList.add('scrolled');
    }
    
    // ✅ Если пользователь уже авторизован — меняем кнопки в навбаре
    const token = localStorage.getItem('cnc_auth_token');
    const navActions = document.querySelector('.nav-actions');
    
    if (token && navActions) {
        const username = localStorage.getItem('cnc_username') || 'Пользователь';
        navActions.innerHTML = `
            <span style="color: #fff; margin-right: 1rem;">${username}</span>
            <a href="/app/" class="btn btn-primary">
                <svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M9 5l7 7-7 7"/>
                </svg>
                В приложение
            </a>
        `;
    }
});
