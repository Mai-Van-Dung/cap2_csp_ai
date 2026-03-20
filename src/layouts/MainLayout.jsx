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
  { to: '/ai-settings', label: 'AI Settings', icon: BrainCircuit },
  { to: '/user-management', label: 'User Management', icon: Users },
]

export default function MainLayout() {
  return (
    <div className="min-h-screen bg-background text-slate-100">
      <aside className="fixed inset-y-0 left-0 z-30 w-64 border-r border-white/10 bg-surface/95 px-4 py-5">
        <div className="mb-8 flex items-center gap-3 border-b border-white/10 pb-4">
          <div className="grid size-10 place-items-center rounded-xl bg-primary/20 text-primary">
            <ShieldCheck size={22} />
          </div>
          <div>
            <p className="text-xl font-semibold tracking-wide text-primary">CSP-AI</p>
            <p className="text-xs text-slate-400">Child Safety</p>
          </div>
        </div>

        <p className="mb-3 px-2 text-xs uppercase tracking-[0.2em] text-slate-500">Admin Panel</p>
        <nav className="space-y-2">
          {menuItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition ${
                  isActive
                    ? 'bg-primary text-[#1A1A1A] shadow-[0_8px_20px_rgba(255,140,0,0.35)]'
                    : 'text-slate-300 hover:bg-white/5 hover:text-white'
                }`
              }
            >
              <Icon size={18} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="ml-64 min-h-screen p-4 md:p-6">
        <header className="panel mb-5 flex flex-wrap items-center justify-between gap-4 px-5 py-3">
          <h1 className="text-lg font-semibold tracking-wide md:text-2xl">MANAGEMENT DASHBOARD</h1>

          <div className="flex w-full items-center justify-end gap-3 md:w-auto">
            <label className="relative w-full max-w-xs md:w-80">
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-500" />
              <input
                type="text"
                placeholder="Search"
                className="h-10 w-full rounded-md border border-white/10 bg-[#242B3A] pl-9 pr-3 text-sm text-slate-200 placeholder:text-slate-500 focus:border-primary focus:outline-none"
              />
            </label>

            <button
              type="button"
              className="grid size-10 place-items-center rounded-md border border-white/10 bg-[#242B3A] text-slate-300"
            >
              <Bell size={16} />
            </button>

            <button
              type="button"
              className="flex h-10 items-center gap-2 rounded-md border border-white/10 bg-[#242B3A] px-3 text-sm text-slate-200"
            >
              <span className="grid size-6 place-items-center rounded-full bg-primary/20 text-xs font-semibold text-primary">
                A
              </span>
              Admin
              <ChevronDown size={14} className="text-slate-400" />
            </button>
          </div>
        </header>

        <Outlet />
      </div>
    </div>
  )
}