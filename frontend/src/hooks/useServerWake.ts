import { useEffect, useState } from 'react'
import { api } from '../api/client'

const SLOW_AFTER_MS = 2500

/**
 * Pings the backend on page load. If the server is starting up (after a
 * deploy, or on a host that sleeps idle apps) the first request can be slow,
 * so we say so instead of leaving the user wondering.
 */
export function useServerWake(): 'ready' | 'waking' | 'unreachable' {
  const [state, setState] = useState<'ready' | 'waking' | 'unreachable' | 'checking'>('checking')

  useEffect(() => {
    const controller = new AbortController()
    const slow = window.setTimeout(() => setState((s) => (s === 'checking' ? 'waking' : s)), SLOW_AFTER_MS)
    api
      .health(controller.signal)
      .then(() => setState('ready'))
      .catch(() => {
        if (!controller.signal.aborted) setState('unreachable')
      })
      .finally(() => window.clearTimeout(slow))
    return () => {
      controller.abort()
      window.clearTimeout(slow)
    }
  }, [])

  return state === 'checking' ? 'ready' : state
}
