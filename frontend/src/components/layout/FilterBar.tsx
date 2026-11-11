import { ChevronDown, RotateCcw } from 'lucide-react'
import { clsx } from 'clsx'
import type { FilterState, SentimentFilter, SourceFilter, TimeRange } from '@/types'

interface FilterBarProps {
  filters: FilterState
  manufacturers: string[]
  vehicleModels: string[]
  optionsStatus: 'idle' | 'loading' | 'ready' | 'error'
  optionsError: string | null
  onFilterChange: (key: keyof FilterState, value: string | boolean) => void
  onResetFilters: () => void
}

const TIME_RANGES: TimeRange[] = [
  'Last 7 days',
  'Last 30 days',
  'Last 90 days',
  'Last 12 months',
  'All time',
]

const SOURCES: { value: SourceFilter; label: string }[] = [
  { value: 'all', label: 'All sources' },
  { value: 'reddit', label: 'Reddit' },
  { value: 'youtube', label: 'YouTube' },
]

const VEHICLE_CATEGORIES = [
  { value: 'all', label: 'All categories' },
  { value: '2W', label: '2W' },
  { value: '3W', label: '3W' },
  { value: '4W', label: '4W' },
]

const SENTIMENTS: { value: SentimentFilter; label: string }[] = [
  { value: 'all', label: 'All sentiment' },
  { value: 'positive', label: 'Positive' },
  { value: 'neutral', label: 'Neutral' },
  { value: 'negative', label: 'Negative' },
]

const DEFAULTS: FilterState = {
  timeRange: 'Last 30 days',
  source: 'all',
  sentiment: 'all',
  includeSynthetic: false,
  manufacturer: 'all',
  vehicleModel: 'all',
  vehicleCategory: 'all',
}

function namedOptions(allLabel: string, names: string[], selected: string) {
  const options = [
    { value: 'all', label: allLabel },
    ...names.map(name => ({ value: name, label: name })),
  ]
  if (selected !== 'all' && !names.includes(selected)) {
    options.push({ value: selected, label: selected })
  }
  return options
}

export function FilterBar({
  filters,
  manufacturers,
  vehicleModels,
  optionsStatus,
  optionsError,
  onFilterChange,
  onResetFilters,
}: FilterBarProps) {
  const hasActive =
    filters.timeRange !== DEFAULTS.timeRange ||
    filters.source !== DEFAULTS.source ||
    filters.sentiment !== DEFAULTS.sentiment ||
    filters.includeSynthetic ||
    filters.manufacturer !== DEFAULTS.manufacturer ||
    filters.vehicleModel !== DEFAULTS.vehicleModel ||
    filters.vehicleCategory !== DEFAULTS.vehicleCategory
  const manufacturerLabel = optionsStatus === 'loading' && manufacturers.length === 0
    ? 'Loading…'
    : 'All manufacturers'
  const modelLabel = optionsStatus === 'loading' && vehicleModels.length === 0
    ? 'Loading…'
    : 'All models'

  return (
    <div className="bg-white border-b border-gray-200 px-5 py-2 shrink-0">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs font-medium text-gray-500 mr-1">Filters:</span>

        <Select
          label="Time"
          value={filters.timeRange}
          active={filters.timeRange !== DEFAULTS.timeRange}
          onChange={value => onFilterChange('timeRange', value)}
          options={TIME_RANGES.map(value => ({ value, label: value }))}
        />
        <Select
          label="Source"
          value={filters.source}
          active={filters.source !== 'all'}
          onChange={value => onFilterChange('source', value)}
          options={SOURCES}
        />
        <Select
          label="Sentiment"
          value={filters.sentiment}
          active={filters.sentiment !== 'all'}
          onChange={value => onFilterChange('sentiment', value)}
          options={SENTIMENTS}
        />

        <Select
          label="Manufacturer"
          value={filters.manufacturer}
          active={filters.manufacturer !== 'all'}
          onChange={value => onFilterChange('manufacturer', value)}
          options={namedOptions(manufacturerLabel, manufacturers, filters.manufacturer)}
        />
        <Select
          label="Model"
          value={filters.vehicleModel}
          active={filters.vehicleModel !== 'all'}
          onChange={value => onFilterChange('vehicleModel', value)}
          options={namedOptions(modelLabel, vehicleModels, filters.vehicleModel)}
        />

        <Select
          label="Vehicle category"
          value={filters.vehicleCategory}
          active={filters.vehicleCategory !== 'all'}
          onChange={value => onFilterChange('vehicleCategory', value)}
          options={VEHICLE_CATEGORIES}
        />
        <DisabledSelect label="State / UT" value="Not available" />

        <label className="flex items-center gap-1.5 text-xs text-gray-600 ml-1">
          <input
            type="checkbox"
            checked={filters.includeSynthetic}
            onChange={event => onFilterChange('includeSynthetic', event.target.checked)}
          />
          Include synthetic demo records
        </label>

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
      <p className="text-[11px] text-gray-400 mt-1.5">
        Manufacturer and model use stored review values. Vehicle category is 2W, 3W, or 4W from a recognized model.
        Body style stays separate. State / UT stays disabled.
        Sentiment filters the review list and aspect counts. The sentiment chart keeps all three classes.
        {optionsError ? ` Manufacturer list failed: ${optionsError}` : ''}
        {optionsStatus === 'ready' && manufacturers.length === 0 && vehicleModels.length === 0
          ? ' No stored manufacturer or model values for this source and time range.'
          : ''}
      </p>
    </div>
  )
}

function Select({
  label,
  value,
  active,
  options,
  onChange,
}: {
  label: string
  value: string
  active: boolean
  options: { value: string; label: string }[]
  onChange: (value: string) => void
}) {
  return (
    <div className={clsx(
      'flex items-center gap-1 pl-2.5 pr-1.5 py-1 rounded-md border text-xs font-medium',
      active
        ? 'border-blue-300 bg-blue-50 text-blue-700'
        : 'border-gray-200 bg-gray-50 text-gray-600'
    )}>
      <span className="text-gray-400 text-[10px] font-normal">{label}:</span>
      <select
        aria-label={label}
        value={value}
        onChange={event => onChange(event.target.value)}
        className="bg-transparent border-0 outline-none cursor-pointer font-medium appearance-none pr-4 text-xs"
      >
        {options.map(option => (
          <option key={option.value} value={option.value}>{option.label}</option>
        ))}
      </select>
      <ChevronDown className="w-3 h-3 text-gray-400 -ml-3 pointer-events-none" />
    </div>
  )
}

function DisabledSelect({ label, value }: { label: string; value: string }) {
  return (
    <div
      className="flex items-center gap-1 pl-2.5 pr-2 py-1 rounded-md border border-dashed border-gray-200 bg-gray-50 text-xs text-gray-400"
      title={`${label} is not available from the current API`}
    >
      <span className="text-[10px]">{label}:</span>
      <select aria-label={label} disabled value={value} className="bg-transparent text-xs cursor-not-allowed">
        <option value={value}>{value}</option>
      </select>
    </div>
  )
}
