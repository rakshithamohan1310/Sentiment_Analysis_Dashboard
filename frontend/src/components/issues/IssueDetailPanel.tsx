import {
  AlertTriangle,
  Calendar,
  Car,
  MessageSquare,
  TrendingUp,
  Tag,
  Quote,
  ArrowUpRight,
  Clock,
} from 'lucide-react'
import { SlideOver } from '@/components/common/Modal'
import { SeverityBadge, CategoryBadge } from '@/components/common/Badge'
import { TrendBadge } from '@/components/common/TrendBadge'
import { SentimentBar } from '@/components/common/SentimentBar'
import type { Issue } from '@/types'

interface IssueDetailPanelProps {
  issue: Issue | null
  open: boolean
  onClose: () => void
}

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  new:           { label: 'New Signal',   color: 'text-red-600 bg-red-50 border-red-200'      },
  investigating: { label: 'Investigating', color: 'text-orange-600 bg-orange-50 border-orange-200' },
  monitoring:    { label: 'Monitoring',   color: 'text-blue-600 bg-blue-50 border-blue-200'   },
  resolved:      { label: 'Resolved',     color: 'text-emerald-600 bg-emerald-50 border-emerald-200' },
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="px-5 py-4 border-b border-gray-100 last:border-0">
      <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">{title}</h3>
      {children}
    </div>
  )
}

function StatPill({ label, value, sub }: { label: string; value: React.ReactNode; sub?: string }) {
  return (
    <div className="bg-gray-50 border border-gray-200 rounded-lg px-3 py-2.5 flex flex-col gap-0.5">
      <div className="text-base font-bold text-gray-900">{value}</div>
      <div className="text-[10px] text-gray-500 font-medium">{label}</div>
      {sub && <div className="text-[10px] text-gray-400">{sub}</div>}
    </div>
  )
}

export function IssueDetailPanel({ issue, open, onClose }: IssueDetailPanelProps) {
  if (!issue) return null

  const statusMeta = STATUS_LABELS[issue.status]
  const positivePct = Math.max(0, 100 - issue.negativePct - 14)
  const neutralPct  = 14

  return (
    <SlideOver
      open={open}
      onClose={onClose}
      title={issue.title}
      subtitle={`${issue.category} · ${issue.aspect.replace(/_/g, ' ')}`}
      width="lg"
    >
      {/* Status bar */}
      <div className="px-5 py-3 bg-gray-50 border-b border-gray-200 flex items-center gap-2 flex-wrap">
        <span className={`text-xs font-semibold px-2.5 py-1 rounded-full border ${statusMeta.color}`}>
          {statusMeta.label}
        </span>
        <SeverityBadge severity={issue.severity} />
        <CategoryBadge category={issue.category} />
        <div className="ml-auto">
          <TrendBadge value={issue.trend} positive={false} />
        </div>
      </div>

      {/* Summary stats */}
      <Section title="Summary">
        <div className="grid grid-cols-3 gap-2 mb-3">
          <StatPill label="Mentions" value={issue.mentions.toLocaleString()} />
          <StatPill label="Negative %" value={`${issue.negativePct}%`} />
          <StatPill label="Trend" value={
            <TrendBadge value={issue.trend} positive={false} />
          } />
        </div>
        <div className="mb-1">
          <div className="flex justify-between text-[10px] text-gray-500 mb-1">
            <span>Sentiment distribution</span>
            <span>{positivePct}% pos · {neutralPct}% neu · {issue.negativePct}% neg</span>
          </div>
          <SentimentBar
            positive={positivePct}
            neutral={neutralPct}
            negative={issue.negativePct}
            height="md"
          />
        </div>
      </Section>

      {/* Description */}
      <Section title="Description">
        <p className="text-sm text-gray-600 leading-relaxed">{issue.description}</p>
      </Section>

      {/* Timeline */}
      <Section title="Timeline">
        <div className="flex gap-4">
          <div className="flex items-center gap-2 text-xs text-gray-600">
            <Calendar className="w-3.5 h-3.5 text-gray-400" />
            <span className="font-medium">First seen</span>
            <span className="text-gray-900">
              {new Date(issue.firstSeen).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}
            </span>
          </div>
          <div className="flex items-center gap-2 text-xs text-gray-600">
            <Clock className="w-3.5 h-3.5 text-gray-400" />
            <span className="font-medium">Last seen</span>
            <span className="text-gray-900">
              {new Date(issue.lastSeen).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}
            </span>
          </div>
        </div>
      </Section>

      {/* Affected vehicles */}
      <Section title="Affected Vehicles">
        <div className="flex flex-wrap gap-1.5">
          {issue.affectedVehicles.map(v => (
            <div key={v} className="flex items-center gap-1 text-xs bg-gray-100 text-gray-700 rounded-full px-2.5 py-1 font-medium">
              <Car className="w-3 h-3 text-gray-400" />
              {v}
            </div>
          ))}
        </div>
      </Section>

      {/* Platforms */}
      <Section title="Platforms with Reports">
        <div className="flex flex-wrap gap-1.5">
          {issue.affectedPlatforms.map(p => (
            <div key={p} className="flex items-center gap-1 text-xs bg-blue-50 text-blue-700 border border-blue-100 rounded-full px-2.5 py-1 font-medium">
              <MessageSquare className="w-3 h-3" />
              {p}
            </div>
          ))}
        </div>
      </Section>

      {/* Sample customer quotes */}
      {issue.sampleQuotes.length > 0 && (
        <Section title="Sample Customer Quotes">
          <div className="space-y-2">
            {issue.sampleQuotes.map((q, i) => (
              <div key={i} className="flex gap-2.5 bg-gray-50 border border-gray-200 rounded-lg p-3">
                <Quote className="w-3.5 h-3.5 text-gray-300 shrink-0 mt-0.5" />
                <p className="text-xs text-gray-600 leading-relaxed italic">{q}</p>
              </div>
            ))}
          </div>
          <p className="text-[10px] text-gray-400 mt-2">
            These represent customer-reported sentiment signals and do not confirm engineering defects.
          </p>
        </Section>
      )}

      {/* Actions */}
      <div className="px-5 py-4 bg-gray-50 border-t border-gray-200 flex gap-2">
        <button className="flex-1 flex items-center justify-center gap-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold rounded-lg px-4 py-2.5 transition-colors">
          <TrendingUp className="w-3.5 h-3.5" />
          Open Full Investigation
        </button>
        <button className="flex items-center justify-center gap-1.5 bg-white hover:bg-gray-100 text-gray-700 text-sm font-medium rounded-lg px-3 py-2.5 border border-gray-200 transition-colors">
          <ArrowUpRight className="w-3.5 h-3.5" />
          View Reviews
        </button>
      </div>
    </SlideOver>
  )
}
