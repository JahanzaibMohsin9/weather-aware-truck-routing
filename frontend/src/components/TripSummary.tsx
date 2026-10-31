import { Button, Paper, Stack, Typography } from '@mui/material'
import EditOutlinedIcon from '@mui/icons-material/EditOutlined'
import type { PlanResponse } from '../types'
import { formatLocalTime } from '../utils/format'

/** The planned trip in one line, shown in place of the form after planning. */
export default function TripSummary({ plan, onEdit }: { plan: PlanResponse; onEdit: () => void }) {
  return (
    <Paper variant="outlined" sx={{ p: 1.5 }}>
      <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
        <Stack sx={{ flex: 1, minWidth: 0 }}>
          <Typography variant="subtitle2" noWrap title={`${plan.origin.label} → ${plan.destination.label}`}>
            {plan.origin.label} → {plan.destination.label}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Departs {formatLocalTime(plan.departure)} · {plan.load_lbs.toLocaleString()} lb · every{' '}
            {plan.interval_miles} mi
          </Typography>
        </Stack>
        <Button size="small" variant="outlined" startIcon={<EditOutlinedIcon />} onClick={onEdit}>
          Edit
        </Button>
      </Stack>
    </Paper>
  )
}
