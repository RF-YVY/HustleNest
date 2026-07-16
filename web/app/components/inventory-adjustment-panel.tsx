"use client";

import { ClipboardCheck, PackageMinus, PackagePlus, X } from "lucide-react";
import { FormEvent, useMemo, useState } from "react";
import { bridgeUrl, type MaterialDetail, type MaterialOption } from "../lib/hustlenest";

type AdjustmentAction = "receive" | "consume" | "count";

const actions = [
  { id: "receive" as const, label: "Receive", detail: "Add delivered stock", icon: PackagePlus },
  { id: "consume" as const, label: "Use", detail: "Record material used", icon: PackageMinus },
  { id: "count" as const, label: "Count", detail: "Set the counted total", icon: ClipboardCheck },
];

const quantity = (value: number) => new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(value);

export function InventoryAdjustmentPanel({ material, onClose, onSaved }: { material: MaterialOption; onClose: () => void; onSaved: (material: MaterialDetail) => void }) {
  const [action, setAction] = useState<AdjustmentAction>("receive");
  const [amount, setAmount] = useState("");
  const [unitCost, setUnitCost] = useState(material.cost_per_unit);
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const numericAmount = Number(amount || 0);
  const projected = useMemo(() => action === "receive" ? material.quantity_on_hand + numericAmount : action === "consume" ? material.quantity_on_hand - numericAmount : numericAmount, [action, material.quantity_on_hand, numericAmount]);
  const amountLabel = action === "receive" ? "Quantity received" : action === "consume" ? "Quantity used" : "Counted quantity on hand";

  const selectAction = (next: AdjustmentAction) => {
    setAction(next);
    setAmount("");
    setError("");
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const response = await fetch(`${bridgeUrl}/api/materials/${material.id}/adjust`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expected_revision: material.revision, values: { action, quantity: amount, unit_cost: unitCost, notes } }),
      });
      const payload = (await response.json()) as { ok: boolean; data?: MaterialDetail; error?: { message: string } };
      if (!response.ok || !payload.ok || !payload.data) throw new Error(payload.error?.message || "Inventory could not be adjusted.");
      onSaved(payload.data);
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "Inventory could not be adjusted.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="composer-backdrop quick-add-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <aside className="quick-add-panel inventory-adjustment-panel" role="dialog" aria-modal="true" aria-labelledby="inventory-adjustment-title">
        <div className="quick-add-heading"><div><span>Inventory activity</span><h2 id="inventory-adjustment-title">Adjust {material.name}</h2></div><button className="icon-button" onClick={onClose} aria-label="Close inventory adjustment"><X size={20} /></button></div>
        <div className="inventory-action-types" aria-label="Adjustment type">
          {actions.map(({ id, label, detail, icon: Icon }) => <button type="button" className={action === id ? "active" : ""} onClick={() => selectAction(id)} key={id}><Icon size={18} /><span><strong>{label}</strong><small>{detail}</small></span></button>)}
        </div>
        <form className="quick-add-form" onSubmit={submit}>
          <div className="inventory-current"><span>Currently on hand</span><strong>{quantity(material.quantity_on_hand)} {material.unit_of_measure || "units"}</strong></div>
          <label><span>{amountLabel} *</span><input autoFocus type="number" min="0" step="0.01" value={amount} onChange={(event) => setAmount(event.target.value)} required /></label>
          {action === "receive" ? <label><span>Unit cost</span><input type="number" min="0" step="0.01" value={unitCost} onChange={(event) => setUnitCost(event.target.value)} /></label> : null}
          <div className={projected < 0 ? "inventory-projection invalid" : "inventory-projection"}><span>After this adjustment</span><strong>{quantity(projected)} {material.unit_of_measure || "units"}</strong></div>
          <label><span>Notes</span><textarea rows={3} value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Delivery reference, job, count details…" /></label>
          {error ? <p className="quick-add-error" role="alert">{error}</p> : null}
          <div className="quick-add-actions"><button type="button" className="secondary-button" onClick={onClose}>Cancel</button><button className="primary-button" disabled={saving || projected < 0}>{saving ? "Saving…" : "Record adjustment"}</button></div>
        </form>
      </aside>
    </div>
  );
}
