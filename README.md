# Treasury

Treasury workflow app for a hedge fund. MVP scope: **margin & collateral management**.

## Run

Backend (http://localhost:8000, docs at /docs):

    cd backend && python3 -m venv .venv && . .venv/bin/activate
    pip install -r requirements.txt
    uvicorn app.main:app --reload
    pytest

Frontend (http://localhost:5173):

    cd frontend && npm install && npm run dev

## Layout

- `backend/app/margin.py` – call calculation (threshold, MTA, independent amount, haircuts)
- `backend/app/store.py` – in-memory seed data (swap for Postgres)
- `frontend/` – React + Vite dashboard

## Next steps

Postgres + migrations, auth and audit trail, real data feeds (prime broker/custodian files, MTM from risk system), call workflow (approve/dispute/settle), eligible-collateral rules and optimisation.
