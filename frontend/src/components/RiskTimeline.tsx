import { Box, Tooltip, Typography } from '@mui/material'
import FlagIcon from '@mui/icons-material/Flag'
import type { RouteTimeline } from '../utils/timeline'
import { levelColor } from '../theme/colors'
import { formatLocalTime, formatMiles } from '../utils/format'

interface Props {
  timeline: RouteTimeline
  totalHours: number
}

/**
 * A strip on the slider's own scale: when the truck is on each stretch of the
 * selected route, coloured by that stretch's risk. The flag marks arrival.
 */
export default function RiskTimeline({ timeline, totalHours }: Props) {
  const pct = (h: number) => `${(h / totalHours) * 100}%`
  return (
    <Box sx={{ position: 'relative', height: 10, mt: 0.75, borderRadius: 1, bgcolor: 'action.hover' }}>
      {timeline.segments.map((seg) => (
        <Tooltip
          key={seg.checkpoint.mile}
          placement="top"
          title={
            <Typography variant="caption">
              Mile {formatMiles(seg.checkpoint.mile)} · {seg.level} · {formatLocalTime(seg.checkpoint.eta)}
            </Typography>
          }
        >
          <Box
            sx={{
              position: 'absolute',
              top: 0,
              bottom: 0,
              left: pct(seg.start),
              width: pct(seg.end - seg.start),
              bgcolor: levelColor(seg.level),
            }}
          />
        </Tooltip>
      ))}
      {timeline.arrival <= totalHours && (
        <Tooltip title="Arrival" placement="top">
          <FlagIcon
            sx={{ position: 'absolute', left: pct(timeline.arrival), top: -9, fontSize: 16, color: 'text.secondary' }}
          />
        </Tooltip>
      )}
    </Box>
  )
}
