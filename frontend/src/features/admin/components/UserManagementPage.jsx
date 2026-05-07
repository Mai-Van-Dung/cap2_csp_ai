import { useEffect, useMemo, useState } from 'react'
import { PencilLine, Search, ShieldCheck, Trash2, UserPlus, X } from 'lucide-react'
import { createUser, deleteUser, getAllUsers, updateUser } from '../api/management_user'

const ROLE_STYLES = {
  admin: 'text-rose-200 border-rose-400/25 bg-rose-500/10',
  moderator: 'text-amber-200 border-amber-400/25 bg-amber-500/10',
  user: 'text-sky-200 border-sky-400/25 bg-sky-500/10',
}

const emptyForm = {
  username: '',
  full_name: '',
  email: '',
  role_id: '',
  telegramid: '',
  password: '',
}

export default function UserManagementPage() {
  const [users, setUsers] = useState([])
  const [search, setSearch] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [editingUser, setEditingUser] = useState(null)
  const [form, setForm] = useState(emptyForm)

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

  const filtered = useMemo(() => {
    const q = search.toLowerCase()
    return users.filter((user) => {
      return (
        user.username?.toLowerCase().includes(q) ||
        user.email?.toLowerCase().includes(q) ||
        user.full_name?.toLowerCase().includes(q) ||
        (user.telegramid || '').toLowerCase().includes(q)
      )
    })
  }, [search, users])

  const openAdd = () => {
    setEditingUser(null)
    setForm(emptyForm)
    setModalOpen(true)
  }

  const openEdit = (user) => {
    setEditingUser(user.id)
    setForm({
      username: user.username || '',
      full_name: user.full_name || '',
      email: user.email || '',
      role_id: user.role_id ?? '',
      telegramid: user.telegramid || '',
      password: '',
    })
    setModalOpen(true)
  }

  const closeModal = () => setModalOpen(false)

  const handleFormChange = (key, value) => setForm((prev) => ({ ...prev, [key]: value }))

  const handleDelete = async (id) => {
    if (!confirm('Xóa người dùng này?')) return

    try {
      await deleteUser(id)
      setUsers((prev) => prev.filter((user) => user.id !== id))
    } catch (err) {
      console.error('Lỗi xóa:', err)
    }
  }

  const handleSubmitForm = async (event) => {
    event.preventDefault()

    try {
      if (editingUser) {
        await updateUser(editingUser, {
          username: form.username,
          full_name: form.full_name,
          email: form.email,
          role_id: form.role_id ? Number(form.role_id) : null,
          telegramid: form.telegramid,
        })
      } else {
        await createUser({
          username: form.username,
          full_name: form.full_name,
          email: form.email,
          role_id: form.role_id ? Number(form.role_id) : null,
          telegramid: form.telegramid,
          password_hash: form.password,
        })
      }

      await fetchUsers()
      closeModal()
    } catch (err) {
      console.error('Lỗi lưu user:', err)
      alert('Lỗi khi lưu user')
    }
  }

  return (
    <>
      <section className="space-y-5">
        <div className="panel overflow-hidden p-5 md:p-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-2xl">
              <p className="text-[11px] font-semibold uppercase tracking-[0.3em] text-sky-300">Admin management</p>
              <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-50">User Management</h2>
              <p className="mt-2 text-sm leading-6 text-slate-300">Quản lý tài khoản, vai trò và thông tin người dùng trong giao diện gọn, rõ và đồng nhất hơn.</p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <button
                onClick={openAdd}
                className="inline-flex h-11 items-center gap-2 rounded-2xl bg-[linear-gradient(135deg,#ff8c2c_0%,#ff6f26_100%)] px-4 text-sm font-semibold text-white shadow-[0_14px_30px_rgba(255,116,44,0.22)] transition hover:translate-y-[-1px]"
              >
                <UserPlus size={16} />
                Add User
              </button>

              <div className="relative">
                <Search size={14} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
                <input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Tìm kiếm..."
                  className="h-11 w-64 rounded-2xl border border-white/10 bg-white/5 pl-9 pr-3 text-sm text-slate-100 placeholder:text-slate-500 outline-none transition focus:border-orange-400/60 focus:bg-white/10 focus:ring-4 focus:ring-orange-500/10"
                />
              </div>
            </div>
          </div>

          <div className="mt-5 grid gap-3 sm:grid-cols-3">
            <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
              <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500">Total users</p>
              <p className="mt-2 text-2xl font-semibold text-slate-50">{users.length}</p>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
              <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500">Filtered</p>
              <p className="mt-2 text-2xl font-semibold text-slate-50">{filtered.length}</p>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
              <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500">Admin tools</p>
              <p className="mt-2 inline-flex items-center gap-2 text-sm text-slate-300">
                <ShieldCheck size={16} className="text-sky-300" />
                Create, edit, delete users
              </p>
            </div>
          </div>
        </div>

        <div className="panel overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-full border-collapse text-left">
              <thead className="border-b border-white/10 bg-white/5">
                <tr>
                  {['#', 'Người dùng', 'Email', 'Telegram ID', 'Vai trò', ''].map((header) => (
                    <th key={header} className="whitespace-nowrap px-5 py-4 text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">
                      {header}
                    </th>
                  ))}
                </tr>
              </thead>

              <tbody>
                {filtered.map((user) => {
                  const roleClass = ROLE_STYLES[user.role_name?.toLowerCase()] || 'text-slate-300 border-white/10 bg-white/5'

                  return (
                    <tr key={user.id} className="border-b border-white/5 transition hover:bg-white/[0.03]">
                      <td className="whitespace-nowrap px-5 py-4 font-mono text-xs text-slate-500">{user.id}</td>
                      <td className="px-5 py-4">
                        <div className="font-medium text-slate-50">{user.full_name || user.username}</div>
                        <div className="mt-1 text-xs text-slate-500">@{user.username}</div>
                      </td>
                      <td className="px-5 py-4 text-sm text-slate-300">{user.email}</td>
                      <td className="px-5 py-4 text-sm text-slate-300">{user.telegramid || '-'}</td>
                      <td className="px-5 py-4">
                        <span className={`inline-flex rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] ${roleClass}`}>
                          {user.role_name || 'user'}
                        </span>
                      </td>
                      <td className="px-5 py-4 text-right">
                        <button
                          onClick={() => openEdit(user)}
                          className="inline-flex items-center gap-1 rounded-full border border-sky-400/20 bg-sky-500/10 px-3 py-2 text-xs font-semibold text-sky-200 transition hover:bg-sky-500/15"
                        >
                          <PencilLine size={14} />
                          Edit
                        </button>
                        <button
                          className="ml-2 inline-flex items-center justify-center rounded-full border border-white/10 bg-white/5 p-2 text-slate-400 transition hover:border-rose-400/25 hover:bg-rose-500/10 hover:text-rose-300"
                          onClick={() => handleDelete(user.id)}
                          aria-label={`Delete ${user.username}`}
                        >
                          <Trash2 size={15} />
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {filtered.length === 0 && (
            <div className="px-6 py-14 text-center text-sm text-slate-400">Không có kết quả</div>
          )}
        </div>
      </section>

      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/65 px-4 py-6 backdrop-blur-sm">
          <form onSubmit={handleSubmitForm} className="w-full max-w-2xl rounded-[28px] border border-white/10 bg-[#0F172A] p-5 shadow-[0_30px_100px_rgba(0,0,0,0.45)] md:p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-sky-300">Account editor</p>
                <h3 className="mt-2 text-2xl font-semibold text-slate-50">{editingUser ? 'Edit User' : 'Add User'}</h3>
              </div>

              <button
                type="button"
                onClick={closeModal}
                className="rounded-full border border-white/10 bg-white/5 p-2 text-slate-300 transition hover:bg-white/10 hover:text-white"
                aria-label="Close modal"
              >
                <X size={18} />
              </button>
            </div>

            <div className="mt-5 grid gap-3 sm:grid-cols-2">
              <input required placeholder="Username" value={form.username} onChange={(event) => handleFormChange('username', event.target.value)} className="input-dark" />
              <input placeholder="Full name" value={form.full_name} onChange={(event) => handleFormChange('full_name', event.target.value)} className="input-dark" />
              <input required placeholder="Email" value={form.email} onChange={(event) => handleFormChange('email', event.target.value)} className="input-dark" />
              <input placeholder="Role ID" value={form.role_id} onChange={(event) => handleFormChange('role_id', event.target.value)} className="input-dark" />
              <input placeholder="Telegram ID" value={form.telegramid} onChange={(event) => handleFormChange('telegramid', event.target.value)} className="input-dark" />
              <input placeholder="Password" value={form.password} onChange={(event) => handleFormChange('password', event.target.value)} type="password" className="input-dark" />
            </div>

            <div className="mt-5 flex justify-end gap-3">
              <button type="button" onClick={closeModal} className="h-11 rounded-2xl border border-white/10 bg-white/5 px-4 text-sm font-semibold text-slate-200 transition hover:bg-white/10">
                Cancel
              </button>
              <button type="submit" className="h-11 rounded-2xl bg-[linear-gradient(135deg,#ff8c2c_0%,#ff6f26_100%)] px-4 text-sm font-semibold text-white shadow-[0_14px_30px_rgba(255,116,44,0.22)] transition hover:translate-y-[-1px]">
                {editingUser ? 'Save' : 'Create'}
              </button>
            </div>
          </form>
        </div>
      )}
    </>
  )
}