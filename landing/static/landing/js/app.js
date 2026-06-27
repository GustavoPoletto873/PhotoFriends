(function () {
  'use strict';

  // ── CSRF ──────────────────────────────────────────────────────────────────
  function csrf() {
    return (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || '';
  }

  // ── TOAST ─────────────────────────────────────────────────────────────────
  function toast(msg, type) {
    const el = document.createElement('div');
    el.className = 'toast' + (type === 'error' ? ' toast-error' : ' toast-ok');
    el.textContent = msg;
    const c = document.getElementById('toasts');
    if (c) { c.appendChild(el); setTimeout(() => el.remove(), 3500); }
  }

  // ── MODALS ────────────────────────────────────────────────────────────────
  function openModal(m) { m && m.classList.add('open'); }
  function closeModal(m) { m && m.classList.remove('open'); }
  document.querySelectorAll('.modal-overlay').forEach(m => {
    m.addEventListener('click', e => { if (e.target === m) closeModal(m); });
  });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') document.querySelectorAll('.modal-overlay.open').forEach(closeModal);
  });

  // ── INVITE ────────────────────────────────────────────────────────────────
  const inviteModal = document.getElementById('invite-modal');
  const inviteBtn = document.getElementById('invite-btn');
  const cancelInvite = document.getElementById('cancel-invite-btn');
  const confirmInvite = document.getElementById('confirm-invite-btn');
  const inviteInput = document.getElementById('invite-username');
  const inviteError = document.getElementById('invite-error');

  inviteBtn && inviteBtn.addEventListener('click', () => {
    openModal(inviteModal);
    inviteInput && inviteInput.focus();
  });
  cancelInvite && cancelInvite.addEventListener('click', () => closeModal(inviteModal));

  confirmInvite && confirmInvite.addEventListener('click', async () => {
    const username = inviteInput.value.trim();
    if (!username) return;
    if (inviteError) inviteError.style.display = 'none';

    const body = new URLSearchParams({ username });
    try {
      const res = await fetch(window.INVITE_URL || '', {
        method: 'POST',
        headers: { 'X-CSRFToken': csrf(), 'Content-Type': 'application/x-www-form-urlencoded' },
        body,
      });
      const data = await res.json();
      if (!res.ok) {
        if (inviteError) { inviteError.textContent = data.error; inviteError.style.display = 'block'; }
      } else {
        toast(`${data.name} adicionado ao álbum! 🎉`);
        closeModal(inviteModal);
        inviteInput.value = '';
        location.reload();
      }
    } catch { toast('Erro ao convidar.', 'error'); }
  });

  // ── DELETE ALBUM ──────────────────────────────────────────────────────────
  const delAlbumBtn = document.getElementById('delete-album-btn');
  delAlbumBtn && delAlbumBtn.addEventListener('click', () => {
    if (confirm('Deletar este álbum? Todas as fotos serão apagadas.')) {
      window.DELETE_ALBUM_FORM && window.DELETE_ALBUM_FORM.submit();
    }
  });

  // ── DELETE MEDIA ──────────────────────────────────────────────────────────
  document.querySelectorAll('.photo-item-delete').forEach(btn => {
    btn.addEventListener('click', async e => {
      e.stopPropagation();
      if (!confirm('Deletar esta mídia?')) return;
      const mediaId = btn.dataset.mediaId;
      const url = `/media/${mediaId}/delete/`;
      try {
        const res = await fetch(url, {
          method: 'POST',
          headers: { 'X-CSRFToken': csrf() },
        });
        if (res.ok) {
          const item = btn.closest('.photo-item');
          item && item.remove();
          toast('Mídia deletada');
        } else {
          toast('Erro ao deletar.', 'error');
        }
      } catch { toast('Erro ao deletar.', 'error'); }
    });
  });

  // ── LIGHTBOX ──────────────────────────────────────────────────────────────
  const lightbox = document.getElementById('lightbox');
  if (lightbox) {
    const lbImg = document.getElementById('lb-img');
    const lbVideo = document.getElementById('lb-video');
    const lbInfo = document.getElementById('lb-info');
    const lbDownload = document.getElementById('lb-download');
    let allItems = [];
    let lbIdx = 0;

    function buildItems() {
      allItems = Array.from(document.querySelectorAll('.photo-item'));
    }

    function showLb(idx) {
      lbIdx = (idx + allItems.length) % allItems.length;
      const el = allItems[lbIdx];
      if (!el) return;
      const url = el.dataset.url;
      const type = el.dataset.type;
      const uploader = el.dataset.uploader || '';
      const date = el.dataset.date || '';

      if (type === 'video') {
        lbImg.style.display = 'none';
        lbVideo.style.display = '';
        lbVideo.src = url;
      } else {
        lbVideo.style.display = 'none';
        lbVideo.src = '';
        lbImg.style.display = '';
        lbImg.src = url;
      }
      lbInfo.textContent = `${lbIdx + 1} / ${allItems.length}  ·  ${uploader}  ·  ${date}`;
      if (lbDownload) lbDownload.href = `/media/${el.dataset.id}/download/`;
      lightbox.classList.add('open');

      // update global currentMediaId for fav/comments
      window.currentMediaId = el.dataset.id;
      const lbFavBtn = document.getElementById('lb-fav');
      if (lbFavBtn) {
        const gridFav = el.querySelector('.photo-item-fav');
        const isFav = gridFav && gridFav.classList.contains('fav-active');
        lbFavBtn.textContent = isFav ? '★' : '☆';
        lbFavBtn.classList.toggle('active', isFav);
      }
      if (typeof loadComments === 'function') loadComments(window.currentMediaId);
    }

    function closeLb() {
      lightbox.classList.remove('open');
      lbVideo.pause && lbVideo.pause();
      lbVideo.src = '';
    }

    document.getElementById('lb-close').addEventListener('click', closeLb);
    lightbox.addEventListener('click', e => { if (e.target === lightbox) closeLb(); });
    document.getElementById('lb-prev').addEventListener('click', () => showLb(lbIdx - 1));
    document.getElementById('lb-next').addEventListener('click', () => showLb(lbIdx + 1));
    document.addEventListener('keydown', e => {
      if (!lightbox.classList.contains('open')) return;
      if (e.key === 'Escape') closeLb();
      if (e.key === 'ArrowLeft') showLb(lbIdx - 1);
      if (e.key === 'ArrowRight') showLb(lbIdx + 1);
    });

    function showLbWithId(el) {
      buildItems();
      const idx = allItems.indexOf(el);
      showLb(idx);
      window.currentMediaId = el.dataset.id;
      // sync fav button state
      const lbFavBtn = document.getElementById('lb-fav');
      if (lbFavBtn) {
        const gridFav = el.querySelector('.photo-item-fav');
        const isFav = gridFav && gridFav.classList.contains('fav-active');
        lbFavBtn.textContent = isFav ? '★' : '☆';
        lbFavBtn.classList.toggle('active', isFav);
      }
      // load comments
      if (typeof loadComments === 'function') loadComments(window.currentMediaId);
    }

    document.querySelectorAll('.photo-item').forEach((el, i) => {
      el.addEventListener('click', e => {
        if (e.target.classList.contains('photo-item-delete')) return;
        if (e.target.classList.contains('photo-item-fav')) return;
        showLbWithId(el);
      });
    });
  }

  // ── UPLOAD ────────────────────────────────────────────────────────────────
  const uploadZone = document.getElementById('upload-zone');
  const uploadInput = document.getElementById('upload-input');
  const progressEl = document.getElementById('upload-progress');
  const progressBar = document.getElementById('upload-progress-bar');

  if (uploadZone && uploadInput) {
    uploadZone.addEventListener('dragover', e => {
      e.preventDefault();
      uploadZone.classList.add('drag-over');
    });
    uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('drag-over'));
    uploadZone.addEventListener('drop', e => {
      e.preventDefault();
      uploadZone.classList.remove('drag-over');
      uploadFiles(e.dataTransfer.files);
    });
    uploadInput.addEventListener('change', () => uploadFiles(uploadInput.files));

    async function uploadFiles(files) {
      if (!files || !files.length) return;
      const url = uploadInput.dataset.uploadUrl;
      if (!url) return;

      progressEl.style.display = 'block';
      progressBar.style.width = '15%';

      const formData = new FormData();
      Array.from(files).forEach(f => formData.append('files', f));

      try {
        progressBar.style.width = '50%';
        const res = await fetch(url, {
          method: 'POST',
          headers: { 'X-CSRFToken': csrf() },
          body: formData,
        });
        progressBar.style.width = '90%';
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Erro no upload');
        progressBar.style.width = '100%';
        const n = data.uploaded.length;
        toast(`${n} ${n === 1 ? 'arquivo enviado' : 'arquivos enviados'}! 📸`);
        uploadInput.value = '';
        setTimeout(() => location.reload(), 700);
      } catch (err) {
        toast(err.message, 'error');
      } finally {
        setTimeout(() => {
          progressEl.style.display = 'none';
          progressBar.style.width = '0%';
        }, 900);
      }
    }
  }


})();
