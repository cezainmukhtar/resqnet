import './Alerts.css'

const SEVERITY_LABEL = { high: 'High', medium: 'Medium', low: 'Low' }

export default function Alerts({ alertData, error, location }) {
  if (!alertData) {
    return (
      <section className="panel">
        <p className="al-empty">{error || 'Loading alerts...'}</p>
      </section>
    )
  }

  const { alerts, summary, rules } = alertData

  return (
    <>
      {error && <div className="al-warning">{error}. Showing the last data received.</div>}

      <section className="al-grid">
        <div className="panel">
          <div className="panel-header">
            <div>
              <h3>Active Alerts</h3>
              <p>
                {location.name} · next {alertData.window_hours} hours
              </p>
            </div>
            <span className="alert-count">{String(alerts.length).padStart(2, '0')}</span>
          </div>

          {alerts.length === 0 ? (
            <p className="al-empty">
              No active alerts. Every forecast value for the next{' '}
              {alertData.window_hours} hours is below the alert thresholds.
            </p>
          ) : (
            alerts.map((alert) => (
              <div className="al-item" key={alert.id}>
                <span className={`alert-indicator ${alert.severity}`}></span>
                <div>
                  <div className="al-item-top">
                    <strong>{alert.title}</strong>
                    <span className={`al-badge ${alert.severity}`}>
                      {SEVERITY_LABEL[alert.severity]} priority
                    </span>
                  </div>
                  <p>{alert.message}</p>
                  <small>
                    {alert.metric_label}: {alert.value} {alert.unit} (alert level{' '}
                    {alert.threshold} {alert.unit} or more)
                  </small>
                </div>
              </div>
            ))
          )}
        </div>

        <div className="panel">
          <div className="panel-header">
            <div>
              <h3>Forecast Summary</h3>
              <p>What the alerts are based on</p>
            </div>
          </div>

          <div className="al-metrics">
            <div className="al-metric">
              <span>Rain</span>
              <strong>
                {summary.rain_24h_mm ?? '--'} <small>mm</small>
              </strong>
            </div>
            <div className="al-metric">
              <span>Peak gust</span>
              <strong>
                {summary.max_gust_kmh ?? '--'} <small>km/h</small>
              </strong>
            </div>
            <div className="al-metric">
              <span>Peak temp</span>
              <strong>
                {summary.max_temp_c ?? '--'} <small>°C</small>
              </strong>
            </div>
          </div>

          <p className="al-stamp">
            Overall risk: <strong>{alertData.risk_level}</strong>
            <br />
            Forecast fetched {alertData.forecast_fetched_at} UTC
            <br />
            Alerts generated {alertData.generated_at} UTC
          </p>
        </div>
      </section>

      <section className="panel al-rules">
        <div className="panel-header">
          <div>
            <h3>How these alerts are generated</h3>
            <p>Fixed rules applied to the live Open-Meteo forecast</p>
          </div>
        </div>

        <div className="al-table-wrap">
          <table className="al-table">
            <thead>
              <tr>
                <th>Alert</th>
                <th>Priority</th>
                <th>Triggers when</th>
                <th>Basis</th>
              </tr>
            </thead>
            <tbody>
              {rules.map((rule) => (
                <tr key={`${rule.category}-${rule.threshold}`}>
                  <td>{rule.title}</td>
                  <td>
                    <span className={`al-badge ${rule.severity}`}>
                      {SEVERITY_LABEL[rule.severity]}
                    </span>
                  </td>
                  <td>
                    {rule.metric_label} ≥ {rule.threshold} {rule.unit}
                  </td>
                  <td>{rule.basis}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <p className="al-note">
          These alerts are indicative and generated automatically from forecast
          data. They are not official warnings. Rain levels follow IMD 24-hour
          rainfall categories, wind levels follow the Beaufort scale, and heat
          levels follow IMD maximum-temperature thresholds (without IMD's
          departure-from-normal and multi-day checks). For official warnings,
          check the India Meteorological Department.
        </p>
      </section>
    </>
  )
}
