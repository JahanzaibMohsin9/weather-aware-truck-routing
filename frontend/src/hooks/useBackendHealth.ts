import { useEffect, useState } from 'react'
import { apiGet } from '../api/client'

type Health = 'checking…' | 'connected' | 'unreachable'

export function useBackendHealth(): Health {
  const [health, setHealth] = useState<Health>('checking…')

  useEffect(() => {
    const controller = new AbortController()
    apiGet<{ status: string }>('/api/health', controller.signal)
      .then(() => setHealth('connected'))
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          console.error(error)
          setHealth('unreachable')
        }
      })
    return () => controller.abort()
  }, [])

  return health
}
