"use client";
import { useEffect, useRef, useState } from "react";

export type LiveSatellite = { id: string; name: string; lat: number; lon: number; altKm: number };

export function useRealTimeSatellites() {
  const [satellites, setSatellites] = useState<LiveSatellite[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let cancelled = false;
    // Use Next.js API proxy path so it works on Vercel if proxied
    const wsUrl = (typeof window !== "undefined" ? window.location.origin.replace("http", "ws") : "ws://localhost:8000") + "/api/ws/satellites";
    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;
      ws.onmessage = (event) => {
        if (cancelled) return;
        try {
          const update = JSON.parse(event.data);
          if (Array.isArray(update?.satellites)) {
            setSatellites(update.satellites);
          }
        } catch {}
      };
      ws.onclose = () => {
        wsRef.current = null;
      };
    } catch {
      // ignore in demo; fallback to empty list
    }
    return () => {
      cancelled = true;
      wsRef.current?.close();
    };
  }, []);

  return satellites;
}


