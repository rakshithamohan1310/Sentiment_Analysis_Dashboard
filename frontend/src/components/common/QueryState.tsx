import type { ReactNode } from 'react'
import type { ApiStatus } from '@/api/useApi'

interface QueryStateProps {
  status: ApiStatus
  error: string | null
  empty?: boolean
  emptyLabel?: string
  onRetry?: () => void
  children: ReactNode
}

export function QueryState({
  status,
  error,
  empty = false,
  emptyLabel = 'No feedback matches this filter.',
  onRetry,
  children,
}: QueryStateProps) {
  if (status === 'loading' || status === 'idle') {
    return (
      <div className="bg-white border border-gray-200 rounded-xl px-4 py-8 text-center text-sm text-gray-500">
        Loading feedback…
      </div>
    )
  }

  if (status === 'error') {
    return (
      <div className="bg-white border border-red-200 rounded-xl px-4 py-8 text-center">
        <p className="text-sm font-medium text-red-700">Could not load this section</p>
        <p className="text-xs text-red-600 mt-1">{error ?? 'The request failed.'}</p>
        {onRetry && (
          <button
            onClick={onRetry}
            className="mt-3 text-xs font-medium text-blue-700 bg-blue-50 hover:bg-blue-100 rounded-md px-3 py-1.5"
          >
            Retry
          </button>
        )}
      </div>
    )
  }

  if (empty) {
    return (
      <div className="bg-white border border-gray-200 rounded-xl px-4 py-8 text-center text-sm text-gray-500">
        {emptyLabel}
      </div>
    )
  }

  return <>{children}</>
}
