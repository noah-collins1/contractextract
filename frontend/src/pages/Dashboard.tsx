import { useState, useEffect } from "react";
import { getHistoryStats } from "../utils/storage";

export default function Dashboard() {
  const [stats, setStats] = useState({ total: 0, pass: 0, fail: 0 });
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    try {
      const historyStats = getHistoryStats();
      setStats(historyStats);
    } catch (e) {
      console.error("Failed to load history:", e);
      setError("Failed to load statistics");
    }
  }, []);

  return (
    <section className="container">
      {error && (
        <div className="card" style={{ border: "1px solid var(--bad)" }}>
          <div className="sub" style={{ color: "var(--bad)" }}>{error}</div>
        </div>
      )}
      <div className="grid">
        <div className="stat">
          <div className="kpi">{stats.total}</div>
          <div className="label">Docs processed</div>
        </div>
        <div className="stat">
          <div className="kpi" style={{ color: "var(--ok)" }}>{stats.pass}</div>
          <div className="label">Pass</div>
        </div>
        <div className="stat">
          <div className="kpi" style={{ color: "var(--bad)" }}>{stats.fail}</div>
          <div className="label">Fail</div>
        </div>
      </div>
      <div className="card">
        <div className="sub">
          These counts reflect local browser history only. Document history is stored in your browser's localStorage.
        </div>
      </div>
    </section>
  );
}
