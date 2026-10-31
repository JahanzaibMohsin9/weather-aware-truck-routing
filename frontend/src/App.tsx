import { Box, Paper, Stack, Typography } from '@mui/material'
import MapView from './components/MapView'
import { useBackendHealth } from './hooks/useBackendHealth'

export default function App() {
  const backend = useBackendHealth()

  return (
    <Box sx={{ display: 'flex', height: '100vh' }}>
      <Paper
        square
        elevation={2}
        sx={{ width: 380, flexShrink: 0, p: 2, overflowY: 'auto', zIndex: 1 }}
      >
        <Stack spacing={1}>
          <Typography variant="h6">Weather-Aware Truck Routing</Typography>
          <Typography variant="body2" color="text.secondary">
            Backend: {backend}
          </Typography>
        </Stack>
      </Paper>
      <Box sx={{ flex: 1, position: 'relative' }}>
        <MapView />
      </Box>
    </Box>
  )
}
