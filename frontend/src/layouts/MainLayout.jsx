import {
  Bell,
  BrainCircuit,
  ChevronDown,
  History,
  MapPinned,
  Monitor,
  Search,
  ShieldCheck,
  Users,
} from 'lucide-react'
import { NavLink, Outlet } from 'react-router-dom'

const menuItems = [
  { to: '/live-monitor', label: 'Live Monitor', icon: Monitor },
  { to: '/events-history', label: 'Events History', icon: History },
  { to: '/zone-config', label: 'Zone Config', icon: MapPinned },
  // { to: '/ai-settings', label: 'AI Settings', icon: BrainCircuit },
  { to: '/user-management', label: 'User Management', icon: Users },
]

export default function MainLayout() {
  return (
    <div className="min-h-screen bg-[#060B17] text-slate-100">
      {/* Sidebar Navigation */}
      <aside className="fixed inset-y-0 left-0 z-30 w-72 border-r border-white/10 bg-[linear-gradient(180deg,rgba(9,14,28,0.98)_0%,rgba(12,18,35,0.96)_100%)] shadow-[0_0_0_1px_rgba(255,255,255,0.02),0_20px_60px_rgba(0,0,0,0.35)] backdrop-blur-xl">
        {/* Logo Section */}
        <div className="border-b border-white/10 px-5 py-5">
          <div className="mb-5 flex items-center gap-3">
            <div className="flex size-11 items-center justify-center rounded-2xl bg-[linear-gradient(135deg,#ff8b2c_0%,#ff6a2d_100%)] text-white shadow-[0_12px_30px_rgba(255,116,44,0.35)]">
              <ShieldCheck size={22} />
            </div>
            <div>
              <p className="text-lg font-semibold tracking-tight text-white">CSP-AI</p>
              <p className="text-xs text-slate-400">Child Safety Platform</p>
            </div>
          </div>
        </div>

        {/* Navigation Menu */}
        <nav className="space-y-2 px-4 py-5">
          <p className="mb-3 px-2 text-[11px] font-semibold uppercase tracking-[0.28em] text-slate-500">
            Navigation
          </p>
          {menuItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `group relative flex items-center gap-3 rounded-2xl px-4 py-3 text-sm font-medium transition-all duration-200 ${
                  isActive
                    ? 'bg-[linear-gradient(135deg,rgba(255,139,44,0.18)_0%,rgba(255,139,44,0.08)_100%)] text-orange-300 shadow-[inset_0_0_0_1px_rgba(255,139,44,0.24)]'
                    : 'text-slate-300 hover:bg-white/5 hover:text-white'
                }`
              }
            >
              <span className="absolute inset-y-2 left-0 w-1 rounded-full bg-orange-400 opacity-0 transition-opacity group-hover:opacity-50" />
              <Icon size={18} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
      </aside>

      {/* Main Content */}
      <div className="ml-72 min-h-screen bg-[radial-gradient(circle_at_top_right,rgba(59,130,246,0.08),transparent_28%),radial-gradient(circle_at_bottom_left,rgba(255,139,44,0.08),transparent_24%)]">
        {/* Header */}
        <header className="sticky top-0 z-20 border-b border-white/10 bg-[rgba(8,13,26,0.72)] backdrop-blur-xl">
          <div className="flex flex-wrap items-center justify-between gap-4 px-6 py-4 lg:px-8">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.32em] text-sky-300/80">Admin workspace</p>
              <h1 className="mt-1 text-2xl font-semibold tracking-tight text-white">Management Dashboard</h1>
            </div>

            {/* Header Controls */}
            <div className="flex items-center gap-3">
              {/* Search Input */}
              <label className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-500" />
                <input
                  type="text"
                  placeholder="Search..."
                  className="h-11 w-56 rounded-2xl border border-white/10 bg-white/5 pl-9 pr-3 text-sm text-slate-100 placeholder:text-slate-500 outline-none transition focus:border-orange-400/60 focus:bg-white/10 focus:ring-4 focus:ring-orange-500/10"
                />
              </label>

              {/* Notification Button */}
              <button
                type="button"
                className="flex size-11 items-center justify-center rounded-2xl border border-white/10 bg-white/5 text-slate-300 transition hover:bg-white/10 hover:text-white"
                title="Notifications"
              >
                <Bell size={18} />
              </button>

              {/* User Dropdown */}
              <button
                type="button"
                className="flex items-center gap-2 rounded-2xl border border-white/10 bg-white/5 px-3 py-2.5 text-sm text-slate-200 transition hover:bg-white/10"
              >
                <div className="flex size-7 items-center justify-center rounded-full bg-[linear-gradient(135deg,#ffb15f_0%,#ff7a24_100%)] text-xs font-semibold text-white">
                  A
                </div>
                <span className="font-medium">Admin</span>
                <ChevronDown size={16} className="text-slate-400" />
              </button>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="mx-auto max-w-[1700px] p-6 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}