require('dotenv').config();
const express = require('express');
const { Pool } = require('pg');
const cors = require('cors');

const app = express();
app.use(cors());
app.use(express.json());

// LA MODIFICA È QUI SOTTO: Aggiunto blocco ssl
const pool = new Pool({
  user: process.env.DB_USER || 'dbadmin',
  host: process.env.DB_HOST || 'localhost',
  database: process.env.DB_NAME || 'playersdb',
  password: process.env.DB_PASSWORD || 'password123',
  port: process.env.DB_PORT || 5432,
  ssl: {
    rejectUnauthorized: false
  }
});

const initDB = async () => {
  let retries = 5;
  while (retries) {
    try {
      await pool.query(`
        CREATE TABLE IF NOT EXISTS players (
          id SERIAL PRIMARY KEY,
          nome VARCHAR(100) NOT NULL,
          cognome VARCHAR(100) NOT NULL,
          ritirato BOOLEAN DEFAULT FALSE
        );
      `);
      console.log('✅ Database Cloud AWS connesso e tabella players pronta!');
      break;
    } catch (err) {
      console.error('❌ Errore connessione DB:', err.message);
      retries -= 1;
      await new Promise(res => setTimeout(res, 3000));
    }
  }
};
initDB();

app.post('/players', async (req, res) => {
  const { nome, cognome } = req.body;
  try {
    const result = await pool.query(
      'INSERT INTO players (nome, cognome) VALUES ($1, $2) RETURNING *',
      [nome, cognome]
    );
    res.status(201).json(result.rows[0]);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/players', async (req, res) => {
  try {
    const result = await pool.query('SELECT * FROM players ORDER BY cognome, nome');
    res.json(result.rows);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.put('/players/:id/drop', async (req, res) => {
  const { id } = req.params;
  try {
    const result = await pool.query(
      'UPDATE players SET ritirato = TRUE WHERE id = $1 RETURNING *',
      [id]
    );
    if (result.rows.length === 0) {
      return res.status(404).json({ error: "Giocatore non trovato" });
    }
    res.json(result.rows[0]);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

const PORT = 3001;
app.listen(PORT, () => {
  console.log(`Player Service in ascolto sulla porta ${PORT}`);
});
