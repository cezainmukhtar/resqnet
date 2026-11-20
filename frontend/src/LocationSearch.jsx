// src/LocationSearch.jsx
import { useState } from 'react'
import { searchLocations } from './api'
import { useMonitoredLocation } from './LocationContext'

export default function LocationSearch() {
  const { location, setLocation } = useMonitoredLocation()
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [busy, setBusy] = useState(false)

  const onSearch = async (e) => {
    e.preventDefault()
    if (!query.trim()) return
    setBusy(true)
    try {
      setResults(await searchLocations(query))
    } catch {
      setResults([])
    } finally {
      setBusy(false)
    }
  }

  const pick = (place) => {
    setLocation(place)
    setResults([])
    setQuery('')
  }

  return (
    <div>
      <form onSubmit={onSearch}>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={`Monitoring: ${location.name}. Search a place...`}
        />
        <button type="submit" disabled={busy}>{busy ? '...' : 'Search'}</button>
      </form>
      <ul>
        {results.map((p) => (
          <li key={`${p.latitude},${p.longitude}`}>
            <button type="button" onClick={() => pick(p)}>{p.name}</button>
          </li>
        ))}
      </ul>
    </div>
  )
}