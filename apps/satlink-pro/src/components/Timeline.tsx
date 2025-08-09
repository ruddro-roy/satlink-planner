"use client";
import { PassesResponse } from "@/lib/api";
import { format } from "date-fns";

export default function Timeline({ data }: { data: PassesResponse | null }) {
  const passes = data?.passes || [];
  return (
    <div className="w-full rounded-xl bg-zinc-900/70 backdrop-blur border border-zinc-800 p-4 md:p-6 text-zinc-100">
      <div className="text-sm text-zinc-400 mb-2">Upcoming Passes</div>
      <div className="space-y-3">
        {passes.length === 0 && <div className="text-zinc-400 text-sm">No passes in window.</div>}
        {passes.map((p, i) => (
          <div key={i} className="flex items-center justify-between rounded-lg bg-zinc-800/60 border border-zinc-700 p-3">
            <div className="text-sm">
              <div className="font-medium">Rise {format(new Date(p.rise), "PPpp")}</div>
              <div className="text-zinc-400">Max {p.max_elevation_deg.toFixed(0)}° • {Math.round(p.duration_s/60)} min</div>
            </div>
            <div className="text-xs text-zinc-400">Set {format(new Date(p.set), "PPpp")}</div>
          </div>
        ))}
      </div>
    </div>
  );
}


