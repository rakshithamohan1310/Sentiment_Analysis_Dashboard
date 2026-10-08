import { clsx } from 'clsx'
import type { ReactNode } from 'react'

interface CardProps {
  children: ReactNode
  className?: string
  onClick?: () => void
  hoverable?: boolean
  padding?: 'none' | 'sm' | 'md' | 'lg'
}

export function Card({
  children,
  className,
  onClick,
  hoverable = false,
  padding = 'md',
}: CardProps) {
  const padMap = { none: '', sm: 'p-3', md: 'p-4', lg: 'p-5' }
  return (
    <div
      onClick={onClick}
      className={clsx(
        'bg-white border border-gray-200 rounded-xl',
        padMap[padding],
        hoverable && 'cursor-pointer transition-shadow hover:shadow-md hover:border-gray-300',
        onClick && !hoverable && 'cursor-pointer',
        className
      )}
    >
      {children}
    </div>
  )
}

// Lightweight section header inside a card
export function CardHeader({
  title,
  subtitle,
  action,
}: {
  title: string
  subtitle?: string
  action?: ReactNode
}) {
  return (
    <div className="flex items-start justify-between mb-4">
      <div>
        <h3 className="text-sm font-semibold text-gray-900">{title}</h3>
        {subtitle && <p className="text-xs text-gray-500 mt-0.5">{subtitle}</p>}
      </div>
      {action && <div className="ml-4 shrink-0">{action}</div>}
    </div>
  )
}
