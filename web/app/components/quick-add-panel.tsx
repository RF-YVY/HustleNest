"use client";

import { Boxes, CircleAlert, Factory, Package, Plus, ReceiptText, Repeat2, Trash2, UserRound, X } from "lucide-react";
import { FormEvent, useState } from "react";
import { bridgeUrl, type VendorOption } from "../lib/hustlenest";

export type QuickAddType = "customer" | "product" | "material" | "vendor" | "expense" | "recurring" | "loss";
export type EditableRecord = { id: number; type: "customer" | "product" | "material" | "vendor" | "expense" | "recurring" | "loss"; revision: string; values: Record<string, string> };

const choices = [
  { id: "customer" as const, label: "Customer", icon: UserRound },
  { id: "product" as const, label: "Product", icon: Package },
  { id: "material" as const, label: "Material", icon: Boxes },
  { id: "vendor" as const, label: "Vendor", icon: Factory },
  { id: "expense" as const, label: "Expense", icon: ReceiptText },
  { id: "recurring" as const, label: "Recurring", icon: Repeat2 },
  { id: "loss" as const, label: "Loss", icon: CircleAlert },
];

const today = () => new Date().toLocaleDateString("en-CA");

function initialValues(type: QuickAddType): Record<string, string> {
  if (type === "recurring") return { category: "", amount: "", frequency: "monthly", start_date: today(), next_occurrence: today(), end_date: "", auto_record: "false", vendor_id: "", notes: "" };
  if (type === "expense" || type === "loss") return { category: "", amount: "", date: today(), description: "", notes: "", vendor_id: "", payment_method: "" };
  if (type === "product") return { sku: "", name: "", description: "", inventory_count: "0", unit_cost: "0", unit_price: "0", status: "Available", cost_components: "[]" };
  if (type === "material") return { sku: "", name: "", category: "", unit_of_measure: "each", quantity_on_hand: "0", reorder_point: "0", cost_per_unit: "0", vendor_id: "", description: "", notes: "" };
  if (type === "vendor") return { name: "", contact_name: "", email: "", phone: "", website: "", account_number: "", preferred_payment_method: "", notes: "" };
  return { name: "", company: "", email: "", phone: "", address: "", notes: "" };
}

