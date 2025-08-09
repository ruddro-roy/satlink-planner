"use client";
import { useEffect } from "react";
import { useAppStore } from "@/state/useAppStore";
import { motion } from "framer-motion";

export default function ControlPanel() {
  const {
    query,
    setQuery,
    setSelectedNoradId,
    ground,
    setGround,
    timeRangeHours,
    setTimeRangeHours,
    band,
    setBand,
  } = useAppStore();

  useEffect(() => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition((pos) => {
        setGround({ lat: pos.coords.latitude, lon: pos.coords.longitude, elevation: 0 });
      });
    }
  }, [setGround]);

  function resolveQueryToNorad(q: string): string | null {
    const lower = q.trim().toLowerCase();
    if (!lower) return null;
    if (/[0-9]{5}/.test(lower)) return lower.match(/[0-9]{5}/)![0];
    if (lower.includes("iss")) return "25544";
    if (lower.includes("starlink")) return "44238"; // sample Starlink NORAD
    return null;
  }

  return (
    <motion.div
      initial={{ y: -12, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.5 }}
      className="w-full rounded-xl bg-zinc-900/70 backdrop-blur border border-zinc-800 p-4 md:p-6 text-zinc-100"
    >
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
        <div>
          <label className="text-sm text-zinc-400">Search</label>
          <input
            className="mt-1 w-full rounded-lg bg-zinc-800 border border-zinc-700 px-3 py-2 outline-none focus:ring-2 ring-cyan-400"
            placeholder="Track ISS or find Starlink passes"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <div>
          <label className="text-sm text-zinc-400">Location</label>
          <div className="mt-1 grid grid-cols-2 gap-2">
            <input
              className="rounded-lg bg-zinc-800 border border-zinc-700 px-3 py-2"
              placeholder="Lat"
              type="number"
              value={ground.lat}
              onChange={(e) => setGround({ lat: parseFloat(e.target.value) })}
            />
            <input
              className="rounded-lg bg-zinc-800 border border-zinc-700 px-3 py-2"
              placeholder="Lon"
              type="number"
              value={ground.lon}
              onChange={(e) => setGround({ lon: parseFloat(e.target.value) })}
            />
          </div>
        </div>
        <div>
          <label className="text-sm text-zinc-400">Time</label>
          <input
            className="mt-1 w-full accent-cyan-400"
            type="range"
            min={1}
            max={72}
            value={timeRangeHours}
            onChange={(e) => setTimeRangeHours(parseInt(e.target.value))}
          />
          <div className="text-xs text-zinc-400 mt-1">Next {timeRangeHours} hours</div>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="text-sm text-zinc-400">Band</label>
            <select
              className="mt-1 w-full rounded-lg bg-zinc-800 border border-zinc-700 px-3 py-2"
              value={band}
              onChange={(e) => setBand((e.target.value === "ka" ? "ka" : "ku"))}
            >
              <option value="ku">Ku</option>
              <option value="ka">Ka</option>
            </select>
          </div>
          <button
            onClick={() => {
              const resolved = resolveQueryToNorad(query);
              setSelectedNoradId(resolved || "25544");
            }}
            className="mt-6 h-10 rounded-lg bg-cyan-500 hover:bg-cyan-400 transition-colors text-black font-semibold shadow-lg shadow-cyan-500/20"
          >
            Plan My Link
          </button>
        </div>
      </div>
    </motion.div>
  );
}


