import Map, { NavigationControl } from 'react-map-gl/maplibre'
import maplibregl from '../maplibreSetup'

// Free vector tiles, no key needed.
const MAP_STYLE = 'https://tiles.openfreemap.org/styles/liberty'

const CONTINENTAL_US = { longitude: -98.5, latitude: 39.5, zoom: 3.6 }

export default function MapView() {
  return (
    <Map
      mapLib={maplibregl}
      initialViewState={CONTINENTAL_US}
      mapStyle={MAP_STYLE}
      style={{ width: '100%', height: '100%' }}
    >
      <NavigationControl position="top-right" />
    </Map>
  )
}
