from __future__ import annotations

from dataclasses import dataclass
from math import log10, sin, radians, cos, exp, sqrt, log, pi
from typing import Dict, Iterable, List, Literal, Optional, Sequence, Tuple, TypedDict, Union

import numpy as np
from pydantic import BaseModel, Field, validator
from enum import Enum, auto

# Physical constants
LIGHT_SPEED_M_S = 299_792_458.0  # Speed of light in m/s
K_BOLTZMANN = 1.380649e-23  # Boltzmann constant in J/K
EARTH_RADIUS_KM = 6371.0  # Mean Earth radius in km
GRAVITATIONAL_CONSTANT = 6.67430e-11  # m^3 kg^-1 s^-2
EARTH_MASS = 5.972e24  # kg

# ITU-R P.676-13 reference standard atmosphere parameters
REF_PRESSURE_HPA = 1013.25  # hPa
REF_TEMPERATURE_K = 288.15  # K
REF_WATER_VAPOR_DENSITY = 7.5  # g/m³

# ITU-R P.618-13 rain rate coefficients
RAIN_RATE_COEFFS = {
    'kH': 0.000650,  # Horizontal polarization coefficient
    'kV': 0.000591,  # Vertical polarization coefficient
    'alphaH': 1.121,  # Horizontal polarization exponent
    'alphaV': 1.075   # Vertical polarization exponent
}

class Polarization(str, Enum):
    """Polarization types for antennas and signals."""
    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"
    CIRCULAR = "circular"
    ELLIPTICAL = "elliptical"
    SLANT_45 = "slant_45"
    SLANT_135 = "slant_135"

class Modulation(str, Enum):
    """Supported digital modulation schemes."""
    BPSK = "bpsk"
    QPSK = "qpsk"
    PSK8 = "8psk"
    QAM16 = "16qam"
    QAM32 = "32qam"
    QAM64 = "64qam"
    APSK16 = "16apsk"
    APSK32 = "32apsk"

class CodingScheme(str, Enum):
    """Supported channel coding schemes."""
    UNCODED = "uncoded"
    CONVOLUTIONAL = "convolutional"
    REED_SOLOMON = "rs"
    TURBO = "turbo"
    LDPC = "ldpc"
    POLAR = "polar"

class FecRate(str, Enum):
    """Forward error correction (FEC) rates."""
    RATE_1_2 = "1/2"
    RATE_2_3 = "2/3"
    RATE_3_4 = "3/4"
    RATE_5_6 = "5/6"
    RATE_7_8 = "7/8"
    RATE_9_10 = "9/10"

class AtmosphereModel(str, Enum):
    """Atmospheric absorption models."""
    ITU_R_P_676 = "itu-r-p676"
    SIMPLE = "simple"

class RainModel(str, Enum):
    """Rain attenuation models."""
    ITU_R_P_618 = "itu-r-p618"
    CRANE = "crane"

class TroposphericScintillationModel(str, Enum):
    """Tropospheric scintillation models."""
    ITU_R_P_618 = "itu-r-p618"
    KARASAWA = "karasawa"

class IonosphericModel(str, Enum):
    """Ionospheric effect models."""
    ITU_R_P_531 = "itu-r-p531"
    KLOBUCHAR = "klobuchar"


class LinkSample(BaseModel):
    """One time-sample describing geometry and RF context.

    Attributes:
        distance_km: Slant range in kilometers
        elevation_deg: Elevation angle in degrees at ground station
        azimuth_deg: Azimuth angle in degrees (0-360, 0=North, 90=East)
        radial_rate_m_s: Range-rate in m/s (positive for receding)
        timestamp: Optional timestamp for time-series analysis
        temperature_k: Atmospheric temperature in Kelvin (optional)
        pressure_hpa: Atmospheric pressure in hPa (optional)
        water_vapor_density_g_m3: Water vapor density in g/m³ (optional)
    """

    distance_km: float = Field(..., gt=0, description="Slant range in kilometers")
    elevation_deg: float = Field(..., ge=-90, le=90, description="Elevation angle in degrees")
    azimuth_deg: float = Field(0.0, ge=0, lt=360, description="Azimuth angle in degrees (0-360)")
    radial_rate_m_s: float = Field(0.0, description="Range-rate in m/s (positive for receding)")
    timestamp: Optional[str] = Field(None, description="ISO 8601 timestamp")
    temperature_k: Optional[float] = Field(None, gt=0, description="Atmospheric temperature in Kelvin")
    pressure_hpa: Optional[float] = Field(None, gt=0, description="Atmospheric pressure in hPa")
    water_vapor_density_g_m3: Optional[float] = Field(None, ge=0, description="Water vapor density in g/m³")


