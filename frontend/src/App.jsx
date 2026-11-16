import { useState, useEffect } from 'react'
import 'leaflet/dist/leaflet.css'
import './App.css'
import MapView from './MapView'

function App() {
  const [activeTab, setActiveTab] = useState('Dashboard')
  const [backendStatus, setBackendStatus] = useState('Checking...')
  const [weather, setWeather] = useState(null)
  const [weatherError, setWeatherError] = useState('')

  useEffect(() => {
    fetch('http://127.0.0.1:5000/')
      .then(response => response.json())
      .then(data => setBackendStatus(data.status))
      .catch(() => setBackendStatus('Offline'))
  }, [])

  useEffect(() => {
    fetch('http://127.0.0.1:5000/weather?latitude=28.4744&longitude=77.5040')
      .then(response => {
        if (!response.ok) {
          throw new Error('Weather data unavailable')
        }
        return response.json()
      })
      .then(data => {
        if (data.status === 'success') {
          setWeather(data.weather)
        } else {
          setWeatherError('Weather data unavailable')
        }
      })
      .catch(() => setWeatherError('Unable to load weather data'))
  }, [])

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
            <span className="breadcrumb">RESQNET / OVERVIEW</span>
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
          <span className="live-label"><i></i> SYSTEM ONLINE</span>
        </section>

        <section className="stats-grid">
          <div className="stat-card">
            <div className="stat-top">
              <span>Disaster Risk Level</span>
              <span className="stat-icon orange">⚠</span>
            </div>
            <h2>MODERATE</h2>
            <p>Sample assessment</p>
            <div className="risk-bar"><div></div></div>
          </div>

          <div className="stat-card">
            <div className="stat-top">
              <span>Active Alerts</span>
              <span className="stat-icon red">!</span>
            </div>
            <h2>03</h2>
            <p>Sample alert count</p>
          </div>

          <div className="stat-card">
            <div className="stat-top">
              <span>Rescue Reports</span>
              <span className="stat-icon blue">⌖</span>
            </div>
            <h2>12</h2>
            <p>Sample reports received</p>
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
              <MapView />
            </div>
          </div>

          <div className="panel alerts-panel">
            <div className="panel-header">
              <div>
                <h3>Recent Alerts</h3>
                <p>Emergency notifications</p>
              </div>
              <span className="alert-count">03</span>
            </div>

            <div className="alert-item">
              <span className="alert-indicator high"></span>
              <div>
                <strong>Heavy Rainfall Warning</strong>
                <p>Sample alert · High priority</p>
                <small>Just now</small>
              </div>
            </div>

            <div className="alert-item">
              <span className="alert-indicator medium"></span>
              <div>
                <strong>Flood Risk Advisory</strong>
                <p>Sample alert · Medium priority</p>
                <small>25 minutes ago</small>
              </div>
            </div>

            <div className="alert-item">
              <span className="alert-indicator low"></span>
              <div>
                <strong>Weather Monitoring</strong>
                <p>Sample alert · Low priority</p>
                <small>1 hour ago</small>
              </div>
            </div>

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
                <p>Live weather data · Greater Noida</p>
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

        <footer>
          <span>©️ 2026 ResQnet · Disaster Response Platform</span>
          <span>Built for safer communities.</span>
        </footer>
      </main>
    </div>
  )
}

export default App
