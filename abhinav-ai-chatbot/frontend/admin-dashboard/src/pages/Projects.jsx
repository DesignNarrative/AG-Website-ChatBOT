import { useQuery } from '@tanstack/react-query'
import apiClient from '../api/client'
import { BuildingOfficeIcon, MapPinIcon, CheckBadgeIcon, ExclamationTriangleIcon } from '@heroicons/react/24/outline'

const KNOWN_PROJECTS_FALLBACK = [
  {
    name: 'Samsara',
    type: 'Residential (Luxury)',
    location: 'Mukund Nagar, Pune',
    configurations: '3 BHK Luxury Residences',
    rera: 'P52100079797 (Unverified)',
    status: 'ACTIVE',
    possession: 'Enquire for updates',
    price_status: 'Contact Sales (+91 9309505388)',
  },
  {
    name: 'Pebbles Greenfield',
    type: 'Residential',
    location: 'Tathawade / Wakad, Pune',
    configurations: '2 & 3 BHK Premium Apartments',
    rera: 'P52100045923 (Unverified)',
    status: 'ACTIVE',
    possession: 'Ongoing',
    price_status: 'On Request',
  },
  {
    name: 'The Curve',
    type: 'Residential',
    location: 'Virar West, Mumbai MMR',
    configurations: '2 & 3 BHK Apartments',
    rera: 'PR1240002600667 (Unverified)',
    status: 'ACTIVE',
    possession: 'June 2031 (As per website)',
    price_status: 'Price on Request',
  },
  {
    name: 'Aeromall',
    type: 'Commercial',
    location: 'Airport Road, Lohegaon, Pune',
    configurations: 'Retail & Commercial Multi-facility',
    rera: 'Commercial Facility',
    status: 'ACTIVE',
    possession: 'Operational (Pune\'s 1st 24x7 Mall)',
    price_status: 'Leasing Enquiries',
  },
]

export default function Projects() {
  const { data: apiProjects } = useQuery({
    queryKey: ['projects-list'],
    queryFn: async () => {
      const res = await apiClient.get('/api/v1/projects/')
      return res.data.projects || []
    },
  })

  const projects = (apiProjects && apiProjects.length > 0) ? apiProjects : KNOWN_PROJECTS_FALLBACK

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Approved Projects</h1>
        <p className="text-sm text-gray-500">Official Abhinav Group property portfolio indexed by the AI</p>
      </div>

      <div className="p-4 bg-amber-50 border border-amber-200 rounded-xl flex items-start gap-3 text-xs text-amber-800">
        <ExclamationTriangleIcon className="w-5 h-5 flex-shrink-0 text-amber-600 mt-0.5" />
        <div>
          <p className="font-semibold">Verification & RERA Notice:</p>
          <p className="mt-0.5 leading-relaxed">
            All prices are strictly designated as &quot;Price on Request / Contact Sales&quot; to prevent the chatbot from making
            unauthorized financial commitments. RERA numbers are flagged for buyer verification on maharerait.maharashtra.gov.in.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {projects.map((proj, idx) => (
          <div key={idx} className="card p-6 space-y-4 hover:shadow-md transition-shadow">
            <div className="flex justify-between items-start">
              <div className="flex items-center gap-2.5">
                <div className="w-10 h-10 rounded-lg bg-primary-50 text-primary flex items-center justify-center font-bold">
                  <BuildingOfficeIcon className="w-5 h-5" />
                </div>
                <div>
                  <h2 className="font-bold text-lg text-gray-900">{proj.name || proj.project_name}</h2>
                  <p className="text-xs text-gray-500 font-medium">{proj.type || proj.project_type}</p>
                </div>
              </div>
              <span className="badge bg-emerald-100 text-emerald-800 text-xs font-semibold">
                {proj.status || 'ACTIVE'}
              </span>
            </div>

            <dl className="grid grid-cols-2 gap-3 text-xs pt-2 border-t border-gray-100">
              <div>
                <dt className="text-gray-400">Location</dt>
                <dd className="font-medium text-gray-800 flex items-center gap-1 mt-0.5">
                  <MapPinIcon className="w-3.5 h-3.5 text-gray-400" />
                  {proj.location}
                </dd>
              </div>

              <div>
                <dt className="text-gray-400">Configurations</dt>
                <dd className="font-medium text-gray-800 mt-0.5">{proj.configurations || '2 & 3 BHK'}</dd>
              </div>

              <div>
                <dt className="text-gray-400">RERA Registration</dt>
                <dd className="font-mono text-gray-700 mt-0.5 text-[11px]">{proj.rera || 'P521000...'}</dd>
              </div>

              <div>
                <dt className="text-gray-400">Pricing Policy</dt>
                <dd className="font-semibold text-primary mt-0.5">{proj.price_status || 'On Request'}</dd>
              </div>
            </dl>
          </div>
        ))}
      </div>
    </div>
  )
}
