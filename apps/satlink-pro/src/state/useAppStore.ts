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
  // Advanced search & UX
  favorites: string[]; // NORAD IDs
  recentSearches: string[]; // plain strings
  filters: {
    category: "ISS" | "Starlink" | "GPS" | "Military" | "Weather" | "All";
    altitude: "LEO" | "MEO" | "GEO" | "All";
    frequency: "VHF" | "UHF" | "L" | "S" | "C" | "X" | "Ku" | "Ka" | "All";
    purpose: "Communication" | "Navigation" | "Earth Observation" | "All";
  };
  professionalMode: boolean;
  loading: boolean;
  setQuery: (q: string) => void;
  setSelectedNoradId: (id: string | null) => void;
  setGround: (g: Partial<GroundStation>) => void;
  setTimeRangeHours: (h: number) => void;
  setBand: (b: "ku" | "ka") => void;
  setLoading: (v: boolean) => void;
  addFavorite: (id: string) => void;
  removeFavorite: (id: string) => void;
  addRecentSearch: (q: string) => void;
  setFilters: (f: Partial<AppState["filters"]>) => void;
  setProfessionalMode: (v: boolean) => void;
};

export const useAppStore = create<AppState>((set) => ({
  query: "",
  selectedNoradId: null,
  ground: { lat: 37.7749, lon: -122.4194, elevation: 10 },
  timeRangeHours: 24,
  band: "ku",
  favorites: [],
  recentSearches: [],
  filters: {
    category: "All",
    altitude: "All",
    frequency: "All",
    purpose: "All",
  },
  professionalMode: false,
  loading: false,
  setQuery: (q) => set({ query: q }),
  setSelectedNoradId: (id) => set({ selectedNoradId: id }),
  setGround: (g) => set((s) => ({ ground: { ...s.ground, ...g } })),
  setTimeRangeHours: (h) => set({ timeRangeHours: h }),
  setBand: (b) => set({ band: b }),
  setLoading: (v) => set({ loading: v }),
  addFavorite: (id) => set((s) => ({ favorites: s.favorites.includes(id) ? s.favorites : [...s.favorites, id] })),
  removeFavorite: (id) => set((s) => ({ favorites: s.favorites.filter((f) => f !== id) })),
  addRecentSearch: (q) => set((s) => {
    const trimmed = q.trim();
    if (!trimmed) return {} as AppState;
    const deduped = [trimmed, ...s.recentSearches.filter((x) => x !== trimmed)].slice(0, 10);
    return { recentSearches: deduped } as Partial<AppState> as AppState;
  }),
  setFilters: (f) => set((s) => ({ filters: { ...s.filters, ...f } })),
  setProfessionalMode: (v) => set({ professionalMode: v }),
}));


