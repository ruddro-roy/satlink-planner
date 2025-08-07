from __future__ import annotations

import math
from typing import List
from .models import MarginRequest, MarginResponse, MarginPoint

BAND_FREQ_GHZ = {
    "VHF": 0.145,
    "UHF": 0.437,
    "S": 2.2,
    "X": 8.2,
    "Ku": 12.0,
    "Ka": 26.0,
}

K_dBW_per_HzK = -228.6


def compute_margin(req: MarginRequest) -> MarginResponse:
    f_ghz = BAND_FREQ_GHZ.get(req.band, 0.437)

    points: List[MarginPoint] = []
    for s in req.samples:
        # Free-space path loss in dB
        if s.range_km <= 0:
            continue
        lfs_db = 92.45 + 20.0 * math.log10(f_ghz) + 20.0 * math.log10(s.range_km)

        eirp_dbw = req.tx_power_dbw + req.tx_gain_dbi
        prx_dbw = (
            eirp_dbw
            + req.rx_gain_dbi
            - lfs_db
            - req.atm_loss_db
            - req.rain_loss_db
            - req.pointing_loss_db
        )

        ktb_dbw = K_dBW_per_HzK + 10.0 * math.log10(req.system_noise_temp_k) + 10.0 * math.log10(req.bandwidth_hz)
        snr_db = prx_dbw - (ktb_dbw + req.noise_figure_db)
        margin_db = snr_db - req.required_snr_db
        points.append(MarginPoint(t=s.t, snr_db=snr_db, margin_db=margin_db))

    return MarginResponse(points=points)
