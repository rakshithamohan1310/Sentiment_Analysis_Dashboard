import { apiGet } from './client'
import type {
  AspectDetailResponse,
  AspectsResponse,
  CollectionStatusResponse,
  DashboardParams,
  ReviewOptionsResponse,
  ReviewsResponse,
  SentimentSummaryResponse,
  SentimentTrendResponse,
} from './types'

function shared(params: DashboardParams) {
  return {
    source: params.source,
    date_from: params.date_from,
    date_to: params.date_to,
    include_synthetic: params.include_synthetic,
    manufacturer: params.manufacturer,
    vehicle_model: params.vehicle_model,
    vehicle_category: params.vehicle_category,
  }
}

export function getReviewOptions(params: DashboardParams) {
  return apiGet<ReviewOptionsResponse>('/api/reviews/options', {
    source: params.source,
    date_from: params.date_from,
    date_to: params.date_to,
    include_synthetic: params.include_synthetic,
    manufacturer: params.manufacturer,
  })
}

export function getSentimentSummary(params: DashboardParams) {
  return apiGet<SentimentSummaryResponse>('/api/sentiment/summary', shared(params))
}

export function getSentimentTrend(params: DashboardParams) {
  return apiGet<SentimentTrendResponse>('/api/sentiment/trend', {
    ...shared(params),
    granularity: params.granularity ?? 'month',
  })
}

export function getAspects(params: DashboardParams) {
  return apiGet<AspectsResponse>('/api/aspects', {
    ...shared(params),
    sentiment: params.sentiment,
  })
}

export function getAspectDetail(aspect: string, params: DashboardParams) {
  return apiGet<AspectDetailResponse>(`/api/aspects/${encodeURIComponent(aspect)}`, {
    ...shared(params),
    sentiment: params.sentiment,
    limit: 8,
  })
}

export function getReviews(params: DashboardParams) {
  return apiGet<ReviewsResponse>('/api/reviews', {
    ...shared(params),
    sentiment: params.sentiment,
    limit: 8,
    offset: 0,
  })
}

export function getCollectionStatus(source?: string) {
  return apiGet<CollectionStatusResponse>('/api/collection/status', {
    source,
    limit: 20,
  })
}
