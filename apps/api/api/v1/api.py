from fastapi import APIRouter
from api.v1.endpoints import passes, margin, export

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(passes.router, prefix="/passes", tags=["passes"])
api_router.include_router(margin.router, prefix="/margin", tags=["margin"])
api_router.include_router(export.router, prefix="/export", tags=["export"])
