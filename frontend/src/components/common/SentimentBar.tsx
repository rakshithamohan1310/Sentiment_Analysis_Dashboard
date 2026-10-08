import { clsx } from 'clsx'

interface SentimentBarProps {
  positive: number
  neutral: number
  negative: number
  height?: 'xs' | 'sm' | 'md'
  showLabels?: boolean
  className?: string
}

export function SentimentBar({
  positive,
  neutral,
  negative,
  height = 'sm',
  showLabels = false,
  className,
}: SentimentBarProps) {
  const total = positive + neutral + negative || 1
  const pPct = Math.round((positive / total) * 100)
  const neuPct = Math.round((neutral / total) * 100)
  const nPct = 100 - pPct - neuPct

  const hCls = { xs: 'h-1', sm: 'h-1.5', md: 'h-2' }[height]

  return (
    <div className={clsx('w-full', className)}>
      <div className={clsx('flex w-full rounded-full overflow-hidden gap-px', hCls)}>
        {pPct > 0 && (
          <div
            className="bg-emerald-500 rounded-l-full transition-all"
            style={{ width: `${pPct}%` }}
          />
        )}
        {neuPct > 0 && (
          <div
            className={clsx('bg-gray-300 transition-all', pPct === 0 && 'rounded-l-full', nPct === 0 && 'rounded-r-full')}
            style={{ width: `${neuPct}%` }}
          />
        )}
        {nPct > 0 && (
          <div
            className="bg-red-400 rounded-r-full transition-all"
            style={{ width: `${nPct}%` }}
          />
        )}
      </div>
      {showLabels && (
        <div className="flex justify-between mt-1 text-[10px] text-gray-500">
          <span className="text-emerald-600">{pPct}%</span>
          <span>{neuPct}%</span>
          <span className="text-red-500">{nPct}%</span>
        </div>
      )}
    </div>
  )
}
