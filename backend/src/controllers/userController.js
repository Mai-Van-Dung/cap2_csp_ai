import { pool } from "../config/database.js";

// GET USERS
export const getUsers = async (req, res) => {
  try {
    const [rows] = await pool.execute(`
      SELECT u.id, u.username, u.email, u.full_name, u.telegram_chat_id AS telegramid, u.role_id, r.role_name
      FROM users u
      LEFT JOIN roles r ON u.role_id = r.id
    `);
    res.json(rows);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
};

// CREATE USER
export const createUser = async (req, res) => {
  try {
    const { username, email, password_hash, role_id, telegramid } = req.body;

    await pool.execute(
      `INSERT INTO users (username, email, password_hash, role_id, telegram_chat_id)
       VALUES (?, ?, ?, ?, ?)`,
      [username, email, password_hash, role_id, telegramid ?? null],
    );

    res.json({ message: "User created" });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
};

// DELETE USER
export const deleteUser = async (req, res) => {
  try {
    await pool.execute(`DELETE FROM users WHERE id = ?`, [req.params.id]);
    res.json({ message: "User deleted" });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
};

// UPDATE USER
export const updateUser = async (req, res) => {
  try {
    const userId = req.params.id;
    const { username, email, full_name, role_id, telegramid } = req.body;

    await pool.execute(
      `UPDATE users SET username = ?, email = ?, full_name = ?, role_id = ?, telegram_chat_id = ? WHERE id = ?`,
      [username, email, full_name, role_id ?? null, telegramid ?? null, userId],
    );

    res.json({ message: "User updated" });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
};
