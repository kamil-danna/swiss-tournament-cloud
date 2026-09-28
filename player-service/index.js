require('dotenv').config();
const express = require('express');
const { Pool } = require('pg');
const cors = require('cors');

const app = express();
app.use(cors());
app.use(express.json());

// Database configuration using environment variables
const pool = new Pool({
  user: process.env.DB_USER || 'admin',
  host: process.env.DB_HOST || 'localhost',
  database: process.env.DB_NAME || 'playersdb',
  password: process.env.DB_PASSWORD || 'password123',
  port: process.env.DB_PORT || 5432,
  // Required for connecting to AWS RDS over SSL
  ssl: process.env.DB_HOST !== 'localhost' ? { rejectUnauthorized: false } : false
});

// Initialize the database table
const initDB = async () => {
  try {
    await pool.query(`
      CREATE TABLE IF NOT EXISTS players (
        id SERIAL PRIMARY KEY,
        nome VARCHAR(100) NOT NULL,
        cognome VARCHAR(100) NOT NULL,
        ritirato BOOLEAN DEFAULT FALSE
      );
    `);
    console.log(`Connected to database at ${process.env.DB_HOST || 'localhost'}. Table 'players' is ready.`);
  } catch (err) {
    console.error('Error creating table:', err);
  }
};
initDB();

// ---------------- API ENDPOINTS ---------------- //

// 1. Add a new player
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

// 2. Get all players
app.get('/players', async (req, res) => {
  try {
    const result = await pool.query('SELECT * FROM players ORDER BY cognome, nome');
    res.json(result.rows);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// 3. Drop a player
app.put('/players/:id/drop', async (req, res) => {
  const { id } = req.params;
  try {
    const result = await pool.query(
      'UPDATE players SET ritirato = TRUE WHERE id = $1 RETURNING *',
      [id]
    );
    if (result.rows.length === 0) {
      return res.status(404).json({ error: "Player not found" });
    }
    res.json(result.rows[0]);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

const PORT = process.env.PORT || 3001;
app.listen(PORT, () => {
  console.log(`Player Service listening on port ${PORT}`);
});