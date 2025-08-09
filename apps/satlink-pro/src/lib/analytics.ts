type EventMap = {
  satellite_searched: { satellite: string; timestamp: Date };
  pass_calculated: { duration: number; accuracy: number };
  export_generated: { type: string; user_type: string };
  advanced_feature_used: { feature: string; success: boolean };
};

export function track<E extends keyof EventMap>(event: E, payload: EventMap[E]) {
  // For portfolio: optional beacon to Next.js route for aggregation
  if (typeof navigator !== "undefined" && navigator.sendBeacon) {
    try {
      const blob = new Blob([
        JSON.stringify({ event, payload: { ...payload, timestamp: new Date().toISOString() } }),
      ], { type: "application/json" });
      navigator.sendBeacon("/api/analytics", blob);
    } catch {}
  }
}


