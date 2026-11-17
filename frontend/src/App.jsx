import { useState, useEffect, useCallback } from 'react'
import 'leaflet/dist/leaflet.css'
import './App.css'
import MapView from './MapView'
import RescueReports from './RescueReports'
import Alerts from './Alerts'
import {
  getStatus,
  getWeather,
  getReports,
  getAlerts,
  MONITORED_LOCATION,
} from './api'

const SEVERITY_LABEL = { high: 'High', medium: 'Medium', low: 'Low' }

const RISK_STYLE = {
  LOW: { width: '25%', color: '#35ae7a' },
  MODERATE: { width: '60%', color: '#f0a534' },
  HIGH: { width: '92%', color: '#e74752' },
}

function App() {
  const [activeTab, setActiveTab] = useState('Dashboard')
  const [backendStatus, setBackendStatus] = useState('Checking...')
  const [weather, setWeather] = useState(null)
  const [weatherError, setWeatherError] = useState('')
  const [alertData, setAlertData] = useState(null)
  const [alertError, setAlertError] = useState('')
  const [reports, setReports] = useState([])

  const loadReports = useCallback(() => {
    return getReports()
      .then(setReports)
      .catch(() => setReports([]))
  }, [])

  const refreshForecast = useCallback(() => {
    const { latitude, longitude } = MONITORED_LOCATION

    getWeather(latitude, longitude)
      .then(data => {
        if (data.status === 'success') {
          setWeather(data.weather)
          setWeatherError('')
        } else {
          setWeatherError('Weather data unavailable')
        }
      })
      .catch(() => setWeatherError('Unable to load weather data'))

    getAlerts(latitude, longitude)
      .then(data => {
        setAlertData(data)
        setAlertError('')
      })
      .catch(() => setAlertError('Unable to load alerts'))
  }, [])

  // Check the backend every 30 seconds
  useEffect(() => {
    const check = () =>
      getStatus()
        .then(data => setBackendStatus(data.status))
        .catch(() => setBackendStatus('Offline'))

    check()
    const timer = setInterval(check, 30 * 1000)
    return () => clearInterval(timer)
  }, [])

  // Load data as soon as the backend is reachable (also when it comes back
  // after being down), then refresh the forecast every 5 minutes
  useEffect(() => {
    if (backendStatus !== 'Online') return

    loadReports()
    refreshForecast()
    const timer = setInterval(refreshForecast, 5 * 60 * 1000)
    return () => clearInterval(timer)
  }, [backendStatus, loadReports, refreshForecast])

  const alerts = alertData ? alertData.alerts : []
  const riskLevel = alertData ? alertData.risk_level : null
  const riskStyle = RISK_STYLE[riskLevel] || { width: '0%', color: '#e5eaf1' }

  const menu = [
    { name: 'Dashboard', icon: '▦' },
    { name: 'Live Map', icon: '⌖' },
    { name: 'Emergency Alerts', icon: '⚠' },
    { name: 'Rescue Reports', icon: '▤' },
    { name: 'Relief Centers', icon: '⌂' },
  ]

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">R</div>
          <div>
            <h2>ResQnet</h2>
            <span>DISASTER RESPONSE SYSTEM</span>
          </div>
        </div>

        <div className="nav-label">MAIN MENU</div>

        <nav>
          {menu.map((item) => (
            <button
              key={item.name}
              className={`nav-item ${activeTab === item.name ? 'active' : ''}`}
              onClick={() => setActiveTab(item.name)}
            >
              <span>{item.icon}</span>
              {item.name}
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="status-dot"></div>
          <div>
            <strong>
              {backendStatus === 'Online'
                ? 'System Operational'
                : 'System Offline'}
            </strong>
            <span>
              {backendStatus === 'Online'
                ? 'Backend connected'
                : backendStatus}
            </span>
          </div>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <span className="breadcrumb">RESQNET / {activeTab.toUpperCase()}</span>
            <h1>{activeTab}</h1>
            <p>Disaster intelligence and emergency response coordination.</p>
          </div>

          <div className="top-actions">
            <button className="notification">♧</button>
            <div className="profile">
              <div className="avatar">A</div>
              <div>
                <strong>Administrator</strong>
                <span>Rescue Operations</span>
              </div>
            </div>
          </div>
        </header>

        {activeTab === 'Dashboard' && (
          <>
            <section className="welcome">
              <div>
                <span className="eyebrow">EMERGENCY RESPONSE NETWORK</span>
                <h2>Stay prepared. Stay protected.</h2>
                <p>
                  Monitor disaster risks, coordinate rescue operations and keep
                  communities safe.
                </p>
              </div>
              <div className="welcome-symbol">⌖</div>
            </section>

            <section className="section-heading">
              <div>
                <h2>Situation Overview</h2>
                <p>Current emergency intelligence at a glance</p>
              </div>
              <span className="live-label">
                <i></i> {backendStatus === 'Online' ? 'SYSTEM ONLINE' : 'SYSTEM OFFLINE'}
              </span>
            </section>

            <section className="stats-grid">
              <div className="stat-card">
                <div className="stat-top">
                  <span>Disaster Risk Level</span>
                  <span className="stat-icon orange">⚠</span>
                </div>
                <h2>{riskLevel || '--'}</h2>
                <p>
                  {riskLevel
                    ? 'Rule-based · next 24 h forecast'
                    : alertError || 'Loading...'}
                </p>
                <div className="risk-bar">
                  <div style={{ width: riskStyle.width, background: riskStyle.color }}></div>
                </div>
              </div>

              <div className="stat-card">
                <div className="stat-top">
                  <span>Active Alerts</span>
                  <span className="stat-icon red">!</span>
                </div>
                <h2>{alertData ? String(alerts.length).padStart(2, '0') : '--'}</h2>
                <p>Forecast-based · next 24 h</p>
              </div>

              <div className="stat-card">
                <div className="stat-top">
                  <span>Rescue Reports</span>
                  <span className="stat-icon blue">⌖</span>
                </div>
                <h2>{String(reports.length).padStart(2, '0')}</h2>
                <p>Submitted reports</p>
              </div>

              <div className="stat-card">
                <div className="stat-top">
                  <span>Relief Centers</span>
                  <span className="stat-icon green">⌂</span>
                </div>
                <h2>08</h2>
                <p>Sample centers listed</p>
              </div>
            </section>

            <section className="content-grid">
              <div className="panel map-panel">
                <div className="panel-header">
                  <div>
                    <h3>Disaster Monitoring Map</h3>
                    <p>Interactive emergency location overview</p>
                  </div>
                  <button
                    className="outline-btn"
                    onClick={() => setActiveTab('Live Map')}
                  >
                    View Map ↗️
                  </button>
                </div>

                <div
                  className="map-placeholder"
                  style={{
                    height: '350px',
                    padding: 0,
                    overflow: 'hidden'
                  }}
                >
                  <MapView reports={reports} />
                </div>
              </div>

              <div className="panel alerts-panel">
                <div className="panel-header">
                  <div>
                    <h3>Recent Alerts</h3>
                    <p>Generated from the live forecast</p>
                  </div>
                  <span className="alert-count">
                    {alertData ? String(alerts.length).padStart(2, '0') : '--'}
                  </span>
                </div>

                {alerts.length === 0 ? (
                  <p className="al-empty">
                    {alertData
                      ? 'No active alerts. Conditions are within normal ranges.'
                      : alertError || 'Loading alerts...'}
                  </p>
                ) : (
                  alerts.slice(0, 3).map((alert) => (
                    <div className="alert-item" key={alert.id}>
                      <span className={`alert-indicator ${alert.severity}`}></span>
                      <div>
                        <strong>{alert.title}</strong>
                        <p>
                          {SEVERITY_LABEL[alert.severity]} priority · {alert.metric_label}:{' '}
                          {alert.value} {alert.unit}
                        </p>
                        <small>Valid for the next {alertData.window_hours} hours</small>
                      </div>
                    </div>
                  ))
                )}

                <button
                  className="view-all"
                  onClick={() => setActiveTab('Emergency Alerts')}
                >
                  View all alerts →
                </button>
              </div>
            </section>

            <section className="bottom-grid">
              <div className="panel">
                <div className="panel-header">
                  <div>
                    <h3>Weather Intelligence</h3>
                    <p>Live weather data · {MONITORED_LOCATION.name}</p>
                  </div>
                  <span className="weather-icon">☁</span>
                </div>

                <div className="weather-content">
                  {weather ? (
                    <>
                      <h2>{weather.temperature_2m}°C</h2>
                      <div>
                        <strong>Current Temperature</strong>
                        <p>Live weather conditions</p>
                      </div>
                    </>
                  ) : (
                    <>
                      <h2>--°C</h2>
                      <div>
                        <strong>
                          {weatherError || 'Loading weather...'}
                        </strong>
                        <p>Connecting to weather service</p>
                      </div>
                    </>
                  )}
                </div>

                <div className="weather-details">
                  <span>
                    Rainfall <strong>{weather ? `${weather.precipitation} mm` : '--'}</strong>
                  </span>
                  <span>
                    Wind speed <strong>{weather ? `${weather.wind_speed_10m} km/h` : '--'}</strong>
                  </span>
                  <span>
                    Humidity <strong>{weather ? `${weather.relative_humidity_2m}%` : '--'}</strong>
                  </span>
                </div>
              </div>

              <div className="panel sos-panel">
                <div>
                  <span className="eyebrow">EMERGENCY ASSISTANCE</span>
                  <h3>Need immediate help?</h3>
                  <p>
                    Use the emergency assistance feature to report a situation
                    requiring rescue.
                  </p>
                </div>
                <button
                  className="sos-button"
                  onClick={() => setActiveTab('Rescue Reports')}
                >
                  + REPORT AN EMERGENCY
                </button>
              </div>
            </section>
          </>
        )}

        {activeTab === 'Live Map' && (
          <section className="panel rr-fullmap">
            <MapView reports={reports} />
          </section>
        )}

        {activeTab === 'Emergency Alerts' && (
          <Alerts
            alertData={alertData}
            error={alertError}
            location={MONITORED_LOCATION}
          />
        )}

        {activeTab === 'Rescue Reports' && (
          <RescueReports reports={reports} onSubmitted={loadReports} />
        )}

        {activeTab === 'Relief Centers' && (
          <section className="panel">
            <div className="panel-header">
              <div>
                <h3>{activeTab}</h3>
                <p>This page has not been built yet.</p>
              </div>
            </div>
          </section>
        )}

        <footer>
          <span>©️ 2026 ResQnet · Disaster Response Platform</span>
          <span>Built for safer communities.</span>
        </footer>
      </main>
    </div>
  )
}

export default App
