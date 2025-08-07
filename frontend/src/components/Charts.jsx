import React, { useMemo } from 'react'
import { Line } from 'react-chartjs-2'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend)

export default function Charts({ pass0, margin }) {
  const timeLabels = useMemo(() => (pass0?.samples || []).map(s => new Date(s.t).toLocaleTimeString('en-GB', { hour12: false })), [pass0])
  const elevData = useMemo(() => (pass0?.samples || []).map(s => s.elev_deg), [pass0])
  const snrData = useMemo(() => (margin?.points || []).map(p => p.snr_db), [margin])

  return (
    <div className="grid grid-cols-1 gap-4">
      <div className="border rounded p-2">
        <div className="font-medium mb-1">Elevation vs Time (deg)</div>
        <Line
          data={{
            labels: timeLabels,
            datasets: [
              {
                label: 'Elevation',
                data: elevData,
                borderColor: 'rgb(59,130,246)',
                backgroundColor: 'rgba(59,130,246,0.3)',
                tension: 0.2,
              }
            ]
          }}
          options={{
            responsive: true,
            plugins: { legend: { display: true } },
            scales: { y: { beginAtZero: true, title: { display: true, text: 'deg' } } }
          }}
        />
      </div>
      <div className="border rounded p-2">
        <div className="font-medium mb-1">SNR vs Time (dB)</div>
        <Line
          data={{
            labels: timeLabels,
            datasets: [
              {
                label: 'SNR',
                data: snrData,
                borderColor: 'rgb(16,185,129)',
                backgroundColor: 'rgba(16,185,129,0.3)',
                tension: 0.2,
              }
            ]
          }}
          options={{
            responsive: true,
            plugins: { legend: { display: true } },
            scales: { y: { title: { display: true, text: 'dB' } } }
          }}
        />
      </div>
    </div>
  )
}
