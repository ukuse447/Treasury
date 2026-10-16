import { useState } from "react";
import "./App.css";
import Liquidity from "./pages/Liquidity";
import Margin from "./pages/Margin";

const TABS = [
  { id: "liquidity", label: "Liquidity Dashboard" },
  { id: "margin", label: "Margin & Collateral" },
] as const;

export default function App() {
  const [tab, setTab] = useState<(typeof TABS)[number]["id"]>("liquidity");
  return (
    <main>
      <h1>Treasury</h1>
      <nav className="tabs" role="tablist">
        {TABS.map((t) => (
          <button key={t.id} role="tab" aria-selected={tab === t.id} className={tab === t.id ? "active" : ""} onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </nav>
      {tab === "liquidity" ? <Liquidity /> : <Margin />}
    </main>
  );
}
