import { pool } from '../config/database.js'

// GET USERS
export const getUsers = async (req, res) => {
  try {
    const [rows] = await pool.execute(`
      SELECT u.id, u.username, u.email, u.full_name, r.role_name
      FROM users u
      LEFT JOIN roles r ON u.role_id = r.id
    `)
    res.json(rows)
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
}

// CREATE USER
export const createUser = async (req, res) => {
  try {
    const { username, email, password_hash, role_id } = req.body

    await pool.execute(
      `INSERT INTO users (username, email, password_hash, role_id)
       VALUES (?, ?, ?, ?)`,
      [username, email, password_hash, role_id]
    )

    res.json({ message: 'User created' })
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
}

// DELETE USER
export const deleteUser = async (req, res) => {
  try {
    await pool.execute(`DELETE FROM users WHERE id = ?`, [req.params.id])
    res.json({ message: 'User deleted' })
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
}