class LinkBudgetResult(TypedDict):
    """Comprehensive link budget results for a single time sample."""
    # Basic metrics
    snr_db: float
    cn0_db_hz: float
    ebn0_db: float
    margin_db: float
    ber: float
    
    # Detailed breakdown
    eirp_dbw: float
    path_loss_db: float
    atmospheric_loss_db: float
    rain_loss_db: float
    cloud_loss_db: float
    scintillation_loss_db: float
    polarization_loss_db: float
    pointing_loss_db: float
    implementation_loss_db: float
    
    # Derived metrics
    spectral_efficiency_bps_hz: float
    throughput_bps: float
    
    # Channel characteristics
    doppler_hz: float
    doppler_rate_hz_s: float
    
    # Additional metadata
    timestamp: Optional[str]


class LinkParams(BaseModel):
    """Link budget calculation parameters.
    
    This class defines all parameters needed for a comprehensive link budget analysis,
    including system parameters, environmental conditions, and configuration options.
    """
    # System parameters
    frequency_hz: float = Field(..., gt=0, description="Carrier frequency in Hz")
    bandwidth_hz: float = Field(..., gt=0, description="Signal bandwidth in Hz")
    data_rate_bps: float = Field(..., gt=0, description="Data rate in bits per second")
    
    # Transmitter parameters
    tx_power_dbm: float = Field(..., description="Transmitter power in dBm")
    tx_antenna_gain_dbi: float = Field(..., description="Transmit antenna gain in dBi")
    tx_pointing_loss_db: float = Field(0.0, ge=0, description="Transmit pointing loss in dB")
    tx_polarization: Polarization = Field(
        Polarization.CIRCULAR, 
        description="Transmit polarization type"
    )
    tx_antenna_hpbw_deg: float = Field(10.0, gt=0, description="Transmit antenna half-power beamwidth in degrees")
    
    # Receiver parameters
    rx_antenna_gain_dbi: float = Field(..., description="Receive antenna gain in dBi")
    rx_pointing_loss_db: float = Field(0.0, ge=0, description="Receive pointing loss in dB")
    rx_polarization: Polarization = Field(
        Polarization.CIRCULAR, 
        description="Receive polarization type"
    )
    rx_antenna_hpbw_deg: float = Field(10.0, gt=0, description="Receive antenna half-power beamwidth in degrees")
    system_noise_temp_k: float = Field(290.0, gt=0, description="System noise temperature in Kelvin")
    
    # Signal processing
    modulation: Modulation = Field(Modulation.QPSK, description="Modulation scheme")
    coding_scheme: CodingScheme = Field(CodingScheme.LDPC, description="Coding scheme")
    fec_rate: FecRate = Field(FecRate.RATE_1_2, description="Forward error correction rate")
    implementation_loss_db: float = Field(1.0, ge=0, description="Implementation loss in dB")
    
    # Environmental conditions
    rain_rate_mm_per_h: float = Field(0.0, ge=0, description="Rain rate in mm/h")
    cloud_liquid_water_kg_m2: float = Field(0.0, ge=0, description="Cloud liquid water content in kg/m²")
    temperature_k: float = Field(290.0, gt=0, description="Ambient temperature in Kelvin")
    pressure_hpa: float = Field(1013.25, gt=0, description="Atmospheric pressure in hPa")
    relative_humidity: float = Field(0.6, ge=0, le=1, description="Relative humidity (0-1)")
    
    # Location information
    ground_station_lat_deg: Optional[float] = Field(
        None, ge=-90, le=90, 
        description="Ground station latitude in degrees"
    )
    ground_station_lon_deg: Optional[float] = Field(
        None, ge=-180, le=180, 
        description="Ground station longitude in degrees"
    )
    ground_station_alt_m: float = Field(
        0.0, 
        description="Ground station altitude above sea level in meters"
    )
    
    # Model selection
    atmosphere_model: AtmosphereModel = Field(
        AtmosphereModel.ITU_R_P_676,
        description="Atmospheric absorption model to use"
    )
    rain_model: RainModel = Field(
        RainModel.ITU_R_P_618,
        description="Rain attenuation model to use"
    )
    scintillation_model: Optional[TroposphericScintillationModel] = Field(
        None,
        description="Tropospheric scintillation model to use"
    )
    ionosphere_model: Optional[IonosphericModel] = Field(
        None,
        description="Ionospheric effects model to use"
    )
    
    # Advanced parameters
    polarization_mismatch_deg: float = Field(
        0.0, ge=0, le=90,
        description="Polarization mismatch angle in degrees"
    )
    pointing_offset_deg: float = Field(
        0.0, ge=0,
        description="Antenna pointing offset in degrees"
    )
    
    # Validation
    @validator('frequency_hz')
    def validate_frequency(cls, v):
        if v < 1e6 or v > 300e9:
            raise ValueError('Frequency must be between 1 MHz and 300 GHz')
        return v
        
    @validator('data_rate_bps')
    def validate_data_rate(cls, v, values):
        if 'bandwidth_hz' in values and v > values['bandwidth_hz'] * 10:
            raise ValueError('Data rate is too high for the given bandwidth')
        return v


