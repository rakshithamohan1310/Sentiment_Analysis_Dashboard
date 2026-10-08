import { Lightbulb, TrendingUp, Cpu, Thermometer, AlertOctagon, Search } from 'lucide-react'
import { clsx } from 'clsx'
import { Card, CardHeader } from '@/components/common/Card'
import { SeverityBadge } from '@/components/common/Badge'
import type { Insight, InsightType } from '@/types'

const TYPE_META: Record<InsightType, { label: string; icon: React.ElementType; color: string }> = {
  'emerging-pattern':  { label: 'Emerging pattern',  icon: TrendingUp,    color: 'text-blue-600 bg-blue-50'     },
  'sentiment-shift':   { label: 'Sentiment shift',   icon: TrendingUp,    color: 'text-amber-600 bg-amber-50'   },
  'model-specific':    { label: 'Model-specific',    icon: Cpu,           color: 'text-purple-600 bg-purple-50' },
  'seasonal':          { label: 'Seasonal pattern',  icon: Thermometer,   color: 'text-cyan-600 bg-cyan-50'     },
  'platform-anomaly':  { label: 'Platform anomaly',  icon: AlertOctagon,  color: 'text-rose-600 bg-rose-50'     },
}

function ConfidencePip({ value }: { value: number }) {
  const color = value >= 85 ? 'bg-emerald-500' : value >= 70 ? 'bg-amber-400' : 'bg-gray-300'
  return (
    <div className="flex items-center gap-1.5">
      <div className="flex gap-0.5">
        {[20, 40, 60, 80, 100].map(thresh => (
          <div
            key={thresh}
            className={clsx(
              'w-1 h-3 rounded-sm',
              value >= thresh ? color : 'bg-gray-100'
            )}
          />
        ))}
      </div>
      <span className="text-[10px] text-gray-500 font-medium">{value}%</span>
    </div>
  )
}

function InsightCard({ insight, onInvestigate }: { insight: Insight; onInvestigate: () => void }) {
  const meta = TYPE_META[insight.type]
  const Icon = meta.icon

  return (
    <div className="border border-gray-200 rounded-lg p-3 hover:border-gray-300 hover:shadow-sm transition-all">
      {/* Header row */}
      <div className="flex items-start gap-2 mb-2">
        <div className={clsx('w-7 h-7 rounded-md flex items-center justify-center shrink-0', meta.color)}>
          <Icon className="w-3.5 h-3.5" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 flex-wrap mb-0.5">
            <span className={clsx('text-[10px] font-semibold rounded-full px-1.5 py-0.5', meta.color)}>
              {meta.label}
            </span>
            <SeverityBadge severity={insight.severity} size="xs" />
          </div>
          <p className="text-xs font-semibold text-gray-900 leading-snug">{insight.title}</p>
        </div>
      </div>

      {/* Body */}
      <p className="text-xs text-gray-500 leading-relaxed mb-3 line-clamp-3">
        {insight.description}
      </p>

      {/* Footer */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div>
            <div className="text-[10px] text-gray-400 mb-0.5">Confidence</div>
            <ConfidencePip value={insight.confidence} />
          </div>
          <div>
            <div className="text-[10px] text-gray-400 mb-0.5">Aspect</div>
            <span className="text-xs font-semibold text-gray-700">{insight.affectedAspect}</span>
          </div>
        </div>
        <button
          onClick={onInvestigate}
          className="flex items-center gap-1 text-xs font-semibold text-blue-600 hover:text-blue-700 bg-blue-50 hover:bg-blue-100 px-2.5 py-1.5 rounded-lg transition-colors"
        >
          <Search className="w-3 h-3" />
          Investigate
        </button>
      </div>
    </div>
  )
}

interface AiInsightsProps {
  insights: Insight[]
  onInvestigate: (insight: Insight) => void
}

export function AiInsights({ insights, onInvestigate }: AiInsightsProps) {
  return (
    <Card>
      <CardHeader
        title="AI Insights"
        subtitle="Customer-reported signal patterns detected this period"
        action={
          <div className="flex items-center gap-1 bg-blue-50 text-blue-700 text-[10px] font-semibold px-2 py-1 rounded-full border border-blue-100">
            <Lightbulb className="w-3 h-3" />
            {insights.length} new
          </div>
        }
      />

      <div className="text-[10px] text-gray-400 bg-amber-50 border border-amber-100 rounded-md px-2.5 py-1.5 mb-3 leading-relaxed">
        ⚠ Insights represent <strong className="text-amber-700">customer-reported sentiment signals</strong> and emerging patterns.
        They do not confirm confirmed engineering defects or product quality issues.
      </div>

      <div className="space-y-2.5">
        {insights.map(insight => (
          <InsightCard
            key={insight.id}
            insight={insight}
            onInvestigate={() => onInvestigate(insight)}
          />
        ))}
      </div>
    </Card>
  )
}
