import { Card, CardHeader } from '@/components/common/Card'
import type { CollectionStatusResponse } from '@/api/types'

const SOURCE_LABEL: Record<string, string> = {
  reddit: 'Reddit',
  youtube: 'YouTube',
  demo: 'Demo (synthetic)',
}

function formatWhen(value: string | null): string {
  if (!value) return 'No completion time'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'No completion time'
  return date.toLocaleString()
}

export function SourceStatus({ status }: { status: CollectionStatusResponse }) {
  const runs = status.runs
  const latest = runs[0]
  const lastSuccess = runs.find(run => run.status === 'completed' || run.status === 'partial')

  let freshness = 'No collection runs are recorded.'
  if (latest?.status === 'failed') {
    freshness = `Latest run for ${SOURCE_LABEL[latest.source] ?? latest.source} failed. Sources are not updating automatically.`
  } else if (lastSuccess) {
    freshness = `Last successful collection: ${formatWhen(lastSuccess.completed_at)}. Sources are not updating automatically.`
  } else if (latest) {
    freshness = `Latest run is ${latest.status}. Sources are not updating automatically.`
  }

  return (
    <Card>
      <CardHeader
        title="Source freshness"
        subtitle="From collection runs. There is no scheduler."
      />
      <p className="text-xs text-amber-800 bg-amber-50 border border-amber-100 rounded-lg px-3 py-2 mb-3">
        {freshness}
      </p>
      {runs.length === 0 ? (
        <p className="text-sm text-gray-500">No runs to show.</p>
      ) : (
        <ul className="space-y-2">
          {runs.slice(0, 5).map(run => (
            <li key={run.run_id} className="flex items-start justify-between gap-3 text-xs border-b border-gray-100 pb-2 last:border-0">
              <div>
                <div className="font-semibold text-gray-800 capitalize">
                  {SOURCE_LABEL[run.source] ?? run.source}
                </div>
                <div className="text-gray-400 mt-0.5">
                  {run.records_inserted} inserted · {run.duplicates} duplicates · {run.errors} errors
                </div>
              </div>
              <div className="text-right text-gray-500">
                <div className="font-medium capitalize">{run.status}</div>
                <div>{formatWhen(run.completed_at ?? run.started_at)}</div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
