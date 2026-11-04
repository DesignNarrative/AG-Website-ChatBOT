import { useQuery } from '@tanstack/react-query'
import apiClient from '../api/client'
import {
  ServerStackIcon,
  CpuChipIcon,
  CircleStackIcon,
  CommandLineIcon,
  ShieldCheckIcon,
} from '@heroicons/react/24/outline'

export default function Settings() {
  const { data: health } = useQuery({
    queryKey: ['system-health'],
    queryFn: async () => {
      const res = await apiClient.get('/health')
      return res.data
    },
  })

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 tracking-tight">System Settings & Health</h1>
        <p className="text-sm text-gray-500">Service configurations, AI providers, and connectivity status</p>
      </div>

      {/* Connectivity & Health Status */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        <div className="card space-y-2 border-l-4 border-l-emerald-500">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-gray-500">
            <ServerStackIcon className="w-4 h-4 text-emerald-600" /> API Gateway
          </div>
          <p className="text-xl font-bold text-gray-900">{health?.status || 'HEALTHY'}</p>
          <p className="text-xs text-gray-400">FastAPI ASGI Server</p>
        </div>

        <div className="card space-y-2 border-l-4 border-l-primary">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-gray-500">
            <CpuChipIcon className="w-4 h-4 text-primary" /> Active AI Provider
          </div>
          <p className="text-xl font-bold text-primary uppercase">{health?.ai_provider || 'MOCK'}</p>
          <p className="text-xs text-gray-400">Configurable to Gemini / OpenAI</p>
        </div>

        <div className="card space-y-2 border-l-4 border-l-accent">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-gray-500">
            <CircleStackIcon className="w-4 h-4 text-accent-700" /> Database Connection
          </div>
          <p className="text-xl font-bold text-accent-800">{health?.database || 'CONNECTED'}</p>
          <p className="text-xs text-gray-400">SQLite (dev) / PostgreSQL (prod)</p>
        </div>
      </div>

      {/* WordPress Widget Embed Code */}
      <div className="card space-y-4">
        <div className="flex items-center gap-2 font-bold text-gray-800 text-sm">
          <CommandLineIcon className="w-5 h-5 text-primary" />
          <span>Website Widget Embed Snippet</span>
        </div>
        <p className="text-xs text-gray-500">
          This script should be included in the header or footer of the WordPress site. (Or use the official Abhinav Chatbot WP plugin).
        </p>

        <div className="bg-gray-900 text-gray-100 p-4 rounded-xl font-mono text-xs overflow-x-auto leading-relaxed">
{`<!-- Abhinav Group AI Chatbot -->
<script>
  window.AbhinavChatConfig = {
    apiBase: "${import.meta.env.VITE_API_BASE || 'http://localhost:8000'}",
    widgetKey: "public-widget-key",
    position: "bottom-right",
    lang: "auto"
  };
</script>
<script src="${import.meta.env.VITE_API_BASE || 'http://localhost:8000'}/static/abhinav-chatbot.min.js" async></script>`}
        </div>
      </div>

      {/* Safety & Scope Rules */}
      <div className="card space-y-4">
        <div className="flex items-center gap-2 font-bold text-gray-800 text-sm">
          <ShieldCheckIcon className="w-5 h-5 text-emerald-600" />
          <span>Active Guardrails & Business Policies</span>
        </div>
        <ul className="text-xs text-gray-600 space-y-2.5 list-disc pl-5">
          <li><strong>Domain restriction:</strong> Property and sales queries only (English & Hindi).</li>
          <li><strong>Out-of-scope redirection:</strong> Career/HR/job, vendor, contractor, and supplier requests are politely redirected to official company contacts without calling LLMs.</li>
          <li><strong>Unverified prices:</strong> Always designated as &quot;Price on Request / Contact Sales&quot; to prevent hallucinated quotes.</li>
          <li><strong>Mdoc CRM:</strong> Runs in non-blocking mock queue until production credentials are supplied.</li>
        </ul>
      </div>
    </div>
  )
}
