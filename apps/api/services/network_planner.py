"""Network Topology Planner and Handover Scheduler"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from domain.models import Satellite, GroundStation
from domain.models_digital_twin import (
    NetworkNode, NetworkLink, HandoverSchedule, 
    AnomalyDetection, AnomalyType, AnomalySeverity, AnomalyStatus
)

logger = logging.getLogger(__name__)

@dataclass
class NetworkNodeInfo:
    """Extended network node information"""
    id: int
    node_id: str
    name: str
    node_type: str
    lat: Optional[float] = None
    lon: Optional[float] = None
    alt: Optional[float] = None  # meters
    capabilities: Dict = None
    status: str = 'active'

@dataclass
class LinkBudget:
    """Link budget parameters"""
    frequency_mhz: float
    tx_power_dbm: float
    tx_antenna_gain_dbi: float
    rx_antenna_gain_dbi: float
    system_noise_temp_k: float = 290.0
    implementation_loss_db: float = 2.0
    rain_margin_db: float = 3.0
    required_cn0_db: float = 50.0  # Minimum required C/N0 in dB-Hz

class NetworkPlanner:
    """Network topology planning and handover scheduling service"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def add_network_node(
        self,
        node_id: str,
        name: str,
        node_type: str,
        lat: float = None,
        lon: float = None,
        alt: float = 0.0,
        capabilities: Dict = None,
        status: str = 'active'
    ) -> NetworkNode:
        """Add a new network node"""
        location = None
        if lat is not None and lon is not None:
            location = {'lat': lat, 'lon': lon, 'alt': alt}
        
        node = NetworkNode(
            node_id=node_id,
            name=name,
            node_type=node_type,
            location=location,
            capabilities=capabilities or {},
            status=status
        )
        
        self.db.add(node)
        
        try:
            self.db.commit()
            logger.info(f"Added network node: {node_id} ({name})")
            return node
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to add network node: {e}")
            raise
    
    def add_network_link(
        self,
        source_node_id: int,
        target_node_id: int,
        link_type: str,
        frequency_mhz: float = None,
        bandwidth_mhz: float = None,
        max_data_rate_mbps: float = None,
        status: str = 'active',
        metadata: Dict = None
    ) -> NetworkLink:
        """Add a new network link between nodes"""
        link = NetworkLink(
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            link_type=link_type,
            frequency_mhz=frequency_mhz,
            bandwidth_mhz=bandwidth_mhz,
            max_data_rate_mbps=max_data_rate_mbps,
            status=status,
            metadata=metadata or {}
        )
        
        self.db.add(link)
        
        try:
            self.db.commit()
            logger.info(f"Added network link: {source_node_id} <-> {target_node_id} ({link_type})")
            return link
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to add network link: {e}")
            raise
    
    def schedule_handover(
        self,
        link_id: int,
        satellite_id: int,
        ground_station_id: int,
        start_time: datetime,
        end_time: datetime,
        handover_type: str = 'make-before-break',
        metadata: Dict = None
    ) -> HandoverSchedule:
        """Schedule a handover between ground stations"""
        # Check for scheduling conflicts
        conflict = self.db.query(HandoverSchedule).filter(
            HandoverSchedule.link_id == link_id,
            HandoverSchedule.satellite_id == satellite_id,
            or_(
                and_(
                    HandoverSchedule.start_time <= start_time,
                    HandoverSchedule.end_time > start_time
                ),
                and_(
                    HandoverSchedule.start_time < end_time,
                    HandoverSchedule.end_time >= end_time
                ),
                and_(
                    HandoverSchedule.start_time >= start_time,
                    HandoverSchedule.end_time <= end_time
                )
            )
        ).first()
        
        if conflict:
            raise ValueError(
                f"Scheduling conflict with existing handover: {conflict.id} "
                f"({conflict.start_time} to {conflict.end_time})"
            )
        
        handover = HandoverSchedule(
            link_id=link_id,
            satellite_id=satellite_id,
            ground_station_id=ground_station_id,
            start_time=start_time,
            end_time=end_time,
            handover_type=handover_type,
            status='scheduled',
            metadata=metadata or {}
        )
        
        self.db.add(handover)
        
        try:
            self.db.commit()
            logger.info(
                f"Scheduled handover for satellite {satellite_id} to ground station {ground_station_id} "
                f"from {start_time} to {end_time}"
            )
            return handover
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to schedule handover: {e}")
            raise
    
    def plan_handovers(
        self,
        satellite_id: int,
        start_time: datetime,
        end_time: datetime,
        min_elevation_deg: float = 10.0,
        min_handover_time_sec: int = 30,
        max_handover_time_sec: int = 300,
        link_type: str = 'RF',
        frequency_mhz: float = None,
        bandwidth_mhz: float = None
    ) -> List[Dict]:
        """
        Plan optimal handovers for a satellite pass over multiple ground stations
        
        Args:
            satellite_id: ID of the satellite
            start_time: Start time for handover planning
            end_time: End time for handover planning
            min_elevation_deg: Minimum elevation angle for ground station visibility
            min_handover_time_sec: Minimum time to spend on a ground station (seconds)
            max_handover_time_sec: Maximum time to spend on a ground station (seconds)
            link_type: Type of link to establish
            frequency_mhz: Optional frequency for the link
            bandwidth_mhz: Optional bandwidth for the link
            
        Returns:
            List of scheduled handovers
        """
        # Get the satellite
        satellite = self.db.query(Satellite).get(satellite_id)
        if not satellite:
            raise ValueError(f"Satellite with ID {satellite_id} not found")
        
        # Get all ground stations
        ground_stations = self.db.query(GroundStation).all()
        if not ground_stations:
            raise ValueError("No ground stations available for handover planning")
        
        # Get or create network nodes for satellite and ground stations
        sat_node = self._get_or_create_satellite_node(satellite)
        gs_nodes = {
            gs.id: self._get_or_create_ground_station_node(gs)
            for gs in ground_stations
        }
        
        # Calculate visibility windows for each ground station
        visibility_windows = []
        for gs in ground_stations:
            # This would use the orbit predictor to calculate visibility windows
            # For now, we'll use a placeholder
            windows = self._calculate_visibility_windows(
                satellite, gs, start_time, end_time, min_elevation_deg
            )
            
            for window in windows:
                visibility_windows.append({
                    'ground_station_id': gs.id,
                    'ground_station_name': gs.name,
                    'start_time': window['start_time'],
                    'end_time': window['end_time'],
                    'max_elevation': window['max_elevation'],
                    'duration': (window['end_time'] - window['start_time']).total_seconds()
                })
        
        # Sort visibility windows by start time
        visibility_windows.sort(key=lambda x: x['start_time'])
        
        # Plan handovers (simple greedy algorithm)
        scheduled_handovers = []
        current_time = start_time
        current_gs = None
        
        while current_time < end_time:
            # Find the best ground station for the current time
            best_gs = None
            best_window = None
            best_score = -1
            
            for window in visibility_windows:
                # Skip if window has already passed
                if window['end_time'] <= current_time:
                    continue
                
                # Skip if window hasn't started yet but we have time before it does
                if window['start_time'] > current_time + timedelta(seconds=min_handover_time_sec):
                    continue
                
                # Calculate score based on elevation and remaining window time
                window_remaining = (window['end_time'] - max(current_time, window['start_time'])).total_seconds()
                if window_remaining < min_handover_time_sec:
                    continue
                
                # Simple scoring: prefer higher elevation and longer remaining time
                score = window['max_elevation'] * min(window_remaining, max_handover_time_sec)
                
                # Penalize handovers to encourage longer dwell times
                if current_gs is not None and window['ground_station_id'] != current_gs:
                    score *= 0.9  # 10% penalty for handover
                
                if score > best_score:
                    best_score = score
                    best_gs = window['ground_station_id']
                    best_window = window
            
            if best_gs is None:
                # No suitable ground station found
                break
            
            # Calculate handover time
            window_start = max(current_time, best_window['start_time'])
            window_end = best_window['end_time']
            
            # Limit handover time to max_handover_time_sec
            handover_end = min(
                window_start + timedelta(seconds=max_handover_time_sec),
                window_end
            )
            
            # Ensure minimum handover time
            if (handover_end - window_start).total_seconds() < min_handover_time_sec:
                handover_end = window_start + timedelta(seconds=min_handover_time_sec)
                if handover_end > window_end:
                    # Not enough time for minimum handover
                    current_time = window_end
                    continue
            
            # Create or get network link
            link = self._get_or_create_link(
                source_node_id=sat_node.id,
                target_node_id=gs_nodes[best_gs].id,
                link_type=link_type,
                frequency_mhz=frequency_mhz,
                bandwidth_mhz=bandwidth_mhz
            )
            
            # Schedule handover
            try:
                handover = self.schedule_handover(
                    link_id=link.id,
                    satellite_id=satellite_id,
                    ground_station_id=best_gs,
                    start_time=window_start,
                    end_time=handover_end,
                    handover_type='make-before-break' if current_gs is not None else 'initial',
                    metadata={
                        'max_elevation': best_window['max_elevation'],
                        'planned_data_volume_mb': 0,  # Would be calculated based on data rate
                        'link_quality': 'high'  # Would be estimated
                    }
                )
                
                scheduled_handovers.append({
                    'handover_id': handover.id,
                    'ground_station_id': best_gs,
                    'ground_station_name': best_window['ground_station_name'],
                    'start_time': window_start.isoformat(),
                    'end_time': handover_end.isoformat(),
                    'duration_seconds': (handover_end - window_start).total_seconds(),
                    'max_elevation': best_window['max_elevation'],
                    'link_id': link.id,
                    'link_type': link_type,
                    'frequency_mhz': frequency_mhz,
                    'bandwidth_mhz': bandwidth_mhz
                })
                
                current_time = handover_end
                current_gs = best_gs
                
            except Exception as e:
                logger.error(f"Failed to schedule handover: {e}")
                current_time = handover_end
                continue
        
        return scheduled_handovers
    
    def _get_or_create_satellite_node(self, satellite: Satellite) -> NetworkNode:
        """Get or create a network node for a satellite"""
        node = self.db.query(NetworkNode).filter(
            NetworkNode.node_id == f'sat_{satellite.norad_id}'
        ).first()
        
        if not node:
            node = NetworkNode(
                node_id=f'sat_{satellite.norad_id}',
                name=f'Satellite {satellite.norad_id}',
                node_type='satellite',
                location=None,  # Dynamic for satellites
                capabilities={
                    'norad_id': satellite.norad_id,
                    'tle_epoch': satellite.tle_epoch.isoformat() if satellite.tle_epoch else None,
                    'orbit_type': 'LEO'  # Would be determined from TLE
                },
                status='active'
            )
            self.db.add(node)
            self.db.flush()
        
        return node
    
    def _get_or_create_ground_station_node(self, ground_station: GroundStation) -> NetworkNode:
        """Get or create a network node for a ground station"""
        node = self.db.query(NetworkNode).filter(
            NetworkNode.node_id == f'gs_{ground_station.id}'
        ).first()
        
        if not node:
            node = NetworkNode(
                node_id=f'gs_{ground_station.id}',
                name=ground_station.name,
                node_type='ground_station',
                location={
                    'lat': ground_station.latitude,
                    'lon': ground_station.longitude,
                    'alt': ground_station.elevation or 0.0
                },
                capabilities={
                    'latitude': ground_station.latitude,
                    'longitude': ground_station.longitude,
                    'elevation': ground_station.elevation or 0.0
                },
                status='active'
            )
            self.db.add(node)
            self.db.flush()
        
        return node
    
    def _get_or_create_link(
        self,
        source_node_id: int,
        target_node_id: int,
        link_type: str,
        frequency_mhz: float = None,
        bandwidth_mhz: float = None
    ) -> NetworkLink:
        """Get or create a network link between nodes"""
        link = self.db.query(NetworkLink).filter(
            or_(
                and_(
                    NetworkLink.source_node_id == source_node_id,
                    NetworkLink.target_node_id == target_node_id
                ),
                and_(
                    NetworkLink.source_node_id == target_node_id,
                    NetworkLink.target_node_id == source_node_id
                )
            ),
            NetworkLink.link_type == link_type,
            NetworkLink.frequency_mhz == frequency_mhz if frequency_mhz else True
        ).first()
        
        if not link:
            link = NetworkLink(
                source_node_id=source_node_id,
                target_node_id=target_node_id,
                link_type=link_type,
                frequency_mhz=frequency_mhz,
                bandwidth_mhz=bandwidth_mhz,
                status='active',
                metadata={}
            )
            self.db.add(link)
            self.db.flush()
        
        return link
    
    def _calculate_visibility_windows(
        self,
        satellite: Satellite,
        ground_station: GroundStation,
        start_time: datetime,
        end_time: datetime,
        min_elevation_deg: float = 10.0
    ) -> List[Dict]:
        """
        Calculate visibility windows between a satellite and ground station
        
        Note: This is a placeholder implementation. In a real system, this would
        use the orbit predictor to calculate actual visibility windows.
        """
        # Placeholder: Return dummy visibility windows for testing
        # In a real implementation, this would use the orbit predictor
        windows = []
        
        # Simple example: Assume the satellite passes over the ground station every 90 minutes
        # with a visibility window of ~10 minutes
        current_time = start_time
        orbit_period = timedelta(minutes=90)
        visibility_duration = timedelta(minutes=10)
        
        while current_time < end_time:
            window_start = current_time + timedelta(minutes=5)  # Time to next pass
            window_end = window_start + visibility_duration
            
            if window_start < end_time:
                windows.append({
                    'start_time': window_start,
                    'end_time': min(window_end, end_time),
                    'max_elevation': 45.0  # Example max elevation
                })
            
            current_time += orbit_period
        
        return windows
