import { AlertTriangle, Check, FileSpreadsheet, RefreshCw, Upload, XCircle } from "lucide-react";
import { useRef, useState } from "react";
import { bridgeUrl } from "../lib/hustlenest";
import type { ImportPreviewData, ImportResultData } from "../lib/hustlenest";

type ImportType = "products" | "orders" | "customers";
type UploadPayload = { name: string; content_base64: string };

const readUpload = (file: File) => new Promise<UploadPayload>((resolve, reject) => {
  const reader = new FileReader();
  reader.onerror = () => reject(new Error("The selected file could not be read."));
  reader.onload = () => {
    const encoded = String(reader.result ?? "").split(",", 2)[1];
    if (!encoded) reject(new Error("The selected file is empty."));
    else resolve({ name: file.name, content_base64: encoded });
  };
  reader.readAsDataURL(file);
});

export function ImportSettingsCard() {
  const input = useRef<HTMLInputElement>(null);
  const [importType, setImportType] = useState<ImportType>("products");
  const [upload, setUpload] = useState<UploadPayload | null>(null);
  const [preview, setPreview] = useState<ImportPreviewData | null>(null);
  const [mappings, setMappings] = useState<Record<number, string>>({});
  const [skipDuplicates, setSkipDuplicates] = useState(true);
  const [working, setWorking] = useState<"preview" | "import" | "">("");
  const [message, setMessage] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const [result, setResult] = useState<ImportResultData | null>(null);

  const requestPreview = async (filePayload: UploadPayload, type: ImportType) => {
    setWorking("preview"); setMessage(null); setResult(null);
    try {
      const response = await fetch(`${bridgeUrl}/api/imports/preview`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ import_type: type, file: filePayload }) });
      const payload = await response.json() as { ok: boolean; data?: ImportPreviewData; error?: { message: string } };
      if (!response.ok || !payload.ok || !payload.data) throw new Error(payload.error?.message || "The file could not be previewed.");
      setPreview(payload.data);
      setMappings(Object.fromEntries(payload.data.columns.map((column) => [column.index, column.suggested_field])));
      setMessage({ tone: "success", text: `${payload.data.columns.length} columns loaded and mapped where possible.` });
    } catch (error) {
      setPreview(null); setMappings({});
      setMessage({ tone: "error", text: error instanceof Error ? error.message : "The file could not be previewed." });
    } finally { setWorking(""); }
  };

  const chooseFile = async (file: File | undefined) => {
    if (!file) return;
    if (file.size > 12 * 1024 * 1024) { setMessage({ tone: "error", text: "Import files must be 12 MB or smaller." }); return; }
    try { const next = await readUpload(file); setUpload(next); await requestPreview(next, importType); }
    catch (error) { setMessage({ tone: "error", text: error instanceof Error ? error.message : "The file could not be read." }); }
  };

  const changeType = (next: ImportType) => { setImportType(next); if (upload) void requestPreview(upload, next); };
  const mappedTargets = new Set(Object.values(mappings).filter(Boolean));
  const missingRequired = preview?.fields.filter((field) => field.required && !mappedTargets.has(field.name)) ?? [];

  const runImport = async () => {
    if (!upload || !preview || missingRequired.length) return;
    setWorking("import"); setMessage(null); setResult(null);
    try {
      const response = await fetch(`${bridgeUrl}/api/imports/execute`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ import_type: importType, file: upload, skip_duplicates: skipDuplicates, mappings: Object.entries(mappings).filter(([, target]) => target).map(([source, target]) => ({ source_column: Number(source), target_field: target })) }) });
      const payload = await response.json() as { ok: boolean; data?: ImportResultData; error?: { message: string } };
      if (!response.ok || !payload.ok || !payload.data) throw new Error(payload.error?.message || "The import could not be completed.");
      setResult(payload.data);
      setMessage({ tone: payload.data.error_count ? "error" : "success", text: payload.data.error_count ? "Import completed with row-level issues." : "Import completed successfully." });
    } catch (error) { setMessage({ tone: "error", text: error instanceof Error ? error.message : "The import could not be completed." }); }
    finally { setWorking(""); }
  };

  return <article className="settings-card import-settings-card">
    <div className="settings-card-heading"><span className="setting-icon amber"><FileSpreadsheet size={19} /></span><div><h2>Import data</h2><p>Preview and map CSV or Excel columns before anything is saved</p></div><button className="secondary-button setting-save" onClick={() => input.current?.click()} disabled={Boolean(working)}><Upload size={14} />Choose file</button></div>
    <input ref={input} className="visually-hidden" type="file" accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" onChange={(event) => void chooseFile(event.target.files?.[0])} />
    <div className="import-controls"><label><span>Import as</span><select value={importType} disabled={Boolean(working)} onChange={(event) => changeType(event.target.value as ImportType)}><option value="products">Products</option><option value="orders">Orders</option><option value="customers">Customers</option></select></label><label className="setting-check"><input type="checkbox" checked={skipDuplicates} onChange={(event) => setSkipDuplicates(event.target.checked)} /><span>{skipDuplicates ? "Skip records that already exist" : "Update matching records and preserve unmapped data"}</span></label></div>
    {message ? <div className={`settings-feedback ${message.tone}`} role="status">{message.tone === "success" ? <Check size={15} /> : <AlertTriangle size={15} />}{message.text}</div> : null}
    {working === "preview" ? <div className="import-loading"><RefreshCw size={18} />Reading file and suggesting mappings…</div> : null}
    {preview ? <>
      <div className="import-file-summary"><FileSpreadsheet size={18} /><span><strong>{preview.file.name}</strong><small>{(preview.file.size_bytes / 1024).toFixed(1)} KB · {preview.file.source_detail}</small></span></div>
      <div className="import-mapping-list"><div><strong>Source column</strong><strong>Sample values</strong><strong>HustleNest field</strong></div>{preview.columns.map((column) => <div key={column.index}><span><strong>{column.name}</strong></span><small>{column.sample_values.filter(Boolean).slice(0, 3).join(" · ") || "No sample"}</small><select aria-label={`Map ${column.name}`} value={mappings[column.index] ?? ""} onChange={(event) => setMappings((current) => ({ ...current, [column.index]: event.target.value }))}><option value="">Skip column</option>{preview.fields.map((field) => <option key={field.name} value={field.name} disabled={mappedTargets.has(field.name) && mappings[column.index] !== field.name}>{field.label}{field.required ? " *" : ""}</option>)}</select></div>)}</div>
      {missingRequired.length ? <div className="import-required"><XCircle size={16} /><span>Map required field{missingRequired.length === 1 ? "" : "s"}: {missingRequired.map((field) => field.label).join(", ")}</span></div> : null}
      <div className="import-footer"><span>{preview.preview_rows.length} preview rows shown · A backup is recommended before a large update.</span><button className="primary-button" disabled={Boolean(working) || Boolean(missingRequired.length)} onClick={() => void runImport()}><Upload size={15} />{working === "import" ? "Importing…" : `Import ${importType}`}</button></div>
    </> : null}
    {result ? <div className="import-result"><div><strong>{result.imported_count}</strong><span>Imported</span></div><div><strong>{result.skipped_count}</strong><span>Skipped</span></div><div className={result.error_count ? "has-errors" : ""}><strong>{result.error_count}</strong><span>Errors</span></div>{result.errors.length || result.warnings.length ? <details><summary>Review import messages</summary><ul>{[...result.errors, ...result.warnings].map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ul>{result.messages_truncated ? <p>Only the first 100 messages of each type are shown.</p> : null}</details> : null}<button className="secondary-button" onClick={() => window.location.reload()}><RefreshCw size={14} />Reload workspace data</button></div> : null}
  </article>;
}
