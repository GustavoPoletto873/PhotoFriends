const express = require('express');
const multer = require('multer');
const { v2: cloudinary } = require('cloudinary');
const { CloudinaryStorage } = require('multer-storage-cloudinary');
const { getDb } = require('../database');
const { requireAuth } = require('../middleware/auth');

const router = express.Router();

cloudinary.config({
  cloud_name: process.env.CLOUDINARY_CLOUD_NAME,
  api_key: process.env.CLOUDINARY_API_KEY,
  api_secret: process.env.CLOUDINARY_API_SECRET,
});

const storage = new CloudinaryStorage({
  cloudinary,
  params: {
    folder: 'photo-friends',
    resource_type: 'auto',
    allowed_formats: ['jpg', 'jpeg', 'png', 'gif', 'webp', 'mp4', 'mov', 'avi'],
  },
});

const upload = multer({
  storage,
  limits: { fileSize: 100 * 1024 * 1024 },
});

router.use(requireAuth);

router.post('/upload', upload.array('files', 20), async (req, res) => {
  const { albumId } = req.body;
  if (!albumId) return res.status(400).json({ error: 'albumId é obrigatório' });

  const db = getDb();
  const access = db.prepare(`
    SELECT 1 FROM albums a
    LEFT JOIN album_members am ON a.id = am.album_id
    WHERE a.id = ? AND (a.created_by = ? OR am.user_id = ?)
  `).get(albumId, req.user.id, req.user.id);

  if (!access) return res.status(403).json({ error: 'Sem acesso a este álbum' });
  if (!req.files || !req.files.length) return res.status(400).json({ error: 'Nenhum arquivo recebido' });

  const stmt = db.prepare(`
    INSERT INTO media (album_id, uploaded_by, cloudinary_url, cloudinary_id, type, filename)
    VALUES (?, ?, ?, ?, ?, ?)
  `);

  const inserted = [];
  for (const file of req.files) {
    const type = file.mimetype.startsWith('video/') ? 'video' : 'photo';
    const result = stmt.run(albumId, req.user.id, file.path, file.filename, type, file.originalname);
    inserted.push({
      id: result.lastInsertRowid,
      cloudinary_url: file.path,
      cloudinary_id: file.filename,
      type,
      filename: file.originalname,
    });
  }

  // Set cover if not set
  const album = db.prepare('SELECT cover_url FROM albums WHERE id = ?').get(albumId);
  const firstPhoto = inserted.find(i => i.type === 'photo');
  if (!album.cover_url && firstPhoto) {
    db.prepare('UPDATE albums SET cover_url = ? WHERE id = ?').run(firstPhoto.cloudinary_url, albumId);
  }

  res.status(201).json({ uploaded: inserted });
});

router.delete('/:id', (req, res) => {
  const db = getDb();
  const media = db.prepare('SELECT * FROM media WHERE id = ?').get(req.params.id);
  if (!media) return res.status(404).json({ error: 'Mídia não encontrada' });
  if (media.uploaded_by !== req.user.id) return res.status(403).json({ error: 'Apenas quem enviou pode deletar' });

  cloudinary.uploader
    .destroy(media.cloudinary_id, { resource_type: media.type === 'video' ? 'video' : 'image' })
    .catch(err => console.error('Cloudinary delete error:', err));

  db.prepare('DELETE FROM media WHERE id = ?').run(req.params.id);
  res.json({ ok: true });
});

module.exports = router;
