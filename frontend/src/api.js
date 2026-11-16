// All backend calls live here. Override the URL with VITE_API_URL in frontend/.env
export const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:5000'

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

export const getReports = () => request('/reports')

export const createReport = (report) =>
  request('/reports', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(report),
  })
