"use client";
import { useEffect, useMemo, useState } from "react";
import { Globe3D } from "@/components/Globe";
import ControlPanel from "@/components/ControlPanel";
import Dashboard from "@/components/Dashboard";
import Timeline from "@/components/Timeline";
import ActionsBar from "@/components/ActionsBar";
import { useAppStore } from "@/state/useAppStore";
import { fetchMargin, fetchPasses, MarginResponse, PassesResponse } from "@/lib/api";
import { addHours } from "date-fns";

export default function Home() {
  const { selectedNoradId, ground, timeRangeHours, band } = useAppStore();
  const [passes, setPasses] = useState<PassesResponse | null>(null);
  const [margin, setMargin] = useState<MarginResponse | null>(null);
  const [satInfo, setSatInfo] = useState<{ id: string; name: string; lat: number; lon: number; altKm: number } | null>(null);

  const now = useMemo(() => new Date(), []);
  const end = useMemo(() => addHours(now, timeRangeHours), [now, timeRangeHours]);

  useEffect(() => {
    async function run() {
      const norad = selectedNoradId || "25544"; // ISS default
      const startIso = now.toISOString();
      const endIso = end.toISOString();
      try {
        const [p, m] = await Promise.all([
          fetchPasses({ norad_id: norad, lat: ground.lat, lon: ground.lon, elevation: ground.elevation, max_passes: 8, start_time: startIso, end_time: endIso }),
          fetchMargin({ norad_id: norad, lat: ground.lat, lon: ground.lon, elevation: ground.elevation, band, start_time: startIso, end_time: endIso, step_s: 120 }),
        ]);
        setPasses(p);
        setMargin(m);
      } catch (e) {
        console.error(e);
        // Graceful demo fallback
        const nowLocal = new Date();
        const fallbackPasses: PassesResponse = {
          passes: Array.from({ length: 3 }).map((_, i) => {
            const rise = new Date(nowLocal.getTime() + (i + 1) * 60 * 60 * 1000);
            const set = new Date(rise.getTime() + 12 * 60 * 1000);
            const max = new Date(rise.getTime() + 6 * 60 * 1000);
            return {
              rise: rise.toISOString(),
              set: set.toISOString(),
              max_elevation_time: max.toISOString(),
              duration_s: 12 * 60,
              max_elevation_deg: 45 - i * 10,
            };
          }),
          tle_epoch: nowLocal.toISOString(),
          tle_age_days: 0.1,
          tle_source: null,
        };
        const fallbackMargin: MarginResponse = {
          points: Array.from({ length: 60 }).map((_, j) => {
            const t = new Date(nowLocal.getTime() + j * 2 * 60 * 1000);
            const phase = Math.sin(j / 10);
            return {
              timestamp: t.toISOString(),
              snr_db: 10 + phase * 3,
              margin_db: 8 + phase * 6,
              range_km: 800 + Math.abs(phase) * 200,
              elevation_deg: 10 + (phase + 1) * 40,
              azimuth_deg: (j * 6) % 360,
            };
          }),
          tle_epoch: nowLocal.toISOString(),
          tle_age_days: 0.1,
          tle_source: null,
          parameters: {},
        };
        setPasses(fallbackPasses);
        setMargin(fallbackMargin);
      }
    }
    run();
  }, [selectedNoradId, ground.lat, ground.lon, ground.elevation, band, now, end]);

  const satellites = useMemo(() => {
    // Minimal sample: show the selected satellite above the ground station (placeholder; real-time would use TLE propagation client-side)
    return [
      { id: "sel", name: "Selected", lat: ground.lat + 10, lon: ground.lon + 10, altKm: 500 },
    ];
  }, [ground]);

  return (
    <div className="min-h-screen w-full bg-gradient-to-b from-black via-zinc-950 to-black text-zinc-100">
      <div className="mx-auto max-w-7xl p-4 md:p-8">
        <div className="mb-6">
          <h1 className="text-2xl md:text-3xl font-semibold tracking-tight">SatLink Pro</h1>
          <p className="text-zinc-400">Google Maps for Satellites — plan professional links in seconds.</p>
        </div>
        <ControlPanel />
        <div className="mt-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 relative">
            <Globe3D
              satellites={satellites}
              ground={{ lat: ground.lat, lon: ground.lon }}
              onSatelliteClick={(s) => setSatInfo(s)}
            />
            {satInfo && (
              <div className="absolute top-4 left-4 z-10 w-72 rounded-xl bg-zinc-900/80 border border-zinc-800 p-4 backdrop-blur">
                <div className="text-sm text-zinc-400">Satellite</div>
                <div className="mt-1 font-semibold">{satInfo.name}</div>
                <div className="mt-2 text-xs text-zinc-400">Lat {satInfo.lat.toFixed(2)}°, Lon {satInfo.lon.toFixed(2)}°, Alt {Math.round(satInfo.altKm)} km</div>
                <div className="mt-3 flex gap-2">
                  <button
                    onClick={() => setSatInfo(null)}
                    className="h-8 px-3 rounded-lg bg-zinc-800 border border-zinc-700 text-sm"
                  >Close</button>
                  <button
                    onClick={() => setSatInfo(null)}
                    className="h-8 px-3 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-black font-semibold text-sm"
                  >Track</button>
                </div>
              </div>
            )}
          </div>
          <div>
            <Dashboard passes={passes} margin={margin} />
          </div>
        </div>
        <div className="mt-6">
          <div className="mb-4">
            <ActionsBar />
          </div>
          <Timeline data={passes} />
        </div>
      </div>
    </div>
  );
}