export function QuickAddPanel({ initialType = "customer", editRecord, vendors, onClose, onSaved, onDeleted }: { initialType?: QuickAddType; editRecord?: EditableRecord | null; vendors: VendorOption[]; onClose: () => void; onSaved: (type: QuickAddType, id: number, label: string) => void; onDeleted: (type: QuickAddType, id: number) => void }) {
  const [type, setType] = useState<QuickAddType>(editRecord?.type ?? initialType);
  const [values, setValues] = useState<Record<string, string>>(() => ({ ...initialValues(editRecord?.type ?? initialType), ...(editRecord?.values ?? {}) }));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [deleteArmed, setDeleteArmed] = useState(false);
  const set = (field: string, value: string) => setValues((current) => ({ ...current, [field]: value }));
  const costComponents = (() => { try { const parsed = JSON.parse(values.cost_components || "[]"); return Array.isArray(parsed) ? parsed as Array<{ label: string; amount: string }> : []; } catch { return []; } })();
  const setCostComponents = (components: Array<{ label: string; amount: string }>) => set("cost_components", JSON.stringify(components));
  const switchType = (next: QuickAddType) => { setType(next); setValues(initialValues(next)); setError(""); };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const url = editRecord ? `${bridgeUrl}/api/records/${editRecord.type}/${editRecord.id}` : `${bridgeUrl}/api/quick-add`;
      const response = await fetch(url, { method: editRecord ? "PUT" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(editRecord ? { values, expected_revision: editRecord.revision } : { type, values }) });
      const payload = (await response.json()) as { ok: boolean; data?: { id: number; label: string }; error?: { message: string } };
      if (!response.ok || !payload.ok || !payload.data) throw new Error(payload.error?.message || "This record could not be saved.");
      onSaved(type, payload.data.id, payload.data.label);
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "This record could not be saved.");
    } finally {
      setSaving(false);
    }
  };

  const deleteRecord = async () => {
    if (!editRecord) return;
    setSaving(true);
    setError("");
    try {
      const response = await fetch(`${bridgeUrl}/api/records/${editRecord.type}/${editRecord.id}`, { method: "DELETE", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expected_revision: editRecord.revision }) });
      const payload = (await response.json()) as { ok: boolean; error?: { message: string } };
      if (!response.ok || !payload.ok) throw new Error(payload.error?.message || "This record could not be deleted.");
      onDeleted(editRecord.type, editRecord.id);
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "This record could not be deleted.");
      setDeleteArmed(false);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="composer-backdrop quick-add-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <aside className="quick-add-panel" role="dialog" aria-modal="true" aria-labelledby="quick-add-title">
        <div className="quick-add-heading"><div><span>{editRecord ? "Update record" : "Keep work moving"}</span><h2 id="quick-add-title">{editRecord ? `Edit ${type}` : "Quick add"}</h2></div><button className="icon-button" onClick={onClose} aria-label="Close record form"><X size={20} /></button></div>
        {!editRecord ? <div className="quick-add-types" aria-label="Record type">{choices.map(({ id, label, icon: Icon }) => <button type="button" className={type === id ? "active" : ""} onClick={() => switchType(id)} key={id}><Icon size={17} /><span>{label}</span></button>)}</div> : <div className="quick-add-edit-type">Changes save to the same local record and appear everywhere it is used.</div>}
        <form className="quick-add-form" onSubmit={submit}>
          {type === "customer" ? <>
            <label><span>Customer name *</span><input autoFocus value={values.name} onChange={(event) => set("name", event.target.value)} required /></label>
            <label><span>Company</span><input value={values.company} onChange={(event) => set("company", event.target.value)} /></label>
            <div className="quick-form-pair"><label><span>Email</span><input type="email" value={values.email} onChange={(event) => set("email", event.target.value)} /></label><label><span>Phone</span><input value={values.phone} onChange={(event) => set("phone", event.target.value)} /></label></div>
            <label><span>Address</span><textarea rows={2} value={values.address} onChange={(event) => set("address", event.target.value)} /></label>
          </> : null}
          {type === "product" ? <>
            <div className="quick-form-pair"><label><span>SKU *</span><input autoFocus value={values.sku} onChange={(event) => set("sku", event.target.value)} required /></label><label><span>Product name *</span><input value={values.name} onChange={(event) => set("name", event.target.value)} required /></label></div>
            <label><span>Description</span><textarea rows={2} value={values.description} onChange={(event) => set("description", event.target.value)} /></label>
            <div className="quick-form-triple"><label><span>Starting stock</span><input type="number" min="0" step="1" value={values.inventory_count} onChange={(event) => set("inventory_count", event.target.value)} /></label><label><span>Unit cost</span><input type="number" min="0" step="0.01" value={values.unit_cost} onChange={(event) => set("unit_cost", event.target.value)} /></label><label><span>Sale price</span><input type="number" min="0" step="0.01" value={values.unit_price} onChange={(event) => set("unit_price", event.target.value)} /></label></div>
            <label><span>Product status</span><select value={values.status} onChange={(event) => set("status", event.target.value)}><option>Ordered</option><option>Available</option><option>Out of Stock</option><option>Discontinued</option></select></label>
            <fieldset className="cost-component-editor"><legend>Extra unit costs</legend>{costComponents.map((component, index) => <div key={index}><input aria-label={`Cost ${index + 1} label`} placeholder="Packaging, labor…" value={component.label} onChange={(event) => setCostComponents(costComponents.map((item, row) => row === index ? { ...item, label: event.target.value } : item))} /><input aria-label={`Cost ${index + 1} amount`} type="number" min="0" step="0.01" placeholder="0.00" value={component.amount} onChange={(event) => setCostComponents(costComponents.map((item, row) => row === index ? { ...item, amount: event.target.value } : item))} /><button type="button" className="icon-button" aria-label={`Remove cost ${index + 1}`} onClick={() => setCostComponents(costComponents.filter((_item, row) => row !== index))}><Trash2 size={15} /></button></div>)}<button type="button" className="secondary-button" onClick={() => setCostComponents([...costComponents, { label: "", amount: "0" }])} disabled={costComponents.length >= 20}><Plus size={14} /> Add extra cost</button></fieldset>
          </> : null}
          {type === "material" ? <>
            <div className="quick-form-pair"><label><span>SKU *</span><input autoFocus value={values.sku} onChange={(event) => set("sku", event.target.value)} required /></label><label><span>Material name *</span><input value={values.name} onChange={(event) => set("name", event.target.value)} required /></label></div>
            <div className="quick-form-pair"><label><span>Category</span><input value={values.category} onChange={(event) => set("category", event.target.value)} /></label><label><span>Unit</span><input value={values.unit_of_measure} onChange={(event) => set("unit_of_measure", event.target.value)} placeholder="each, ft, oz…" /></label></div>
            <div className="quick-form-triple"><label><span>On hand</span><input type="number" min="0" step="0.01" value={values.quantity_on_hand} onChange={(event) => set("quantity_on_hand", event.target.value)} /></label><label><span>Reorder at</span><input type="number" min="0" step="0.01" value={values.reorder_point} onChange={(event) => set("reorder_point", event.target.value)} /></label><label><span>Cost / unit</span><input type="number" min="0" step="0.01" value={values.cost_per_unit} onChange={(event) => set("cost_per_unit", event.target.value)} /></label></div>
            <VendorField vendors={vendors} value={values.vendor_id} onChange={(value) => set("vendor_id", value)} />
          </> : null}
          {type === "vendor" ? <>
            <label><span>Vendor name *</span><input autoFocus value={values.name} onChange={(event) => set("name", event.target.value)} required /></label>
            <label><span>Contact name</span><input value={values.contact_name} onChange={(event) => set("contact_name", event.target.value)} /></label>
            <div className="quick-form-pair"><label><span>Email</span><input type="email" value={values.email} onChange={(event) => set("email", event.target.value)} /></label><label><span>Phone</span><input value={values.phone} onChange={(event) => set("phone", event.target.value)} /></label></div>
            <label><span>Website</span><input type="url" value={values.website} onChange={(event) => set("website", event.target.value)} /></label>
            <div className="quick-form-pair"><label><span>Account number</span><input value={values.account_number} onChange={(event) => set("account_number", event.target.value)} /></label><label><span>Preferred payment</span><input value={values.preferred_payment_method} onChange={(event) => set("preferred_payment_method", event.target.value)} /></label></div>
          </> : null}
          {type === "recurring" ? <>
            <div className="quick-form-pair"><label><span>Category *</span><input autoFocus value={values.category} onChange={(event) => set("category", event.target.value)} required placeholder="Rent, software, insurance…" /></label><label><span>Amount *</span><input type="number" min="0.01" step="0.01" value={values.amount} onChange={(event) => set("amount", event.target.value)} required /></label></div>
            <label><span>Frequency *</span><select value={values.frequency} onChange={(event) => set("frequency", event.target.value)}><option value="daily">Daily</option><option value="weekly">Weekly</option><option value="biweekly">Biweekly</option><option value="monthly">Monthly</option><option value="quarterly">Quarterly</option><option value="yearly">Yearly</option></select></label>
            <div className="quick-form-pair"><label><span>Start date *</span><input type="date" value={values.start_date} onChange={(event) => set("start_date", event.target.value)} required /></label><label><span>Next occurrence *</span><input type="date" value={values.next_occurrence} onChange={(event) => set("next_occurrence", event.target.value)} required /></label></div>
            <label><span>End date</span><input type="date" value={values.end_date} onChange={(event) => set("end_date", event.target.value)} /></label>
            <VendorField vendors={vendors} value={values.vendor_id} onChange={(value) => set("vendor_id", value)} />
            <label className="setting-check"><input type="checkbox" checked={values.auto_record === "true"} onChange={(event) => set("auto_record", String(event.target.checked))} /><span>Automatically record when due</span></label>
          </> : null}
          {type === "expense" || type === "loss" ? <>
            <div className="quick-form-pair"><label><span>Category *</span><input autoFocus value={values.category} onChange={(event) => set("category", event.target.value)} required placeholder={type === "expense" ? "Supplies, shipping…" : "Damage, waste…"} /></label><label><span>Amount *</span><input type="number" min="0.01" step="0.01" value={values.amount} onChange={(event) => set("amount", event.target.value)} required /></label></div>
            <label><span>Date *</span><input type="date" value={values.date} onChange={(event) => set("date", event.target.value)} required /></label>
            <label><span>Description</span><input value={values.description} onChange={(event) => set("description", event.target.value)} /></label>
            {type === "expense" ? <><VendorField vendors={vendors} value={values.vendor_id} onChange={(value) => set("vendor_id", value)} /><label><span>Payment method</span><input value={values.payment_method} onChange={(event) => set("payment_method", event.target.value)} /></label></> : null}
          </> : null}
          <label><span>Notes</span><textarea rows={3} value={values.notes ?? ""} onChange={(event) => set("notes", event.target.value)} /></label>
          {error ? <p className="quick-add-error" role="alert">{error}</p> : null}
          <div className="quick-add-actions">{editRecord ? (!deleteArmed ? <button type="button" className="danger-text-button" onClick={() => setDeleteArmed(true)}><Trash2 size={14} /> {type === "product" ? "Move to trash" : "Delete"}</button> : <button type="button" className="danger-button" onClick={() => void deleteRecord()} disabled={saving}>Confirm {type === "product" ? "move" : "delete"}</button>) : null}<span /><button type="button" className="secondary-button" onClick={onClose}>Cancel</button><button className="primary-button" disabled={saving}>{saving ? "Saving…" : editRecord ? "Save changes" : `Save ${type}`}</button></div>
        </form>
      </aside>
    </div>
  );
}

function VendorField({ vendors, value, onChange }: { vendors: VendorOption[]; value: string; onChange: (value: string) => void }) {
  return <label><span>Vendor</span><select value={value} onChange={(event) => onChange(event.target.value)}><option value="">No vendor</option>{vendors.map((vendor) => <option value={vendor.id} key={vendor.id}>{vendor.name}</option>)}</select></label>;
}
