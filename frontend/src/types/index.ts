// ─── Navigation ──────────────────────────────────────────────────────────────

export type NavPage =
  | 'command-center'
  | 'reviews'
  | 'vehicles'
  | 'battery'
  | 'charging'
  | 'platforms'
  | 'issues'
  | 'customer-journeys'
  | 'insights'
  | 'reports'
  | 'domain'
  | 'data-sources'
  | 'settings'

// ─── Filters ─────────────────────────────────────────────────────────────────

export type TimeRange = 'Last 7 days' | 'Last 30 days' | 'Last 90 days' | 'Last 12 months' | 'All time'
export type SourceFilter = 'all' | 'reddit' | 'youtube'
export type SentimentFilter = 'all' | 'positive' | 'neutral' | 'negative'

export interface FilterState {
  timeRange: TimeRange
  source: SourceFilter
  sentiment: SentimentFilter
  includeSynthetic: boolean
  manufacturer: string
  vehicleModel: string
  vehicleCategory: string
}

// ─── Sentiment ───────────────────────────────────────────────────────────────

export type SentimentLabel = 'positive' | 'neutral' | 'negative'

export interface SentimentBreakdown {
  positive: number
  neutral: number
  negative: number
}

// ─── KPI ─────────────────────────────────────────────────────────────────────

export interface KPI {
  id: string
  label: string
  value: string | number
  change: number | null   // percent vs previous trend bucket; null when the API has no comparison
  changeLabel: string
  description: string
  icon: string            // lucide icon name
  trend: 'up' | 'down' | 'flat'
  positive: boolean       // whether "up" is good for this metric
}

// ─── Aspect ──────────────────────────────────────────────────────────────────

export interface Aspect {
  id: string
  category: string        // e.g. "battery"
  name: string            // e.g. "battery_health"
  label: string           // display label
  sentiment: SentimentBreakdown
  mentions: number
  trend: number           // % change vs previous period
}

// ─── Issue ───────────────────────────────────────────────────────────────────

export type IssueSeverity = 'critical' | 'high' | 'medium' | 'low'
export type IssueStatus   = 'new' | 'investigating' | 'monitoring' | 'resolved'

export interface Issue {
  id: string
  title: string
  description: string
  category: string
  aspect: string
  severity: IssueSeverity
  status: IssueStatus
  mentions: number
  negativePct: number
  trend: number           // % change in mentions
  affectedVehicles: string[]
  affectedPlatforms: string[]
  firstSeen: string       // ISO date
  lastSeen: string
  sampleQuotes: string[]
}

// ─── Review ──────────────────────────────────────────────────────────────────

export interface Review {
  id: string
  text: string
  sentiment: SentimentLabel
  sentimentScore: number   // 0–1
  aspects: string[]
  category: string
  vehicle: string | null
  platform: string
  date: string
  severity: IssueSeverity | null
  author: string           // anonymised
  upvotes: number
  language: string
}

// ─── Platform ────────────────────────────────────────────────────────────────

export interface Platform {
  id: string
  name: string
  icon: string
  reviewCount: number
  negativePct: number
  positivePct: number
  neutralPct: number
  topIssue: string
  trend?: number
}

// ─── AI Insight ──────────────────────────────────────────────────────────────

export type InsightType =
  | 'emerging-pattern'
  | 'sentiment-shift'
  | 'model-specific'
  | 'seasonal'
  | 'platform-anomaly'

export interface Insight {
  id: string
  type: InsightType
  title: string
  description: string
  confidence: number       // 0–100
  affectedAspect: string
  affectedVehicles: string[]
  detectedAt: string
  severity: IssueSeverity
}

// ─── Trend data point ─────────────────────────────────────────────────────────

export interface TrendPoint {
  period: string
  positive: number
  neutral: number
  negative: number
  total: number
}

// ─── Aspect × Sentiment (for bar chart) ──────────────────────────────────────

/** Customer-reported aspect mention. Counts come from GET /api/aspects. */
export interface ReportedMention {
  aspect: string
  category: string
  label: string
  mentions: number
  positivePct: number
  neutralPct: number
  negativePct: number
}

export interface AspectSentimentRow {
  aspect: string
  positive: number
  neutral: number
  negative: number
  total: number
}
