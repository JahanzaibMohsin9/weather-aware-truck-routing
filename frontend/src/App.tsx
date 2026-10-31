import { useCallback, useDeferredValue, useEffect, useState } from 'react'
import { Alert, Box, Chip, Collapse, Divider, Paper, Stack, Typography } from '@mui/material'
import { api, type PlanProgress as PlanProgressEvent } from './api/client'
import ForecastSlider from './components/ForecastSlider'
import Legend from './components/Legend'
import MapView from './components/MapView'
import PlanForm from './components/PlanForm'
import PlanProgress from './components/PlanProgress'
import RouteCards from './components/RouteCards'
import TripSummary from './components/TripSummary'
import { useRequest } from './hooks/useRequest'
import { useServerWake } from './hooks/useServerWake'
import type { PlanRequest, PlanResponse } from './types'
import type { HeatMode } from './utils/heat'

/** The route to show first: the recommended one, else the best-ranked. */
function defaultRouteId(plan: PlanResponse | null): string | null {
  if (!plan) return null
  return plan.recommended_route_id ?? [...plan.routes].sort((a, b) => a.rank - b.rank)[0]?.id ?? null
}

export default function App() {
  const server = useServerWake()
  // Planning streams its progress; keep the steps for the progress list.
  const [progress, setProgress] = useState<{ startedAt: number; events: PlanProgressEvent[] }>({
    startedAt: 0,
    events: [],
  })
  const planWithProgress = useCallback((body: PlanRequest, signal: AbortSignal) => {
    setProgress({ startedAt: Date.now(), events: [] })
    return api.planStream(body, (event) => setProgress((p) => ({ ...p, events: [...p.events, event] })), signal)
  }, [])
  const plan = useRequest(planWithProgress)
  const heat = useRequest(api.heatmap, { keepData: false })
  const { run: runHeat } = heat

  // Selection and slider hour are tied to the plan / heatmap they were made
  // on, so a new result resets them without extra renders.
  const [selection, setSelection] = useState<{ plan: PlanResponse | null; id: string | null }>({ plan: null, id: null })
  const selectedId = selection.plan === plan.data ? selection.id : defaultRouteId(plan.data)
  const onSelect = (id: string) => setSelection({ plan: plan.data, id })

  const [hourState, setHourState] = useState<{ heat: unknown; hour: number }>({ heat: null, hour: 0 })
  const hour = hourState.heat === heat.data ? hourState.hour : 0
  const heatData = heat.data
  const onHour = useCallback((h: number) => setHourState({ heat: heatData, hour: h }), [heatData])
  // The slider follows the pointer immediately; the map renders the latest
  // hour at lower priority, skipping steps if it falls behind a fast drag.
  const mapHour = useDeferredValue(hour)
  const [heatMode, setHeatMode] = useState<HeatMode>('risk')

  // After a plan the form folds into a one-line summary; Edit reopens it.
  // Tied to the plan it was opened on, so the next plan folds it again.
  const [editing, setEditing] = useState<{ plan: PlanResponse | null; open: boolean }>({ plan: null, open: false })
  const showForm = !plan.data || !!plan.error || (editing.plan === plan.data && editing.open)
  const coveredPoints = heat.data?.points.filter((p) => p.score[mapHour] != null).length ?? 0
  const totalPoints = heat.data?.points.length ?? 0

  // Load the heatmap for a new plan's corridor in the background.
  useEffect(() => {
    if (!plan.data) return
    runHeat({
      routes: plan.data.routes.map((r) => r.checkpoints.map((cp) => [cp.lng, cp.lat] as [number, number])),
      load_lbs: plan.data.load_lbs,
      start: plan.data.departure,
    })
  }, [plan.data, runHeat])

  return (
    <Box sx={{ display: 'flex', flexDirection: { xs: 'column-reverse', md: 'row' }, height: '100dvh' }}>
      <Paper
        square
        elevation={2}
        sx={{
          width: { xs: '100%', md: 400 },
          flexShrink: 0,
          overflowY: 'auto',
          zIndex: 1,
          height: { xs: '50dvh', md: '100%' },
        }}
      >
        <Box
          component="header"
          sx={{ px: 2, py: 1.75, bgcolor: 'primary.main', color: 'primary.contrastText', display: 'flex', gap: 1.5, alignItems: 'center' }}
        >
          <Box component="img" src="/favicon.svg" alt="" sx={{ width: 34, height: 34, borderRadius: 1.5, boxShadow: 2 }} />
          <Box>
            <Typography variant="h6" component="h1" sx={{ lineHeight: 1.2 }}>
              Weather-Aware Truck Routing
            </Typography>
            <Typography variant="caption" sx={{ opacity: 0.85 }}>
              Pick the safest of three truck routes, by the weather at the hour you'll be there
            </Typography>
          </Box>
        </Box>
        <Box sx={{ p: 2 }}>
          {server === 'waking' && (
            <Alert severity="info" sx={{ mb: 2 }}>
              The server is taking a moment to respond. It may be starting up; this can take up to a minute.
            </Alert>
          )}
          {server === 'unreachable' && (
            <Alert severity="warning" sx={{ mb: 2 }}>
              Can't reach the server right now. You can still try planning; it may be starting up.
            </Alert>
          )}
          {/* The form stays mounted (keeping what was typed) and folds into a summary after planning. */}
          <Collapse in={showForm} unmountOnExit={false}>
            <PlanForm loading={plan.loading} fieldErrors={plan.error?.fieldErrors ?? {}} onSubmit={plan.run} />
          </Collapse>
          {!showForm && plan.data && <TripSummary plan={plan.data} onEdit={() => setEditing({ plan: plan.data, open: true })} />}
        </Box>
        {plan.loading && <PlanProgress events={progress.events} startedAt={progress.startedAt} />}
        {plan.error && !Object.keys(plan.error.fieldErrors).length && (
          <Alert severity="error" sx={{ mx: 2, mb: 2 }}>
            {plan.error.message}
          </Alert>
        )}
        {plan.data && (
          <>
            <Divider />
            <Stack spacing={1.5} sx={{ p: 2, opacity: plan.loading ? 0.5 : 1 }}>
              <Alert severity={plan.data.recommended_route_id ? 'success' : 'warning'} variant="outlined">
                {plan.data.explanation}
              </Alert>
              {plan.data.notes.map((note) => (
                <Alert key={note} severity="info" variant="outlined">
                  {note}
                </Alert>
              ))}
              <RouteCards routes={plan.data.routes} selectedId={selectedId} onSelect={onSelect} />
            </Stack>
          </>
        )}
      </Paper>

      <Box sx={{ flex: 1, position: 'relative', minHeight: 0 }}>
        <MapView
          plan={plan.data}
          selectedId={selectedId}
          onSelect={onSelect}
          heatmap={heat.data}
          hour={mapHour}
          heatMode={heatMode}
        />
        {plan.data && (
          <Box sx={{ position: 'absolute', top: 12, left: 12, zIndex: 4 }}>
            <Legend heat={heat.data ? { mode: heatMode, onMode: setHeatMode, scales: heat.data.scales } : undefined} />
          </Box>
        )}
        {/* Above the map's markers (route labels, truck) so they never cover the controls. */}
        <Box sx={{ position: 'absolute', left: 12, right: 48, bottom: 28, maxWidth: 720, mx: 'auto', zIndex: 4 }}>
          {heat.data ? (
            <Stack spacing={1}>
              {(!totalPoints || coveredPoints < totalPoints) && (
                <Alert severity="warning" sx={{ boxShadow: 2 }}>
                  {coveredPoints === 0
                    ? 'No weather forecast is available for this map hour. An empty heatmap does not mean safe conditions.'
                    : `Forecast missing for ${totalPoints - coveredPoints} of ${totalPoints} corridor locations at this hour. Unshaded areas may have no data.`}
                </Alert>
              )}
              <ForecastSlider
                hours={heat.data.hours}
                hour={hour}
                onChange={onHour}
                route={plan.data?.routes.find((r) => r.id === selectedId)}
              />
            </Stack>
          ) : heat.loading ? (
            <Chip label="Loading the 48-hour forecast map…" sx={{ bgcolor: 'background.paper', boxShadow: 2 }} />
          ) : heat.error ? (
            <Chip label={`Forecast map unavailable: ${heat.error.message}`} color="warning" sx={{ boxShadow: 2 }} />
          ) : null}
        </Box>
        {!plan.data && !plan.loading && (
          <Paper
            elevation={3}
            sx={{ position: 'absolute', top: 12, left: 12, p: 1.5, maxWidth: 300 }}
          >
            <Typography variant="body2">
              Enter a trip to see three routes, weather checkpoints along each, and a 48-hour forecast map
              of the corridor.
            </Typography>
          </Paper>
        )}
      </Box>
    </Box>
  )
}
