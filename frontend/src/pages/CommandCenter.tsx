import { useMemo, useState } from 'react'
import { KpiCards } from '@/components/dashboard/KpiCards'
import { SentimentOverview } from '@/components/dashboard/SentimentOverview'
import { IssuePipeline } from '@/components/dashboard/IssuePipeline'
import { TopIssues } from '@/components/dashboard/TopIssues'
import { AspectSentimentChart } from '@/components/dashboard/AspectSentimentChart'
import { PlatformComparison } from '@/components/dashboard/PlatformComparison'
import { ReviewFeed } from '@/components/dashboard/ReviewFeed'
import { SourceStatus } from '@/components/dashboard/SourceStatus'
import { IssueDetailPanel } from '@/components/issues/IssueDetailPanel'
import { QueryState } from '@/components/common/QueryState'
import {
  getAspectDetail,
  getAspects,
  getCollectionStatus,
  getReviews,
  getSentimentSummary,
  getSentimentTrend,
} from '@/api/dashboard'
import { filtersToQuery } from '@/api/filters'
import { useApi, type ApiStatus } from '@/api/useApi'
import type { AspectSummaryResponse, ReviewResponse, SentimentBreakdown } from '@/api/types'
import type {
  AspectSentimentRow,
  FilterState,
  KPI,
  Platform,
  ReportedMention,
  Review,
  SentimentLabel,
  TrendPoint,
} from '@/types'

interface CommandCenterProps {
  filters: FilterState
}

function aspectLabel(aspect: string): string {
  return aspect.replace(/_/g, ' ')
}

function toMentions(rows: AspectSummaryResponse[]): ReportedMention[] {
  return [...rows]
    .sort((a, b) => b.mention_count - a.mention_count)
    .map(row => ({
      aspect: row.aspect,
      category: row.category,
      label: aspectLabel(row.aspect),
      mentions: row.mention_count,
      positivePct: row.positive_pct,
      neutralPct: row.neutral_pct,
      negativePct: row.negative_pct,
    }))
}

function toChartRows(rows: ReportedMention[]): AspectSentimentRow[] {
  return rows.slice(0, 8).map(row => ({
    aspect: row.label,
    positive: row.positivePct,
    neutral: row.neutralPct,
    negative: row.negativePct,
    total: row.mentions,
  }))
}

function sourceName(source: string): string {
  if (source === 'reddit') return 'Reddit'
  if (source === 'youtube') return 'YouTube'
  if (source === 'demo') return 'Demo'
  return source
}

function toPlatforms(bySource: Record<string, SentimentBreakdown>): Platform[] {
  return Object.entries(bySource).map(([source, breakdown]) => ({
    id: source,
    name: sourceName(source),
    icon: source === 'youtube' ? 'Play' : 'MessageCircle',
    reviewCount: breakdown.total,
    negativePct: breakdown.negative_pct,
    positivePct: breakdown.positive_pct,
    neutralPct: breakdown.neutral_pct,
    topIssue: source === 'demo' ? 'Synthetic demo records' : 'Processed feedback',
  }))
}

function asSentiment(value: string | null): SentimentLabel {
  if (value === 'positive' || value === 'neutral' || value === 'negative') return value
  return 'neutral'
}

function toReview(row: ReviewResponse): Review {
  const vehicle = [row.manufacturer, row.vehicle_model].filter(Boolean).join(' ') || row.vehicle_type
  return {
    id: String(row.review_id),
    text: row.review_text || row.title || '',
    sentiment: asSentiment(row.sentiment_label),
    sentimentScore: row.sentiment_confidence ?? 0,
    aspects: row.aspects.map(aspect => aspect.aspect),
    category: row.aspects[0]?.category ?? '',
    vehicle,
    platform: sourceName(row.source),
    date: row.published_at ?? '',
    severity: null,
    author: '',
    upvotes: row.engagement_count,
    language: row.language ?? '',
  }
}

