import axios from 'axios'

const getApiBase = () => {
  if (import.meta.env.VITE_API_BASE) return import.meta.env.VITE_API_BASE
  if (typeof window !== 'undefined' && window.location.origin) {
    if (window.location.port === '5173') return 'http://localhost:8000'
    return window.location.origin
  }
  return 'http://localhost:8000'
}
const BASE_URL = getApiBase()
const TOKEN_KEY = 'abhinav_admin_token'

const apiClient = axios.create({
  baseURL: BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor — attach Bearer token
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem(TOKEN_KEY)
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error),
)

// Response interceptor — handle 401
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem(TOKEN_KEY)
      window.location.href = '/admin/login'
    }
    return Promise.reject(error)
  },
)

export default apiClient
