import { useCallback, useEffect, useState } from "react";
import { API } from "../api";
import { compact, usd } from "../format";

type Summary = {
  agreement_id: string;
  counterparty: string;
  mark_to_market: string | number;
  collateral_balance: string | number;
  required_collateral: string | number;
  threshold: string | number;
  minimum_transfer_amount: string | number;
  implied_call: { direction: "incoming" | "outgoing"; amount: string | number } | null;
};

type Call = {
  id: string;
  agreement_id: string;
  direction: "incoming" | "outgoing";
  amount: string | number;
  currency: string;
  due_date: string;
  status: "pending" | "agreed" | "disputed" | "settled";
};

function Kpi({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="kpi">
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}</div>
      {sub && <div className="kpi-sub">{sub}</div>}
    </div>
  );
}

function ExposureCard({ s, onSetExposure }: { s: Summary; onSetExposure: (id: string, mtm: string) => void }) {
  const required = Math.max(Number(s.required_collateral), 0);
  const held = Number(s.collateral_balance);
  const scale = Math.max(required, held, 1);
  const coverage = required > 0 ? held / required : null;
  const [edit, setEdit] = useState(String(Number(s.mark_to_market)));
  useEffect(() => setEdit(String(Number(s.mark_to_market))), [s.mark_to_market]);

  return (
    <section className="card">
      <header>
        <h3>{s.counterparty}</h3>
        {s.implied_call ? (
          <span className={`badge ${s.implied_call.direction}`}>
            {s.implied_call.direction === "incoming" ? "Post" : "Receive"} {usd(s.implied_call.amount)}
          </span>
        ) : (
          <span className="badge ok">No call</span>
        )}
      </header>
      <dl>
        <div><dt>Mark-to-market</dt><dd className={Number(s.mark_to_market) < 0 ? "neg" : ""}>{usd(s.mark_to_market)}</dd></div>
        <div><dt>Threshold</dt><dd>{usd(s.threshold)}</dd></div>
        <div><dt>Min transfer</dt><dd>{usd(s.minimum_transfer_amount)}</dd></div>
      </dl>
      <div className="bars" aria-label="Collateral held versus required">
        <div className="bar-row">
          <span>Required</span>
          <div className="track"><div className="fill required" style={{ width: `${Math.max(required / scale, 0) * 100}%` }} /></div>
          <span className="num">{compact(required)}</span>
        </div>
        <div className="bar-row">
          <span>Held</span>
          <div className="track"><div className="fill held" style={{ width: `${Math.max(held / scale, 0) * 100}%` }} /></div>
          <span className="num">{compact(held)}</span>
        </div>
      </div>
      <div className="coverage">
        Coverage: <strong>{coverage === null ? "n/a" : `${(coverage * 100).toFixed(1)}%`}</strong>
      </div>
      <form className="edit" onSubmit={(e) => { e.preventDefault(); onSetExposure(s.agreement_id, edit); }}>
        <label>
          Set MTM
          <input type="number" value={edit} onChange={(e) => setEdit(e.target.value)} />
        </label>
        <button type="submit">Update</button>
      </form>
    </section>
  );
}

export default function Margin() {
  const [summary, setSummary] = useState<Summary[]>([]);
  const [calls, setCalls] = useState<Call[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [s, c] = await Promise.all([fetch(`${API}/summary`), fetch(`${API}/calls`)]);
      if (!s.ok || !c.ok) throw new Error(`API returned ${s.status}/${c.status}`);
      setSummary(await s.json());
      setCalls(await c.json());
      setError(null);
    } catch (e) {
      setError(`Cannot reach the backend at ${API}. Is uvicorn running? (${(e as Error).message})`);
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  const post = async (url: string, init?: RequestInit) => { await fetch(`${API}${url}`, init); await load(); };
  const generate = () => post("/calls/generate", { method: "POST" });
  const setStatus = (id: string, status: string) => post(`/calls/${id}/status?status=${status}`, { method: "POST" });
  const setExposure = (agreement_id: string, mtm: string) =>
    post("/exposures", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ agreement_id, mark_to_market: mtm }),
    });

  const totalMtm = summary.reduce((a, s) => a + Number(s.mark_to_market), 0);
  const totalHeld = summary.reduce((a, s) => a + Number(s.collateral_balance), 0);
  const open = calls.filter((c) => c.status !== "settled");
  const incoming = summary.reduce((a, s) => a + (s.implied_call?.direction === "incoming" ? Number(s.implied_call.amount) : 0), 0);

  const nCalls = summary.filter((s) => s.implied_call).length;

  return (
    <>
      {error && <div className="error" role="alert">{error}</div>}

      <div className="kpis">
        <Kpi label="Net mark-to-market" value={usd(totalMtm)} sub="negative = fund owes" />
        <Kpi label="Collateral held" value={usd(totalHeld)} sub="after haircuts" />
        <Kpi label="Implied calls to post" value={usd(incoming)} sub={`${nCalls} ${nCalls === 1 ? "counterparty" : "counterparties"}`} />
        <Kpi label="Open margin calls" value={String(open.length)} />
      </div>

      <h2>Counterparties</h2>
      <div className="cards">
        {summary.map((s) => <ExposureCard key={s.agreement_id} s={s} onSetExposure={setExposure} />)}
      </div>

      <h2>Margin calls <button className="primary" onClick={generate}>Generate calls</button></h2>
      {calls.length === 0 ? (
        <p className="empty">No calls yet. Click "Generate calls" to create them from current exposures.</p>
      ) : (
        <table>
          <thead><tr><th>ID</th><th>Agreement</th><th>Direction</th><th className="r">Amount</th><th>Due</th><th>Status</th><th>Actions</th></tr></thead>
          <tbody>
            {calls.map((c) => (
              <tr key={c.id}>
                <td>{c.id}</td>
                <td>{c.agreement_id}</td>
                <td><span className={`badge ${c.direction}`}>{c.direction === "incoming" ? "Post" : "Receive"}</span></td>
                <td className="r">{usd(c.amount)}</td>
                <td>{c.due_date}</td>
                <td><span className={`badge status-${c.status}`}>{c.status}</span></td>
                <td>
                  {c.status !== "settled" && (
                    <div className="actions">
                      <button onClick={() => setStatus(c.id, "agreed")}>Agree</button>
                      <button onClick={() => setStatus(c.id, "disputed")}>Dispute</button>
                      <button onClick={() => setStatus(c.id, "settled")}>Settle</button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}
