"use client";
import { useEffect, useState } from "react";

function format(durationMs: number): string {
  if (durationMs <= 0) return "now";
  const totalSeconds = Math.floor(durationMs / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours > 0) return `${hours}h ${minutes}m`;
  if (minutes > 0) return `${minutes}m ${seconds}s`;
  return `${seconds}s`;
}

export default function Countdown({ to }: { to: string | Date }) {
  const target = typeof to === "string" ? new Date(to) : to;
  const [now, setNow] = useState<Date>(new Date());

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const delta = target.getTime() - now.getTime();
  return <span>{format(delta)}</span>;
}


