import {
  Boxes,
  ChevronRight,
  CircleAlert,
  CreditCard,
  ExternalLink,
  Factory,
  Mail,
  Pencil,
  Phone,
  Search,
  Truck,
  UserRound,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { getBridgeData } from "../lib/hustlenest";
import type { VendorDetail, VendorOption } from "../lib/hustlenest";

const money = (value: string | number) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(value));

export function VendorsWorkspace({
  vendors,
  onOpenMaterial,
  focusVendorId,
  onEdit,
}: {
  vendors: VendorOption[];
  onOpenMaterial: (materialId: number) => void;
  focusVendorId?: number | null;
  onEdit: (vendor: VendorOption) => void;
}) {
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(focusVendorId ?? vendors[0]?.id ?? null);
  const [detail, setDetail] = useState<VendorDetail | null>(null);
  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    return vendors.filter((vendor) => !term || [vendor.name, vendor.contact_name, vendor.email, vendor.phone, vendor.account_number].join(" ").toLowerCase().includes(term));
  }, [search, vendors]);
  const selected = vendors.find((vendor) => vendor.id === selectedId) ?? filtered[0] ?? vendors[0];

  useEffect(() => {
    if (!selected?.id) return;
    const controller = new AbortController();
    getBridgeData<VendorDetail>(`/api/vendors/${selected.id}`, controller.signal)
      .then(setDetail)
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setDetail(null);
      });
    return () => controller.abort();
  }, [selected?.id]);

  const current = detail?.id === selected?.id ? detail : selected;
  const linkedMaterials = vendors.reduce((sum, vendor) => sum + vendor.material_count, 0);
  const inventoryValue = vendors.reduce((sum, vendor) => sum + Number(vendor.inventory_value), 0);
  const reorderExposure = vendors.reduce((sum, vendor) => sum + vendor.reorder_count, 0);

  return (
    <div className="workspace entity-page vendors-page">
      <div className="page-heading">
        <div><div className="eyebrow"><span>Inventory</span><ChevronRight size={14} /><span>Vendors</span></div><h1>Vendors</h1><p>Keep supplier contacts, purchasing context, and material exposure together.</p></div>{current ? <button className="secondary-button" onClick={() => onEdit(current)}><Pencil size={16} /> Edit vendor</button> : null}
      </div>
      <section className="material-metrics" aria-label="Vendor summary">
        <article><Factory size={19} /><div><span>Active vendors</span><strong>{vendors.length}</strong></div></article>
        <article><CircleAlert size={19} /><div><span>Reorder exposure</span><strong>{reorderExposure}</strong></div></article>
        <article><Boxes size={19} /><div><span>Linked materials</span><strong>{linkedMaterials}</strong></div></article>
        <article><Truck size={19} /><div><span>Supplied inventory</span><strong>{money(inventoryValue)}</strong></div></article>
      </section>
      <section className="entity-workspace vendor-workspace">
        <div className="entity-list-panel">
          <label className="entity-search"><Search size={17} /><input aria-label="Search vendors" placeholder="Search vendor, contact, or account…" value={search} onChange={(event) => setSearch(event.target.value)} /></label>
          <div className="entity-list-heading"><span>{filtered.length} vendors</span><span>Materials</span></div>
          <div className="entity-rows">
            {filtered.map((vendor) => (
              <button className={vendor.id === selected?.id ? "entity-row selected" : "entity-row"} onClick={() => setSelectedId(vendor.id)} key={vendor.id}>
                <span className="vendor-mark"><Factory size={17} /></span>
                <span><strong>{vendor.name}</strong><small>{vendor.contact_name || vendor.email || vendor.phone || "Contact details pending"}</small></span>
                <em className={vendor.reorder_count ? "stock-low" : ""}>{vendor.material_count}</em>
              </button>
            ))}
            {!filtered.length ? <div className="empty-state"><Factory size={24} /><strong>No vendors found</strong><span>Try another company, contact, or account.</span></div> : null}
          </div>
        </div>
        <aside className="entity-detail">
          {current ? (
            <>
              <div className="entity-hero"><div className="vendor-mark entity-avatar"><Factory size={24} /></div><div><span>Supplier</span><h2>{current.name}</h2><p>{current.contact_name || "No primary contact assigned."}</p></div></div>
              <div className="entity-stat-grid three"><div><span>Materials</span><strong>{current.material_count}</strong></div><div><span>Inventory value</span><strong>{money(current.inventory_value)}</strong></div><div><span>Need reorder</span><strong>{current.reorder_count}</strong></div></div>
              <div className="detail-section customer-summary"><div className="section-heading"><h3>Contact and purchasing</h3></div><p><UserRound size={15} /> {current.contact_name || "No contact name"}</p><p><Mail size={15} /> {current.email || "No email on file"}</p><p><Phone size={15} /> {current.phone || "No phone on file"}</p><p><CreditCard size={15} /> {current.preferred_payment_method || "No preferred payment method"}</p>{current.account_number ? <p><Truck size={15} /> Account {current.account_number}</p> : null}{current.website ? <a className="vendor-link" href={current.website} target="_blank" rel="noreferrer"><ExternalLink size={14} /> Open vendor website</a> : null}</div>
              <div className="detail-section"><div className="section-heading"><h3>Supplied materials</h3><span>{detail?.id === current.id ? detail.materials.length : current.material_count}</span></div>{detail?.id === current.id && detail.materials.length ? detail.materials.map((material) => <button className="related-order related-material" onClick={() => onOpenMaterial(material.id)} key={material.id}><span className={`material-mark stock-${material.stock_status}`}><Boxes size={15} /></span><span><strong>{material.name}</strong><small>{material.sku} · {material.quantity_on_hand} {material.unit_of_measure} on hand</small></span><em>{money(material.inventory_value)}</em><ChevronRight size={15} /></button>) : <p className="quiet-empty">No active materials are assigned to this vendor.</p>}</div>
              {current.notes ? <div className="detail-section note-card"><div className="section-heading"><h3>Vendor notes</h3></div><p>{current.notes}</p></div> : null}
            </>
          ) : <div className="empty-state"><Factory size={24} /><strong>Select a vendor</strong></div>}
        </aside>
      </section>
    </div>
  );
}
