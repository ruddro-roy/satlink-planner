"use client";
import { useEffect, useMemo } from "react";
import { useAppStore } from "@/state/useAppStore";
import { motion } from "framer-motion";

export default function ControlPanel() {
  type Category = 'All' | 'ISS' | 'Starlink' | 'GPS' | 'Military' | 'Weather';
  type Altitude = 'All' | 'LEO' | 'MEO' | 'GEO';
  type Frequency = 'All' | 'VHF' | 'UHF' | 'L' | 'S' | 'C' | 'X' | 'Ku' | 'Ka';
  type Purpose = 'All' | 'Communication' | 'Navigation' | 'Earth Observation';

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
    favorites,
    addFavorite,
    removeFavorite,
    recentSearches,
    addRecentSearch,
    filters,
    setFilters,
    professionalMode,
    setProfessionalMode,
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

  const isFavorite = useMemo(() => (id: string) => favorites.includes(id), [favorites]);

  return (
    <motion.div
      initial={{ y: -12, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.5 }}
      className="w-full rounded-xl bg-zinc-900/70 backdrop-blur border border-zinc-800 p-4 md:p-6 text-zinc-100"
    >
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
        <div className="satellite-search">
          <label className="text-sm text-zinc-400">Search</label>
          <input
            className="mt-1 w-full rounded-lg bg-zinc-800 border border-zinc-700 px-3 py-2 outline-none focus:ring-2 ring-cyan-400"
            placeholder="Track ISS or find Starlink passes"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          {recentSearches.length > 0 && (
            <div className="mt-2 flex gap-2 flex-wrap text-xs text-zinc-400">
              {recentSearches.map((s, i) => (
                <button key={i} onClick={() => setQuery(s)} className="rounded-md bg-zinc-800/60 border border-zinc-700 px-2 py-1 hover:bg-zinc-700">
                  {s}
                </button>
              ))}
            </div>
          )}
        </div>
        <div className="location-picker">
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
              const norad = resolved || "25544";
              setSelectedNoradId(norad);
              addRecentSearch(query || norad);
            }}
            className="mt-6 h-10 rounded-lg bg-cyan-500 hover:bg-cyan-400 transition-colors text-black font-semibold shadow-lg shadow-cyan-500/20"
          >
            Plan My Link
          </button>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-3">
        <div>
          <label className="text-sm text-zinc-400">Category</label>
          <select className="mt-1 w-full rounded-lg bg-zinc-800 border border-zinc-700 px-3 py-2" value={filters.category}
                  onChange={(e) => setFilters({ category: e.target.value as Category })}>
            {['All','ISS','Starlink','GPS','Military','Weather'].map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-sm text-zinc-400">Altitude</label>
          <select className="mt-1 w-full rounded-lg bg-zinc-800 border border-zinc-700 px-3 py-2" value={filters.altitude}
                  onChange={(e) => setFilters({ altitude: e.target.value as Altitude })}>
            {['All','LEO','MEO','GEO'].map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-sm text-zinc-400">Frequency</label>
          <select className="mt-1 w-full rounded-lg bg-zinc-800 border border-zinc-700 px-3 py-2" value={filters.frequency}
                  onChange={(e) => setFilters({ frequency: e.target.value as Frequency })}>
            {['All','VHF','UHF','L','S','C','X','Ku','Ka'].map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-sm text-zinc-400">Purpose</label>
          <select className="mt-1 w-full rounded-lg bg-zinc-800 border border-zinc-700 px-3 py-2" value={filters.purpose}
                  onChange={(e) => setFilters({ purpose: e.target.value as Purpose })}>
            {['All','Communication','Navigation','Earth Observation'].map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="mt-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={() => {
              const resolved = resolveQueryToNorad(query);
              if (resolved) {
                if (isFavorite(resolved)) {
                  removeFavorite(resolved);
                } else {
                  addFavorite(resolved);
                }
              }
            }}
            className="h-9 px-3 rounded-lg bg-zinc-800 border border-zinc-700 hover:bg-zinc-700 text-sm"
          >
            Toggle Favorite
          </button>
          {favorites.length > 0 && (
            <div className="text-xs text-zinc-400">Favorites: {favorites.join(', ')}</div>
          )}
        </div>
        <label className="inline-flex items-center gap-2 text-sm text-zinc-300">
          <input type="checkbox" className="accent-cyan-400" checked={professionalMode} onChange={(e) => setProfessionalMode(e.target.checked)} />
          Professional Mode
        </label>
      </div>
    </motion.div>
  );
}