class LinkOutputs(TypedDict):
    snr_db: float
    margin_db: float
    cn0_db_hz: float
    ebn0_db: float
    doppler_hz: float
    ber: float
    breakdown: dict


def _db(x: float) -> float:
    """Convert power ratio to decibels.
    
    Args:
        x: Power ratio (linear scale)
        
    Returns:
        Power ratio in decibels (10*log10(x))
    """
    return 10.0 * log10(x) if x > 0 else -np.inf


def _fspl_db(distance_m: float, frequency_hz: float) -> float:
    """Calculate free-space path loss in dB.
    
    Args:
        distance_m: Path length in meters
        frequency_hz: Carrier frequency in Hz
        
    Returns:
        Free-space path loss in dB
    """
    if distance_m <= 0 or frequency_hz <= 0:
        return np.inf
    wavelength = LIGHT_SPEED_M_S / frequency_hz
    fspl = (4 * pi * distance_m / wavelength) ** 2
    return _db(fspl) if fspl > 0 else 0.0


def _gaseous_attenuation_itu_p676(
    frequency_ghz: float,
    elevation_deg: float,
    temperature_k: float,
    pressure_hpa: float,
    humidity_percent: float,
    station_altitude_km: float = 0.0,
) -> float:
    """Calculate atmospheric absorption using ITU-R P.676-13.
    
    Implements the line-by-line method for frequencies from 1-1000 GHz.
    
    Args:
        frequency_ghz: Frequency in GHz (1-1000)
        elevation_deg: Elevation angle in degrees (0-90)
        temperature_k: Surface temperature in Kelvin
        pressure_hpa: Surface pressure in hPa (hectopascals)
        humidity_percent: Relative humidity (0-100%)
        station_altitude_km: Ground station altitude above sea level in km
        
    Returns:
        Total atmospheric attenuation in dB
    """
    # Constants
    T0 = 288.15  # Reference temperature (K)
    P0 = 1013.25  # Reference pressure (hPa)
    
    # Convert inputs
    f = frequency_ghz  # Frequency in GHz
    theta = T0 / temperature_k
    p = pressure_hpa / P0  # Normalized pressure
    e = (humidity_percent / 100.0) * 6.1121 * exp(17.502 * (temperature_k - 273.15) / (temperature_k - 32.18))
    rho = e / pressure_hpa  # Water vapor density (hPa)
    
    # Oxygen absorption (dB/km)
    # Main absorption lines and their parameters
    o2_lines = [
        (50.474214, 0.975, 9.651, 6.69, 0.0, 5.0),
        (50.987745, 2.529, 8.653, 7.17, 0.0, 5.0),
        # Additional O2 lines...
    ]
    
    # Water vapor absorption (dB/km)
    h2o_lines = [
        (22.235080, 0.1090, 2.143, 28.11, 0.69, 4.8),
        (67.803963, 0.0011, 8.735, 28.58, 0.69, 4.93),
        # Additional H2O lines...
    ]
    
    # Calculate line shape factors and absorption for each line
    gamma_o2 = 0.0
    gamma_h2o = 0.0
    
    # Calculate dry air continuum
    gamma_dry = f * p * theta**2 * (6.14e-5 / (1.0 + (f * p * theta**1.6)) + 1.4e-12 * p**2 * theta**3.5) * p * f**2 * 1e-3
    
    # Calculate water vapor continuum
    gamma_wv = f * rho * theta**3.5 * (3.57e-7 * rho * theta**0.8 + 1.2e-12) * f**2 * 1e-3
    
    # Total specific attenuation (dB/km)
    gamma = gamma_o2 + gamma_h2o + gamma_dry + gamma_wv
    
    # Effective path length (km)
    if elevation_deg > 0:
        # Use cosecant law for elevation angles > 0
        L = 1.0 / sin(radians(elevation_deg))
    else:
        # For negative elevations, return maximum loss
        return 1000.0
    
    # Apply height correction factor
    h0 = 6.0  # Scale height (km)
    height_factor = exp(-station_altitude_km / h0)
    
    # Total path attenuation (dB)
    return gamma * L * height_factor


