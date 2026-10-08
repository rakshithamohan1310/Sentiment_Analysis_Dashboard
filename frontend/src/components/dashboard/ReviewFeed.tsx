import { ThumbsUp, ExternalLink, ChevronRight } from 'lucide-react'
import { Card, CardHeader } from '@/components/common/Card'
import { SentimentBadge, CategoryBadge } from '@/components/common/Badge'
import type { Review } from '@/types'

interface ReviewCardProps {
  review: Review
  onClick: () => void
}

const SENTIMENT_LEFT: Record<string, string> = {
  positive: 'border-l-emerald-400',
  negative: 'border-l-red-400',
  neutral:  'border-l-gray-300',
  mixed:    'border-l-amber-400',
}

function ReviewCard({ review, onClick }: ReviewCardProps) {
  return (
    <button
      onClick={onClick}
      className={`w-full text-left border-l-2 ${SENTIMENT_LEFT[review.sentiment]} bg-white border border-gray-200 rounded-lg p-3 hover:shadow-md hover:border-gray-300 transition-all group`}
    >
      {/* Meta row */}
      <div className="flex items-center gap-1.5 flex-wrap mb-2">
        <SentimentBadge sentiment={review.sentiment} size="xs" />
        {review.aspects.slice(0, 2).map(a => (
          <span key={a} className="text-[10px] text-gray-400 bg-gray-50 border border-gray-200 rounded-full px-1.5 py-0.5 font-medium capitalize">
            {a.replace(/_/g, ' ')}
          </span>
        ))}
        {review.aspects.length > 2 && (
          <span className="text-[10px] text-gray-400">+{review.aspects.length - 2}</span>
        )}
      </div>

      {/* Quote */}
      <p className="text-xs text-gray-700 leading-relaxed line-clamp-2 mb-2.5 group-hover:text-gray-900 transition-colors">
        "{review.text}"
      </p>

      {/* Footer */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-[10px] text-gray-400">
          {review.vehicle && (
            <span className="font-medium text-gray-600">{review.vehicle}</span>
          )}
          {review.vehicle && <span>·</span>}
          <span>{review.platform}</span>
          <span>·</span>
          <span>{new Date(review.date).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}</span>
          {review.upvotes > 0 && (
            <>
              <span>·</span>
              <span className="flex items-center gap-0.5">
                <ThumbsUp className="w-2.5 h-2.5" />
                {review.upvotes >= 1000
                  ? `${(review.upvotes / 1000).toFixed(1)}k`
                  : review.upvotes}
              </span>
            </>
          )}
        </div>
        <ChevronRight className="w-3.5 h-3.5 text-gray-300 group-hover:text-blue-500 transition-colors" />
      </div>
    </button>
  )
}

interface ReviewFeedProps {
  reviews: Review[]
  onReviewClick: (review: Review) => void
}

export function ReviewFeed({ reviews, onReviewClick }: ReviewFeedProps) {
  return (
    <Card>
      <CardHeader
        title="Recent Customer Signals"
        subtitle="Latest reviews across all platforms"
        action={
          <button className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 font-medium transition-colors">
            View all <ExternalLink className="w-3 h-3" />
          </button>
        }
      />
      <div className="space-y-2">
        {reviews.map(r => (
          <ReviewCard key={r.id} review={r} onClick={() => onReviewClick(r)} />
        ))}
      </div>
    </Card>
  )
}
