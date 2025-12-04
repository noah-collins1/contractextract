import { useState } from "react";
import { previewRun } from "../api/client";
import type { RulePackOut, PreviewRunOut } from "../api/types";

export type FileJob = {
  id: string;
  file: File;
  packId: string | undefined; // undefined => auto-detect
  progress: number; // 0-100
  status: "queued" | "running" | "done" | "error";
  result?: PreviewRunOut;
  error?: string;
};

export default function FileRow({
  job,
  packs,
  onChange,
}: {
  job: FileJob;
  packs: RulePackOut[];
  onChange: (j: FileJob) => void;
}) {
  const [local, setLocal] = useState(job);

  async function run() {
    try {
      const running = { ...local, status: "running", progress: 5 };
      setLocal(running); onChange(running);
      const res = await previewRun(local.file, local.packId, (pct) => {
        const upd = { ...running, progress: Math.max(pct, running.progress) };
        setLocal(upd); onChange(upd);
      });
      const done = { ...running, status: "done", progress: 100, result: res };
      setLocal(done); onChange(done);
    } catch (e:any) {
      const err = { ...local, status: "error", error: e?.response?.data?.detail || e.message, progress: 100 };
      setLocal(err); onChange(err);
    }
  }

  return (
    <div className="card">
      <div className="row">
        <div className="grow">
          <div className="title">{local.file.name}</div>
          <div className="sub">{Math.round(local.file.size/1024)} KB</div>
        </div>
        <select
          value={local.packId || "__auto__"}
          onChange={(e)=>{
            const v = e.target.value === "__auto__" ? undefined : e.target.value;
            const upd = { ...local, packId: v };
            setLocal(upd); onChange(upd);
          }}
        >
          <option value="__auto__">Auto-detect</option>
          {packs.map(p => (
            <option key={`${p.id}@${p.version}`} value={p.id}>
              {p.id} (v{p.version})
            </option>
          ))}
        </select>
        <button className="primary" onClick={run} disabled={local.status==="running"}>Run</button>
      </div>
      <div className="progress"><span style={{width: `${local.progress}%`}}/></div>
      {local.status === "error" && <div className="error">{local.error}</div>}
      {local.result && (
        <details>
          <summary>View report</summary>
          <div className="report">
            <strong>Pack:</strong> {local.result.pack_id}<br/>
            <strong>Doc:</strong> {local.result.document_name}
          </div>
        </details>
      )}
    </div>
  );
}
