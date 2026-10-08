import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts'
import { Card, CardHeader } from '@/components/common/Card'
import { TrendBadge } from '@/components/common/TrendBadge'
import type { TrendPoint } from '@/types'

const COLORS = {
  positive: '#10b981',
  neutral:  '#94a3b8',
  negative: '#f87171',
}

interface SentimentOverviewProps {
  data: TrendPoint[]
}

// Compute overall breakdown from last data point
function computeSummary(data: TrendPoint[]) {
  if (!data.length) return { positive: 0, neutral: 0, negative: 0, score: 0 }
  const last = data[data.length - 1]
  const prev = data[data.length - 2]
  const trend = prev ? last.negative - prev.negative : 0
  return {
    positive: last.positive,
    neutral:  last.neutral,
    negative: last.negative,
    score: Math.round(last.positive - last.negative),
    trend,
  }
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-lg p-3 text-xs">
      <p className="font-semibold text-gray-700 mb-2">{label}</p>
      {payload.map((p: any) => (
        <div key={p.name} className="flex items-center justify-between gap-4 mb-0.5">
          <span className="flex items-center gap-1.5 capitalize text-gray-600">
            <span className="w-2 h-2 rounded-full inline-block" style={{ background: p.color }} />
            {p.name}
          </span>
          <span className="font-medium text-gray-900">{p.value}%</span>
        </div>
      ))}
    </div>
  )
}

export function SentimentOverview({ data }: SentimentOverviewProps) {
  const summary = computeSummary(data)

  return (
    <Card className="flex flex-col">
      <CardHeader
        title="Sentiment Overview"
        subtitle="12-month trend across all platforms"
        action={
          <div className="flex items-center gap-2">
            <TrendBadge value={-(summary.trend ?? 0)} positive={false} suffix="pp" size="xs" />
            <span className="text-xs text-gray-400">vs prev month</span>
          </div>
        }
      />

      {/* Summary pills */}
      <div className="flex gap-3 mb-4">
        {[
          { label: 'Positive', value: summary.positive, color: 'text-emerald-600', bg: 'bg-emerald-50' },
          { label: 'Neutral',  value: summary.neutral,  color: 'text-gray-600',    bg: 'bg-gray-100'   },
          { label: 'Negative', value: summary.negative, color: 'text-red-500',     bg: 'bg-red-50'     },
        ].map(item => (
          <div key={item.label} className={`flex-1 rounded-lg ${item.bg} px-3 py-2`}>
            <div className={`text-lg font-bold ${item.color}`}>{item.value}%</div>
            <div className="text-xs text-gray-500 mt-0.5">{item.label}</div>
          </div>
        ))}
        <div className="flex-1 rounded-lg bg-blue-50 px-3 py-2">
          <div className="text-lg font-bold text-blue-600">
            {summary.score > 0 ? '+' : ''}{summary.score}
          </div>
          <div className="text-xs text-gray-500 mt-0.5">Net score</div>
        </div>
      </div>

      {/* Chart */}
      <div className="h-48">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
            <defs>
              {(['positive', 'neutral', 'negative'] as const).map(key => (
                <linearGradient key={key} id={`grad-${key}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor={COLORS[key]} stopOpacity={0.2} />
                  <stop offset="95%" stopColor={COLORS[key]} stopOpacity={0}   />
                </linearGradient>
              ))}
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis
              dataKey="period"
              tick={{ fontSize: 11, fill: '#94a3b8' }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tick={{ fontSize: 11, fill: '#94a3b8' }}
              axisLine={false}
              tickLine={false}
              tickFormatter={v => `${v}%`}
              domain={[0, 80]}
            />
            <Tooltip content={<CustomTooltip />} />
            <Area
              type="monotone"
              dataKey="positive"
              stroke={COLORS.positive}
              strokeWidth={2}
              fill={`url(#grad-positive)`}
            />
            <Area
              type="monotone"
              dataKey="neutral"
              stroke={COLORS.neutral}
              strokeWidth={1.5}
              fill={`url(#grad-neutral)`}
              strokeDasharray="4 2"
            />
            <Area
              type="monotone"
              dataKey="negative"
              stroke={COLORS.negative}
              strokeWidth={2}
              fill={`url(#grad-negative)`}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </Card>
  )
}
