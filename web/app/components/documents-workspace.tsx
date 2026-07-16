import {
  Check,
  ChevronRight,
  Clipboard,
  Download,
  FileArchive,
  FileImage,
  FileSpreadsheet,
  Files,
  FileText,
  FolderOpen,
  Link2,
  Pencil,
  Plus,
  Search,
  Tags,
  TriangleAlert,
} from "lucide-react";
import { useMemo, useState } from "react";
import { bridgeUrl, type DocumentsWorkspaceData, type WorkspaceView } from "../lib/hustlenest";
import { DocumentPanel, type DocumentLinkOptions } from "./document-panel";

type DocumentItem = DocumentsWorkspaceData["documents"][number];
const imageExtensions = new Set(["JPG", "JPEG", "PNG", "GIF", "WEBP", "SVG"]);
const sheetExtensions = new Set(["XLS", "XLSX", "CSV", "ODS"]);
const archiveExtensions = new Set(["ZIP", "RAR", "7Z", "TAR"]);
const emptyDocuments: DocumentItem[] = [];
function DocumentTypeIcon({ extension, size }: { extension: string; size: number }) {
  if (imageExtensions.has(extension)) return <FileImage size={size} />;
  if (sheetExtensions.has(extension)) return <FileSpreadsheet size={size} />;
  if (archiveExtensions.has(extension)) return <FileArchive size={size} />;
  return <FileText size={size} />;
}
const formatSize = (bytes: number | null) => {
  if (bytes === null) return "Size unavailable";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
};

