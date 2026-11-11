import { ThumbsUp } from 'lucide-react'
import { Card, CardHeader } from '@/components/common/Card'
import { SentimentBadge } from '@/components/common/Badge'
import type { Review, SentimentLabel } from '@/types'

const SENTIMENT_LEFT: Record<SentimentLabel, string> = {
  positive: 'border-l-emerald-400',
  negative: 'border-l-red-400',
  neutral:  'border-l-gray-300',
}

function isSentiment(value: string): value is SentimentLabel {
  return value === 'positive' || value === 'neutral' || value === 'negative'
}

interface ReviewFeedProps {
  reviews: Review[]
  total: number
}

export function ReviewFeed({ reviews, total }: ReviewFeedProps) {
  return (
    <Card>
      <CardHeader
        title="Recent customer feedback"
        subtitle={`${total.toLocaleString()} processed items match this filter. Showing ${reviews.length}.`}
      />
      <div className="space-y-2">
        {reviews.map(review => {
          const sentiment = isSentiment(review.sentiment) ? review.sentiment : 'neutral'
          const when = review.date ? new Date(review.date) : null
          const whenLabel = when && !Number.isNaN(when.getTime())
            ? when.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
            : 'No publish date'
          return (
            <article
              key={review.id}
              className={`border-l-2 ${SENTIMENT_LEFT[sentiment]} bg-white border border-gray-200 rounded-lg p-3`}
            >
              <div className="flex items-center gap-1.5 flex-wrap mb-2">
                <SentimentBadge sentiment={sentiment} size="xs" />
                <span className="text-[10px] font-medium text-amber-800 bg-amber-50 border border-amber-100 rounded-full px-1.5 py-0.5">
                  Customer-reported
                </span>
                {review.aspects.slice(0, 2).map(aspect => (
                  <span key={aspect} className="text-[10px] text-gray-500 bg-gray-50 border border-gray-200 rounded-full px-1.5 py-0.5 font-medium capitalize">
                    {aspect.replace(/_/g, ' ')}
                  </span>
                ))}
              </div>
              <p className="text-xs text-gray-700 leading-relaxed line-clamp-3 mb-2.5">
                {review.text || 'No review text stored.'}
              </p>
              <div className="flex items-center gap-2 text-[10px] text-gray-400 flex-wrap">
                {review.vehicle && <span className="font-medium text-gray-600">{review.vehicle}</span>}
                <span className="capitalize">{review.platform}</span>
                <span>{whenLabel}</span>
                {review.sentimentScore > 0 && (
                  <span>Label confidence {Math.round(review.sentimentScore * 100)}%</span>
                )}
                {review.upvotes > 0 && (
                  <span className="flex items-center gap-0.5">
                    <ThumbsUp className="w-2.5 h-2.5" />
                    {review.upvotes}
                  </span>
                )}
              </div>
            </article>
          )
        })}
      </div>
    </Card>
  )
}
