import { useEffect, useState } from 'react'
import { Box, CircularProgress, LinearProgress, Stack, Typography } from '@mui/material'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import RadioButtonUncheckedIcon from '@mui/icons-material/RadioButtonUnchecked'
import type { PlanProgress as Progress } from '../api/client'

// The server's steps, in order. "alternatives" is part of finding routes.
const STAGES = [
  { label: 'Look up places', steps: ['places'] },
  { label: 'Find truck routes', steps: ['routes', 'alternatives'] },
  { label: 'Check the forecast along each route', steps: ['forecast'] },
  { label: 'Score risk and rank the routes', steps: ['scoring'] },
]

interface Props {
  events: Progress[]
  startedAt: number
}

/** What the planning wait is spent on, step by step, with the live server message. */
export default function PlanProgress({ events, startedAt }: Props) {
  const elapsed = useElapsedSeconds(startedAt)
  const last = events.at(-1)
  const current = last ? STAGES.findIndex((s) => s.steps.includes(last.step)) : 0

  return (
    <Box sx={{ px: 2, pb: 2 }} role="status" aria-live="polite">
      <LinearProgress sx={{ mb: 1.5 }} />
      <Stack spacing={0.75}>
        {STAGES.map((stage, i) => {
          const state = i < current ? 'done' : i === current ? 'active' : 'waiting'
          return (
            <Stack key={stage.label} direction="row" spacing={1} sx={{ alignItems: 'flex-start' }}>
              <Box sx={{ width: 20, height: 20, display: 'grid', placeItems: 'center', flexShrink: 0, mt: '1px' }}>
                {state === 'done' && <CheckCircleIcon sx={{ fontSize: 18, color: 'success.main' }} />}
                {state === 'active' && <CircularProgress size={14} thickness={5} />}
                {state === 'waiting' && <RadioButtonUncheckedIcon sx={{ fontSize: 18, color: 'action.disabled' }} />}
              </Box>
              <Box sx={{ minWidth: 0 }}>
                <Typography
                  variant="body2"
                  sx={{ fontWeight: state === 'active' ? 600 : 400 }}
                  color={state === 'waiting' ? 'text.disabled' : 'text.primary'}
                >
                  {stage.label}
                </Typography>
                {state === 'active' && last && (
                  <Typography variant="caption" color="text.secondary" component="div">
                    {last.message}…
                  </Typography>
                )}
              </Box>
            </Stack>
          )
        })}
      </Stack>
      <Typography variant="caption" color="text.secondary" component="div" sx={{ mt: 1 }}>
        {elapsed} s · long trips usually take 10–15 s, mostly while TomTom computes truck routes
      </Typography>
    </Box>
  )
}

function useElapsedSeconds(startedAt: number): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [])
  return Math.max(0, Math.floor((now - startedAt) / 1000))
}
