/* eslint-disable @next/next/no-img-element -- product images are served by the loopback Python backend, not the site asset pipeline */
import { Boxes, Camera, ChevronRight, CircleAlert, ImageOff, Package, Pencil, Plus, Search, ShoppingBag, Trash2, TrendingUp, X } from "lucide-react";
import { useMemo, useState } from "react";
import { bridgeUrl } from "../lib/hustlenest";
import type { Order, ProductOption } from "../lib/hustlenest";

const money = (value: string | number) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(value));

export function ProductsWorkspace({
  products,
  orders,
  onCreateOrder,
  onOpenOrder,
  onEdit,
  onTrash,
  onChanged,
  focusProductId,
}: {
  products: ProductOption[];
  orders: Order[];
  onCreateOrder: (product: ProductOption) => void;
  onOpenOrder: (orderId: number) => void;
  onEdit: (product: ProductOption) => void;
  onTrash: (product: ProductOption) => void;
  onChanged: (message: string) => void;
  focusProductId?: number | null;
}) {
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(focusProductId ?? products[0]?.id ?? null);
  const [photoBusy, setPhotoBusy] = useState(false);
  const [removePhoto, setRemovePhoto] = useState(false);
  const [photoError, setPhotoError] = useState("");
  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    return products.filter((product) => !term || [product.sku, product.name, product.description, product.status].join(" ").toLowerCase().includes(term));
  }, [products, search]);
  const selected = products.find((product) => product.id === selectedId) ?? filtered[0] ?? products[0];
  const relatedOrders = selected ? orders.filter((order) => order.items.some((item) => item.productId === selected.id || item.sku === selected.sku)) : [];
  const unitsSold = selected ? relatedOrders.reduce((sum, order) => sum + order.items.filter((item) => item.productId === selected.id || item.sku === selected.sku).reduce((lineSum, item) => lineSum + item.quantity, 0), 0) : 0;

  const mutatePhoto = async (file?: File) => {
    if (!selected) return;
    setPhotoBusy(true); setPhotoError("");
    try {
      let body: Record<string, unknown> = { expected_revision: selected.revision };
      if (file) {
        if (file.size > 8 * 1024 * 1024) throw new Error("Product images must be 8 MB or smaller.");
        const content = await new Promise<string>((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result).split(",", 2)[1] || ""); reader.onerror = () => reject(new Error("The product image could not be read.")); reader.readAsDataURL(file); });
        body = { ...body, file: { name: file.name, content_base64: content } };
      }
      const response = await fetch(`${bridgeUrl}/api/products/${selected.id}/photo`, { method: file ? "POST" : "DELETE", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const payload = await response.json() as { ok: boolean; error?: { message: string } };
      if (!response.ok || !payload.ok) throw new Error(payload.error?.message || "The product image could not be updated.");
      setRemovePhoto(false);
      onChanged(file ? `${selected.name} photo updated.` : `${selected.name} photo removed.`);
    } catch (caught) { setPhotoError(caught instanceof Error ? caught.message : "The product image could not be updated."); }
    finally { setPhotoBusy(false); }
  };

  return (
    <div className="workspace entity-page">
      <div className="page-heading">
        <div><div className="eyebrow"><span>Inventory</span><ChevronRight size={14} /><span>Products</span></div><h1>Products</h1><p>See stock, pricing, and sales context in one place.</p></div>
        {selected ? <div className="page-actions"><button className="secondary-button" onClick={() => onEdit(selected)}><Pencil size={16} /> Edit</button><button className="primary-button" onClick={() => onCreateOrder(selected)}><Plus size={17} /> Add to order</button></div> : null}
      </div>
      <section className="entity-workspace">
        <div className="entity-list-panel">
          <label className="entity-search"><Search size={17} /><input aria-label="Search products" placeholder="Search SKU, product, or status…" value={search} onChange={(event) => setSearch(event.target.value)} /></label>
          <div className="entity-list-heading"><span>{filtered.length} products</span><span>Stock</span></div>
          <div className="entity-rows">
            {filtered.map((product) => (
              <button className={product.id === selected?.id ? "entity-row selected" : "entity-row"} onClick={() => setSelectedId(product.id)} key={product.id}>
                <span className="product-thumb"><Package size={17} /></span>
                <span><strong>{product.name}</strong><small>{product.sku} · {money(product.unit_price)}</small></span>
                <em className={product.inventory_count <= 2 ? "stock-low" : ""}>{product.inventory_count}</em>
              </button>
            ))}
            {!filtered.length ? <div className="empty-state"><Boxes size={24} /><strong>No products found</strong><span>Try another SKU, name, or status.</span></div> : null}
          </div>
        </div>
        <aside className="entity-detail">
          {selected ? (
            <>
              <div className="entity-hero product-hero"><div className="product-photo">{selected.photo_available ? <img src={`${bridgeUrl}/api/products/${selected.id}/photo?v=${selected.revision}`} alt="" /> : <ImageOff size={24} />}<label className="product-photo-upload"><Camera size={14} /><span>{selected.photo_available ? "Replace" : "Add photo"}</span><input type="file" accept="image/png,image/jpeg,image/gif,image/webp" disabled={photoBusy} onChange={(event) => { const file = event.target.files?.[0]; if (file) void mutatePhoto(file); event.target.value = ""; }} /></label></div><div><span>{selected.sku}</span><h2>{selected.name}</h2><p>{selected.description || "No product description yet."}</p>{selected.photo_available ? <button className="remove-product-photo" onClick={() => setRemovePhoto(true)}><Trash2 size={13} /> Remove photo</button> : null}</div></div>
              {photoError ? <div className="workspace-error" role="alert">{photoError}</div> : null}
              <div className="entity-stat-grid three"><div><span>In stock</span><strong>{selected.inventory_count}</strong></div><div><span>Price</span><strong>{money(selected.unit_price)}</strong></div><div><span>Margin</span><strong>{Number(selected.unit_price) > 0 ? `${(((Number(selected.unit_price) - Number(selected.unit_cost)) / Number(selected.unit_price)) * 100).toFixed(0)}%` : "—"}</strong></div></div>
              <div className={selected.forecast.needs_reorder ? "product-forecast-alert attention" : "product-forecast-alert"}><TrendingUp size={17} /><div><strong>{selected.forecast.needs_reorder ? "Reorder planning needed" : "Stock outlook"}</strong><span>{selected.forecast.average_weekly_sales.toFixed(1)} sold weekly · {selected.forecast.days_until_stockout === null ? "No stockout projected" : `${selected.forecast.days_until_stockout} days until stockout`}</span></div></div>
              <div className={selected.inventory_count <= 2 ? "inventory-callout low" : "inventory-callout"}>{selected.inventory_count <= 2 ? <CircleAlert size={17} /> : <TrendingUp size={17} />}<div><strong>{selected.inventory_count <= 2 ? "Low stock" : "Inventory available"}</strong><span>{unitsSold} units represented in loaded orders</span></div></div>
              <div className="detail-section product-cost-breakdown"><div className="section-heading"><h3>Total unit cost</h3><strong>{money(selected.unit_cost)}</strong></div><p><span>Base cost</span><strong>{money(selected.base_unit_cost)}</strong></p><p><span>Linked materials</span><strong>{money(selected.material_unit_cost)}</strong></p>{selected.cost_components.map((component, index) => <p key={`${component.label}-${index}`}><span>{component.label}</span><strong>{money(component.amount)}</strong></p>)}{!selected.cost_components.length ? <p className="quiet-empty">No extra labor or overhead costs configured.</p> : null}</div>
              <div className="detail-section"><div className="section-heading"><h3>Materials used</h3><span>{selected.materials.length}</span></div>{selected.materials.map((material) => <div className="transaction-row" key={material.material_id}><Boxes size={15} /><div><strong>{material.name}</strong><small>{material.sku} · {material.quantity_required} {material.unit_of_measure || "units"} per product · {material.include_in_unit_cost ? "Direct material" : "Track only"}</small></div><em>{material.include_in_unit_cost ? money(material.cost_per_product) : "Excluded"}</em></div>)}{!selected.materials.length ? <p className="quiet-empty">No materials linked. Edit this product to add what it uses.</p> : null}</div>
              <div className="detail-section"><div className="section-heading"><h3>Recent orders</h3><span>{relatedOrders.length}</span></div>{relatedOrders.slice(0, 5).map((order) => <button className="related-order" onClick={() => onOpenOrder(order.id)} key={order.id}><ShoppingBag size={15} /><span><strong>{order.number}</strong><small>{order.customer} · {order.date}</small></span><em>{money(order.total)}</em><ChevronRight size={15} /></button>)}{!relatedOrders.length ? <p className="quiet-empty">No loaded orders contain this product yet.</p> : null}</div>
              <button className="primary-button entity-primary" onClick={() => onCreateOrder(selected)}><Plus size={17} /> Start order with {selected.name}</button>
              <button className="entity-trash-action" onClick={() => onTrash(selected)}><Trash2 size={15} /> Move product to trash</button>
            </>
          ) : <div className="empty-state"><Package size={24} /><strong>Select a product</strong></div>}
        </aside>
      </section>
      {removePhoto && selected ? <div className="composer-backdrop lifecycle-dialog-backdrop" role="presentation"><section className="lifecycle-dialog" role="alertdialog" aria-modal="true" aria-labelledby="remove-product-photo-title"><button className="dialog-close" aria-label="Close" onClick={() => setRemovePhoto(false)}><X size={18} /></button><span className="lifecycle-dialog-icon danger"><Trash2 size={22} /></span><h2 id="remove-product-photo-title">Remove {selected.name}&apos;s photo?</h2><p>The managed image file will be deleted. You can upload a new image later.</p><div><button className="secondary-button" onClick={() => setRemovePhoto(false)} disabled={photoBusy}>Keep photo</button><button className="danger-button" onClick={() => void mutatePhoto()} disabled={photoBusy}>{photoBusy ? "Removing…" : "Remove photo"}</button></div></section></div> : null}
    </div>
  );
}