function negativeDelta(points: { negative_pct: number }[]): number | null {
  if (points.length < 2) return null
  const last = points[points.length - 1].negative_pct
  const prev = points[points.length - 2].negative_pct
  return Math.round((last - prev) * 10) / 10
}

function buildKpis(
  overall: SentimentBreakdown,
  aspects: AspectSummaryResponse[],
  delta: number | null,
  aspectStatus: ApiStatus,
): KPI[] {
  const aspectsReady = aspectStatus === 'ready'
  const batteryMentions = aspects
    .filter(row => row.category === 'battery')
    .reduce((sum, row) => sum + row.mention_count, 0)
  const top = [...aspects].sort((a, b) => b.mention_count - a.mention_count)[0]
  const batteryValue = aspectsReady
    ? batteryMentions.toLocaleString()
    : aspectStatus === 'error' ? 'Unavailable' : '…'
  const topValue = aspectsReady
    ? (top ? aspectLabel(top.aspect) : 'None')
    : aspectStatus === 'error' ? 'Unavailable' : '…'
  return [
    {
      id: 'total-reviews',
      label: 'Feedback items',
      value: overall.total.toLocaleString(),
      change: null,
      changeLabel: '',
      description: 'Processed records, duplicates excluded',
      icon: 'MessageSquare',
      trend: 'flat',
      positive: true,
    },
    {
      id: 'negative-sentiment',
      label: 'Negative share',
      value: `${overall.negative_pct}%`,
      change: delta,
      changeLabel: 'vs previous bucket',
      description: `${overall.negative_count.toLocaleString()} of ${overall.total.toLocaleString()} items`,
      icon: 'TrendingDown',
      trend: delta === null || delta === 0 ? 'flat' : delta > 0 ? 'up' : 'down',
      positive: false,
    },
    {
      id: 'battery-mentions',
      label: 'Battery mentions',
      value: batteryValue,
      change: null,
      changeLabel: '',
      description: 'Customer-reported aspect mentions, not unique reviews',
      icon: 'AlertTriangle',
      trend: 'flat',
      positive: false,
    },
    {
      id: 'top-aspect',
      label: 'Most-mentioned aspect',
      value: topValue,
      change: null,
      changeLabel: '',
      description: aspectsReady
        ? (top ? `${top.mention_count.toLocaleString()} mentions` : 'No aspects in this filter')
        : aspectStatus === 'error' ? 'Aspect request failed' : 'Loading aspect counts',
      icon: 'Globe',
      trend: 'flat',
      positive: true,
    },
  ]
}

