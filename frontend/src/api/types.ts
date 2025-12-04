export type RulePackOut = {
  id: string;
  version: number;
  status: string; // "active" | "draft" | "deprecated"
  doc_type_names: string[];
};

export type PreviewRunOut = {
  document_name: string;
  pack_id: string;
  report_markdown: string;
};

export type RulePackRead = {
  id: string;
  version: number;
  status: string;
  schema_version?: number | string;
  doc_type_names?: string[];
  rules?: any;
  rules_json?: any[];
  llm_prompt?: string | null;
  examples?: any[];
  extensions?: any;
  extensions_schema?: any;
  raw_yaml?: string;
  notes?: string | null;
  created_by?: string | null;
};

export type DeleteResult = { id: string; version: number; status: string };

export type RulePackUpdate = Partial<{
  schema_version: number | string;
  doc_type_names: string[];
  rules: any;
  rules_json: any[];
  llm_prompt: string | null;
  examples: any[];
  extensions: any;
  extensions_schema: any;
  raw_yaml: string | null;
  notes: string | null;
}>;
