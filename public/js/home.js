(function () {
  'use strict';

  const token = localStorage.getItem('pf_token');
  const user = JSON.parse(localStorage.getItem('pf_user') || 'null');

  if (!token || !user) { window.location.href = '/'; return; }

  document.getElementById('nav-user-name').textContent = user.name;
  document.getElementById('logout-btn').addEventListener('click', () => {
    localStorage.clear();
    window.location.href = '/';
  });

  async function api(method, path, body) {
    const res = await fetch(`/api${path}`, {
      method,
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: body ? JSON.stringify(body) : undefined,
    });
    if (res.status === 401) { localStorage.clear(); window.location.href = '/'; return; }
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Erro');
    return data;
  }

  function toast(msg, type = 'success') {
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.textContent = msg;
    document.getElementById('toasts').appendChild(el);
    setTimeout(() => el.remove(), 3500);
  }

  const GRADIENTS = [
    'linear-gradient(135deg,#667eea,#764ba2)',
    'linear-gradient(135deg,#f093fb,#f5576c)',
    'linear-gradient(135deg,#4facfe,#00f2fe)',
    'linear-gradient(135deg,#43e97b,#38f9d7)',
    'linear-gradient(135deg,#fa709a,#fee140)',
    'linear-gradient(135deg,#a18cd1,#fbc2eb)',
    'linear-gradient(135deg,#fccb90,#d57eeb)',
    'linear-gradient(135deg,#e0c3fc,#8ec5fc)',
    'linear-gradient(135deg,#fd7043,#ff8f00)',
    'linear-gradient(135deg,#26c6da,#00838f)',
  ];

  function getGradient(id) { return GRADIENTS[id % GRADIENTS.length]; }

  function formatDate(str) {
    return new Date(str).toLocaleDateString('pt-BR', { day: '2-digit', month: 'short', year: 'numeric' });
  }

  function renderAlbums(albums) {
    const grid = document.getElementById('albums-grid');
    if (!albums.length) {
      grid.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">📷</div>
          <h3>Nenhum álbum ainda</h3>
          <p>Crie seu primeiro álbum e chame os amigos!</p>
        </div>`;
      return;
    }

    grid.innerHTML = albums.map(a => {
      const count = a.media_count || 0;
      const coverHtml = a.latest_media_url
        ? `<img src="${a.latest_media_url}" alt="${a.name}" loading="lazy">`
        : `<div class="album-card__cover-gradient" style="background:${getGradient(a.id)}"></div>`;

      return `
        <div class="album-card" data-id="${a.id}">
          <div class="album-card__cover">
            ${coverHtml}
            <span class="album-card__count-badge">${count} ${count === 1 ? 'item' : 'itens'}</span>
          </div>
          <div class="album-card__info">
            <div class="album-card__name">${a.name}</div>
            <div class="album-card__meta">por ${a.creator_name} · ${formatDate(a.created_at)}</div>
          </div>
        </div>`;
    }).join('');

    grid.querySelectorAll('.album-card').forEach(card => {
      card.addEventListener('click', () => {
        window.location.href = `/album.html?id=${card.dataset.id}`;
      });
    });
  }

  async function loadAlbums() {
    try {
      const albums = await api('GET', '/albums');
      renderAlbums(albums);
    } catch {
      document.getElementById('albums-grid').innerHTML =
        '<div class="empty-state"><p>Erro ao carregar álbuns.</p></div>';
    }
  }

  const modal = document.getElementById('new-album-modal');
  document.getElementById('new-album-btn').addEventListener('click', () => modal.classList.add('open'));
  document.getElementById('cancel-album-btn').addEventListener('click', () => modal.classList.remove('open'));
  modal.addEventListener('click', e => { if (e.target === modal) modal.classList.remove('open'); });

  document.getElementById('new-album-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const name = document.getElementById('album-name').value.trim();
    const description = document.getElementById('album-desc').value.trim();
    try {
      await api('POST', '/albums', { name, description });
      modal.classList.remove('open');
      document.getElementById('new-album-form').reset();
      toast('Álbum criado! 🎉');
      loadAlbums();
    } catch (err) {
      toast(err.message, 'error');
    }
  });

  loadAlbums();
})();
