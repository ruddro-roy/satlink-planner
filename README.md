## Satlink Planner

A mobile-first web app that, given any satellite (NORAD ID or name) and user location (via address or map), returns:
- Upcoming LEO pass predictions
- Link margin/SNR vs time
- Timeline chart, ICS export, PDF report

### Backend
- FastAPI + SQLite (no Postgres)
- Uses `sgp4`, `astropy`, `numpy`, `pyproj`
- Full error handling with Pydantic
- TLE from Celestrak via public API
- No secrets or tokens hardcoded — inject public API keys via `.env`

### Frontend
- React + Tailwind + Zustand
- Google Maps API to resolve location from map click or geolocation
- Times in UTC on API, rendered in local time on client
- Beginner mode = address-less; Advanced mode unlocks RF params
- Charts are lazy-loaded

### DevOps
- Single Dockerfile for API + frontend
- `render.yaml` included (no auto-deploy)
- `make dev`, `make run`, `make test`, `make export`

### Security
- No inline tokens or keys in source
- No exposed DB or secrets in client; Google Maps key is injected at runtime via `/api/config/public`
- All inputs validated/sanitized via FastAPI/Pydantic

---

## Quickstart (Local)

1) Copy `.env.example` to `.env` and set `GOOGLE_MAPS_API_KEY` (public key).

2) Install backend deps and run dev servers:

```
make dev
```
- Backend: http://localhost:8000
- Frontend: http://localhost:5173 (proxy to backend under `/api`)

3) Production-like run (serves built frontend via FastAPI):

```
make run
```

## API

- Health
```
curl -s http://localhost:8000/api/health
```

- Fetch TLE
```
curl -s http://localhost:8000/api/tle/25544
```

- Pass predictions
```
curl -s -X POST http://localhost:8000/api/passes \
  -H 'Content-Type: application/json' \
  -d '{
    "norad_id": 25544,
    "lat": 37.7749,
    "lon": -122.4194,
    "mask_deg": 10,
    "step_seconds": 10
  }'
```

- Link margin / SNR
```
curl -s -X POST http://localhost:8000/api/margin \
  -H 'Content-Type: application/json' \
  -d '{
    "samples": [{"t": "2024-01-01T00:00:00Z", "elev_deg": 10, "az_deg": 180, "range_km": 1200}],
    "band": "UHF",
    "tx_power_dbw": 10,
    "tx_gain_dbi": 5,
    "rx_gain_dbi": 20,
    "bandwidth_hz": 20000,
    "system_noise_temp_k": 290
  }'
```

- ICS export
```
curl -s -X POST http://localhost:8000/api/export/ics \
  -H 'Content-Type: application/json' \
  -d '{ "norad_id": 25544, "passes": [] }'
```

- PDF export
```
curl -s -X POST http://localhost:8000/api/export/pdf \
  -H 'Content-Type: application/json' \
  -d '{ "norad_id": 25544, "passes": [] }' \
  -o pass_report_25544.pdf
```

## Link Budget (simplified)
- Free-space loss: Lfs[dB] = 92.45 + 20 log10(f[GHz]) + 20 log10(R[km])
- EIRP[dBW] = Ptx[dBW] + Gtx[dBi]
- Prx[dBW] = EIRP + Grx - Lfs - L_atm - L_rain - L_point
- kTB[dBW] = -228.6 + 10 log10(T[K]) + 10 log10(B[Hz])
- SNR[dB] = Prx - (kTB + NF)

## Sample TLEs
A small set is under `data/sample_tles.json`.

## Notes
- This implementation uses a simplified TEME->ECEF rotation (GMST), which is adequate for planning purposes but not for precision orbit determination.
- All times are treated as UTC in the API; the frontend renders local-time labels.

