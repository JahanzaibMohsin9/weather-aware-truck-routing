import { useState } from 'react'
import {
  Box,
  ButtonBase,
  Paper,
  Stack,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
  useMediaQuery,
  useTheme,
} from '@mui/material'
import ExpandLessIcon from '@mui/icons-material/ExpandLess'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import type { HeatmapResponse } from '../types'
import { LEVELS, NO_FORECAST_COLOR } from '../theme/colors'
import type { HeatMode } from '../utils/heat'

const HEAT_MODES: { value: HeatMode; label: string }[] = [
  { value: 'risk', label: 'Risk' },
  { value: 'wind', label: 'Wind' },
  { value: 'rain', label: 'Rain' },
  { value: 'snow', label: 'Snow' },
]

/** The right end of the colour scale: where No Travel starts for this mode. */
function topLabel(mode: HeatMode, scales: HeatmapResponse['scales']): string {
  if (mode === 'risk') return 'no travel'
  const limit = scales[mode][3]
  return mode === 'wind' ? `${limit}+ mph` : `>${limit} in/hr`
}

interface Props {
  /** Heatmap controls; absent until the heatmap has loaded. */
  heat?: { mode: HeatMode; onMode: (mode: HeatMode) => void; scales: HeatmapResponse['scales'] }
}

export default function Legend({ heat }: Props) {
  // Starts collapsed on small screens, where the map has little room.
  const theme = useTheme()
  const roomy = useMediaQuery(theme.breakpoints.up('md'))
  const [toggled, setToggled] = useState<boolean | null>(null)
  const open = toggled ?? roomy

  return (
    <Paper elevation={2} sx={{ p: 1 }}>
      <ButtonBase
        onClick={() => setToggled(!open)}
        aria-expanded={open}
        sx={{ width: '100%', justifyContent: 'space-between', borderRadius: 0.5 }}
      >
        <Typography variant="caption" sx={{ fontWeight: 600 }}>
          Risk
        </Typography>
        {open ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
      </ButtonBase>
      {!open ? (
        <Stack direction="row" spacing={0.5} sx={{ mt: 0.5 }} aria-hidden>
          {LEVELS.map((level) => (
            <Box key={level.label} sx={{ width: 10, height: 10, borderRadius: '50%', bgcolor: level.color }} />
          ))}
        </Stack>
      ) : (
        <>
          <Stack spacing={0.25}>
            {[...LEVELS, { label: 'No forecast', color: NO_FORECAST_COLOR }].map((level) => (
              <Stack key={level.label} direction="row" spacing={0.75} sx={{ alignItems: 'center' }}>
                <Box sx={{ width: 10, height: 10, borderRadius: '50%', bgcolor: level.color }} />
                <Typography variant="caption">{level.label}</Typography>
              </Stack>
            ))}
          </Stack>
          {heat && (
            <Box sx={{ mt: 1 }}>
              <Typography variant="caption" component="div" color="text.secondary">
                Heatmap at slider time
              </Typography>
              <ToggleButtonGroup
                value={heat.mode}
                exclusive
                size="small"
                onChange={(_, mode: HeatMode | null) => mode && heat.onMode(mode)}
                aria-label="What the heatmap shows"
                sx={{ my: 0.5, '& .MuiToggleButton-root': { px: 0.9, py: 0.1, fontSize: 11 } }}
              >
                {HEAT_MODES.map((m) => (
                  <ToggleButton key={m.value} value={m.value}>
                    {m.label}
                  </ToggleButton>
                ))}
              </ToggleButtonGroup>
              <Box
                sx={{
                  height: 8,
                  borderRadius: 1,
                  background: `linear-gradient(to right, rgba(46,125,50,0.15), ${LEVELS.map((l) => l.color).join(', ')})`,
                }}
              />
              <Stack direction="row" sx={{ justifyContent: 'space-between' }}>
                <Typography variant="caption">calm</Typography>
                <Typography variant="caption">{topLabel(heat.mode, heat.scales)}</Typography>
              </Stack>
            </Box>
          )}
        </>
      )}
    </Paper>
  )
}
