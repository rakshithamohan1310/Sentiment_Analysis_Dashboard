// ─── Navigation ──────────────────────────────────────────────────────────────

export type NavPage =
  | 'command-center'
  | 'reviews'
  | 'vehicles'
  | 'battery'
  | 'charging'
  | 'platforms'
  | 'issues'
  | 'predictions'
  | 'customer-journeys'
  | 'insights'
  | 'reports'
  | 'domain'
  | 'data-sources'
  | 'settings'

// ─── Filters ─────────────────────────────────────────────────────────────────

export interface FilterState {
  domain: string
  timeRange: string
  platform: string
  vehicle: string
  sentiment: string
}

// ─── Sentiment ───────────────────────────────────────────────────────────────

export type SentimentLabel = 'positive' | 'neutral' | 'negative' | 'mixed'

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
  change: number          // percent, positive = up
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
  trend: number
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

export interface AspectSentimentRow {
  aspect: string
  positive: number
  neutral: number
  negative: number
  total: number
}
