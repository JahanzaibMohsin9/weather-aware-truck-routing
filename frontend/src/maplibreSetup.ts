import * as maplibregl from 'maplibre-gl'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'

// MapLibre looks for its worker next to its own file, which Vite's bundling
// moves. `?worker&url` makes Vite serve and build the file as a real worker.
maplibregl.setWorkerUrl(workerUrl)

// Passed to react-map-gl as `mapLib` so the map uses this configured instance.
export default maplibregl
