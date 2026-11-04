import { useState } from 'react'
import { Link, useLocation, Outlet } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import {
  HomeIcon,
  UserGroupIcon,
  ChatBubbleLeftRightIcon,
  BuildingOffice2Icon,
  BookOpenIcon,
  ChartBarIcon,
  Cog6ToothIcon,
  ArrowRightOnRectangleIcon,
  Bars3Icon,
  XMarkIcon,
} from '@heroicons/react/24/outline'

const NAV_ITEMS = [
  { name: 'Overview', path: '/dashboard', icon: HomeIcon },
  { name: 'Leads', path: '/leads', icon: UserGroupIcon },
  { name: 'Conversations', path: '/conversations', icon: ChatBubbleLeftRightIcon },
  { name: 'Projects', path: '/projects', icon: BuildingOffice2Icon },
  { name: 'Knowledge Base', path: '/knowledge', icon: BookOpenIcon, role: 'developer' },
  { name: 'Analytics', path: '/analytics', icon: ChartBarIcon },
  { name: 'Settings', path: '/settings', icon: Cog6ToothIcon, role: 'admin' },
]

export default function Layout() {
  const { user, logout, isAdmin, isDeveloper } = useAuth()
  const location = useLocation()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  const isAllowed = (item) => {
    if (!item.role) return true
    if (item.role === 'developer') return isDeveloper
    if (item.role === 'admin') return isAdmin
    return true
  }

  const roleBadgeColor = {
    developer: 'bg-purple-100 text-purple-800 border-purple-200',
    admin: 'bg-blue-100 text-blue-800 border-blue-200',
    staff: 'bg-emerald-100 text-emerald-800 border-emerald-200',
  }[user?.role] || 'bg-gray-100 text-gray-800 border-gray-200'

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* Sidebar for Desktop */}
      <aside className="hidden md:flex flex-col w-64 bg-primary text-white flex-shrink-0 shadow-lg">
        {/* Brand */}
        <div className="h-16 px-6 flex items-center border-b border-primary-800 gap-3">
          <div className="w-9 h-9 rounded-lg bg-accent flex items-center justify-center font-bold text-primary text-lg shadow-sm">
            A
          </div>
          <div>
            <h1 className="font-bold text-base tracking-wide text-white leading-tight">Abhinav Group</h1>
            <p className="text-xs text-accent-300 font-medium">Chatbot Admin</p>
          </div>
        </div>

        {/* Navigation links */}
        <nav className="flex-1 px-4 py-6 space-y-1.5 overflow-y-auto">
          {NAV_ITEMS.filter(isAllowed).map((item) => {
            const Icon = item.icon
            const active = location.pathname === item.path || location.pathname.startsWith(`${item.path}/`)
            return (
              <Link
                key={item.name}
                to={item.path}
                className={`flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  active
                    ? 'bg-primary-800 text-white shadow-inner font-semibold'
                    : 'text-gray-300 hover:bg-primary-800/60 hover:text-white'
                }`}
              >
                <Icon className={`w-5 h-5 ${active ? 'text-accent' : 'text-gray-400'}`} />
                <span>{item.name}</span>
              </Link>
            )
          })}
        </nav>

        {/* User footer */}
        <div className="p-4 border-t border-primary-800 bg-primary-950/40">
          <div className="flex items-center justify-between mb-3">
            <div className="truncate">
              <p className="text-sm font-semibold text-white truncate">{user?.username}</p>
              <span className={`inline-block mt-0.5 text-[10px] font-bold px-2 py-0.5 rounded-full border uppercase tracking-wider ${roleBadgeColor}`}>
                {user?.role}
              </span>
            </div>
            <button
              onClick={logout}
              title="Logout"
              className="p-1.5 rounded-lg text-gray-400 hover:text-red-400 hover:bg-primary-800 transition-colors"
            >
              <ArrowRightOnRectangleIcon className="w-5 h-5" />
            </button>
          </div>
          <p className="text-[11px] text-gray-400 text-center">v1.0.0 • Abhinav Group AI</p>
        </div>
      </aside>

      {/* Main content area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top bar for Mobile */}
        <header className="md:hidden bg-primary text-white px-4 h-16 flex items-center justify-between shadow-md">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center font-bold text-primary">
              A
            </div>
            <span className="font-bold text-sm">Abhinav Group Admin</span>
          </div>
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="p-1.5 rounded-lg hover:bg-primary-800 text-gray-200"
          >
            {mobileMenuOpen ? <XMarkIcon className="w-6 h-6" /> : <Bars3Icon className="w-6 h-6" />}
          </button>
        </header>

        {/* Mobile menu dropdown */}
        {mobileMenuOpen && (
          <div className="md:hidden bg-primary-900 border-b border-primary-800 px-4 py-4 space-y-1">
            {NAV_ITEMS.filter(isAllowed).map((item) => {
              const Icon = item.icon
              const active = location.pathname === item.path
              return (
                <Link
                  key={item.name}
                  to={item.path}
                  onClick={() => setMobileMenuOpen(false)}
                  className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium ${
                    active ? 'bg-primary text-accent font-semibold' : 'text-gray-300'
                  }`}
                >
                  <Icon className="w-5 h-5" />
                  <span>{item.name}</span>
                </Link>
              )
            })}
            <button
              onClick={() => {
                setMobileMenuOpen(false)
                logout()
              }}
              className="w-full text-left flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-red-300 font-medium hover:bg-red-950/40"
            >
              <ArrowRightOnRectangleIcon className="w-5 h-5" />
              <span>Logout</span>
            </button>
          </div>
        )}

        {/* Page content */}
        <main className="flex-1 overflow-y-auto p-4 md:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
