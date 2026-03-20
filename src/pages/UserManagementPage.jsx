import {
  Ban,
  Check,
  Download,
  Filter,
  Monitor,
  Pencil,
  Plus,
  SlidersHorizontal,
  Trash2,
  UserCog,
} from 'lucide-react'

const users = [
  {
    id: 'USR-001',
    name: 'John Doe (Admin)',
    email: 'john.doe@email.com',
    role: 'Super Admin',
    zones: 'All Zones',
    zoneColor: 'bg-emerald-400',
    status: 'Active',
  },
  {
    id: 'USR-002',
    name: 'Jane Smith (Op)',
    email: 'jane.smith@email.com',
    role: 'Operator',
    zones: 'Pool Perimeter',
    zoneColor: 'bg-danger',
    status: 'Active',
  },
  {
    id: 'USR-003',
    name: 'John Doe (Admin)',
    email: 'john.doe@email.com',
    role: 'Super Admin',
    zones: 'All Zones',
    zoneColor: 'bg-emerald-400',
    status: 'Inactive',
  },
  {
    id: 'USR-004',
    name: 'Jane Smith (Op)',
    email: 'jane.smith@email.com',
    role: 'Operator',
    zones: 'Pool Perimeter',
    zoneColor: 'bg-danger',
    status: 'Active',
  },
  {
    id: 'USR-005',
    name: 'Jane Smith',
    email: 'jane.smith@email.com',
    role: 'Super Admin',
    zones: 'All Zones',
    zoneColor: 'bg-slate-500',
    status: 'Inactive',
  },
]

const accessSteps = [
  { label: 'Live Monitor', icon: Monitor, active: true },
  { label: 'Events History', icon: Filter, active: true },
  { label: 'Zone Config', icon: SlidersHorizontal, active: true },
  { label: 'AI Settings', icon: UserCog, active: true },
  { label: 'User Management', icon: UserCog, active: false },
]

const permissionItems = [
  'Read Live',
  'Draw Zone',
  'Set AI Thresholds',
  'Edit Users',
]

const activityLogs = [
  {
    timestamp: '2024-05-22 15:10',
    user: 'John Doe',
    event: "User 'J. Smith' Role Updated",
    ip: '192.168.1.10',
  },
  {
    timestamp: '2024-05-22 15:05',
    user: 'AI System',
    event: 'Intrusion Event Logged',
    ip: '10.0.0.5',
  },
  {
    timestamp: '2024-05-22 14:55',
    user: 'Jane Smith',
    event: 'Siren Manual Trigger',
    ip: '192.168.1.12',
  },
]

function statusBadge(status) {
  if (status === 'Active') {
    return 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
  }

  return 'bg-danger/20 text-danger border-danger/50'
}

