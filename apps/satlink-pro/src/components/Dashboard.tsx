"use client";
import { useMemo } from "react";
import { motion } from "framer-motion";
import { MarginResponse, PassesResponse } from "@/lib/api";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { format } from "date-fns";
import Countdown from "./Countdown";

function TrafficLight({ marginDb }: { marginDb: number | null }) {
  const color = marginDb == null ? "bg-zinc-700" : marginDb >= 10 ? "bg-green-500" : marginDb >= 2 ? "bg-yellow-400" : "bg-red-500";
  const label = marginDb == null ? "N/A" : marginDb >= 10 ? "Excellent" : marginDb >= 2 ? "Marginal" : "Poor";
  return (
    <div className="flex items-center gap-3">
      <span className={`inline-block h-3 w-3 rounded-full ${color}`} />
      <span className="text-sm text-zinc-300">{label}</span>
    </div>
  );
}

export default function Dashboard({
  passes,
  margin,
}: {
  passes: PassesResponse | null;
  margin: MarginResponse | null;
}) {
  const simpleMetrics = useMemo(() => {
    const m = margin?.points?.length ? margin.points : [];
    const latest = m[m.length - 1];
    const best = m.reduce<typeof m[number] | undefined>((acc, p) => (p.margin_db > (acc?.margin_db ?? -Infinity) ? p : acc), undefined);
    return {
      marginDb: latest?.margin_db ?? best?.margin_db ?? null,
      uptime: m.length ? Math.round((m.filter((p) => p.margin_db > 0).length / m.length) * 100) : null,
      nextPass: passes?.passes?.[0]?.rise ? passes.passes[0].rise : null,
      bestGainTip: best ? (best.margin_db < 15 ? "Try 2 hours later for +5 dB" : "Great window soon") : "",
    };
  }, [passes, margin]);

  const chartData = useMemo(() => {
    return (margin?.points || []).map((p) => ({
      t: new Date(p.timestamp),
      margin: p.margin_db,
    }));
  }, [margin]);

  return (
    <motion.div
      initial={{ y: 12, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.5 }}
      className="w-full rounded-xl bg-zinc-900/70 backdrop-blur border border-zinc-800 p-4 md:p-6 text-zinc-100"
    >
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="rounded-lg bg-zinc-800/60 border border-zinc-700 p-4">
          <div className="text-sm text-zinc-400">Status</div>
          <div className="mt-2 text-2xl font-semibold">
            <TrafficLight marginDb={simpleMetrics.marginDb} />
          </div>
        </div>
        <div className="rounded-lg bg-zinc-800/60 border border-zinc-700 p-4">
          <div className="text-sm text-zinc-400">Link Margin</div>
          <div className="mt-2 text-2xl font-semibold">{simpleMetrics.marginDb != null ? `${simpleMetrics.marginDb.toFixed(1)} dB` : "—"}</div>
        </div>
        <div className="rounded-lg bg-zinc-800/60 border border-zinc-700 p-4">
          <div className="text-sm text-zinc-400">Uptime</div>
          <div className="mt-2 text-2xl font-semibold">{simpleMetrics.uptime != null ? `${simpleMetrics.uptime}%` : "—"}</div>
        </div>
        <div className="rounded-lg bg-zinc-800/60 border border-zinc-700 p-4">
          <div className="text-sm text-zinc-400">Next pass</div>
          <div className="mt-2 text-2xl font-semibold">
            {simpleMetrics.nextPass ? (
              <div className="flex items-baseline gap-2">
                <span>{format(new Date(simpleMetrics.nextPass), "MMM d, HH:mm")}</span>
                <span className="text-sm text-zinc-400">in <Countdown to={simpleMetrics.nextPass} /></span>
              </div>
            ) : (
              "—"
            )}
          </div>
        </div>
      </div>

      <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="md:col-span-2 rounded-lg bg-zinc-800/60 border border-zinc-700 p-4">
          <div className="text-sm text-zinc-400 mb-2">Link Margin Over Time</div>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ left: 12, right: 12, top: 12, bottom: 12 }}>
                <defs>
                  <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#22d3ee" stopOpacity={0.6} />
                    <stop offset="100%" stopColor="#22d3ee" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="t" tickFormatter={(t) => format(new Date(t), "HH:mm")} tick={{ fill: "#a1a1aa" }} stroke="#52525b"/>
                <YAxis tick={{ fill: "#a1a1aa" }} stroke="#52525b"/>
                <Tooltip contentStyle={{ background: "#18181b", border: "1px solid #3f3f46" }} labelFormatter={(l) => format(new Date(l as Date | number | string), "PPpp")} />
                <Area type="monotone" dataKey="margin" stroke="#22d3ee" fill="url(#g)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div className="rounded-lg bg-zinc-800/60 border border-zinc-700 p-4">
          <div className="text-sm text-zinc-400 mb-2">Recommendations</div>
          <ul className="text-sm text-zinc-300 list-disc list-inside space-y-2">
            <li>{simpleMetrics.bestGainTip}</li>
            <li>Increase TX power by 3 dB for more headroom</li>
            <li>Consider lowering elevation mask to 5° if safe</li>
          </ul>
        </div>
      </div>
    </motion.div>
  );
}


