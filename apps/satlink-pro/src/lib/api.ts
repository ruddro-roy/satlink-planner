/* eslint-disable @typescript-eslint/no-explicit-any */
export type PassWindow = {
  rise: string;
  max_elevation_time: string;
  set: string;
  duration_s: number;
  max_elevation_deg: number;
};

export type PassesResponse = {
  passes: PassWindow[];
  tle_epoch: string;
  tle_age_days: number;
  tle_source?: string | null;
};

export type MarginPoint = {
  timestamp: string;
  snr_db: number;
  margin_db: number;
  range_km: number;
  elevation_deg: number;
  azimuth_deg: number;
};

export type MarginResponse = {
  points: MarginPoint[];
  tle_epoch: string;
  tle_age_days: number;
  tle_source?: string | null;
  parameters: Record<string, any>;
};

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000/api/v1").replace(/\/$/, "");

export async function fetchPasses(args: {
  norad_id: string;
  lat: number;
  lon: number;
  elevation?: number;
  mask?: number;
  start_time?: string;
  end_time?: string;
  max_passes?: number;
}): Promise<PassesResponse> {
  const params = new URLSearchParams();
  params.set("norad_id", args.norad_id);
  params.set("lat", String(args.lat));
  params.set("lon", String(args.lon));
  if (args.elevation !== undefined) params.set("elevation", String(args.elevation));
  if (args.mask !== undefined) params.set("mask", String(args.mask));
  if (args.start_time) params.set("start_time", args.start_time);
  if (args.end_time) params.set("end_time", args.end_time);
  if (args.max_passes) params.set("max_passes", String(args.max_passes));

  const res = await fetch(`${API_BASE}/passes/?${params.toString()}`);
  if (!res.ok) throw new Error(`Passes request failed: ${res.status}`);
  return res.json();
}

export async function fetchMargin(args: {
  norad_id: string;
  lat: number;
  lon: number;
  elevation?: number;
  band: "ku" | "ka";
  rain_rate_mmh?: number;
  tx_power_dbm?: number;
  tx_antenna_gain_dbi?: number;
  rx_antenna_gain_dbi?: number;
  system_noise_temp_k?: number;
  bandwidth_mhz?: number;
  required_cn0_db_hz?: number;
  start_time: string;
  end_time: string;
  step_s?: number;
}): Promise<MarginResponse> {
  const params = new URLSearchParams();
  params.set("norad_id", args.norad_id);
  params.set("lat", String(args.lat));
  params.set("lon", String(args.lon));
  if (args.elevation !== undefined) params.set("elevation", String(args.elevation));
  params.set("band", args.band);
  if (args.rain_rate_mmh !== undefined) params.set("rain_rate_mmh", String(args.rain_rate_mmh));
  if (args.tx_power_dbm !== undefined) params.set("tx_power_dbm", String(args.tx_power_dbm));
  if (args.tx_antenna_gain_dbi !== undefined) params.set("tx_antenna_gain_dbi", String(args.tx_antenna_gain_dbi));
  if (args.rx_antenna_gain_dbi !== undefined) params.set("rx_antenna_gain_dbi", String(args.rx_antenna_gain_dbi));
  if (args.system_noise_temp_k !== undefined) params.set("system_noise_temp_k", String(args.system_noise_temp_k));
  if (args.bandwidth_mhz !== undefined) params.set("bandwidth_mhz", String(args.bandwidth_mhz));
  if (args.required_cn0_db_hz !== undefined) params.set("required_cn0_db_hz", String(args.required_cn0_db_hz));
  params.set("start_time", args.start_time);
  params.set("end_time", args.end_time);
  if (args.step_s !== undefined) params.set("step_s", String(args.step_s));

  const res = await fetch(`${API_BASE}/margin/?${params.toString()}`);
  if (!res.ok) throw new Error(`Margin request failed: ${res.status}`);
  return res.json();
}

export function exportICSUrl(args: {
  norad_id: string;
  lat: number;
  lon: number;
  elevation?: number;
  mask?: number;
  days?: number;
}): string {
  const params = new URLSearchParams();
  params.set("norad_id", args.norad_id);
  params.set("lat", String(args.lat));
  params.set("lon", String(args.lon));
  if (args.elevation !== undefined) params.set("elevation", String(args.elevation));
  if (args.mask !== undefined) params.set("mask", String(args.mask));
  if (args.days !== undefined) params.set("days", String(args.days));
  return `${API_BASE}/export/ics?${params.toString()}`;
}

export async function exportPDF(args: {
  norad_id: string;
  lat: number;
  lon: number;
  elevation?: number;
  mask?: number;
  band: "ku" | "ka";
  rain_rate_mmh?: number;
  tx_power_dbm?: number;
  tx_antenna_gain_dbi?: number;
  rx_antenna_gain_dbi?: number;
  system_noise_temp_k?: number;
  bandwidth_mhz?: number;
  start_time: string;
  end_time: string;
  step_s?: number;
}): Promise<Blob> {
  const res = await fetch(`${API_BASE}/export/pdf`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      norad_id: args.norad_id,
      lat: args.lat,
      lon: args.lon,
      elevation: args.elevation ?? 0,
      mask: args.mask ?? 10,
      band: args.band,
      rain_rate_mmh: args.rain_rate_mmh ?? 0,
      tx_power_dbm: args.tx_power_dbm ?? 40,
      tx_antenna_gain_dbi: args.tx_antenna_gain_dbi ?? 30,
      rx_antenna_gain_dbi: args.rx_antenna_gain_dbi,
      system_noise_temp_k: args.system_noise_temp_k,
      bandwidth_mhz: args.bandwidth_mhz ?? 10,
      start_time: args.start_time,
      end_time: args.end_time,
      step_s: args.step_s ?? 60,
    }),
  });
  if (!res.ok) throw new Error(`PDF export failed: ${res.status}`);
  return res.blob();
}


