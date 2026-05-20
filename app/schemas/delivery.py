from pydantic import BaseModel, Field, model_validator

from app.models.enums import ExtraType, WicketType
from app.schemas.common import ORMModel


class RecordDeliveryRequest(BaseModel):
    over_number: int = Field(ge=0, description="0-based over index in the innings.")
    delivery_in_over: int = Field(
        ge=1,
        description="1-based physical delivery slot within the over (legal or extra).",
    )
    striker_id: int
    non_striker_id: int
    bowler_id: int
    runs_off_bat: int = Field(ge=0, default=0)
    extra_type: ExtraType | None = None
    extra_runs: int = Field(ge=0, default=0)
    wicket_type: WicketType | None = None
    dismissed_player_id: int | None = None
    fielder_id: int | None = None

    @model_validator(mode="after")
    def validate_scoring(self) -> "RecordDeliveryRequest":
        if self.striker_id == self.non_striker_id:
            raise ValueError("striker_id and non_striker_id must differ")

        if self.extra_type in (ExtraType.WIDE, ExtraType.NO_BALL) and self.extra_runs < 1:
            raise ValueError("wide and no_ball require extra_runs >= 1")

        if self.extra_type is None and self.extra_runs > 0:
            raise ValueError("extra_runs requires extra_type")

        if self.wicket_type and not self.dismissed_player_id:
            raise ValueError("dismissed_player_id is required when wicket_type is set")

        if not self.wicket_type and self.dismissed_player_id:
            raise ValueError("wicket_type is required when dismissed_player_id is set")

        if self.wicket_type in (WicketType.CAUGHT, WicketType.RUN_OUT) and not self.fielder_id:
            if self.wicket_type == WicketType.CAUGHT:
                raise ValueError("fielder_id is required for caught dismissals")

        return self


class InningsStateResponse(BaseModel):
    id: int
    status: str
    total_runs: int
    total_wickets: int
    legal_balls_bowled: int
    overs_display: str
    is_innings_complete: bool
    target_runs: int | None


class DeliveryResponse(ORMModel):
    id: int
    innings_id: int
    sequence_number: int
    over_number: int
    delivery_in_over: int
    legal_ball_in_over: int | None
    is_legal_delivery: bool
    striker_id: int
    non_striker_id: int
    bowler_id: int
    runs_off_bat: int
    extra_type: ExtraType | None
    extra_runs: int
    wicket_type: WicketType | None
    dismissed_player_id: int | None
    fielder_id: int | None


class RecordDeliveryResponse(BaseModel):
    delivery: DeliveryResponse
    innings: InningsStateResponse
    match_status: str
    match_result_summary: str | None = None
    innings_ended: bool = False
    match_ended: bool = False
