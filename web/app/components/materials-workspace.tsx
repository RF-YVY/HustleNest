import {
  Boxes,
  ChevronRight,
  CircleAlert,
  Factory,
  History,
  MapPin,
  PackageCheck,
  PackagePlus,
  Pencil,
  Search,
  Truck,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { getBridgeData } from "../lib/hustlenest";
import type { MaterialDetail, MaterialOption } from "../lib/hustlenest";

const money = (value: string | number) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(value));

function quantity(value: number) {
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(value);
}

export function MaterialsWorkspace({ materials, focusMaterialId, onEdit, onAdjust }: { materials: MaterialOption[]; focusMaterialId?: number | null; onEdit: (material: MaterialOption) => void; onAdjust: (material: MaterialOption) => void }) {
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<"all" | "attention">("all");
  const [selectedId, setSelectedId] = useState<number | null>(focusMaterialId ?? materials[0]?.id ?? null);
  const [detail, setDetail] = useState<MaterialDetail | null>(null);
  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    return materials.filter((material) => {
      if (filter === "attention" && material.stock_status === "healthy") return false;
      return !term || [material.sku, material.name, material.category, material.description, material.vendor?.name ?? ""].join(" ").toLowerCase().includes(term);
    });
  }, [filter, materials, search]);
  const selected = materials.find((material) => material.id === selectedId) ?? filtered[0] ?? materials[0];

  useEffect(() => {
    if (!selected?.id) return;
    const controller = new AbortController();
    getBridgeData<MaterialDetail>(`/api/materials/${selected.id}`, controller.signal)
      .then(setDetail)
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setDetail(null);
      });
    return () => controller.abort();
  }, [selected?.id]);

  const current = detail?.id === selected?.id ? detail : selected;
  const inventoryValue = materials.reduce((sum, material) => sum + Number(material.inventory_value), 0);
  const attentionCount = materials.filter((material) => material.stock_status !== "healthy").length;
  const vendorCount = new Set(materials.map((material) => material.vendor?.id).filter(Boolean)).size;

  return (
    <div className="workspace entity-page materials-page">
      <div className="page-heading">
        <div><div className="eyebrow"><span>Inventory</span><ChevronRight size={14} /><span>Materials</span></div><h1>Materials</h1><p>Know what is available, what it costs, and what needs replenishing.</p></div>{current ? <div className="page-actions"><button className="secondary-button" onClick={() => onEdit(current)}><Pencil size={16} /> Edit material</button><button className="primary-button" onClick={() => onAdjust(current)}><PackagePlus size={16} /> Adjust stock</button></div> : null}
      </div>
      <section className="material-metrics" aria-label="Material inventory summary">
        <article><Boxes size={19} /><div><span>Active materials</span><strong>{materials.length}</strong></div></article>
        <article><CircleAlert size={19} /><div><span>Needs attention</span><strong>{attentionCount}</strong></div></article>
        <article><PackageCheck size={19} /><div><span>Inventory value</span><strong>{money(inventoryValue)}</strong></div></article>
        <article><Truck size={19} /><div><span>Active vendors</span><strong>{vendorCount}</strong></div></article>
      </section>
      <section className="entity-workspace material-workspace">
        <div className="entity-list-panel">
          <div className="material-toolbar">
            <label className="entity-search"><Search size={17} /><input aria-label="Search materials" placeholder="Search material, SKU, category, or vendor…" value={search} onChange={(event) => setSearch(event.target.value)} /></label>
            <div className="mini-tabs"><button className={filter === "all" ? "active" : ""} onClick={() => setFilter("all")}>All</button><button className={filter === "attention" ? "active" : ""} onClick={() => setFilter("attention")}>Needs attention</button></div>
          </div>
          <div className="entity-list-heading"><span>{filtered.length} materials</span><span>On hand</span></div>
          <div className="entity-rows">
            {filtered.map((material) => (
              <button className={material.id === selected?.id ? "entity-row selected" : "entity-row"} onClick={() => setSelectedId(material.id)} key={material.id}>
                <span className={`material-mark stock-${material.stock_status}`}><Boxes size={17} /></span>
                <span><strong>{material.name}</strong><small>{material.sku} · {material.category || "Uncategorized"}</small></span>
                <em className={material.stock_status !== "healthy" ? "stock-low" : ""}>{quantity(material.quantity_on_hand)} {material.unit_of_measure}</em>
              </button>
            ))}
            {!filtered.length ? <div className="empty-state"><Boxes size={24} /><strong>No materials found</strong><span>Try another term or inventory filter.</span></div> : null}
          </div>
        </div>
        <aside className="entity-detail">
          {current ? (
            <>
              <div className="entity-hero"><div className={`material-mark entity-avatar stock-${current.stock_status}`}><Boxes size={24} /></div><div><span>{current.sku}</span><h2>{current.name}</h2><p>{current.description || current.category || "No material description yet."}</p></div></div>
              <div className="entity-stat-grid three"><div><span>On hand</span><strong>{quantity(current.quantity_on_hand)} {current.unit_of_measure}</strong></div><div><span>Reorder at</span><strong>{quantity(current.reorder_point)}</strong></div><div><span>Value</span><strong>{money(current.inventory_value)}</strong></div></div>
              <div className={current.stock_status === "healthy" ? "inventory-callout" : "inventory-callout low"}>{current.stock_status === "healthy" ? <PackageCheck size={17} /> : <CircleAlert size={17} />}<div><strong>{current.stock_status === "reorder" ? "Reorder recommended" : current.stock_status === "low" ? "Stock is running low" : "Stock level is healthy"}</strong><span>{money(current.cost_per_unit)} per {current.unit_of_measure || "unit"} · {current.lead_time_days || 0} day lead time</span></div></div>
              <div className="detail-section"><div className="section-heading"><h3>Vendor</h3></div>{current.vendor ? <div className="vendor-card"><Factory size={18} /><div><strong>{current.vendor.name}</strong><span>{current.vendor.contact_name || current.vendor.email || current.vendor.phone || "No contact details"}</span></div></div> : <p className="quiet-empty"><MapPin size={14} /> No preferred vendor assigned.</p>}</div>
              <div className="detail-section"><div className="section-heading"><h3>Recent inventory activity</h3><span>{detail?.id === current.id ? detail.transactions.length : 0}</span></div>{detail?.id === current.id && detail.transactions.length ? detail.transactions.slice(0, 6).map((transaction) => <div className="transaction-row" key={transaction.id}><span className={transaction.quantity_delta >= 0 ? "transaction-positive" : "transaction-negative"}>{transaction.quantity_delta >= 0 ? "+" : ""}{quantity(transaction.quantity_delta)}</span><div><strong>{transaction.reason || "Inventory adjustment"}</strong><small>{new Date(transaction.transaction_date).toLocaleDateString()} {transaction.notes ? `· ${transaction.notes}` : ""}</small></div><em>{money(transaction.unit_cost)}</em></div>) : <p className="quiet-empty"><History size={14} /> No inventory transactions recorded.</p>}</div>
              {current.notes ? <div className="detail-section note-card"><div className="section-heading"><h3>Notes</h3></div><p>{current.notes}</p></div> : null}
            </>
          ) : <div className="empty-state"><Boxes size={24} /><strong>Select a material</strong></div>}
        </aside>
      </section>
    </div>
  );
}
