import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import type { UserContext } from '../types'

interface AuthContextType {
  user: UserContext | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (token: string, user: UserContext) => void
  logout: () => void
  updateUser: (user: UserContext) => void
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export const useAuth = () => {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

interface AuthProviderProps {
  children: ReactNode
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<UserContext | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    // Verify authentication on mount
    const verifyAuth = async () => {
      const token = localStorage.getItem('auth_token')
      const cachedUser = localStorage.getItem('user_context')
      
      console.log('🔐 Auth verification starting...', { 
        hasToken: !!token, 
        hasCachedUser: !!cachedUser 
      })
      
      if (!token) {
        console.log('❌ No token found, user not authenticated')
        setIsLoading(false)
        return
      }

      // ALWAYS verify with server first (don't trust cached data blindly)
      try {
        console.log('🔄 Calling /auth/me to verify token...')
        const ssoServiceUrl = import.meta.env.VITE_SSO_SERVICE_URL
        const response = await fetch(`${ssoServiceUrl}/auth/me`, {
          method: 'GET',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
          credentials: 'include',
        })

        if (!response.ok) {
          console.error('❌ /auth/me failed:', response.status, response.statusText)
          // Token is invalid, clear everything
          localStorage.removeItem('auth_token')
          localStorage.removeItem('user_context')
          setUser(null)
          setIsLoading(false)
          return
        }

        const data = await response.json()
        console.log('✅ /auth/me success:', data)
        
        // Update user context from server (handle both nested user object and flat structure)
        const userData = data.user || data
        const userContext: UserContext = {
          user_id: userData.user_id || userData.sub,
          email: userData.user_email || userData.email,
          name: userData.user_name || userData.name,
          picture: userData.user_picture || userData.picture,
          org_id: userData.org_id,
          org_name: userData.org_name,
          team_id: userData.team_id,
          team_name: userData.team_name,
          project_id: userData.project_id || null,
          project_name: userData.project_name,
          user_role: userData.global_role || userData.user_role || userData.role || 'member',
        }

        localStorage.setItem('user_context', JSON.stringify(userContext))
        setUser(userContext)
        setIsLoading(false)
      } catch (error) {
        console.error('❌ Auth verification error:', error)
        // On network error, try to use cached data as fallback
        if (cachedUser) {
          try {
            const parsedUser = JSON.parse(cachedUser)
            console.warn('⚠️ Using cached data due to network error')
            setUser(parsedUser)
          } catch (e) {
            console.error('❌ Failed to parse cached user data:', e)
            localStorage.removeItem('auth_token')
            localStorage.removeItem('user_context')
            setUser(null)
          }
        } else {
          // No cached data and network error, clear everything
          localStorage.removeItem('auth_token')
          localStorage.removeItem('user_context')
          setUser(null)
        }
        setIsLoading(false)
      }
    }

    verifyAuth()
  }, [])

  const login = (token: string, userData: UserContext) => {
    localStorage.setItem('auth_token', token)
    localStorage.setItem('user_context', JSON.stringify(userData))
    setUser(userData)
  }

  const logout = async () => {
    const token = localStorage.getItem('auth_token')
    
    // Clear local storage first
    localStorage.removeItem('auth_token')
    localStorage.removeItem('user_context')
    setUser(null)
    
    // Call SSO logout endpoint
    try {
      const ssoServiceUrl = import.meta.env.VITE_SSO_SERVICE_URL
      const redirectUri = `${window.location.origin}/login`
      
      await fetch(`${ssoServiceUrl}/auth/logout`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          redirect_uri: redirectUri
        }),
        credentials: 'include',
      })
    } catch (error) {
      console.error('Logout error:', error)
    }
    
    // Redirect to login page
    window.location.href = '/login'
  }

  const updateUser = (userData: UserContext) => {
    localStorage.setItem('user_context', JSON.stringify(userData))
    setUser(userData)
  }

  const value = {
    user,
    isAuthenticated: !!user,
    isLoading,
    login,
    logout,
    updateUser,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

