import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { listActiveRulePacks } from "../api/client";
import type { RulePackOut, PreviewRunOut } from "../api/types";
import FileRow, { FileJob } from "../components/FileRow";
import ReportCard from "../components/ReportCard";

export default function Upload() {
  const { data: packs = [] } = useQuery({ queryKey: ["packs", "active"], queryFn: listActiveRulePacks });
  const [jobs, setJobs] = useState<FileJob[]>([]);
  const [results, setResults] = useState<PreviewRunOut[]>([]);

  function onFiles(files: FileList | null) {
    if (!files) return;
    const newJobs: FileJob[] = Array.from(files).map((f, i) => ({
      id: `${f.name}-${Date.now()}-${i}`,
      file: f,
      packId: undefined,
      progress: 0,
      status: "queued",
    }));
    setJobs((prev)=>[...prev, ...newJobs]);
  }

  function onJobChange(updated: FileJob) {
    setJobs(prev => prev.map(j => j.id === updated.id ? updated : j));
    if (updated.status === "done" && updated.result) {
      setResults(prev => [updated.result!, ...prev]);
      const hist = JSON.parse(localStorage.getItem("cextract_history")||"[]");
      hist.unshift(updated.result);
      localStorage.setItem("cextract_history", JSON.stringify(hist).slice(0, 2000));
    }
  }

  return (
    <section className="container">
      <div className="card">
        <div className="title">Upload & Evaluate</div>
        <div className="drop" onDragOver={(e)=>e.preventDefault()} onDrop={(e)=>{ e.preventDefault(); onFiles(e.dataTransfer.files); }}>
          <input type="file" multiple onChange={(e)=>onFiles(e.target.files)} />
          <p>Drag PDFs here or choose files. Select a rule pack per file or use auto-detect.</p>
        </div>
      </div>

      <div className="grid">
        <div>
          {jobs.map(j => (
            <FileRow key={j.id} job={j} packs={packs as RulePackOut[]} onChange={onJobChange} />
          ))}
        </div>
        <div>
          {results.map((r, idx) => (
            <ReportCard key={idx} title={r.document_name} markdown={r.report_markdown} />
          ))}
        </div>
      </div>
    </section>
  );
}
