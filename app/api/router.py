from fastapi import APIRouter

from app.api.routes import deliveries, matches, players, stats

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(matches.router, tags=["matches"])
api_router.include_router(players.router, tags=["players"])
api_router.include_router(deliveries.router, tags=["deliveries"])
api_router.include_router(stats.router, tags=["stats"])