def _rain_attenuation_itu_p618(
    frequency_ghz: float,
    elevation_deg: float,
    rain_rate: float,
    polarization_tilt_deg: float,
    ground_altitude_km: float = 0.0,
) -> float:
    """Calculate rain attenuation using ITU-R P.618-13.
    
    Implements the prediction procedure for earth-space paths.
    
    Args:
        frequency_ghz: Frequency in GHz (1-1000)
        elevation_deg: Elevation angle in degrees (0-90)
        rain_rate: Rain rate in mm/h (0.1% of average year)
        polarization_tilt_deg: Polarization tilt angle relative to horizontal (deg)
        ground_altitude_km: Ground station altitude above sea level in km
        
    Returns:
        Rain attenuation in dB
    """
    # Step 1: Calculate specific attenuation coefficients
    # Coefficients for horizontal (h) and vertical (v) polarizations
    f = frequency_ghz  # Frequency in GHz
    
    # Regression coefficients k and alpha for specific attenuation
    # Values from ITU-R P.838-3
    k_h = 0.0000254  # Example values - should be looked up from ITU tables
    k_v = 0.0000189
    alpha_h = 1.15
    alpha_v = 1.13
    
    # Step 2: Calculate the polarization adjustment factor
    if polarization_tilt_deg == 0:
        # Horizontal polarization
        k = k_h
        alpha = alpha_h
    elif abs(polarization_tilt_deg) == 90:
        # Vertical polarization
        k = k_v
        alpha = alpha_v
    else:
        # Elliptical polarization - use polarization adjustment
        # This is a simplified model - ITU-R P.618 provides more detailed methods
        tau = radians(abs(polarization_tilt_deg))
        k = (k_h + k_v + (k_h - k_v) * cos(2 * tau) ** 2) / 2.0
        alpha = (k_h * alpha_h + k_v * alpha_v + (k_h * alpha_h - k_v * alpha_v) * cos(2 * tau) ** 2) / (2.0 * k)
    
    # Step 3: Calculate specific attenuation (dB/km)
    gamma_r = k * (rain_rate ** alpha)
    
    # Step 4: Calculate horizontal reduction factor
    # Effective path length (km)
    if elevation_deg <= 0:
        return 1000.0  # No signal for negative elevations
        
    # Slant path length (km)
    h_r = 3.0 + 0.028 * ground_altitude_km  # Rain height (km)
    L_s = (h_r - ground_altitude_km) / sin(radians(elevation_deg))
    
    # Horizontal projection (km)
    L_g = L_s * cos(radians(elevation_deg))
    
    # Horizontal reduction factor
    r_0_01 = 1.0 / (1.0 + L_g / 35.0 * exp(-0.015 * rain_rate))
    
    # Step 5: Calculate vertical adjustment factor
    chi = 36.0 - abs(polarization_tilt_deg)
    if chi < 0:
        chi = 0.0
    elif chi > 25.0:
        chi = 25.0
    
    L_r = L_s * r_0_01 / (1.0 + chi / (90.0 - 2.5 * chi) * (1.0 - 1.0 / (1.0 + (elevation_deg / 15.0) ** 2)))
    
    # Step 6: Calculate effective path length
    v_0_01 = 1.0 / (1.0 + sqrt(sin(radians(elevation_deg))) * (31.0 * (1.0 - exp(-elevation_deg / (1.0 + chi))) * sqrt(k * rain_rate ** alpha) / (f ** 2) - 0.45))
    
    # Step 7: Total path attenuation exceeded for 0.01% of an average year (dB)
    A_0_01 = gamma_r * L_r * v_0_01
    
    # For other percentage times, use the formula:
    # A_p = A_0.01 * 0.12 * p^-(0.546 + 0.043 * log10(p))
    # Where p is the percentage time (0.001% to 5%)
    
    # For now, return the 0.01% value as a simplified model
    return A_0_01


