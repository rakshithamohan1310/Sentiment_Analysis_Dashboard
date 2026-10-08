import { TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { clsx } from 'clsx'

interface TrendBadgeProps {
  value: number        // percent change
  positive?: boolean   // whether an increase is good (default true)
  suffix?: string      // e.g. "%" or " mentions"
  size?: 'xs' | 'sm'
}

export function TrendBadge({
  value,
  positive = true,
  suffix = '%',
  size = 'sm',
}: TrendBadgeProps) {
  const isUp   = value > 0
  const isDown = value < 0
  const isFlat = value === 0

  // Colour logic: isGood = (up AND positive metric) OR (down AND negative metric)
  const isGood = (isUp && positive) || (isDown && !positive)
  const isBad  = (isUp && !positive) || (isDown && positive)

  const colorCls = isGood
    ? 'text-emerald-600 bg-emerald-50'
    : isBad
    ? 'text-red-600 bg-red-50'
    : 'text-gray-500 bg-gray-50'

  const Icon = isUp ? TrendingUp : isDown ? TrendingDown : Minus
  const label = isFlat ? '0' : `${isUp ? '+' : ''}${value.toFixed(1)}`

  return (
    <span className={clsx(
      'inline-flex items-center gap-0.5 rounded-full font-medium',
      colorCls,
      size === 'xs' ? 'px-1.5 py-0.5 text-[10px]' : 'px-2 py-0.5 text-xs'
    )}>
      <Icon className={size === 'xs' ? 'w-2.5 h-2.5' : 'w-3 h-3'} />
      {label}{suffix}
    </span>
  )
}
