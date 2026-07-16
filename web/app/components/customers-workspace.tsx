import { CalendarClock, ChevronRight, Clock3, Mail, MapPin, MessageSquareText, Phone, Plus, Search, ShoppingBag, Trash2, UserRound } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { InteractionPanel } from "./interaction-panel";
import { bridgeUrl, getBridgeData, type CustomerDetail, type CustomerOption, type Order } from "../lib/hustlenest";

export function CustomersWorkspace({
  customers,
  orders,
  onCreateOrder,
  onOpenOrder,
  onEdit,
  onInteractionSaved,
  onPromoted,
  focusCustomerKey,
}: {
  customers: CustomerOption[];
  orders: Order[];
  onCreateOrder: (customer: CustomerOption) => void;
  onOpenOrder: (orderId: number) => void;
  onEdit: (customer: CustomerOption) => void;
  onInteractionSaved: (customer: CustomerDetail) => void;
  onPromoted: (customer: CustomerOption) => void;
  focusCustomerKey?: string | null;
}) {
  const [search, setSearch] = useState("");
  const [selectedKey, setSelectedKey] = useState<string | null>(focusCustomerKey ?? customers[0]?.key ?? null);
  const [detail, setDetail] = useState<CustomerDetail | null>(null);
  const [interactionOpen, setInteractionOpen] = useState(false);
  const [deleteInteractionId, setDeleteInteractionId] = useState<number | null>(null);
  const [interactionBusy, setInteractionBusy] = useState(false);
  const [promoting, setPromoting] = useState(false);
  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    return customers.filter((customer) => !term || [customer.name, customer.company, customer.email, customer.phone, customer.address].join(" ").toLowerCase().includes(term));
  }, [customers, search]);
  const selected = customers.find((customer) => customer.key === selectedKey) ?? filtered[0] ?? customers[0];
  useEffect(() => {
    if (!selected?.id) return;
    const controller = new AbortController();
    getBridgeData<CustomerDetail>(`/api/customers/${selected.id}`, controller.signal).then(setDetail).catch((error: unknown) => { if (!(error instanceof DOMException && error.name === "AbortError")) setDetail(null); });
    return () => controller.abort();
  }, [selected?.id]);
  const current = detail?.id === selected?.id ? detail : selected;
  const selectedOrders = selected
    ? orders.filter((order) => (selected.id !== null && order.customerId === selected.id) || order.customer.toLowerCase() === selected.name.toLowerCase())
    : [];
  const totalRevenue = selectedOrders.reduce((sum, order) => sum + order.total, 0);
  const deleteInteraction = async (interactionId: number, revision: string) => {
    if (!current?.id) return;
    setInteractionBusy(true);
    try {
      const response = await fetch(`${bridgeUrl}/api/customers/${current.id}/interactions/${interactionId}`, { method: "DELETE", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expected_revision: revision }) });
      const payload = (await response.json()) as { ok: boolean; data?: CustomerDetail; error?: { message: string } };
      if (!response.ok || !payload.ok || !payload.data) throw new Error(payload.error?.message || "The interaction could not be deleted.");
      setDetail(payload.data);
      onInteractionSaved(payload.data);
      setDeleteInteractionId(null);
    } finally { setInteractionBusy(false); }
  };
  const promoteCustomer = async () => {
    if (!current || current.id) return;
    setPromoting(true);
    try {
      const response = await fetch(`${bridgeUrl}/api/customers/promote`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: current.name }) });
      const payload = (await response.json()) as { ok: boolean; data?: CustomerOption; error?: { message: string } };
      if (!response.ok || !payload.ok || !payload.data) throw new Error(payload.error?.message || "The customer could not be added to contacts.");
      onPromoted(payload.data);
    } finally { setPromoting(false); }
  };

  return (
    <div className="workspace entity-page">
      <div className="page-heading">
        <div><div className="eyebrow"><span>Sales</span><ChevronRight size={14} /><span>Customers</span></div><h1>Customers</h1><p>Keep relationships and order context together.</p></div>
        {current ? <div className="page-actions">{current.id ? <button className="secondary-button" onClick={() => setInteractionOpen(true)}><MessageSquareText size={16} /> Log interaction</button> : null}<button className="primary-button" onClick={() => onCreateOrder(current)}><Plus size={17} /> New order</button></div> : null}
      </div>
      <section className="entity-workspace">
        <div className="entity-list-panel">
          <label className="entity-search"><Search size={17} /><input aria-label="Search customers" placeholder="Search customers…" value={search} onChange={(event) => setSearch(event.target.value)} /></label>
          <div className="entity-list-heading"><span>{filtered.length} customers</span><span>Orders</span></div>
          <div className="entity-rows">
            {filtered.map((customer) => {
              const customerOrders = orders.filter((order) => (customer.id !== null && order.customerId === customer.id) || order.customer.toLowerCase() === customer.name.toLowerCase());
              return (
                <button className={customer.key === selected?.key ? "entity-row selected" : "entity-row"} onClick={() => setSelectedKey(customer.key)} key={customer.key}>
                  <span className="avatar">{customer.name.split(/\s+/).slice(0, 2).map((part) => part[0]).join("")}</span>
                  <span><strong>{customer.name}</strong><small>{customer.company || customer.email || customer.address || "Contact details pending"}</small></span>
                  <em>{customerOrders.length}</em>
                </button>
              );
            })}
            {!filtered.length ? <div className="empty-state"><UserRound size={24} /><strong>No customers found</strong><span>Try a different name or contact detail.</span></div> : null}
          </div>
        </div>
        <aside className="entity-detail">
          {selected ? (
            <>
              <div className="entity-hero"><div className="avatar entity-avatar">{current.name.split(/\s+/).slice(0, 2).map((part) => part[0]).join("")}</div><div><span>Customer</span><h2>{current.name}</h2><p>{current.company || "Individual customer"}</p></div></div>
              <div className="entity-stat-grid"><div><span>Orders</span><strong>{selectedOrders.length}</strong></div><div><span>Revenue</span><strong>{new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(totalRevenue)}</strong></div></div>
              <div className="detail-section customer-summary"><div className="section-heading"><h3>Contact</h3>{current.id ? <button onClick={() => onEdit(current)}>Edit</button> : <button onClick={() => void promoteCustomer()} disabled={promoting}>{promoting ? "Adding…" : "Add to contacts"}</button>}</div><p><Mail size={15} /> {current.email || "No email on file"}</p><p><Phone size={15} /> {current.phone || "No phone on file"}</p><p><MapPin size={15} /> {current.address || "No address on file"}</p></div>
              {current.id ? <div className="detail-section relationship-cadence"><div className="section-heading"><h3>Relationship cadence</h3>{current.preferred_channel ? <span>{current.preferred_channel}</span> : null}</div><div><p><Clock3 size={15} /><span>Last contacted<strong>{current.last_contacted || "Not recorded"}</strong></span></p><p className={current.next_follow_up && current.next_follow_up <= new Date().toLocaleDateString("en-CA") ? "follow-up-due" : ""}><CalendarClock size={15} /><span>Next follow-up<strong>{current.next_follow_up || "Not scheduled"}</strong></span></p></div></div> : null}
              {current.id ? <div className="detail-section interaction-history"><div className="section-heading"><h3>Interaction history</h3><span>{detail?.interactions.length ?? 0}</span></div>{detail?.interactions.length ? detail.interactions.slice(0, 8).map((interaction) => <article key={interaction.id}><span className="interaction-channel"><MessageSquareText size={14} /></span><div><span><strong>{interaction.channel || "Interaction"}</strong><time>{new Date(`${interaction.interaction_date}Z`).toLocaleDateString()}</time></span><p>{interaction.summary}</p>{interaction.follow_up_date ? <small><CalendarClock size={12} /> {interaction.follow_up_action || "Follow up"} · {interaction.follow_up_date}</small> : null}<div className="interaction-actions">{interaction.order_id ? <button onClick={() => onOpenOrder(interaction.order_id!)}>Open related order <ChevronRight size={12} /></button> : <span />}{deleteInteractionId !== interaction.id ? <button className="danger-text-button" onClick={() => setDeleteInteractionId(interaction.id)}><Trash2 size={12} /> Delete</button> : <button className="danger-text-button" disabled={interactionBusy} onClick={() => void deleteInteraction(interaction.id, interaction.revision)}>Confirm delete</button>}</div></div></article>) : <p className="quiet-empty"><MessageSquareText size={14} /> No interactions logged yet.</p>}</div> : null}
              <div className="detail-section"><div className="section-heading"><h3>Recent orders</h3><span>{selectedOrders.length}</span></div>{selectedOrders.slice(0, 5).map((order) => <button className="related-order" onClick={() => onOpenOrder(order.id)} key={order.id}><ShoppingBag size={15} /><span><strong>{order.number}</strong><small>{order.status} · {order.date}</small></span><em>{new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(order.total)}</em><ChevronRight size={15} /></button>)}{!selectedOrders.length ? <p className="quiet-empty">No orders yet. Start one with this customer’s details prefilled.</p> : null}</div>
              <button className="primary-button entity-primary" onClick={() => onCreateOrder(current)}><Plus size={17} /> Create order for {current.name}</button>
            </>
          ) : <div className="empty-state"><UserRound size={24} /><strong>Select a customer</strong></div>}
        </aside>
      </section>
      {interactionOpen && current.id ? <InteractionPanel customer={current} orders={selectedOrders} onClose={() => setInteractionOpen(false)} onSaved={(updated) => { setDetail(updated); setInteractionOpen(false); onInteractionSaved(updated); }} /> : null}
    </div>
  );
}
