import { useEffect, useState, useRef } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { Loader2, AlertCircle } from 'lucide-react'

export const CallbackPage = () => {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { login } = useAuth()
  const [error, setError] = useState<string | null>(null)
  const hasRun = useRef(false)

  useEffect(() => {
    // Prevent double execution in React StrictMode
    if (hasRun.current) return
    hasRun.current = true

    const handleCallback = async () => {
      try {
        // Get authorization code from URL (standard OAuth 2.0 flow)
        const code = searchParams.get('code')
        const errorParam = searchParams.get('error')

        if (errorParam) {
          setError(`Authentication failed: ${errorParam}`)
          return
        }

        if (!code) {
          setError('No authorization code received')
          return
        }

        // Exchange code for token with Auth Guard
        const ssoServiceUrl = import.meta.env.VITE_SSO_SERVICE_URL
        const redirectUri = import.meta.env.VITE_REDIRECT_URI || `${window.location.origin}/auth/callback`
        
        const response = await fetch(`${ssoServiceUrl}/auth/callback`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          credentials: 'include', // Include cookies
          body: JSON.stringify({ 
            code,
            redirect_uri: redirectUri
          }),
        })

        if (!response.ok) {
          throw new Error('Failed to exchange authorization code')
        }

        const data = await response.json()
        
        console.log('📦 Callback response:', data)
        
        // Auth Guard returns user data and token
        const token = data.token || data.access_token
        
        if (!token) {
          throw new Error('No token received from Auth Guard')
        }

        // Extract user context from response (data.user object)
        const userData = data.user || data
        
        // Handle picture from different possible locations
        let picture = userData.user_picture || userData.picture
        if (!picture && data['https://atlas.turing.com/user_picture']) {
          picture = data['https://atlas.turing.com/user_picture']
        }
        
        const userContext = {
          user_id: userData.user_id || userData.sub,
          email: userData.user_email || userData.email,
          name: userData.user_name || userData.name,
          picture: picture,
          org_id: userData.org_id,
          org_name: userData.org_name,
          team_id: userData.team_id,
          team_name: userData.team_name,
          project_id: userData.project_id || null,
          project_name: userData.project_name,
          user_role: userData.global_role || userData.user_role || userData.role || 'member',
        }
        
        console.log('✅ Extracted user context:', userContext)

        // Store auth data
        login(token, userContext)

        // Redirect to dashboard
        navigate('/', { replace: true })
      } catch (err) {
        console.error('Callback error:', err)
        setError(err instanceof Error ? err.message : 'Authentication failed. Please try again.')
      }
    }

    handleCallback()
  }, [searchParams, login, navigate])

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary-500 to-purple-600 px-4">
        <div className="max-w-md w-full bg-white rounded-2xl shadow-xl p-8">
          <div className="text-center">
            <AlertCircle className="w-12 h-12 text-error-500 mx-auto mb-4" />
            <h2 className="text-2xl font-semibold text-gray-800 mb-2">
              Authentication Error
            </h2>
            <p className="text-gray-600 mb-6">{error}</p>
            <button
              onClick={() => navigate('/login')}
              className="btn-primary"
            >
              Back to Login
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary-500 to-purple-600">
      <div className="text-center">
        <Loader2 className="w-12 h-12 text-white animate-spin mx-auto mb-4" />
        <p className="text-white text-lg">Completing authentication...</p>
      </div>
    </div>
  )
}

