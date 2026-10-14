# Treasury Platform: Functional Specification (draft v0.1)

## 1. Purpose
Give a hedge fund's treasury team one place to see where cash is, what is
coming, and what is owed, so they can fund margin, avoid shortfalls and make
daily decisions with confidence.

## 2. Users
**Treasury analyst / ops** (primary): works the daily cycle: loads balances,
reconciles, forecasts, processes margin calls. Needs speed, accuracy and an
audit trail. Read-only and approver roles are out of scope for v1 (single role).

## 3. Modules and priority
| # | Module | Status |
|---|--------|--------|
| 1 | Margin & Collateral | MVP built, needs workflow hardening |
| 2 | Cash Management & Positions | Next |
| 3 | Cash Forecasting & Liquidity | After 2 |
| 4 | Liquidity Dashboard | Built incrementally on top of 1-3 |

## 4. Cross-cutting requirements
- **Reporting currency:** USD; every amount stored in its native currency with a USD equivalent.
- **Money handling:** decimal arithmetic only, never floats. Rounding rules documented per calculation.
- **Entities:** every account and obligation belongs to a legal entity (fund, master, feeder, SPV).
- **As-of dating:** all data is dated; users can view any prior business day.
- **Audit trail:** every create/update records who, when, old and new value. Nothing is hard-deleted.
- **Auth:** login required; single "analyst" role in v1; roles are a later extension.
- **Data sources:** manual entry and CSV upload first; designed so bank/prime broker feeds can plug in later.
- **Persistence:** Postgres with migrations (replaces the in-memory store).
- **Export:** every table exports to CSV.

## 5. Module 1: Margin & Collateral
**Already built:** agreements (threshold, minimum transfer amount, independent amount), collateral with haircuts, required-collateral and implied-call calculation, call generation without duplicates, call statuses, counterparty cards, manual MTM edit.

**Expected functionality**
- M1.1 **Agreements screen is the system of record for margin rules.** Create/edit/deactivate agreements (CSA/ISDA, GMRA etc.): counterparty, entity, currency, threshold, minimum transfer amount (MTA), independent amount, rounding, call cut-off time, and a reference to the signed document. Terms are **effective-dated** (a change creates a new version; calls always use the version in force on the call date) and every change is audit-logged. Today these values are hardcoded in `backend/app/store.py`; this item moves them into the database and a UI.
- M1.2 Manage collateral positions: asset, quantity, price, haircut, posted vs received, eligibility.
- M1.3 **Eligible collateral schedule per agreement** (maintained on the Agreements screen alongside M1.1): for each asset type/rating/maturity bucket, the haircut and an optional concentration cap. Positions inherit their haircut from the schedule instead of carrying one each; collateral that is not on the schedule is flagged ineligible and excluded from the balance. (Today haircuts are set on each position and there is no schedule.)
- M1.4 Import exposures (MTM) per agreement from CSV; show as-of date and staleness warning.
- M1.5 **Excess/Deficit field (the core output of Module 1; everything else is derived from it).** Per agreement, from the fund's point of view:
  Rule (as specified by you), with MtM from the fund's point of view (positive = counterparty owes the fund):
  - **MtM > 0** -> **Excess**; no posting required.
  - **MtM < 0**: let `cover = MtM + collateral posted`.
    - **cover > 0** -> collateral already covers the exposure; **Excess = cover**; no posting required.
    - **cover <= 0** -> **Deficit = MtM + collateral posted** (a negative number); **posting required** for |Deficit|, subject to the MTA test below.
  - **MTA:** a deficit smaller than the minimum transfer amount does not trigger a call.
  - The field is stored and displayed as a single signed number (positive = excess, negative = deficit) plus a status (Excess / Deficit / Deficit below MTA).
  The screen shows the calculation breakdown (MtM, collateral posted, cover, MTA test) so an analyst can explain any number. Replaces the earlier "implied call" wording.
  **Differences from the current code (to be confirmed, section 12):** the current calculation also applies the threshold and independent amount and takes haircuts on collateral. The rule above does not mention them. Example with the seed data: Goldman MtM -14.5M, collateral posted 11.76M after haircut -> Deficit -2.74M under this rule, versus a 1.74M call today (which deducts the 1.0M threshold).
