import React, { useState, Suspense } from 'react'
import { useAppStore } from '../store'
import { fetchPasses, fetchMargin, exportICS, exportPDF } from '../lib/api'
const Charts = React.lazy(() => import('./Charts'))

function toIsoUtcLocalInput(value) {
  if (!value) return ''
  const d = new Date(value)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getUTCFullYear()}-${pad(d.getUTCMonth()+1)}-${pad(d.getUTCDate())}T${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`
}

export default function PassForm() {
  const mode = useAppStore((s) => s.mode)
  const setMode = useAppStore((s) => s.setMode)
  const location = useAppStore((s) => s.location)
  const noradId = useAppStore((s) => s.noradId)
  const setNoradId = useAppStore((s) => s.setNoradId)
  const passes = useAppStore((s) => s.passes)
  const setPasses = useAppStore((s) => s.setPasses)
  const rfParams = useAppStore((s) => s.rfParams)

  const [loading, setLoading] = useState(false)
  const [margin, setMargin] = useState(null)
  const [startIso, setStartIso] = useState(null)
  const [endIso, setEndIso] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    if (!noradId) return alert('Enter NORAD ID')
    if (!location) return alert('Select a location')
    setLoading(true)
    try {
      const body = {
        norad_id: Number(noradId),
        lat: location.lat,
        lon: location.lon,
        mask_deg: 10,
        start_iso: startIso ? new Date(startIso).toISOString() : undefined,
        end_iso: endIso ? new Date(endIso).toISOString() : undefined,
      }
      const resp = await fetchPasses(body)
      setPasses(resp.passes)
      if (resp.passes?.[0]?.samples?.length) {
        const m = await fetchMargin({
          samples: resp.passes[0].samples,
          ...rfParams,
        })
        setMargin(m)
      }
    } catch (e) {
      alert(e.message)
    } finally {
      setLoading(false)
    }
  }

  const onExportICS = async () => {
    const ics = await exportICS({ norad_id: Number(noradId), passes, title: 'Satlink Passes' })
    const blob = new Blob([ics], { type: 'text/calendar' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `passes_${noradId}.ics`
    a.click()
    URL.revokeObjectURL(url)
  }

  const onExportPDF = async () => {
    const blob = await exportPDF({ norad_id: Number(noradId), passes, title: 'Satlink Passes' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `passes_${noradId}.pdf`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-2 items-center">
        <div className="font-medium">Mode:</div>
        <button onClick={() => setMode('beginner')} className={`px-3 py-1 rounded ${mode==='beginner'?'bg-blue-600 text-white':'bg-gray-200'}`}>Beginner</button>
        <button onClick={() => setMode('advanced')} className={`px-3 py-1 rounded ${mode==='advanced'?'bg-blue-600 text-white':'bg-gray-200'}`}>Advanced</button>
      </div>
      <form onSubmit={submit} className="space-y-3">
        <div>
          <label className="block text-sm text-gray-700">NORAD ID</label>
          <input value={noradId} onChange={e=>setNoradId(e.target.value)} className="mt-1 w-full border rounded px-3 py-2" placeholder="e.g., 25544 for ISS" />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-sm">Start (UTC)</label>
            <input type="datetime-local" className="mt-1 w-full border rounded px-3 py-2" value={toIsoUtcLocalInput(startIso)} onChange={(e)=>setStartIso(e.target.value ? new Date(e.target.value + 'Z').toISOString() : null)} />
          </div>
          <div>
            <label className="block text-sm">End (UTC)</label>
            <input type="datetime-local" className="mt-1 w-full border rounded px-3 py-2" value={toIsoUtcLocalInput(endIso)} onChange={(e)=>setEndIso(e.target.value ? new Date(e.target.value + 'Z').toISOString() : null)} />
          </div>
        </div>

        {mode === 'advanced' && (
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm">Band</label>
              <select className="mt-1 w-full border rounded px-3 py-2" value={rfParams.band} onChange={(e)=>useAppStore.getState().setRfParams({ band: e.target.value })}>
                {['VHF','UHF','S','X','Ku','Ka'].map(b=> <option key={b} value={b}>{b}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm">TX Power (dBW)</label>
              <input type="number" className="mt-1 w-full border rounded px-3 py-2" value={rfParams.tx_power_dbw} onChange={(e)=>useAppStore.getState().setRfParams({ tx_power_dbw: Number(e.target.value) })} />
            </div>
            <div>
              <label className="block text-sm">TX Gain (dBi)</label>
              <input type="number" className="mt-1 w-full border rounded px-3 py-2" value={rfParams.tx_gain_dbi} onChange={(e)=>useAppStore.getState().setRfParams({ tx_gain_dbi: Number(e.target.value) })} />
            </div>
            <div>
              <label className="block text-sm">RX Gain (dBi)</label>
              <input type="number" className="mt-1 w-full border rounded px-3 py-2" value={rfParams.rx_gain_dbi} onChange={(e)=>useAppStore.getState().setRfParams({ rx_gain_dbi: Number(e.target.value) })} />
            </div>
            <div>
              <label className="block text-sm">Bandwidth (Hz)</label>
              <input type="number" className="mt-1 w-full border rounded px-3 py-2" value={rfParams.bandwidth_hz} onChange={(e)=>useAppStore.getState().setRfParams({ bandwidth_hz: Number(e.target.value) })} />
            </div>
            <div>
              <label className="block text-sm">System Noise Temp (K)</label>
              <input type="number" className="mt-1 w-full border rounded px-3 py-2" value={rfParams.system_noise_temp_k} onChange={(e)=>useAppStore.getState().setRfParams({ system_noise_temp_k: Number(e.target.value) })} />
            </div>
            <div>
              <label className="block textsm">Noise Figure (dB)</label>
              <input type="number" className="mt-1 w-full border rounded px-3 py-2" value={rfParams.noise_figure_db} onChange={(e)=>useAppStore.getState().setRfParams({ noise_figure_db: Number(e.target.value) })} />
            </div>
            <div>
              <label className="block text-sm">Rain Loss (dB)</label>
              <input type="number" className="mt-1 w-full border rounded px-3 py-2" value={rfParams.rain_loss_db} onChange={(e)=>useAppStore.getState().setRfParams({ rain_loss_db: Number(e.target.value) })} />
            </div>
            <div>
              <label className="block text-sm">Atmospheric Loss (dB)</label>
              <input type="number" className="mt-1 w-full border rounded px-3 py-2" value={rfParams.atm_loss_db} onChange={(e)=>useAppStore.getState().setRfParams({ atm_loss_db: Number(e.target.value) })} />
            </div>
            <div>
              <label className="block text-sm">Required SNR (dB)</label>
              <input type="number" className="mt-1 w-full border rounded px-3 py-2" value={rfParams.required_snr_db} onChange={(e)=>useAppStore.getState().setRfParams({ required_snr_db: Number(e.target.value) })} />
            </div>
          </div>
        )}
        <div className="text-xs text-gray-500">All times are converted to UTC before calling the API.</div>
        <button disabled={loading} className="px-4 py-2 rounded bg-green-600 text-white">{loading?'Calculating...':'Get Passes'}</button>
      </form>

      {passes?.length>0 && (
        <div className="space-y-3">
          <div className="flex gap-2">
            <button onClick={onExportICS} className="px-3 py-2 rounded bg-indigo-600 text-white">Export ICS</button>
            <button onClick={onExportPDF} className="px-3 py-2 rounded bg-purple-600 text-white">Export PDF</button>
          </div>
          <div className="border rounded p-3">
            <div className="font-medium mb-2">Upcoming Passes</div>
            <ul className="text-sm">
              {passes.map((p,i)=> (
                <li key={i} className="py-1">{p.aos_utc} → {p.los_utc} (max {p.max_elev_deg.toFixed(1)}°)</li>
              ))}
            </ul>
          </div>

          <Suspense fallback={<div>Loading charts…</div>}>
            <Charts pass0={passes[0]} margin={margin} />
          </Suspense>
        </div>
      )}
    </div>
  )
}
