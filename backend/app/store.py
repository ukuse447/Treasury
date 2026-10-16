"""In-memory store with seed data. Replace with Postgres for production."""
from datetime import date, timedelta
from decimal import Decimal

from .models import (
    Agreement,
    AgreementType,
    CashAccount,
    CollateralKind,
    CollateralPosition,
    ExposureSnapshot,
    MarginCall,
)


class Store:
    def __init__(self) -> None:
        today = date.today()
        self.agreements = {
            a.id: a
            for a in [
                Agreement(id="PB-GS", counterparty="Goldman Sachs PB", threshold=Decimal("1000000"), minimum_transfer_amount=Decimal("250000")),
                Agreement(id="PB-MS", counterparty="Morgan Stanley PB", threshold=Decimal(0), minimum_transfer_amount=Decimal("500000")),
                Agreement(id="OTC-JPM", counterparty="JPMorgan OTC", agreement_type=AgreementType.OTC, threshold=Decimal(0), minimum_transfer_amount=Decimal("500000")),
                Agreement(id="PBFI-BARC", counterparty="Barclays PBFI", agreement_type=AgreementType.PBFI, threshold=Decimal(0), minimum_transfer_amount=Decimal("500000")),
            ]
        }
        self.positions = {
            p.id: p
            for p in [
                CollateralPosition(id="C1", agreement_id="PB-GS", asset="US Treasury 10Y", market_value=Decimal("12000000"), haircut=Decimal("0.02")),
                CollateralPosition(id="C2", agreement_id="PB-MS", asset="Cash USD", market_value=Decimal("5000000"), kind=CollateralKind.CASH),
                CollateralPosition(id="C3", agreement_id="OTC-JPM", asset="Cash USD", market_value=Decimal("3000000"), posted=False, kind=CollateralKind.CASH),
                CollateralPosition(id="C4", agreement_id="PBFI-BARC", asset="Cash USD", market_value=Decimal("1000000"), kind=CollateralKind.CASH),
            ]
        }
        self.exposures = {
            e.agreement_id: e
            for e in [
                ExposureSnapshot(agreement_id="PB-GS", mark_to_market=Decimal("-14500000")),
                ExposureSnapshot(agreement_id="PB-MS", mark_to_market=Decimal("-4800000")),
                ExposureSnapshot(agreement_id="OTC-JPM", mark_to_market=Decimal("3000000")),
                ExposureSnapshot(agreement_id="PBFI-BARC", mark_to_market=Decimal("-1200000")),
            ]
        }
        self.cash_accounts = [
            CashAccount(id="BNY-OPS", name="BNY Operating USD", entity="Fund LP", balance=Decimal("40000000")),
            CashAccount(id="BNY-MRG", name="BNY Margin Cash USD", entity="Fund LP", balance=Decimal("25000000"), restricted=Decimal("3000000")),
        ]
        self.calls: dict[str, MarginCall] = {}
        self._seq = 0
        self._today = today
        self._due = today + timedelta(days=1)

    def next_call_id(self) -> str:
        self._seq += 1
        return f"MC-{self._seq:05d}"
