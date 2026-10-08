import { AlertTriangle, ArrowUpRight } from 'lucide-react'
import { clsx } from 'clsx'
import { SentimentBadge } from '@/components/common/Badge'
import { SeverityBadge } from '@/components/common/Badge'
import { TrendBadge } from '@/components/common/TrendBadge'
import type { Issue, IssueStatus } from '@/types'

const COLUMNS: { id: IssueStatus; label: string; color: string; dot: string }[] = [
  { id: 'new',           label: 'New Signals',   color: 'border-t-red-400',    dot: 'bg-red-400'    },
  { id: 'investigating', label: 'Investigating',  color: 'border-t-orange-400', dot: 'bg-orange-400' },
  { id: 'monitoring',    label: 'Monitoring',     color: 'border-t-blue-400',   dot: 'bg-blue-400'   },
  { id: 'resolved',      label: 'Resolved',       color: 'border-t-emerald-400',dot: 'bg-emerald-400'},
]

function IssueCard({ issue, onClick }: { issue: Issue; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="w-full text-left bg-white border border-gray-200 rounded-lg p-3 hover:shadow-md hover:border-gray-300 transition-all group"
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <span className="text-xs font-semibold text-gray-800 leading-snug line-clamp-2 group-hover:text-blue-600 transition-colors">
          {issue.title}
        </span>
        <ArrowUpRight className="w-3 h-3 text-gray-300 group-hover:text-blue-500 shrink-0 mt-0.5 transition-colors" />
      </div>

      <div className="flex items-center gap-1 flex-wrap mb-2">
        <SentimentBadge sentiment="negative" size="xs" />
        <SeverityBadge severity={issue.severity} size="xs" />
      </div>

      <div className="flex items-center justify-between text-[10px] text-gray-500">
        <span className="font-medium">{issue.mentions.toLocaleString()} mentions</span>
        <TrendBadge value={issue.trend} positive={false} size="xs" />
      </div>
    </button>
  )
}

interface IssuePipelineProps {
  issues: Issue[]
  onIssueClick: (issue: Issue) => void
}

export function IssuePipeline({ issues, onIssueClick }: IssuePipelineProps) {
  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="text-sm font-semibold text-gray-900">Issue Pipeline</h3>
          <p className="text-xs text-gray-500 mt-0.5">Track issue lifecycle from signal to resolution</p>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-3">
        {COLUMNS.map(col => {
          const colIssues = issues.filter(i => i.status === col.id)
          return (
            <div key={col.id} className="flex flex-col">
              {/* Column header */}
              <div className={clsx(
                'bg-white border border-gray-200 rounded-t-lg px-3 py-2 border-t-2',
                col.color
              )}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <span className={clsx('w-2 h-2 rounded-full', col.dot)} />
                    <span className="text-xs font-semibold text-gray-700">{col.label}</span>
                  </div>
                  <span className="text-xs font-bold text-gray-500 bg-gray-100 rounded-full w-5 h-5 flex items-center justify-center">
                    {colIssues.length}
                  </span>
                </div>
              </div>

              {/* Cards */}
              <div className="bg-gray-50 border border-t-0 border-gray-200 rounded-b-lg p-2 flex flex-col gap-2 min-h-[160px]">
                {colIssues.length === 0 && (
                  <div className="flex-1 flex items-center justify-center">
                    <span className="text-xs text-gray-300 italic">No issues</span>
                  </div>
                )}
                {colIssues.map(issue => (
                  <IssueCard
                    key={issue.id}
                    issue={issue}
                    onClick={() => onIssueClick(issue)}
                  />
                ))}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
