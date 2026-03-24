const db = require('../config/database')

exports.getAllUsers = async () => {
  const [rows] = await db.execute(`
    SELECT u.id, u.username, u.email, u.full_name, r.role_name
    FROM users u
    LEFT JOIN roles r ON u.role_id = r.id
  `)
  return rows
}

exports.createUser = async (data) => {
  const { username, email, password_hash, role_id } = data
  await db.execute(
    `INSERT INTO users (username, email, password_hash, role_id)
     VALUES (?, ?, ?, ?)`,
    [username, email, password_hash, role_id]
  )
}

exports.deleteUser = async (id) => {
  await db.execute(`DELETE FROM users WHERE id = ?`, [id])
}