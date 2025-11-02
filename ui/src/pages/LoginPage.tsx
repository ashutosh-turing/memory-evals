import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { useTheme } from '../contexts/ThemeContext'
import { 
  LogIn, 
  Shield, 
  Sparkles, 
  Zap, 
  TrendingUp, 
  Moon, 
  Sun,
  Brain,
  BarChart3,
  Lock,
  Rocket,
  Code2,
  GitPullRequest
} from 'lucide-react'

export const LoginPage = () => {
  const { isAuthenticated } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const navigate = useNavigate()
  const [isHovered, setIsHovered] = useState(false)

  useEffect(() => {
    if (isAuthenticated) {
      navigate('/', { replace: true })
    }
  }, [isAuthenticated, navigate])

  const handleLogin = () => {
    const ssoServiceUrl = import.meta.env.VITE_SSO_SERVICE_URL
    const teamId = import.meta.env.VITE_TEAM_ID
    const redirectUri = import.meta.env.VITE_REDIRECT_URI || `${window.location.origin}/auth/callback`
    
    window.location.href = `${ssoServiceUrl}/auth/login?redirect_uri=${encodeURIComponent(redirectUri)}&team_id=${teamId}`
  }

  return (
    <div className="min-h-screen flex bg-white dark:bg-dark-950 transition-colors duration-300">
      {/* Theme Toggle */}
      <button
        onClick={toggleTheme}
        className="fixed top-6 right-6 z-50 p-3 rounded-xl bg-white dark:bg-dark-900 shadow-lg hover:shadow-xl transition-all duration-200 border border-gray-200 dark:border-gray-800"
      >
        {theme === 'dark' ? (
          <Sun className="w-5 h-5 text-yellow-500" />
        ) : (
          <Moon className="w-5 h-5 text-gray-700" />
        )}
      </button>

      {/* Left Panel - Hero Section */}
      <div className="hidden lg:flex lg:w-1/2 bg-gradient-to-br from-primary-600 via-purple-600 to-primary-700 dark:from-primary-900 dark:via-purple-900 dark:to-primary-950 p-12 flex-col justify-between relative overflow-hidden">
        {/* Animated background */}
        <div className="absolute inset-0 opacity-30">
          <div className="absolute top-20 left-20 w-72 h-72 bg-purple-500 rounded-full mix-blend-multiply filter blur-3xl animate-blob"></div>
          <div className="absolute bottom-20 right-20 w-72 h-72 bg-primary-500 rounded-full mix-blend-multiply filter blur-3xl animate-blob animation-delay-2000"></div>
          <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-72 h-72 bg-indigo-500 rounded-full mix-blend-multiply filter blur-3xl animate-blob animation-delay-4000"></div>
        </div>

        <div className="relative z-10">
          {/* Logo */}
          <div className="flex items-center gap-3 mb-12">
            <div className="w-12 h-12 rounded-xl bg-white/20 backdrop-blur-sm flex items-center justify-center">
              <Brain className="w-7 h-7 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white">Memory Break</h1>
              <p className="text-sm text-white/80">Orchestrator</p>
            </div>
          </div>

          {/* Hero Content */}
          <div className="space-y-6">
            <h2 className="text-5xl font-bold text-white leading-tight">
              Evaluate AI Agents
              <br />
              <span className="text-white/80">Like Never Before</span>
            </h2>
            <p className="text-xl text-white/90 leading-relaxed max-w-md">
              Comprehensive memory compression testing for iFlow, Claude, and Gemini agents with real-time insights.
            </p>
          </div>

          {/* Features Grid */}
          <div className="grid grid-cols-2 gap-4 mt-12">
            <div className="bg-white/10 backdrop-blur-sm rounded-xl p-4 border border-white/20">
              <BarChart3 className="w-8 h-8 text-white mb-2" />
              <h3 className="text-white font-semibold mb-1">Real-time Analytics</h3>
              <p className="text-sm text-white/70">Live performance tracking</p>
            </div>
            <div className="bg-white/10 backdrop-blur-sm rounded-xl p-4 border border-white/20">
              <GitPullRequest className="w-8 h-8 text-white mb-2" />
              <h3 className="text-white font-semibold mb-1">PR Integration</h3>
              <p className="text-sm text-white/70">Seamless GitHub workflow</p>
            </div>
            <div className="bg-white/10 backdrop-blur-sm rounded-xl p-4 border border-white/20">
              <Code2 className="w-8 h-8 text-white mb-2" />
              <h3 className="text-white font-semibold mb-1">Multi-Agent</h3>
              <p className="text-sm text-white/70">Compare 3+ agents</p>
            </div>
            <div className="bg-white/10 backdrop-blur-sm rounded-xl p-4 border border-white/20">
              <Lock className="w-8 h-8 text-white mb-2" />
              <h3 className="text-white font-semibold mb-1">Enterprise SSO</h3>
              <p className="text-sm text-white/70">Secure authentication</p>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="relative z-10 text-white/60 text-sm">
          <p>© 2025 Turing Platform Team. All rights reserved.</p>
        </div>
      </div>

      {/* Right Panel - Login Form */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-md space-y-8 animate-fade-in">
          {/* Mobile Logo */}
          <div className="lg:hidden text-center mb-8">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-primary-600 to-purple-600 mb-4">
              <Brain className="w-9 h-9 text-white" />
            </div>
            <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Memory Break</h1>
            <p className="text-gray-500 dark:text-gray-400">Orchestrator</p>
          </div>

          {/* Welcome Text */}
          <div className="text-center lg:text-left">
            <h2 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
              Welcome Back
            </h2>
            <p className="text-gray-600 dark:text-gray-400">
              Sign in to continue to your dashboard
            </p>
          </div>

          {/* Login Card */}
          <div className="card p-8 space-y-6">
            {/* Features List */}
            <div className="space-y-4">
              <div className="flex items-start gap-3">
                <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-primary-100 dark:bg-primary-900/30 flex items-center justify-center">
                  <Sparkles className="w-5 h-5 text-primary-600 dark:text-primary-400" />
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900 dark:text-white text-sm">
                    Multi-Agent Evaluation
                  </h3>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    Test iFlow, Claude & Gemini simultaneously
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-3">
                <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center">
                  <Zap className="w-5 h-5 text-purple-600 dark:text-purple-400" />
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900 dark:text-white text-sm">
                    Real-Time Insights
                  </h3>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    Live logs and performance metrics
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-3">
                <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-success-100 dark:bg-success-900/30 flex items-center justify-center">
                  <TrendingUp className="w-5 h-5 text-success-600 dark:text-success-400" />
                </div>
                <div>
                  <h3 className="font-semibold text-gray-900 dark:text-white text-sm">
                    Team Collaboration
                  </h3>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    Multi-tenant workspace support
                  </p>
                </div>
              </div>
            </div>

            {/* Divider */}
            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-gray-200 dark:border-gray-800"></div>
              </div>
              <div className="relative flex justify-center text-sm">
                <span className="px-4 bg-white dark:bg-dark-900 text-gray-500 dark:text-gray-400">
                  Continue with
                </span>
              </div>
            </div>

            {/* Login Button */}
            <button
              onClick={handleLogin}
              onMouseEnter={() => setIsHovered(true)}
              onMouseLeave={() => setIsHovered(false)}
              className="w-full btn-primary py-4 text-base relative overflow-hidden group"
            >
              <div className="absolute inset-0 bg-gradient-to-r from-primary-700 to-purple-700 transform scale-x-0 group-hover:scale-x-100 transition-transform origin-left duration-300"></div>
              <div className="relative flex items-center justify-center gap-3">
                <LogIn className={`w-5 h-5 transition-transform duration-300 ${isHovered ? 'translate-x-1' : ''}`} />
                <span>Sign in with Google</span>
                <Rocket className={`w-5 h-5 transition-all duration-300 ${isHovered ? 'translate-x-2 opacity-100' : 'translate-x-0 opacity-0'}`} />
              </div>
            </button>

            {/* Security Badge */}
            <div className="flex items-center justify-center gap-2 pt-4">
              <Shield className="w-4 h-4 text-success-600 dark:text-success-400" />
              <span className="text-xs text-gray-600 dark:text-gray-400">
                Secured by <span className="font-semibold text-gray-900 dark:text-white">APAC Atlas Guard</span>
              </span>
            </div>
          </div>

          {/* Help Text */}
          <p className="text-center text-sm text-gray-600 dark:text-gray-400">
            By signing in, you agree to our{' '}
            <a href="#" className="text-primary-600 dark:text-primary-400 hover:underline">
              Terms of Service
            </a>{' '}
            and{' '}
            <a href="#" className="text-primary-600 dark:text-primary-400 hover:underline">
              Privacy Policy
            </a>
          </p>
        </div>
      </div>

      <style>{`
        @keyframes blob {
          0%, 100% { transform: translate(0px, 0px) scale(1); }
          33% { transform: translate(30px, -50px) scale(1.1); }
          66% { transform: translate(-20px, 20px) scale(0.9); }
        }
        .animate-blob {
          animation: blob 7s infinite;
        }
        .animation-delay-2000 {
          animation-delay: 2s;
        }
        .animation-delay-4000 {
          animation-delay: 4s;
        }
      `}</style>
    </div>
  )
}
