from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Table
from sqlalchemy.orm import relationship
from core.db import Base
from sqlalchemy import JSON


# Association table for many-to-many relationship between satellites and ground stations
satellite_ground_station = Table(
    'satellite_ground_station',
    Base.metadata,
    Column('satellite_id', Integer, ForeignKey('satellites.id')),
    Column('ground_station_id', Integer, ForeignKey('ground_stations.id'))
)

class Satellite(Base):
    """Satellite model for storing TLE and metadata"""
    __tablename__ = 'satellites'
    
    id = Column(Integer, primary_key=True, index=True)
    norad_id = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=True)
    tle_line1 = Column(String, nullable=False)
    tle_line2 = Column(String, nullable=False)
    tle_epoch = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    ground_stations = relationship("GroundStation", secondary=satellite_ground_station, back_populates="satellites")
    
    def __repr__(self):
        return f"<Satellite(norad_id='{self.norad_id}', name='{self.name}')>"

class GroundStation(Base):
    """Ground station model"""
    __tablename__ = 'ground_stations'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    elevation = Column(Float, default=0.0)  # in meters
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    satellites = relationship("Satellite", secondary=satellite_ground_station, back_populates="ground_stations")
    
    def __repr__(self):
        return f"<GroundStation(name='{self.name}', lat={self.latitude}, lon={self.longitude})>"

class LinkBudgetProfile(Base):
    """Link budget configuration profiles"""
    __tablename__ = 'link_budget_profiles'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    frequency_ghz = Column(Float, nullable=False)  # GHz
    bandwidth_mhz = Column(Float, nullable=False)  # MHz
    tx_power_dbm = Column(Float)  # dBm
    tx_antenna_gain_dbi = Column(Float)  # dBi
    rx_antenna_gain_dbi = Column(Float)  # dBi
    system_noise_temp_k = Column(Float)  # Kelvin
    implementation_loss_db = Column(Float, default=0.0)  # dB
    rain_margin_db = Column(Float, default=0.0)  # dB
    other_margins_db = Column(JSON, default={})  # Additional margins
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<LinkBudgetProfile(name='{self.name}', freq={self.frequency_ghz}GHz)>"
