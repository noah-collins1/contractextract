import axios from "axios";
import type {
  RulePackOut,
  RulePackRead,
  PreviewRunOut,
  DeleteResult,
  RulePackUpdate,
} from "./types";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://localhost:8000",
});

// Rule Packs
export async function listActiveRulePacks(): Promise<RulePackOut[]> {
  const { data } = await api.get<RulePackOut[]>("/rule-packs", { params: { status: "active" } });
  return data;
}
export async function listAllRulePacks(): Promise<RulePackOut[]> {
  const { data } = await api.get<RulePackOut[]>("/rule-packs/all");
  return data;
}
export async function listPackVersions(packId: string): Promise<RulePackOut[]> {
  const { data } = await api.get<RulePackOut[]>(`/rule-packs/${encodeURIComponent(packId)}`);
  return data;
}
export async function readRulePack(packId: string, version: number): Promise<RulePackRead> {
  const { data } = await api.get<RulePackRead>(`/rule-packs/${encodeURIComponent(packId)}/${version}`);
  return data;
}
export async function readRulePackYaml(packId: string, version: number): Promise<string> {
  const { data } = await api.get<string>(`/rule-packs/${encodeURIComponent(packId)}/${version}/yaml`);
  return data;
}
export async function importYamlText(yaml_text: string): Promise<RulePackOut> {
  const { data } = await api.post<RulePackOut>("/rule-packs/import-yaml", { yaml_text });
  return data;
}
export async function uploadYamlFile(file: File): Promise<RulePackOut> {
  const fd = new FormData();
  fd.append("file", file);
  const { data } = await api.post<RulePackOut>("/rule-packs/upload-yaml", fd, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}
export async function publishPack(packId: string, version: number): Promise<RulePackOut> {
  const { data } = await api.post<RulePackOut>(`/rule-packs/${encodeURIComponent(packId)}/${version}:publish`);
  return data;
}
export async function deprecatePack(packId: string, version: number): Promise<{id:string;version:number;status:string}> {
  const { data } = await api.post(`/rule-packs/${encodeURIComponent(packId)}/${version}:deprecate`);
  return data;
}
export async function deletePack(packId: string, version: number, force = false): Promise<DeleteResult> {
  const { data } = await api.delete<DeleteResult>(`/rule-packs/${encodeURIComponent(packId)}/${version}`, { params: { force } });
  return data;
}
export async function updateDraftPatch(packId: string, version: number, patch: RulePackUpdate): Promise<RulePackRead> {
  const { data } = await api.put<RulePackRead>(`/rule-packs/${encodeURIComponent(packId)}/${version}`, { patch });
  return data;
}
export async function updateDraftYaml(packId: string, version: number, yaml_text: string): Promise<RulePackRead> {
  const { data } = await api.put<RulePackRead>(`/rule-packs/${encodeURIComponent(packId)}/${version}`, { yaml_text });
  return data;
}

// Preview run (sync evaluation)
export async function previewRun(file: File, packId?: string, onProgress?: (p:number)=>void): Promise<PreviewRunOut> {
  const fd = new FormData();
  fd.append("file", file);
  if (packId) fd.append("pack_id", packId);
  const { data } = await api.post<PreviewRunOut>("/preview-run", fd, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (e) => {
      if (e.total) {
        const pct = Math.round((e.loaded / e.total) * 100);
        onProgress?.(pct);
      }
    },
  });
  return data;
}
