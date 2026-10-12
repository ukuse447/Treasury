from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import app
from app.margin import collateral_balance, required_call
from app.models import Agreement, CallDirection, CollateralPosition

AGR = Agreement(id="A", counterparty="X", threshold=Decimal(1_000_000), minimum_transfer_amount=Decimal(250_000))


def pos(value, haircut="0", posted=True):
    return CollateralPosition(id="p", agreement_id="A", asset="cash", market_value=Decimal(value), haircut=Decimal(haircut), posted=posted)


def test_haircut_reduces_collateral_value():
    assert collateral_balance([pos(1_000_000, "0.02")]) == Decimal(980_000)


def test_fund_must_post_when_owing_above_threshold():
    direction, amount = required_call(AGR, Decimal(-5_000_000), [pos(2_000_000)])
    assert direction == CallDirection.INCOMING
    assert amount == Decimal(2_000_000)  # needs 4M (5M - 1M threshold), has 2M


def test_below_minimum_transfer_returns_none():
    assert required_call(AGR, Decimal(-5_000_000), [pos(3_900_000)]) is None


def test_fund_gets_return_when_overcollateralised():
    direction, amount = required_call(AGR, Decimal(-2_000_000), [pos(4_000_000)])
    assert direction == CallDirection.OUTGOING
    assert amount == Decimal(3_000_000)


def test_api_generate_calls():
    client = TestClient(app)
    assert client.get("/health").json() == {"status": "ok"}
    calls = client.post("/calls/generate").json()
    assert len(calls) >= 1
    assert client.get("/calls").json()
