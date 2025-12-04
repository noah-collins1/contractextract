import ReportCard from "../components/ReportCard";

export default function Documents() {
  const hist: any[] = JSON.parse(localStorage.getItem("cextract_history")||"[]");
  return (
    <section className="container">
      <div className="title">Processed Documents (local history)</div>
      {hist.length === 0 && <div className="sub">No documents yet. Run some on the Upload page.</div>}
      {hist.map((r, i) => (
        <ReportCard key={i} title={r.document_name} markdown={r.report_markdown} />
      ))}
    </section>
  );
}
