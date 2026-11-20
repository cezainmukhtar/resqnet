import { useEffect, useState } from 'react'
import { getFloodRisk, getLandslideRisk } from './api'
import './HazardRisk.css'

const FLOOD_POINTS = [
  { name: 'Yamuna at Okhla (Delhi–Noida)', latitude: 28.553, longitude: 77.305 },
  { name: 'Ganga at Haridwar', latitude: 29.946, longitude: 78.164 },
  { name: 'Jhelum at Srinagar', latitude: 34.084, longitude: 74.797 },
]

const SLOPE_POINTS = [
  { name: 'Pahalgam, Kashmir', latitude: 34.016, longitude: 75.315 },
  { name: 'Joshimath, Uttarakhand', latitude: 30.555, longitude: 79.565 },
  { name: 'Shimla, Himachal Pradesh', latitude: 31.105, longitude: 77.173 },
  { name: 'Greater Noida (flat reference)', latitude: 28.4744, longitude: 77.504 },
]

const SCENARIOS = [
  { label: 'Monsoon day', rain24: 40, rain72: 80 },
  { label: 'Heavy spell', rain24: 110, rain72: 160 },
  { label: 'Extreme event', rain24: 200, rain72: 320 },
]

const LEVEL_COLOR = {
  MINIMAL: '#35ae7a',
  LOW: '#3478f6',
  MEDIUM: '#e08a00',
  HIGH: '#e74752',
}

function LevelBadge({ level }) {
  return (
    <span className="hz-level" style={{ background: LEVEL_COLOR[level] }}>
      {level}
    </span>
  )
}

function DischargeChart({ series, thresholds, peakDate }) {
  const width = 440
  const height = 170
  const left = 8
  const top = 14
  const bottom = 26
  const plotHeight = height - top - bottom

  const values = series.map((point) => point.discharge)
  const yMax = Math.max(...values, thresholds['2'] * 1.15)
  const slot = (width - left * 2) / series.length
  const y = (value) => top + plotHeight - (value / yMax) * plotHeight

  return (
    <svg
      className="hz-chart"
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label="Daily river discharge forecast against flood levels"
    >
      {['2', '5', '20'].map((period) =>
        thresholds[period] <= yMax ? (
          <g key={period}>
            <line
              x1={left}
              x2={width - left}
              y1={y(thresholds[period])}
              y2={y(thresholds[period])}
              className="hz-chart-line"
            />
            <text x={width - left} y={y(thresholds[period]) - 3} className="hz-chart-label" textAnchor="end">
              {period}-year flood
            </text>
          </g>
        ) : null
      )}

      {series.map((point, index) => {
        const barHeight = Math.max(plotHeight - (y(point.discharge) - top), 1)
        return (
          <g key={point.date}>
            <rect
              x={left + index * slot + 4}
              y={y(point.discharge)}
              width={slot - 8}
              height={barHeight}
              rx="3"
              fill={point.date === peakDate ? '#e08a00' : '#7eb5ff'}
            />
            <text
              x={left + index * slot + slot / 2}
              y={height - 8}
              className="hz-chart-day"
              textAnchor="middle"
            >
              {point.date.slice(8)}
            </text>
          </g>
        )
      })}
    </svg>
  )
}

