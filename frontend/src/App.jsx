import React from 'react'
import LocationPicker from './components/LocationPicker'
import PassForm from './components/PassForm'

export default function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      <header className="sticky top-0 z-10 bg-white shadow">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="text-lg font-semibold">Satlink Planner</div>
          <a className="text-sm text-blue-600" href="https://celestrak.org" target="_blank" rel="noreferrer">TLE via Celestrak</a>
        </div>
      </header>
      <main className="max-w-5xl mx-auto px-4 py-4 grid gap-4 md:grid-cols-2">
        <section className="space-y-3">
          <div className="bg-white rounded shadow p-4">
            <h2 className="font-semibold mb-2">Pick Location</h2>
            <LocationPicker />
          </div>
        </section>
        <section className="space-y-3">
          <div className="bg-white rounded shadow p-4">
            <h2 className="font-semibold mb-2">Plan Passes</h2>
            <PassForm />
          </div>
          <div className="text-xs text-gray-500">Times shown in your local timezone; API computes in UTC.</div>
        </section>
      </main>
      <footer className="text-center text-xs text-gray-500 py-4">No secrets in client. Keys injected via backend config endpoint.</footer>
    </div>
  )
}
