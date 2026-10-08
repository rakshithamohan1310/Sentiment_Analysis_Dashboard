import { useState } from 'react'
import { AppShell } from '@/components/layout/AppShell'
import { CommandCenter } from '@/pages/CommandCenter'
import { PlaceholderPage } from '@/pages/PlaceholderPage'
import type { NavPage, FilterState } from '@/types'

const DEFAULT_FILTERS: FilterState = {
  domain: 'EV',
  timeRange: 'Last 30 days',
  platform: 'All Platforms',
  vehicle: 'All Vehicles',
  sentiment: 'All Sentiment',
}

export default function App() {
  const [activePage, setActivePage] = useState<NavPage>('command-center')
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS)

  const updateFilter = (key: keyof FilterState, value: string) => {
    setFilters(prev => ({ ...prev, [key]: value }))
  }

  const resetFilters = () => setFilters(DEFAULT_FILTERS)

  return (
    <AppShell
      activePage={activePage}
      onNavigate={setActivePage}
      filters={filters}
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
