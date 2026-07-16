"use client";

import { CalendarRange, ChevronRight, CircleDollarSign, Clock3, Download, FileClock, Filter, History, RefreshCw, Search, ShoppingBag } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { bridgeUrl, type HistoryWorkspaceData } from "../lib/hustlenest";

const money = (value: string | number) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(value));

export function HistoryWorkspace({ onOpenOrder }: { onOpenOrder: (id: number) => void }) {
  const [data, setData] = useState<HistoryWorkspaceData | null>(null);
  const [query, setQuery] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [eventType, setEventType] = useState("All activity");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async (filters = { query, startDate, endDate }) => {
    setLoading(true); setError("");
    try {
      const params = new URLSearchParams({ limit: "300" });
      if (filters.query.trim()) params.set("query", filters.query.trim());
      if (filters.startDate) params.set("start_date", filters.startDate);
      if (filters.endDate) params.set("end_date", filters.endDate);
      const response = await fetch(`${bridgeUrl}/api/history?${params}`);
      const payload = (await response.json()) as { ok: boolean; data?: HistoryWorkspaceData; error?: { message: string } };
      if (!response.ok || !payload.ok || !payload.data) throw new Error(payload.error?.message || "History could not be loaded.");
      setData(payload.data); setEventType("All activity");
    } catch (caught: unknown) { setError(caught instanceof Error ? caught.message : "History could not be loaded."); } finally { setLoading(false); }
  };
  useEffect(() => {
    const controller = new AbortController();
    fetch(`${bridgeUrl}/api/history?limit=300`, { signal: controller.signal })
      .then(async (response) => {
        const payload = (await response.json()) as { ok: boolean; data?: HistoryWorkspaceData; error?: { message: string } };
        if (!response.ok || !payload.ok || !payload.data) throw new Error(payload.error?.message || "History could not be loaded.");
        return payload.data;
      })
      .then(setData)
      .catch((caught: unknown) => { if (!(caught instanceof DOMException && caught.name === "AbortError")) setError(caught instanceof Error ? caught.message : "History could not be loaded."); })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, []);
  const events = useMemo(() => eventType === "All activity" ? data?.events ?? [] : data?.events.filter((event) => event.event_type === eventType) ?? [], [data, eventType]);
  const visibleOrders = new Set(events.map((event) => event.order_number)).size;
  const visibleNet = events.reduce((total, event) => total + Number(event.amount_delta), 0);
  const apply = (event: FormEvent) => { event.preventDefault(); void load(); };
  const clear = () => { setQuery(""); setStartDate(""); setEndDate(""); setEventType("All activity"); void load({ query: "", startDate: "", endDate: "" }); };
  const exportCsv = () => {
    const quote = (value: string | number | null) => `"${String(value ?? "").replaceAll('"', '""')}"`;
    const rows = [["When", "Order", "Event", "Description", "Amount change"], ...events.map((item) => [item.created_at, item.order_number, item.event_type, item.description, item.amount_delta])];
    const href = URL.createObjectURL(new Blob([rows.map((row) => row.map(quote).join(",")).join("\r\n")], { type: "text/csv;charset=utf-8" }));
    const anchor = document.createElement("a"); anchor.href = href; anchor.download = `hustlenest-history-${new Date().toLocaleDateString("en-CA")}.csv`; anchor.click(); URL.revokeObjectURL(href);
  };

  return <div className="workspace history-page">
    <div className="page-heading"><div><div className="eyebrow"><span>Understand</span><ChevronRight size={14} /><span>History</span></div><h1>Activity history</h1><p>Trace order changes, payments, status updates, and their financial impact.</p></div><button className="secondary-button" onClick={exportCsv} disabled={!events.length}><Download size={16} /> Export CSV</button></div>
    <section className="material-metrics history-metrics" aria-label="History summary"><article><FileClock size={19} /><div><span>Events shown</span><strong>{events.length}</strong></div></article><article><ShoppingBag size={19} /><div><span>Orders affected</span><strong>{visibleOrders}</strong></div></article><article><CircleDollarSign size={19} /><div><span>Net order change</span><strong>{money(visibleNet)}</strong></div></article><article><Clock3 size={19} /><div><span>Latest event</span><strong>{events[0] ? new Date(events[0].created_at).toLocaleDateString() : "None"}</strong></div></article></section>
    <form className="history-filters" onSubmit={apply}><label><Search size={16} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Order number contains…" aria-label="Search order history" /></label><label><span>From</span><input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} /></label><label><span>To</span><input type="date" min={startDate} value={endDate} onChange={(event) => setEndDate(event.target.value)} /></label><button className="primary-button" disabled={loading}><Filter size={15} /> Apply</button><button type="button" className="secondary-button" onClick={clear}><RefreshCw size={15} /> Clear</button></form>
    <section className="history-card"><div className="history-type-tabs"><button className={eventType === "All activity" ? "active" : ""} onClick={() => setEventType("All activity")}>All activity <span>{data?.events.length ?? 0}</span></button>{data?.event_types.map((item) => <button className={eventType === item.name ? "active" : ""} onClick={() => setEventType(item.name)} key={item.name}>{item.name} <span>{item.count}</span></button>)}</div>
      {error ? <div className="history-empty"><History size={23} /><strong>History unavailable</strong><span>{error}</span><button className="secondary-button" onClick={() => void load()}>Try again</button></div> : loading ? <div className="history-empty"><RefreshCw className="spin" size={22} /><strong>Loading activity…</strong></div> : events.length ? <div className="history-list">{events.map((item) => <article key={item.id}><i className={`history-tone ${item.tone}`}><History size={15} /></i><time>{new Date(item.created_at).toLocaleString()}</time><div><span><strong>{item.event_type}</strong><em>{item.order_number}</em></span><p>{item.description || "No description recorded."}</p></div><b className={Number(item.amount_delta) > 0 ? "positive" : Number(item.amount_delta) < 0 ? "negative" : ""}>{Number(item.amount_delta) ? `${Number(item.amount_delta) > 0 ? "+" : ""}${money(item.amount_delta)}` : "—"}</b>{item.order_available && item.order_id ? <button onClick={() => onOpenOrder(item.order_id!)}>Open order <ChevronRight size={13} /></button> : <span className="history-unavailable">Historical record</span>}</article>)}</div> : <div className="history-empty"><CalendarRange size={24} /><strong>No matching activity</strong><span>Adjust the order number or date range.</span></div>}
    </section>
  </div>;
}
