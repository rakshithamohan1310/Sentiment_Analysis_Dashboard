import type { ReactNode } from 'react'
import { Sidebar } from './Sidebar'
import { Header } from './Header'
import { FilterBar } from './FilterBar'
import type { NavPage, FilterState } from '@/types'

interface AppShellProps {
  activePage: NavPage
  onNavigate: (page: NavPage) => void
  filters: FilterState
  manufacturers: string[]
  vehicleModels: string[]
  optionsStatus: 'idle' | 'loading' | 'ready' | 'error'
  optionsError: string | null
  onFilterChange: (key: keyof FilterState, value: string | boolean) => void
  onResetFilters: () => void
  children: ReactNode
}

export function AppShell({
  activePage,
  onNavigate,
  filters,
  manufacturers,
  vehicleModels,
  optionsStatus,
  optionsError,
  onFilterChange,
  onResetFilters,
  children,
}: AppShellProps) {
  return (
    <div className="flex h-screen overflow-hidden bg-gray-50">
      <Sidebar activePage={activePage} onNavigate={onNavigate} />

      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        <Header />
        <FilterBar
          filters={filters}
          manufacturers={manufacturers}
          vehicleModels={vehicleModels}
          optionsStatus={optionsStatus}
          optionsError={optionsError}
          onFilterChange={onFilterChange}
          onResetFilters={onResetFilters}
        />
        <main className="flex-1 overflow-y-auto scrollbar-thin">
          {children}
        </main>
      </div>
    </div>
  )
}
