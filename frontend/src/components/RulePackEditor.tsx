import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import type { RulePackRead, RulePackUpdate } from "../api/types";

const schema = z.object({
  id: z.string(),
  version: z.number(),
  doc_type_names: z.string().optional(), // comma-separated
  jurisdiction_allowlist: z.string().optional(), // comma-separated
  notes: z.string().optional(),
});

type FormValues = z.infer<typeof schema>;

export default function RulePackEditor({
  pack,
  onSubmit,
}: {
  pack: RulePackRead;
  onSubmit: (patch: RulePackUpdate) => void;
}) {
  const { register, handleSubmit } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      id: pack.id,
      version: pack.version,
      doc_type_names: (pack.doc_type_names || []).join(", "),
      jurisdiction_allowlist: (pack.rules?.jurisdiction?.allowed_countries || []).join(", "),
      notes: pack.notes || "",
    },
  });

  return (
    <form
      className="card"
      onSubmit={handleSubmit((v) => {
        const patch: RulePackUpdate = {
          doc_type_names: v.doc_type_names?.split(",").map(s=>s.trim()).filter(Boolean),
          rules: {
            ...(pack.rules || {}),
            jurisdiction: {
              allowed_countries: v.jurisdiction_allowlist?.split(",").map(s=>s.trim()).filter(Boolean) || [],
            },
          },
          notes: v.notes ?? undefined,
        };
        onSubmit(patch);
      })}
    >
      <div className="title">Edit draft: {pack.id}@{pack.version}</div>
      <label>
        <div>Document type names (comma-separated)</div>
        <input {...register("doc_type_names")} placeholder="Strategic Alliance Agreement, Alliance Agreement" />
      </label>
      <label>
        <div>Jurisdiction allowlist (comma-separated countries/regions)</div>
        <input {...register("jurisdiction_allowlist")} placeholder="United States, Canada, EU" />
      </label>
      <label>
        <div>Notes</div>
        <textarea {...register("notes")} rows={3} />
      </label>
      <div className="row end">
        <button className="primary" type="submit">Save changes</button>
      </div>
    </form>
  );
}
