
// CSRF Token Helper
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

function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('show');
        document.body.style.overflow = 'hidden';
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('show');
        document.body.style.overflow = '';
    }
}

function switchModal(fromId, toId) {
    closeModal(fromId);
    setTimeout(() => openModal(toId), 300);
}

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        document.querySelectorAll('.modal.show').forEach(modal => {
            modal.classList.remove('show');
        });
        document.body.style.overflow = '';
    }
});

function scrollToFeatures() {
    document.getElementById('features')?.scrollIntoView({ behavior: 'smooth' });
}

async function handleLogin(event) {
    event.preventDefault();
    
    const username = document.getElementById('loginUsername').value;
    const password = document.getElementById('loginPassword').value;
    
    const formData = new FormData();
    formData.append('username', username);
    formData.append('password', password);
    
    try {
        const csrftoken = getCookie('csrftoken');
        
        const response = await fetch('/api-auth/login/', {
            method: 'POST',
            credentials: 'include',
            headers: {
                'X-CSRFToken': csrftoken,
                'Accept': 'application/json'
            },
            body: formData
        });
        
        if (response.ok || response.status === 302) {
            localStorage.setItem('cnc_username', username);
            window.location.href = '/app/';
        } else {
            alert('Ошибка входа: Неверный логин или пароль');
        }
    } catch (error) {
        console.error('Login error:', error);
        alert('Ошибка подключения к серверу');
    }
}

async function handleRegister(event) {
    event.preventDefault();
    
    const username = document.getElementById('regUsername').value;
    const email = document.getElementById('regEmail').value;
    const password1 = document.getElementById('regPassword').value;
    const password2 = document.getElementById('regPasswordConfirm').value;
    
    if (password1 !== password2) {
        alert('Пароли не совпадают');
        return;
    }
    
    try {
        const csrftoken = getCookie('csrftoken');
        
        const response = await fetch('/api/users/register/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrftoken || '',
                'Accept': 'application/json'
            },
            credentials: 'include',
            body: JSON.stringify({
                username: username,
                email: email,
                password: password1,
                password_confirm: password2
            })
        });
        
        const data = await response.json().catch(() => ({}));
        
        if (response.ok || response.status === 201) {
            alert('✅ Аккаунт успешно создан! Теперь войдите.');
            switchModal('registerModal', 'loginModal');
            document.getElementById('registerForm')?.reset();
        } else {
            let errorMessage = '❌ Ошибка регистрации:\n';
            if (typeof data === 'object' && data !== null) {
                for (const [key, value] of Object.entries(data)) {
                    if (Array.isArray(value)) {
                        errorMessage += `${key}: ${value.join(', ')}\n`;
                    } else {
                        errorMessage += `${value}\n`;
                    }
                }
            } else {
                errorMessage += data.detail || 'Неизвестная ошибка';
            }
            alert(errorMessage);
        }
    } catch (error) {
        console.error('Register error:', error);
        alert('⚠️ Ошибка: ' + error.message);
    }
}

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

document.querySelectorAll('.feature-card').forEach(card => {
    card.addEventListener('mousemove', (e) => {
        const rect = card.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        card.style.setProperty('--mouse-x', `${x}px`);
        card.style.setProperty('--mouse-y', `${y}px`);
    });
});

document.addEventListener('DOMContentLoaded', () => {
    if (window.scrollY > 50) {
        document.querySelector('.navbar')?.classList.add('scrolled');
    }
});
