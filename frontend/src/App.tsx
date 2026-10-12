import { useEffect, useState } from "react";
import "./App.css";

const API = "http://localhost:8000";

type Summary = {
  agreement_id: string;
  counterparty: string;
  mark_to_market: string | number;
  collateral_balance: string | number;
  implied_call: { direction: string; amount: string | number } | null;
};

type Call = {
  id: string;
  agreement_id: string;
  direction: string;
  amount: string | number;
  currency: string;
  due_date: string;
  status: string;
};

const fmt = (v: string | number) =>
  Number(v).toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

export default function App() {
  const [summary, setSummary] = useState<Summary[]>([]);
  const [calls, setCalls] = useState<Call[]>([]);

  const load = async () => {
    setSummary(await (await fetch(`${API}/summary`)).json());
    setCalls(await (await fetch(`${API}/calls`)).json());
  };
  useEffect(() => { load(); }, []);

  const generate = async () => {
    await fetch(`${API}/calls/generate`, { method: "POST" });
    load();
  };

  return (
    <main>
      <h1>Treasury: Margin &amp; Collateral</h1>
      <h2>Counterparty exposure</h2>
      <table>
        <thead><tr><th>Counterparty</th><th>MTM</th><th>Collateral</th><th>Implied call</th></tr></thead>
        <tbody>
          {summary.map((s) => (
            <tr key={s.agreement_id}>
              <td>{s.counterparty}</td>
              <td>{fmt(s.mark_to_market)}</td>
              <td>{fmt(s.collateral_balance)}</td>
              <td>{s.implied_call ? `${s.implied_call.direction} ${fmt(s.implied_call.amount)}` : "none"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <h2>Margin calls <button onClick={generate}>Generate calls</button></h2>
      <table>
        <thead><tr><th>ID</th><th>Agreement</th><th>Direction</th><th>Amount</th><th>Due</th><th>Status</th></tr></thead>
        <tbody>
          {calls.map((c) => (
            <tr key={c.id}>
              <td>{c.id}</td><td>{c.agreement_id}</td><td>{c.direction}</td>
              <td>{fmt(c.amount)}</td><td>{c.due_date}</td><td>{c.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}
