import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import apiClient from '../api/client'
import { MagnifyingGlassIcon, FunnelIcon } from '@heroicons/react/24/outline'

export default function Leads() {
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [projectFilter, setProjectFilter] = useState('ALL')

  const { data, isLoading } = useQuery({
    queryKey: ['leads-list', statusFilter, projectFilter],
    queryFn: async () => {
      let url = '/api/v1/leads/?limit=100'
      if (statusFilter !== 'ALL') url += `&status=${statusFilter}`
      if (projectFilter !== 'ALL') url += `&project=${projectFilter}`
      const res = await apiClient.get(url)
      return res.data.leads || []
    },
  })

  const filteredLeads = (data || []).filter((lead) => {
    if (!searchTerm) return true
    const term = searchTerm.toLowerCase()
    return (
      (lead.name && lead.name.toLowerCase().includes(term)) ||
      (lead.phone && lead.phone.includes(term)) ||
      (lead.phone_normalized && lead.phone_normalized.includes(term))
    )
  })

  const statusBadge = (status) => {
    const map = {
      NEW: 'bg-blue-100 text-blue-800',
      CONTACTED: 'bg-amber-100 text-amber-800',
      QUALIFIED: 'bg-emerald-100 text-emerald-800',
      LOST: 'bg-rose-100 text-rose-800',
      SITE_VISIT_BOOKED: 'bg-purple-100 text-purple-800',
    }
    return map[status] || 'bg-gray-100 text-gray-800'
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Customer Leads</h1>
        <p className="text-sm text-gray-500">Captured through website AI chatbot interactions</p>
      </div>

      {/* Filter and Search Bar */}
      <div className="card p-4 flex flex-col md:flex-row gap-4 justify-between items-center">
        <div className="relative w-full md:w-80">
          <MagnifyingGlassIcon className="w-5 h-5 text-gray-400 absolute left-3 top-2.5" />
          <input
            type="text"
            placeholder="Search by name or phone..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="input-field pl-10"
          />
        </div>

        <div className="flex flex-wrap items-center gap-3 w-full md:w-auto">
          <div className="flex items-center gap-2 text-xs font-semibold text-gray-600">
            <FunnelIcon className="w-4 h-4" /> Filters:
          </div>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="input-field py-1.5 text-xs w-36"
          >
            <option value="ALL">All Statuses</option>
            <option value="NEW">New</option>
            <option value="CONTACTED">Contacted</option>
            <option value="QUALIFIED">Qualified</option>
            <option value="LOST">Lost</option>
          </select>

          <select
            value={projectFilter}
            onChange={(e) => setProjectFilter(e.target.value)}
            className="input-field py-1.5 text-xs w-44"
          >
            <option value="ALL">All Projects</option>
            <option value="Samsara">Samsara</option>
            <option value="Pebbles Greenfield">Pebbles Greenfield</option>
            <option value="The Curve">The Curve</option>
            <option value="Aeromall">Aeromall</option>
          </select>
        </div>
      </div>

      {/* Leads Table */}
      <div className="card overflow-hidden p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-gray-50 text-gray-500 text-xs font-semibold uppercase tracking-wider border-b">
              <tr>
                <th className="py-3 px-4">Customer</th>
                <th className="py-3 px-4">Contact Phone</th>
                <th className="py-3 px-4">Project Interest</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Mdoc Sync</th>
                <th className="py-3 px-4">Captured At</th>
                <th className="py-3 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {isLoading ? (
                <tr>
                  <td colSpan="7" className="py-8 text-center text-gray-400">
                    Loading customer leads...
                  </td>
                </tr>
              ) : filteredLeads.length > 0 ? (
                filteredLeads.map((lead) => (
                  <tr key={lead.id} className="hover:bg-gray-50/60 transition-colors">
                    <td className="py-3.5 px-4">
                      <p className="font-semibold text-gray-900">{lead.name || 'Anonymous'}</p>
                      {lead.is_nri && (
                        <span className="badge bg-indigo-50 text-indigo-700 text-[10px] mt-0.5">NRI Buyer</span>
                      )}
                    </td>
                    <td className="py-3.5 px-4 font-mono text-xs text-gray-700">
                      {lead.phone_normalized || lead.phone}
                    </td>
                    <td className="py-3.5 px-4 text-gray-800">
                      <span className="font-medium">{lead.interested_project || 'General'}</span>
                      {lead.preferred_config && (
                        <span className="text-xs text-gray-400 ml-1.5">({lead.preferred_config})</span>
                      )}
                    </td>
                    <td className="py-3.5 px-4">
                      <span className={`badge ${statusBadge(lead.status)} text-[11px] font-semibold`}>
                        {lead.status || 'NEW'}
                      </span>
                    </td>
                    <td className="py-3.5 px-4">
                      <span className="text-xs text-gray-500 font-mono">
                        {lead.mdoc_sync_status || 'MOCK_PENDING'}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-xs text-gray-400">
                      {lead.created_at ? new Date(lead.created_at).toLocaleString() : 'Recent'}
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <Link
                        to={`/leads/${lead.id}`}
                        className="text-xs font-semibold text-primary hover:text-accent transition-colors"
                      >
                        Inspect →
                      </Link>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="7" className="py-12 text-center text-gray-400">
                    No leads found matching your criteria.
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