export function CommandCenter({ filters }: CommandCenterProps) {
  const [reload, setReload] = useState(0)
  const [selected, setSelected] = useState<ReportedMention | null>(null)
  const query = useMemo(() => filtersToQuery(filters), [filters])
  const queryKey = `${JSON.stringify(query)}:${reload}`

  const summary = useApi(queryKey, () => getSentimentSummary(query))
  const trend = useApi(queryKey, () => getSentimentTrend(query))
  const aspects = useApi(queryKey, () => getAspects(query))
  const reviews = useApi(queryKey, () => getReviews(query))
  const runs = useApi(`${query.source ?? 'all'}:${reload}`, () => getCollectionStatus(query.source))
  const detail = useApi(
    selected ? `${selected.aspect}:${queryKey}` : '',
    () => getAspectDetail(selected!.aspect, query),
    selected !== null,
  )

  const retry = () => setReload(value => value + 1)
  const mentions = aspects.data ? toMentions(aspects.data.aspects) : []
  const trendPoints: TrendPoint[] = (trend.data?.points ?? []).map(point => ({
    period: point.period,
    positive: point.positive_pct,
    neutral: point.neutral_pct,
    negative: point.negative_pct,
    total: point.total,
  }))
  const delta = trend.data ? negativeDelta(trend.data.points) : null
  const fetchedAt = summary.fetchedAt ? new Date(summary.fetchedAt).toLocaleString() : null

  return (
    <>
      <div className="px-6 py-5 max-w-[1600px] mx-auto">
        <div className="mb-5">
          <h1 className="text-lg font-bold text-gray-900">Review Intelligence Command Center</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Counts come from the processed-review API. Customer text is not treated as a confirmed fault.
          </p>
          <p className="text-xs text-gray-400 mt-1">
            {summary.status === 'error'
              ? 'The sentiment summary failed. No saved or demo numbers are shown.'
              : fetchedAt
                ? `Fetched ${fetchedAt}.`
                : 'Waiting for the sentiment summary.'}
            {' '}Sources are not on a schedule, so this view does not update by itself.
          </p>
        </div>

        {filters.includeSynthetic && (
          <div className="mb-4 text-xs text-amber-900 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
            Demo data is included. These records are synthetic and are excluded unless this option is on.
          </div>
        )}

        <QueryState status={summary.status} error={summary.error} onRetry={retry}>
          {summary.data && (
            <KpiCards kpis={buildKpis(summary.data.overall, aspects.data?.aspects ?? [], delta, aspects.status)} />
          )}
        </QueryState>

        <div className="mt-4 grid grid-cols-1 lg:grid-cols-[1fr_420px] gap-4">
          <QueryState
            status={summary.status === 'ready' ? trend.status : summary.status}
            error={trend.error ?? summary.error}
            onRetry={retry}
          >
            {summary.data && trend.data && (
              <SentimentOverview
                data={trendPoints}
                share={{
                  positive: summary.data.overall.positive_pct,
                  neutral: summary.data.overall.neutral_pct,
                  negative: summary.data.overall.negative_pct,
                }}
                subtitle={`${filters.timeRange} · ${trend.data.granularity} buckets · positive, neutral, and negative`}
                negativeDelta={delta}
              />
            )}
          </QueryState>
          <QueryState
            status={aspects.status}
            error={aspects.error}
            empty={mentions.length === 0}
            emptyLabel="No aspect mentions for this filter."
            onRetry={retry}
          >
            <AspectSentimentChart data={toChartRows(mentions)} />
          </QueryState>
        </div>

        <div className="mt-4 bg-white border border-gray-200 rounded-xl p-4">
          <QueryState
            status={aspects.status}
            error={aspects.error}
            empty={mentions.length === 0}
            emptyLabel="No customer-reported aspects for this filter."
            onRetry={retry}
          >
            <IssuePipeline issues={mentions.slice(0, 8)} onIssueClick={setSelected} />
          </QueryState>
        </div>

        <div className="mt-4 grid grid-cols-1 lg:grid-cols-2 gap-4">
          <QueryState
            status={aspects.status}
            error={aspects.error}
            empty={mentions.length === 0}
            emptyLabel="No customer-reported aspects for this filter."
            onRetry={retry}
          >
            <TopIssues issues={mentions.slice(0, 5)} onIssueClick={setSelected} />
          </QueryState>
          <QueryState
            status={summary.status}
            error={summary.error}
            empty={!summary.data || Object.keys(summary.data.by_source).length === 0}
            emptyLabel="No sources in this filter."
            onRetry={retry}
          >
            {summary.data && (
              <PlatformComparison platforms={toPlatforms(summary.data.by_source)} />
            )}
          </QueryState>
        </div>

        <div className="mt-4 grid grid-cols-1 lg:grid-cols-[1fr_420px] gap-4 pb-8">
          <QueryState
            status={reviews.status}
            error={reviews.error}
            empty={!reviews.data || reviews.data.total === 0}
            emptyLabel="No feedback items for this filter."
            onRetry={retry}
          >
            {reviews.data && (
              <ReviewFeed
                reviews={reviews.data.items.map(toReview)}
                total={reviews.data.total}
              />
            )}
          </QueryState>
          <QueryState status={runs.status} error={runs.error} onRetry={retry}>
            {runs.data && <SourceStatus status={runs.data} />}
          </QueryState>
        </div>
      </div>

      <IssueDetailPanel
        issue={selected}
        detail={detail}
        open={selected !== null}
        onClose={() => setSelected(null)}
      />
    </>
  )
}
