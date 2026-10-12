from datetime import date
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field


class CallDirection(str, Enum):
    INCOMING = "incoming"  # counterparty calls the fund
    OUTGOING = "outgoing"  # fund calls the counterparty


class CallStatus(str, Enum):
    PENDING = "pending"
    AGREED = "agreed"
    DISPUTED = "disputed"
    SETTLED = "settled"


class Agreement(BaseModel):
    """Simplified CSA / margin agreement with a counterparty."""

    id: str
    counterparty: str
    currency: str = "USD"
    threshold: Decimal = Decimal(0)
    minimum_transfer_amount: Decimal = Decimal(0)
    independent_amount: Decimal = Decimal(0)


class CollateralPosition(BaseModel):
    id: str
    agreement_id: str
    asset: str
    market_value: Decimal
    haircut: Decimal = Field(default=Decimal(0), ge=0, le=1)
    posted: bool = True  # True = posted by fund, False = received

    @property
    def collateral_value(self) -> Decimal:
        return self.market_value * (1 - self.haircut)


class MarginCall(BaseModel):
    id: str
    agreement_id: str
    direction: CallDirection
    amount: Decimal
    currency: str
    due_date: date
    status: CallStatus = CallStatus.PENDING


class ExposureSnapshot(BaseModel):
    agreement_id: str
    mark_to_market: Decimal  # positive = counterparty owes fund
