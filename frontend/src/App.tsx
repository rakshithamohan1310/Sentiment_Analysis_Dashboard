import { useMemo, useState } from 'react'
import { AppShell } from '@/components/layout/AppShell'
import { CommandCenter } from '@/pages/CommandCenter'
import { PlaceholderPage } from '@/pages/PlaceholderPage'
import { getReviewOptions } from '@/api/dashboard'
import { reviewOptionParams } from '@/api/filters'
import { useApi } from '@/api/useApi'
import type { NavPage, FilterState } from '@/types'

const DEFAULT_FILTERS: FilterState = {
  timeRange: 'Last 30 days',
  source: 'all',
  sentiment: 'all',
  includeSynthetic: false,
  manufacturer: 'all',
  vehicleModel: 'all',
  vehicleCategory: 'all',
}

export default function App() {
  const [activePage, setActivePage] = useState<NavPage>('command-center')
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS)

  const updateFilter = (key: keyof FilterState, value: string | boolean) => {
    setFilters(prev => ({ ...prev, [key]: value }))
  }

  const resetFilters = () => setFilters(DEFAULT_FILTERS)
  const optionParams = useMemo(() => reviewOptionParams(filters), [filters])
  const options = useApi(
    JSON.stringify(optionParams),
    () => getReviewOptions(optionParams),
  )

  return (
    <AppShell
      activePage={activePage}
      onNavigate={setActivePage}
      filters={filters}
      manufacturers={options.data?.manufacturers ?? []}
      vehicleModels={options.data?.vehicle_models ?? []}
      optionsStatus={options.status}
      optionsError={options.error}
      onFilterChange={updateFilter}
      onResetFilters={resetFilters}
    >
      {activePage === 'command-center' && (
        <CommandCenter filters={filters} />
      )}
      {activePage !== 'command-center' && (
        <PlaceholderPage page={activePage} />
      )}
    </AppShell>
  )
}
