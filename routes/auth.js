const express = require('express');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const { getDb } = require('../database');

const router = express.Router();

router.post('/register', async (req, res) => {
  const { name, username, password } = req.body;
  if (!name || !username || !password) {
    return res.status(400).json({ error: 'Preencha todos os campos' });
  }
  if (password.length < 6) {
    return res.status(400).json({ error: 'Senha deve ter ao menos 6 caracteres' });
  }

  const db = getDb();
  const existing = db.prepare('SELECT id FROM users WHERE username = ?').get(username);
  if (existing) {
    return res.status(409).json({ error: 'Username já em uso' });
  }

  const hash = await bcrypt.hash(password, 10);
  const result = db.prepare('INSERT INTO users (name, username, password) VALUES (?, ?, ?)').run(name, username, hash);

  const token = jwt.sign(
    { id: result.lastInsertRowid, username, name },
    process.env.JWT_SECRET,
    { expiresIn: '30d' }
  );
  res.status(201).json({ token, user: { id: result.lastInsertRowid, name, username } });
});

router.post('/login', async (req, res) => {
  const { username, password } = req.body;
  if (!username || !password) {
    return res.status(400).json({ error: 'Preencha todos os campos' });
  }

  const db = getDb();
  const user = db.prepare('SELECT * FROM users WHERE username = ?').get(username);
  if (!user) {
    return res.status(401).json({ error: 'Usuário ou senha incorretos' });
  }

  const valid = await bcrypt.compare(password, user.password);
  if (!valid) {
    return res.status(401).json({ error: 'Usuário ou senha incorretos' });
  }

  const token = jwt.sign(
    { id: user.id, username: user.username, name: user.name },
    process.env.JWT_SECRET,
    { expiresIn: '30d' }
  );
  res.json({ token, user: { id: user.id, name: user.name, username: user.username } });
});

module.exports = router;
