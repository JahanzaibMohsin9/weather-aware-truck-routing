import { useEffect, useMemo, useState } from 'react'
import { Box, IconButton, Paper, Slider, Stack, Tooltip, Typography } from '@mui/material'
import PauseIcon from '@mui/icons-material/Pause'
import PlayArrowIcon from '@mui/icons-material/PlayArrow'
import type { Route } from '../types'
import { levelColor } from '../theme/colors'
import { formatClock, formatLocalTime, formatMiles } from '../utils/format'
import { routeTimeline, type RouteTimeline } from '../utils/timeline'
import RiskTimeline from './RiskTimeline'

// Ticks every 6 h, labels every 12 h so they fit on a phone.
const MARKS = [0, 6, 12, 18, 24, 30, 36, 42, 48].map((h) => ({ value: h, label: h % 12 === 0 ? `${h}h` : undefined }))
const PLAY_STEP_MS = 350

interface Props {
  hours: string[]
  hour: number
  /** Called on every change; the map defers its own update (see App). */
  onChange: (hour: number) => void
  /** The selected route, shown as a risk timeline on the slider's scale. */
  route?: Route
}

export default function ForecastSlider({ hours, hour, onChange, route }: Props) {
  const [playing, setPlaying] = useState(false)
  const last = hours.length - 1
  const timeline = useMemo(() => (route ? routeTimeline(route.checkpoints, hours[0], last) : null), [route, hours, last])
  const status = timeline && route ? truckStatus(route.id, timeline, hour) : null

  useEffect(() => {
    if (!playing) return
    const timer = window.setTimeout(() => onChange(hour >= last ? 0 : hour + 1), PLAY_STEP_MS)
    return () => window.clearTimeout(timer)
  }, [playing, hour, last, onChange])

  return (
    <Paper elevation={3} sx={{ px: 2, py: 1 }}>
      <Stack direction="row" spacing={1.5} sx={{ alignItems: 'center' }}>
        <Tooltip title={playing ? 'Pause' : 'Play forecast'}>
          <IconButton size="small" onClick={() => setPlaying((p) => !p)} aria-label={playing ? 'Pause' : 'Play forecast'}>
            {playing ? <PauseIcon /> : <PlayArrowIcon />}
          </IconButton>
        </Tooltip>
        <Stack sx={{ flex: 1, minWidth: 0 }}>
          <Typography variant="body2" sx={{ fontWeight: 600 }} aria-live="polite">
            {formatLocalTime(hours[hour])}
            <Typography component="span" variant="body2" color="text.secondary">
              {' '}· +{hour} h
              <Box component="span" sx={{ display: { xs: 'none', sm: 'inline' } }}>
                {' '}from departure
              </Box>
            </Typography>
            {status && (
              <Typography component="span" variant="body2" sx={{ ml: 1, color: status.color, fontWeight: 600 }}>
                · {status.text}
              </Typography>
            )}
          </Typography>
          {timeline && <RiskTimeline timeline={timeline} totalHours={last} />}
          <Slider
            value={hour}
            min={0}
            max={last}
            step={1}
            marks={MARKS}
            onChange={(_, value) => onChange(value as number)}
            valueLabelDisplay="auto"
            valueLabelFormat={(h) => `+${h} h`}
            aria-label="Forecast hour"
            size="small"
          />
        </Stack>
      </Stack>
    </Paper>
  )
}

/** Where the selected route's truck is at this hour, in a few words. */
function truckStatus(routeId: string, timeline: RouteTimeline, hour: number): { text: string; color: string } {
  const first = timeline.segments[0]
  if (first && hour < first.start) {
    // The slider hour that contains the departure says when it leaves.
    const departs = hour + 1 > first.start ? ` departs ${formatClock(first.checkpoint.eta)}` : ' not departed yet'
    return { text: `Route ${routeId}${departs}`, color: 'text.secondary' }
  }
  if (hour >= timeline.arrival) return { text: `Route ${routeId} arrived`, color: 'text.secondary' }
  const seg = timeline.segments.find((s) => hour >= s.start && hour < s.end)
  if (!seg) return { text: `Route ${routeId}`, color: 'text.secondary' }
  return {
    text: `Route ${routeId} · mile ${formatMiles(seg.checkpoint.mile)} · ${seg.level}`,
    color: levelColor(seg.level),
  }
}
