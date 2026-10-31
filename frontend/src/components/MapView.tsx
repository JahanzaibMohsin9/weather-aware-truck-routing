import { useEffect, useMemo, useRef, useState } from 'react'
import Map, {
  AttributionControl,
  Layer,
  Marker,
  NavigationControl,
  Popup,
  Source,
  type MapMouseEvent,
  type MapRef,
} from 'react-map-gl/maplibre'
import { Box, Paper, Typography } from '@mui/material'
import LocalShippingIcon from '@mui/icons-material/LocalShipping'
import maplibregl from '../maplibreSetup'
import type { HeatmapResponse, PlanResponse, Route } from '../types'
import { ROUTE_COLORS } from '../theme/colors'
import { formatDuration, formatMiles } from '../utils/format'
import { MeasuredLine, mileAtTime } from '../utils/geo'
import CheckpointPopup from './CheckpointPopup'
import {
  CHECKPOINT_LAYER,
  HEAT_COLOR,
  HEAT_INTENSITY,
  ROUTE_CASING_LAYER,
  ROUTE_LINE_LAYER,
  checkpointPoints,
  heatFrames,
  heatRadius,
  riskSegments,
  routeLines,
} from './map/layers'

// Free vector tiles, no key needed.
const MAP_STYLE = 'https://tiles.openfreemap.org/styles/liberty'
const CONTINENTAL_US = { longitude: -98.5, latitude: 39.5, zoom: 3.6 }
// Labels sit at different points along each route so they don't stack where routes overlap.
const LABEL_POSITION: Record<string, number> = { A: 0.5, B: 0.38, C: 0.62 }

interface Props {
  plan: PlanResponse | null
  selectedId: string | null
  onSelect: (id: string) => void
  heatmap: HeatmapResponse | null
  hour: number
}

