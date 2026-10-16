from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from .models import Agreement, CallDirection, CollateralPosition


def collateral_balance(positions: list[CollateralPosition]) -> Decimal:
    """Net collateral held, haircut-adjusted. Posted by fund is positive."""
    return sum(
        (p.collateral_value if p.posted else -p.collateral_value for p in positions),
        Decimal(0),
    )


def required_collateral(agreement: Agreement, mark_to_market: Decimal) -> Decimal:
    """Collateral the fund should have posted (negative: counterparty should post)."""
    owed_by_fund = -mark_to_market + agreement.independent_amount
    if owed_by_fund >= 0:
        return max(Decimal(0), owed_by_fund - agreement.threshold)
    return min(Decimal(0), owed_by_fund + agreement.threshold)


def required_call(
    agreement: Agreement, mark_to_market: Decimal, positions: list[CollateralPosition]
) -> tuple[CallDirection, Decimal] | None:
    """Compute the margin call implied by current exposure.

    mark_to_market < 0 means the fund owes the counterparty, so the fund posts
    (incoming call). > 0 means the counterparty owes the fund (outgoing call).
    Returns None when the delta is below the minimum transfer amount.
    """
    delta = required_collateral(agreement, mark_to_market) - collateral_balance(positions)
    if abs(delta) < agreement.minimum_transfer_amount or delta == 0:
        return None
    direction = CallDirection.INCOMING if delta > 0 else CallDirection.OUTGOING
    return direction, abs(delta)


class ExcessDeficitStatus(str, Enum):
    EXCESS = "excess"
    DEFICIT = "deficit"
    DEFICIT_BELOW_MTA = "deficit_below_mta"


@dataclass(frozen=True)
class ExcessDeficit:
    value: Decimal  # positive = excess, negative = deficit
    status: ExcessDeficitStatus
    posting_required: bool


def excess_deficit(
    agreement: Agreement, mark_to_market: Decimal, positions: list[CollateralPosition]
) -> ExcessDeficit:
    """Excess/Deficit per docs/SPEC.md M1.5, from the fund's point of view.

    MtM > 0: excess (counterparty owes the fund), no posting.
    MtM <= 0: cover = MtM + collateral posted. cover > 0 is an excess; otherwise a
    deficit equal to cover. A deficit below the MTA does not require posting.
    Threshold and independent amount are not applied (open question in the spec).
    """
    if mark_to_market > 0:
        return ExcessDeficit(mark_to_market, ExcessDeficitStatus.EXCESS, False)
    cover = mark_to_market + collateral_balance(positions)
    if cover >= 0:
        return ExcessDeficit(cover, ExcessDeficitStatus.EXCESS, False)
    if -cover < agreement.minimum_transfer_amount:
        return ExcessDeficit(cover, ExcessDeficitStatus.DEFICIT_BELOW_MTA, False)
    return ExcessDeficit(cover, ExcessDeficitStatus.DEFICIT, True)
