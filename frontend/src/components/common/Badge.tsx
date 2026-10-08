import { clsx } from 'clsx'
import type { SentimentLabel, IssueSeverity } from '@/types'

// ─── Sentiment Badge ──────────────────────────────────────────────────────────

const SENTIMENT_STYLES: Record<SentimentLabel, string> = {
  positive: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  neutral:  'bg-gray-50 text-gray-600 border-gray-200',
  negative: 'bg-red-50 text-red-700 border-red-200',
  mixed:    'bg-amber-50 text-amber-700 border-amber-200',
}

const SENTIMENT_DOTS: Record<SentimentLabel, string> = {
  positive: 'bg-emerald-500',
  neutral:  'bg-gray-400',
  negative: 'bg-red-500',
  mixed:    'bg-amber-500',
}

export function SentimentBadge({
  sentiment,
  showDot = true,
  size = 'sm',
}: {
  sentiment: SentimentLabel
  showDot?: boolean
  size?: 'xs' | 'sm'
}) {
  return (
    <span className={clsx(
      'inline-flex items-center gap-1 border rounded-full font-medium capitalize',
      SENTIMENT_STYLES[sentiment],
      size === 'xs' ? 'px-1.5 py-0.5 text-[10px]' : 'px-2 py-0.5 text-xs'
    )}>
      {showDot && (
        <span className={clsx('w-1.5 h-1.5 rounded-full shrink-0', SENTIMENT_DOTS[sentiment])} />
      )}
      {sentiment}
    </span>
  )
}

// ─── Severity Badge ───────────────────────────────────────────────────────────

const SEVERITY_STYLES: Record<IssueSeverity, string> = {
  critical: 'bg-red-100 text-red-800 border-red-200',
  high:     'bg-orange-100 text-orange-800 border-orange-200',
  medium:   'bg-amber-100 text-amber-800 border-amber-200',
  low:      'bg-blue-50 text-blue-700 border-blue-200',
}

export function SeverityBadge({
  severity,
  size = 'sm',
}: {
  severity: IssueSeverity
  size?: 'xs' | 'sm'
}) {
  return (
    <span className={clsx(
      'inline-flex items-center border rounded-full font-medium capitalize',
      SEVERITY_STYLES[severity],
      size === 'xs' ? 'px-1.5 py-0.5 text-[10px]' : 'px-2 py-0.5 text-xs'
    )}>
      {severity}
    </span>
  )
}

// ─── Category Badge ───────────────────────────────────────────────────────────

const CATEGORY_COLORS: Record<string, string> = {
  battery:     'bg-purple-50 text-purple-700 border-purple-200',
  charging:    'bg-blue-50 text-blue-700 border-blue-200',
  range:       'bg-cyan-50 text-cyan-700 border-cyan-200',
  thermal:     'bg-rose-50 text-rose-700 border-rose-200',
  reliability: 'bg-green-50 text-green-700 border-green-200',
  ownership:   'bg-indigo-50 text-indigo-700 border-indigo-200',
}

export function CategoryBadge({
  category,
  size = 'sm',
}: {
  category: string
  size?: 'xs' | 'sm'
}) {
  const style = CATEGORY_COLORS[category.toLowerCase()] ?? 'bg-gray-50 text-gray-600 border-gray-200'
  return (
    <span className={clsx(
      'inline-flex items-center border rounded-full font-medium capitalize',
      style,
      size === 'xs' ? 'px-1.5 py-0.5 text-[10px]' : 'px-2 py-0.5 text-xs'
    )}>
      {category}
    </span>
  )
}
