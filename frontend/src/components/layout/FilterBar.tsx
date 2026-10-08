import { ChevronDown, RotateCcw } from 'lucide-react'
import { clsx } from 'clsx'
import type { FilterState } from '@/types'
import { filterOptions } from '@/data/mockData'

interface FilterBarProps {
  filters: FilterState
  onFilterChange: (key: keyof FilterState, value: string) => void
  onResetFilters: () => void
}

const FILTER_DEFS: {
  key: keyof FilterState
  label: string
  options: string[]
}[] = [
  { key: 'domain',    label: 'Domain',    options: filterOptions.domains },
  { key: 'timeRange', label: 'Time',      options: filterOptions.timeRanges },
  { key: 'platform',  label: 'Platform',  options: filterOptions.platforms },
  { key: 'vehicle',   label: 'Vehicle',   options: filterOptions.vehicles },
  { key: 'sentiment', label: 'Sentiment', options: filterOptions.sentiments },
]

const DEFAULT_FILTERS: FilterState = {
  domain:    'EV',
  timeRange: 'Last 30 days',
  platform:  'All Platforms',
  vehicle:   'All Vehicles',
  sentiment: 'All Sentiment',
}

function isDefaultValue(key: keyof FilterState, value: string) {
  return value === DEFAULT_FILTERS[key]
}

export function FilterBar({ filters, onFilterChange, onResetFilters }: FilterBarProps) {
  const hasActive = (Object.keys(filters) as (keyof FilterState)[]).some(
    k => !isDefaultValue(k, filters[k])
  )

  return (
    <div className="h-11 bg-white border-b border-gray-200 flex items-center gap-2 px-5 shrink-0">
      <span className="text-xs font-medium text-gray-500 mr-1">Filters:</span>

      <div className="flex items-center gap-1.5 flex-wrap">
        {FILTER_DEFS.map(({ key, label, options }) => {
          const value = filters[key]
          const active = !isDefaultValue(key, value)
          return (
            <div key={key} className="relative">
              <label className="sr-only">{label}</label>
              <div className={clsx(
                'flex items-center gap-1 pl-2.5 pr-1.5 py-1 rounded-md border text-xs font-medium cursor-pointer transition-colors',
                active
                  ? 'border-blue-300 bg-blue-50 text-blue-700'
                  : 'border-gray-200 bg-gray-50 text-gray-600 hover:border-gray-300 hover:bg-gray-100'
              )}>
                <span className="text-gray-400 text-[10px] font-normal mr-0.5">{label}:</span>
                <select
                  value={value}
                  onChange={e => onFilterChange(key, e.target.value)}
                  className="bg-transparent border-0 outline-none cursor-pointer font-medium appearance-none pr-4 text-xs"
                  style={{ minWidth: 0 }}
                >
                  {options.map(opt => (
                    <option key={opt} value={opt}>{opt}</option>
                  ))}
                </select>
                <ChevronDown className="w-3 h-3 text-gray-400 -ml-3 pointer-events-none" />
              </div>
            </div>
          )
        })}
      </div>

      {hasActive && (
        <button
          onClick={onResetFilters}
          className="flex items-center gap-1 ml-1 px-2 py-1 text-xs text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-md transition-colors"
        >
          <RotateCcw className="w-3 h-3" />
          Reset
        </button>
      )}
    </div>
  )
}
