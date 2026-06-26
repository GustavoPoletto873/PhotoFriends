(function () {
  'use strict';

  if (localStorage.getItem('pf_token')) {
    window.location.href = '/home.html';
    return;
  }

  const tabBtns = document.querySelectorAll('.tab-btn');
  const loginForm = document.getElementById('login-form');
  const registerForm = document.getElementById('register-form');
  const errorMsg = document.getElementById('error-msg');

  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      tabBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      errorMsg.classList.remove('show');
      if (btn.dataset.tab === 'login') {
        loginForm.style.display = '';
        registerForm.style.display = 'none';
      } else {
        loginForm.style.display = 'none';
        registerForm.style.display = '';
      }
    });
  });

  function showError(msg) {
    errorMsg.textContent = msg;
    errorMsg.classList.add('show');
  }

  function saveAuth(data) {
    localStorage.setItem('pf_token', data.token);
    localStorage.setItem('pf_user', JSON.stringify(data.user));
    window.location.href = '/home.html';
  }

  loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    errorMsg.classList.remove('show');
    const username = document.getElementById('login-username').value.trim();
    const password = document.getElementById('login-password').value;
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      const data = await res.json();
      if (!res.ok) return showError(data.error || 'Erro ao entrar');
      saveAuth(data);
    } catch {
      showError('Erro de conexão. Tente novamente.');
    }
  });

  registerForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    errorMsg.classList.remove('show');
    const name = document.getElementById('reg-name').value.trim();
    const username = document.getElementById('reg-username').value.trim();
    const password = document.getElementById('reg-password').value;
    try {
      const res = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, username, password }),
      });
      const data = await res.json();
      if (!res.ok) return showError(data.error || 'Erro ao cadastrar');
      saveAuth(data);
    } catch {
      showError('Erro de conexão. Tente novamente.');
    }
  });
})();
