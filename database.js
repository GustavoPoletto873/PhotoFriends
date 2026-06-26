const Database = require('better-sqlite3');
const path = require('path');

const DB_PATH = process.env.DB_PATH || path.join(__dirname, 'photo_friends.db');
let db;

function getDb() {
  if (!db) {
    db = new Database(DB_PATH);
    db.pragma('journal_mode = WAL');
    db.pragma('foreign_keys = ON');
  }
  return db;
}

function initDb() {
  const db = getDb();
  db.exec(`
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      username TEXT UNIQUE NOT NULL,
      password TEXT NOT NULL,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS albums (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      description TEXT,
      cover_url TEXT,
      created_by INTEGER REFERENCES users(id),
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS album_members (
      album_id INTEGER REFERENCES albums(id) ON DELETE CASCADE,
      user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
      PRIMARY KEY (album_id, user_id)
    );

    CREATE TABLE IF NOT EXISTS media (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      album_id INTEGER REFERENCES albums(id) ON DELETE CASCADE,
      uploaded_by INTEGER REFERENCES users(id),
      cloudinary_url TEXT NOT NULL,
      cloudinary_id TEXT NOT NULL,
      type TEXT CHECK(type IN ('photo', 'video')),
      filename TEXT,
      taken_at DATETIME,
      uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
  `);
  console.log('Banco de dados inicializado.');
}

module.exports = { getDb, initDb };
