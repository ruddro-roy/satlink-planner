"use client";
import { exportICSUrl, exportPDF } from "@/lib/api";
import { useAppStore } from "@/state/useAppStore";
import { addHours } from "date-fns";

export default function ActionsBar() {
  const { selectedNoradId, ground, timeRangeHours, band } = useAppStore();
  const norad = selectedNoradId || "25544";
  const start = new Date();
  const end = addHours(start, timeRangeHours);

  async function onDownloadPDF() {
    const blob = await exportPDF({
      norad_id: norad,
      lat: ground.lat,
      lon: ground.lon,
      elevation: ground.elevation,
      band,
      start_time: start.toISOString(),
      end_time: end.toISOString(),
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `satlink_report_${norad}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
  }

  function onExportICS() {
    const url = exportICSUrl({ norad_id: norad, lat: ground.lat, lon: ground.lon, elevation: ground.elevation, days: Math.ceil(timeRangeHours / 24) });
    window.open(url, "_blank");
  }

  function onShare() {
    const shareUrl = `${window.location.origin}?norad=${norad}&lat=${ground.lat}&lon=${ground.lon}&h=${timeRangeHours}&band=${band}`;
    navigator.clipboard.writeText(shareUrl);
    alert("Share link copied to clipboard");
  }

  return (
    <div className="w-full flex items-center gap-3">
      <button onClick={onExportICS} className="h-10 rounded-lg bg-zinc-800 border border-zinc-700 px-3 hover:bg-zinc-700">Export Calendar</button>
      <button onClick={onDownloadPDF} className="h-10 rounded-lg bg-zinc-800 border border-zinc-700 px-3 hover:bg-zinc-700">Download PDF</button>
      <button onClick={onShare} className="h-10 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-black font-semibold px-3">Share</button>
    </div>
  );
}


