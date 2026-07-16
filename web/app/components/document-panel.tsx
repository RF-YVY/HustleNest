"use client";

import { FileUp, Link2, ShieldCheck, Trash2, X } from "lucide-react";
import { FormEvent, useMemo, useState } from "react";
import { bridgeUrl, type DocumentsWorkspaceData } from "../lib/hustlenest";

type DocumentItem = DocumentsWorkspaceData["documents"][number];
export type DocumentLinkOptions = Record<"order" | "customer" | "product" | "material" | "vendor", Array<{ id: number; label: string; detail: string }>>;

const readBase64 = (file: File) => new Promise<string>((resolve, reject) => {
  const reader = new FileReader();
  reader.onload = () => resolve(String(reader.result).split(",", 2)[1] || "");
  reader.onerror = () => reject(new Error("The selected file could not be read."));
  reader.readAsDataURL(file);
});

export function DocumentPanel({ document, options, onClose, onChanged }: { document?: DocumentItem; options: DocumentLinkOptions; onClose: () => void; onChanged: (message: string, id?: number) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [category, setCategory] = useState(document?.category === "Uncategorized" ? "" : document?.category ?? "");
  const [description, setDescription] = useState(document?.description ?? "");
  const [tags, setTags] = useState(document?.tags.join(", ") ?? "");
  const [entityType, setEntityType] = useState(document?.entity.type ?? "general");
  const [entityId, setEntityId] = useState(document?.entity.id ? String(document.entity.id) : "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [deleteArmed, setDeleteArmed] = useState(false);
  const [deleteFile, setDeleteFile] = useState(Boolean(document?.managed));
  const records = useMemo(() => entityType === "general" ? [] : options[entityType as keyof DocumentLinkOptions] ?? [], [entityType, options]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!document && !file) { setError("Choose a file to upload."); return; }
    if (file && file.size > 20 * 1024 * 1024) { setError("Files must be 20 MB or smaller."); return; }
    setSaving(true); setError("");
    try {
      const body: Record<string, unknown> = {
        expected_revision: document?.revision,
        values: { category, description, tags: tags.split(",").map((tag) => tag.trim()).filter(Boolean), entity_type: entityType, entity_id: entityId },
      };
      if (file) body.file = { name: file.name, content_base64: await readBase64(file) };
      const response = await fetch(`${bridgeUrl}/api/documents${document ? `/${document.id}` : ""}`, { method: document ? "PUT" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const payload = (await response.json()) as { ok: boolean; data?: DocumentItem; error?: { message: string } };
      if (!response.ok || !payload.ok || !payload.data) throw new Error(payload.error?.message || "The document could not be saved.");
      onChanged(`${payload.data.name} ${document ? "updated" : "uploaded"}.`, payload.data.id);
    } catch (caught: unknown) { setError(caught instanceof Error ? caught.message : "The document could not be saved."); } finally { setSaving(false); }
  };

  const remove = async () => {
    if (!document) return; setSaving(true); setError("");
    try {
      const response = await fetch(`${bridgeUrl}/api/documents/${document.id}`, { method: "DELETE", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expected_revision: document.revision, delete_file: deleteFile }) });
      const payload = (await response.json()) as { ok: boolean; error?: { message: string } };
      if (!response.ok || !payload.ok) throw new Error(payload.error?.message || "The document could not be removed.");
      onChanged(`${document.name} removed${deleteFile ? " with its managed file" : " from the library"}.`);
    } catch (caught: unknown) { setError(caught instanceof Error ? caught.message : "The document could not be removed."); } finally { setSaving(false); }
  };

  return <div className="composer-backdrop quick-add-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <aside className="quick-add-panel document-panel" role="dialog" aria-modal="true" aria-labelledby="document-panel-title">
      <div className="quick-add-heading"><div><span>Document library</span><h2 id="document-panel-title">{document ? "Edit document" : "Upload document"}</h2><p>{document ? document.name : "Store a local copy and connect it to the work it supports."}</p></div><button className="icon-button" onClick={onClose} aria-label="Close document form"><X size={20} /></button></div>
      <div className="interaction-context"><ShieldCheck size={18} /><div><strong>{document?.managed ? "Managed by HustleNest" : "Saved to this computer"}</strong><span>{document ? "Metadata changes preserve the underlying file." : "Uploads are copied into HustleNest’s managed document folder."}</span></div></div>
      <form className="quick-add-form" onSubmit={submit}>
        {!document ? <label className={file ? "document-drop has-file" : "document-drop"}><FileUp size={24} /><strong>{file?.name || "Choose a document"}</strong><span>{file ? `${(file.size / 1024 / 1024).toFixed(2)} MB selected` : "PDF, image, spreadsheet, archive, or other business file · 20 MB maximum"}</span><input type="file" onChange={(event) => setFile(event.target.files?.[0] ?? null)} required /></label> : null}
        <label><span>Category *</span><input value={category} onChange={(event) => setCategory(event.target.value)} required placeholder="Invoice, contract, receipt…" /></label>
        <label><span>Description</span><textarea rows={3} value={description} onChange={(event) => setDescription(event.target.value)} placeholder="What is this file for?" /></label>
        <label><span>Tags</span><input value={tags} onChange={(event) => setTags(event.target.value)} placeholder="approved, 2026, customer copy" /></label>
        <section className="document-link-fields"><div><Link2 size={17} /><span><strong>Linked business record</strong><small>Optional · makes the file easier to find in context.</small></span></div><div className="quick-form-pair"><label><span>Record type</span><select value={entityType} onChange={(event) => { setEntityType(event.target.value); setEntityId(""); }}><option value="general">General business</option><option value="order">Order</option><option value="customer">Customer</option><option value="product">Product</option><option value="material">Material</option><option value="vendor">Vendor</option></select></label>{entityType !== "general" ? <label><span>Record *</span><select value={entityId} onChange={(event) => setEntityId(event.target.value)} required><option value="">Choose a record</option>{records.map((record) => <option value={record.id} key={record.id}>{record.label} · {record.detail}</option>)}</select></label> : null}</div></section>
        {document && deleteArmed ? <section className="document-delete-choice"><strong>Remove this document?</strong><span>The library record will be deleted.</span>{document.managed ? <label className="setting-check"><input type="checkbox" checked={deleteFile} onChange={(event) => setDeleteFile(event.target.checked)} /><span><strong>Also delete the managed file</strong><small>Turn this off to keep the file on this computer.</small></span></label> : <small>The external file will remain untouched.</small>}</section> : null}
        {error ? <p className="quick-add-error" role="alert">{error}</p> : null}
        <div className="quick-add-actions document-actions">{document ? (!deleteArmed ? <button type="button" className="danger-text-button" onClick={() => setDeleteArmed(true)}><Trash2 size={14} /> Remove</button> : <button type="button" className="danger-button" onClick={() => void remove()} disabled={saving}>Confirm remove</button>) : null}<span /><button type="button" className="secondary-button" onClick={onClose}>Cancel</button><button className="primary-button" disabled={saving}>{saving ? "Saving…" : document ? "Save changes" : "Upload file"}</button></div>
      </form>
    </aside>
  </div>;
}
