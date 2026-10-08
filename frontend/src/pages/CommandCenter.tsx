import { useState } from 'react'
import { KpiCards } from '@/components/dashboard/KpiCards'
import { SentimentOverview } from '@/components/dashboard/SentimentOverview'
import { IssuePipeline } from '@/components/dashboard/IssuePipeline'
import { TopIssues } from '@/components/dashboard/TopIssues'
import { AspectSentimentChart } from '@/components/dashboard/AspectSentimentChart'
import { PlatformComparison } from '@/components/dashboard/PlatformComparison'
import { ReviewFeed } from '@/components/dashboard/ReviewFeed'
import { AiInsights } from '@/components/dashboard/AiInsights'
import { IssueDetailPanel } from '@/components/issues/IssueDetailPanel'
import {
  kpis,
  sentimentTrend,
  aspectSentimentData,
  issues,
  reviews,
  platforms,
  insights,
  topIssues,
} from '@/data/mockData'
import type { FilterState, Issue, Insight, Review } from '@/types'

interface CommandCenterProps {
  filters: FilterState
}

export function CommandCenter({ filters: _filters }: CommandCenterProps) {
  const [selectedIssue, setSelectedIssue] = useState<Issue | null>(null)
  const [panelOpen,     setPanelOpen]     = useState(false)

  const openIssue = (issue: Issue) => {
    setSelectedIssue(issue)
    setPanelOpen(true)
  }

  const closePanel = () => {
    setPanelOpen(false)
    setTimeout(() => setSelectedIssue(null), 300)
  }

  const handleInvestigate = (_insight: Insight) => {
    // Placeholder — will link to full investigation view in next phase
    const related = issues.find(i => i.category === _insight.affectedAspect.toLowerCase())
    if (related) openIssue(related)
  }

  const handleReviewClick = (_review: Review) => {
    // Placeholder — will open review detail in next phase
    console.log('Review clicked:', _review.id)
  }

  return (
    <>
      <div className="px-6 py-5 max-w-[1600px] mx-auto">
        {/* Page header */}
        <div className="mb-5">
          <h1 className="text-lg font-bold text-gray-900">Review Intelligence Command Center</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Monitor customer sentiment, emerging issues and vehicle-level feedback signals.
          </p>
        </div>

        {/* ── Row 1: KPIs ──────────────────────────────────────────────────── */}
        <KpiCards kpis={kpis} />

        {/* ── Row 2: Sentiment overview + Aspect sentiment ─────────────────── */}
        <div className="mt-4 grid grid-cols-1 lg:grid-cols-[1fr_420px] gap-4">
          <SentimentOverview data={sentimentTrend} />
          <AspectSentimentChart data={aspectSentimentData} />
        </div>

        {/* ── Row 3: Issue Pipeline ─────────────────────────────────────────── */}
        <div className="mt-4 bg-white border border-gray-200 rounded-xl p-4">
          <IssuePipeline issues={issues} onIssueClick={openIssue} />
        </div>

        {/* ── Row 4: Top Issues + Platform Comparison ───────────────────────── */}
        <div className="mt-4 grid grid-cols-1 lg:grid-cols-2 gap-4">
          <TopIssues issues={topIssues} onIssueClick={openIssue} />
          <PlatformComparison platforms={platforms} />
        </div>

        {/* ── Row 5: Review Feed + AI Insights ─────────────────────────────── */}
        <div className="mt-4 grid grid-cols-1 lg:grid-cols-[1fr_420px] gap-4 pb-8">
          <ReviewFeed reviews={reviews} onReviewClick={handleReviewClick} />
          <AiInsights insights={insights} onInvestigate={handleInvestigate} />
        </div>
      </div>

      {/* Issue detail slide-over */}
      <IssueDetailPanel
        issue={selectedIssue}
        open={panelOpen}
        onClose={closePanel}
      />
    </>
  )
}
