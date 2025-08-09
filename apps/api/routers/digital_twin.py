"""Digital Twin API Router"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import logging

from core.database import get_db
from domain.models import Satellite, GroundStation
from domain.models_digital_twin import (
    NetworkNode, NetworkLink, HandoverSchedule, AnomalyDetection,
    AnomalyType, AnomalySeverity, AnomalyStatus, FrequencyAllocation
)
from services.space_track import SpaceTrackClient, TLEManager as SpaceTrackService
from services.collision_risk import CollisionRiskAnalyzer as CollisionRiskService
from services.frequency import FrequencyCoordinator as FrequencyService
from services.acm import ACMController, ACMProfile
from services.network_planner import NetworkPlanner, LinkBudget

router = APIRouter(prefix="/digital-twin", tags=["digital-twin"])
logger = logging.getLogger(__name__)

# Services that need a database session will be initialized in the endpoint functions
# using dependency injection

@router.get("/tle/update/{norad_id}")
async def update_tle(
    norad_id: str,
    db: Session = Depends(get_db)
):
    """
    Fetch and update TLE data for a satellite from Space-Track.org
    
    Args:
        norad_id: NORAD ID of the satellite
        
    Returns:
        Updated TLE information
    """
    try:
        # Initialize TLEManager with database session
        tle_manager = SpaceTrackService(db)
        tle = tle_manager.update_satellite_tle(int(norad_id))
        if not tle:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Failed to update TLE for NORAD ID {norad_id}"
            )
        return {"status": "success", "data": tle}
    except Exception as e:
        logger.error(f"Failed to update TLE: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update TLE: {str(e)}"
        )

@router.get("/collision-risk/{satellite_id}")
async def get_collision_risk(
    satellite_id: int,
    start_time: datetime = None,
    end_time: datetime = None,
    lookahead_hours: int = 24,
    db: Session = Depends(get_db)
):
    """
    Calculate collision risk for a satellite
    
    Args:
        satellite_id: ID of the satellite
        start_time: Start time for analysis (default: now)
        end_time: End time for analysis (default: start_time + lookahead_hours)
        lookahead_hours: Hours to look ahead if end_time not provided
        
    Returns:
        Collision risk assessment
    """
    if not start_time:
        start_time = datetime.utcnow()
    if not end_time:
        end_time = start_time + timedelta(hours=lookahead_hours)
    
    try:
        # Initialize service with database session
        collision_risk_service = CollisionRiskService(db)
        risk_assessment = collision_risk_service.assess_collision_risk(
            satellite_id, start_time, end_time
        )
        return {"status": "success", "data": risk_assessment}
    except Exception as e:
        logger.error(f"Failed to calculate collision risk: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate collision risk: {str(e)}"
        )

@router.get("/frequency/check")
async def check_frequency(
    frequency_mhz: float,
    bandwidth_mhz: float,
    service_type: str,
    region: str = "GLOBAL",
    db: Session = Depends(get_db)
):
    """
    Check frequency allocation and interference
    
    Args:
        frequency_mhz: Center frequency in MHz
        bandwidth_mhz: Bandwidth in MHz
        service_type: Type of service (e.g., 'FSS', 'BSS', 'MSS')
        region: ITU region (1, 2, 3 or 'GLOBAL')
        
    Returns:
        Frequency allocation and interference information
    """
    try:
        # Initialize service with database session
        frequency_service = FrequencyService(db)
        result = frequency_service.check_frequency_allocation(
            frequency_mhz, bandwidth_mhz, service_type, region
        )
        return {"status": "success", "data": result}
    except Exception as e:
        logger.error(f"Frequency check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Frequency check failed: {str(e)}"
        )

@router.post("/acm/select-profile")
async def select_acm_profile(
    cn0: float,
    bandwidth_hz: float,
    target_ber: float = 1e-6,
    margin_db: float = 3.0
):
    """
    Select the best ACM profile based on current C/N0
    
    Args:
        cn0: Carrier-to-noise density ratio in dB-Hz
        bandwidth_hz: Channel bandwidth in Hz
        target_ber: Target bit error rate (default: 1e-6)
        margin_db: Additional margin in dB (default: 3.0)
        
    Returns:
        Selected ACM profile and data rate information
    """
    try:
        acm = ACMController()
        profile, metrics = acm.select_best_profile(cn0, target_ber, margin_db)
        data_rate_info = acm.get_available_data_rate(bandwidth_hz, cn0, target_ber, margin_db)
        
        return {
            "status": "success",
            "data": {
                "profile": {
                    "name": profile.name,
                    "modulation": profile.modulation,
                    "code_rate": profile.code_rate,
                    "spectral_efficiency": profile.spectral_efficiency,
                    "required_cn0": profile.required_cn0
                },
                "data_rate_info": data_rate_info,
                "metrics": metrics
            }
        }
    except Exception as e:
        logger.error(f"ACM profile selection failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"ACM profile selection failed: {str(e)}"
        )

@router.post("/network/plan-handovers")
async def plan_handovers(
    satellite_id: int,
    start_time: datetime,
    end_time: datetime,
    min_elevation_deg: float = 10.0,
    min_handover_time_sec: int = 30,
    max_handover_time_sec: int = 300,
    link_type: str = "RF",
    frequency_mhz: float = None,
    bandwidth_mhz: float = None,
    db: Session = Depends(get_db)
):
    """
    Plan optimal handovers for a satellite pass over multiple ground stations
    
    Args:
        satellite_id: ID of the satellite
        start_time: Start time for handover planning
        end_time: End time for handover planning
        min_elevation_deg: Minimum elevation angle (degrees)
        min_handover_time_sec: Minimum time per ground station (seconds)
        max_handover_time_sec: Maximum time per ground station (seconds)
        link_type: Type of link (RF, optical, etc.)
        frequency_mhz: Center frequency in MHz (optional)
        bandwidth_mhz: Bandwidth in MHz (optional)
        
    Returns:
        List of scheduled handovers
    """
    try:
        planner = NetworkPlanner(db)
        handovers = planner.plan_handovers(
            satellite_id=satellite_id,
            start_time=start_time,
            end_time=end_time,
            min_elevation_deg=min_elevation_deg,
            min_handover_time_sec=min_handover_time_sec,
            max_handover_time_sec=max_handover_time_sec,
            link_type=link_type,
            frequency_mhz=frequency_mhz,
            bandwidth_mhz=bandwidth_mhz
        )
        
        return {"status": "success", "data": handovers}
    except Exception as e:
        logger.error(f"Handover planning failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Handover planning failed: {str(e)}"
        )

@router.get("/anomalies")
async def get_anomalies(
    satellite_id: int = None,
    ground_station_id: int = None,
    anomaly_type: str = None,
    severity: str = None,
    status: str = None,
    start_time: datetime = None,
    end_time: datetime = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Retrieve anomaly detections with filtering options
    
    Args:
        satellite_id: Filter by satellite ID
        ground_station_id: Filter by ground station ID
        anomaly_type: Filter by anomaly type
        severity: Filter by severity level
        status: Filter by status
        start_time: Filter by anomaly detection time (after)
        end_time: Filter by anomaly detection time (before)
        limit: Maximum number of results to return
        
    Returns:
        List of anomaly detections matching the filters
    """
    try:
        query = db.query(AnomalyDetection)
        
        if satellite_id is not None:
            query = query.filter(AnomalyDetection.satellite_id == satellite_id)
        if ground_station_id is not None:
            query = query.filter(AnomalyDetection.ground_station_id == ground_station_id)
        if anomaly_type is not None:
            query = query.filter(AnomalyDetection.anomaly_type == anomaly_type)
        if severity is not None:
            query = query.filter(AnomalyDetection.severity == severity)
        if status is not None:
            query = query.filter(AnomalyDetection.status == status)
        if start_time is not None:
            query = query.filter(AnomalyDetection.detected_at >= start_time)
        if end_time is not None:
            query = query.filter(AnomalyDetection.detected_at <= end_time)
            
        anomalies = query.order_by(AnomalyDetection.detected_at.desc()).limit(limit).all()
        
        return {
            "status": "success",
            "data": [
                {
                    "id": a.id,
                    "satellite_id": a.satellite_id,
                    "ground_station_id": a.ground_station_id,
                    "anomaly_type": a.anomaly_type,
                    "severity": a.severity,
                    "status": a.status,
                    "detected_at": a.detected_at.isoformat(),
                    "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
                    "description": a.description,
                    "metadata": a.metadata
                }
                for a in anomalies
            ]
        }
    except Exception as e:
        logger.error(f"Failed to retrieve anomalies: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve anomalies: {str(e)}"
        )

