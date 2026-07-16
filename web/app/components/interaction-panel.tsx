"use client";

import { CalendarClock, MessageSquareText, X } from "lucide-react";
import { FormEvent, useState } from "react";
import { bridgeUrl, type CustomerDetail, type CustomerOption, type Order } from "../lib/hustlenest";

const today = () => new Date().toLocaleDateString("en-CA");

export function InteractionPanel({ customer, orders, onClose, onSaved }: { customer: CustomerOption; orders: Order[]; onClose: () => void; onSaved: (customer: CustomerDetail) => void }) {
  const [interactionDate, setInteractionDate] = useState(today());
  const [channel, setChannel] = useState(customer.preferred_channel || "Email");
  const [summary, setSummary] = useState("");
  const [followUpDate, setFollowUpDate] = useState("");
  const [followUpAction, setFollowUpAction] = useState("");
  const [orderId, setOrderId] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!customer.id) return;
    setSaving(true);
    setError("");
    try {
      const response = await fetch(`${bridgeUrl}/api/customers/${customer.id}/interactions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expected_revision: customer.revision, values: { interaction_date: interactionDate, channel, summary, follow_up_date: followUpDate, follow_up_action: followUpAction, order_id: orderId } }),
      });
      const payload = (await response.json()) as { ok: boolean; data?: CustomerDetail; error?: { message: string } };
      if (!response.ok || !payload.ok || !payload.data) throw new Error(payload.error?.message || "The interaction could not be saved.");
      onSaved(payload.data);
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "The interaction could not be saved.");
    } finally { setSaving(false); }
  };

  return (
    <div className="composer-backdrop quick-add-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <aside className="quick-add-panel interaction-panel" role="dialog" aria-modal="true" aria-labelledby="interaction-title">
        <div className="quick-add-heading"><div><span>Customer relationship</span><h2 id="interaction-title">Log interaction</h2><p>{customer.name}</p></div><button className="icon-button" onClick={onClose} aria-label="Close interaction form"><X size={20} /></button></div>
        <div className="interaction-context"><MessageSquareText size={18} /><div><strong>Keep the next step visible</strong><span>Record what happened and optionally schedule the follow-up.</span></div></div>
        <form className="quick-add-form" onSubmit={submit}>
          <div className="quick-form-pair"><label><span>Interaction date *</span><input type="date" value={interactionDate} onChange={(event) => setInteractionDate(event.target.value)} required /></label><label><span>Channel</span><select value={channel} onChange={(event) => setChannel(event.target.value)}><option>Email</option><option>Phone</option><option>Text</option><option>In person</option><option>Social</option><option>Other</option></select></label></div>
          <label><span>Summary *</span><textarea autoFocus rows={5} value={summary} onChange={(event) => setSummary(event.target.value)} required placeholder="What was discussed or decided?" /></label>
          {orders.length ? <label><span>Related order</span><select value={orderId} onChange={(event) => setOrderId(event.target.value)}><option value="">No order linked</option>{orders.map((order) => <option value={order.id} key={order.id}>{order.number} · {order.status}</option>)}</select></label> : null}
          <div className="follow-up-fields"><div><CalendarClock size={17} /><span><strong>Next follow-up</strong><small>Leave blank when no follow-up is needed.</small></span></div><label><span>Date</span><input type="date" min={interactionDate} value={followUpDate} onChange={(event) => setFollowUpDate(event.target.value)} /></label><label><span>Action</span><input value={followUpAction} onChange={(event) => setFollowUpAction(event.target.value)} placeholder="Send quote, check delivery…" /></label></div>
          {error ? <p className="quick-add-error" role="alert">{error}</p> : null}
          <div className="quick-add-actions"><button type="button" className="secondary-button" onClick={onClose}>Cancel</button><button className="primary-button" disabled={saving}>{saving ? "Saving…" : "Save interaction"}</button></div>
        </form>
      </aside>
    </div>
  );
}
