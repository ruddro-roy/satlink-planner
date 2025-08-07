import numpy as np
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import math

class FrequencyBand(str, Enum):
    KU = "ku"  # 11.5 GHz
    KA = "ka"  # 20 GHz

@dataclass
class LinkBudgetParameters:
    """Parameters for link budget calculation"""
    frequency_ghz: float  # GHz
    tx_power_dbm: float  # dBm
    tx_antenna_gain_dbi: float  # dBi
    rx_antenna_gain_dbi: float  # dBi
    system_noise_temp_k: float  # Kelvin
    bandwidth_mhz: float  # MHz
    implementation_loss_db: float = 0.0  # dB
    rain_margin_db: float = 0.0  # dB
    other_margins_db: Dict[str, float] = None  # Additional margins
    
    def __post_init__(self):
        if self.other_margins_db is None:
            self.other_margins_db = {}

class LinkBudgetCalculator:
    """Service for calculating link budget and margins"""
    
    # Predefined parameters for common frequency bands
    BAND_PARAMETERS = {
        FrequencyBand.KU: {
            'frequency_ghz': 11.5,
            'system_noise_temp_k': 150,  # Typical for Ku-band
            'rx_antenna_gain_dbi': 40.0,  # Typical for a 1.2m dish
        },
        FrequencyBand.KA: {
            'frequency_ghz': 20.0,
            'system_noise_temp_k': 200,  # Higher noise at Ka-band
            'rx_antenna_gain_dbi': 45.0,  # Higher gain for same size dish at higher frequency
        }
    }
    
    # ITU-R P.676-13: Attenuation due to atmospheric gases (zenith)
    # Values in dB/km for different frequencies and elevation angles
    # This is a simplified model - in practice, use ITU-R P.676 for more accurate calculations
    ATMOSPHERIC_ATTENUATION = {
        'ku': {
            90: 0.07,   # Zenith
            30: 0.13,
            20: 0.18,
            10: 0.32,
            5:  0.57,
            3:  0.85
        },
        'ka': {
            90: 0.10,
            30: 0.18,
            20: 0.26,
            10: 0.47,
            5:  0.85,
            3:  1.28
        }
    }
    
    # ITU-R P.618-13: Rain rate coefficients (k and α)
    # Values for horizontal polarization
    RAIN_RATE_COEFFICIENTS = {
        'ku': {'k': 0.000650, 'alpha': 1.121},
        'ka': {'k': 0.00138, 'alpha': 1.192}
    }
    
    @classmethod
    def get_band_parameters(cls, band: FrequencyBand) -> Dict:
        """Get default parameters for a frequency band"""
        return cls.BAND_PARAMETERS.get(band, {})
    
    @classmethod
    def calculate_fspl(cls, distance_km: float, frequency_ghz: float) -> float:
        """
        Calculate Free Space Path Loss (FSPL) in dB
        
        Args:
            distance_km: Distance in kilometers
            frequency_ghz: Frequency in GHz
            
        Returns:
            FSPL in dB
        """
        # FSPL(dB) = 20*log10(d) + 20*log10(f) + 92.45
        # where d is in km and f is in GHz
        return 20 * math.log10(distance_km) + 20 * math.log10(frequency_ghz) + 92.45
    
    @classmethod
    def calculate_atmospheric_loss(
        cls, 
        elevation_deg: float, 
        frequency_band: FrequencyBand,
        rain_rate_mmph: float = 0.0
    ) -> Tuple[float, Dict[str, float]]:
        """
        Calculate atmospheric losses including gaseous and rain attenuation
        
        Args:
            elevation_deg: Elevation angle in degrees
            frequency_band: Frequency band ('ku' or 'ka')
            rain_rate_mmph: Rain rate in mm/h
            
        Returns:
            tuple: (total_loss_db, breakdown)
        """
        band = frequency_band.value
        
        # Gaseous attenuation (zenith) - simple model
        # In practice, use ITU-R P.676 for more accurate calculations
        elevation_key = min(cls.ATMOSPHERIC_ATTENUATION[band].keys(), 
                          key=lambda x: abs(x - elevation_deg))
        gaseous_att_db_per_km = cls.ATMOSPHERIC_ATTENUATION[band][elevation_key]
        
        # Adjust for elevation angle (zenith to slant path)
        if elevation_deg > 5:
            # Simple slant path approximation
            gaseous_att_db = gaseous_att_db_per_km / math.sin(math.radians(elevation_deg))
        else:
            # For very low elevations, use a more conservative estimate
            gaseous_att_db = gaseous_att_db_per_km * 10  # Approximate for low angles
        
        # Rain attenuation (ITU-R P.838)
        if rain_rate_mmph > 0 and band in cls.RAIN_RATE_COEFFICIENTS:
            k = cls.RAIN_RATE_COEFFICIENTS[band]['k']
            alpha = cls.RAIN_RATE_COEFFICIENTS[band]['alpha']
            
            # Effective path length (simplified)
            if elevation_deg > 5:
                # Simple model - in practice, use ITU-R P.618
                leff = 35 * math.exp(-0.015 * rain_rate_mmph) / math.sin(math.radians(elevation_deg))
            else:
                leff = 35 * math.exp(-0.015 * rain_rate_mmph) * 2  # Approximate for low angles
                
            # Specific attenuation (dB/km)
            gamma_r = k * (rain_rate_mmph ** alpha)
            
            # Total rain attenuation
            rain_att_db = gamma_r * leff
        else:
            rain_att_db = 0.0
        
        # Other atmospheric effects (tropospheric scintillation, cloud attenuation, etc.)
        # These are typically small compared to gaseous and rain attenuation
        other_att_db = 0.5  # Fixed small value for simplicity
        
        total_loss = gaseous_att_db + rain_att_db + other_att_db
        
        breakdown = {
            'gaseous_attenuation_db': gaseous_att_db,
            'rain_attenuation_db': rain_att_db,
            'other_atmospheric_losses_db': other_att_db
        }
        
        return total_loss, breakdown
    
    @classmethod
    def calculate_cn0(
        cls,
        tx_power_dbm: float,
        tx_antenna_gain_dbi: float,
        rx_antenna_gain_dbi: float,
        distance_km: float,
        frequency_ghz: float,
        system_noise_temp_k: float,
        bandwidth_mhz: float,
        atmospheric_loss_db: float = 0.0,
        implementation_loss_db: float = 0.0,
        other_margins_db: Dict[str, float] = None
    ) -> Tuple[float, Dict[str, float]]:
        """
        Calculate carrier-to-noise density ratio (C/N0)
        
        Args:
            tx_power_dbm: Transmitter power in dBm
            tx_antenna_gain_dbi: Transmitter antenna gain in dBi
            rx_antenna_gain_dbi: Receiver antenna gain in dBi
            distance_km: Distance between transmitter and receiver in km
            frequency_ghz: Frequency in GHz
            system_noise_temp_k: System noise temperature in Kelvin
            bandwidth_mhz: Bandwidth in MHz
            atmospheric_loss_db: Atmospheric losses in dB
            implementation_loss_db: Implementation losses in dB
            other_margins_db: Additional margins in dB
            
        Returns:
            tuple: (cn0_db_hz, breakdown)
        """
        # Convert power from dBm to dBW
        tx_power_dbw = tx_power_dbm - 30
        
        # Calculate EIRP (dBW)
        eirp_dbw = tx_power_dbw + tx_antenna_gain_dbi
        
        # Calculate free space path loss
        fspl_db = cls.calculate_fspl(distance_km, frequency_ghz)
        
        # Calculate received power
        rx_power_dbw = eirp_dbw + rx_antenna_gain_dbi - fspl_db - atmospheric_loss_db - implementation_loss_db
        
        # Calculate system noise power spectral density (dBW/Hz)
        # N0 = k*T, where k is Boltzmann's constant (1.38e-23 J/K)
        k_dbw_per_hz_k = -228.6  # 10*log10(1.38e-23)
        n0_dbw_per_hz = k_dbw_per_hz_k + 10 * math.log10(system_noise_temp_k)
        
        # Calculate C/N0
        cn0_db_hz = rx_power_dbw - n0_dbw_per_hz
        
        # Apply additional margins if provided
        if other_margins_db:
            total_margin_db = sum(other_margins_db.values())
            cn0_db_hz -= total_margin_db
        else:
            total_margin_db = 0.0
        
        # Calculate Eb/N0 (energy per bit to noise power spectral density ratio)
        # Eb/N0 = C/N0 - 10*log10(bit_rate)
        # For now, we'll just return C/N0
        
        breakdown = {
            'eirp_dbw': eirp_dbw,
            'fspl_db': fspl_db,
            'atmospheric_loss_db': atmospheric_loss_db,
            'implementation_loss_db': implementation_loss_db,
            'other_margins_db': total_margin_db,
            'rx_power_dbw': rx_power_dbw,
            'system_noise_psd_dbw_hz': n0_dbw_per_hz,
            'cn0_db_hz': cn0_db_hz
        }
        
        return cn0_db_hz, breakdown
    
    @classmethod
    def calculate_link_margin(
        cls,
        params: LinkBudgetParameters,
        distance_km: float,
        elevation_deg: float,
        rain_rate_mmph: float = 0.0,
        required_cn0_db_hz: Optional[float] = None
    ) -> Dict:
        """
        Calculate link margin for a given set of parameters
        
        Args:
            params: Link budget parameters
            distance_km: Distance between transmitter and receiver in km
            elevation_deg: Elevation angle in degrees
            rain_rate_mmph: Rain rate in mm/h
            required_cn0_db_hz: Required C/N0 in dB-Hz (if None, calculate from Shannon limit)
            
        Returns:
            dict: Link budget results including margin and breakdown
        """
        # Calculate atmospheric losses
        atmospheric_loss_db, att_breakdown = cls.calculate_atmospheric_loss(
            elevation_deg=elevation_deg,
            frequency_band=FrequencyBand.KU if params.frequency_ghz < 15 else FrequencyBand.KA,
            rain_rate_mmph=rain_rate_mmph
        )
        
        # Calculate C/N0
        cn0_db_hz, cn0_breakdown = cls.calculate_cn0(
            tx_power_dbm=params.tx_power_dbm,
            tx_antenna_gain_dbi=params.tx_antenna_gain_dbi,
            rx_antenna_gain_dbi=params.rx_antenna_gain_dbi,
            distance_km=distance_km,
            frequency_ghz=params.frequency_ghz,
            system_noise_temp_k=params.system_noise_temp_k,
            bandwidth_mhz=params.bandwidth_mhz,
            atmospheric_loss_db=atmospheric_loss_db,
            implementation_loss_db=params.implementation_loss_db,
            other_margins_db=params.other_margins_db
        )
        
        # If required C/N0 is not provided, calculate from Shannon limit
        if required_cn0_db_hz is None:
            # Shannon limit: C/N0 = Eb/N0 * R, where R is data rate
            # For QPSK at BER=1e-6, Eb/N0 ~ 10.5 dB
            # This is a simplified approach - in practice, use the actual modulation/coding scheme
            required_ebn0_db = 10.5  # dB for QPSK at BER=1e-6
            spectral_efficiency = 1.0  # bits/s/Hz (QPSK with 1/2 rate coding)
            required_cn0_db_hz = required_ebn0_db + 10 * math.log10(spectral_efficiency * params.bandwidth_mhz * 1e6)
        
        # Calculate margin
        margin_db = cn0_db_hz - required_cn0_db_hz
        
        # Prepare results
        result = {
            'cn0_db_hz': cn0_db_hz,
            'required_cn0_db_hz': required_cn0_db_hz,
            'margin_db': margin_db,
            'atmospheric_loss_db': atmospheric_loss_db,
            'fspl_db': cn0_breakdown['fspl_db'],
            'eirp_dbw': cn0_breakdown['eirp_dbw'],
            'rx_power_dbw': cn0_breakdown['rx_power_dbw'],
            'system_noise_psd_dbw_hz': cn0_breakdown['system_noise_psd_dbw_hz'],
            'breakdown': {
                'atmospheric': att_breakdown,
                'link_budget': cn0_breakdown
            }
        }
        
        return result
