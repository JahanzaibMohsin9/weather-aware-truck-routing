import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from '../api/client'

export interface RequestState<T> {
  data: T | null
  loading: boolean
  error: ApiError | null
}

/**
 * Runs one request at a time: starting a new one aborts the previous, so a
 * slow old response can never overwrite a newer one. With `keepData`, the
 * previous result stays visible while the next one loads.
 */
export function useRequest<Args extends unknown[], T>(
  fn: (...args: [...Args, AbortSignal]) => Promise<T>,
  { keepData = true } = {},
) {
  const [state, setState] = useState<RequestState<T>>({ data: null, loading: false, error: null })
  const controller = useRef<AbortController | null>(null)

  const run = useCallback(
    (...args: Args) => {
      controller.current?.abort()
      const current = new AbortController()
      controller.current = current
      setState((s) => ({ data: keepData ? s.data : null, loading: true, error: null }))
      fn(...args, current.signal)
        .then((data) => {
          if (!current.signal.aborted) setState({ data, loading: false, error: null })
        })
        .catch((error: unknown) => {
          if (current.signal.aborted) return
          const apiError = error instanceof ApiError ? error : new ApiError(0, 'Something went wrong. Please try again.')
          setState((s) => ({ data: s.data, loading: false, error: apiError }))
        })
    },
    [fn, keepData],
  )

  useEffect(() => () => controller.current?.abort(), [])

  return { ...state, run }
}
