import { MessageCircle, Play, LucideIcon } from 'lucide-react'
import { Card, CardHeader } from '@/components/common/Card'
import { SentimentBar } from '@/components/common/SentimentBar'
import type { Platform } from '@/types'

const ICON_MAP: Record<string, LucideIcon> = {
  MessageCircle,
  Play,
}

interface PlatformComparisonProps {
  platforms: Platform[]
}

export function PlatformComparison({ platforms }: PlatformComparisonProps) {
  return (
    <Card>
      <CardHeader
        title="Source comparison"
        subtitle="Processed feedback volume and sentiment by source"
      />

      <div className="grid text-[10px] text-gray-400 font-medium mb-1"
        style={{ gridTemplateColumns: '24px 1fr 80px 70px 1fr' }}>
        <span />
        <span>Source</span>
        <span className="text-right">Volume</span>
        <span className="text-right">Neg %</span>
        <span className="text-center">Sentiment</span>
      </div>

      <div>
        {platforms.map(platform => {
          const Icon = ICON_MAP[platform.icon] ?? MessageCircle
          return (
            <div
              key={platform.id}
              className="grid items-center gap-3 py-2.5 border-b border-gray-50 last:border-0"
              style={{ gridTemplateColumns: '24px 1fr 80px 70px 1fr' }}
            >
              <div className="flex items-center justify-center">
                <Icon className="w-4 h-4 text-gray-400" />
              </div>
              <div className="min-w-0">
                <div className="text-xs font-semibold text-gray-800">{platform.name}</div>
                <div className="text-[10px] text-gray-400 truncate mt-0.5">{platform.topIssue}</div>
              </div>
              <div className="text-right">
                <div className="text-xs font-semibold text-gray-700">{platform.reviewCount}</div>
                <div className="text-[10px] text-gray-400">reviews</div>
              </div>
              <div className="text-right">
                <div className="text-xs font-semibold text-red-500">{platform.negativePct}%</div>
              </div>
              <SentimentBar
                positive={platform.positivePct}
                neutral={platform.neutralPct}
                negative={platform.negativePct}
                height="sm"
              />
            </div>
          )
        })}
      </div>
    </Card>
  )
}
