import { ArchiveRestore, ChevronRight, Package, Search, ShieldAlert, ShoppingBag, Trash2, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { bridgeUrl, getBridgeData } from "../lib/hustlenest";
import type { TrashWorkspaceData } from "../lib/hustlenest";

type TrashItem = TrashWorkspaceData["items"][number];
type Filter = "all" | "order" | "product";

export function TrashWorkspace({ onChanged }: { onChanged: (message: string) => void }) {
  const [data, setData] = useState<TrashWorkspaceData | null>(null);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [workingKey, setWorkingKey] = useState("");
  const [deleteCandidate, setDeleteCandidate] = useState<TrashItem | null>(null);
  const [emptyOpen, setEmptyOpen] = useState(false);
  const [emptyConfirmation, setEmptyConfirmation] = useState("");
  const [error, setError] = useState("");

  const refresh = async () => {
    try {
      setData(await getBridgeData<TrashWorkspaceData>("/api/trash"));
      setError("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Trash could not be loaded.");
    }
  };

  useEffect(() => {
    const controller = new AbortController();
    getBridgeData<TrashWorkspaceData>("/api/trash", controller.signal)
      .then((payload) => { setData(payload); setError(""); })
      .catch((caught) => {
        if (caught instanceof DOMException && caught.name === "AbortError") return;
        setError(caught instanceof Error ? caught.message : "Trash could not be loaded.");
      });
    return () => controller.abort();
  }, []);

  const visible = useMemo(() => {
    const term = search.trim().toLowerCase();
    return (data?.items ?? []).filter((item) => {
      if (filter !== "all" && item.type !== filter) return false;
      return !term || `${item.name} ${item.details} ${item.type}`.toLowerCase().includes(term);
    });
  }, [data, filter, search]);

  const mutateItem = async (item: TrashItem, action: "restore" | "delete") => {
    const key = `${item.type}-${item.id}-${action}`;
    setWorkingKey(key);
    setError("");
    try {
      const response = await fetch(`${bridgeUrl}/api/trash/${item.type}/${item.id}${action === "restore" ? "/restore" : ""}`, {
        method: action === "restore" ? "POST" : "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expected_revision: item.revision, confirm: action === "delete" }),
      });
      const payload = await response.json() as { ok: boolean; error?: { message: string } };
      if (!response.ok || !payload.ok) throw new Error(payload.error?.message || "Trash could not be updated.");
      setDeleteCandidate(null);
      await refresh();
      onChanged(action === "restore" ? `${item.name} restored.` : `${item.name} permanently deleted.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Trash could not be updated.");
    } finally { setWorkingKey(""); }
  };

  const emptyTrash = async () => {
    if (!data) return;
    setWorkingKey("empty");
    setError("");
    try {
      const response = await fetch(`${bridgeUrl}/api/trash`, {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirmation: emptyConfirmation, expected_count: data.metrics.total }),
      });
      const payload = await response.json() as { ok: boolean; data?: { deleted: number }; error?: { message: string } };
      if (!response.ok || !payload.ok || !payload.data) throw new Error(payload.error?.message || "Trash could not be emptied.");
      const count = payload.data.deleted;
      setEmptyOpen(false);
      setEmptyConfirmation("");
      await refresh();
      onChanged(`${count} ${count === 1 ? "item" : "items"} permanently deleted.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Trash could not be emptied.");
    } finally { setWorkingKey(""); }
  };

  return (
    <div className="workspace trash-page">
      <div className="page-heading">
        <div><div className="eyebrow"><span>Workspace</span><ChevronRight size={14} /><span>Trash</span></div><h1>Recently deleted</h1><p>Recover orders and products, or remove them permanently.</p></div>
        <button className="danger-button" disabled={!data?.metrics.total} onClick={() => setEmptyOpen(true)}><Trash2 size={16} /> Empty trash</button>
      </div>

      <section className="trash-metrics" aria-label="Trash summary">
        <article><Trash2 size={19} /><div><span>All items</span><strong>{data?.metrics.total ?? "—"}</strong></div></article>
        <article><ShoppingBag size={19} /><div><span>Orders</span><strong>{data?.metrics.orders ?? "—"}</strong></div></article>
        <article><Package size={19} /><div><span>Products</span><strong>{data?.metrics.products ?? "—"}</strong></div></article>
      </section>

      <div className="trash-safety-note"><ShieldAlert size={18} /><div><strong>Restoring is safe. Permanent deletion cannot be undone.</strong><span>Moving an order to trash does not change inventory; cancel it first when inventory should be returned.</span></div></div>
      {error ? <div className="workspace-error" role="alert">{error}</div> : null}

      <section className="trash-card">
        <div className="trash-toolbar">
          <label className="entity-search"><Search size={17} /><input aria-label="Search trash" placeholder="Search deleted orders or products…" value={search} onChange={(event) => setSearch(event.target.value)} /></label>
          <div className="filter-tabs" role="tablist" aria-label="Trash filters">
            {(["all", "order", "product"] as Filter[]).map((item) => <button role="tab" aria-selected={filter === item} className={filter === item ? "active" : ""} onClick={() => setFilter(item)} key={item}>{item === "all" ? "All" : item === "order" ? "Orders" : "Products"}</button>)}
          </div>
        </div>
        <div className="trash-list-heading"><span>Item</span><span>Deleted</span><span>Actions</span></div>
        <div className="trash-list">
          {visible.map((item) => {
            const Icon = item.type === "order" ? ShoppingBag : Package;
            const busy = workingKey.startsWith(`${item.type}-${item.id}-`);
            return <article className="trash-row" key={`${item.type}-${item.id}`}><span className={`trash-type ${item.type}`}><Icon size={18} /></span><div><strong>{item.name}</strong><span>{item.details}</span><small>{item.type === "order" ? "Order" : "Product"}</small></div><time dateTime={item.deleted_at}>{new Date(item.deleted_at).toLocaleString()}</time><div><button className="secondary-button" disabled={busy} onClick={() => void mutateItem(item, "restore")}><ArchiveRestore size={15} />{workingKey === `${item.type}-${item.id}-restore` ? "Restoring…" : "Restore"}</button><button className="icon-button trash-delete-button" aria-label={`Permanently delete ${item.name}`} disabled={busy} onClick={() => setDeleteCandidate(item)}><Trash2 size={16} /></button></div></article>;
          })}
          {data && !visible.length ? <div className="empty-state"><ArchiveRestore size={27} /><strong>{data.metrics.total ? "No matching deleted items" : "Trash is empty"}</strong><span>{data.metrics.total ? "Try another search or filter." : "Deleted orders and products will appear here."}</span></div> : null}
        </div>
      </section>

      {deleteCandidate ? <div className="composer-backdrop lifecycle-dialog-backdrop" role="presentation"><section className="lifecycle-dialog" role="alertdialog" aria-modal="true" aria-labelledby="permanent-delete-title"><button className="dialog-close" aria-label="Close" onClick={() => setDeleteCandidate(null)}><X size={18} /></button><span className="lifecycle-dialog-icon danger"><Trash2 size={22} /></span><h2 id="permanent-delete-title">Permanently delete {deleteCandidate.name}?</h2><p>This removes the {deleteCandidate.type} and its retained data. This action cannot be undone.</p><div><button className="secondary-button" onClick={() => setDeleteCandidate(null)} disabled={Boolean(workingKey)}>Keep item</button><button className="danger-button" onClick={() => void mutateItem(deleteCandidate, "delete")} disabled={Boolean(workingKey)}>{workingKey ? "Deleting…" : "Delete permanently"}</button></div></section></div> : null}

      {emptyOpen ? <div className="composer-backdrop lifecycle-dialog-backdrop" role="presentation"><section className="lifecycle-dialog empty-trash-dialog" role="alertdialog" aria-modal="true" aria-labelledby="empty-trash-title"><button className="dialog-close" aria-label="Close" onClick={() => setEmptyOpen(false)}><X size={18} /></button><span className="lifecycle-dialog-icon danger"><ShieldAlert size={22} /></span><h2 id="empty-trash-title">Empty all trash?</h2><p>This permanently deletes {data?.metrics.total ?? 0} items. Type <strong>EMPTY TRASH</strong> to continue.</p><label><span>Confirmation</span><input autoFocus value={emptyConfirmation} onChange={(event) => setEmptyConfirmation(event.target.value)} placeholder="EMPTY TRASH" /></label><div><button className="secondary-button" onClick={() => setEmptyOpen(false)} disabled={workingKey === "empty"}>Cancel</button><button className="danger-button" onClick={() => void emptyTrash()} disabled={emptyConfirmation.trim().toUpperCase() !== "EMPTY TRASH" || workingKey === "empty"}>{workingKey === "empty" ? "Deleting…" : "Empty trash"}</button></div></section></div> : null}
    </div>
  );
}
