import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import apiClient from '../api/client'
import toast from 'react-hot-toast'

const AuthContext = createContext(null)

const TOKEN_KEY = 'abhinav_admin_token'

function decodeJwt(token) {
  try {
    const base64Url = token.split('.')[1]
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/')
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    )
    return JSON.parse(jsonPayload)
  } catch {
    return null
  }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  const decodeAndSetUser = useCallback((token) => {
    try {
      const decoded = decodeJwt(token)
      if (!decoded) {
        localStorage.removeItem(TOKEN_KEY)
        setUser(null)
        return false
      }
      // Check expiry
      if (decoded.exp && decoded.exp * 1000 < Date.now()) {
        localStorage.removeItem(TOKEN_KEY)
        setUser(null)
        return false
      }
      setUser({
        username: decoded.sub || decoded.username || decoded.email || 'Admin',
        role: decoded.role || 'viewer',
        exp: decoded.exp,
      })
      return true
    } catch {
      localStorage.removeItem(TOKEN_KEY)
      setUser(null)
      return false
    }
  }, [])

  useEffect(() => {
    const token = localStorage.getItem(TOKEN_KEY)
    if (token) {
      decodeAndSetUser(token)
    }
    setLoading(false)
  }, [decodeAndSetUser])

  const login = async (username, password) => {
    const formData = new URLSearchParams()
    formData.append('username', username)
    formData.append('password', password)

    const response = await apiClient.post('/api/v1/auth/login', formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    })

    const { access_token } = response.data
    localStorage.setItem(TOKEN_KEY, access_token)
    decodeAndSetUser(access_token)
    toast.success('Logged in successfully')
    return response.data
  }

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY)
    setUser(null)
    toast.success('Logged out')
  }, [])

  const isAdmin = user?.role === 'admin' || user?.role === 'developer'
  const isDeveloper = user?.role === 'developer'
  const isAuthenticated = !!user

  return (
    <AuthContext.Provider
      value={{ user, loading, login, logout, isAdmin, isDeveloper, isAuthenticated }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
