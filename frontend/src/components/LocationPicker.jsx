import React, { useEffect, useRef, useState } from 'react'
import { useAppStore } from '../store'
import { getPublicConfig } from '../lib/api'

function loadScript(src) {
  return new Promise((resolve, reject) => {
    const s = document.createElement('script')
    s.src = src
    s.async = true
    s.defer = true
    s.onload = resolve
    s.onerror = reject
    document.head.appendChild(s)
  })
}

export default function LocationPicker() {
  const mapRef = useRef(null)
  const markerRef = useRef(null)
  const inputRef = useRef(null)
  const [ready, setReady] = useState(false)
  const location = useAppStore((s) => s.location)
  const setLocation = useAppStore((s) => s.setLocation)

  useEffect(() => {
    async function init() {
      const cfg = await getPublicConfig()
      const key = cfg.google_maps_api_key
      if (!key) {
        console.warn('No GOOGLE_MAPS_API_KEY provided')
        return
      }
      if (!window.google) {
        await loadScript(`https://maps.googleapis.com/maps/api/js?key=${key}&libraries=places`)
      }
      const center = { lat: location?.lat || 37.7749, lng: location?.lon || -122.4194 }
      const map = new window.google.maps.Map(mapRef.current, {
        center,
        zoom: 4,
        disableDefaultUI: false,
      })
      const marker = new window.google.maps.Marker({ position: center, map })
      markerRef.current = marker
      map.addListener('click', (ev) => {
        const pos = { lat: ev.latLng.lat(), lon: ev.latLng.lng() }
        setLocation(pos)
        marker.setPosition({ lat: pos.lat, lng: pos.lon })
      })

      if (inputRef.current) {
        const autocomplete = new window.google.maps.places.Autocomplete(inputRef.current, { types: ['geocode'] })
        autocomplete.addListener('place_changed', () => {
          const place = autocomplete.getPlace()
          if (!place.geometry) return
          const pos = { lat: place.geometry.location.lat(), lon: place.geometry.location.lng() }
          setLocation(pos)
          map.setCenter({ lat: pos.lat, lng: pos.lon })
          map.setZoom(10)
          marker.setPosition({ lat: pos.lat, lng: pos.lon })
        })
      }

      setReady(true)
    }
    init().catch(console.error)
  }, [])

  const useMyLocation = () => {
    if (!navigator.geolocation) return
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const coords = { lat: pos.coords.latitude, lon: pos.coords.longitude }
        useAppStore.getState().setLocation(coords)
        if (markerRef.current && window.google) {
          markerRef.current.setPosition({ lat: coords.lat, lng: coords.lon })
        }
      },
      () => {
        alert('Unable to get location; please click on the map or enter address.')
      }
    )
  }

  return (
    <div className="space-y-2">
      <div className="flex gap-2 items-center">
        <button className="px-3 py-2 rounded bg-blue-600 text-white" onClick={useMyLocation}>Use my location</button>
        <input ref={inputRef} placeholder="Search address" className="flex-1 px-3 py-2 border rounded" />
      </div>
      <div ref={mapRef} className="w-full h-64 rounded border" />
      {location && (
        <div className="text-sm text-gray-700">Lat: {location.lat.toFixed(5)} Lon: {location.lon.toFixed(5)}</div>
      )}
    </div>
  )
}
