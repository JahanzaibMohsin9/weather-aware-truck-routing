import { useEffect, useState } from 'react'
import { Box, IconButton, Paper, Slider, Stack, Tooltip, Typography } from '@mui/material'
import PauseIcon from '@mui/icons-material/Pause'
import PlayArrowIcon from '@mui/icons-material/PlayArrow'
import { formatLocalTime } from '../utils/format'

// Ticks every 6 h, labels every 12 h so they fit on a phone.
const MARKS = [0, 6, 12, 18, 24, 30, 36, 42, 48].map((h) => ({ value: h, label: h % 12 === 0 ? `${h}h` : undefined }))
const PLAY_STEP_MS = 350

interface Props {
  hours: string[]
  hour: number
  /** Called on every change; the map defers its own update (see App). */
  onChange: (hour: number) => void
}

export default function ForecastSlider({ hours, hour, onChange }: Props) {
  const [playing, setPlaying] = useState(false)
  const last = hours.length - 1

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
          </Typography>
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
