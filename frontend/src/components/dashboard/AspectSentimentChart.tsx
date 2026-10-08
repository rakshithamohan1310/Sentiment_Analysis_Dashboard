import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts'
import { Card, CardHeader } from '@/components/common/Card'
import type { AspectSentimentRow } from '@/types'

const COLORS = {
  positive: '#10b981',
  neutral:  '#cbd5e1',
  negative: '#f87171',
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null
  const pos = payload.find((p: any) => p.dataKey === 'positive')?.value ?? 0
  const neu = payload.find((p: any) => p.dataKey === 'neutral')?.value ?? 0
  const neg = payload.find((p: any) => p.dataKey === 'negative')?.value ?? 0
  const total = pos + neu + neg || 1
  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-lg p-3 text-xs min-w-[140px]">
      <p className="font-semibold text-gray-700 mb-2">{label}</p>
      {[
        { key: 'Positive', val: pos, color: COLORS.positive },
        { key: 'Neutral',  val: neu, color: COLORS.neutral   },
        { key: 'Negative', val: neg, color: COLORS.negative  },
      ].map(r => (
        <div key={r.key} className="flex items-center justify-between gap-3 mb-0.5">
          <span className="flex items-center gap-1.5 text-gray-600">
            <span className="w-2 h-2 rounded-sm inline-block" style={{ background: r.color }} />
            {r.key}
          </span>
          <span className="font-semibold text-gray-900">{r.val}%</span>
        </div>
      ))}
      <div className="mt-2 pt-2 border-t border-gray-100 text-gray-500">
        Net: <span className={pos > neg ? 'text-emerald-600 font-semibold' : 'text-red-500 font-semibold'}>
          {pos > neg ? '+' : ''}{pos - neg}pp
        </span>
      </div>
    </div>
  )
}

interface AspectSentimentChartProps {
  data: AspectSentimentRow[]
}

export function AspectSentimentChart({ data }: AspectSentimentChartProps) {
  return (
    <Card>
      <CardHeader
        title="Sentiment by Aspect"
        subtitle="Positive / neutral / negative distribution per category"
      />
      <div className="h-52">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 0, right: 8, left: 0, bottom: 0 }}
            barSize={10}
          >
            <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f1f5f9" />
            <XAxis
              type="number"
              domain={[0, 100]}
              tick={{ fontSize: 10, fill: '#94a3b8' }}
              axisLine={false}
              tickLine={false}
              tickFormatter={v => `${v}%`}
            />
            <YAxis
              type="category"
              dataKey="aspect"
              tick={{ fontSize: 11, fill: '#64748b', fontWeight: 500 }}
              axisLine={false}
              tickLine={false}
              width={72}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: '#f8fafc' }} />
            <Bar dataKey="positive" stackId="a" fill={COLORS.positive} radius={[0, 0, 0, 0]} />
            <Bar dataKey="neutral"  stackId="a" fill={COLORS.neutral}   />
            <Bar dataKey="negative" stackId="a" fill={COLORS.negative}  radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 mt-2 justify-end">
        {[
          { label: 'Positive', color: COLORS.positive },
          { label: 'Neutral',  color: COLORS.neutral   },
          { label: 'Negative', color: COLORS.negative  },
        ].map(l => (
          <div key={l.label} className="flex items-center gap-1 text-xs text-gray-500">
            <span className="w-2.5 h-2.5 rounded-sm" style={{ background: l.color }} />
            {l.label}
          </div>
        ))}
      </div>
    </Card>
  )
}
