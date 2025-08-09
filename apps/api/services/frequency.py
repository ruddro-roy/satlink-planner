"""Frequency coordination and ITU-R recommendation service"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Union
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import or_

from domain.models import Satellite, GroundStation
from domain.models_digital_twin import FrequencyAllocation, AnomalyDetection, AnomalyType, AnomalySeverity, AnomalyStatus

logger = logging.getLogger(__name__)

class FrequencyCoordinator:
    """Service for frequency coordination and ITU-R compliance"""
    
    # ITU-R frequency bands and their characteristics
    ITUR_FREQUENCY_BANDS = {
        'VHF': {
            'min_freq_mhz': 30, 'max_freq_mhz': 300,
            'primary_services': ['aeronautical mobile', 'maritime mobile', 'broadcasting'],
            'secondary_services': ['amateur', 'radio astronomy'],
            'itu_region_restrictions': {},
            'coordination_required': True,
            'notes': 'Subject to high levels of interference'
        },
        'UHF': {
            'min_freq_mhz': 300, 'max_freq_mhz': 3000,
            'primary_services': ['mobile', 'broadcasting', 'fixed', 'mobile-satellite'],
            'secondary_services': ['amateur', 'radio astronomy'],
            'itu_region_restrictions': {},
            'coordination_required': True,
            'notes': 'Heavily used, coordination critical'
        },
        'L': {
            'min_freq_mhz': 1000, 'max_freq_mhz': 2000,
            'primary_services': ['mobile-satellite', 'aeronautical mobile-satellite', 'radionavigation-satellite'],
            'secondary_services': ['radio astronomy', 'space research'],
            'itu_region_restrictions': {},
            'coordination_required': True,
            'notes': 'Common for LEO satellite communications'
        },
        'S': {
            'min_freq_mhz': 2000, 'max_freq_mhz': 4000,
            'primary_services': ['mobile-satellite', 'fixed-satellite', 'earth exploration-satellite'],
            'secondary_services': ['radio astronomy', 'space research'],
            'itu_region_restrictions': {},
            'coordination_required': True,
            'notes': 'Widely used for TT&C and data downlink'
        },
        'C': {
            'min_freq_mhz': 4000, 'max_freq_mhz': 8000,
            'primary_services': ['fixed-satellite', 'mobile-satellite', 'radar'],
            'secondary_services': ['radio astronomy'],
            'itu_region_restrictions': {},
            'coordination_required': True,
            'notes': 'Common for satellite communications'
        },
        'X': {
            'min_freq_mhz': 8000, 'max_freq_mhz': 12000,
            'primary_services': ['fixed-satellite', 'mobile-satellite', 'radar', 'earth exploration-satellite'],
            'secondary_services': ['radio astronomy'],
            'itu_region_restrictions': {},
            'coordination_required': True,
            'notes': 'Widely used for military and Earth observation'
        },
        'Ku': {
            'min_freq_mhz': 12000, 'max_freq_mhz': 18000,
            'primary_services': ['fixed-satellite', 'broadcasting-satellite', 'mobile-satellite'],
            'secondary_services': ['radio astronomy', 'space research'],
            'itu_region_restrictions': {},
            'coordination_required': True,
            'notes': 'Popular for DTH and VSAT services'
        },
        'Ka': {
            'min_freq_mhz': 27000, 'max_freq_mhz': 40000,
            'primary_services': ['fixed-satellite', 'mobile-satellite', 'inter-satellite'],
            'secondary_services': ['radio astronomy', 'space research'],
            'itu_region_restrictions': {},
            'coordination_required': True,
            'notes': 'High throughput satellites, rain attenuation significant'
        },
        'V': {
            'min_freq_mhz': 40000, 'max_freq_mhz': 75000,
            'primary_services': ['fixed-satellite', 'mobile-satellite', 'earth exploration-satellite'],
            'secondary_services': ['radio astronomy', 'space research'],
            'itu_region_restrictions': {},
            'coordination_required': True,
            'notes': 'Emerging for high-capacity satellite links, atmospheric effects significant'
        }
    }
    
    # ITU Regions
    ITU_REGIONS = {
        1: 'Europe, Africa, the Middle East west of the Persian Gulf including Iraq, the former Soviet Union and Mongolia',
        2: 'Americas, Greenland and some of the eastern Pacific Islands',
        3: 'Most of non-former-Soviet-Union Asia east of Iran and most of Oceania'
    }
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_frequency_band(self, frequency_mhz: float) -> Optional[Dict]:
        """Get the ITU-R frequency band for a given frequency"""
        for band_name, band_info in self.ITUR_FREQUENCY_BANDS.items():
            if band_info['min_freq_mhz'] <= frequency_mhz <= band_info['max_freq_mhz']:
                return {
                    'band': band_name,
                    **band_info,
                    'center_freq_mhz': (band_info['min_freq_mhz'] + band_info['max_freq_mhz']) / 2,
                    'bandwidth_mhz': band_info['max_freq_mhz'] - band_info['min_freq_mhz']
                }
        return None
    
    def check_frequency_allocation(
        self,
        frequency_mhz: float,
        bandwidth_mhz: float,
        service: str,
        itu_region: int = 1,
        tx_power_dbm: float = None,
        tx_antenna_gain_dbi: float = None,
        rx_sensitivity_dbm: float = None
    ) -> Dict:
        """Check if a frequency allocation is compliant with ITU-R recommendations"""
        band_info = self.get_frequency_band(frequency_mhz)
        if not band_info:
            return {
                'status': 'error',
                'message': f'Frequency {frequency_mhz} MHz is outside defined ITU-R bands',
                'compatible': False,
                'band': None,
                'recommendations': []
            }
        
        service = service.lower()
        primary_services = [s.lower() for s in band_info['primary_services']]
        secondary_services = [s.lower() for s in band_info['secondary_services']]
        
        is_primary = service in primary_services
        is_secondary = service in secondary_services
        
        if not (is_primary or is_secondary):
            return {
                'status': 'error',
                'message': f'Service "{service}" is not allocated in the {band_info["band"]} band',
                'compatible': False,
                'band': band_info['band'],
                'recommendations': [
                    f'Consider using one of these primary services: {", ".join(band_info["primary_services"])}',
                    f'Or these secondary services: {", ".join(band_info["secondary_services"])}'
                ]
            }
        
        region_restriction = band_info['itu_region_restrictions'].get(itu_region)
        if region_restriction:
            return {
                'status': 'warning',
                'message': f'Service "{service}" has restrictions in ITU Region {itu_region}: {region_restriction}',
                'compatible': False,
                'band': band_info['band'],
                'recommendations': [
                    'Check with national regulatory authority for specific restrictions',
                    'Consider alternative frequency bands if available'
                ]
            }
        
        min_freq = frequency_mhz - (bandwidth_mhz / 2)
        max_freq = frequency_mhz + (bandwidth_mhz / 2)
        
        if min_freq < band_info['min_freq_mhz'] or max_freq > band_info['max_freq_mhz']:
            return {
                'status': 'error',
                'message': f'Frequency allocation {min_freq}-{max_freq} MHz exceeds {band_info["band"]} band limits',
                'compatible': False,
                'band': band_info['band'],
                'recommendations': [
                    f'Reduce bandwidth to fit within {band_info["min_freq_mhz"]}-{band_info["max_freq_mhz"]} MHz',
                    'Or select a different center frequency'
                ]
            }
        
        interference = self.check_interference(frequency_mhz, bandwidth_mhz, tx_power_dbm, tx_antenna_gain_dbi)
        coordination_required = band_info['coordination_required']
        
        recommendations = []
        if is_secondary:
            recommendations.append(
                f'Service "{service}" is secondary in the {band_info["band"]} band. '
                'Must not cause harmful interference to primary services.'
            )
        
        if coordination_required:
            recommendations.append(
                'Coordination with other satellite networks and terrestrial services '
                'is required before operation.'
            )
        
        if interference['interference_detected']:
            recommendations.extend([
                'Potential interference detected with existing allocations:',
                *[f'- {desc}' for desc in interference['interference_details']]
            ])
        
        return {
            'status': 'success',
            'message': 'Frequency allocation is compliant with ITU-R recommendations',
            'compatible': True,
            'band': band_info['band'],
            'is_primary': is_primary,
            'is_secondary': is_secondary,
            'coordination_required': coordination_required,
            'interference_risk': interference['interference_detected'],
            'interference_details': interference['interference_details'],
            'recommendations': recommendations,
            'band_info': band_info
        }
    
    def check_interference(
        self,
        frequency_mhz: float,
        bandwidth_mhz: float,
        tx_power_dbm: float = None,
        tx_antenna_gain_dbi: float = None
    ) -> Dict:
        """Check for potential interference with existing allocations"""
        min_freq = frequency_mhz - (bandwidth_mhz / 2)
        max_freq = frequency_mhz + (bandwidth_mhz / 2)
        
        # Find overlapping frequency allocations
        overlapping = self.db.query(FrequencyAllocation).filter(
            or_(
                (FrequencyAllocation.frequency_mhz + (FrequencyAllocation.bandwidth_mhz / 2)) >= min_freq,
                (FrequencyAllocation.frequency_mhz - (FrequencyAllocation.bandwidth_mhz / 2)) <= max_freq
            )
        ).all()
        
        interference_details = []
        interference_detected = False
        
        for alloc in overlapping:
            # Calculate overlap percentage
            overlap_min = max(min_freq, alloc.frequency_mhz - (alloc.bandwidth_mhz / 2))
            overlap_max = min(max_freq, alloc.frequency_mhz + (alloc.bandwidth_mhz / 2))
            overlap_bw = max(0, overlap_max - overlap_min)
            overlap_percent = (overlap_bw / min(bandwidth_mhz, alloc.bandwidth_mhz)) * 100
            
            if overlap_percent > 0:
                interference_detected = True
                details = (
                    f"{overlap_percent:.1f}% overlap with {alloc.service} allocation "
                    f"({alloc.frequency_mhz} MHz, {alloc.bandwidth_mhz} MHz)"
                )
                
                if tx_power_dbm is not None and tx_antenna_gain_dbi is not None:
                    eirp = tx_power_dbm + tx_antenna_gain_dbi
                    details += f" (EIRP: {eirp:.1f} dBm)"
                
                interference_details.append(details)
        
        return {
            'interference_detected': interference_detected,
            'interference_details': interference_details,
            'overlapping_allocations': len(interference_details)
        }
    
    def recommend_frequencies(
        self,
        desired_band: str,
        service: str,
        bandwidth_mhz: float,
        itu_region: int = 1,
        avoid_frequencies: List[float] = None
    ) -> List[Dict]:
        """Recommend frequency allocations based on requirements"""
        if desired_band.upper() not in self.ITUR_FREQUENCY_BANDS:
            return [{
                'status': 'error',
                'message': f'Unknown frequency band: {desired_band}'
            }]
        
        band_info = self.ITUR_FREQUENCY_BANDS[desired_band.upper()]
        service = service.lower()
        
        # Check if service is allowed in this band
        primary_services = [s.lower() for s in band_info['primary_services']]
        secondary_services = [s.lower() for s in band_info['secondary_services']]
        
        if service not in primary_services and service not in secondary_services:
            return [{
                'status': 'error',
                'message': f'Service "{service}" is not allocated in the {desired_band} band'
            }]
        
        # Generate frequency candidates
        min_freq = band_info['min_freq_mhz']
        max_freq = band_info['max_freq_mhz']
        
        # Avoid band edges (5% margin)
        margin = 0.05
        min_freq += (max_freq - min_freq) * margin
        max_freq -= (max_freq - min_freq) * margin
        
        # Generate candidate frequencies
        candidates = []
        step = max(bandwidth_mhz * 1.5, (max_freq - min_freq) / 10)  # At least 50% guard band
        
        for center_freq in np.arange(min_freq + bandwidth_mhz/2, max_freq, step):
            if avoid_frequencies and any(abs(center_freq - f) < bandwidth_mhz for f in avoid_frequencies):
                continue
                
            # Check for interference
            interference = self.check_interference(center_freq, bandwidth_mhz)
            
            candidates.append({
                'frequency_mhz': round(center_freq, 3),
                'bandwidth_mhz': bandwidth_mhz,
                'interference_risk': interference['interference_detected'],
                'interference_details': interference['interference_details'],
                'band': desired_band.upper(),
                'is_primary': service in primary_services,
                'is_secondary': service in secondary_services,
                'coordination_required': band_info['coordination_required']
            })
        
        # Sort by interference risk (lowest first), then by frequency
        candidates.sort(key=lambda x: (x['interference_risk'], x['frequency_mhz']))
        
        return candidates
    
    def register_frequency_allocation(
        self,
        satellite_id: int,
        frequency_mhz: float,
        bandwidth_mhz: float,
        service: str,
        itu_region: int,
        status: str = 'pending',
        coordination_notes: str = None,
        valid_from: datetime = None,
        valid_until: datetime = None,
        metadata: Dict = None
    ) -> FrequencyAllocation:
        """Register a new frequency allocation"""
        # Check if allocation already exists
        existing = self.db.query(FrequencyAllocation).filter(
            FrequencyAllocation.satellite_id == satellite_id,
            FrequencyAllocation.frequency_mhz == frequency_mhz,
            FrequencyAllocation.bandwidth_mhz == bandwidth_mhz
        ).first()
        
        if existing:
            return existing
        
        # Validate the allocation
        validation = self.check_frequency_allocation(
            frequency_mhz=frequency_mhz,
            bandwidth_mhz=bandwidth_mhz,
            service=service,
            itu_region=itu_region
        )
        
        if not validation['compatible']:
            raise ValueError(f"Invalid frequency allocation: {validation['message']}")
        
        # Create the allocation
        allocation = FrequencyAllocation(
            satellite_id=satellite_id,
            frequency_mhz=frequency_mhz,
            bandwidth_mhz=bandwidth_mhz,
            service=service,
            itu_region=itu_region,
            status=status,
            coordination_notes=coordination_notes,
            valid_from=valid_from or datetime.utcnow(),
            valid_until=valid_until,
            metadata=metadata or {}
        )
        
        self.db.add(allocation)
        
        try:
            self.db.commit()
            logger.info(f"Registered frequency allocation for satellite {satellite_id}: {frequency_mhz} MHz")
            return allocation
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to register frequency allocation: {e}")
            raise
    
    def get_coordination_status(self, satellite_id: int) -> Dict:
        """Get the frequency coordination status for a satellite"""
        allocations = self.db.query(FrequencyAllocation).filter(
            FrequencyAllocation.satellite_id == satellite_id
        ).all()
        
        if not allocations:
            return {
                'status': 'not_required',
                'message': 'No frequency allocations found for this satellite',
                'allocations': []
            }
        
        # Check coordination status
        coordinated = all(alloc.status == 'coordinated' for alloc in allocations)
        pending = any(alloc.status == 'pending' for alloc in allocations)
        
        if coordinated:
            status = 'fully_coordinated'
            message = 'All frequency allocations are coordinated'
        elif pending:
            status = 'pending_coordination'
            message = 'Some frequency allocations are pending coordination'
        else:
            status = 'partially_coordinated'
            message = 'Some frequency allocations are not coordinated'
        
        return {
            'status': status,
            'message': message,
            'allocations': [{
                'id': alloc.id,
                'frequency_mhz': alloc.frequency_mhz,
                'bandwidth_mhz': alloc.bandwidth_mhz,
                'service': alloc.service,
                'status': alloc.status,
                'valid_from': alloc.valid_from.isoformat() if alloc.valid_from else None,
                'valid_until': alloc.valid_until.isoformat() if alloc.valid_until else None,
                'coordination_notes': alloc.coordination_notes
            } for alloc in allocations]
        }
