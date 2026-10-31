import { useState, type FormEvent } from 'react'
import {
  Box,
  Button,
  CircularProgress,
  Link,
  Stack,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material'
import type { PlanRequest } from '../types'
import { nextQuarterHour, toDateTimeLocal } from '../utils/format'

const INTERVALS = [10, 25, 50]

interface Props {
  loading: boolean
  fieldErrors: Record<string, string[]>
  onSubmit: (request: PlanRequest) => void
}

export default function PlanForm({ loading, fieldErrors, onSubmit }: Props) {
  const [origin, setOrigin] = useState('')
  const [destination, setDestination] = useState('')
  const [departure, setDeparture] = useState(() => toDateTimeLocal(nextQuarterHour()))
  const [load, setLoad] = useState('36000')
  const [intervalMiles, setIntervalMiles] = useState(25)
  const [departureError, setDepartureError] = useState<string | null>(null)

  const submit = (event: FormEvent) => {
    event.preventDefault()
    const departureDate = new Date(departure)
    if (!departure || !Number.isFinite(departureDate.getTime())) {
      setDepartureError('Enter a valid departure date and time.')
      return
    }
    setDepartureError(null)
    onSubmit({
      origin: origin.trim(),
      destination: destination.trim(),
      // datetime-local is the viewer's local time; send it as an absolute instant.
      departure: departureDate.toISOString(),
      load_lbs: Number(load),
      interval_miles: intervalMiles,
    })
  }

  const tryExample = () => {
    setOrigin('Dallas, TX')
    setDestination('Denver, CO')
  }

  const error = (field: string) => fieldErrors[field]?.join(' ')

  return (
    <Box component="form" onSubmit={submit} noValidate>
      <Stack spacing={2}>
        <TextField
          label="Origin"
          placeholder="City, ST or address"
          value={origin}
          onChange={(e) => setOrigin(e.target.value)}
          required
          error={!!error('origin')}
          helperText={error('origin')}
          size="small"
        />
        <TextField
          label="Destination"
          placeholder="City, ST or address"
          value={destination}
          onChange={(e) => setDestination(e.target.value)}
          required
          error={!!error('destination')}
          helperText={error('destination')}
          size="small"
        />
        <Stack direction="row" spacing={1.5}>
          <TextField
            label="Departure"
            type="datetime-local"
            value={departure}
            onChange={(e) => {
              setDeparture(e.target.value)
              setDepartureError(null)
            }}
            required
            error={!!(departureError || error('departure'))}
            helperText={departureError || error('departure') || 'Your local time'}
            size="small"
            sx={{ flex: 3 }}
            slotProps={{ inputLabel: { shrink: true } }}
          />
          <TextField
            label="Load (lb)"
            type="number"
            value={load}
            onChange={(e) => setLoad(e.target.value)}
            required
            error={!!error('load_lbs')}
            helperText={error('load_lbs')}
            size="small"
            sx={{ flex: 2 }}
            slotProps={{ htmlInput: { min: 1, max: 150000, step: 1000 } }}
          />
        </Stack>
        <Box>
          <Typography variant="caption" color="text.secondary" component="div" sx={{ mb: 0.5 }}>
            Check the weather every
          </Typography>
          <ToggleButtonGroup
            value={intervalMiles}
            exclusive
            size="small"
            onChange={(_, value: number | null) => value && setIntervalMiles(value)}
            aria-label="Weather checkpoint interval"
          >
            {INTERVALS.map((miles) => (
              <ToggleButton key={miles} value={miles} sx={{ px: 2 }}>
                {miles} mi
              </ToggleButton>
            ))}
          </ToggleButtonGroup>
        </Box>
        <Button
          type="submit"
          variant="contained"
          disabled={loading || !origin.trim() || !destination.trim()}
          startIcon={loading ? <CircularProgress size={16} color="inherit" /> : undefined}
        >
          {loading ? 'Planning…' : 'Plan routes'}
        </Button>
        {!origin && !destination && (
          <Typography variant="caption" color="text.secondary">
            New here?{' '}
            <Link component="button" type="button" onClick={tryExample} variant="caption">
              Try Dallas, TX → Denver, CO
            </Link>
          </Typography>
        )}
      </Stack>
    </Box>
  )
}
