import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import apiClient from '../api/client'
import {
  UserGroupIcon,
  ChatBubbleLeftRightIcon,
  BuildingOffice2Icon,
  BookOpenIcon,
  ArrowTrendingUpIcon,
  PhoneArrowUpRightIcon,
} from '@heroicons/react/24/outline'

export default function Overview() {
  const { data: stats, isLoading } = useQuery({
    queryKey: ['admin-overview'],
    queryFn: async () => {
      const res = await apiClient.get('/api/v1/admin/overview')
      return res.data
    },
    refetchInterval: 30000,
  })

  const { data: recentLeads } = useQuery({
    queryKey: ['recent-leads'],
    queryFn: async () => {
      const res = await apiClient.get('/api/v1/leads/?limit=5')
      return res.data.leads || []
    },
  })

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Overview</h1>
        <p className="text-sm text-gray-500">Live operational snapshot of the website AI assistant</p>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        <div className="card border-l-4 border-l-primary flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Total Leads</p>
            <p className="text-2xl font-bold text-gray-900 mt-1">
              {isLoading ? '...' : stats?.total_leads ?? 0}
            </p>
            <span className="text-xs text-emerald-600 font-medium inline-flex items-center gap-1 mt-1">
              <ArrowTrendingUpIcon className="w-3.5 h-3.5" /> Direct enquiries
            </span>
          </div>
          <div className="w-12 h-12 rounded-xl bg-primary-50 text-primary flex items-center justify-center">
            <UserGroupIcon className="w-6 h-6" />
          </div>
        </div>

        <div className="card border-l-4 border-l-accent flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Conversations</p>
            <p className="text-2xl font-bold text-gray-900 mt-1">
              {isLoading ? '...' : stats?.total_conversations ?? 0}
            </p>
            <span className="text-xs text-gray-500 mt-1 inline-block">Sessions logged</span>
          </div>
          <div className="w-12 h-12 rounded-xl bg-accent-50 text-accent-800 flex items-center justify-center">
            <ChatBubbleLeftRightIcon className="w-6 h-6" />
          </div>
        </div>

        <div className="card border-l-4 border-l-emerald-600 flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Active Projects</p>
            <p className="text-2xl font-bold text-gray-900 mt-1">
              {isLoading ? '...' : stats?.active_projects ?? 4}
            </p>
            <span className="text-xs text-gray-500 mt-1 inline-block">Samsara, Pebbles, Curve, Aero</span>
          </div>
          <div className="w-12 h-12 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
            <BuildingOffice2Icon className="w-6 h-6" />
          </div>
        </div>

        <div className="card border-l-4 border-l-purple-600 flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Knowledge Base</p>
            <p className="text-2xl font-bold text-gray-900 mt-1">
              {isLoading ? '...' : stats?.knowledge_chunks ?? 120}
            </p>
            <span className="text-xs text-gray-500 mt-1 inline-block">Indexed RAG chunks</span>
          </div>
          <div className="w-12 h-12 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center">
            <BookOpenIcon className="w-6 h-6" />
          </div>
        </div>
      </div>

      {/* Quick Actions & Recent Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Leads */}
        <div className="card lg:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-bold text-gray-800">Recent Customer Leads</h2>
            <Link to="/leads" className="text-xs font-semibold text-primary hover:underline">
              View all leads →
            </Link>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-gray-50 text-gray-500 text-xs font-semibold uppercase tracking-wider border-b">
                <tr>
                  <th className="py-2.5 px-3">Name</th>
                  <th className="py-2.5 px-3">Phone</th>
                  <th className="py-2.5 px-3">Interested Project</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3">Date</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {recentLeads && recentLeads.length > 0 ? (
                  recentLeads.map((lead) => (
                    <tr key={lead.id} className="hover:bg-gray-50/50">
                      <td className="py-2.5 px-3 font-medium text-gray-900">{lead.name || 'Anonymous'}</td>
                      <td className="py-2.5 px-3 text-gray-600 font-mono text-xs">{lead.phone_normalized || lead.phone}</td>
                      <td className="py-2.5 px-3 text-gray-700">{lead.interested_project || 'General'}</td>
                      <td className="py-2.5 px-3">
                        <span className="badge bg-blue-100 text-blue-800 text-[11px] font-semibold">
                          {lead.status || 'NEW'}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-xs text-gray-400">
                        {lead.created_at ? new Date(lead.created_at).toLocaleDateString() : 'Today'}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan="5" className="py-6 text-center text-sm text-gray-400">
                      No leads recorded yet. New website enquiries will appear here.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* System & Property Status */}
        <div className="card space-y-4">
          <h2 className="font-bold text-gray-800">Projects In Scope</h2>
          <div className="space-y-3">
            <div className="p-3 bg-gray-50 rounded-lg border border-gray-100">
              <div className="flex justify-between items-start">
                <div>
                  <h3 className="font-semibold text-sm text-gray-900">Samsara</h3>
                  <p className="text-xs text-gray-500">Mukund Nagar, Pune • 3 BHK</p>
                </div>
                <span className="badge bg-emerald-100 text-emerald-800 text-[10px]">Verified</span>
              </div>
            </div>

            <div className="p-3 bg-gray-50 rounded-lg border border-gray-100">
              <div className="flex justify-between items-start">
                <div>
                  <h3 className="font-semibold text-sm text-gray-900">Pebbles Greenfield</h3>
                  <p className="text-xs text-gray-500">Tathawade/Wakad, Pune • 2 & 3 BHK</p>
                </div>
                <span className="badge bg-emerald-100 text-emerald-800 text-[10px]">Verified</span>
              </div>
            </div>

            <div className="p-3 bg-gray-50 rounded-lg border border-gray-100">
              <div className="flex justify-between items-start">
                <div>
                  <h3 className="font-semibold text-sm text-gray-900">The Curve</h3>
                  <p className="text-xs text-gray-500">Virar West, Mumbai • 2 & 3 BHK</p>
                </div>
                <span className="badge bg-emerald-100 text-emerald-800 text-[10px]">Verified</span>
              </div>
            </div>

            <div className="p-3 bg-gray-50 rounded-lg border border-gray-100">
              <div className="flex justify-between items-start">
                <div>
                  <h3 className="font-semibold text-sm text-gray-900">Aeromall</h3>
                  <p className="text-xs text-gray-500">Airport Road, Lohegaon, Pune • Commercial</p>
                </div>
                <span className="badge bg-emerald-100 text-emerald-800 text-[10px]">Verified</span>
              </div>
            </div>
          </div>

          <div className="p-3 bg-amber-50 rounded-lg border border-amber-200 text-xs text-amber-800 flex items-center gap-2">
            <PhoneArrowUpRightIcon className="w-5 h-5 flex-shrink-0 text-amber-600" />
            <span>Sales Escalation: <strong>+91 9309505388</strong></span>
          </div>
        </div>
      </div>
    </div>
  )
}
