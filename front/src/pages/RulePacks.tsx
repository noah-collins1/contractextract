import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  listAllRulePacks,
  readRulePack,
  updateDraftPatch,
  importYamlText,
  uploadYamlFile,
  publishPack,
  deprecatePack,
  deletePack,
} from "../api/client";
import RulePackEditor from "../components/RulePackEditor";
import React from "react";

export default function RulePacks() {
  const qc = useQueryClient();
  const { data: all = [] } = useQuery({ queryKey: ["packs", "all"], queryFn: listAllRulePacks });

  const [selected, setSelected] = React.useState<{ id:string; version:number } | null>(null);
  const { data: selectedPack } = useQuery({
    queryKey: ["pack", selected?.id, selected?.version],
    queryFn: () => readRulePack(selected!.id, selected!.version),
    enabled: !!selected,
  });

  const upd = useMutation({
    mutationFn: (patch:any) => updateDraftPatch(selected!.id, selected!.version, patch),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["packs"] }); },
  });

  const onCreateFromText = useMutation({
    mutationFn: importYamlText,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["packs"] }),
  });
  const onUploadFile = useMutation({
    mutationFn: uploadYamlFile,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["packs"] }),
  });

  return (
    <section className="container">
      <div className="card">
        <div className="title">Rule Packs</div>
        <table className="table">
          <thead><tr><th>Pack</th><th>Version</th><th>Status</th><th>Doc types</th><th>Actions</th></tr></thead>
          <tbody>
            {all.map(p => (
              <tr key={`${p.id}@${p.version}`}>
                <td>{p.id}</td>
                <td>{p.version}</td>
                <td>{p.status}</td>
                <td>{(p.doc_type_names||[]).join(", ")}</td>
                <td className="actions">
                  <button onClick={()=>setSelected({id:p.id, version:p.version})}>Open</button>
                  {p.status==="draft" && <>
                    <button className="primary" onClick={()=>publishPack(p.id, p.version).then(()=>qc.invalidateQueries({queryKey:["packs"]}))}>Publish</button>
                  </>}
                  {p.status!=="deprecated" && <button onClick={()=>deprecatePack(p.id, p.version).then(()=>qc.invalidateQueries({queryKey:["packs"]}))}>Deprecate</button>}
                  <button onClick={()=>deletePack(p.id, p.version, p.status!=="draft").then(()=>qc.invalidateQueries({queryKey:["packs"]}))}>Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="grid">
        <div>
          <div className="card">
            <div className="title">New rule pack (YAML)</div>
            <textarea placeholder="Paste YAML here" rows={10} id="yamlText" />
            <div className="row end">
              <button className="primary" onClick={()=>{
                const txt = (document.getElementById("yamlText") as HTMLTextAreaElement).value;
                onCreateFromText.mutate(txt);
              }}>Import YAML</button>
              <input type="file" accept=".yml,.yaml" onChange={(e)=>{
                const f = e.target.files?.[0];
                if (f) onUploadFile.mutate(f);
              }} />
            </div>
          </div>
        </div>

        <div>
          {selected && selectedPack && (
            <RulePackEditor
              pack={selectedPack}
              onSubmit={(patch)=>upd.mutate(patch)}
            />
          )}
        </div>
      </div>
    </section>
  );
}
