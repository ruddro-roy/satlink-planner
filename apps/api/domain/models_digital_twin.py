"""Enhanced models for Digital Twin Satellite Operations"""
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional, Dict, Any
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Table, Boolean, JSON, Enum as SQLEnum, Text, Index
from sqlalchemy.orm import relationship, Mapped, mapped_column
from core.db import Base

# Association tables
class TLESource(str, Enum):
    SPACE_TRACK = "space_track"
    CELESTRAK = "celestrak"
    MANUAL = "manual"
    OTHER = "other"

class TLEAccuracy(str, Enum):
    HIGH = "high"       # < 1km position error
    MEDIUM = "medium"   # 1-5km position error
    LOW = "low"         # > 5km position error

class TLE(Base):
    """Enhanced TLE model with source tracking and accuracy metrics"""
    __tablename__ = 'tle_history'
    
    id = Column(Integer, primary_key=True, index=True)
    satellite_id = Column(Integer, ForeignKey('satellites.id'), nullable=False)
    tle_line1 = Column(String, nullable=False)
    tle_line2 = Column(String, nullable=False)
    tle_epoch = Column(DateTime, nullable=False)
    source = Column(SQLEnum(TLESource), nullable=False, default=TLESource.MANUAL)
    accuracy = Column(SQLEnum(TLEAccuracy), nullable=True)
    position_error_km = Column(Float, nullable=True)  # Estimated position error in km
    is_current = Column(Boolean, default=False, index=True)
    metadata_ = Column('metadata', JSON, default={})  # Raw response from source, etc.
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    satellite = relationship("Satellite", back_populates="tle_history")
    
    __table_args__ = (
        Index('idx_tle_satellite_epoch', 'satellite_id', 'tle_epoch', unique=True),
    )

class COLAStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

class CollisionRiskAssessment(Base):
    """Collision On Launch Assessment (COLA) results"""
    __tablename__ = 'collision_risk_assessments'
    
    id = Column(Integer, primary_key=True, index=True)
    satellite_id = Column(Integer, ForeignKey('satellites.id'), nullable=False)
    assessment_time = Column(DateTime, default=datetime.utcnow, index=True)
    assessment_window_hours = Column(Integer, default=72)  # Assessment window in hours
    status = Column(SQLEnum(COLAStatus), default=COLAStatus.PENDING, index=True)
    risk_score = Column(Float, nullable=True)  # 0-1 scale
    closest_approach_km = Column(Float, nullable=True)
    closest_approach_time = Column(DateTime, nullable=True)
    objects_at_risk = Column(JSON, default=[])  # List of NORAD IDs with close approaches
    metadata_ = Column('metadata', JSON, default={})  # Raw assessment data
    
    # Relationships
    satellite = relationship("Satellite", back_populates="collision_assessments")

class FrequencyAllocation(Base):
    """Frequency coordination and allocation records"""
    __tablename__ = 'frequency_allocations'
    
    id = Column(Integer, primary_key=True, index=True)
    satellite_id = Column(Integer, ForeignKey('satellites.id'), nullable=False)
    frequency_mhz = Column(Float, nullable=False)
    bandwidth_mhz = Column(Float, nullable=False)
    service = Column(String)  # e.g., "Earth exploration-satellite", "Fixed", "Mobile"
    itu_region = Column(String)  # 1, 2, or 3
    status = Column(String)  # "coordinated", "pending", "not_required"
    coordination_notes = Column(Text)
    valid_from = Column(DateTime)
    valid_until = Column(DateTime)
    metadata_ = Column('metadata', JSON, default={})  # ITU filing references, etc.
    
    # Relationships
    satellite = relationship("Satellite", back_populates="frequency_allocations")
    
    __table_args__ = (
        Index('idx_freq_alloc_satellite_band', 'satellite_id', 'frequency_mhz', 'bandwidth_mhz'),
    )

class NetworkNodeType(str, Enum):
    SATELLITE = "satellite"
    GROUND_STATION = "ground_station"
    GATEWAY = "gateway"
    RELAY = "relay"
    USER_TERMINAL = "user_terminal"

