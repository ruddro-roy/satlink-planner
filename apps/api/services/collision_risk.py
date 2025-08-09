"""Collision Risk Assessment Service (COLA)"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import numpy as np
from sqlalchemy.orm import Session
from sgp4.api import Satrec, WGS72
from sgp4 import omm
from astropy.time import Time
from astropy import units as u
from astropy.coordinates import TEME, ITRS, CartesianRepresentation, CartesianDifferential

from domain.models import Satellite
from domain.models_digital_twin import CollisionRiskAssessment, COLAStatus, AnomalyDetection, AnomalyType, AnomalySeverity, AnomalyStatus

logger = logging.getLogger(__name__)

class CollisionRiskAnalyzer:
    """Service for collision risk assessment and analysis"""
    
    # Constants
    EARTH_RADIUS_KM = 6378.137  # WGS84 equatorial radius in km
    COLLISION_THRESHOLD_KM = 5.0  # Distance threshold for collision risk (km)
    TIME_STEP_MINUTES = 1.0  # Time step for propagation (minutes)
    
    def __init__(self, db: Session):
        self.db = db
    
    def assess_collision_risk(
        self, 
        satellite_id: int, 
        assessment_window_hours: int = 72,
        force: bool = False
    ) -> Optional[CollisionRiskAssessment]:
        """
        Perform collision risk assessment for a satellite
        
        Args:
            satellite_id: ID of the satellite to assess
            assessment_window_hours: Time window for assessment in hours
            force: If True, force reassessment even if a recent one exists
            
        Returns:
            CollisionRiskAssessment object if assessment was performed, None otherwise
        """
        # Check if a recent assessment exists
        if not force:
            existing = self.db.query(CollisionRiskAssessment).filter(
                CollisionRiskAssessment.satellite_id == satellite_id,
                CollisionRiskAssessment.assessment_time > datetime.utcnow() - timedelta(hours=1)
            ).first()
            
            if existing:
                logger.info(f"Recent assessment found for satellite {satellite_id}, skipping")
                return existing
        
        # Get the satellite
        satellite = self.db.query(Satellite).get(satellite_id)
        if not satellite or not satellite.tle_line1 or not satellite.tle_line2:
            logger.error(f"Satellite {satellite_id} not found or missing TLE data")
            return None
        
        # Create a new assessment
        assessment = CollisionRiskAssessment(
            satellite_id=satellite_id,
            assessment_time=datetime.utcnow(),
            assessment_window_hours=assessment_window_hours,
            status=COLAStatus.IN_PROGRESS,
            metadata={
                'assessment_start': datetime.utcnow().isoformat(),
                'satellite_name': satellite.name,
                'norad_id': satellite.norad_id
            }
        )
        
        self.db.add(assessment)
        self.db.flush()  # Get the assessment ID
        
        try:
            # Get all active satellites for comparison
            active_sats = self.db.query(Satellite).filter(
                Satellite.id != satellite_id,
                Satellite.tle_line1.isnot(None),
                Satellite.tle_line2.isnot(None)
            ).all()
            
            # Convert assessment window to minutes
            window_minutes = assessment_window_hours * 60
            time_steps = int(window_minutes / self.TIME_STEP_MINUTES)
            
            # Initialize tracking variables
            closest_approach_km = float('inf')
            closest_approach_time = None
            objects_at_risk = set()
            
            # Get the primary satellite's orbit predictor
            primary_sat = self._create_satrec(satellite)
            
            # Perform propagation and collision checking
            for i in range(time_steps):
                minutes_from_epoch = i * self.TIME_STEP_MINUTES
                current_time = datetime.utcnow() + timedelta(minutes=minutes_from_epoch)
                
                # Propagate primary satellite
                primary_pos, _ = self._propagate_satrec(primary_sat, minutes_from_epoch)
                
                # Skip if propagation failed
                if primary_pos is None:
                    continue
                
                # Check against all other satellites
                for other_sat in active_sats:
                    try:
                        # Create and propagate secondary satellite
                        secondary_sat = self._create_satrec(other_sat)
                        secondary_pos, _ = self._propagate_satrec(
                            secondary_sat, 
                            self._minutes_since_epoch(other_sat, current_time)
                        )
                        
                        if secondary_pos is None:
                            continue
                        
                        # Calculate distance between satellites
                        distance_km = np.linalg.norm(np.array(primary_pos) - np.array(secondary_pos))
                        
                        # Check if this is a new closest approach
                        if distance_km < closest_approach_km:
                            closest_approach_km = distance_km
                            closest_approach_time = current_time
                        
                        # Check for collision risk
                        if distance_km < self.COLLISION_THRESHOLD_KM:
                            objects_at_risk.add((other_sat.norad_id, other_sat.name or f"NORAD-{other_sat.norad_id}"))
                            
                    except Exception as e:
                        logger.error(f"Error checking collision with satellite {other_sat.id}: {e}")
                        continue
            
            # Update assessment with results
            assessment.status = COLAStatus.COMPLETED
            assessment.risk_score = self._calculate_risk_score(closest_approach_km, len(objects_at_risk))
            assessment.closest_approach_km = closest_approach_km
            assessment.closest_approach_time = closest_approach_time
            
            # Convert set of tuples to list of dicts for JSON serialization
            assessment.objects_at_risk = [
                {'norad_id': norad_id, 'name': name}
                for norad_id, name in objects_at_risk
            ]
            
            assessment.metadata.update({
                'assessment_end': datetime.utcnow().isoformat(),
                'closest_approach_km': closest_approach_km,
                'closest_approach_time': closest_approach_time.isoformat() if closest_approach_time else None,
                'objects_at_risk_count': len(objects_at_risk),
                'risk_assessment': 'high' if assessment.risk_score > 0.7 else 
                                 'medium' if assessment.risk_score > 0.3 else 'low'
            })
            
            # Create anomaly if high risk
            if assessment.risk_score > 0.7:
                self._create_collision_anomaly(satellite, assessment)
            
            self.db.commit()
            logger.info(f"Completed collision risk assessment for satellite {satellite_id}")
            return assessment
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to complete collision risk assessment: {e}")
            assessment.status = COLAStatus.FAILED
            assessment.metadata['error'] = str(e)
            self.db.commit()
            return None
    
    def _create_satrec(self, satellite: Satellite) -> Satrec:
        """Create a Satrec object from a Satellite model"""
        return Satrec.twoline2rv(satellite.tle_line1, satellite.tle_line2, WGS72)
    
    def _minutes_since_epoch(self, satellite: Satellite, time: datetime) -> float:
        """Calculate minutes since TLE epoch for a given time"""
        tle_epoch = Time(satellite.tle_epoch)
        current_time = Time(time)
        return (current_time - tle_epoch).to(u.minute).value
    
    def _propagate_satrec(self, satrec: Satrec, minutes_from_epoch: float) -> Tuple[Optional[tuple], Optional[tuple]]:
        """Propagate a satellite's position and velocity"""
        try:
            # Convert minutes to days since epoch for SGP4
            days_from_epoch = minutes_from_epoch / 1440.0
            
            # Propagate to get position/velocity in TEME
            error_code, position, velocity = satrec.sgp4(satrec.jdsatepoch + days_from_epoch, 0.0)
            
            if error_code != 0:
                logger.warning(f"SGP4 propagation error: {error_code}")
                return None, None
                
            return tuple(position), tuple(velocity)
            
        except Exception as e:
            logger.error(f"Error in satellite propagation: {e}")
            return None, None
    
    def _calculate_risk_score(self, closest_approach_km: float, objects_at_risk_count: int) -> float:
        """Calculate a normalized risk score (0-1)"""
        if closest_approach_km == float('inf'):
            return 0.0
            
        # Base score on closest approach distance (closer = higher risk)
        distance_score = max(0, 1 - (closest_approach_km / (self.COLLISION_THRESHOLD_KM * 2)))
        
        # Increase score based on number of objects at risk
        object_factor = min(1.0, objects_at_risk_count * 0.1)
        
        # Combine factors (70% distance, 30% object count)
        risk_score = (0.7 * distance_score) + (0.3 * object_factor)
        
        return min(1.0, risk_score)  # Cap at 1.0
    
    def _create_collision_anomaly(
        self, 
        satellite: Satellite, 
        assessment: CollisionRiskAssessment
    ) -> AnomalyDetection:
        """Create an anomaly detection record for high collision risk"""
        anomaly = AnomalyDetection(
            anomaly_type=AnomalyType.COLLISION_RISK,
            severity=AnomalySeverity.CRITICAL,
            status=AnomalyStatus.DETECTED,
            title=f"High collision risk detected for {satellite.name or f'NORAD-{satellite.norad_id}'}",
            description=(
                f"Detected {len(assessment.objects_at_risk)} potential conjunction(s) "
                f"within {assessment.closest_approach_km:.2f} km. "
                f"Closest approach at {assessment.closest_approach_time} UTC."
            ),
            satellite_id=satellite.id,
            confidence_score=min(0.99, assessment.risk_score * 1.1),  # Cap at 0.99
            features={
                'closest_approach_km': assessment.closest_approach_km,
                'objects_at_risk': assessment.objects_at_risk,
                'assessment_window_hours': assessment.assessment_window_hours,
                'assessment_time': assessment.assessment_time.isoformat()
            },
            metadata={
                'cola_assessment_id': assessment.id,
                'recommended_actions': [
                    "Review conjunction details in the COLA dashboard",
                    "Consider performing a collision avoidance maneuver",
                    "Monitor the situation for changes"
                ]
            }
        )
        
        self.db.add(anomaly)
        self.db.flush()
        
        return anomaly
    
    def get_collision_risk_summary(self, satellite_id: int) -> Dict:
        """Get a summary of collision risk for a satellite"""
        latest = self.db.query(CollisionRiskAssessment).filter(
            CollisionRiskAssessment.satellite_id == satellite_id,
            CollisionRiskAssessment.status == COLAStatus.COMPLETED
        ).order_by(
            CollisionRiskAssessment.assessment_time.desc()
        ).first()
        
        if not latest:
            return {
                'status': 'no_data',
                'message': 'No collision risk assessment available',
                'last_updated': None,
                'risk_score': 0.0,
                'closest_approach_km': None,
                'closest_approach_time': None,
                'objects_at_risk': []
            }
        
        return {
            'status': 'ok',
            'last_updated': latest.assessment_time.isoformat(),
            'risk_score': latest.risk_score,
            'risk_level': 'high' if latest.risk_score > 0.7 else 'medium' if latest.risk_score > 0.3 else 'low',
            'closest_approach_km': latest.closest_approach_km,
            'closest_approach_time': latest.closest_approach_time.isoformat() if latest.closest_approach_time else None,
            'objects_at_risk': latest.objects_at_risk,
            'assessment_window_hours': latest.assessment_window_hours,
            'metadata': latest.metadata
        }
