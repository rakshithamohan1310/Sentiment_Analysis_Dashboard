import { ArrowUpRight } from 'lucide-react'
import type { ReportedMention } from '@/types'

interface IssuePipelineProps {
  issues: ReportedMention[]
  onIssueClick: (issue: ReportedMention) => void
}

export function IssuePipeline({ issues, onIssueClick }: IssuePipelineProps) {
  return (
    <div>
      <div className="mb-3">
        <h3 className="text-sm font-semibold text-gray-900">Customer-reported mentions</h3>
        <p className="text-xs text-gray-500 mt-0.5">
          Each card is an issue mentioned in feedback. There is no verified-fault status in the API, so nothing here is marked confirmed.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3">
        {issues.map(issue => (
          <button
            key={issue.aspect}
            onClick={() => onIssueClick(issue)}
            className="w-full text-left bg-white border border-gray-200 rounded-lg p-3 hover:border-gray-300 transition-all group"
          >
            <div className="flex items-start justify-between gap-2 mb-2">
              <span className="text-xs font-semibold text-gray-800 leading-snug group-hover:text-blue-600">
                {issue.label}
              </span>
              <ArrowUpRight className="w-3 h-3 text-gray-300 group-hover:text-blue-500 shrink-0 mt-0.5" />
            </div>
            <div className="flex items-center gap-1.5 flex-wrap mb-2">
              <span className="text-[10px] font-medium text-gray-600 bg-gray-100 rounded-full px-1.5 py-0.5 capitalize">
                {issue.category.replace(/_/g, ' ')}
              </span>
              <span className="text-[10px] font-medium text-amber-800 bg-amber-50 border border-amber-100 rounded-full px-1.5 py-0.5">
                Customer-reported
              </span>
            </div>
            <div className="flex items-center justify-between text-[10px] text-gray-500">
              <span className="font-medium">{issue.mentions.toLocaleString()} mentions</span>
              <span>Text signal {issue.negativePct}% negative</span>
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}
