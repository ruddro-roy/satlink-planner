import { create } from 'zustand'

export const useAppStore = create((set) => ({
  mode: 'beginner', // 'beginner' | 'advanced'
  setMode: (m) => set({ mode: m }),

  location: null, // {lat, lon}
  setLocation: (loc) => set({ location: loc }),

  noradId: '',
  setNoradId: (v) => set({ noradId: v }),

  timeWindow: {
    startIso: null,
    endIso: null,
  },
  setTimeWindow: (tw) => set({ timeWindow: tw }),

  passes: [],
  setPasses: (p) => set({ passes: p }),

  samples: [],
  setSamples: (s) => set({ samples: s }),

  rfParams: {
    band: 'UHF',
    tx_power_dbw: 10,
    tx_gain_dbi: 5,
    rx_gain_dbi: 20,
    bandwidth_hz: 20000,
    system_noise_temp_k: 290,
    noise_figure_db: 2,
    rain_loss_db: 0,
    atm_loss_db: 1,
    required_snr_db: 3,
    pointing_loss_db: 0.5,
  },
  setRfParams: (p) => set((s) => ({ rfParams: { ...s.rfParams, ...p } })),
}))
