import { NavLink } from 'react-router-dom'
import { 
  LayoutDashboard, 
  ListTodo, 
  Users, 
  Trophy
} from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'

interface SidebarProps {
  className?: string
}

export const Sidebar = ({ className = '' }: SidebarProps) => {
  const { user } = useAuth()
  
  // Determine effective role (global_role takes precedence)
  const effectiveRole = user?.global_role || user?.user_role
  
  // Check if user has team_admin or higher privileges
  const canViewTeamTasks = effectiveRole && ['team_admin', 'org_admin', 'super_admin'].includes(effectiveRole)
  
  const navigation = [
    { name: 'Dashboard', href: '/', icon: LayoutDashboard, show: true },
    { name: 'My Tasks', href: '/?filter=my_tasks', icon: ListTodo, show: true },
    { name: 'Team Tasks', href: '/?filter=team_tasks', icon: Users, show: canViewTeamTasks },
    { name: 'Leaderboards', href: '/leaderboards', icon: Trophy, show: true },
  ].filter(item => item.show)

  return (
    <aside className={`sidebar ${className}`}>
      <div className="flex flex-col h-full">
        {/* Logo - Increased spacing and size */}
        <div className="flex items-center gap-4 px-6 py-6 border-b border-gray-200 dark:border-gray-800 shadow-sm">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary-600 to-purple-600 flex items-center justify-center shadow-lg transform transition-transform hover:scale-105">
            <span className="text-white font-bold text-base">MB</span>
          </div>
          <div>
            <h1 className="text-xl font-bold text-gray-900 dark:text-white tracking-tight">
              Memory Break
            </h1>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
              Orchestrator
            </p>
          </div>
        </div>

        {/* Navigation - Better spacing and typography */}
        <nav className="flex-1 px-4 py-6 space-y-2 overflow-y-auto">
          {navigation.map((item) => (
            <NavLink
              key={item.name}
              to={item.href}
              className={({ isActive }) =>
                `flex items-center gap-4 px-4 py-3.5 rounded-xl text-base font-medium transition-all duration-200 ${
                  isActive
                    ? 'bg-primary-50 dark:bg-primary-900/20 text-primary-700 dark:text-primary-400 shadow-sm transform scale-[1.02]'
                    : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-dark-800 hover:shadow-sm hover:transform hover:scale-[1.01]'
                }`
              }
            >
              <item.icon className="w-5 h-5 flex-shrink-0" />
              <span>{item.name}</span>
            </NavLink>
          ))}
        </nav>
      </div>
    </aside>
  )
}

