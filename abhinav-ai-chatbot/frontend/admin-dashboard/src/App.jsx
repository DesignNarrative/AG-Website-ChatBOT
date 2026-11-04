import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'
import Layout from './components/Layout'

import Login from './pages/Login'
import Overview from './pages/Overview'
import Leads from './pages/Leads'
import LeadDetail from './pages/LeadDetail'
import Conversations from './pages/Conversations'
import ConversationDetail from './pages/ConversationDetail'
import Projects from './pages/Projects'
import Knowledge from './pages/Knowledge'
import Analytics from './pages/Analytics'
import Settings from './pages/Settings'

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public login */}
          <Route path="/login" element={<Login />} />

          {/* Authenticated routes wrapped in Layout */}
          <Route
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route path="/dashboard" element={<Overview />} />
            <Route path="/leads" element={<Leads />} />
            <Route path="/leads/:id" element={<LeadDetail />} />
            <Route path="/conversations" element={<Conversations />} />
            <Route path="/conversations/:token" element={<ConversationDetail />} />
            <Route path="/projects" element={<Projects />} />
            <Route
              path="/knowledge"
              element={
                <ProtectedRoute requiredRole="developer">
                  <Knowledge />
                </ProtectedRoute>
              }
            />
            <Route path="/analytics" element={<Analytics />} />
            <Route
              path="/settings"
              element={
                <ProtectedRoute requiredRole="admin">
                  <Settings />
                </ProtectedRoute>
              }
            />
          </Route>

          {/* Default redirect */}
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
