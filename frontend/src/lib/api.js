export async function getPublicConfig() {
  const r = await fetch('/api/config/public')
  return r.json()
}

export async function fetchPasses(body) {
  const r = await fetch('/api/passes', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!r.ok) throw new Error((await r.json()).detail || 'Failed')
  return r.json()
}

export async function fetchMargin(body) {
  const r = await fetch('/api/margin', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!r.ok) throw new Error((await r.json()).detail || 'Failed')
  return r.json()
}

export async function exportICS(body) {
  const r = await fetch('/api/export/ics', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const data = await r.json()
  return data.ics
}

export async function exportPDF(body) {
  const r = await fetch('/api/export/pdf', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!r.ok) throw new Error('PDF export failed')
  const blob = await r.blob()
  return blob
}
