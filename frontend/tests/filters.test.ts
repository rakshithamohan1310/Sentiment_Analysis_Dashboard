import assert from 'node:assert/strict'
import test from 'node:test'
import { filtersToQuery, reviewOptionParams } from '../src/api/filters.ts'
import type { FilterState } from '../src/types/index.ts'

const base: FilterState = {
  timeRange: 'All time',
  source: 'all',
  sentiment: 'all',
  includeSynthetic: false,
  manufacturer: 'all',
  vehicleModel: 'all',
  vehicleCategory: 'all',
}

test('analytics query includes manufacturer and model and omits body style', () => {
  const query = filtersToQuery({
    ...base,
    source: 'reddit',
    sentiment: 'negative',
    manufacturer: 'Tesla',
    vehicleModel: 'Model_Y',
    vehicleCategory: '4W',
  })
  assert.equal(query.manufacturer, 'Tesla')
  assert.equal(query.vehicle_model, 'Model_Y')
  assert.equal(query.vehicle_category, '4W')
  assert.equal(query.source, 'reddit')
  assert.equal(query.sentiment, 'negative')
  assert.equal(query.date_from, undefined)
  assert.equal('vehicle_type' in query, false)
  assert.equal('state' in query, false)
})

test('all manufacturer and model are left unset', () => {
  const query = filtersToQuery(base)
  assert.equal(query.manufacturer, undefined)
  assert.equal(query.vehicle_model, undefined)
  assert.equal(query.vehicle_category, undefined)
  assert.equal(query.sentiment, undefined)
})

test('option request keeps manufacturer and drops sentiment and model', () => {
  const params = reviewOptionParams({
    ...base,
    timeRange: 'All time',
    sentiment: 'negative',
    manufacturer: 'Hyundai',
    vehicleModel: 'Ioniq5',
  })
  assert.equal(params.manufacturer, 'Hyundai')
  assert.equal(params.vehicle_model, undefined)
  assert.equal(params.sentiment, undefined)
  assert.equal(params.date_from, undefined)
})

test('a bounded time range sends a date and does not invent a manufacturer', () => {
  const query = filtersToQuery({ ...base, timeRange: 'Last 7 days' })
  assert.equal(typeof query.date_from, 'string')
  assert.equal(query.granularity, 'day')
  assert.equal(query.manufacturer, undefined)
  assert.equal(query.vehicle_model, undefined)
})
