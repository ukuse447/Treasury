from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import liquidity, margin
from .models import (
    Agreement,
    CallStatus,
    CollateralPosition,
    ExposureSnapshot,
    MarginCall,
)
from .store import Store

app = FastAPI(title="Treasury")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
store = Store()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/agreements")
def list_agreements() -> list[Agreement]:
    return list(store.agreements.values())


@app.get("/collateral")
def list_collateral() -> list[CollateralPosition]:
    return list(store.positions.values())


@app.post("/collateral")
def add_collateral(position: CollateralPosition) -> CollateralPosition:
    if position.agreement_id not in store.agreements:
        raise HTTPException(404, "Unknown agreement")
    store.positions[position.id] = position
    return position


@app.put("/exposures")
def set_exposure(snapshot: ExposureSnapshot) -> ExposureSnapshot:
    if snapshot.agreement_id not in store.agreements:
        raise HTTPException(404, "Unknown agreement")
    store.exposures[snapshot.agreement_id] = snapshot
    return snapshot


@app.get("/summary")
def summary() -> list[dict]:
    rows = []
    for aid, agreement in store.agreements.items():
        positions = [p for p in store.positions.values() if p.agreement_id == aid]
        exposure = store.exposures.get(aid)
        mtm = exposure.mark_to_market if exposure else 0
        call = margin.required_call(agreement, mtm, positions) if exposure else None
        rows.append(
            {
                "agreement_id": aid,
                "counterparty": agreement.counterparty,
                "mark_to_market": mtm,
                "collateral_balance": margin.collateral_balance(positions),
                "required_collateral": margin.required_collateral(agreement, mtm),
                "threshold": agreement.threshold,
                "minimum_transfer_amount": agreement.minimum_transfer_amount,
                "implied_call": {"direction": call[0], "amount": call[1]} if call else None,
            }
        )
    return rows


@app.post("/calls/generate")
def generate_calls() -> list[MarginCall]:
    created = []
    for aid, agreement in store.agreements.items():
        exposure = store.exposures.get(aid)
        if not exposure:
            continue
        if any(c.agreement_id == aid and c.status != CallStatus.SETTLED for c in store.calls.values()):
            continue  # an open call already exists for this agreement
        positions = [p for p in store.positions.values() if p.agreement_id == aid]
        result = margin.required_call(agreement, exposure.mark_to_market, positions)
        if result:
            call = MarginCall(
                id=store.next_call_id(),
                agreement_id=aid,
                direction=result[0],
                amount=result[1],
                currency=agreement.currency,
                due_date=store._due,
            )
            store.calls[call.id] = call
            created.append(call)
    return created


@app.get("/calls")
def list_calls() -> list[MarginCall]:
    return list(store.calls.values())


@app.post("/calls/{call_id}/status")
def update_call_status(call_id: str, status: CallStatus) -> MarginCall:
    call = store.calls.get(call_id)
    if not call:
        raise HTTPException(404, "Unknown call")
    call.status = status
    return call


@app.get("/liquidity/dashboard")
def liquidity_dashboard() -> dict:
    return liquidity.build_dashboard(
        store.agreements,
        list(store.positions.values()),
        store.exposures,
        store.cash_accounts,
    )
