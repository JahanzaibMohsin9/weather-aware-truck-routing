import { useState } from 'react'
import { Box, ButtonBase, Paper, Stack, Typography, useMediaQuery, useTheme } from '@mui/material'
import ExpandLessIcon from '@mui/icons-material/ExpandLess'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import { LEVELS, NO_FORECAST_COLOR } from '../theme/colors'

export default function Legend({ showHeat }: { showHeat: boolean }) {
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
          {showHeat && (
            <Box sx={{ mt: 1 }}>
              <Typography variant="caption" component="div" color="text.secondary">
                Heatmap at slider time
              </Typography>
              <Box
                sx={{
                  height: 8,
                  width: 110,
                  borderRadius: 1,
                  background: `linear-gradient(to right, rgba(46,125,50,0.15), ${LEVELS.map((l) => l.color).join(', ')})`,
                }}
              />
              <Stack direction="row" sx={{ width: 110, justifyContent: 'space-between' }}>
                <Typography variant="caption">calm</Typography>
                <Typography variant="caption">no travel</Typography>
              </Stack>
            </Box>
          )}
        </>
      )}
    </Paper>
  )
}
