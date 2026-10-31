import { Box, Chip, Stack, Typography } from '@mui/material'
import type { Checkpoint } from '../types'
import { levelColor } from '../theme/colors'
import { formatLocalTime, formatMiles } from '../utils/format'

export default function CheckpointPopup({ routeId, checkpoint: cp }: { routeId: string; checkpoint: Checkpoint }) {
  const color = levelColor(cp.level)
  return (
    <Box sx={{ minWidth: 200 }}>
      <Stack direction="row" spacing={1} sx={{ alignItems: 'center', justifyContent: 'space-between' }}>
        <Typography variant="subtitle2">
          Route {routeId} · mile {formatMiles(cp.mile)}
        </Typography>
        <Chip
          label={cp.level}
          size="small"
          sx={{ bgcolor: color, color: cp.level === 'Moderate' ? '#000' : '#fff', fontWeight: 600 }}
        />
      </Stack>
      <Typography variant="body2" color="text.secondary">
        ETA {formatLocalTime(cp.eta)}
      </Typography>

      {cp.wind_mph == null ? (
        <Typography variant="body2" sx={{ mt: 1 }}>
          No forecast this far ahead, so this stretch isn't scored.
        </Typography>
      ) : (
        <Box component="dl" sx={{ display: 'grid', gridTemplateColumns: 'auto 1fr', columnGap: 1.5, rowGap: 0.25, my: 1 }}>
          <Row label="Wind" value={`${cp.wind_mph.toFixed(0)} mph${cp.gust_mph != null ? ` (gusts ${cp.gust_mph.toFixed(0)})` : ''}`} />
          <Row label="Rain" value={`${cp.rain_in_hr?.toFixed(2)} in/hr`} />
          <Row label="Snow" value={`${cp.snow_in_hr?.toFixed(2)} in/hr`} />
        </Box>
      )}

      {cp.reasons.length > 0 && (
        <Box component="ul" sx={{ pl: 2, my: 0.5 }}>
          {cp.reasons.map((reason) => (
            <Typography component="li" variant="caption" key={reason}>
              {reason}
            </Typography>
          ))}
        </Box>
      )}
      <Typography variant="caption" color="text.secondary">
        Covers {formatMiles(cp.covers_mi)} mi of road nearest to this point
      </Typography>
    </Box>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <>
      <Typography component="dt" variant="body2" color="text.secondary">
        {label}
      </Typography>
      <Typography component="dd" variant="body2" sx={{ m: 0 }}>
        {value}
      </Typography>
    </>
  )
}
