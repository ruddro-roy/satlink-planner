"""Adaptive Coding and Modulation (ACM) Service"""
import logging
import numpy as np
from enum import Enum, auto
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class ACMState(Enum):
    """ACM operational states"""
    NOMINAL = auto()
    DEGRADED = auto()
    MARGINAL = auto()
    OUTAGE = auto()

@dataclass
class ACMProfile:
    """ACM profile configuration"""
    name: str
    code_rate: float  # FEC code rate (e.g., 1/2, 3/4)
    modulation: str   # Modulation scheme (e.g., QPSK, 8PSK, 16APSK, 32APSK)
    spectral_efficiency: float  # bits/s/Hz
    required_cn0: float  # dB-Hz required for this mode
    implementation_margin_db: float = 1.0  # dB implementation margin
    
    @property
    def data_rate(self, bandwidth_hz: float) -> float:
        """Calculate data rate in bps for a given bandwidth"""
        return bandwidth_hz * self.spectral_efficiency

class ACMController:
    """Adaptive Coding and Modulation controller"""
    
    # Standard DVB-S2X ACM profiles (simplified)
    STANDARD_PROFILES = [
        ACMProfile(
            name="QPSK 1/4",
            code_rate=1/4,
            modulation="QPSK",
            spectral_efficiency=0.49,
            required_cn0=45.5  # dB-Hz
        ),
        ACMProfile(
            name="QPSK 1/3",
            code_rate=1/3,
            modulation="QPSK",
            spectral_efficiency=0.65,
            required_cn0=47.5
        ),
        ACMProfile(
            name="QPSK 2/5",
            code_rate=2/5,
            modulation="QPSK",
            spectral_efficiency=0.79,
            required_cn0=49.0
        ),
        ACMProfile(
            name="QPSK 1/2",
            code_rate=1/2,
            modulation="QPSK",
            spectral_efficiency=0.99,
            required_cn0=51.0
        ),
        ACMProfile(
            name="QPSK 3/5",
            code_rate=3/5,
            modulation="QPSK",
            spectral_efficiency=1.19,
            required_cn0=53.0
        ),
        ACMProfile(
            name="QPSK 2/3",
            code_rate=2/3,
            modulation="QPSK",
            spectral_efficiency=1.32,
            required_cn0=54.5
        ),
        ACMProfile(
            name="QPSK 3/4",
            code_rate=3/4,
            modulation="QPSK",
            spectral_efficiency=1.49,
            required_cn0=56.0
        ),
        ACMProfile(
            name="QPSK 4/5",
            code_rate=4/5,
            modulation="QPSK",
            spectral_efficiency=1.59,
            required_cn0=57.0
        ),
        ACMProfile(
            name="QPSK 5/6",
            code_rate=5/6,
            modulation="QPSK",
            spectral_efficiency=1.66,
            required_cn0=58.0
        ),
        ACMProfile(
            name="8PSK 3/5",
            code_rate=3/5,
            modulation="8PSK",
            spectral_efficiency=1.78,
            required_cn0=59.5
        ),
        ACMProfile(
            name="8PSK 2/3",
            code_rate=2/3,
            modulation="8PSK",
            spectral_efficiency=1.98,
            required_cn0=61.0
        ),
        ACMProfile(
            name="8PSK 3/4",
            code_rate=3/4,
            modulation="8PSK",
            spectral_efficiency=2.23,
            required_cn0=63.0
        ),
        ACMProfile(
            name="8PSK 5/6",
            code_rate=5/6,
            modulation="8PSK",
            spectral_efficiency=2.48,
            required_cn0=65.0
        ),
        ACMProfile(
            name="16APSK 2/3",
            code_rate=2/3,
            modulation="16APSK",
            spectral_efficiency=2.64,
            required_cn0=67.0
        ),
        ACMProfile(
            name="16APSK 3/4",
            code_rate=3/4,
            modulation="16APSK",
            spectral_efficiency=2.97,
            required_cn0=69.0
        ),
        ACMProfile(
            name="16APSK 5/6",
            code_rate=5/6,
            modulation="16APSK",
            spectral_efficiency=3.30,
            required_cn0=71.0
        ),
        ACMProfile(
            name="32APSK 3/4",
            code_rate=3/4,
            modulation="32APSK",
            spectral_efficiency=3.71,
            required_cn0=74.0
        ),
        ACMProfile(
            name="32APSK 5/6",
            code_rate=5/6,
            modulation="32APSK",
            spectral_efficiency=4.13,
            required_cn0=76.0
        ),
        ACMProfile(
            name="64APSK 3/4",
            code_rate=3/4,
            modulation="64APSK",
            spectral_efficiency=4.46,
            required_cn0=79.0
        ),
        ACMProfile(
            name="64APSK 5/6",
            code_rate=5/6,
            modulation="64APSK",
            spectral_efficiency=4.95,
            required_cn0=82.0
        )
    ]
    
    def __init__(self, profiles: List[ACMProfile] = None):
        """Initialize ACM controller with optional custom profiles"""
        self.profiles = profiles or sorted(
            self.STANDARD_PROFILES,
            key=lambda p: p.required_cn0
        )
        self.current_profile = None
        self.history = []
        self.state = ACMState.NOMINAL
    
    def select_best_profile(
        self, 
        cn0: float, 
        target_ber: float = 1e-6,
        margin_db: float = 3.0
    ) -> Tuple[ACMProfile, Dict]:
        """
        Select the best ACM profile based on current C/N0
        
        Args:
            cn0: Carrier-to-noise density ratio in dB-Hz
            target_ber: Target bit error rate
            margin_db: Additional margin in dB to account for fading
            
        Returns:
            Tuple of (best_profile, metrics)
        """
        # Adjust C/N0 with margin and implementation loss
        effective_cn0 = cn0 - margin_db
        
        # Find the highest spectral efficiency profile that meets requirements
        best_profile = None
        for profile in reversed(self.profiles):
            if effective_cn0 >= profile.required_cn0:
                best_profile = profile
                break
        
        if not best_profile:
            # No suitable profile found, use the most robust one
            best_profile = self.profiles[0]
            self.state = ACMState.OUTAGE
        else:
            # Determine state based on margin
            margin = cn0 - best_profile.required_cn0
            if margin < 2.0:
                self.state = ACMState.MARGINAL
            elif margin < 5.0:
                self.state = ACMState.DEGRADED
            else:
                self.state = ACMState.NOMINAL
        
        # Calculate metrics
        metrics = {
            'effective_cn0': effective_cn0,
            'margin_db': cn0 - best_profile.required_cn0,
            'state': self.state.name,
            'timestamp': datetime.utcnow().isoformat(),
            'target_ber': target_ber
        }
        
        # Record history
        self.history.append({
            'profile': best_profile.name,
            'cn0': cn0,
            'effective_cn0': effective_cn0,
            'timestamp': datetime.utcnow(),
            'state': self.state.name,
            'metrics': metrics
        })
        
        # Keep only the last 1000 entries
        if len(self.history) > 1000:
            self.history = self.history[-1000:]
        
        self.current_profile = best_profile
        return best_profile, metrics
    
    def get_available_data_rate(
        self, 
        bandwidth_hz: float, 
        cn0: float = None,
        target_ber: float = 1e-6,
        margin_db: float = 3.0
    ) -> Dict:
        """
        Calculate available data rate for current or specified C/N0
        
        Args:
            bandwidth_hz: Channel bandwidth in Hz
            cn0: Optional C/N0 in dB-Hz. If None, use current profile
            target_ber: Target bit error rate
            margin_db: Additional margin in dB
            
        Returns:
            Dictionary with data rate and profile information
        """
        if cn0 is not None:
            profile, metrics = self.select_best_profile(cn0, target_ber, margin_db)
        elif self.current_profile:
            profile = self.current_profile
            metrics = {
                'effective_cn0': None,
                'margin_db': None,
                'state': self.state.name,
                'timestamp': datetime.utcnow().isoformat(),
                'target_ber': target_ber
            }
        else:
            # No profile selected yet, use most robust
            profile = self.profiles[0]
            metrics = {
                'effective_cn0': None,
                'margin_db': None,
                'state': 'UNKNOWN',
                'timestamp': datetime.utcnow().isoformat(),
                'target_ber': target_ber
            }
        
        data_rate_bps = bandwidth_hz * profile.spectral_efficiency
        
        return {
            'data_rate_bps': data_rate_bps,
            'data_rate_mbps': data_rate_bps / 1e6,
            'spectral_efficiency': profile.spectral_efficiency,
            'profile': profile.name,
            'modulation': profile.modulation,
            'code_rate': f"{int(profile.code_rate * 100)}%",
            'bandwidth_hz': bandwidth_hz,
            'bandwidth_mhz': bandwidth_hz / 1e6,
            'metrics': metrics
        }
    
    def get_required_cn0(
        self,
        data_rate_bps: float,
        bandwidth_hz: float,
        target_ber: float = 1e-6
    ) -> Dict:
        """
        Calculate required C/N0 for a target data rate and bandwidth
        
        Args:
            data_rate_bps: Target data rate in bps
            bandwidth_hz: Available bandwidth in Hz
            target_ber: Target bit error rate
            
        Returns:
            Dictionary with required C/N0 and profile information
        """
        required_spectral_eff = data_rate_bps / bandwidth_hz
        
        # Find the profile with the lowest C/N0 that meets the spectral efficiency
        required_profile = None
        for profile in self.profiles:
            if profile.spectral_efficiency >= required_spectral_eff:
                required_profile = profile
                break
        
        if not required_profile:
            # No profile can support this data rate with the given bandwidth
            return {
                'feasible': False,
                'required_cn0': None,
                'message': 'No ACM profile can support the requested data rate with the given bandwidth',
                'required_spectral_efficiency': required_spectral_eff,
                'max_spectral_efficiency': self.profiles[-1].spectral_efficiency
            }
        
        return {
            'feasible': True,
            'required_cn0': required_profile.required_cn0,
            'profile': required_profile,
            'required_spectral_efficiency': required_spectral_eff,
            'achievable_data_rate': required_profile.data_rate(bandwidth_hz)
        }
