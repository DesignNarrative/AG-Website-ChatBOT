import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  PieChart,
  Pie,
  Cell,
  CartesianGrid,
} from 'recharts'

const PROJECT_INTEREST_DATA = [
  { name: 'Samsara', enquiries: 42 },
  { name: 'Pebbles Greenfield', enquiries: 58 },
  { name: 'The Curve (Virar)', enquiries: 31 },
  { name: 'Aeromall', enquiries: 19 },
]

const LANGUAGE_DATA = [
  { name: 'English', value: 72, color: '#1a2f5a' },
  { name: 'Hindi', value: 28, color: '#d4a017' },
]

const INTENT_DATA = [
  { intent: 'Project Info', count: 68 },
  { intent: 'Pricing', count: 45 },
  { intent: 'Configurations', count: 34 },
  { intent: 'Brochure Download', count: 26 },
  { intent: 'Sales Escalation', count: 18 },
  { intent: 'NRI Enquiries', count: 12 },
]

export default function Analytics() {
  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Chatbot Analytics</h1>
        <p className="text-sm text-gray-500">Visitor interaction trends and property interest metrics</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Project Enquiries Breakdown */}
        <div className="card space-y-4">
          <h2 className="font-bold text-gray-800 text-sm">Most Enquired Projects</h2>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={PROJECT_INTEREST_DATA}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f0f0f0" />
                <XAxis dataKey="name" stroke="#888888" fontSize={11} tickLine={false} />
                <YAxis stroke="#888888" fontSize={11} tickLine={false} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#fff',
                    borderRadius: '8px',
                    border: '1px solid #e5e7eb',
                    fontSize: '12px',
                  }}
                />
                <Bar dataKey="enquiries" fill="#1a2f5a" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Language Distribution */}
        <div className="card space-y-4">
          <h2 className="font-bold text-gray-800 text-sm">Language Distribution (EN vs HI)</h2>
          <div className="h-64 w-full flex items-center justify-center">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={LANGUAGE_DATA}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={85}
                  paddingAngle={5}
                  dataKey="value"
                >
                  {LANGUAGE_DATA.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#fff',
                    borderRadius: '8px',
                    border: '1px solid #e5e7eb',
                    fontSize: '12px',
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="flex justify-center gap-6 text-xs font-semibold">
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-full bg-primary inline-block"></span>
              <span>English (72%)</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-full bg-accent inline-block"></span>
              <span>Hindi (28%)</span>
            </div>
          </div>
        </div>
      </div>

      {/* Intents Distribution */}
      <div className="card space-y-4">
        <h2 className="font-bold text-gray-800 text-sm">Customer Query Intent Breakdown</h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          {INTENT_DATA.map((item, idx) => (
            <div key={idx} className="p-3 bg-gray-50 rounded-xl border border-gray-100 text-center">
              <p className="text-lg font-bold text-primary">{item.count}</p>
              <p className="text-[11px] text-gray-500 font-medium mt-0.5">{item.intent}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
