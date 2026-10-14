import { useCallback, useEffect, useRef, useState } from 'react'

export interface AsyncState<T> {
  data: T | undefined
  error: Error | undefined
  loading: boolean
  reload: () => void
}

/** Runs an async loader on mount (and when deps change), with optional polling. */
export function useAsync<T>(loader: () => Promise<T>, deps: unknown[] = [], pollMs?: number): AsyncState<T> {
  const [data, setData] = useState<T>()
  const [error, setError] = useState<Error>()
  const [loading, setLoading] = useState(true)
  const [tick, setTick] = useState(0)
  const loaderRef = useRef(loader)
  loaderRef.current = loader

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    loaderRef.current()
      .then((d) => {
        if (!cancelled) {
          setData(d)
          setError(undefined)
        }
      })
      .catch((e: Error) => !cancelled && setError(e))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick])

  useEffect(() => {
    if (!pollMs) return
    const id = window.setInterval(() => setTick((t) => t + 1), pollMs)
    return () => window.clearInterval(id)
  }, [pollMs])

  const reload = useCallback(() => setTick((t) => t + 1), [])
  return { data, error, loading, reload }
}
