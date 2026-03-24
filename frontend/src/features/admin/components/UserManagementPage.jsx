import { useEffect, useState } from 'react'
import { Trash2, Search } from 'lucide-react'
import { getAllUsers, deleteUser } from '../api/management_user'

const ROLE_COLORS = {
  admin: '#ff4d4d',
  moderator: '#f5a623',
  user: '#4a90d9',
}

export default function UserManagementPage() {
  const [users, setUsers] = useState([])
  const [search, setSearch] = useState('')

  const fetchUsers = async () => {
    try {
      const data = await getAllUsers()
      setUsers(data)
    } catch (err) {
      console.error('Lỗi load user:', err)
    }
  }

  useEffect(() => { fetchUsers() }, [])

  const handleDelete = async (id) => {
    if (!confirm('Xóa người dùng này?')) return
    try {
      await deleteUser(id)
      setUsers(prev => prev.filter(u => u.id !== id))
    } catch (err) {
      console.error('Lỗi xóa:', err)
    }
  }

  const filtered = users.filter(u => {
    const q = search.toLowerCase()
    return u.username?.toLowerCase().includes(q) ||
      u.email?.toLowerCase().includes(q) ||
      u.full_name?.toLowerCase().includes(q)
  })

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&family=DM+Mono:wght@500&display=swap');
        * { box-sizing: border-box; }
        .um-row:hover { background: #fafafa; }
        .um-row:hover .del-btn { opacity: 1; }
        .del-btn { opacity: 0; transition: opacity .15s; }
        .del-btn:hover { color: #ff4d4d !important; }
        input:focus { outline: none; border-color: #111 !important; }
      `}</style>

      <div style={{ fontFamily: "'DM Sans', sans-serif", padding: '40px 48px', background: '#fff', minHeight: '100vh' }}>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 32 }}>
          <div>
            <h1 style={{ margin: 0, fontSize: '1.4rem', fontWeight: 600, color: '#111', letterSpacing: '-0.01em' }}>
              User Management
            </h1>
            <p style={{ margin: '4px 0 0', color: '#aaa', fontSize: '0.82rem' }}>{users.length} người dùng</p>
          </div>

          <div style={{ position: 'relative' }}>
            <Search size={14} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: '#bbb' }} />
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Tìm kiếm..."
              style={{
                padding: '8px 14px 8px 34px', border: '1.5px solid #ebebeb',
                borderRadius: 8, fontSize: '0.82rem', color: '#111',
                fontFamily: "'DM Sans', sans-serif", width: 220,
                transition: 'border-color .15s',
              }}
            />
          </div>
        </div>

        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '2px solid #e8e8e8' }}>
              {['#', 'Người dùng', 'Email', 'Vai trò', ''].map(h => (
                <th key={h} style={{
                  padding: '0 16px 12px', textAlign: 'left',
                  fontSize: '0.7rem', fontWeight: 700,
                  letterSpacing: '0.08em', textTransform: 'uppercase', color: '#888',
                }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map(user => {
              const roleColor = ROLE_COLORS[user.role_name?.toLowerCase()] || '#555'
              return (
                <tr key={user.id} className="um-row" style={{ borderBottom: '1px solid #efefef', transition: 'background .12s' }}>
                  <td style={{ padding: '15px 16px', fontFamily: "'DM Mono', monospace", fontSize: '0.75rem', color: '#999' }}>
                    {user.id}
                  </td>
                  <td style={{ padding: '15px 16px' }}>
                    <div style={{ fontWeight: 600, color: '#111', fontSize: '0.9rem' }}>{user.full_name || user.username}</div>
                    <div style={{ color: '#888', fontSize: '0.78rem', marginTop: 2 }}>@{user.username}</div>
                  </td>
                  <td style={{ padding: '15px 16px', color: '#444', fontSize: '0.875rem' }}>{user.email}</td>
                  <td style={{ padding: '15px 16px' }}>
                    <span style={{
                      color: roleColor, fontSize: '0.72rem', fontWeight: 700,
                      letterSpacing: '0.06em', textTransform: 'uppercase',
                    }}>
                      {user.role_name}
                    </span>
                  </td>
                  <td style={{ padding: '15px 16px', textAlign: 'right' }}>
                    <button
                      className="del-btn"
                      onClick={() => handleDelete(user.id)}
                      style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#aaa', display: 'inline-flex', padding: 4 }}
                    >
                      <Trash2 size={15} />
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>

        {filtered.length === 0 && (
          <div style={{ textAlign: 'center', padding: '60px 0', color: '#999', fontSize: '0.875rem' }}>
            Không có kết quả
          </div>
        )}
      </div>
    </>
  )
}