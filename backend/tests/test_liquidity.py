from decimal import Decimal

from fastapi.testclient import TestClient

from app.liquidity import build_dashboard
from app.main import app
from app.margin import ExcessDeficitStatus, excess_deficit
from app.models import Agreement, CashAccount, CollateralKind, CollateralPosition, ExposureSnapshot
from app.store import Store

D = Decimal
AGR = Agreement(id="A", counterparty="X", minimum_transfer_amount=D(500_000))


def pos(value, posted=True, kind=CollateralKind.CASH, haircut="0"):
    return CollateralPosition(id="p", agreement_id="A", asset="x", market_value=D(value), posted=posted, kind=kind, haircut=D(haircut))


def test_positive_mtm_is_excess_no_posting():
    r = excess_deficit(AGR, D(3_000_000), [])
    assert (r.value, r.status, r.posting_required) == (D(3_000_000), ExcessDeficitStatus.EXCESS, False)


def test_negative_mtm_covered_by_collateral_is_excess():
    r = excess_deficit(AGR, D(-4_800_000), [pos(5_000_000)])
    assert (r.value, r.status, r.posting_required) == (D(200_000), ExcessDeficitStatus.EXCESS, False)


def test_deficit_at_or_above_mta_requires_posting():
    r = excess_deficit(AGR, D(-5_000_000), [pos(4_000_000)])
    assert (r.value, r.status, r.posting_required) == (D(-1_000_000), ExcessDeficitStatus.DEFICIT, True)


def test_deficit_below_mta_does_not_require_posting():
    r = excess_deficit(AGR, D(-1_200_000), [pos(1_000_000)])
    assert (r.value, r.status, r.posting_required) == (D(-200_000), ExcessDeficitStatus.DEFICIT_BELOW_MTA, False)


def test_collateral_received_counts_against_cover():
    r = excess_deficit(AGR, D(-1_000_000), [pos(2_000_000, posted=False)])
    assert r.value == D(-3_000_000) and r.posting_required


def test_dashboard_seed_data_matches_hand_calculation():
    s = Store()
    d = build_dashboard(s.agreements, list(s.positions.values()), s.exposures, s.cash_accounts)
    t = d["tiles"]
    assert t["total_cash"] == D(65_000_000)
    assert t["unencumbered_cash"] == D(62_000_000)  # 65M less 3M restricted
    assert t["cash_posted_as_collateral"] == D(6_000_000)  # 5M (MS) + 1M (Barclays); 3M received excluded
    assert t["margin_calls_count"] == 1
    assert t["margin_calls_total"] == D("2740000")  # GS: -14.5M + 11.76M
    assert [r["agreement_id"] for r in d["impact"]] == ["PB-GS", "PBFI-BARC", "PB-MS", "OTC-JPM"]
    by_type = {r["agreement_type"]: r for r in d["asset_liability"]}
    assert by_type["PB"]["assets"] == D(200_000) and by_type["PB"]["liabilities"] == D("2740000")
    assert by_type["PB"]["net"] == D("-2540000")
    assert by_type["OTC"]["net"] == D(3_000_000)
    assert by_type["PBFI"]["liabilities"] == D(200_000)


def test_dashboard_skips_agreements_without_exposure_and_handles_no_cash():
    d = build_dashboard({"A": AGR}, [], {}, [])
    assert d["impact"] == [] and d["tiles"]["total_cash"] == 0


def test_dashboard_endpoint():
    r = TestClient(app).get("/liquidity/dashboard")
    assert r.status_code == 200
    assert {"tiles", "impact", "asset_liability", "cash_accounts"} <= r.json().keys()
