import { useState } from 'react'
import { createReport } from './api'
import './RescueReports.css'

const TYPES = ['Flood', 'Landslide', 'Fire', 'Earthquake', 'Medical', 'Other']

const EMPTY_FORM = {
  name: '',
  emergency_type: 'Flood',
  description: '',
  location: '',
  latitude: '',
  longitude: '',
}

export default function RescueReports({ reports, onSubmitted }) {
  const [form, setForm] = useState(EMPTY_FORM)
  const [submitting, setSubmitting] = useState(false)
  const [message, setMessage] = useState(null)

  const update = (event) => {
    const { name, value } = event.target
    setForm((previous) => ({ ...previous, [name]: value }))
  }

  const useMyLocation = () => {
    if (!navigator.geolocation) {
      setMessage({ type: 'error', text: 'This browser does not support location.' })
      return
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        setForm((previous) => ({
          ...previous,
          latitude: position.coords.latitude.toFixed(5),
          longitude: position.coords.longitude.toFixed(5),
        }))
        setMessage(null)
      },
      () =>
        setMessage({
          type: 'error',
          text: 'Could not get your location. Enter the coordinates manually.',
        })
    )
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    setMessage(null)

    if (form.latitude === '' || form.longitude === '') {
      setMessage({ type: 'error', text: 'Latitude and longitude are required.' })
      return
    }

    setSubmitting(true)
    try {
      const result = await createReport({
        ...form,
        latitude: Number(form.latitude),
        longitude: Number(form.longitude),
      })
      setMessage({ type: 'success', text: `Report #${result.report_id} submitted.` })
      setForm(EMPTY_FORM)
      onSubmitted()
    } catch (error) {
      setMessage({ type: 'error', text: error.message })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section className="rr-grid">
      <div className="panel">
        <div className="panel-header">
          <div>
            <h3>Report an Emergency</h3>
            <p>Share what is happening and where</p>
          </div>
        </div>

        <form className="rr-form" onSubmit={handleSubmit}>
          <div className="rr-field">
            <label htmlFor="rr-name">Your name</label>
            <input
              id="rr-name"
              className="rr-input"
              name="name"
              value={form.name}
              onChange={update}
              maxLength={100}
              required
            />
          </div>

          <div className="rr-field">
            <label htmlFor="rr-type">Emergency type</label>
            <select
              id="rr-type"
              className="rr-input"
              name="emergency_type"
              value={form.emergency_type}
              onChange={update}
            >
              {TYPES.map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </select>
          </div>

          <div className="rr-field">
            <label htmlFor="rr-location">Place or landmark</label>
            <input
              id="rr-location"
              className="rr-input"
              name="location"
              value={form.location}
              onChange={update}
              maxLength={200}
              placeholder="e.g. Near Pari Chowk, Greater Noida"
              required
            />
          </div>

          <div className="rr-row">
            <div className="rr-field">
              <label htmlFor="rr-lat">Latitude</label>
              <input
                id="rr-lat"
                className="rr-input"
                name="latitude"
                value={form.latitude}
                onChange={update}
                inputMode="decimal"
                placeholder="28.4744"
              />
            </div>
            <div className="rr-field">
              <label htmlFor="rr-lon">Longitude</label>
              <input
                id="rr-lon"
                className="rr-input"
                name="longitude"
                value={form.longitude}
                onChange={update}
                inputMode="decimal"
                placeholder="77.5040"
              />
            </div>
          </div>

          <button type="button" className="rr-secondary" onClick={useMyLocation}>
            Use my current location
          </button>

          <div className="rr-field">
            <label htmlFor="rr-description">What happened?</label>
            <textarea
              id="rr-description"
              className="rr-input"
              name="description"
              value={form.description}
              onChange={update}
              maxLength={1000}
              required
            />
          </div>

          <div className="rr-actions">
            <button type="submit" className="rr-submit" disabled={submitting}>
              {submitting ? 'Submitting...' : 'Submit report'}
            </button>
          </div>

          {message && (
            <div className={`rr-message ${message.type}`} role="status">
              {message.text}
            </div>
          )}
        </form>
      </div>

      <div className="panel">
        <div className="panel-header">
          <div>
            <h3>Submitted Reports</h3>
            <p>Newest first</p>
          </div>
          <span className="alert-count">{String(reports.length).padStart(2, '0')}</span>
        </div>

        {reports.length === 0 ? (
          <p className="rr-empty">No reports yet.</p>
        ) : (
          <div className="rr-list">
            {reports.map((report) => (
              <div className="rr-item" key={report.id}>
                <div className="rr-item-top">
                  <span className="rr-badge">{report.emergency_type}</span>
                  <small>{report.created_at} UTC</small>
                </div>
                <strong>{report.location}</strong>
                <p>{report.description}</p>
                <small>
                  Reported by {report.name} ·{' '}
                  {report.latitude != null && report.longitude != null
                    ? `${report.latitude.toFixed(4)}, ${report.longitude.toFixed(4)}`
                    : 'No coordinates'}
                </small>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  )
}
