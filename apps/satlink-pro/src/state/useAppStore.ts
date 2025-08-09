import { create } from "zustand";

type GroundStation = {
  lat: number;
  lon: number;
  elevation: number;
};

type AppState = {
  query: string;
  selectedNoradId: string | null;
  ground: GroundStation;
  timeRangeHours: number; // next N hours
  band: "ku" | "ka";
  loading: boolean;
  setQuery: (q: string) => void;
  setSelectedNoradId: (id: string | null) => void;
  setGround: (g: Partial<GroundStation>) => void;
  setTimeRangeHours: (h: number) => void;
  setBand: (b: "ku" | "ka") => void;
  setLoading: (v: boolean) => void;
};

export const useAppStore = create<AppState>((set) => ({
  query: "",
  selectedNoradId: null,
  ground: { lat: 37.7749, lon: -122.4194, elevation: 10 },
  timeRangeHours: 24,
  band: "ku",
  loading: false,
  setQuery: (q) => set({ query: q }),
  setSelectedNoradId: (id) => set({ selectedNoradId: id }),
  setGround: (g) => set((s) => ({ ground: { ...s.ground, ...g } })),
  setTimeRangeHours: (h) => set({ timeRangeHours: h }),
  setBand: (b) => set({ band: b }),
  setLoading: (v) => set({ loading: v }),
}));


