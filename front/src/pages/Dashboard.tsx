export default function Dashboard(){
  const hist: any[] = JSON.parse(localStorage.getItem("cextract_history")||"[]");
  const pass = hist.filter(h => /\*\*Overall:\*\*.*PASS/.test(h.report_markdown)).length;
  const fail = hist.length - pass;
  return (
    <section className="container">
      <div className="grid">
        <div className="stat"><div className="kpi">{hist.length}</div><div className="label">Docs processed</div></div>
        <div className="stat"><div className="kpi">{pass}</div><div className="label">Pass</div></div>
        <div className="stat"><div className="kpi">{fail}</div><div className="label">Fail</div></div>
      </div>
      <p className="sub">These counts reflect local history from this browser only. For true multi-user job tracking, the backend would need job endpoints.</p>
    </section>
  );
}
