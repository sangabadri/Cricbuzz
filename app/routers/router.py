from fastapi import APIRouter

from app.routers import players, teams, matches, squads, deliveries, scorecards

router = APIRouter(prefix="/api/v1")

router.include_router(players.router)
router.include_router(teams.router)
router.include_router(matches.router)
router.include_router(squads.router)
router.include_router(deliveries.router)
router.include_router(scorecards.router)