export default function MapView({ plan, selectedId, onSelect, heatmap, hour }: Props) {
  const mapRef = useRef<MapRef>(null)
  // A popup belongs to the routes it was opened on, so a new plan closes it without an effect.
  const [popupState, setPopupState] = useState<{ routes: Route[]; routeId: string; index: number } | null>(null)
  const [cursor, setCursor] = useState('')
  const routes = useMemo(() => plan?.routes ?? [], [plan])
  const popup = popupState?.routes === routes ? popupState : null
  const setPopup = (value: { routeId: string; index: number } | null) =>
    setPopupState(value && { routes, ...value })

  const lines = useMemo(
    () => Object.fromEntries(routes.map((r) => [r.id, new MeasuredLine(r.geometry, r.distance_mi)])),
    [routes],
  )
  const selected = routes.find((r) => r.id === selectedId)

  const routeData = useMemo(() => routeLines(routes, selectedId), [routes, selectedId])
  const segmentData = useMemo(() => riskSegments(selected, selected && lines[selected.id]), [selected, lines])
  const checkpointData = useMemo(() => checkpointPoints(routes, selectedId), [routes, selectedId])
  const frames = useMemo(() => (heatmap ? heatFrames(heatmap) : []), [heatmap])
  const radius = useMemo(() => {
    if (!heatmap || !plan) return 0
    return heatRadius(heatmap.spacing_mi, (plan.origin.lat + plan.destination.lat) / 2)
  }, [heatmap, plan])

  // Fit the map to a new plan's routes.
  useEffect(() => {
    if (!routes.length) return
    let [minLng, minLat, maxLng, maxLat] = [180, 90, -180, -90]
    for (const route of routes) {
      for (const [lng, lat] of route.geometry) {
        minLng = Math.min(minLng, lng)
        maxLng = Math.max(maxLng, lng)
        minLat = Math.min(minLat, lat)
        maxLat = Math.max(maxLat, lat)
      }
    }
    // Keep the routes clear of the legend (top left) and the forecast slider (bottom).
    const wide = (mapRef.current?.getContainer().clientWidth ?? 0) >= 700
    const padding = wide ? { top: 50, bottom: 130, left: 180, right: 70 } : { top: 70, bottom: 150, left: 30, right: 50 }
    mapRef.current?.fitBounds([[minLng, minLat], [maxLng, maxLat]], { padding, duration: 800 })
  }, [routes])

  const truck = useMemo(() => {
    if (!heatmap || !selected) return null
    const time = Date.parse(heatmap.hours[hour])
    const mile = mileAtTime(selected.checkpoints, time)
    const [lng, lat] = lines[selected.id].at(mile)
    return { lng, lat, arrived: mile >= selected.distance_mi - 0.01 }
  }, [heatmap, hour, selected, lines])

  const onClick = (event: MapMouseEvent) => {
    const feature = event.features?.[0]
    if (!feature) return setPopup(null)
    const { route, index, id } = feature.properties as { route?: string; index?: number; id?: string }
    if (feature.layer.id === CHECKPOINT_LAYER && route != null && index != null) {
      setPopup({ routeId: route, index })
      if (route !== selectedId) onSelect(route)
    } else if (id) {
      onSelect(id)
    }
  }

  const popupRoute = popup ? routes.find((r) => r.id === popup.routeId) : undefined
  const popupCheckpoint = popup ? popupRoute?.checkpoints[popup.index] : undefined

  return (
    <Map
      ref={mapRef}
      mapLib={maplibregl}
      initialViewState={CONTINENTAL_US}
      mapStyle={MAP_STYLE}
      style={{ width: '100%', height: '100%' }}
      interactiveLayerIds={routes.length ? [CHECKPOINT_LAYER, ROUTE_LINE_LAYER] : []}
      onClick={onClick}
      onMouseEnter={() => setCursor('pointer')}
      onMouseLeave={() => setCursor('')}
      cursor={cursor}
      attributionControl={false}
    >
      <NavigationControl position="top-right" />
      <AttributionControl compact position="bottom-right" />

      <Source id="routes" type="geojson" data={routeData}>
        <Layer
          id={ROUTE_CASING_LAYER}
          type="line"
          layout={{ 'line-join': 'round', 'line-cap': 'round', 'line-sort-key': ['case', ['get', 'selected'], 1, 0] }}
          paint={{ 'line-color': '#ffffff', 'line-width': ['case', ['get', 'selected'], 12, 6] }}
        />
        <Layer
          id={ROUTE_LINE_LAYER}
          type="line"
          layout={{ 'line-join': 'round', 'line-cap': 'round', 'line-sort-key': ['case', ['get', 'selected'], 1, 0] }}
          paint={{
            'line-color': ['get', 'color'],
            'line-width': ['case', ['get', 'selected'], 9, 3.5],
            'line-opacity': ['case', ['get', 'selected'], 1, 0.6],
          }}
        />
      </Source>

      {/* Inner stripe on the selected route: the stretch each checkpoint covers, coloured by risk. */}
      <Source id="risk-segments" type="geojson" data={segmentData}>
        <Layer
          id="risk-segments"
          type="line"
          layout={{ 'line-join': 'round', 'line-cap': 'butt' }}
          paint={{ 'line-color': ['get', 'color'], 'line-width': 4 }}
        />
      </Source>

      <Source id="checkpoints" type="geojson" data={checkpointData}>
        <Layer
          id={CHECKPOINT_LAYER}
          type="circle"
          paint={{
            'circle-color': ['get', 'color'],
            'circle-radius': ['case', ['get', 'selected'], 6, 3.5],
            'circle-stroke-color': '#ffffff',
            'circle-stroke-width': ['case', ['get', 'selected'], 2, 1],
            'circle-opacity': ['case', ['get', 'selected'], 1, 0.7],
          }}
        />
      </Source>

      {frames.length > 0 && (
        <Source id="heat" type="geojson" data={frames[hour]}>
          <Layer
            id="heat"
            type="heatmap"
            beforeId={ROUTE_CASING_LAYER}
            paint={{
              'heatmap-weight': ['/', ['get', 'score'], 4],
              'heatmap-intensity': HEAT_INTENSITY,
              'heatmap-radius': radius,
              'heatmap-color': HEAT_COLOR,
              'heatmap-opacity': 0.85,
            }}
          />
        </Source>
      )}

      {plan && (
        <>
          <PlaceMarker lng={plan.origin.lng} lat={plan.origin.lat} label={plan.origin.label} color="#2e7d32" />
          <PlaceMarker lng={plan.destination.lng} lat={plan.destination.lat} label={plan.destination.label} color="#212121" />
        </>
      )}

      {routes.map((route) => (
        <RouteLabel
          key={route.id}
          route={route}
          line={lines[route.id]}
          selected={route.id === selectedId}
          onSelect={onSelect}
        />
      ))}

      {truck && (
        <Marker longitude={truck.lng} latitude={truck.lat} anchor="center" style={{ zIndex: 3 }}>
          <Box
            title={truck.arrived ? 'Arrived' : 'Truck position at the selected forecast hour'}
            sx={{
              bgcolor: 'background.paper',
              border: '2px solid',
              borderColor: ROUTE_COLORS[selectedId ?? 'A'],
              borderRadius: '50%',
              width: 30,
              height: 30,
              display: 'grid',
              placeItems: 'center',
              boxShadow: 2,
            }}
          >
            <LocalShippingIcon sx={{ fontSize: 18, color: ROUTE_COLORS[selectedId ?? 'A'] }} />
          </Box>
        </Marker>
      )}

      {popupRoute && popupCheckpoint && (
        <Popup
          longitude={popupCheckpoint.lng}
          latitude={popupCheckpoint.lat}
          offset={10}
          onClose={() => setPopup(null)}
          closeOnClick={false}
          maxWidth="280px"
          style={{ zIndex: 5 }}
        >
          <CheckpointPopup routeId={popupRoute.id} checkpoint={popupCheckpoint} />
        </Popup>
      )}
    </Map>
  )
}

