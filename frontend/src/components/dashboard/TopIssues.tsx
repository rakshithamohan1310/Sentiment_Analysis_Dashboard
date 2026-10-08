import { ArrowUpRight } from 'lucide-react'
import { Card, CardHeader } from '@/components/common/Card'
import { SeverityBadge } from '@/components/common/Badge'
import { TrendBadge } from '@/components/common/TrendBadge'
import { SentimentBar } from '@/components/common/SentimentBar'
import type { Issue } from '@/types'

interface TopIssuesProps {
  issues: Issue[]
  onIssueClick: (issue: Issue) => void
}

export function TopIssues({ issues, onIssueClick }: TopIssuesProps) {
  return (
    <Card>
      <CardHeader
        title="Top Customer Issues"
        subtitle="Ranked by mention volume"
      />
      <ol className="space-y-1">
        {issues.map((issue, idx) => (
          <li key={issue.id}>
            <button
              onClick={() => onIssueClick(issue)}
              className="w-full flex items-center gap-3 px-2 py-2.5 rounded-lg hover:bg-gray-50 transition-colors group text-left"
            >
              {/* Rank */}
              <span className="w-5 h-5 rounded-full bg-gray-100 text-gray-500 text-[10px] font-bold flex items-center justify-center shrink-0">
                {idx + 1}
              </span>

              {/* Info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5 mb-1">
                  <span className="text-xs font-semibold text-gray-800 truncate group-hover:text-blue-600 transition-colors">
                    {issue.title}
                  </span>
                  <ArrowUpRight className="w-3 h-3 text-gray-300 group-hover:text-blue-500 shrink-0 transition-colors" />
                </div>
                <SentimentBar
                  positive={100 - issue.negativePct - 15}
                  neutral={15}
                  negative={issue.negativePct}
                  height="xs"
                />
              </div>

              {/* Stats */}
              <div className="flex flex-col items-end gap-1 shrink-0">
                <div className="flex items-center gap-1">
                  <span className="text-xs font-semibold text-gray-700">
                    {issue.mentions.toLocaleString()}
                  </span>
                  <TrendBadge value={issue.trend} positive={false} size="xs" />
                </div>
                <SeverityBadge severity={issue.severity} size="xs" />
              </div>
            </button>

            {idx < issues.length - 1 && (
              <div className="ml-8 h-px bg-gray-100" />
            )}
          </li>
        ))}
      </ol>
    </Card>
  )
}
