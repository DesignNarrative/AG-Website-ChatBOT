import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

export default function ProtectedRoute({ children, requiredRole }) {
  const { isAuthenticated, loading, user } = useAuth()
  const location = useLocation()

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin"></div>
          <p className="text-sm text-gray-500 font-medium">Verifying session...</p>
        </div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  if (requiredRole) {
    const roleHierarchy = { staff: 1, admin: 2, developer: 3 }
    const userLevel = roleHierarchy[user?.role] || 0
    const reqLevel = roleHierarchy[requiredRole] || 0
    if (userLevel < reqLevel) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-gray-50 p-6">
          <div className="card max-w-md text-center p-8">
            <h2 className="text-xl font-bold text-gray-800 mb-2">Access Restricted</h2>
            <p className="text-gray-600 mb-4 text-sm">
              You need <strong>{requiredRole}</strong> permissions to access this page. Your role is{' '}
              <strong>{user?.role}</strong>.
            </p>
            <a href="/dashboard" className="btn-primary inline-block text-sm">
              Back to Dashboard
            </a>
          </div>
        </div>
      )
    }
  }

  return children
}
