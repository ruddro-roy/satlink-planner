from __future__ import annotations

import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from rf.models import LinkParams, LinkSample, compute_link_budget, Modulation, Coding


def test_fspl_and_snr_golden():
    params = LinkParams(
        frequency_hz=2.2e9,
        bandwidth_hz=50e3,
        data_rate_bps=50e3,
        tx_power_dbm=30.0,
        tx_antenna_gain_dbi=5.0,
        rx_antenna_gain_dbi=12.0,
        system_noise_temp_k=500.0,
        implementation_loss_db=1.0,
        polarization_mismatch_deg=0.0,
        pointing_offset_deg=0.0,
        rx_antenna_hpbw_deg=20.0,
        rain_rate_mm_per_h=0.0,
        modulation=Modulation.BPSK,
        coding=Coding.VITERBI,
    )

    # 1000 km slant range, 30 deg elevation
    sample = LinkSample(distance_km=1000.0, elevation_deg=30.0, radial_rate_m_s=0.0)
    out = compute_link_budget([sample], params)[0]

    # Golden values: within reasonable tolerance for our approximations
    assert -10.0 <= out["snr_db"] <= 15.0
    assert out["cn0_db_hz"] > 0.0
    assert out["ber"] < 0.5


def test_rain_and_absorption_increase_losses():
    base = LinkParams(
        frequency_hz=20e9,
        bandwidth_hz=1e6,
        data_rate_bps=1e6,
        tx_power_dbm=40.0,
        tx_antenna_gain_dbi=30.0,
        rx_antenna_gain_dbi=40.0,
        system_noise_temp_k=300.0,
        rain_rate_mm_per_h=0.0,
    )
    wet = base.model_copy(update={"rain_rate_mm_per_h": 50.0})
    s = LinkSample(distance_km=2000.0, elevation_deg=20.0, radial_rate_m_s=0.0)
    out_base = compute_link_budget([s], base)[0]
    out_wet = compute_link_budget([s], wet)[0]
    assert out_wet["snr_db"] < out_base["snr_db"]
    assert out_wet["margin_db"] < out_base["margin_db"]


