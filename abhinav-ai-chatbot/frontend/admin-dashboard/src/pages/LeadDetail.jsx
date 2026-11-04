import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import apiClient from '../api/client'
import toast from 'react-hot-toast'
import { ArrowLeftIcon, PhoneIcon, CheckCircleIcon } from '@heroicons/react/24/outline'

export default function LeadDetail() {
  const { id } = useParams()
  const queryClient = useQueryClient()
  const [newNote, setNewNote] = useState('')

  const { data: lead, isLoading } = useQuery({
    queryKey: ['lead-detail', id],
    queryFn: async () => {
      const res = await apiClient.get(`/api/v1/leads/${id}`)
      return res.data
    },
  })

  const updateStatusMutation = useMutation({
    mutationFn: async (newStatus) => {
      await apiClient.patch(`/api/v1/leads/${id}`, { status: newStatus })
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['lead-detail', id])
      toast.success('Lead status updated')
    },
    onError: () => toast.error('Failed to update status'),
  })

  const addNoteMutation = useMutation({
    mutationFn: async (note) => {
      await apiClient.post(`/api/v1/leads/${id}/notes`, { note })
    },
    onSuccess: () => {
      setNewNote('')
      queryClient.invalidateQueries(['lead-detail', id])
      toast.success('Note added')
    },
    onError: () => toast.error('Failed to add note'),
  })

  if (isLoading) {
    return (
      <div className="py-12 text-center text-gray-400">
        <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-2"></div>
        Loading lead dossier...
      </div>
    )
  }

  if (!lead) {
    return (
      <div className="card p-8 text-center max-w-lg mx-auto">
        <h2 className="text-lg font-bold text-gray-800">Lead Not Found</h2>
        <p className="text-sm text-gray-500 mt-2 mb-4">No lead matches ID #{id}</p>
        <Link to="/leads" className="btn-primary text-xs">
          Back to Leads
        </Link>
      </div>
    )
  }

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <Link to="/leads" className="inline-flex items-center gap-1.5 text-xs font-semibold text-primary hover:underline">
        <ArrowLeftIcon className="w-3.5 h-3.5" /> Back to Leads list
      </Link>

      {/* Header Profile Card */}
      <div className="card p-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-white border border-gray-100">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-gray-900">{lead.name || 'Anonymous Visitor'}</h1>
            {lead.is_nri && <span className="badge bg-indigo-100 text-indigo-800 text-xs">NRI</span>}
          </div>
          <p className="text-sm text-gray-500 font-mono mt-0.5">
            Phone: <strong>{lead.phone_normalized || lead.phone}</strong>
          </p>
        </div>

        <div className="flex items-center gap-3">
          <label className="text-xs font-semibold text-gray-500">Status:</label>
          <select
            value={lead.status || 'NEW'}
            onChange={(e) => updateStatusMutation.mutate(e.target.value)}
            disabled={updateStatusMutation.isPending}
            className="input-field py-1.5 text-xs w-40 font-semibold"
          >
            <option value="NEW">NEW</option>
            <option value="CONTACTED">CONTACTED</option>
            <option value="QUALIFIED">QUALIFIED</option>
            <option value="LOST">LOST</option>
          </select>
        </div>
      </div>

      {/* Details Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Enquiry Attributes */}
        <div className="card space-y-4">
          <h2 className="font-bold text-gray-800 text-sm uppercase tracking-wider">Property Interest Profile</h2>
          <dl className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <dt className="text-xs text-gray-400">Target Project</dt>
              <dd className="font-semibold text-gray-800">{lead.interested_project || 'General Inquiry'}</dd>
            </div>
            <div>
              <dt className="text-xs text-gray-400">Preferred Configuration</dt>
              <dd className="font-semibold text-gray-800">{lead.preferred_config || 'Not specified'}</dd>
            </div>
            <div>
              <dt className="text-xs text-gray-400">Budget Range</dt>
              <dd className="font-semibold text-gray-800">
                {lead.budget_min || lead.budget_max ? `₹${lead.budget_min || '—'} - ₹${lead.budget_max || '—'}` : 'Not specified'}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-gray-400">Preferred Location</dt>
              <dd className="font-semibold text-gray-800">{lead.preferred_location || 'Pune'}</dd>
            </div>
            <div>
              <dt className="text-xs text-gray-400">Source Page</dt>
              <dd className="text-xs text-gray-600 truncate">{lead.source_page || 'Website Homepage'}</dd>
            </div>
            <div>
              <dt className="text-xs text-gray-400">Consent Given</dt>
              <dd className="text-xs font-semibold text-emerald-600 flex items-center gap-1">
                <CheckCircleIcon className="w-4 h-4" /> Opted-in for contact
              </dd>
            </div>
          </dl>
        </div>

        {/* Mdoc CRM Sync Status */}
        <div className="card space-y-4">
          <h2 className="font-bold text-gray-800 text-sm uppercase tracking-wider">CRM Integration (Mdoc)</h2>
          <div className="p-3 bg-gray-50 rounded-lg border border-gray-100 text-xs space-y-2">
            <div className="flex justify-between">
              <span className="text-gray-500">Mdoc Status:</span>
              <span className="font-mono font-semibold text-amber-700">{lead.mdoc_sync_status || 'MOCK_PENDING'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">Mdoc ID:</span>
              <span className="font-mono text-gray-600">{lead.mdoc_lead_id || 'Not assigned (mock mode)'}</span>
            </div>
            <p className="text-[11px] text-gray-400 pt-1 border-t border-gray-200">
              Real sync is on standby until official Mdoc credentials and API documentation are provided.
            </p>
          </div>
        </div>
      </div>

      {/* Staff Notes */}
      <div className="card space-y-4">
        <h2 className="font-bold text-gray-800 text-sm uppercase tracking-wider">Sales Follow-up Notes</h2>
        <form
          onSubmit={(e) => {
            e.preventDefault()
            if (newNote.trim()) addNoteMutation.mutate(newNote.trim())
          }}
          className="flex gap-3"
        >
          <input
            type="text"
            placeholder="Add follow-up notes (e.g. called customer, requested brochure for Samsara 3 BHK)..."
            value={newNote}
            onChange={(e) => setNewNote(e.target.value)}
            className="input-field flex-1 text-sm"
          />
          <button type="submit" disabled={addNoteMutation.isPending} className="btn-primary text-xs px-4">
            Add Note
          </button>
        </form>

        <div className="space-y-2 pt-2">
          {lead.notes && lead.notes.length > 0 ? (
            lead.notes.map((n, idx) => (
              <div key={idx} className="p-3 bg-gray-50 rounded-lg text-xs text-gray-700 border border-gray-100">
                <p className="font-medium">{n.note || n}</p>
                <span className="text-[10px] text-gray-400 mt-1 block">
                  {n.created_at ? new Date(n.created_at).toLocaleString() : 'Recent'}
                </span>
              </div>
            ))
          ) : (
            <p className="text-xs text-gray-400 italic">No notes added yet.</p>
          )}
        </div>
      </div>
    </div>
  )
}
