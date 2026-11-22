import { createContext, useContext, useState } from 'react'
import { MONITORED_LOCATION } from './api'

const LocationContext = createContext(null)

export function LocationProvider({ children }) {
  const [location, setLocation] = useState(MONITORED_LOCATION)
  return (
    <LocationContext.Provider value={{ location, setLocation }}>
      {children}
    </LocationContext.Provider>
  )
}

export const useMonitoredLocation = () => useContext(LocationContext)