import { Search, Bell, ChevronDown } from 'lucide-react'
import { useState } from 'react'

export function Header() {
  const [search, setSearch] = useState('')

  return (
    <header className="h-14 bg-white border-b border-gray-200 flex items-center gap-4 px-5 shrink-0 z-10">
      {/* Brand */}
      <div className="flex flex-col leading-tight mr-4">
        <span className="font-semibold text-gray-900 text-sm">EV Review Intelligence</span>
        <span className="text-xs text-gray-500">Customer feedback & issue intelligence</span>
      </div>

      {/* Search */}
      <div className="flex-1 max-w-sm relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
        <input
          type="text"
          placeholder="Search reviews, issues, vehicles…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="w-full pl-9 pr-3 py-1.5 bg-gray-50 border border-gray-200 rounded-md text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
      </div>

      <div className="flex-1" />

      {/* Actions */}
      <div className="flex items-center gap-1">
        {/* Notifications */}
        <button className="relative p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-md transition-colors">
          <Bell className="w-4.5 h-4.5" style={{ width: 18, height: 18 }} />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full" />
        </button>

        {/* Profile */}
        <button className="flex items-center gap-2 ml-1 px-2.5 py-1.5 text-sm text-gray-700 hover:bg-gray-100 rounded-md transition-colors">
          <div className="w-6 h-6 rounded-full bg-blue-600 flex items-center justify-center text-white text-xs font-semibold">
            A
          </div>
          <span className="font-medium hidden sm:block">Analyst</span>
          <ChevronDown className="w-3.5 h-3.5 text-gray-400" />
        </button>
      </div>
    </header>
  )
}
