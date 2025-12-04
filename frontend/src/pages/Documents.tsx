import { useState, useEffect } from "react";
import ReportCard from "../components/ReportCard";
import { getHistory, clearHistory, type HistoryItem } from "../utils/storage";

export default function Documents() {
  const [hist, setHist] = useState<HistoryItem[]>([]);
  const [error, setError] = useState<string | null>(null);

  const loadHistory = () => {
    try {
      const history = getHistory();
      setHist(history);
      setError(null);
    } catch (e) {
      console.error("Failed to load history:", e);
      setError("Failed to load document history");
    }
  };

  useEffect(() => {
    loadHistory();
  }, []);

  const handleClearHistory = () => {
    if (window.confirm("Are you sure you want to clear all document history?")) {
      clearHistory();
      loadHistory();
    }
  };

  if (error) {
    return (
      <section className="container">
        <div className="card" style={{ border: "1px solid var(--bad)" }}>
          <div className="title" style={{ color: "var(--bad)" }}>Error Loading History</div>
          <div className="sub">{error}</div>
          <button onClick={handleClearHistory} style={{ marginTop: "12px" }}>
            Clear History & Reload
          </button>
        </div>
      </section>
    );
  }

  return (
    <section className="container">
      <div className="card">
        <div className="row">
          <div className="grow">
            <div className="title">Processed Documents</div>
            <div className="sub">Local browser history ({hist.length} documents)</div>
          </div>
          {hist.length > 0 && (
            <button onClick={handleClearHistory}>Clear All</button>
          )}
        </div>
      </div>
      {hist.length === 0 && (
        <div className="card">
          <div className="sub">No documents yet. Run some on the Upload page.</div>
        </div>
      )}
      {hist.map((r, i) => (
        <ReportCard
          key={r.timestamp || i}
          title={r?.document_name || `Document ${i + 1}`}
          markdown={r?.report_markdown || "No report available"}
        />
      ))}
    </section>
  );
}
