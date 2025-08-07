from abc import ABC, abstractmethod
from typing import List, Optional, TypeVar, Generic, Type, Any
from datetime import datetime
from sqlalchemy.orm import Session
from pydantic import BaseModel

from .models import Base

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)

class BaseRepository(Generic[ModelType, CreateSchemaType, UpdateSchemaType], ABC):
    """Base repository interface with common CRUD operations"""
    
    def __init__(self, model: Type[ModelType], db: Session):
        self.model = model
        self.db = db
    
    def get(self, id: Any) -> Optional[ModelType]:
        return self.db.query(self.model).filter(self.model.id == id).first()
    
    def get_multi(self, *, skip: int = 0, limit: int = 100) -> List[ModelType]:
        return self.db.query(self.model).offset(skip).limit(limit).all()
    
    def create(self, obj_in: CreateSchemaType) -> ModelType:
        db_obj = self.model(**obj_in.dict())  # type: ignore
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj
    
    def update(self, db_obj: ModelType, obj_in: UpdateSchemaType) -> ModelType:
        obj_data = obj_in.dict(exclude_unset=True)
        for field, value in obj_data.items():
            setattr(db_obj, field, value)
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj
    
    def delete(self, id: int) -> ModelType:
        obj = self.db.query(self.model).get(id)
        self.db.delete(obj)
        self.db.commit()
        return obj

class SatelliteRepository(BaseRepository):
    """Repository for satellite operations"""
    
    def get_by_norad_id(self, norad_id: str) -> Optional[ModelType]:
        return self.db.query(self.model).filter(self.model.norad_id == norad_id).first()
    
    def get_by_tle_epoch_range(self, start: datetime, end: datetime) -> List[ModelType]:
        return self.db.query(self.model).filter(
            self.model.tle_epoch.between(start, end)
        ).all()

class GroundStationRepository(BaseRepository):
    """Repository for ground station operations"""
    
    def get_by_location(self, latitude: float, longitude: float, tolerance: float = 0.1) -> List[ModelType]:
        return self.db.query(self.model).filter(
            (self.model.latitude.between(latitude - tolerance, latitude + tolerance)) &
            (self.model.longitude.between(longitude - tolerance, longitude + tolerance))
        ).all()

class LinkBudgetProfileRepository(BaseRepository):
    """Repository for link budget profile operations"""
    
    def get_by_frequency_range(self, min_freq: float, max_freq: float) -> List[ModelType]:
        return self.db.query(self.model).filter(
            self.model.frequency_ghz.between(min_freq, max_freq)
        ).all()

# Repository factory
def get_repository(
    model_type: str, 
    db: Session
) -> BaseRepository:
    """Factory function to get the appropriate repository"""
    from .models import Satellite, GroundStation, LinkBudgetProfile
    
    repositories = {
        'satellite': SatelliteRepository,
        'ground_station': GroundStationRepository,
        'link_budget_profile': LinkBudgetProfileRepository,
    }
    
    model_map = {
        'satellite': Satellite,
        'ground_station': GroundStation,
        'link_budget_profile': LinkBudgetProfile,
    }
    
    if model_type not in repositories:
        raise ValueError(f"Unknown model type: {model_type}")
        
    return repositories[model_type](model_map[model_type], db)
