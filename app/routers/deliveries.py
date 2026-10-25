from fastapi import APIRouter, Depends

from app.schemas.delivery import DeliveryCreate, DeliveryResponse
from app.services.delivery import DeliveryService, get_delivery_service

router = APIRouter(prefix="/matches", tags=["Deliveries"])

@router.post("/{match_id}/innings/{innings_number}/deliveries", response_model=DeliveryResponse)
async def create_delivery(
    match_id: int,
    innings_number: int,
    delivery: DeliveryCreate,
    service: DeliveryService = Depends(get_delivery_service),
):
    return await service.record_delivery(match_id, innings_number, delivery)

@router.put("/{match_id}/innings/{innings_number}/deliveries/last", response_model=DeliveryResponse)
async def modify_last_delivery(
    match_id: int,
    innings_number: int,
    delivery: DeliveryCreate,
    service: DeliveryService = Depends(get_delivery_service),
):
    return await service.update_last_delivery(match_id, innings_number, delivery)

@router.delete("/{match_id}/innings/{innings_number}/deliveries/last", response_model=DeliveryResponse)
async def undo_last_delivery(
    match_id: int,
    innings_number: int,
    service: DeliveryService = Depends(get_delivery_service),
):
    return await service.undo_last_delivery(match_id, innings_number)

@router.get("/{match_id}/innings/{innings_number}/deliveries", response_model=list[DeliveryResponse])
async def get_deliveries(
    match_id: int,
    innings_number: int,
    service: DeliveryService = Depends(get_delivery_service),
):
    return await service.get_innings_deliveries(match_id, innings_number)
