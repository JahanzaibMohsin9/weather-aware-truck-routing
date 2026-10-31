import { Box, Card, CardActionArea, Chip, Stack, Tooltip, Typography } from '@mui/material'
import type { Route } from '../types'
import { LEVELS, NO_FORECAST_COLOR, ROUTE_COLORS } from '../theme/colors'
import { formatDuration, formatLocalTime, formatMiles } from '../utils/format'

interface Props {
  routes: Route[]
  selectedId: string | null
  onSelect: (id: string) => void
}

export default function RouteCards({ routes, selectedId, onSelect }: Props) {
  const ranked = [...routes].sort((a, b) => a.rank - b.rank)
  return (
    <Stack spacing={1.5}>
      {ranked.map((route) => (
        <RouteCard key={route.id} route={route} selected={route.id === selectedId} onSelect={onSelect} />
      ))}
    </Stack>
  )
}

function RouteCard({ route, selected, onSelect }: { route: Route; selected: boolean; onSelect: (id: string) => void }) {
  const { summary } = route
  const color = ROUTE_COLORS[route.id]
  const arrival = route.checkpoints[route.checkpoints.length - 1]?.eta

  return (
    <Card
      variant="outlined"
      sx={{
        borderColor: selected ? color : undefined,
        borderWidth: selected ? 2 : 1,
        borderLeft: `6px solid ${color}`,
      }}
    >
      <CardActionArea onClick={() => onSelect(route.id)} sx={{ p: 1.5 }} aria-pressed={selected}>
        <Stack direction="row" spacing={1} sx={{ mb: 0.5, alignItems: 'center', flexWrap: 'wrap', rowGap: 0.5 }}>
          <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
            Route {route.id}
          </Typography>
          {route.recommended && <Chip label="Recommended" color="success" size="small" />}
          {summary.has_no_travel && <Chip label="Not recommended: No Travel" color="error" size="small" />}
          {!summary.forecast_complete && !summary.has_no_travel && (
            <Chip label="Incomplete forecast" color="warning" size="small" variant="outlined" />
          )}
          <Box sx={{ flex: 1 }} />
          <Typography variant="caption" color="text.secondary">
            #{route.rank}
          </Typography>
        </Stack>

        <Typography variant="body2">
          {formatMiles(route.distance_mi)} mi · {formatDuration(route.duration_min)}
          {arrival && (
            <Typography component="span" variant="body2" color="text.secondary">
              {' '}· arrives {formatLocalTime(arrival)}
            </Typography>
          )}
        </Typography>

        <LevelBar route={route} />

        <Stack direction="row" spacing={2} sx={{ mt: 0.5 }}>
          <Stat label="Severe" value={`${formatMiles(summary.severe_mi)} mi`} />
          <Stat label="High" value={`${formatMiles(summary.high_mi)} mi`} />
          {summary.no_travel_mi > 0 && <Stat label="No Travel" value={`${formatMiles(summary.no_travel_mi)} mi`} />}
          <Stat label="Avg risk" value={summary.avg_risk == null ? '–' : summary.avg_risk.toFixed(2)} hint="0 = Low … 4 = No Travel, weighted by miles" />
        </Stack>
      </CardActionArea>
    </Card>
  )
}

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  const content = (
    <Box>
      <Typography variant="caption" color="text.secondary" component="div" sx={{ lineHeight: 1.2 }}>
        {label}
      </Typography>
      <Typography variant="body2" sx={{ fontWeight: 600 }}>
        {value}
      </Typography>
    </Box>
  )
  return hint ? <Tooltip title={hint}>{content}</Tooltip> : content
}

/** The route's miles at each risk level, as one stacked bar. */
function LevelBar({ route }: { route: Route }) {
  const miles = new Map<string, number>()
  for (const cp of route.checkpoints) miles.set(cp.level, (miles.get(cp.level) ?? 0) + cp.covers_mi)
  const total = route.checkpoints.reduce((sum, cp) => sum + cp.covers_mi, 0) || 1
  const segments = [...LEVELS, { label: 'No Forecast', color: NO_FORECAST_COLOR }]
    .map((level) => ({ ...level, miles: miles.get(level.label) ?? 0 }))
    .filter((s) => s.miles > 0)

  return (
    <Box
      sx={{ display: 'flex', height: 8, borderRadius: 1, overflow: 'hidden', mt: 1 }}
      role="img"
      aria-label={segments.map((s) => `${s.label} ${formatMiles(s.miles)} mi`).join(', ')}
    >
      {segments.map((s) => (
        <Tooltip key={s.label} title={`${s.label}: ${formatMiles(s.miles)} mi`}>
          <Box sx={{ width: `${(s.miles / total) * 100}%`, bgcolor: s.color }} />
        </Tooltip>
      ))}
    </Box>
  )
}
