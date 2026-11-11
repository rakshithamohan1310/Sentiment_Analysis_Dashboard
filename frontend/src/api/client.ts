export type QueryValue = string | number | boolean | undefined | null

export function toQuery(params: Record<string, QueryValue>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '' || value === false) continue
    search.set(key, String(value))
  }
  const qs = search.toString()
  return qs ? `?${qs}` : ''
}

export async function apiGet<T>(path: string, params: Record<string, QueryValue> = {}): Promise<T> {
  const response = await fetch(`${path}${toQuery(params)}`, {
    headers: { Accept: 'application/json' },
  })
  if (!response.ok) {
    let detail = response.statusText || 'Request failed'
    try {
      const body = await response.json() as { detail?: unknown }
      if (typeof body.detail === 'string' && body.detail) detail = body.detail
    } catch {
      // Response was not JSON.
    }
    throw new Error(`${response.status} ${detail}`)
  }
  return response.json() as Promise<T>
}
