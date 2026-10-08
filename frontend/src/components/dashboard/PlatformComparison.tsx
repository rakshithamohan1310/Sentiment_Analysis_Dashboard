import {
  MessageCircle,
  Play,
  Users,
  Star,
  Hash,
  MoreHorizontal,
  LucideIcon,
} from 'lucide-react'
import { Card, CardHeader } from '@/components/common/Card'
import { TrendBadge } from '@/components/common/TrendBadge'
import { SentimentBar } from '@/components/common/SentimentBar'
import type { Platform } from '@/types'

const ICON_MAP: Record<string, LucideIcon> = {
  MessageCircle,
  Play,
  Users,
  Star,
  Hash,
  MoreHorizontal,
}

interface PlatformRowProps {
  platform: Platform
}

function PlatformRow({ platform }: PlatformRowProps) {
  const Icon = ICON_MAP[platform.icon] ?? MessageCircle

  return (
    <div className="grid items-center gap-3 py-2.5 border-b border-gray-50 last:border-0"
      style={{ gridTemplateColumns: '24px 1fr 80px 70px 1fr' }}>

      {/* Icon */}
      <div className="flex items-center justify-center">
        <Icon className="w-4 h-4 text-gray-400" />
      </div>

      {/* Name + top issue */}
      <div className="min-w-0">
        <div className="text-xs font-semibold text-gray-800">{platform.name}</div>
        <div className="text-[10px] text-gray-400 truncate mt-0.5">{platform.topIssue}</div>
      </div>

      {/* Volume */}
      <div className="text-right">
        <div className="text-xs font-semibold text-gray-700">
          {platform.reviewCount >= 1000
            ? `${(platform.reviewCount / 1000).toFixed(1)}k`
            : platform.reviewCount}
        </div>
        <div className="text-[10px] text-gray-400">reviews</div>
      </div>

      {/* Negative % */}
      <div className="text-right">
        <div className="text-xs font-semibold text-red-500">{platform.negativePct}%</div>
        <div className="flex justify-end mt-0.5">
          <TrendBadge value={platform.trend} positive={false} size="xs" />
        </div>
      </div>

      {/* Sentiment bar */}
      <SentimentBar
        positive={platform.positivePct}
        neutral={platform.neutralPct}
        negative={platform.negativePct}
        height="sm"
      />
    </div>
  )
}

interface PlatformComparisonProps {
  platforms: Platform[]
}

export function PlatformComparison({ platforms }: PlatformComparisonProps) {
  return (
    <Card>
      <CardHeader
        title="Platform Comparison"
        subtitle="Review volume and sentiment by source"
      />

      {/* Column headers */}
      <div className="grid text-[10px] text-gray-400 font-medium mb-1 px-0"
        style={{ gridTemplateColumns: '24px 1fr 80px 70px 1fr' }}>
        <span />
        <span>Platform</span>
        <span className="text-right">Volume</span>
        <span className="text-right">Neg %</span>
        <span className="text-center">Sentiment</span>
      </div>

      <div>
        {platforms.map(p => (
          <PlatformRow key={p.id} platform={p} />
        ))}
      </div>
    </Card>
  )
}
