import { useState } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { useTheme } from '../contexts/ThemeContext'
import { 
  Settings as SettingsIcon, 
  User, 
  Bell, 
  Shield, 
  Moon, 
  Sun,
  Save,
  Mail,
  Building2,
  Users,
  Briefcase
} from 'lucide-react'
import { Sidebar, Header, useToast } from '../components'

export const SettingsPage = () => {
  const { user } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const { showToast } = useToast()
  
  const [activeTab, setActiveTab] = useState<'profile' | 'preferences' | 'team'>('profile')

  const handleSaveSettings = () => {
    showToast({
      type: 'success',
      title: 'Settings saved',
      message: 'Your preferences have been updated successfully',
    })
  }

  const tabs = [
    { id: 'profile', label: 'Profile', icon: User },
    { id: 'preferences', label: 'Preferences', icon: SettingsIcon },
    { id: 'team', label: 'Team', icon: Users },
  ]

  return (
    <div className="flex h-screen overflow-hidden bg-gray-50 dark:bg-dark-950">
      <Sidebar />

      <div className="flex-1 flex flex-col overflow-hidden ml-64">
        <Header />
        
        {/* Page Header */}
        <div className="bg-white dark:bg-dark-900 border-b border-gray-200 dark:border-gray-800 px-6 py-4">
          <div className="flex items-center gap-3">
            <SettingsIcon className="w-8 h-8 text-gray-700 dark:text-gray-300" />
            <div>
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
                Settings
              </h1>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
                Manage your account and preferences
              </p>
            </div>
          </div>
        </div>

        {/* Content */}
        <main className="flex-1 overflow-y-auto p-6">
          <div className="max-w-4xl mx-auto">
            {/* Tabs */}
            <div className="flex gap-2 mb-6 border-b border-gray-200 dark:border-gray-800">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as any)}
                  className={`flex items-center gap-2 px-4 py-3 font-medium transition-colors border-b-2 ${
                    activeTab === tab.id
                      ? 'border-primary-600 text-primary-600 dark:text-primary-400'
                      : 'border-transparent text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200'
                  }`}
                >
                  <tab.icon className="w-5 h-5" />
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Profile Tab */}
            {activeTab === 'profile' && (
              <div className="space-y-6">
                <div className="card p-6">
                  <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                    Profile Information
                  </h2>
                  
                  <div className="space-y-4">
                    <div>
                      <label className="label">
                        <User className="w-4 h-4" />
                        Full Name
                      </label>
                      <input
                        type="text"
                        className="input"
                        value={user?.name || ''}
                        disabled
                      />
                      <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                        Managed by your organization's SSO
                      </p>
                    </div>

                    <div>
                      <label className="label">
                        <Mail className="w-4 h-4" />
                        Email Address
                      </label>
                      <input
                        type="email"
                        className="input"
                        value={user?.email || ''}
                        disabled
                      />
                    </div>

                    <div>
                      <label className="label">
                        <Shield className="w-4 h-4" />
                        Role
                      </label>
                      <input
                        type="text"
                        className="input"
                        value={user?.user_role || 'user'}
                        disabled
                      />
                    </div>
                  </div>
                </div>

                <div className="card p-6">
                  <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                    Organization Details
                  </h2>
                  
                  <div className="space-y-4">
                    <div>
                      <label className="label">
                        <Building2 className="w-4 h-4" />
                        Organization ID
                      </label>
                      <input
                        type="text"
                        className="input font-mono text-sm"
                        value={user?.org_id || 'N/A'}
                        disabled
                      />
                    </div>

                    <div>
                      <label className="label">
                        <Users className="w-4 h-4" />
                        Team ID
                      </label>
                      <input
                        type="text"
                        className="input font-mono text-sm"
                        value={user?.team_id || 'N/A'}
                        disabled
                      />
                    </div>

                    <div>
                      <label className="label">
                        <Briefcase className="w-4 h-4" />
                        Project ID
                      </label>
                      <input
                        type="text"
                        className="input font-mono text-sm"
                        value={user?.project_id || 'N/A'}
                        disabled
                      />
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Preferences Tab */}
            {activeTab === 'preferences' && (
              <div className="space-y-6">
                <div className="card p-6">
                  <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                    Appearance
                  </h2>
                  
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <label className="label mb-0">
                          {theme === 'dark' ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />}
                          Theme
                        </label>
                        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                          Choose your preferred color scheme
                        </p>
                      </div>
                      <button
                        onClick={toggleTheme}
                        className="px-4 py-2 rounded-lg bg-gray-100 dark:bg-dark-800 hover:bg-gray-200 dark:hover:bg-dark-700 transition-colors font-medium text-sm"
                      >
                        {theme === 'dark' ? 'Dark Mode' : 'Light Mode'}
                      </button>
                    </div>
                  </div>
                </div>

                <div className="card p-6">
                  <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                    Notifications
                  </h2>
                  
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <label className="label mb-0">
                          <Bell className="w-4 h-4" />
                          Task Completion Notifications
                        </label>
                        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                          Get notified when your tasks complete
                        </p>
                      </div>
                      <input
                        type="checkbox"
                        className="w-5 h-5 rounded border-gray-300 dark:border-gray-700"
                        defaultChecked
                      />
                    </div>

                    <div className="flex items-center justify-between">
                      <div>
                        <label className="label mb-0">
                          <Bell className="w-4 h-4" />
                          Team Activity Notifications
                        </label>
                        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                          Get notified about team member activities
                        </p>
                      </div>
                      <input
                        type="checkbox"
                        className="w-5 h-5 rounded border-gray-300 dark:border-gray-700"
                        defaultChecked
                      />
                    </div>
                  </div>
                </div>

                <div className="flex justify-end">
                  <button onClick={handleSaveSettings} className="btn-primary">
                    <Save className="w-5 h-5" />
                    Save Preferences
                  </button>
                </div>
              </div>
            )}

            {/* Team Tab */}
            {activeTab === 'team' && (
              <div className="space-y-6">
                <div className="card p-6">
                  <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                    Team Information
                  </h2>
                  
                  <div className="text-center py-12">
                    <Users className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                      Team Management
                    </h3>
                    <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
                      Team management features are coming soon
                    </p>
                    <p className="text-xs text-gray-400 dark:text-gray-500">
                      Contact your organization administrator for team access
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  )
}

