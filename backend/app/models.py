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


class AgreementType(str, Enum):
    PB = "PB"
    OTC = "OTC"
    PBFI = "PBFI"
    MNA = "MNA"


class CollateralKind(str, Enum):
    CASH = "cash"
    SECURITY = "security"


class Agreement(BaseModel):
    """Simplified CSA / margin agreement with a counterparty."""

    id: str
    counterparty: str
    agreement_type: AgreementType = AgreementType.PB
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
    kind: CollateralKind = CollateralKind.SECURITY

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


class CashAccount(BaseModel):
    """Cash account held at the custodian bank (BNY). USD only in this version."""

    id: str
    name: str
    bank: str = "BNY"
    entity: str
    balance: Decimal
    restricted: Decimal = Decimal(0)  # restricted or earmarked, not available
