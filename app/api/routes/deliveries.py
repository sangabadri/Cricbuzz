from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_session
from app.schemas.delivery import RecordDeliveryRequest, RecordDeliveryResponse
from app.services import delivery_service

router = APIRouter()


@router.post(
    "/innings/{innings_id}/deliveries",
    response_model=RecordDeliveryResponse,
    status_code=201,
)
async def record_delivery(
    innings_id: int,
    payload: RecordDeliveryRequest,
    session: AsyncSession = Depends(get_async_session),
) -> RecordDeliveryResponse:
    """Record a ball-by-ball delivery with full scoring-rule validation."""
    return await delivery_service.record_delivery(session, innings_id, payload)