export default function UserManagementPage() {
  return (
    <section className="grid gap-5 xl:grid-cols-[minmax(0,2.1fr)_minmax(340px,1fr)]">
      <div className="space-y-5">
        <div className="panel p-4 sm:p-5">
          <h2 className="text-xl font-semibold text-slate-100">USER ADMINISTRATION & ACCESS CONTROL</h2>

          <div className="mt-4 rounded-lg border border-white/10 bg-background/25 p-4">
            <h3 className="text-lg font-semibold text-slate-100">USER ACCOUNTS & ROLES</h3>

            <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(220px,1.4fr)_0.8fr_0.8fr_auto]">
              <label className="space-y-1.5">
                <span className="block text-xs font-medium uppercase tracking-wider text-slate-400">Search Filter</span>
                <input type="text" placeholder="Search users..." className="input-dark w-full" />
              </label>

              <label className="space-y-1.5">
                <span className="block text-xs font-medium uppercase tracking-wider text-slate-400">Role</span>
                <select className="select-dark w-full">
                  <option>All</option>
                  <option>Super Admin</option>
                  <option>Operator</option>
                </select>
              </label>

              <label className="space-y-1.5">
                <span className="block text-xs font-medium uppercase tracking-wider text-slate-400">Status</span>
                <select className="select-dark w-full">
                  <option>Active</option>
                  <option>Inactive</option>
                </select>
              </label>

              <div className="flex items-end gap-2">
                <button
                  type="button"
                  className="grid h-10 w-10 place-items-center rounded-md border border-white/10 bg-[#252531] text-slate-300"
                >
                  <Filter size={16} />
                </button>
                <button
                  type="button"
                  className="grid h-10 w-10 place-items-center rounded-md border border-white/10 bg-[#252531] text-slate-300"
                >
                  <SlidersHorizontal size={16} />
                </button>
              </div>
            </div>

            <div className="mt-4 overflow-x-auto rounded-lg border border-white/10">
              <table className="min-w-full divide-y divide-white/10 text-sm">
                <thead className="bg-[#252531] text-xs uppercase tracking-wider text-slate-400">
                  <tr>
                    <th className="px-3 py-3 text-left">User ID</th>
                    <th className="px-3 py-3 text-left">Name</th>
                    <th className="px-3 py-3 text-left">Email</th>
                    <th className="px-3 py-3 text-left">Role</th>
                    <th className="px-3 py-3 text-left">Assigned Zones</th>
                    <th className="px-3 py-3 text-left">Status</th>
                    <th className="px-3 py-3 text-left">Actions</th>
                  </tr>
                </thead>

                <tbody className="divide-y divide-white/10 text-slate-200">
                  {users.map((user) => (
                    <tr key={user.id} className="hover:bg-white/[0.02]">
                      <td className="px-3 py-3 font-medium text-slate-100">{user.id}</td>
                      <td className="px-3 py-3">{user.name}</td>
                      <td className="px-3 py-3 text-slate-300">{user.email}</td>
                      <td className="px-3 py-3">{user.role}</td>
                      <td className="px-3 py-3">
                        <span className="inline-flex items-center gap-2">
                          <span className={`h-2.5 w-2.5 rounded-full ${user.zoneColor}`} />
                          {user.zones}
                        </span>
                      </td>
                      <td className="px-3 py-3">
                        <span
                          className={`inline-flex rounded-md border px-2.5 py-1 text-xs font-semibold uppercase tracking-wide ${statusBadge(
                            user.status,
                          )}`}
                        >
                          {user.status}
                        </span>
                      </td>
                      <td className="px-3 py-3">
                        <div className="flex items-center gap-2">
                          <button type="button" className="text-emerald-400 hover:text-emerald-300">
                            <Pencil size={16} />
                          </button>
                          <button type="button" className="text-slate-400 hover:text-slate-200">
                            <Ban size={16} />
                          </button>
                          <button type="button" className="text-danger hover:text-danger/80">
                            <Trash2 size={16} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="mt-4 flex flex-wrap items-center gap-3">
              <select className="select-dark w-44">
                <option>BULK ACTIONS:</option>
                <option>Activate</option>
                <option>Deactivate</option>
                <option>Delete</option>
              </select>

              <button
                type="button"
                className="h-10 rounded-md border border-white/10 bg-white/5 px-4 text-sm font-medium text-slate-300"
              >
                APPLY
              </button>

              <button
                type="button"
                className="ml-auto inline-flex h-10 items-center gap-2 rounded-md bg-emerald-600 px-4 text-sm font-semibold text-white hover:bg-emerald-500"
              >
                <Plus size={16} />
                ADD NEW USER
              </button>
            </div>
          </div>
        </div>

        <div className="panel p-3">
          <button
            type="button"
            className="mx-auto inline-flex h-11 items-center gap-2 rounded-lg border border-white/20 bg-white/5 px-6 text-sm font-semibold text-slate-100"
          >
            <Download size={16} />
            EXPORT USER LIST (CSV/PDF)
          </button>
        </div>
      </div>

      <aside className="space-y-5">
        <div className="panel p-5">
          <h3 className="text-lg font-semibold text-slate-100">
            ACCESS CONTROL DETAILS <span className="text-sm text-slate-400">(Selected User: USR-001)</span>
          </h3>

          <div className="mt-5 grid gap-2 sm:grid-cols-2">
            {accessSteps.map(({ label, icon: Icon, active }) => (
              <div key={label} className="rounded-lg border border-white/10 bg-background/30 p-3">
                <div className="flex items-center gap-2">
                  <span
                    className={`grid h-8 w-8 place-items-center rounded-md ${
                      active ? 'bg-emerald-500/20 text-emerald-300' : 'bg-danger/20 text-danger'
                    }`}
                  >
                    <Icon size={15} />
                  </span>
                  <span className="text-sm font-medium text-slate-200">{label}</span>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-5 border-t border-white/10 pt-4">
            <h4 className="text-base font-semibold text-slate-100">PERMISSION BREAKDOWN:</h4>
            <p className="mt-1 text-sm text-slate-400">USR-001 (Super Admin)</p>

            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              {permissionItems.map((permission) => (
                <div
                  key={permission}
                  className="flex items-center justify-between rounded-md border border-white/10 bg-background/30 px-3 py-2 text-sm text-slate-200"
                >
                  {permission}
                  <span className="grid h-5 w-5 place-items-center rounded-full bg-emerald-500/20 text-emerald-300">
                    <Check size={12} />
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="panel p-5">
          <h3 className="text-lg font-semibold text-slate-100">SYSTEM ACTIVITY LOG</h3>
          <div className="mt-3 overflow-x-auto rounded-lg border border-white/10">
            <table className="min-w-full divide-y divide-white/10 text-sm">
              <thead className="bg-[#252531] text-xs uppercase tracking-wider text-slate-400">
                <tr>
                  <th className="px-3 py-2 text-left">Timestamp</th>
                  <th className="px-3 py-2 text-left">User</th>
                  <th className="px-3 py-2 text-left">Event</th>
                  <th className="px-3 py-2 text-left">IP Address</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/10 text-slate-200">
                {activityLogs.map((entry) => (
                  <tr key={`${entry.timestamp}-${entry.ip}`}>
                    <td className="px-3 py-2 text-slate-300">{entry.timestamp}</td>
                    <td className="px-3 py-2">{entry.user}</td>
                    <td className="px-3 py-2">{entry.event}</td>
                    <td className="px-3 py-2 text-slate-300">{entry.ip}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </aside>
    </section>
  )
}