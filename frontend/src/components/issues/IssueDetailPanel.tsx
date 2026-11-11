import { Quote } from 'lucide-react'
import { SlideOver } from '@/components/common/Modal'
import { CategoryBadge } from '@/components/common/Badge'
import { SentimentBar } from '@/components/common/SentimentBar'
import type { AspectExample } from '@/api/types'
import type { ApiState } from '@/api/useApi'
import type { AspectDetailResponse } from '@/api/types'
import type { ReportedMention } from '@/types'

interface IssueDetailPanelProps {
  issue: ReportedMention | null
  detail: ApiState<AspectDetailResponse>
  open: boolean
  onClose: () => void
}

export function IssueDetailPanel({ issue, detail, open, onClose }: IssueDetailPanelProps) {
  if (!issue) return null

  const examples: AspectExample[] = detail.data?.recent_examples ?? []

  return (
    <SlideOver
      open={open}
      onClose={onClose}
      title={issue.label}
      subtitle={`${issue.category} · customer-reported mention`}
      width="lg"
    >
      <div className="px-5 py-3 bg-amber-50 border-b border-amber-100 text-xs text-amber-900">
        Customer-reported. Verified status is not available. A negative share is a text-based indicator, not a confirmed battery or vehicle fault.
      </div>

      <div className="px-5 py-4 border-b border-gray-100">
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">From the aspect API</h3>
        <div className="grid grid-cols-3 gap-2 mb-3">
          <Stat label="Mentions" value={issue.mentions.toLocaleString()} />
          <Stat label="Negative text" value={`${issue.negativePct}%`} />
          <Stat label="Verified" value="Not available" />
        </div>
        <SentimentBar
          positive={issue.positivePct}
          neutral={issue.neutralPct}
          negative={issue.negativePct}
          height="md"
          showLabels
        />
        <div className="mt-3">
          <CategoryBadge category={issue.category} />
        </div>
      </div>

      <div className="px-5 py-4">
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Matching text</h3>
        {detail.status === 'loading' && (
          <p className="text-sm text-gray-500">Loading examples…</p>
        )}
        {detail.status === 'error' && (
          <p className="text-sm text-red-600">{detail.error ?? 'Could not load examples.'}</p>
        )}
        {detail.status === 'ready' && examples.length === 0 && (
          <p className="text-sm text-gray-500">No matching excerpts for this filter.</p>
        )}
        {detail.status === 'ready' && examples.length > 0 && (
          <div className="space-y-2">
            {examples.map((example, index) => (
              <div key={`${example.source}-${index}`} className="bg-gray-50 border border-gray-200 rounded-lg p-3">
                <div className="flex items-start gap-2">
                  <Quote className="w-3.5 h-3.5 text-gray-300 shrink-0 mt-0.5" />
                  <p className="text-xs text-gray-700 leading-relaxed">
                    {example.matched_text || 'No excerpt stored.'}
                  </p>
                </div>
                <p className="text-[10px] text-gray-400 mt-2 capitalize">
                  {example.sentiment_label ?? 'unlabelled'} · {example.source}
                  {example.published_at ? ` · ${new Date(example.published_at).toLocaleDateString('en-GB')}` : ''}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    </SlideOver>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-gray-50 border border-gray-200 rounded-lg px-3 py-2.5">
      <div className="text-sm font-bold text-gray-900">{value}</div>
      <div className="text-[10px] text-gray-500 font-medium">{label}</div>
    </div>
  )
}