class NetworkNode(Base):
    """Network topology nodes"""
    __tablename__ = 'network_nodes'
    
    id = Column(Integer, primary_key=True, index=True)
    node_id = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    node_type = Column(SQLEnum(NetworkNodeType), nullable=False)
    description = Column(Text)
    location = Column(JSON)  # {lat, lon, alt} or {orbit_params} for satellites
    capabilities = Column(JSON, default={})  # Frequency bands, protocols, etc.
    status = Column(String, default="active")  # active, maintenance, disabled
    metadata_ = Column('metadata', JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    links = relationship("NetworkLink", 
                        primaryjoin="or_(NetworkNode.id==NetworkLink.source_node_id, "
                                    "NetworkNode.id==NetworkLink.target_node_id)")

class NetworkLink(Base):
    """Network topology links between nodes"""
    __tablename__ = 'network_links'
    
    id = Column(Integer, primary_key=True, index=True)
    source_node_id = Column(Integer, ForeignKey('network_nodes.id'), nullable=False)
    target_node_id = Column(Integer, ForeignKey('network_nodes.id'), nullable=False)
    link_type = Column(String)  # RF, optical, ground, inter-satellite, etc.
    frequency_mhz = Column(Float, nullable=True)
    bandwidth_mhz = Column(Float, nullable=True)
    max_data_rate_mbps = Column(Float, nullable=True)
    status = Column(String, default="active")  # active, degraded, down
    metadata_ = Column('metadata', JSON, default={})  # Protocol details, modulation, etc.
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    source_node = relationship("NetworkNode", foreign_keys=[source_node_id])
    target_node = relationship("NetworkNode", foreign_keys=[target_node_id])
    handovers = relationship("HandoverSchedule", back_populates="link")
    
    __table_args__ = (
        Index('idx_network_link_nodes', 'source_node_id', 'target_node_id'),
    )

class HandoverSchedule(Base):
    """Scheduled handovers between network links"""
    __tablename__ = 'handover_schedules'
    
    id = Column(Integer, primary_key=True, index=True)
    link_id = Column(Integer, ForeignKey('network_links.id'), nullable=False)
    satellite_id = Column(Integer, ForeignKey('satellites.id'), nullable=False)
    ground_station_id = Column(Integer, ForeignKey('ground_stations.id'), nullable=False)
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime, nullable=False, index=True)
    status = Column(String, default="scheduled")  # scheduled, in_progress, completed, failed
    handover_type = Column(String)  # hard, soft, make-before-break, etc.
    metadata_ = Column('metadata', JSON, default={})  # Handover parameters, metrics
    
    # Relationships
    link = relationship("NetworkLink", back_populates="handovers")
    satellite = relationship("Satellite")
    ground_station = relationship("GroundStation")
    
    __table_args__ = (
        Index('idx_handover_times', 'start_time', 'end_time'),
        Index('idx_handover_sat_gs', 'satellite_id', 'ground_station_id'),
    )

class AnomalyType(str, Enum):
    TLE_AGING = "tle_aging"
    COLLISION_RISK = "collision_risk"
    LINK_MARGIN = "link_margin"
    SYSTEM_HEALTH = "system_health"
    DATA_QUALITY = "data_quality"
    OPERATIONAL = "operational"

class AnomalySeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

class AnomalyStatus(str, Enum):
    DETECTED = "detected"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    FALSE_POSITIVE = "false_positive"

class AnomalyDetection(Base):
    """Detected anomalies and their status"""
    __tablename__ = 'anomaly_detections'
    
    id = Column(Integer, primary_key=True, index=True)
    anomaly_type = Column(SQLEnum(AnomalyType), nullable=False, index=True)
    severity = Column(SQLEnum(AnomalySeverity), nullable=False, index=True)
    status = Column(SQLEnum(AnomalyStatus), default=AnomalyStatus.DETECTED, index=True)
    title = Column(String, nullable=False)
    description = Column(Text)
    detected_at = Column(DateTime, default=datetime.utcnow, index=True)
    resolved_at = Column(DateTime, nullable=True)
    
    # Associated resources
    satellite_id = Column(Integer, ForeignKey('satellites.id'), nullable=True)
    ground_station_id = Column(Integer, ForeignKey('ground_stations.id'), nullable=True)
    link_id = Column(Integer, ForeignKey('network_links.id'), nullable=True)
    
    # AI/ML metadata
    confidence_score = Column(Float, nullable=True)  # 0-1 confidence in detection
    features = Column(JSON, default={})  # Features used for detection
    metadata_ = Column('metadata', JSON, default={})  # Raw data, model info, etc.
    
    # Relationships
    satellite = relationship("Satellite")
    ground_station = relationship("GroundStation")
    link = relationship("NetworkLink")
    responses = relationship("AnomalyResponse", back_populates="anomaly")

class AnomalyResponse(Base):
    """Recommended and executed responses to anomalies"""
    __tablename__ = 'anomaly_responses'
    
    id = Column(Integer, primary_key=True, index=True)
    anomaly_id = Column(Integer, ForeignKey('anomaly_detections.id'), nullable=False)
    response_type = Column(String, nullable=False)  # automated, manual, ai_suggested
    action = Column(String, nullable=False)  # Short action description
    description = Column(Text)  # Detailed description of the response
    status = Column(String, default="pending")  # pending, in_progress, completed, failed
    executed_at = Column(DateTime, nullable=True)
    executed_by = Column(String, nullable=True)  # User or system that executed the response
    result = Column(Text)  # Result of the response action
    metadata_ = Column('metadata', JSON, default={})  # Additional response data
    
    # Relationships
    anomaly = relationship("AnomalyDetection", back_populates="responses")

# Add relationships to existing models
from .models import Satellite, GroundStation

# Add relationships to Satellite model
setattr(Satellite, 'tle_history', relationship("TLE", back_populates="satellite", order_by="TLE.tle_epoch.desc()"))
setattr(Satellite, 'collision_assessments', relationship("CollisionRiskAssessment", back_populates="satellite", order_by="CollisionRiskAssessment.assessment_time.desc()"))
setattr(Satellite, 'frequency_allocations', relationship("FrequencyAllocation", back_populates="satellite"))

# Add relationships to GroundStation model if needed
# setattr(GroundStation, 'frequency_allocations', relationship("FrequencyAllocation", back_populates="ground_station"))
