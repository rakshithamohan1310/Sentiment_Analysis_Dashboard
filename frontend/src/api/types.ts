export interface SentimentBreakdown {
  positive_count: number
  neutral_count: number
  negative_count: number
  total: number
  positive_pct: number
  neutral_pct: number
  negative_pct: number
}

export interface SentimentSummaryResponse {
  overall: SentimentBreakdown
  by_source: Record<string, SentimentBreakdown>
  synthetic_excluded: boolean
}

export interface TrendPointResponse {
  period: string
  total: number
  positive_count: number
  neutral_count: number
  negative_count: number
  positive_pct: number
  neutral_pct: number
  negative_pct: number
}

export interface SentimentTrendResponse {
  granularity: 'day' | 'week' | 'month'
  points: TrendPointResponse[]
  synthetic_excluded: boolean
}

export interface AspectSummaryResponse {
  category: string
  aspect: string
  mention_count: number
  positive_count: number
  neutral_count: number
  negative_count: number
  positive_pct: number
  neutral_pct: number
  negative_pct: number
  negative_aspect_pct: number
}

export interface AspectsResponse {
  aspects: AspectSummaryResponse[]
  synthetic_excluded: boolean
}

export interface AspectExample {
  matched_text: string | null
  sentiment_label: string | null
  source: string
  published_at: string | null
}

export interface AspectDetailResponse {
  aspect: string
  summary: AspectSummaryResponse
  recent_examples: AspectExample[]
  synthetic_excluded: boolean
}

export interface ReviewAspectResponse {
  id: number
  category: string
  aspect: string
  sentiment_label: string | null
  sentiment_score: number | null
  confidence: number | null
  matched_text: string | null
}

export interface ReviewResponse {
  review_id: number
  source: string
  source_record_id: string
  published_at: string | null
  title: string | null
  review_text: string | null
  language: string | null
  vehicle_type: string | null
  manufacturer: string | null
  vehicle_model: string | null
  vehicle_category: string | null
  sentiment_label: string | null
  sentiment_score: number | null
  sentiment_confidence: number | null
  is_duplicate: boolean
  processing_status: string
  synthetic: boolean
  engagement_count: number
  aspects: ReviewAspectResponse[]
}

export interface ReviewsResponse {
  total: number
  limit: number
  offset: number
  items: ReviewResponse[]
}

export interface CollectionRunResponse {
  run_id: number
  source: string
  status: string
  started_at: string
  completed_at: string | null
  records_found: number
  records_inserted: number
  duplicates: number
  rejected: number
  errors: number
  error_detail: string | null
}

export interface CollectionStatusResponse {
  total_runs: number
  runs: CollectionRunResponse[]
}

export interface ReviewOptionsResponse {
  manufacturers: string[]
  vehicle_models: string[]
}

export interface DashboardParams {
  source?: string
  sentiment?: string
  date_from?: string
  date_to?: string
  include_synthetic?: boolean
  manufacturer?: string
  vehicle_model?: string
  vehicle_category?: string
  granularity?: 'day' | 'week' | 'month'
}
