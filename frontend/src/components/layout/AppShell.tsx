import type { ReactNode } from 'react'
import { Sidebar } from './Sidebar'
import { Header } from './Header'
import { FilterBar } from './FilterBar'
import type { NavPage, FilterState } from '@/types'

interface AppShellProps {
  activePage: NavPage
  onNavigate: (page: NavPage) => void
  filters: FilterState
  onFilterChange: (key: keyof FilterState, value: string) => void
  onResetFilters: () => void
  children: ReactNode
}

export function AppShell({
  activePage,
  onNavigate,
  filters,
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
