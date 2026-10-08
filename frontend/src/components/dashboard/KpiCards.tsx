import {
  MessageSquare,
  TrendingDown,
  AlertTriangle,
  Globe,
  LucideIcon,
} from 'lucide-react'
import { clsx } from 'clsx'
import { TrendBadge } from '@/components/common/TrendBadge'
import type { KPI } from '@/types'

const ICON_MAP: Record<string, LucideIcon> = {
  MessageSquare,
  TrendingDown,
  AlertTriangle,
  Globe,
}

function KpiCard({ kpi }: { kpi: KPI }) {
  const Icon = ICON_MAP[kpi.icon] ?? MessageSquare
  const isGoodTrend = kpi.trend === 'up' ? kpi.positive : !kpi.positive

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4 flex flex-col gap-3">
      <div className="flex items-start justify-between">
        <div className={clsx(
          'w-9 h-9 rounded-lg flex items-center justify-center',
          isGoodTrend ? 'bg-blue-50' : 'bg-red-50'
        )}>
          <Icon className={clsx(
            'w-4.5 h-4.5',
            isGoodTrend ? 'text-blue-600' : 'text-red-500'
          )} style={{ width: 18, height: 18 }} />
        </div>
        <TrendBadge
          value={kpi.change}
          positive={kpi.positive}
          suffix="%"
          size="xs"
        />
      </div>

      <div>
        <div className="text-2xl font-bold text-gray-900 leading-none">
          {kpi.value}
        </div>
        <div className="text-sm font-medium text-gray-700 mt-1">{kpi.label}</div>
        <div className="text-xs text-gray-400 mt-0.5">{kpi.description}</div>
      </div>
    </div>
  )
}

export function KpiCards({ kpis }: { kpis: KPI[] }) {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      {kpis.map(kpi => (
        <KpiCard key={kpi.id} kpi={kpi} />
      ))}
    </div>
  )
}
