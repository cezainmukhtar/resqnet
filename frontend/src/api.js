// src/api.js
// All backend calls live here. Override the URL with VITE_API_URL in frontend/.env
export const API_URL = import.meta.env.VITE_API_URL ?? '/api'

// The one place the dashboard monitors. Change it here to monitor somewhere else.
export const MONITORED_LOCATION = {
  name: 'Greater Noida',
  latitude: 28.4744,
  longitude: 77.5040,
}

async function request(path, options) {
  const response = await fetch(`${API_URL}${path}`, options)
  const data = await response.json().catch(() => ({}))

  if (!response.ok) {
    throw new Error(data.error || data.message || `Request failed (${response.status})`)
  }

  return data
}

export const getStatus = () => request('/')

export const getWeather = (latitude, longitude) =>
  request(`/weather?latitude=${latitude}&longitude=${longitude}`)

export const getAlerts = (latitude, longitude) =>
  request(`/alerts?latitude=${latitude}&longitude=${longitude}`)

export const getRainOutlook = (latitude, longitude) =>
  request(`/predict/rain?latitude=${latitude}&longitude=${longitude}`)

export const getFloodRisk = (latitude, longitude) =>
  request(`/hazards/flood?latitude=${latitude}&longitude=${longitude}`)

export const getLandslideRisk = (latitude, longitude, scenario) => {
  const extra = scenario
    ? `&scenario_rain_24h=${scenario.rain24}&scenario_rain_72h=${scenario.rain72}`
    : ''
  return request(`/hazards/landslide?latitude=${latitude}&longitude=${longitude}${extra}`)
}

export const getReports = () => request('/reports')

export const createReport = (report) =>
  request('/reports', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(report),
  })

export const searchLocations = async (query) => {
  const url =
    'https://geocoding-api.open-meteo.com/v1/search' +
    `?name=${encodeURIComponent(query)}&count=5&language=en&format=json`
  const res = await fetch(url)
  const data = await res.json()
  return (data.results || []).map((r) => ({
    name: [r.name, r.admin1, r.country].filter(Boolean).join(', '),
    latitude: r.latitude,
    longitude: r.longitude,
  }))
}