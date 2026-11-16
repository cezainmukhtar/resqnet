import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet'
import L from 'leaflet'
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png'
import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'

// Vite breaks Leaflet's default marker icons unless they are set explicitly
delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
})

const CENTER = [28.4744, 77.5040] // Greater Noida

export default function MapView({ reports = [] }) {
  // Older test reports were saved without coordinates, so skip those
  const located = reports.filter(
    (report) => report.latitude != null && report.longitude != null
  )

  return (
    <MapContainer center={CENTER} zoom={11} style={{ height: '100%', width: '100%' }}>
      <TileLayer
        attribution="&copy; OpenStreetMap contributors"
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {located.map((report) => (
        <Marker key={report.id} position={[report.latitude, report.longitude]}>
          <Popup>
            <strong>{report.emergency_type}</strong>
            <br />
            {report.location}
            <br />
            {report.description}
          </Popup>
        </Marker>
      ))}
    </MapContainer>
  )
}
