(function () {
  'use strict';

  const token = localStorage.getItem('pf_token');
  const user = JSON.parse(localStorage.getItem('pf_user') || 'null');

  if (!token || !user) { window.location.href = '/'; return; }

  const params = new URLSearchParams(window.location.search);
  const albumId = params.get('id');
  if (!albumId) { window.location.href = '/home.html'; return; }

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

  function formatDateTime(str) {
    if (!str) return '';
    return new Date(str).toLocaleString('pt-BR', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
  }

  // ---- LIGHTBOX ----
  let mediaItems = [];
  let lbIndex = 0;

  const lightbox = document.getElementById('lightbox');
  const lbImg = document.getElementById('lightbox-img');
  const lbVideo = document.getElementById('lightbox-video');
  const lbInfo = document.getElementById('lightbox-info');

  function openLightbox(index) {
    lbIndex = index;
    const item = mediaItems[index];
    if (item.type === 'video') {
      lbImg.style.display = 'none';
      lbVideo.style.display = '';
      lbVideo.src = item.cloudinary_url;
    } else {
      lbVideo.style.display = 'none';
      lbVideo.src = '';
      lbImg.style.display = '';
      lbImg.src = item.cloudinary_url;
      lbImg.alt = item.filename || '';
    }
    lbInfo.textContent = `${index + 1} / ${mediaItems.length}  ·  ${item.uploader_name}  ·  ${formatDateTime(item.uploaded_at)}`;
    lightbox.classList.add('open');
  }

  function closeLightbox() {
    lightbox.classList.remove('open');
    lbVideo.pause && lbVideo.pause();
    lbVideo.src = '';
  }

  document.getElementById('lightbox-close').addEventListener('click', closeLightbox);
  lightbox.addEventListener('click', e => { if (e.target === lightbox) closeLightbox(); });

  document.getElementById('lightbox-prev').addEventListener('click', () => {
    openLightbox((lbIndex - 1 + mediaItems.length) % mediaItems.length);
  });
  document.getElementById('lightbox-next').addEventListener('click', () => {
    openLightbox((lbIndex + 1) % mediaItems.length);
  });

  document.addEventListener('keydown', e => {
    if (!lightbox.classList.contains('open')) return;
    if (e.key === 'Escape') closeLightbox();
    if (e.key === 'ArrowLeft') openLightbox((lbIndex - 1 + mediaItems.length) % mediaItems.length);
    if (e.key === 'ArrowRight') openLightbox((lbIndex + 1) % mediaItems.length);
  });

  // ---- RENDER MEDIA ----
  function renderMedia(media) {
    mediaItems = media;
    const grid = document.getElementById('media-grid');
    const label = document.getElementById('media-count-label');
    label.textContent = `${media.length} ${media.length === 1 ? 'item' : 'itens'}`;

    if (!media.length) {
      grid.innerHTML = '<p style="color:var(--text-muted);font-size:.875rem;padding:2rem 0">Nenhuma foto ainda. Seja o primeiro a enviar! 🎉</p>';
      return;
    }

    grid.innerHTML = media.map((m, i) => {
      const isOwner = m.uploaded_by === user.id;
      const mediaSrc = m.type === 'video'
        ? `<video src="${m.cloudinary_url}" preload="metadata" muted></video>`
        : `<img src="${m.cloudinary_url}" alt="${m.filename || ''}" loading="lazy">`;

      return `
        <div class="media-item" data-index="${i}">
          ${mediaSrc}
          ${m.type === 'video' ? '<div class="media-item__video-badge">▶ Vídeo</div>' : ''}
          <div class="media-item__overlay">
            <div class="media-item__meta">
              <span class="media-item__uploader">${m.uploader_name}</span>
              <button class="media-item__delete ${isOwner ? 'show' : ''}" data-id="${m.id}">✕</button>
            </div>
          </div>
        </div>`;
    }).join('');

    grid.querySelectorAll('.media-item').forEach(el => {
      el.addEventListener('click', e => {
        if (e.target.classList.contains('media-item__delete')) return;
        openLightbox(parseInt(el.dataset.index));
      });
    });

    grid.querySelectorAll('.media-item__delete').forEach(btn => {
      btn.addEventListener('click', async e => {
        e.stopPropagation();
        if (!confirm('Deletar esta mídia?')) return;
        try {
          await api('DELETE', `/media/${btn.dataset.id}`);
          toast('Mídia deletada');
          loadAlbum();
        } catch (err) {
          toast(err.message, 'error');
        }
      });
    });
  }

  // ---- LOAD ALBUM ----
  async function loadAlbum() {
    try {
      const data = await api('GET', `/albums/${albumId}`);
      document.title = `Photo Friends — ${data.name}`;
      document.getElementById('album-title').textContent = data.name;
      document.getElementById('album-description').textContent = data.description || '';

      const membersRow = document.getElementById('members-row');
      membersRow.innerHTML = data.members.map(m => `<span class="member-badge">👤 ${m.name}</span>`).join('');

      if (data.created_by === user.id) {
        document.getElementById('delete-album-btn').style.display = '';
      }

      renderMedia(data.media || []);
    } catch (err) {
      toast(err.message || 'Erro ao carregar álbum', 'error');
    }
  }

  // ---- DELETE ALBUM ----
  document.getElementById('delete-album-btn').addEventListener('click', async () => {
    if (!confirm('Deletar este álbum? Todas as fotos serão perdidas.')) return;
    try {
      await api('DELETE', `/albums/${albumId}`);
      toast('Álbum deletado');
      setTimeout(() => { window.location.href = '/home.html'; }, 1000);
    } catch (err) {
      toast(err.message, 'error');
    }
  });

  // ---- INVITE MODAL ----
  const inviteModal = document.getElementById('invite-modal');
  document.getElementById('invite-btn').addEventListener('click', () => inviteModal.classList.add('open'));
  document.getElementById('cancel-invite-btn').addEventListener('click', () => inviteModal.classList.remove('open'));
  inviteModal.addEventListener('click', e => { if (e.target === inviteModal) inviteModal.classList.remove('open'); });

  document.getElementById('invite-form').addEventListener('submit', async e => {
    e.preventDefault();
    const username = document.getElementById('invite-username').value.trim();
    try {
      const data = await api('POST', `/albums/${albumId}/invite`, { username });
      inviteModal.classList.remove('open');
      document.getElementById('invite-form').reset();
      toast(`${data.user.name} foi adicionado ao álbum! 🎉`);
      loadAlbum();
    } catch (err) {
      toast(err.message, 'error');
    }
  });

  // ---- UPLOAD ----
  const uploadZone = document.getElementById('upload-zone');
  const uploadInput = document.getElementById('upload-input');
  const progressEl = document.getElementById('upload-progress');
  const progressBar = document.getElementById('upload-progress-bar');

  uploadZone.addEventListener('dragover', e => { e.preventDefault(); uploadZone.classList.add('drag-over'); });
  uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('drag-over'));
  uploadZone.addEventListener('drop', e => {
    e.preventDefault();
    uploadZone.classList.remove('drag-over');
    uploadFiles(e.dataTransfer.files);
  });
  uploadInput.addEventListener('change', () => uploadFiles(uploadInput.files));

  async function uploadFiles(files) {
    if (!files || !files.length) return;
    progressEl.style.display = 'block';
    progressBar.style.width = '15%';

    const formData = new FormData();
    formData.append('albumId', albumId);
    Array.from(files).forEach(f => formData.append('files', f));

    try {
      progressBar.style.width = '50%';
      const res = await fetch('/api/media/upload', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData,
      });
      progressBar.style.width = '90%';
      if (res.status === 401) { localStorage.clear(); window.location.href = '/'; return; }
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Erro no upload');
      progressBar.style.width = '100%';
      const n = data.uploaded.length;
      toast(`${n} ${n === 1 ? 'arquivo enviado' : 'arquivos enviados'}! 📸`);
      uploadInput.value = '';
      loadAlbum();
    } catch (err) {
      toast(err.message, 'error');
    } finally {
      setTimeout(() => { progressEl.style.display = 'none'; progressBar.style.width = '0%'; }, 800);
    }
  }

  loadAlbum();
})();
