from datetime import datetime, timedelta
from typing import List, Optional, Tuple
import numpy as np
from sgp4.api import Satrec, WGS72
from sgp4 import omm
from astropy import units as u
from astropy.time import Time
from astropy.coordinates import (
    TEME, ITRS, GCRS, 
    CartesianRepresentation,
    CartesianDifferential,
    EarthLocation,
    AltAz,
    get_sun,
    solar_system_ephemeris
)
from astropy.coordinates import get_body
from astropy.coordinates import SkyCoord
from astropy.utils.iers import conf

# Configure astropy to use IERS data properly
conf.auto_max_age = 30  # days
conf.auto_download = True

class OrbitPredictor:
    """Service for satellite orbit prediction and pass calculations"""
    
    def __init__(self, tle_line1: str, tle_line2: str, tle_epoch: datetime):
        """
        Initialize with TLE data
        
        Args:
            tle_line1: First line of TLE
            tle_line2: Second line of TLE
            tle_epoch: Epoch of the TLE data
        """
        self.satellite = Satrec.twoline2rv(tle_line1, tle_line2, WGS72)
        self.tle_epoch = Time(tle_epoch)
    
    def get_position_velocity_teme(self, time: datetime) -> Tuple[np.ndarray, np.ndarray]:
        """
        Get satellite position and velocity in TEME frame
        
        Args:
            time: UTC time for which to calculate position/velocity
            
        Returns:
            tuple: (position_km, velocity_km_s) in TEME frame
        """
        # Convert to minutes since TLE epoch
        astro_time = Time(time)
        minutes_since_epoch = (astro_time - self.tle_epoch).to(u.minute).value
        
        # Get TEME position/velocity (km, km/s)
        error_code, position, velocity = self.satellite.sgp4(
            self.satellite.jdsatepoch + minutes_since_epoch / 1440.0,
            0.0  # Fraction of day
        )
        
        if error_code != 0:
            raise ValueError(f"SGP4 propagation error: {error_code}")
            
        return np.array(position), np.array(velocity)
    
    def get_position_velocity_itrf(self, time: datetime) -> Tuple[np.ndarray, np.ndarray]:
        """
        Get satellite position and velocity in ITRF frame
        
        Args:
            time: UTC time for which to calculate position/velocity
            
        Returns:
            tuple: (position_km, velocity_km_s) in ITRF frame
        """
        # Get position/velocity in TEME
        r_teme, v_teme = self.get_position_velocity_teme(time)
        
        # Convert to astropy Time
        astro_time = Time(time)
        
        # Create TEME frame
        teme_p = CartesianRepresentation(r_teme * u.km)
        teme_v = CartesianDifferential(v_teme * u.km / u.s)
        teme = TEME(teme_p.with_differentials(teme_v), obstime=astro_time)
        
        # Convert to ITRS (which is effectively ITRF)
        itrs = teme.transform_to(ITRS(obstime=astro_time))
        
        # Extract position and velocity
        position_km = np.array([itrs.x.value, itrs.y.value, itrs.z.value])
        velocity_km_s = np.array([itrs.v_x.value, itrs.v_y.value, itrs.v_z.value])
        
        return position_km, velocity_km_s
    
    def get_az_el_range(
        self, 
        time: datetime, 
        lat: float, 
        lon: float, 
        elevation: float = 0.0
    ) -> Tuple[float, float, float]:
        """
        Calculate azimuth, elevation and range to satellite from observer
        
        Args:
            time: UTC time
            lat: Observer latitude (degrees)
            lon: Observer longitude (degrees)
            elevation: Observer elevation (meters)
            
        Returns:
            tuple: (azimuth_deg, elevation_deg, range_km)
        """
        # Get satellite position in ITRF
        sat_pos_km, _ = self.get_position_velocity_itrf(time)
        
        # Create observer location
        obs_location = EarthLocation(
            lat=lat * u.deg,
            lon=lon * u.deg,
            height=elevation * u.m
        )
        
        # Create ITRS position for satellite
        sat_itrs = ITRS(
            x=sat_pos_km[0] * u.km,
            y=sat_pos_km[1] * u.km,
            z=sat_pos_km[2] * u.km,
            obstime=Time(time)
        )
        
        # Convert to topocentric coordinates
        alt_az = sat_itrs.transform_to(AltAz(obstime=Time(time), location=obs_location))
        
        return (
            alt_az.az.deg,  # azimuth in degrees
            alt_az.alt.deg,  # elevation in degrees
            alt_az.distance.km  # range in km
        )
    
    def find_next_pass(
        self,
        lat: float,
        lon: float,
        elevation: float = 0.0,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        min_elevation: float = 10.0,
        time_step: float = 60.0,  # seconds
        max_iterations: int = 1000
    ) -> Optional[dict]:
        """
        Find the next satellite pass over a ground station
        
        Args:
            lat: Observer latitude (degrees)
            lon: Observer longitude (degrees)
            elevation: Observer elevation (meters)
            start_time: Start time for search (default: now)
            end_time: End time for search (default: 7 days from now)
            min_elevation: Minimum elevation for a valid pass (degrees)
            time_step: Time step for initial search (seconds)
            max_iterations: Maximum number of iterations for search
            
        Returns:
            dict: Pass details or None if no pass found
        """
        if start_time is None:
            start_time = datetime.utcnow()
        if end_time is None:
            end_time = start_time + timedelta(days=7)
            
        current_time = start_time
        iteration = 0
        
        while current_time <= end_time and iteration < max_iterations:
            # Get elevation at current time
            try:
                _, el, _ = self.get_az_el_range(current_time, lat, lon, elevation)
            except Exception as e:
                print(f"Error calculating elevation: {e}")
                el = -90.0
            
            # Check if we're above the minimum elevation
            if el >= min_elevation:
                # Found a potential pass, now find the exact times
                return self._refine_pass(
                    current_time, lat, lon, elevation, 
                    min_elevation, time_step
                )
            
            # Move forward in time
            current_time += timedelta(seconds=time_step)
            iteration += 1
        
        return None
    
    def _refine_pass(
        self,
        start_time: datetime,
        lat: float,
        lon: float,
        elevation: float,
        min_elevation: float,
        time_step: float
    ) -> dict:
        """Refine pass details with higher precision"""
        # Find rise time (when elevation crosses min_elevation going up)
        rise_time = self._find_crossing(
            start_time - timedelta(minutes=30),  # Look back 30 minutes
            start_time,
            lat, lon, elevation,
            min_elevation,
            rising=True
        )
        
        # Find set time (when elevation crosses min_elevation going down)
        set_time = self._find_crossing(
            start_time,
            start_time + timedelta(hours=2),  # Look ahead 2 hours
            lat, lon, elevation,
            min_elevation,
            rising=False
        )
        
        if rise_time is None or set_time is None:
            return None
            
        # Find maximum elevation time
        max_el_time = self._find_max_elevation(
            rise_time, 
            set_time,
            lat, lon, elevation
        )
        
        if max_el_time is None:
            return None
            
        # Get max elevation
        _, max_el, _ = self.get_az_el_range(
            max_el_time, lat, lon, elevation
        )
        
        # Calculate duration
        duration_s = (set_time - rise_time).total_seconds()
        
        return {
            'rise_time': rise_time,
            'set_time': set_time,
            'max_elevation_time': max_el_time,
            'max_elevation': max_el,
            'duration_s': duration_s
        }
    
    def _find_crossing(
        self,
        t1: datetime,
        t2: datetime,
        lat: float,
        lon: float,
        elevation: float,
        min_elevation: float,
        rising: bool = True
    ) -> Optional[datetime]:
        """Find when the satellite crosses the minimum elevation"""
        # Binary search between t1 and t2
        left = t1
        right = t2
        
        for _ in range(10):  # Limit iterations
            if (right - left).total_seconds() < 1.0:  # 1 second precision
                mid = left + (right - left) / 2
                return mid
                
            mid = left + (right - left) / 2
            
            try:
                _, el, _ = self.get_az_el_range(mid, lat, lon, elevation)
            except Exception:
                return None
            
            if (rising and el >= min_elevation) or (not rising and el < min_elevation):
                right = mid
            else:
                left = mid
                
        return None
    
    def _find_max_elevation(
        self,
        t1: datetime,
        t2: datetime,
        lat: float,
        lon: float,
        elevation: float
    ) -> Optional[datetime]:
        """Find time of maximum elevation between t1 and t2"""
        # Simple approach: sample at 10 points and find the maximum
        # For higher precision, use golden section search
        best_elevation = -90.0
        best_time = None
        
        # Sample at 10 points
        for i in range(10):
            t = t1 + (t2 - t1) * (i / 9.0)
            try:
                _, el, _ = self.get_az_el_range(t, lat, lon, elevation)
                if el > best_elevation:
                    best_elevation = el
                    best_time = t
            except Exception:
                continue
                
        return best_time

    @classmethod
    def from_tle_lines(cls, tle_line1: str, tle_line2: str, tle_epoch: datetime) -> 'OrbitPredictor':
        """Create an OrbitPredictor from TLE lines"""
        return cls(tle_line1, tle_line2, tle_epoch)
    
    @classmethod
    def from_omm_entries(cls, omm_entries: dict) -> 'OrbitPredictor':
        """Create an OrbitPredictor from OMM (Orbit Mean-Elements Message) entries"""
        # This is a simplified version - in practice you'd need to handle all OMM fields
        tle_line1 = omm_entries.get('TLE_LINE1')
        tle_line2 = omm_entries.get('TLE_LINE2')
        tle_epoch = omm_entries.get('EPOCH')
        
        if not all([tle_line1, tle_line2, tle_epoch]):
            raise ValueError("Missing required TLE data in OMM entries")
            
        return cls(tle_line1, tle_line2, tle_epoch)