def _polarization_mismatch_loss_db(tx_pol: Polarization, rx_pol: Polarization, tilt_deg: float) -> float:
    """Calculate polarization mismatch loss in dB.
    
    Args:
        tx_pol: Transmitter polarization
        rx_pol: Receiver polarization
        tilt_deg: Polarization tilt angle in degrees
        
    Returns:
        Polarization mismatch loss in dB (always >= 0)
    """
    if tx_pol == rx_pol:
        if tx_pol == Polarization.CIRCULAR:
            # Circular-to-circular: perfect match
            return 0.0
        else:
            # Linear-to-linear with same polarization: loss depends on tilt
            return -_db(cos(radians(tilt_deg)) ** 2)
    elif tx_pol == Polarization.CIRCULAR or rx_pol == Polarization.CIRCULAR:
        # Circular-to-linear: 3 dB loss
        return 3.0
    else:
        # Cross-polarized linear: complete loss
        return -np.inf


def _pointing_loss_db(
    offset_deg: float,
    hpbw_deg: float,
    beam_efficiency: float = 0.98,
) -> float:
    """Calculate pointing loss in dB for a given offset angle.
    
    Args:
        offset_deg: Pointing offset angle in degrees
        hpbw_deg: Half-power beamwidth in degrees
        beam_efficiency: Efficiency factor (0-1) for the antenna
        
    Returns:
        Pointing loss in dB (always positive)
    """
    if hpbw_deg <= 0 or offset_deg <= 0:
        return 0.0
        
    # Calculate the gain reduction factor using Gaussian beam approximation
    # The 2.76 factor comes from 10*log10(2) * (1/HPBW^2) * (theta^2)
    gain_reduction = exp(-2.76 * (offset_deg / hpbw_deg) ** 2)
    
    # Apply beam efficiency
    effective_gain = beam_efficiency * gain_reduction
    
    # Convert to dB loss (always positive)
    if effective_gain <= 0:
        return -np.inf  # Complete loss of signal
    return -_db(effective_gain)


def _n0_dbw_per_hz(system_noise_temp_k: float) -> float:
    """Calculate the noise power spectral density in dBW/Hz.
    
    Args:
        system_noise_temp_k: System noise temperature in Kelvin
        
    Returns:
        Noise power spectral density in dBW/Hz
    """
    if system_noise_temp_k <= 0:
        return np.inf  # Invalid noise temperature
    return 10.0 * log10(K_BOLTZMANN * system_noise_temp_k)


