from fastapi import APIRouter
from api.v1.endpoints import passes, margin, export
from api.v1.endpoints import public_config, tle as tle_ep, schedule
from api.v1.endpoints import horizon as horizon_ep

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(passes.router, prefix="/passes", tags=["passes"])
api_router.include_router(margin.router, prefix="/margin", tags=["margin"])
api_router.include_router(export.router, prefix="/export", tags=["export"])
api_router.include_router(public_config.router, prefix="/config", tags=["config"])  # /api/v1/config/public
api_router.include_router(tle_ep.router, prefix="/tle", tags=["tle"])  # /api/v1/tle/{id}
api_router.include_router(schedule.router, prefix="/schedule", tags=["schedule"])  # /api/v1/schedule
api_router.include_router(horizon_ep.router, prefix="/horizon", tags=["horizon"])  # /api/v1/horizon
