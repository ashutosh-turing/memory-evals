import { useAuth } from '../contexts/AuthContext'
import { useTheme } from '../contexts/ThemeContext'
import { 
  Settings, 
  LogOut, 
  Moon, 
  Sun, 
  Building2,
  Users as UsersIcon,
  Briefcase,
  ChevronDown
} from 'lucide-react'
import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

export const Header = () => {
  const { user, logout } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const navigate = useNavigate()
  const [showUserMenu, setShowUserMenu] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  // Close menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setShowUserMenu(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const getRoleBadgeColor = (role?: string) => {
    switch (role) {
      case 'super_admin':
        return 'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-400 border-purple-300 dark:border-purple-700'
      case 'org_admin':
        return 'bg-primary-100 dark:bg-primary-900/30 text-primary-700 dark:text-primary-400 border-primary-300 dark:border-primary-700'
      case 'team_admin':
        return 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 border-blue-300 dark:border-blue-700'
      default:
        return 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 border-gray-300 dark:border-gray-700'
    }
  }

  const formatRole = (role?: string) => {
    if (!role) return 'User'
    return role.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ')
  }

  return (
    <header className="bg-white dark:bg-dark-900 border-b border-gray-200 dark:border-gray-800 shadow-sm sticky top-0 z-40">
      <div className="px-6 py-3">
        <div className="flex items-center justify-between gap-6">
          {/* Left: Context Info (Org/Team/Project) */}
          <div className="flex items-center gap-3 min-w-0 flex-1">
            {/* Organization */}
            {user?.org_name && (
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gradient-to-r from-primary-50 to-purple-50 dark:from-primary-900/20 dark:to-purple-900/20 border border-primary-200 dark:border-primary-800">
                <Building2 className="w-4 h-4 text-primary-600 dark:text-primary-400 flex-shrink-0" />
                <span className="text-sm font-semibold text-primary-900 dark:text-primary-100 truncate">
                  {user.org_name}
                </span>
              </div>
            )}

            {/* Team */}
            {user?.team_name && (
              <>
                <span className="text-gray-400 dark:text-gray-600">/</span>
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800">
                  <UsersIcon className="w-4 h-4 text-blue-600 dark:text-blue-400 flex-shrink-0" />
                  <span className="text-sm font-semibold text-blue-900 dark:text-blue-100 truncate">
                    {user.team_name}
                  </span>
                </div>
              </>
            )}

            {/* Project (if exists) */}
            {user?.project_name && (
              <>
                <span className="text-gray-400 dark:text-gray-600">/</span>
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800">
                  <Briefcase className="w-4 h-4 text-green-600 dark:text-green-400 flex-shrink-0" />
                  <span className="text-sm font-semibold text-green-900 dark:text-green-100 truncate">
                    {user.project_name}
                  </span>
                </div>
              </>
            )}
          </div>

          {/* Right: User Actions */}
          <div className="flex items-center gap-3 flex-shrink-0">
            {/* Theme Toggle */}
            <button
              onClick={toggleTheme}
              className="p-2.5 rounded-lg hover:bg-gray-100 dark:hover:bg-dark-800 transition-all duration-200 hover:scale-105"
              title={theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
            >
              {theme === 'dark' ? (
                <Sun className="w-5 h-5 text-yellow-500" />
              ) : (
                <Moon className="w-5 h-5 text-gray-600" />
              )}
            </button>

            {/* Settings */}
            <button
              onClick={() => navigate('/settings')}
              className="p-2.5 rounded-lg hover:bg-gray-100 dark:hover:bg-dark-800 transition-all duration-200 hover:scale-105"
              title="Settings"
            >
              <Settings className="w-5 h-5 text-gray-600 dark:text-gray-400" />
            </button>

            {/* Divider */}
            <div className="h-8 w-px bg-gray-200 dark:bg-gray-700"></div>

            {/* User Menu */}
            <div className="relative" ref={menuRef}>
              <button
                onClick={() => setShowUserMenu(!showUserMenu)}
                className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-gray-100 dark:hover:bg-dark-800 transition-all duration-200 group"
              >
                {/* Avatar */}
                {user?.picture ? (
                  <img 
                    src={user.picture} 
                    alt={user.name || 'User'} 
                    className="w-9 h-9 rounded-full object-cover ring-2 ring-gray-200 dark:ring-gray-700 group-hover:ring-primary-500 transition-all"
                  />
                ) : (
                  <div className="w-9 h-9 rounded-full bg-gradient-to-br from-primary-600 to-purple-600 flex items-center justify-center text-white font-bold text-sm ring-2 ring-gray-200 dark:ring-gray-700 group-hover:ring-primary-500 transition-all shadow-md">
                    {user?.name?.charAt(0)?.toUpperCase() || user?.email?.charAt(0)?.toUpperCase() || 'U'}
                  </div>
                )}

                {/* User Info */}
                <div className="hidden md:flex flex-col items-start">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-gray-900 dark:text-white">
                      {user?.name || 'User'}
                    </span>
                    <span className={`px-2 py-0.5 text-xs font-bold rounded-full border ${getRoleBadgeColor(user?.user_role)}`}>
                      {formatRole(user?.user_role)}
                    </span>
                  </div>
                  <span className="text-xs text-gray-500 dark:text-gray-400">
                    {user?.email}
                  </span>
                </div>

                <ChevronDown className={`w-4 h-4 text-gray-500 transition-transform ${showUserMenu ? 'rotate-180' : ''}`} />
              </button>

              {/* Dropdown Menu */}
              {showUserMenu && (
                <div className="absolute right-0 mt-2 w-72 bg-white dark:bg-dark-800 rounded-xl shadow-2xl border border-gray-200 dark:border-gray-700 py-2 z-50 animate-fade-in">
                  {/* User Info Section */}
                  <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
                    <div className="flex items-center gap-3 mb-3">
                      {user?.picture ? (
                        <img 
                          src={user.picture} 
                          alt={user.name || 'User'} 
                          className="w-12 h-12 rounded-full object-cover ring-2 ring-primary-200 dark:ring-primary-800"
                        />
                      ) : (
                        <div className="w-12 h-12 rounded-full bg-gradient-to-br from-primary-600 to-purple-600 flex items-center justify-center text-white font-bold text-lg shadow-md">
                          {user?.name?.charAt(0)?.toUpperCase() || user?.email?.charAt(0)?.toUpperCase() || 'U'}
                        </div>
                      )}
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-bold text-gray-900 dark:text-white truncate">
                          {user?.name || 'User'}
                        </p>
                        <p className="text-xs text-gray-500 dark:text-gray-400 truncate">
                          {user?.email}
                        </p>
                      </div>
                    </div>
                    <span className={`inline-block px-3 py-1 text-xs font-bold rounded-full border ${getRoleBadgeColor(user?.user_role)}`}>
                      {formatRole(user?.user_role)}
                    </span>
                  </div>

                  {/* Context Info */}
                  <div className="px-4 py-3 space-y-2 text-xs border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-dark-900/50">
                    {user?.org_name && (
                      <div className="flex items-center gap-2">
                        <Building2 className="w-4 h-4 text-primary-500 flex-shrink-0" />
                        <span className="text-gray-600 dark:text-gray-400">Organization:</span>
                        <span className="font-semibold text-gray-900 dark:text-white truncate">{user.org_name}</span>
                      </div>
                    )}
                    {user?.team_name && (
                      <div className="flex items-center gap-2">
                        <UsersIcon className="w-4 h-4 text-blue-500 flex-shrink-0" />
                        <span className="text-gray-600 dark:text-gray-400">Team:</span>
                        <span className="font-semibold text-gray-900 dark:text-white truncate">{user.team_name}</span>
                      </div>
                    )}
                    {user?.project_name && (
                      <div className="flex items-center gap-2">
                        <Briefcase className="w-4 h-4 text-green-500 flex-shrink-0" />
                        <span className="text-gray-600 dark:text-gray-400">Project:</span>
                        <span className="font-semibold text-gray-900 dark:text-white truncate">{user.project_name}</span>
                      </div>
                    )}
                  </div>

                  {/* Actions */}
                  <div className="px-2 py-2">
                    <button
                      onClick={() => {
                        setShowUserMenu(false)
                        navigate('/settings')
                      }}
                      className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-dark-700 transition-colors"
                    >
                      <Settings className="w-4 h-4" />
                      <span>Account Settings</span>
                    </button>
                    <button
                      onClick={() => {
                        setShowUserMenu(false)
                        logout()
                      }}
                      className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-error-700 dark:text-error-400 hover:bg-error-50 dark:hover:bg-error-900/20 transition-colors mt-1"
                    >
                      <LogOut className="w-4 h-4" />
                      <span>Logout</span>
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </header>
  )
}
