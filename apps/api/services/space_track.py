"""Space-Track.org integration service for TLE data"""
import os
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import requests
from requests.adapters import HTTPAdapter, Retry
from urllib.parse import urljoin

from sqlalchemy.orm import Session
from domain.models import Satellite
from domain.models_digital_twin import TLE, TLESource, TLEAccuracy

logger = logging.getLogger(__name__)

class SpaceTrackClient:
    """Client for interacting with Space-Track.org API"""
    
    BASE_URL = "https://www.space-track.org"
    AUTH_URL = "https://www.space-track.org/ajaxauth/login"
    
    def __init__(self, username: str = None, password: str = None):
        """Initialize with Space-Track credentials"""
        self.username = username or os.getenv("SPACE_TRACK_USERNAME")
        self.password = password or os.getenv("SPACE_TRACK_PASSWORD")
        self.session = self._create_session()
        self.authenticated = False
        
        if not self.username or not self.password:
            logger.warning("Space-Track username/password not provided. Some features may be limited.")
    
    def _create_session(self) -> requests.Session:
        """Create a requests session with retry logic"""
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"]
        )
        
        # Mount the retry adapter
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        
        return session
    
    def authenticate(self) -> bool:
        """Authenticate with Space-Track.org"""
        if not self.username or not self.password:
            logger.error("Cannot authenticate: Missing username or password")
            return False
            
        try:
            response = self.session.post(
                self.AUTH_URL,
                data={
                    'identity': self.username,
                    'password': self.password,
                    'query': 'https://www.space-track.org/basicspacedata/query/class/tle_latest/ORDINAL/1/EPOCH/%3Enow-30/format/json'
                },
                timeout=30
            )
            response.raise_for_status()
            self.authenticated = True
            logger.info("Successfully authenticated with Space-Track.org")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to authenticate with Space-Track.org: {e}")
            self.authenticated = False
            return False
    
    def get_latest_tle(self, norad_id: str) -> Optional[Dict]:
        """Get the latest TLE for a specific satellite by NORAD ID"""
        if not self.authenticated and not self.authenticate():
            return None
            
        try:
            url = urljoin(
                self.BASE_URL,
                f"basicspacedata/query/class/tle_latest/NORAD_CAT_ID/{norad_id}/ORDINAL/1/format/3le"
            )
            
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            # Parse the 3-line TLE format
            lines = response.text.strip().split('\n')
            if len(lines) != 3:
                logger.error(f"Unexpected TLE format for NORAD ID {norad_id}")
                return None
                
            name = lines[0].strip()
            line1 = lines[1].strip()
            line2 = lines[2].strip()
            
            # Get additional metadata
            metadata_url = urljoin(
                self.BASE_URL,
                f"basicspacedata/query/class/satcat/NORAD_CAT_ID/{norad_id}/format/json"
            )
            
            metadata_response = self.session.get(metadata_url, timeout=30)
            metadata_response.raise_for_status()
            metadata = metadata_response.json()[0] if metadata_response.json() else {}
            
            # Estimate TLE accuracy based on age
            tle_epoch = self._parse_tle_epoch(line1)
            age_days = (datetime.utcnow() - tle_epoch).days
            
            if age_days <= 1:
                accuracy = TLEAccuracy.HIGH
                position_error_km = 0.5  # Conservative estimate for <1 day old TLE
            elif age_days <= 7:
                accuracy = TLEAccuracy.MEDIUM
                position_error_km = 2.0
            else:
                accuracy = TLEAccuracy.LOW
                position_error_km = 5.0  # Could be much worse for older TLEs
            
            return {
                'name': name,
                'tle_line1': line1,
                'tle_line2': line2,
                'tle_epoch': tle_epoch,
                'source': TLESource.SPACE_TRACK,
                'accuracy': accuracy,
                'position_error_km': position_error_km,
                'metadata': {
                    'norad_id': norad_id,
                    'int_designator': metadata.get('INTLDES', ''),
                    'launch_date': metadata.get('LAUNCH', ''),
                    'decay_date': metadata.get('DECAY', ''),
                    'orbit_status': metadata.get('STATUS_CODE', '').lower(),
                    'tle_age_days': age_days,
                    'source': 'space-track.org',
                    'retrieved_at': datetime.utcnow().isoformat()
                }
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch TLE data for NORAD ID {norad_id}: {e}")
            return None
    
    def _parse_tle_epoch(self, line1: str) -> datetime:
        """Parse TLE epoch from line 1"""
        # TLE epoch is in YYDDD.DDDDDDDD format (first 18 chars of line 1)
        epoch_str = line1[18:32]
        year = 2000 + int(epoch_str[:2])  # Y2K fix
        day_of_year = float(epoch_str[2:])
        
        # Create datetime object for the given year and day of year
        base_date = datetime(year, 1, 1)
        epoch = base_date + timedelta(days=day_of_year - 1)
        
        return epoch.replace(tzinfo=None)


class TLEManager:
    """Manager for TLE data with Space-Track integration"""
    
    def __init__(self, db: Session, space_track_client: SpaceTrackClient = None):
        self.db = db
        self.space_track = space_track_client or SpaceTrackClient()
    
    def update_satellite_tle(self, satellite_id: int) -> Optional[TLE]:
        """Update TLE for a satellite from Space-Track"""
        # Get satellite by ID
        satellite = self.db.query(Satellite).get(satellite_id)
        if not satellite:
            logger.error(f"Satellite with ID {satellite_id} not found")
            return None
            
        if not satellite.norad_id:
            logger.error(f"Satellite {satellite_id} has no NORAD ID")
            return None
        
        # Get latest TLE from Space-Track
        tle_data = self.space_track.get_latest_tle(satellite.norad_id)
        if not tle_data:
            return None
        
        # Mark any existing TLEs as not current
        self.db.query(TLE).filter(
            TLE.satellite_id == satellite_id,
            TLE.is_current == True
        ).update({'is_current': False})
        
        # Create new TLE record
        new_tle = TLE(
            satellite_id=satellite_id,
            tle_line1=tle_data['tle_line1'],
            tle_line2=tle_data['tle_line2'],
            tle_epoch=tle_data['tle_epoch'],
            source=tle_data['source'],
            accuracy=tle_data['accuracy'],
            position_error_km=tle_data['position_error_km'],
            is_current=True,
            metadata=tle_data['metadata']
        )
        
        self.db.add(new_tle)
        
        # Update satellite's TLE data
        satellite.tle_line1 = tle_data['tle_line1']
        satellite.tle_line2 = tle_data['tle_line2']
        satellite.tle_epoch = tle_data['tle_epoch']
        satellite.updated_at = datetime.utcnow()
        
        try:
            self.db.commit()
            logger.info(f"Updated TLE for satellite {satellite_id} (NORAD: {satellite.norad_id})")
            return new_tle
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to update TLE for satellite {satellite_id}: {e}")
            return None
    
    def check_tle_ages(self, max_age_days: int = 7) -> List[Dict]:
        """Check for satellites with outdated TLE data"""
        threshold = datetime.utcnow() - timedelta(days=max_age_days)
        
        outdated = []
        
        # Get all satellites with TLEs older than threshold
        satellites = self.db.query(Satellite).filter(
            Satellite.tle_epoch < threshold
        ).all()
        
        for sat in satellites:
            age = (datetime.utcnow() - sat.tle_epoch).days
            outdated.append({
                'satellite_id': sat.id,
                'norad_id': sat.norad_id,
                'name': sat.name,
                'tle_epoch': sat.tle_epoch,
                'age_days': age,
                'needs_update': True
            })
        
        return outdated
    
    def update_all_outdated_tles(self, max_age_days: int = 7) -> Dict:
        """Update all outdated TLEs"""
        outdated = self.check_tle_ages(max_age_days)
        results = {
            'total': len(outdated),
            'updated': 0,
            'failed': 0,
            'details': []
        }
        
        for sat_info in outdated:
            result = self.update_satellite_tle(sat_info['satellite_id'])
            if result:
                results['updated'] += 1
                status = 'success'
            else:
                results['failed'] += 1
                status = 'failed'
            
            results['details'].append({
                'satellite_id': sat_info['satellite_id'],
                'norad_id': sat_info['norad_id'],
                'status': status
            })
        
        return results