function PlaceMarker({ lng, lat, label, color }: { lng: number; lat: number; label: string; color: string }) {
  return (
    <Marker longitude={lng} latitude={lat} anchor="center" style={{ zIndex: 2 }}>
      <Box
        title={label}
        sx={{ width: 16, height: 16, borderRadius: '50%', bgcolor: color, border: '3px solid white', boxShadow: 2 }}
      />
    </Marker>
  )
}

/** Route summary shown on the map itself, as the brief asks. Click to select. */
function RouteLabel({
  route,
  line,
  selected,
  onSelect,
}: {
  route: Route
  line: MeasuredLine
  selected: boolean
  onSelect: (id: string) => void
}) {
  const [lng, lat] = line.at(route.distance_mi * (LABEL_POSITION[route.id] ?? 0.5))
  const { summary } = route
  const risk = summary.has_no_travel
    ? `${formatMiles(summary.no_travel_mi)} mi No Travel`
    : `${formatMiles(summary.severe_mi)} severe · ${formatMiles(summary.high_mi)} high mi`
  return (
    <Marker longitude={lng} latitude={lat} anchor="bottom" offset={[0, -8]} style={{ zIndex: selected ? 2 : 1 }}>
      <Paper
        elevation={selected ? 4 : 1}
        onClick={(e) => {
          e.stopPropagation()
          onSelect(route.id)
        }}
        sx={{
          px: 1,
          py: 0.25,
          cursor: 'pointer',
          borderLeft: `4px solid ${ROUTE_COLORS[route.id]}`,
          opacity: selected ? 1 : 0.85,
          whiteSpace: 'nowrap',
        }}
      >
        <Typography variant="caption" sx={{ fontWeight: 700 }}>
          {route.id}
          {route.recommended ? ' ★' : ''}
        </Typography>
        <Typography variant="caption">
          {' '}
          {formatMiles(route.distance_mi)} mi · {formatDuration(route.duration_min)}
        </Typography>
        {selected && (
          <Typography variant="caption" component="div" color="text.secondary">
            {risk}
          </Typography>
        )}
      </Paper>
    </Marker>
  )
}