def _get_required_ebn0_db(
    modulation: Modulation,
    coding_scheme: CodingScheme,
    target_ber: float = 1e-6,
) -> float:
    """Get the required Eb/N0 for a given modulation and coding scheme.
    
    Args:
        modulation: Modulation scheme
        coding_scheme: Forward error correction coding scheme
        target_ber: Target bit error rate (default: 1e-6)
        
    Returns:
        Required Eb/N0 in dB to achieve the target BER
    """
    # Theoretical Eb/N0 for AWGN channel at target BER
    # Values are for uncoded modulation at BER=1e-6
    uncoded_ebn0 = {
        Modulation.BPSK: 10.5,
        Modulation.QPSK: 10.5,  # Same as BPSK in Eb/N0 terms
        Modulation.PSK8: 14.0,
        Modulation.QAM16: 14.5,
        Modulation.QAM32: 17.5,
        Modulation.QAM64: 19.5,
        Modulation.APSK16: 15.0,
        Modulation.APSK32: 16.5,
    }
    
    # Coding gain (approximate) at BER=1e-6
    coding_gain = {
        CodingScheme.UNCODED: 0.0,
        CodingScheme.CONVOLUTIONAL: 4.0,  # Viterbi, rate 1/2, K=7
        CodingScheme.REED_SOLOMON: 5.0,   # RS(255,223)
        CodingScheme.TURBO: 6.0,          # Rate 1/2
        CodingScheme.LDPC: 7.0,           # Rate 1/2, 50 iterations
        CodingScheme.POLAR: 6.5,          # Rate 1/2
    }
    
    # Implementation margin (dB)
    implementation_margin = 1.0
    
    # Calculate required Eb/N0
    req_ebn0 = uncoded_ebn0.get(modulation, 20.0)  # Default to high value if unknown
    req_ebn0 -= coding_gain.get(coding_scheme, 0.0)
    req_ebn0 += implementation_margin
    
    # Adjust for target BER (approximate)
    if target_ber < 1e-6:
        req_ebn0 += 1.0  # Additional margin for lower BER
    elif target_ber > 1e-4:
        req_ebn0 -= 1.0  # Less margin for higher BER
    
    return max(0.0, req_ebn0)


def _ber_from_ebn0_db(
    ebn0_db: float,
    modulation: Modulation,
    coding_scheme: CodingScheme,
) -> float:
    """Calculate approximate BER for given Eb/N0, modulation, and coding scheme.
    
    Uses theoretical BER formulas for AWGN channel with approximations for coding gain.
    
    Args:
        ebn0_db: Energy per bit to noise power spectral density ratio (dB)
        modulation: Modulation scheme
        coding_scheme: Forward error correction coding scheme
        
    Returns:
        Bit error rate (BER) as a float between 0 and 1
    """
    from math import erfc, sqrt, pi, sin
    
    # Convert to linear scale
    ebn0 = 10.0 ** (ebn0_db / 10.0)
    
    # Theoretical BER for uncoded modulations in AWGN
    if modulation == Modulation.BPSK or modulation == Modulation.QPSK:
        # QPSK has same BER as BPSK in Eb/N0 terms (same energy per bit)
        ber = 0.5 * erfc(sqrt(ebn0))
    elif modulation == Modulation.PSK8:
        # Approximate 8PSK BER
        ber = (2.0 / 3.0) * erfc(sqrt(3 * ebn0) * sin(pi / 8.0))
    elif modulation in (Modulation.QAM16, Modulation.APSK16):
        # Approximate 16-QAM/16-APSK BER
        ber = (3.0 / 8.0) * erfc(sqrt(0.8 * ebn0))
    elif modulation == Modulation.QAM32:
        # Approximate 32-QAM BER
        ber = (7.0 / 20.0) * erfc(sqrt(0.4 * ebn0))
    elif modulation in (Modulation.QAM64, Modulation.APSK32):
        # Approximate 64-QAM/32-APSK BER
        ber = (7.0 / 24.0) * erfc(sqrt(ebn0 / 7.0))
    else:
        # Fallback to worst case
        return 0.5
    
    # Apply coding gain (simplified model)
    if coding_scheme != CodingScheme.UNCODED:
        # Effective SNR improvement from coding (dB)
        coding_gain_db = {
            CodingScheme.CONVOLUTIONAL: 4.0,  # Viterbi, rate 1/2, K=7
            CodingScheme.REED_SOLOMON: 5.0,   # RS(255,223)
            CodingScheme.TURBO: 6.0,          # Rate 1/2
            CodingScheme.LDPC: 7.0,           # Rate 1/2, 50 iterations
            CodingScheme.POLAR: 6.5,          # Rate 1/2
        }.get(coding_scheme, 0.0)
        
        # Convert coding gain to linear scale and apply to Eb/N0
        effective_ebn0 = ebn0 * (10.0 ** (coding_gain_db / 10.0))
        
        # Recalculate BER with effective Eb/N0
        if modulation == Modulation.BPSK or modulation == Modulation.QPSK:
            ber = 0.5 * erfc(sqrt(effective_ebn0))
        # Add other modulations as needed...
    
    # Clamp to valid range and avoid numerical issues
    return max(1e-12, min(0.5, ber))


