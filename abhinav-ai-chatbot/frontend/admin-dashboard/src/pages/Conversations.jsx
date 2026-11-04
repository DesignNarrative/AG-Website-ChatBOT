import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import apiClient from '../api/client'
import { ChatBubbleLeftRightIcon, LanguageIcon } from '@heroicons/react/24/outline'

export default function Conversations() {
  const [langFilter, setLangFilter] = useState('ALL')

  const { data: conversations, isLoading } = useQuery({
    queryKey: ['conversations-list', langFilter],
    queryFn: async () => {
      let url = '/api/v1/admin/conversations?limit=100'
      if (langFilter !== 'ALL') url += `&language=${langFilter}`
      const res = await apiClient.get(url)
      return res.data.conversations || []
    },
  })

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Conversations</h1>
          <p className="text-sm text-gray-500">Live chat session logs between visitors and the AI assistant</p>
        </div>

        <div className="flex items-center gap-2">
          <LanguageIcon className="w-4 h-4 text-gray-500" />
          <select
            value={langFilter}
            onChange={(e) => setLangFilter(e.target.value)}
            className="input-field py-1.5 text-xs w-36"
          >
            <option value="ALL">All Languages</option>
            <option value="en">English (EN)</option>
            <option value="hi">Hindi (HI)</option>
          </select>
        </div>
      </div>

      <div className="card overflow-hidden p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-gray-50 text-gray-500 text-xs font-semibold uppercase tracking-wider border-b">
              <tr>
                <th className="py-3 px-4">Session Token</th>
                <th className="py-3 px-4">Language</th>
                <th className="py-3 px-4">Messages</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Escalated</th>
                <th className="py-3 px-4">Last Activity</th>
                <th className="py-3 px-4 text-right">Transcript</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {isLoading ? (
                <tr>
                  <td colSpan="7" className="py-8 text-center text-gray-400">
                    Loading conversations...
                  </td>
                </tr>
              ) : conversations && conversations.length > 0 ? (
                conversations.map((conv) => (
                  <tr key={conv.id || conv.session_token} className="hover:bg-gray-50/60">
                    <td className="py-3.5 px-4 font-mono text-xs text-primary font-medium">
                      {(conv.session_token || '').slice(0, 16)}...
                    </td>
                    <td className="py-3.5 px-4 uppercase text-xs font-semibold">
                      <span className={`badge ${conv.language === 'hi' ? 'bg-orange-100 text-orange-800' : 'bg-blue-100 text-blue-800'}`}>
                        {conv.language || 'EN'}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-gray-700 font-semibold text-xs">
                      {conv.message_count ?? '—'}
                    </td>
                    <td className="py-3.5 px-4">
                      <span className="badge bg-emerald-100 text-emerald-800 text-[11px]">
                        {conv.status || 'ACTIVE'}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-xs">
                      {conv.is_escalated ? (
                        <span className="text-amber-600 font-semibold">Yes (Sales)</span>
                      ) : (
                        <span className="text-gray-400">No</span>
                      )}
                    </td>
                    <td className="py-3.5 px-4 text-xs text-gray-400">
                      {conv.last_message_at ? new Date(conv.last_message_at).toLocaleTimeString() : 'Recently'}
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <Link
                        to={`/conversations/${conv.session_token}`}
                        className="text-xs font-semibold text-primary hover:text-accent transition-colors"
                      >
                        View Chat →
                      </Link>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="7" className="py-12 text-center text-gray-400">
                    No conversation transcripts available.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