- M1.6 Call workflow with enforced transitions: pending → agreed / disputed → settled; disputes carry a reason and the disputed amount; undo only via audit-logged reversal.
- M1.7 Call direction, always from the fund's point of view: **Received call** = the counterparty says the fund owes more collateral, so the fund **posts** (the code currently calls this "incoming"); **Issued call** = the fund is owed collateral or a return of excess, so the fund **receives** (code: "outgoing"). Each call shows its due date and a cut-off countdown. The UI and spec use "Received/Issued" with a "Post/Receive" action label; the code values are renamed to match.
- M1.8 Settlement: **cash for margin is held at BNY, and all cash movements for calls are made from BNY accounts.** *Choosing cash vs security:* in v1 the analyst chooses. The app lists what the agreement's eligible schedule (M1.3) allows, with the haircut for each option and the amount needed to cover the deficit (deficit / (1 - haircut)), plus unencumbered cash and unencumbered securities available. The firm's real decision rules are an open question (section 12); common drivers are what the counterparty accepts, the cheapest asset to deliver (lowest haircut and opportunity cost), liquidity to preserve, concentration limits and settlement cut-offs. Automatic optimisation is a later extension. For a call the fund posts, the analyst selects the BNY account to be debited and the app creates the planned movement (Module 2, C2.7) against that account and reduces projected balance; for a call the fund receives, the credit lands in the chosen BNY account. Non-cash collateral (for example Treasuries) is recorded as a security transfer from the custody account. The app records and tracks the instruction; it does not send payments to BNY in v1 (the analyst releases the payment in BNY's own system), and the movement is marked confirmed once seen on the BNY balance.
- M1.9 Call history per agreement (merged into the audit trail, not a separate feature). Why it matters: (a) evidence when a counterparty disputes a call or an auditor asks what was agreed and when; (b) reconciliation of calls against counterparty statements; (c) the historical frequency and size of calls is the main input for estimating future margin outflows in the forecast (F3.8). If you do not want this, it can be dropped to the bare status log that M1.6 already requires.
- M1.10 Alerts, derived from the Excess/Deficit field (M1.5): **posting required** (deficit at or above MTA); **large deficit** (above a configurable size); **call due today / cut-off approaching** (for open calls). Excess/Deficit is not used for **stale exposure data**, which is a data-quality alert based on the MTM as-of date, kept separately.
- M1.11 **Agreement type** on every agreement: PB, OTC, PBFI, MNA (definitions to be confirmed by you, section 12). Used for grouping and for the asset/liability presentation in Module 4.

## 6. Module 2: Cash Management & Positions
**Expected functionality**
- C2.1 Manage cash accounts: name, bank/prime broker/custodian, entity, currency, account type (operating, custody, margin, prime broker), status.
- C2.2 Record daily closing balances per account (manual entry or CSV upload); one balance per account per date; edits overwrite and are audit-logged.
- C2.3 Distinguish ledger balance, available balance, and restricted/encumbered cash (for example cash posted as collateral).
- C2.4 FX rates table (manual input, dated) for USD conversion; clear error if a rate is missing rather than silently using zero.
- C2.5 Summary views: total by currency, entity, bank, account type; day-over-day change.
- C2.6 Reconciliation: enter bank-reported balance vs internal balance; show differences and mark as reconciled with a note.
- C2.7 Cash movements log: manual transfers between accounts (internal) with status (planned, sent, confirmed).
- C2.8 Flag accounts with no balance for the current business day.

## 7. Module 3: Cash Forecasting & Liquidity
**Expected functionality**
- F3.1 Forecast items: description, category, entity, account, currency, amount, expected date, certainty (confirmed / expected / estimated), recurring rule (optional).
- F3.2 Categories: capital calls, redemptions, subscriptions, management/performance fees, expenses, trade settlements, margin calls (auto-linked from Module 1), tax, other.
- F3.3 Forecast horizon (default 30 days, selectable) with daily running balance per currency and total in USD.
- F3.4 Shortfall detection: highlight dates where projected balance falls below a minimum cash buffer set per account or entity.
- F3.5 Scenarios: base, plus user-defined stress (for example redemptions +X%, margin calls +Y%); compare scenarios side by side.
- F3.6 Actual vs forecast: when a movement settles, mark the forecast item as realised and show variance.
- F3.7 Funding recommendations: when a shortfall appears, list accounts with available surplus in the same currency.
- F3.8 **How outflows are forecast (the app aggregates known and planned items; it does not predict markets).** Sources, in order of reliability: (1) *margin deficits* taken directly from the Excess/Deficit field (M1.5) when posting is required, dated by the call due date; (2) *analyst-entered known items* with a date (redemptions after notice, capital calls, trade settlements, tax); (3) *recurring items* from rules (management/performance fees, expenses, payroll); (4) *estimated items* flagged as estimates, for example a margin-call allowance sized from the history in M1.9 (average and worst call over the last N days) and used only in stress scenarios (F3.5). Each item carries a certainty tag so the dashboard can show confirmed vs estimated outflows separately. Which of these matter most to you is an open question (section 12).

## 8. Module 4: Liquidity Dashboard
**Design principle:** the dashboard shows how unencumbered cash is affected by the margin calls derived from the Excess/Deficit field (M1.5), position by position.

**Definitions**
- **Unencumbered cash** = cash balances at BNY (Module 2) that are not restricted, not already posted as collateral and not earmarked for a planned movement.

**Expected functionality** (read-only view assembled from Modules 1-3)
- L4.1 Headline tiles: total cash (USD), unencumbered cash, cash posted as collateral, upcoming 7-day net flow, and **margin calls = agreements where Excess/Deficit shows posting required (count and total USD)**, not a separately stored number.
- L4.1a **Impact table per position/agreement:** agreement, type, Excess/Deficit, posting required (yes/no), cash impact if funded in cash, sorted largest deficit first.
- L4.1b **Asset / liability view by agreement type (PB, OTC, PBFI, MNA):** each agreement is classified using the Excess/Deficit rule in M1.5 (not a separate calculation):
  - **Asset** = Excess: either MtM > 0 (the counterparty owes the fund), or MtM < 0 but `MtM + collateral posted > 0` (the fund has posted more than it owes; the surplus is `MtM + collateral posted`).
  - **Liability** = Deficit: MtM < 0 and `MtM + collateral posted <= 0`; the amount is |MtM + collateral posted|. Shown as a liability even when below the MTA (no call is raised), with a "below MTA" flag so it is not mistaken for a call.
  - Each row shows agreement, type, MtM, collateral posted, Excess/Deficit, and Asset or Liability. Grouped by type with total assets, total liabilities and net per type and overall. No netting across agreements unless an agreement explicitly allows it. (Assumed from your comment; please confirm.)
- L4.4 Alert panel: everything from M1.10 (Excess/Deficit-driven), C2.8, F3.4 in one prioritised list.
- L4.5 As-of date selector and entity filter apply to the whole dashboard.
- L4.6 Drill-down: click any tile or row to the underlying accounts or agreements.

## 9. Daily workflow (what the spec must support)
1. Morning: upload prior-day balances and exposures; check staleness alerts.
2. Reconcile balances against bank reports.
3. Review implied margin calls; agree, dispute or settle; choose funding account.
4. Update forecast with new known flows; check shortfall alerts.
5. Review the dashboard; export a daily liquidity report (CSV for v1).

## 10. Non-functional requirements
- Correctness first: every calculation covered by unit tests with hand-checked cases.
- Page loads under 2 seconds for up to 50 accounts, 20 agreements, 500 forecast items.
- Secure by default: no secrets in code, TLS in deployment, access logged.
- Test and build gates in CI.

## 11. Out of scope (v1)
FX & hedging, trade execution, bank payments/SWIFT, general ledger accounting, investor reporting, multi-role permissions, live market data feeds.

## 12. Open questions for the user
0. BNY: which BNY accounts hold margin cash (account numbers/entities/currencies), and in what file or format does BNY report balances and movements?
0a. **Cash vs security:** how does treasury decide today what to post for a call? (Counterparty acceptance, cheapest-to-deliver, liquidity preservation, concentration limits, cut-offs, a written policy?) The answer decides whether v1 needs only a manual choice or a recommendation rule.
0b. **Agreement types:** please confirm what PB, OTC, PBFI and MNA stand for in your firm and whether any of them allow netting across agreements.
0c. **Threshold, independent amount and haircuts:** should the Excess/Deficit rule ignore them (as worded), or should they still apply as in the current code? Is MtM already net of them in the data you receive?
0d. **Outflows:** which outflow types should be in the forecast first (redemptions, fees, expenses, trade settlements, capital calls, margin allowance), and where does the information come from today?
1. Which prime brokers/banks/custodians do you use, and what file formats do they send?
2. Is there a system of record for exposures (risk system, OMS) that we must integrate with?
3. Typical scale: number of entities, accounts, counterparties, currencies?
4. Do actual margin agreements (CSAs) include rules the current calculation ignores (rounding, call timing, eligible collateral)?
5. Who signs off on movements today, and should the app model approvals later?

## 13. Suggested build order
1. Persistence + audit trail + auth (foundation)
2. Module 2: cash positions
3. Module 1 hardening (M1.3, M1.6, M1.8)
4. Module 3: forecasting
5. Module 4: dashboard (grow it with each module, finalise last)
