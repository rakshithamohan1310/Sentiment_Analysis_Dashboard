import { useEffect, useRef, useState } from 'react'

export type ApiStatus = 'idle' | 'loading' | 'ready' | 'error'

export interface ApiState<T> {
  status: ApiStatus
  data: T | null
  error: string | null
  fetchedAt: string | null
}

export function useApi<T>(key: string, loader: () => Promise<T>, enabled = true): ApiState<T> {
  const loaderRef = useRef(loader)
  loaderRef.current = loader
  const [state, setState] = useState<ApiState<T>>({
    status: enabled && key ? 'loading' : 'idle',
    data: null,
    error: null,
    fetchedAt: null,
  })

  useEffect(() => {
    if (!enabled || !key) {
      setState({ status: 'idle', data: null, error: null, fetchedAt: null })
      return
    }
    let cancelled = false
    setState({ status: 'loading', data: null, error: null, fetchedAt: null })
    loaderRef.current()
      .then(data => {
        if (cancelled) return
        setState({
          status: 'ready',
          data,
          error: null,
          fetchedAt: new Date().toISOString(),
        })
      })
      .catch(err => {
        if (cancelled) return
        setState({
          status: 'error',
          data: null,
          error: err instanceof Error ? err.message : 'Request failed',
          fetchedAt: null,
        })
      })
    return () => {
      cancelled = true
    }
  }, [key, enabled])

  return state
}
