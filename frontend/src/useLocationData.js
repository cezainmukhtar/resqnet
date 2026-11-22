import { useEffect, useState } from 'react'
import { useMonitoredLocation } from './LocationContext'

// Usage: const { data, loading, error } = useLocationData(getWeather)
// Re-runs whenever the monitored location changes.
export function useLocationData(fetcher, ...extraArgs) {
  const { location } = useMonitoredLocation()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let ignore = false
    setLoading(true)
    setError('')
    setData(null)

    fetcher(location.latitude, location.longitude, ...extraArgs)
      .then((result) => { if (!ignore) setData(result) })
      .catch((err) => { if (!ignore) setError(err.message) })
      .finally(() => { if (!ignore) setLoading(false) })

    return () => { ignore = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.latitude, location.longitude, fetcher, JSON.stringify(extraArgs)])

  return { data, loading, error }
}