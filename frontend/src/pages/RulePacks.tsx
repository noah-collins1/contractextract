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

  // Fetch all rule packs
  const {
    data: all = [],
    isLoading,
    error,
    refetch
  } = useQuery({
    queryKey: ["packs", "all"],
    queryFn: listAllRulePacks
  });

  const [selected, setSelected] = React.useState<{ id: string; version: number } | null>(null);
  const [yamlText, setYamlText] = React.useState("");
  const [uploadError, setUploadError] = React.useState<string | null>(null);

  // Fetch selected pack details
  const { data: selectedPack } = useQuery({
    queryKey: ["pack", selected?.id, selected?.version],
    queryFn: () => readRulePack(selected!.id, selected!.version),
    enabled: !!selected,
  });

  // Mutation for updating draft packs
  const upd = useMutation({
    mutationFn: (patch: any) => updateDraftPatch(selected!.id, selected!.version, patch),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["packs"] });
      qc.invalidateQueries({ queryKey: ["pack", selected?.id, selected?.version] });
    },
    onError: (error: any) => {
      alert(`Update failed: ${error.message || String(error)}`);
    },
  });

  // Mutation for importing YAML text
  const importMutation = useMutation({
    mutationFn: importYamlText,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["packs"] });
      setYamlText("");
      setUploadError(null);
      alert("Rule pack imported successfully!");
    },
    onError: (error: any) => {
      setUploadError(error.response?.data?.detail || error.message || String(error));
    },
  });

  // Mutation for uploading YAML file
  const uploadMutation = useMutation({
    mutationFn: uploadYamlFile,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["packs"] });
      setUploadError(null);
      alert("Rule pack uploaded successfully!");
    },
    onError: (error: any) => {
      setUploadError(error.response?.data?.detail || error.message || String(error));
    },
  });

  const handleImportYaml = () => {
    if (!yamlText.trim()) {
      alert("Please paste YAML content first");
      return;
    }
    importMutation.mutate(yamlText);
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      uploadMutation.mutate(file);
    }
  };

  return (
    <section className="container">
      <div className="card">
        <div className="title">Rule Packs</div>

        {/* Loading State */}
        {isLoading && (
          <div className="sub" style={{ padding: "20px", textAlign: "center" }}>
            Loading rule packs...
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="card" style={{ border: "1px solid var(--bad)", marginBottom: "20px" }}>
            <div className="sub" style={{ color: "var(--bad)" }}>
              Error loading rule packs: {(error as any).message || String(error)}
            </div>
            <button onClick={() => refetch()} style={{ marginTop: "10px" }}>
              Retry
            </button>
          </div>
        )}

        {/* Table */}
        {!isLoading && !error && (
          <table className="table">
            <thead>
              <tr>
                <th>Pack ID</th>
                <th>Version</th>
                <th>Status</th>
                <th>Doc Types</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {all.length === 0 && (
                <tr>
                  <td colSpan={5} style={{ textAlign: "center", padding: "20px" }}>
                    No rule packs found. Create one below.
                  </td>
                </tr>
              )}
              {all.map((p) => (
                <tr key={`${p.id}@${p.version}`}>
                  <td>{p.id}</td>
                  <td>{p.version}</td>
                  <td>
                    <span
                      style={{
                        color:
                          p.status === "active"
                            ? "var(--ok)"
                            : p.status === "draft"
                            ? "var(--warn)"
                            : "var(--muted)",
                      }}
                    >
                      {p.status}
                    </span>
                  </td>
                  <td>{(p.doc_type_names || []).join(", ")}</td>
                  <td className="actions">
                    <button onClick={() => setSelected({ id: p.id, version: p.version })}>
                      Open
                    </button>
                    {p.status === "draft" && (
                      <button
                        className="primary"
                        onClick={() =>
                          publishPack(p.id, p.version).then(() =>
                            qc.invalidateQueries({ queryKey: ["packs"] })
                          )
                        }
                      >
                        Publish
                      </button>
                    )}
                    {p.status !== "deprecated" && (
                      <button
                        onClick={() =>
                          deprecatePack(p.id, p.version).then(() =>
                            qc.invalidateQueries({ queryKey: ["packs"] })
                          )
                        }
                      >
                        Deprecate
                      </button>
                    )}
                    <button
                      onClick={() =>
                        deletePack(p.id, p.version, p.status !== "draft").then(() =>
                          qc.invalidateQueries({ queryKey: ["packs"] })
                        )
                      }
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="grid">
        <div>
          <div className="card">
            <div className="title">Import New Rule Pack (YAML)</div>

            {/* Upload Error */}
            {uploadError && (
              <div style={{ padding: "10px", backgroundColor: "#fee", border: "1px solid #c00", borderRadius: "4px", marginBottom: "12px" }}>
                <strong>Error:</strong> {uploadError}
              </div>
            )}

            <textarea
              placeholder="Paste YAML here"
              rows={10}
              value={yamlText}
              onChange={(e) => setYamlText(e.target.value)}
              style={{ width: "100%", fontFamily: "monospace", fontSize: "12px" }}
            />
            <div className="row end" style={{ marginTop: "12px", gap: "12px" }}>
              <button
                className="primary"
                onClick={handleImportYaml}
                disabled={importMutation.isPending || !yamlText.trim()}
              >
                {importMutation.isPending ? "Importing..." : "Import YAML"}
              </button>
              <label
                style={{
                  padding: "8px 16px",
                  backgroundColor: "var(--bg-secondary)",
                  cursor: "pointer",
                  borderRadius: "4px",
                }}
              >
                {uploadMutation.isPending ? "Uploading..." : "Upload File"}
                <input
                  type="file"
                  accept=".yml,.yaml"
                  onChange={handleFileUpload}
                  disabled={uploadMutation.isPending}
                  style={{ display: "none" }}
                />
              </label>
            </div>
          </div>
        </div>

        <div>
          {selected && selectedPack && (
            <RulePackEditor pack={selectedPack} onSubmit={(patch) => upd.mutate(patch)} />
          )}
        </div>
      </div>

      {/* Debug Panel */}
      <div className="card" style={{ marginTop: "20px", backgroundColor: "#f5f5f5" }}>
        <div className="sub" style={{ fontFamily: "monospace", fontSize: "12px" }}>
          <strong>Debug Info:</strong>
          <br />
          API Base: {import.meta.env.VITE_API_BASE_URL || "(default)"}
          <br />
          Packs Loaded: {all?.length ?? 0}
          <br />
          Loading: {isLoading ? "Yes" : "No"}
          <br />
          Error: {error ? String((error as any).message || error) : "none"}
        </div>
      </div>
    </section>
  );
}
