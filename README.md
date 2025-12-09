## Satlink Planner

A mobile-first web app that, given any satellite (NORAD ID or name) and user location (via address or map), returns:
- Upcoming LEO pass predictions
- Link margin/SNR vs time
- Timeline chart, ICS export, PDF report


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

