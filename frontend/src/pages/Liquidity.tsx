import { useCallback, useEffect, useState } from "react";
import { API } from "../api";
import { compact, usd } from "../format";

type Row = {
  agreement_id: string;
  counterparty: string;
  agreement_type: string;
  mark_to_market: string | number;
  excess_deficit: string | number;
  status: "excess" | "deficit" | "deficit_below_mta";
  posting_required: boolean;
  classification: "asset" | "liability";
  cash_impact: string | number;
};
type Dashboard = {
  tiles: {
    total_cash: string | number;
    unencumbered_cash: string | number;
    cash_posted_as_collateral: string | number;
    margin_calls_count: number;
    margin_calls_total: string | number;
  };
  impact: Row[];
  asset_liability: { agreement_type: string; assets: string | number; liabilities: string | number; net: string | number }[];
  cash_accounts: { id: string; name: string; bank: string; entity: string; balance: string | number; restricted: string | number }[];
};

const STATUS_LABEL: Record<Row["status"], string> = {
  excess: "▲ Excess",
  deficit: "▼ Deficit",
  deficit_below_mta: "▼ Deficit below MTA",
};

function Tile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="kpi">
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}</div>
      {sub && <div className="kpi-sub">{sub}</div>}
    </div>
  );
}

/** Diverging bars from a shared zero baseline: excess right (blue), deficit left (red). */
function ExcessDeficitChart({ rows }: { rows: Row[] }) {
  const max = Math.max(...rows.map((r) => Math.abs(Number(r.excess_deficit))), 1);
  return (
    <figure className="chart" aria-label="Excess or deficit by agreement">
      <figcaption>
        Excess / Deficit by agreement
        <span className="legend">
          <i className="sw deficit" /> Deficit <i className="sw excess" /> Excess
        </span>
      </figcaption>
      {rows.map((r) => {
        const v = Number(r.excess_deficit);
        const pct = (Math.abs(v) / max) * 50;
        const tip = `${r.counterparty}: ${v < 0 ? "-" : ""}${usd(Math.abs(v))} ${v < 0 ? "deficit" : "excess"}`;
        return (
          <div className="dv-row" key={r.agreement_id} title={tip} tabIndex={0} aria-label={tip}>
            <span className="dv-name">{r.counterparty}</span>
            <div className="dv-track">
              <div className="dv-axis" />
              {v < 0 ? (
                <div className="dv-bar deficit" style={{ width: `${pct}%`, right: "50%" }} />
              ) : (
                <div className="dv-bar excess" style={{ width: `${pct}%`, left: "50%" }} />
              )}
            </div>
            <span className="num">{v < 0 ? "-" : ""}{compact(Math.abs(v))}</span>
          </div>
        );
      })}
    </figure>
  );
}

export default function Liquidity() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await fetch(`${API}/liquidity/dashboard`);
      if (!res.ok) throw new Error(`API returned ${res.status}`);
      setData(await res.json());
      setError(null);
    } catch (e) {
      setError(`Cannot reach the backend at ${API}. Is uvicorn running? (${(e as Error).message})`);
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  if (error) return <div className="error" role="alert">{error}</div>;
  if (!data) return <p className="empty">Loading…</p>;
  const t = data.tiles;

  return (
    <>
      <div className="kpis">
        <Tile label="Total cash (BNY)" value={usd(t.total_cash)} />
        <Tile label="Unencumbered cash" value={usd(t.unencumbered_cash)} sub="after restricted / earmarked" />
        <Tile label="Cash posted as collateral" value={usd(t.cash_posted_as_collateral)} />
        <Tile
          label="Margin calls"
          value={usd(t.margin_calls_total)}
          sub={`${t.margin_calls_count} ${t.margin_calls_count === 1 ? "agreement requires" : "agreements require"} posting`}
        />
      </div>

      <h2>Impact on cash by agreement</h2>
      <div className="split">
        <ExcessDeficitChart rows={data.impact} />
        <table>
          <thead>
            <tr><th>Agreement</th><th>Type</th><th className="r">MtM</th><th className="r">Excess / Deficit</th><th>Status</th><th className="r">Cash impact</th></tr>
          </thead>
          <tbody>
            {data.impact.map((r) => (
              <tr key={r.agreement_id}>
                <td>{r.counterparty}</td>
                <td>{r.agreement_type}</td>
                <td className="r">{usd(r.mark_to_market)}</td>
                <td className={`r ${Number(r.excess_deficit) < 0 ? "neg" : ""}`}>{usd(r.excess_deficit)}</td>
                <td><span className={`badge ed-${r.status}`}>{STATUS_LABEL[r.status]}</span></td>
                <td className="r">{r.posting_required ? usd(r.cash_impact) : "–"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="note">Cash impact is shown if the deficit is funded in cash. Deficits below the minimum transfer amount raise no call.</p>

      <h2>Assets and liabilities by agreement type</h2>
      <table>
        <thead><tr><th>Type</th><th className="r">Assets (excess)</th><th className="r">Liabilities (deficit)</th><th className="r">Net</th></tr></thead>
        <tbody>
          {data.asset_liability.map((r) => (
            <tr key={r.agreement_type}>
              <td>{r.agreement_type}</td>
              <td className="r">{usd(r.assets)}</td>
              <td className="r">{usd(r.liabilities)}</td>
              <td className={`r ${Number(r.net) < 0 ? "neg" : ""}`}>{usd(r.net)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2>Cash accounts</h2>
      <table>
        <thead><tr><th>Account</th><th>Entity</th><th className="r">Balance</th><th className="r">Restricted</th><th className="r">Unencumbered</th></tr></thead>
        <tbody>
          {data.cash_accounts.map((a) => (
            <tr key={a.id}>
              <td>{a.name}</td><td>{a.entity}</td>
              <td className="r">{usd(a.balance)}</td>
              <td className="r">{usd(a.restricted)}</td>
              <td className="r">{usd(Number(a.balance) - Number(a.restricted))}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