@router.post("/network/nodes")
async def create_network_node(
    node_id: str,
    name: str,
    node_type: str,
    lat: float = None,
    lon: float = None,
    alt: float = 0.0,
    capabilities: dict = None,
    status: str = "active",
    db: Session = Depends(get_db)
):
    """
    Create a new network node
    
    Args:
        node_id: Unique node identifier
        name: Display name
        node_type: Type of node (satellite, ground_station, gateway, etc.)
        lat: Latitude (for ground-based nodes)
        lon: Longitude (for ground-based nodes)
        alt: Altitude in meters (for ground-based nodes)
        capabilities: Dictionary of node capabilities
        status: Node status (active, inactive, maintenance)
        
    Returns:
        Created node information
    """
    try:
        planner = NetworkPlanner(db)
        location = None
        if lat is not None and lon is not None:
            location = {"lat": lat, "lon": lon, "alt": alt}
            
        node = NetworkNode(
            node_id=node_id,
            name=name,
            node_type=node_type,
            location=location,
            capabilities=capabilities or {},
            status=status
        )
        
        db.add(node)
        db.commit()
        db.refresh(node)
        
        return {
            "status": "success",
            "data": {
                "id": node.id,
                "node_id": node.node_id,
                "name": node.name,
                "node_type": node.node_type,
                "location": node.location,
                "capabilities": node.capabilities,
                "status": node.status,
                "created_at": node.created_at.isoformat(),
                "updated_at": node.updated_at.isoformat()
            }
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create network node: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create network node: {str(e)}"
        )

@router.get("/network/nodes")
async def list_network_nodes(
    node_type: str = None,
    status: str = None,
    db: Session = Depends(get_db)
):
    """
    List all network nodes with optional filtering
    
    Args:
        node_type: Filter by node type
        status: Filter by status
        
    Returns:
        List of network nodes
    """
    try:
        query = db.query(NetworkNode)
        
        if node_type is not None:
            query = query.filter(NetworkNode.node_type == node_type)
        if status is not None:
            query = query.filter(NetworkNode.status == status)
            
        nodes = query.all()
        
        return {
            "status": "success",
            "data": [
                {
                    "id": n.id,
                    "node_id": n.node_id,
                    "name": n.name,
                    "node_type": n.node_type,
                    "location": n.location,
                    "capabilities": n.capabilities,
                    "status": n.status,
                    "created_at": n.created_at.isoformat(),
                    "updated_at": n.updated_at.isoformat()
                }
                for n in nodes
            ]
        }
    except Exception as e:
        logger.error(f"Failed to list network nodes: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list network nodes: {str(e)}"
        )
