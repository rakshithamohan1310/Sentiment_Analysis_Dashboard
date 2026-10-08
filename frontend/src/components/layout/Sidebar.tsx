import { useState } from 'react'
import {
  LayoutDashboard,
  MessageSquare,
  Car,
  Battery,
  Zap,
  Globe,
  AlertTriangle,
  TrendingUp,
  Route,
  Lightbulb,
  FileText,
  ChevronLeft,
  ChevronRight,
  Cpu,
  Database,
  Settings,
  Activity,
} from 'lucide-react'
import { clsx } from 'clsx'
import type { NavPage } from '@/types'

interface NavItem {
  id: NavPage
  label: string
  icon: React.ElementType
  badge?: string
}

const PRIMARY_NAV: NavItem[] = [
  { id: 'command-center',    label: 'Command Center',    icon: LayoutDashboard, badge: undefined },
  { id: 'reviews',           label: 'Reviews',           icon: MessageSquare },
  { id: 'vehicles',          label: 'Vehicles',          icon: Car },
  { id: 'battery',           label: 'Battery',           icon: Battery },
  { id: 'charging',          label: 'Charging',          icon: Zap },
  { id: 'platforms',         label: 'Platforms',         icon: Globe },
  { id: 'issues',            label: 'Issues',            icon: AlertTriangle, badge: '17' },
  { id: 'predictions',       label: 'Predictions',       icon: TrendingUp },
  { id: 'customer-journeys', label: 'Customer Journeys', icon: Route },
  { id: 'insights',          label: 'Insights',          icon: Lightbulb },
  { id: 'reports',           label: 'Reports',           icon: FileText },
]

const SECONDARY_NAV: NavItem[] = [
  { id: 'domain',       label: 'Domain',       icon: Cpu },
  { id: 'data-sources', label: 'Data Sources', icon: Database },
  { id: 'settings',     label: 'Settings',     icon: Settings },
]

interface SidebarProps {
  activePage: NavPage
  onNavigate: (page: NavPage) => void
}

export function Sidebar({ activePage, onNavigate }: SidebarProps) {
  const [collapsed, setCollapsed] = useState(false)

  return (
    <aside
      className={clsx(
        'flex flex-col h-screen bg-gray-900 text-gray-300 transition-all duration-200 shrink-0 relative',
        collapsed ? 'w-[56px]' : 'w-[220px]'
      )}
    >
      {/* Logo */}
      <div className={clsx(
        'flex items-center gap-2.5 px-4 py-4 border-b border-gray-800',
        collapsed && 'justify-center px-0'
      )}>
        <div className="flex items-center justify-center w-7 h-7 bg-blue-600 rounded-lg shrink-0">
          <Activity className="w-4 h-4 text-white" />
        </div>
        {!collapsed && (
          <span className="font-semibold text-white text-sm leading-tight">
            EV Intelligence
          </span>
        )}
      </div>

      {/* Primary nav */}
      <nav className="flex-1 py-3 overflow-y-auto scrollbar-thin">
        <NavGroup
          items={PRIMARY_NAV}
          activePage={activePage}
          onNavigate={onNavigate}
          collapsed={collapsed}
        />

        <div className="mt-2 pt-2 border-t border-gray-800">
          <NavGroup
            items={SECONDARY_NAV}
            activePage={activePage}
            onNavigate={onNavigate}
            collapsed={collapsed}
          />
        </div>
      </nav>

      {/* Collapse toggle */}
      <button
        onClick={() => setCollapsed(c => !c)}
        className="absolute -right-3 top-[72px] w-6 h-6 bg-gray-700 border border-gray-600 rounded-full flex items-center justify-center text-gray-400 hover:text-white hover:bg-gray-600 transition-colors z-10"
        aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
      >
        {collapsed
          ? <ChevronRight className="w-3 h-3" />
          : <ChevronLeft className="w-3 h-3" />
        }
      </button>
    </aside>
  )
}

function NavGroup({
  items,
  activePage,
  onNavigate,
  collapsed,
}: {
  items: NavItem[]
  activePage: NavPage
  onNavigate: (page: NavPage) => void
  collapsed: boolean
}) {
  return (
    <ul className="space-y-0.5 px-2">
      {items.map(item => {
        const Icon = item.icon
        const isActive = item.id === activePage
        return (
          <li key={item.id}>
            <button
              onClick={() => onNavigate(item.id)}
              title={collapsed ? item.label : undefined}
              className={clsx(
                'w-full flex items-center gap-2.5 px-2.5 py-2 rounded-md text-sm transition-colors group relative',
                isActive
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-400 hover:bg-gray-800 hover:text-gray-100'
              )}
            >
              <Icon className="w-4 h-4 shrink-0" />
              {!collapsed && (
                <span className="flex-1 text-left leading-none">{item.label}</span>
              )}
              {!collapsed && item.badge && (
                <span className={clsx(
                  'text-xs font-medium px-1.5 py-0.5 rounded-full',
                  isActive
                    ? 'bg-blue-500 text-white'
                    : 'bg-gray-700 text-gray-300'
                )}>
                  {item.badge}
                </span>
              )}
              {collapsed && item.badge && (
                <span className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 bg-red-500 rounded-full" />
              )}
            </button>
          </li>
        )
      })}
    </ul>
  )
}