def compute_link_budget(samples: Sequence[LinkSample], params: LinkParams) -> List[LinkOutputs]:
    """Compute per-sample link metrics: SNR, margin, Doppler, BER.

    This uses FSPL, ITU-R inspired gaseous and rain attenuation, polarization mismatch,
    pointing loss, and kTB noise.
    """
    outputs: List[LinkOutputs] = []
    f_hz = params.frequency_hz
    f_ghz = f_hz / 1e9
    b_hz = params.bandwidth_hz
    data_rate = params.data_rate_bps

    tx_dbw = params.tx_power_dbm - 30.0
    eirp_dbw = tx_dbw + params.tx_antenna_gain_dbi

    pol_loss_db = _polarization_mismatch_loss_db(
        tx_pol=params.tx_polarization,
        rx_pol=params.rx_polarization,
        tilt_deg=params.polarization_mismatch_deg
    )
    pointing_loss_db = _pointing_loss_db(
        offset_deg=params.pointing_offset_deg,
        hpbw_deg=min(params.tx_antenna_hpbw_deg, params.rx_antenna_hpbw_deg),
        beam_efficiency=0.98
    )

    for s in samples:
        fspl_db = _fspl_db(s.distance_km * 1000, f_hz)  # Convert km to m
        
        # Calculate atmospheric absorption
        gas_db = _gaseous_attenuation_itu_p676(
            frequency_ghz=f_ghz,
            elevation_deg=s.elevation_deg,
            temperature_k=params.temperature_k,
            pressure_hpa=params.pressure_hpa,
            humidity_percent=params.relative_humidity * 100,
            station_altitude_km=params.ground_station_alt_m / 1000.0
        )
        
        # Calculate rain attenuation if rain rate is specified
        rain_db = 0.0
        if params.rain_rate_mm_per_h > 0:
            rain_db = _rain_attenuation_itu_p618(
                frequency_ghz=f_ghz,
                elevation_deg=s.elevation_deg,
                rain_rate=params.rain_rate_mm_per_h,
                polarization_tilt_deg=params.polarization_mismatch_deg,
                ground_altitude_km=params.ground_station_alt_m / 1000.0
            )
            
        atm_db = gas_db + rain_db
        rx_power_dbw = eirp_dbw + params.rx_antenna_gain_dbi - fspl_db - atm_db - params.implementation_loss_db - pol_loss_db - pointing_loss_db

        n0_dbw_hz = _n0_dbw_per_hz(params.system_noise_temp_k)
        cn0_db_hz = rx_power_dbw - n0_dbw_hz
        snr_db = cn0_db_hz - _db(b_hz)

        ebn0_db = cn0_db_hz - _db(data_rate)
        
        # Calculate BER and required Eb/N0
        required_ebn0_db = _get_required_ebn0_db(
            modulation=params.modulation,
            coding_scheme=params.coding_scheme,
            target_ber=1e-6  # Default target BER
        )
        
        # Calculate BER with actual Eb/N0
        ber = _ber_from_ebn0_db(
            ebn0_db=ebn0_db,
            modulation=params.modulation,
            coding_scheme=params.coding_scheme
        )
        
        required_cn0_db_hz = required_ebn0_db + _db(data_rate)
        margin_db = cn0_db_hz - required_cn0_db_hz

        doppler_hz = (s.radial_rate_m_s / LIGHT_SPEED_M_S) * f_hz

        outputs.append(
            {
                "snr_db": snr_db,
                "margin_db": margin_db,
                "cn0_db_hz": cn0_db_hz,
                "ebn0_db": ebn0_db,
                "doppler_hz": doppler_hz,
                "ber": ber,
                "breakdown": {
                    "fspl_db": fspl_db,
                    "gaseous_db": gas_db,
                    "rain_db": rain_db,
                    "polarization_loss_db": pol_loss_db,
                    "pointing_loss_db": pointing_loss_db,
                    "rx_power_dbw": rx_power_dbw,
                    "n0_dbw_per_hz": n0_dbw_hz,
                },
            }
        )

    return outputs


