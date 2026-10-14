from decimal import Decimal

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
