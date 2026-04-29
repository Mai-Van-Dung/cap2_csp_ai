import { useEffect, useState } from 'react'
import { Trash2, Search } from 'lucide-react'
import { getAllUsers, deleteUser, createUser, updateUser } from '../api/management_user'

const ROLE_COLORS = {
  admin: '#ff4d4d',
  moderator: '#f5a623',
  user: '#4a90d9',
}

export default function UserManagementPage() {
  const [users, setUsers] = useState([])
  const [search, setSearch] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [editingUser, setEditingUser] = useState(null)
  const [form, setForm] = useState({ username: '', full_name: '', email: '', role_id: '', telegramid: '', password: '' })

  const fetchUsers = async () => {
    try {
      const data = await getAllUsers()
      setUsers(data)
    } catch (err) {
      console.error('Lỗi load user:', err)
    }
  }

  useEffect(() => {
    fetchUsers()
  }, [])

  const handleDelete = async (id) => {
    if (!confirm('Xóa người dùng này?')) return
    try {
      await deleteUser(id)
      setUsers(prev => prev.filter(u => u.id !== id))
    } catch (err) {
      console.error('Lỗi xóa:', err)
    }
  }

  const openAdd = () => {
    setEditingUser(null)
    setForm({ username: '', full_name: '', email: '', role_id: '', telegramid: '', password: '' })
    setModalOpen(true)
  }

  const openEdit = (user) => {
    setEditingUser(user.id)
    setForm({ username: user.username || '', full_name: user.full_name || '', email: user.email || '', role_id: user.role_id ?? '', telegramid: user.telegramid || '', password: '' })
    setModalOpen(true)
  }

  const closeModal = () => setModalOpen(false)

  const handleFormChange = (k, v) => setForm(prev => ({ ...prev, [k]: v }))

  const handleSubmitForm = async (e) => {
    e.preventDefault()
    try {
      if (editingUser) {
        await updateUser(editingUser, { username: form.username, full_name: form.full_name, email: form.email, role_id: form.role_id ? Number(form.role_id) : null, telegramid: form.telegramid })
      } else {
        await createUser({ username: form.username, full_name: form.full_name, email: form.email, role_id: form.role_id ? Number(form.role_id) : null, telegramid: form.telegramid, password_hash: form.password })
      }
      await fetchUsers()
      closeModal()
    } catch (err) {
      console.error('Lỗi lưu user:', err)
      alert('Lỗi khi lưu user')
    }
  }

  const q = search.toLowerCase()
  const filtered = users.filter(u => {
    return u.username?.toLowerCase().includes(q) ||
      u.email?.toLowerCase().includes(q) ||
      u.full_name?.toLowerCase().includes(q) ||
      (u.telegramid || '').toLowerCase().includes(q)
  })

  return (
    <>
      <style>{`@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&family=DM+Mono:wght@500&display=swap'); * { box-sizing: border-box; } .um-row:hover { background: #fafafa; } .um-row:hover .del-btn { opacity: 1; } .del-btn { opacity: 0; transition: opacity .15s; } .del-btn:hover { color: #ff4d4d !important; } input:focus { outline: none; border-color: #111 !important; }`}</style>

      <div style={{ fontFamily: "'DM Sans', sans-serif", padding: '40px 48px', background: '#fff', minHeight: '100vh' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 32 }}>
          <div>
            <h1 style={{ margin: 0, fontSize: '1.4rem', fontWeight: 600, color: '#111', letterSpacing: '-0.01em' }}>User Management</h1>
            <p style={{ margin: '4px 0 0', color: '#aaa', fontSize: '0.82rem' }}>{users.length} người dùng</p>
          </div>

          <div style={{ position: 'relative', display: 'flex', gap: 12, alignItems: 'center' }}>
            <button onClick={openAdd} style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid #e8e8e8', background: '#fff', cursor: 'pointer' }}>Add User</button>
            <div style={{ position: 'relative' }}>
              <Search size={14} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: '#bbb' }} />
              <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Tìm kiếm..." style={{ padding: '8px 14px 8px 34px', border: '1.5px solid #ebebeb', borderRadius: 8, fontSize: '0.82rem', color: '#111', fontFamily: "'DM Sans', sans-serif", width: 220, transition: 'border-color .15s' }} />
            </div>
          </div>
        </div>

        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '2px solid #e8e8e8' }}>
              {['#', 'Người dùng', 'Email', 'Telegram ID', 'Vai trò', ''].map(h => (
                <th key={h} style={{ padding: '0 16px 12px', textAlign: 'left', fontSize: '0.7rem', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: '#888' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map(user => {
              const roleColor = ROLE_COLORS[user.role_name?.toLowerCase()] || '#555'
              return (
                <tr key={user.id} className="um-row" style={{ borderBottom: '1px solid #efefef', transition: 'background .12s' }}>
                  <td style={{ padding: '15px 16px', fontFamily: "'DM Mono', monospace", fontSize: '0.75rem', color: '#999' }}>{user.id}</td>
                  <td style={{ padding: '15px 16px' }}>
                    <div style={{ fontWeight: 600, color: '#111', fontSize: '0.9rem' }}>{user.full_name || user.username}</div>
                    <div style={{ color: '#888', fontSize: '0.78rem', marginTop: 2 }}>@{user.username}</div>
                  </td>
                  <td style={{ padding: '15px 16px', color: '#444', fontSize: '0.875rem' }}>{user.email}</td>
                  <td style={{ padding: '15px 16px', color: '#444', fontSize: '0.875rem' }}>{user.telegramid || '-'}</td>
                  <td style={{ padding: '15px 16px' }}><span style={{ color: roleColor, fontSize: '0.72rem', fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase' }}>{user.role_name}</span></td>
                  <td style={{ padding: '15px 16px', textAlign: 'right' }}>
                    <button onClick={() => openEdit(user)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#3b82f6', marginRight: 8 }}>Edit</button>
                    <button className="del-btn" onClick={() => handleDelete(user.id)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#aaa', display: 'inline-flex', padding: 4 }}><Trash2 size={15} /></button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>

        {modalOpen && (
          <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 60 }}>
            <form onSubmit={handleSubmitForm} style={{ background: '#fff', padding: 20, borderRadius: 8, width: 520, boxShadow: '0 8px 30px rgba(0,0,0,0.15)' }}>
              <h3 style={{ marginTop: 0 }}>{editingUser ? 'Edit User' : 'Add User'}</h3>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                <input required placeholder="Username" value={form.username} onChange={e => handleFormChange('username', e.target.value)} style={{ padding: 8, borderRadius: 6, border: '1px solid #e8e8e8' }} />
                <input placeholder="Full name" value={form.full_name} onChange={e => handleFormChange('full_name', e.target.value)} style={{ padding: 8, borderRadius: 6, border: '1px solid #e8e8e8' }} />
                <input required placeholder="Email" value={form.email} onChange={e => handleFormChange('email', e.target.value)} style={{ padding: 8, borderRadius: 6, border: '1px solid #e8e8e8' }} />
                <input placeholder="Role ID" value={form.role_id} onChange={e => handleFormChange('role_id', e.target.value)} style={{ padding: 8, borderRadius: 6, border: '1px solid #e8e8e8' }} />
                <input placeholder="Telegram ID" value={form.telegramid} onChange={e => handleFormChange('telegramid', e.target.value)} style={{ padding: 8, borderRadius: 6, border: '1px solid #e8e8e8' }} />
                <input placeholder="Password" value={form.password} onChange={e => handleFormChange('password', e.target.value)} type="password" style={{ padding: 8, borderRadius: 6, border: '1px solid #e8e8e8' }} />
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 14 }}>
                <button type="button" onClick={closeModal} style={{ padding: '8px 12px', borderRadius: 6, border: '1px solid #e8e8e8', background: '#fff' }}>Cancel</button>
                <button type="submit" style={{ padding: '8px 12px', borderRadius: 6, border: 'none', background: '#111', color: '#fff' }}>{editingUser ? 'Save' : 'Create'}</button>
              </div>
            </form>
          </div>
        )}

        {filtered.length === 0 && (
          <div style={{ textAlign: 'center', padding: '60px 0', color: '#999', fontSize: '0.875rem' }}>Không có kết quả</div>
        )}
      </div>
    </>
  )
}
