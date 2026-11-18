import './RainOutlook.css'

const FEATURE_LABELS = {
  surface_pressure: 'Air pressure',
  pressure_change_3h: 'Pressure change (3 h)',
  pressure_change_12h: 'Pressure change (12 h)',
  pressure_change_24h: 'Pressure change (24 h)',
  dew_point_2m: 'Dew point',
  temp_dew_spread: 'Temperature minus dew point',
  temperature_2m: 'Temperature',
  temp_change_24h: 'Temperature change (24 h)',
  relative_humidity_2m: 'Humidity',
  humidity_change_6h: 'Humidity change (6 h)',
  cloud_cover: 'Cloud cover',
  wind_speed_10m: 'Wind speed',
  wind_dir_sin: 'Wind direction',
  wind_dir_cos: 'Wind direction',
  rain_last_3h: 'Rain in the last 3 h',
  rain_last_24h: 'Rain in the last 24 h',
  hour_sin: 'Time of day',
  hour_cos: 'Time of day',
  doy_sin: 'Time of year',
  doy_cos: 'Time of year',
}

const LEVEL_COLOR = { Unlikely: '#35ae7a', Possible: '#f0a534', Likely: '#3478f6' }

function score(value) {
  return typeof value === 'number' ? value.toFixed(2) : '--'
}

export default function RainOutlook({ outlook, error, location }) {
  if (!outlook) {
    return (
      <section className="panel ro-panel">
        <div className="panel-header">
          <div>
            <h3>AI Rain Outlook</h3>
            <p>Machine-learning estimate for the next 24 hours</p>
          </div>
          <span className="ro-tag">Machine learning</span>
        </div>
        <p className="ro-empty">{error || 'Loading rain outlook...'}</p>
      </section>
    )
  }

  const model = outlook.model
  const test = model.test_scores
  const climatology = model.baselines.climatology_by_month
  const persistence = model.baselines.rained_in_last_24h

  // Several features describe the same thing (e.g. wind direction); list each once
  const seen = new Set()
  const drivers = []
  for (const item of model.top_features) {
    const label = FEATURE_LABELS[item.feature] || item.feature
    if (!seen.has(label)) {
      seen.add(label)
      drivers.push(label)
    }
  }

  return (
    <section className="panel ro-panel">
      <div className="panel-header">
        <div>
          <h3>AI Rain Outlook</h3>
          <p>
            Chance of {model.target.replace('at least ', '≥ ')} · {location.name}
          </p>
        </div>
        <span className="ro-tag">Machine learning</span>
      </div>

      {error && <div className="ro-warning">{error}. Showing the last result.</div>}

      <div className="ro-body">
        <div className="ro-gauge">
          <div className="ro-percent" style={{ color: LEVEL_COLOR[outlook.level] }}>
            {outlook.percent}%
          </div>
          <div className="ro-level">{outlook.level}</div>
          <div className="ro-bar">
            <div
              style={{ width: `${outlook.percent}%`, background: LEVEL_COLOR[outlook.level] }}
            ></div>
          </div>
          <small>Based on weather data for {outlook.data_time} UTC</small>
        </div>

        <div className="ro-details">
          <h4>How well it works</h4>
          <p className="ro-small">
            Tested on {model.split.test.replace('from ', 'weather from ')}, which the model
            never saw while learning. ROC-AUC: 1.0 is perfect, 0.5 is guessing.
          </p>
          <table className="ro-table">
            <tbody>
              <tr>
                <td>This model</td>
                <td>
                  <strong>{score(test.roc_auc)}</strong>
                </td>
              </tr>
              <tr>
                <td>Typical rain for the month</td>
                <td>{score(climatology.roc_auc)}</td>
              </tr>
              <tr>
                <td>&ldquo;Did it rain in the last 24 h?&rdquo;</td>
                <td>{score(persistence.roc_auc)}</td>
              </tr>
            </tbody>
          </table>

          <h4>What it looks at</h4>
          <p className="ro-small">{drivers.slice(0, 5).join(' · ')}</p>
        </div>
      </div>

      <p className="ro-note">
        Trained on {model.data_range.from} to {model.data_range.to} ({model.data_source}) for{' '}
        {location.name} only. It estimates a chance from recent conditions and does not
        replace the forecast-based alerts or official IMD warnings.
      </p>
    </section>
  )
}