export function DocumentsWorkspace({
  data,
  onNavigate,
  onOpenOrder,
  onOpenMaterial,
  focusDocumentId,
  linkOptions,
  onChanged,
}: {
  data: DocumentsWorkspaceData | null;
  onNavigate: (view: WorkspaceView) => void;
  onOpenOrder: (id: number) => void;
  onOpenMaterial: (id: number) => void;
  focusDocumentId?: number | null;
  linkOptions: DocumentLinkOptions;
  onChanged: (message: string, id?: number) => void;
}) {
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("All categories");
  const [selectedId, setSelectedId] = useState<number | null>(focusDocumentId ?? null);
  const [copiedId, setCopiedId] = useState<number | null>(null);
  const [panelDocument, setPanelDocument] = useState<DocumentItem | "new" | null>(null);
  const [downloading, setDownloading] = useState(false);
  const documents = data?.documents ?? emptyDocuments;
  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    return documents.filter((item) => (category === "All categories" || item.category === category) && (!term || [item.name, item.category, item.description, item.tags.join(" "), item.entity.label, item.entity.detail].join(" ").toLowerCase().includes(term)));
  }, [category, documents, search]);
  const selected = documents.find((item) => item.id === selectedId) ?? filtered[0] ?? documents[0];
  const openEntity = (item: DocumentItem) => {
    if (!item.entity.target_view || !item.entity.id) return;
    if (item.entity.target_view === "orders") return onOpenOrder(item.entity.id);
    if (item.entity.target_view === "materials") return onOpenMaterial(item.entity.id);
    onNavigate(item.entity.target_view);
  };
  const copyPath = async (item: DocumentItem) => {
    try {
      await navigator.clipboard.writeText(item.path);
      setCopiedId(item.id);
      window.setTimeout(() => setCopiedId(null), 1800);
    } catch { setCopiedId(null); }
  };
  const download = async (item: DocumentItem) => {
    setDownloading(true);
    try {
      const response = await fetch(`${bridgeUrl}/api/documents/${item.id}/download`);
      if (!response.ok) {
        const payload = (await response.json()) as { error?: { message: string } };
        throw new Error(payload.error?.message || "The file could not be downloaded.");
      }
      const blob = await response.blob();
      const href = URL.createObjectURL(blob);
      const anchor = window.document.createElement("a");
      anchor.href = href; anchor.download = item.name; anchor.click(); URL.revokeObjectURL(href);
    } catch (caught: unknown) { onChanged(caught instanceof Error ? caught.message : "The file could not be downloaded."); } finally { setDownloading(false); }
  };
  return (
    <div className="workspace entity-page documents-page">
      <div className="page-heading"><div><div className="eyebrow"><span>Understand</span><ChevronRight size={14} /><span>Documents</span></div><h1>Documents</h1><p>Find business files by what they belong to, not only where they were saved.</p></div><button className="primary-button" onClick={() => setPanelDocument("new")}><Plus size={17} /> Upload document</button></div>
      <section className="material-metrics document-metrics" aria-label="Document summary">
        <article><Files size={19} /><div><span>Total files</span><strong>{data?.metrics.total ?? 0}</strong></div></article>
        <article><Link2 size={19} /><div><span>Linked records</span><strong>{data?.metrics.linked ?? 0}</strong></div></article>
        <article><Tags size={19} /><div><span>Categories</span><strong>{data?.metrics.category_count ?? 0}</strong></div></article>
        <article><TriangleAlert size={19} /><div><span>Missing locally</span><strong>{data?.metrics.missing ?? 0}</strong></div></article>
      </section>
      <section className="entity-workspace documents-workspace">
        <div className="entity-list-panel">
          <div className="document-toolbar"><label className="entity-search"><Search size={17} /><input aria-label="Search documents" placeholder="Search files, records, or tags…" value={search} onChange={(event) => setSearch(event.target.value)} /></label><select aria-label="Filter document category" value={category} onChange={(event) => setCategory(event.target.value)}><option>All categories</option>{data?.categories.map((item) => <option value={item.name} key={item.name}>{item.name} ({item.count})</option>)}</select></div>
          <div className="entity-list-heading"><span>{filtered.length} documents</span><span>Record</span></div>
          <div className="entity-rows">
            {filtered.map((item) => <button className={item.id === selected?.id ? "entity-row document-row selected" : "entity-row document-row"} onClick={() => setSelectedId(item.id)} key={item.id}><span className={item.exists ? "document-mark" : "document-mark missing"}><DocumentTypeIcon extension={item.extension} size={17} /></span><span><strong>{item.name}</strong><small>{item.category} · {formatSize(item.size_bytes)}{item.exists ? "" : " · File missing"}</small></span><em>{item.entity.label}</em></button>)}
            {!filtered.length ? <div className="empty-state"><Files size={24} /><strong>No documents found</strong><span>Try another file name, category, record, or tag.</span></div> : null}
          </div>
        </div>
        <aside className="entity-detail document-detail">
          {selected ? <>
            <div className="entity-hero"><div className={selected.exists ? "document-mark entity-avatar" : "document-mark missing entity-avatar"}><DocumentTypeIcon extension={selected.extension} size={24} /></div><div><span>{selected.extension} document</span><h2>{selected.name}</h2><p>{selected.category} · {formatSize(selected.size_bytes)}</p></div></div>
            <div className={selected.exists ? "file-health healthy" : "file-health missing"}>{selected.exists ? <Check size={15} /> : <TriangleAlert size={15} />}<span><strong>{selected.exists ? "Available on this computer" : "File location is unavailable"}</strong><small>{selected.exists ? "Download it here or copy the saved location below." : "The document record remains, but its saved file cannot currently be found."}</small></span></div>
            <div className="document-primary-actions"><button className="primary-button" onClick={() => void download(selected)} disabled={!selected.exists || downloading}><Download size={15} /> {downloading ? "Preparing…" : "Download"}</button><button className="secondary-button" onClick={() => setPanelDocument(selected)}><Pencil size={15} /> Edit details</button></div>
            <div className="detail-section"><div className="section-heading"><h3>Saved location</h3></div><div className="document-path"><FolderOpen size={15} /><code>{selected.path}</code></div><button className="secondary-button document-copy" onClick={() => void copyPath(selected)}>{copiedId === selected.id ? <Check size={15} /> : <Clipboard size={15} />}{copiedId === selected.id ? "Location copied" : "Copy file location"}</button></div>
            <div className="detail-section"><div className="section-heading"><h3>Linked business record</h3></div><button className="document-entity" onClick={() => openEntity(selected)} disabled={!selected.entity.target_view}><span className="document-mark"><Link2 size={16} /></span><span><strong>{selected.entity.label}</strong><small>{selected.entity.type} · {selected.entity.detail || "No additional detail"}</small></span>{selected.entity.target_view ? <ChevronRight size={15} /> : null}</button></div>
            {selected.description ? <div className="detail-section note-card"><div className="section-heading"><h3>Description</h3></div><p>{selected.description}</p></div> : null}
            {selected.tags.length ? <div className="detail-section"><div className="section-heading"><h3>Tags</h3></div><div className="finance-tags">{selected.tags.map((tag) => <span key={tag}><Tags size={12} />{tag}</span>)}</div></div> : null}
            <div className="detail-section document-metadata"><div className="section-heading"><h3>Record details</h3></div><p><span>Storage</span><strong>{selected.stored_at || "Local"}</strong></p><p><span>Added</span><strong>{selected.created_at ? new Date(selected.created_at).toLocaleDateString() : "Not recorded"}</strong></p><p><span>Checksum</span><strong>{selected.checksum || "Not recorded"}</strong></p></div>
          </> : <div className="empty-state"><Files size={24} /><strong>No documents yet</strong><span>Upload a file and connect it to the work it supports.</span><button className="primary-button" onClick={() => setPanelDocument("new")}><Plus size={15} /> Upload document</button></div>}
        </aside>
      </section>
      {panelDocument ? <DocumentPanel document={panelDocument === "new" ? undefined : panelDocument} options={linkOptions} onClose={() => setPanelDocument(null)} onChanged={(message, id) => { setPanelDocument(null); onChanged(message, id); }} /> : null}
    </div>
  );
}
