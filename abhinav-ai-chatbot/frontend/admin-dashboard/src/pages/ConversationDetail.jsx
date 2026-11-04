import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import apiClient from '../api/client'
import { ArrowLeftIcon, UserIcon, CpuChipIcon } from '@heroicons/react/24/outline'

export default function ConversationDetail() {
  const { token } = useParams()

  const { data, isLoading } = useQuery({
    queryKey: ['conversation-detail', token],
    queryFn: async () => {
      const res = await apiClient.get(`/api/v1/chat/history/${token}`)
      return res.data
    },
  })

  const messages = data?.messages || []

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <Link to="/conversations" className="inline-flex items-center gap-1.5 text-xs font-semibold text-primary hover:underline">
        <ArrowLeftIcon className="w-3.5 h-3.5" /> Back to Conversations
      </Link>

      <div className="card p-5 flex justify-between items-center bg-white border border-gray-100">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Session Transcript</h1>
          <p className="text-xs text-gray-500 font-mono mt-0.5">Session: {token}</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="badge bg-blue-100 text-blue-800 text-xs">
            Language: {data?.language?.toUpperCase() || 'EN'}
          </span>
          <span className="badge bg-gray-100 text-gray-800 text-xs">
            {messages.length} messages
          </span>
        </div>
      </div>

      {/* Chat Thread */}
      <div className="card p-6 space-y-4 bg-gray-50/50 min-h-[400px]">
        {isLoading ? (
          <div className="py-12 text-center text-gray-400">Loading conversation history...</div>
        ) : messages.length > 0 ? (
          messages.map((m, idx) => {
            const isUser = m.role === 'user'
            return (
              <div
                key={idx}
                className={`flex gap-3 max-w-[85%] ${isUser ? 'ml-auto flex-row-reverse' : 'mr-auto'}`}
              >
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 text-xs ${
                    isUser ? 'bg-accent text-white' : 'bg-primary text-white'
                  }`}
                >
                  {isUser ? <UserIcon className="w-4 h-4" /> : <CpuChipIcon className="w-4 h-4" />}
                </div>

                <div
                  className={`p-4 rounded-2xl text-sm leading-relaxed shadow-sm ${
                    isUser
                      ? 'bg-primary text-white rounded-tr-none'
                      : 'bg-white text-gray-800 border border-gray-100 rounded-tl-none whitespace-pre-wrap'
                  }`}
                >
                  <p>{m.content}</p>
                  <div
                    className={`mt-1.5 text-[10px] flex items-center gap-2 ${
                      isUser ? 'text-primary-200 justify-end' : 'text-gray-400'
                    }`}
                  >
                    <span>{m.created_at ? new Date(m.created_at).toLocaleTimeString() : 'Delivered'}</span>
                    {m.intent && (
                      <span className="font-mono bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded">
                        {m.intent}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            )
          })
        ) : (
          <div className="py-12 text-center text-gray-400">No messages found in this session.</div>
        )}
      </div>
    </div>
  )
}
