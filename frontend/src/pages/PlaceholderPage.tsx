import {
  LayoutDashboard, MessageSquare, Car, Battery, Zap, Globe,
  AlertTriangle, TrendingUp, Route, Lightbulb, FileText,
  Cpu, Database, Settings, LucideIcon,
} from 'lucide-react'
import type { NavPage } from '@/types'

const PAGE_META: Record<NavPage, { label: string; icon: LucideIcon; description: string }> = {
  'command-center':    { label: 'Command Center',    icon: LayoutDashboard, description: 'Overview of all review signals and issues.' },
  'reviews':           { label: 'Reviews',           icon: MessageSquare,   description: 'Browse, filter and search all collected reviews.' },
  'vehicles':          { label: 'Vehicles',          icon: Car,             description: 'Sentiment and issues broken down by vehicle model.' },
  'battery':           { label: 'Battery',           icon: Battery,         description: 'Deep-dive into battery-related customer signals.' },
  'charging':          { label: 'Charging',          icon: Zap,             description: 'Charging speed, reliability and cost complaints.' },
  'platforms':         { label: 'Platforms',         icon: Globe,           description: 'Compare sentiment and volume across data sources.' },
  'issues':            { label: 'Issues',            icon: AlertTriangle,   description: 'Full issue registry with lifecycle management.' },
  'predictions':       { label: 'Predictions',       icon: TrendingUp,      description: 'Trend forecasts and emerging signal detection.' },
  'customer-journeys': { label: 'Customer Journeys', icon: Route,           description: 'Trace how issues evolve across ownership stages.' },
  'insights':          { label: 'Insights',          icon: Lightbulb,       description: 'AI-generated pattern analysis and recommendations.' },
  'reports':           { label: 'Reports',           icon: FileText,        description: 'Export and schedule automated reports.' },
  'domain':            { label: 'Domain',            icon: Cpu,             description: 'Configure the active analysis domain and categories.' },
  'data-sources':      { label: 'Data Sources',      icon: Database,        description: 'Manage platform connectors and data ingestion.' },
  'settings':          { label: 'Settings',          icon: Settings,        description: 'Application preferences and user management.' },
}

interface PlaceholderPageProps {
  page: NavPage
}

export function PlaceholderPage({ page }: PlaceholderPageProps) {
  const meta = PAGE_META[page] ?? PAGE_META['reviews']
  const Icon = meta.icon

  return (
    <div className="flex flex-col items-center justify-center h-full min-h-[60vh] px-6">
      <div className="text-center max-w-sm">
        <div className="w-14 h-14 bg-gray-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
          <Icon className="w-7 h-7 text-gray-400" />
        </div>
        <h2 className="text-base font-semibold text-gray-900 mb-1">{meta.label}</h2>
        <p className="text-sm text-gray-500 mb-5">{meta.description}</p>
        <div className="inline-flex items-center gap-2 bg-blue-50 text-blue-700 border border-blue-100 rounded-full px-4 py-2 text-xs font-medium">
          <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-pulse" />
          Coming in the next build phase
        </div>
      </div>
    </div>
  )
}
