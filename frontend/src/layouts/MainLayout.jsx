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
    <div className="min-h-screen bg-gray-50">
      {/* Sidebar Navigation */}
      <aside className="fixed inset-y-0 left-0 z-30 w-64 border-r border-gray-200 bg-white shadow-sm">
        {/* Logo Section */}
        <div className="border-b border-gray-200 px-4 py-5">
          <div className="mb-4 flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-lg bg-gradient-to-br from-orange-500 to-orange-600 text-white shadow-md">
              <ShieldCheck size={22} />
            </div>
            <div>
              <p className="text-lg font-bold text-gray-900">CSP-AI</p>
              <p className="text-xs text-gray-500">Child Safety Platform</p>
            </div>
          </div>
        </div>

        {/* Navigation Menu */}
        <nav className="space-y-1 px-3 py-4">
          <p className="mb-3 px-2 text-xs font-semibold uppercase tracking-widest text-gray-400">
            Navigation
          </p>
          {menuItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-200 ${
                  isActive
                    ? 'bg-orange-50 text-orange-600 border-l-4 border-orange-500 pl-2'
                    : 'text-gray-700 hover:bg-gray-100 hover:text-gray-900'
                }`
              }
            >
              <Icon size={18} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
      </aside>

      {/* Main Content */}
      <div className="ml-64 min-h-screen">
        {/* Header */}
        <header className="border-b border-gray-200 bg-white shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-4 px-6 py-4">
            <h1 className="text-2xl font-bold text-gray-900">Management Dashboard</h1>

            {/* Header Controls */}
            <div className="flex items-center gap-3">
              {/* Search Input */}
              <label className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-gray-400" />
                <input
                  type="text"
                  placeholder="Search..."
                  className="h-10 rounded-lg border border-gray-300 bg-white pl-9 pr-3 text-sm text-gray-700 placeholder-gray-400 transition-colors focus:border-orange-500 focus:outline-none focus:ring-1 focus:ring-orange-500"
                />
              </label>

              {/* Notification Button */}
              <button
                type="button"
                className="flex size-10 items-center justify-center rounded-lg border border-gray-300 bg-white text-gray-600 transition-all hover:bg-gray-50 hover:text-gray-900"
                title="Notifications"
              >
                <Bell size={18} />
              </button>

              {/* User Dropdown */}
              <button
                type="button"
                className="flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 transition-all hover:bg-gray-50"
              >
                <div className="flex size-6 items-center justify-center rounded-full bg-gradient-to-br from-orange-400 to-orange-500 text-xs font-semibold text-white">
                  A
                </div>
                <span className="font-medium">Admin</span>
                <ChevronDown size={16} className="text-gray-400" />
              </button>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}