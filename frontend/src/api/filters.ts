import type { DashboardParams } from './types'
import type { FilterState, TimeRange } from '@/types'

export interface DashboardQuery extends DashboardParams {
  granularity: 'day' | 'week' | 'month'
}

export function filtersToQuery(filters: FilterState): DashboardQuery {
  const query: DashboardQuery = { granularity: granularityFor(filters.timeRange) }
  if (filters.source !== 'all') query.source = filters.source
  if (filters.sentiment !== 'all') query.sentiment = filters.sentiment
  if (filters.includeSynthetic) query.include_synthetic = true
  if (filters.manufacturer !== 'all') query.manufacturer = filters.manufacturer
  if (filters.vehicleModel !== 'all') query.vehicle_model = filters.vehicleModel
  if (filters.vehicleCategory !== 'all') query.vehicle_category = filters.vehicleCategory
  const dateFrom = startOfRange(filters.timeRange)
  if (dateFrom) query.date_from = dateFrom
  return query
}

/** Dropdown values follow source, time, and synthetic scope. Sentiment stays off this request. */
export function reviewOptionParams(filters: FilterState): DashboardParams {
  const query = filtersToQuery({ ...filters, sentiment: 'all', vehicleModel: 'all' })
  return {
    source: query.source,
    date_from: query.date_from,
    date_to: query.date_to,
    include_synthetic: query.include_synthetic,
    manufacturer: query.manufacturer,
  }
}

export function startOfRange(range: TimeRange): string | undefined {
  const days: Record<TimeRange, number | null> = {
    'Last 7 days': 7,
    'Last 30 days': 30,
    'Last 90 days': 90,
    'Last 12 months': 365,
    'All time': null,
  }
  const span = days[range]
  if (span === null) return undefined
  const date = new Date()
  date.setDate(date.getDate() - span)
  return date.toISOString()
}

export function granularityFor(range: TimeRange): 'day' | 'week' | 'month' {
  if (range === 'Last 7 days' || range === 'Last 30 days') return 'day'
  if (range === 'Last 90 days') return 'week'
  return 'month'
}