export function FloodView({ data }) {
  const { thresholds } = data

  return (
    <>
      <div className="hz-summary">
        <LevelBadge level={data.level} />
        <div>
          <strong>
            Forecast peak {data.peak_m3s} m³/s on {data.peak_date}
          </strong>
          <p>
            {data.ratio_to_2yr} × the 2-year flood level ({thresholds['2']} m³/s)
          </p>
        </div>
      </div>

      <DischargeChart series={data.series} thresholds={thresholds} peakDate={data.peak_date} />

      <table className="hz-table">
        <thead>
          <tr>
            <th>Flood level</th>
            <th>Discharge</th>
            <th>Alert</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>2-year</td>
            <td>{thresholds['2']} m³/s</td>
            <td>Low</td>
          </tr>
          <tr>
            <td>5-year</td>
            <td>{thresholds['5']} m³/s</td>
            <td>Medium</td>
          </tr>
          <tr>
            <td>20-year</td>
            <td>{thresholds['20']} m³/s</td>
            <td>High</td>
          </tr>
        </tbody>
      </table>

      <p className="hz-fine">
        Nearest river in the 5 km model cell at {data.river_cell.latitude}, {data.river_cell.longitude}.
        Levels come from {data.history.years_used} yearly peaks ({data.history.period}); average flow{' '}
        {data.history.mean_flow_m3s} m³/s.
      </p>
      <ul className="hz-caveats">
        {data.caveats.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
    </>
  )
}

function RainBar({ label, mm, thresholdMm, ratio }) {
  const percent = Math.min(ratio, 1.5) / 1.5 * 100
  const marker = (1 / 1.5) * 100
  const color = ratio >= 1 ? '#e74752' : ratio >= 0.6 ? '#e08a00' : '#3478f6'

  return (
    <div className="hz-rainbar">
      <div className="hz-rainbar-top">
        <span>{label}</span>
        <strong>
          {mm} mm of {thresholdMm} mm
        </strong>
      </div>
      <div className="hz-track">
        <div className="hz-fill" style={{ width: `${percent}%`, background: color }}></div>
        <div className="hz-marker" style={{ left: `${marker}%` }} title="Threshold"></div>
      </div>
    </div>
  )
}

export function LandslideView({ data }) {
  const { rain, terrain } = data

  return (
    <>
      <div className="hz-summary">
        <LevelBadge level={data.level} />
        <div>
          <strong>
            {terrain.class.charAt(0).toUpperCase() + terrain.class.slice(1)} terrain, rain at{' '}
            {Math.round(rain.ratio * 100)}% of the threshold
          </strong>
          <p>{data.scenario ? 'What-if scenario (not a forecast)' : 'Live rainfall forecast'}</p>
        </div>
      </div>

      <div className="hz-tiles">
        <div className="hz-tile">
          <span>Average slope</span>
          <strong>{terrain.mean_slope_deg}°</strong>
          <small>
            steepest {terrain.steepest_slope_deg}° · {data.elevation_m} m
          </small>
        </div>
        <div className="hz-tile">
          <span>Rain scenario</span>
          <strong>{rain.rain_24h_mm} mm</strong>
          <small>in 24 h ({rain.rain_72h_mm} mm in 72 h)</small>
        </div>
      </div>

      <RainBar label="24 hours" mm={rain.rain_24h_mm} thresholdMm={rain.threshold_24h_mm} ratio={rain.ratio_24h} />
      <RainBar label="72 hours" mm={rain.rain_72h_mm} thresholdMm={rain.threshold_72h_mm} ratio={rain.ratio_72h} />
      <p className="hz-fine">The line marks the global minimum rainfall that has triggered landslides (Caine, 1980).</p>

      <ul className="hz-explain">
        {data.explanation.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
      <ul className="hz-caveats">
        {data.caveats.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
    </>
  )
}

function FloodPanel() {
  const [pointIndex, setPointIndex] = useState(0)
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    const point = FLOOD_POINTS[pointIndex]

    getFloodRisk(point.latitude, point.longitude)
      .then((result) => {
        if (cancelled) return
        setData(result)
        setError('')
        setLoading(false)
      })
      .catch((problem) => {
        if (cancelled) return
        setData(null)
        setError(problem.message)
        setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [pointIndex])

  const choose = (event) => {
    setLoading(true)
    setPointIndex(Number(event.target.value))
  }

  return (
    <div className="panel">
      <div className="panel-header">
        <div>
          <h3>Flood Risk</h3>
          <p>River discharge forecast vs flood levels</p>
        </div>
        <span className="hz-tag">GloFAS · 7-day</span>
      </div>

      <select className="hz-select" value={pointIndex} onChange={choose} aria-label="River location">
        {FLOOD_POINTS.map((point, index) => (
          <option key={point.name} value={index}>
            {point.name}
          </option>
        ))}
      </select>

      {loading && <p className="hz-empty">Loading river data. The first request for a river can take a few seconds.</p>}
      {!loading && error && <p className="hz-error">{error}</p>}
      {!loading && data && <FloodView data={data} />}
    </div>
  )
}

function LandslidePanel() {
  const [pointIndex, setPointIndex] = useState(0)
  const [scenario, setScenario] = useState(null)
  const [rain24Input, setRain24Input] = useState('')
  const [rain72Input, setRain72Input] = useState('')
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const rain24 = scenario ? scenario.rain24 : null
  const rain72 = scenario ? scenario.rain72 : null

  useEffect(() => {
    let cancelled = false
    const point = SLOPE_POINTS[pointIndex]
    const what = rain24 === null ? null : { rain24, rain72 }

    getLandslideRisk(point.latitude, point.longitude, what)
      .then((result) => {
        if (cancelled) return
        setData(result)
        setError('')
        setLoading(false)
      })
      .catch((problem) => {
        if (cancelled) return
        setData(null)
        setError(problem.message)
        setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [pointIndex, rain24, rain72])

  const choose = (event) => {
    setLoading(true)
    setPointIndex(Number(event.target.value))
  }

  const runScenario = (first, second) => {
    setLoading(true)
    setRain24Input(String(first))
    setRain72Input(String(second))
    setScenario({ rain24: first, rain72: second })
  }

  const runCustom = (event) => {
    event.preventDefault()
    const first = Number(rain24Input)
    const second = rain72Input === '' ? first : Number(rain72Input)
    if (rain24Input === '' || Number.isNaN(first) || Number.isNaN(second)) {
      setError('Enter the rainfall in millimetres as numbers.')
      return
    }
    runScenario(first, second)
  }

  const useLive = () => {
    setLoading(true)
    setScenario(null)
  }

  return (
    <div className="panel">
      <div className="panel-header">
        <div>
          <h3>Landslide Risk</h3>
          <p>Rainfall threshold and terrain slope</p>
        </div>
        <span className="hz-tag">{scenario ? 'What-if' : 'Live forecast'}</span>
      </div>

      <select className="hz-select" value={pointIndex} onChange={choose} aria-label="Landslide location">
        {SLOPE_POINTS.map((point, index) => (
          <option key={point.name} value={index}>
            {point.name}
          </option>
        ))}
      </select>

      <div className="hz-scenario">
        <span>Try a what-if rainfall:</span>
        <div className="hz-chips">
          {SCENARIOS.map((item) => (
            <button key={item.label} type="button" onClick={() => runScenario(item.rain24, item.rain72)}>
              {item.label}
            </button>
          ))}
          {scenario && (
            <button type="button" className="hz-live" onClick={useLive}>
              Back to live forecast
            </button>
          )}
        </div>
        <form className="hz-custom" onSubmit={runCustom}>
          <input
            value={rain24Input}
            onChange={(event) => setRain24Input(event.target.value)}
            inputMode="decimal"
            placeholder="mm in 24 h"
            aria-label="Rain in 24 hours, millimetres"
          />
          <input
            value={rain72Input}
            onChange={(event) => setRain72Input(event.target.value)}
            inputMode="decimal"
            placeholder="mm in 72 h"
            aria-label="Rain in 72 hours, millimetres"
          />
          <button type="submit">Run</button>
        </form>
      </div>

      {loading && <p className="hz-empty">Loading terrain and rainfall...</p>}
      {!loading && error && <p className="hz-error">{error}</p>}
      {!loading && data && <LandslideView data={data} />}
    </div>
  )
}

export default function HazardRisk() {
  return (
    <>
      <div className="hz-intro">
        These are risk screenings built from real data and published methods, not machine-learning
        predictions. There are no labelled flood or landslide records to train a model on, so each
        result shows the rule behind it.
      </div>

      <section className="hz-grid">
        <FloodPanel />
        <LandslidePanel />
      </section>

      <p className="hz-attribution">
        Data: Open-Meteo.com (weather forecast, GloFAS river discharge from the Copernicus Emergency
        Management Service, Copernicus DEM elevation). Indicative screening only, not official warnings.
      </p>
    </>
  )
}
