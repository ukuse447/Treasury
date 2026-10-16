"""Liquidity dashboard calculations (docs/SPEC.md section 8)."""
from decimal import Decimal

from .margin import ExcessDeficitStatus, excess_deficit
from .models import (
    Agreement,
    CashAccount,
    CollateralKind,
    CollateralPosition,
    ExposureSnapshot,
)

ZERO = Decimal(0)


def build_dashboard(
    agreements: dict[str, Agreement],
    positions: list[CollateralPosition],
    exposures: dict[str, ExposureSnapshot],
    cash_accounts: list[CashAccount],
) -> dict:
    total_cash = sum((a.balance for a in cash_accounts), ZERO)
    unencumbered = sum((a.balance - a.restricted for a in cash_accounts), ZERO)
    cash_posted = sum(
        (p.market_value for p in positions if p.posted and p.kind == CollateralKind.CASH),
        ZERO,
    )

    rows = []
    for aid, agreement in agreements.items():
        exposure = exposures.get(aid)
        if exposure is None:
            continue
        agreement_positions = [p for p in positions if p.agreement_id == aid]
        ed = excess_deficit(agreement, exposure.mark_to_market, agreement_positions)
        is_asset = ed.status == ExcessDeficitStatus.EXCESS
        rows.append(
            {
                "agreement_id": aid,
                "counterparty": agreement.counterparty,
                "agreement_type": agreement.agreement_type,
                "mark_to_market": exposure.mark_to_market,
                "excess_deficit": ed.value,
                "status": ed.status,
                "posting_required": ed.posting_required,
                "classification": "asset" if is_asset else "liability",
                "cash_impact": -ed.value if ed.posting_required else ZERO,
            }
        )
    rows.sort(key=lambda r: r["excess_deficit"])  # largest deficit first

    by_type: dict[str, dict[str, Decimal]] = {}
    for r in rows:
        t = by_type.setdefault(
            r["agreement_type"].value, {"assets": ZERO, "liabilities": ZERO}
        )
        if r["classification"] == "asset":
            t["assets"] += r["excess_deficit"]
        else:
            t["liabilities"] += -r["excess_deficit"]
    asset_liability = [
        {"agreement_type": k, **v, "net": v["assets"] - v["liabilities"]}
        for k, v in sorted(by_type.items())
    ]

    calls = [r for r in rows if r["posting_required"]]
    return {
        "tiles": {
            "total_cash": total_cash,
            "unencumbered_cash": unencumbered,
            "cash_posted_as_collateral": cash_posted,
            "margin_calls_count": len(calls),
            "margin_calls_total": sum((-r["excess_deficit"] for r in calls), ZERO),
        },
        "impact": rows,
        "asset_liability": asset_liability,
        "cash_accounts": cash_accounts,
    }
