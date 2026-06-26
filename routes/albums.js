const express = require('express');
const { getDb } = require('../database');
const { requireAuth } = require('../middleware/auth');

const router = express.Router();
router.use(requireAuth);

router.get('/', (req, res) => {
  const db = getDb();
  const albums = db.prepare(`
    SELECT DISTINCT a.*, u.name AS creator_name,
      (SELECT COUNT(*) FROM media WHERE album_id = a.id) AS media_count,
      (SELECT cloudinary_url FROM media WHERE album_id = a.id AND type = 'photo' ORDER BY uploaded_at DESC LIMIT 1) AS latest_media_url
    FROM albums a
    LEFT JOIN users u ON a.created_by = u.id
    LEFT JOIN album_members am ON a.id = am.album_id
    WHERE a.created_by = ? OR am.user_id = ?
    ORDER BY a.created_at DESC
  `).all(req.user.id, req.user.id);
  res.json(albums);
});

router.post('/', (req, res) => {
  const { name, description } = req.body;
  if (!name) return res.status(400).json({ error: 'Nome do álbum é obrigatório' });

  const db = getDb();
  const result = db.prepare('INSERT INTO albums (name, description, created_by) VALUES (?, ?, ?)').run(name, description || null, req.user.id);
  db.prepare('INSERT OR IGNORE INTO album_members (album_id, user_id) VALUES (?, ?)').run(result.lastInsertRowid, req.user.id);

  const album = db.prepare(`
    SELECT a.*, u.name AS creator_name
    FROM albums a LEFT JOIN users u ON a.created_by = u.id
    WHERE a.id = ?
  `).get(result.lastInsertRowid);
  res.status(201).json(album);
});

router.get('/:id', (req, res) => {
  const db = getDb();
  const albumId = parseInt(req.params.id);

  const access = db.prepare(`
    SELECT 1 FROM albums a
    LEFT JOIN album_members am ON a.id = am.album_id
    WHERE a.id = ? AND (a.created_by = ? OR am.user_id = ?)
  `).get(albumId, req.user.id, req.user.id);

  if (!access) return res.status(403).json({ error: 'Sem acesso a este álbum' });

  const album = db.prepare(`
    SELECT a.*, u.name AS creator_name,
      (SELECT COUNT(*) FROM media WHERE album_id = a.id) AS media_count
    FROM albums a LEFT JOIN users u ON a.created_by = u.id
    WHERE a.id = ?
  `).get(albumId);

  const media = db.prepare(`
    SELECT m.*, u.name AS uploader_name
    FROM media m LEFT JOIN users u ON m.uploaded_by = u.id
    WHERE m.album_id = ?
    ORDER BY COALESCE(m.taken_at, m.uploaded_at) DESC
  `).all(albumId);

  const members = db.prepare(`
    SELECT u.id, u.name, u.username
    FROM album_members am LEFT JOIN users u ON am.user_id = u.id
    WHERE am.album_id = ?
  `).all(albumId);

  res.json({ ...album, media, members });
});

router.delete('/:id', (req, res) => {
  const db = getDb();
  const album = db.prepare('SELECT * FROM albums WHERE id = ?').get(req.params.id);
  if (!album) return res.status(404).json({ error: 'Álbum não encontrado' });
  if (album.created_by !== req.user.id) return res.status(403).json({ error: 'Apenas o criador pode deletar o álbum' });

  db.prepare('DELETE FROM albums WHERE id = ?').run(req.params.id);
  res.json({ ok: true });
});

router.post('/:id/invite', (req, res) => {
  const db = getDb();
  const album = db.prepare('SELECT * FROM albums WHERE id = ?').get(req.params.id);
  if (!album) return res.status(404).json({ error: 'Álbum não encontrado' });
  if (album.created_by !== req.user.id) return res.status(403).json({ error: 'Apenas o criador pode convidar' });

  const { username } = req.body;
  const user = db.prepare('SELECT id, name, username FROM users WHERE username = ?').get(username);
  if (!user) return res.status(404).json({ error: 'Usuário não encontrado' });

  db.prepare('INSERT OR IGNORE INTO album_members (album_id, user_id) VALUES (?, ?)').run(album.id, user.id);
  res.json({ ok: true, user });
});

module.exports = router;
