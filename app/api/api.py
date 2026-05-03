from fastapi import APIRouter
from app.api.endpoints import claim, config, kiosk

api_router = APIRouter()
api_router.include_router(claim.router, prefix="/claim", tags=["claim"])
api_router.include_router(config.router, prefix="/config", tags=["config"])
api_router.include_router(kiosk.router, prefix="/kiosk", tags=["kiosk"])
