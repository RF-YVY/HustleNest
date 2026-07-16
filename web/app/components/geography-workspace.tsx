"use client";

import { ChevronRight, CircleDot, Compass, House, MapPin, MapPinned, PackageCheck, Search, ShoppingBag } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { bridgeUrl, type GeographyWorkspaceData } from "../lib/hustlenest";

const tiles: Array<[string, number, number]> = [
  ["WA",1,1],["OR",1,2],["CA",1,3],["AK",1,7],["ID",2,2],["NV",2,3],["HI",2,7],["MT",3,2],["WY",3,3],["UT",3,4],["AZ",3,5],
  ["ND",4,2],["SD",4,3],["NE",4,4],["CO",4,5],["NM",4,6],["MN",5,2],["IA",5,3],["KS",5,4],["OK",5,5],["TX",5,6],
  ["WI",6,2],["IL",6,3],["MO",6,4],["AR",6,5],["LA",6,6],["MI",7,2],["IN",7,3],["KY",7,4],["TN",7,5],["MS",7,6],
  ["OH",8,3],["WV",8,4],["NC",8,5],["AL",8,6],["PA",9,3],["VA",9,4],["SC",9,5],["GA",9,6],["FL",9,7],
  ["NY",10,2],["NJ",10,3],["MD",10,4],["DE",10,5],["VT",11,1],["MA",11,2],["CT",11,3],["DC",11,5],["NH",12,1],["RI",12,2],["ME",13,1],
];

const money = (value: string | number) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(value));

export function GeographyWorkspace({ onOpenOrder, onOpenSettings }: { onOpenOrder: (id: number) => void; onOpenSettings: () => void }) {
  const [data, setData] = useState<GeographyWorkspaceData | null>(null);
  const [selectedState, setSelectedState] = useState("All states");
  const [search, setSearch] = useState("");
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    fetch(`${bridgeUrl}/api/geography`, { signal: controller.signal }).then(async (response) => {
      const payload = (await response.json()) as { ok: boolean; data?: GeographyWorkspaceData; error?: { message: string } };
      if (!response.ok || !payload.ok || !payload.data) throw new Error(payload.error?.message || "Sales geography could not be loaded.");
      return payload.data;
    }).then(setData).catch((caught: unknown) => { if (!(caught instanceof DOMException && caught.name === "AbortError")) setError(caught instanceof Error ? caught.message : "Sales geography could not be loaded."); });
    return () => controller.abort();
  }, []);
  const stateCounts = useMemo(() => new Map(data?.states.map((state) => [state.code, state.count]) ?? []), [data]);
  const maxCount = Math.max(...(data?.states.map((state) => state.count) ?? [1]), 1);
  const destinations = useMemo(() => (data?.destinations ?? []).filter((destination) => (selectedState === "All states" || destination.state === selectedState) && (!search.trim() || `${destination.city} ${destination.state} ${destination.order_numbers.join(" ")}`.toLowerCase().includes(search.trim().toLowerCase()))), [data, search, selectedState]);
  const selected = destinations.find((destination) => destination.key === selectedKey) ?? destinations[0];
  const chooseState = (code: string) => { setSelectedState((current) => current === code ? "All states" : code); setSelectedKey(null); };

  return <div className="workspace geography-page">
    <div className="page-heading"><div><div className="eyebrow"><span>Understand</span><ChevronRight size={14} /><span>Geography</span></div><h1>Sales geography</h1><p>See where orders are going and which markets are becoming repeat destinations.</p></div>{data?.home.configured ? <div className="home-base-pill"><House size={15} /><span><small>Home base</small><strong>{data.home.city}, {data.home.state}</strong></span></div> : <button className="secondary-button" onClick={onOpenSettings}><House size={15} /> Set home base</button>}</div>
    <section className="material-metrics geography-metrics"><article><ShoppingBag size={19} /><div><span>Orders mapped</span><strong>{data?.metrics.mapped_orders ?? 0}</strong></div></article><article><MapPin size={19} /><div><span>Destinations</span><strong>{data?.metrics.destinations ?? 0}</strong></div></article><article><Compass size={19} /><div><span>States reached</span><strong>{data?.metrics.states ?? 0}</strong></div></article><article><PackageCheck size={19} /><div><span>Strongest market</span><strong>{data?.metrics.top_state ?? "None yet"}</strong></div></article></section>
    {error ? <div className="geography-empty"><MapPinned size={26} /><strong>Sales geography unavailable</strong><span>{error}</span></div> : <section className="geography-layout">
      <article className="state-map-card"><div className="geography-card-heading"><div><span>U.S. distribution</span><h2>Order activity by state</h2></div><small>Choose a state to filter destinations</small></div><div className="state-map-scroll"><div className="state-tile-map" aria-label="United States order distribution">{tiles.map(([code, column, row]) => { const count = stateCounts.get(code) ?? 0; const active = selectedState === code; const home = data?.home.state === code; const level = count ? Math.max(1, Math.ceil(count / maxCount * 4)) : 0; return <button className={`${count ? `has-orders level-${level}` : ""} ${active ? "active" : ""} ${home ? "home-state" : ""}`} style={{ gridColumn: column, gridRow: row }} onClick={() => chooseState(code)} title={`${code}: ${count} order${count === 1 ? "" : "s"}`} key={code}><strong>{code}</strong>{count ? <span>{count}</span> : null}{home ? <i><House size={8} /></i> : null}</button>; })}</div></div><div className="map-legend"><span><i /> No orders</span><span><i className="low" /> Emerging</span><span><i className="high" /> Strong activity</span>{data?.home.configured ? <span><House size={11} /> Home base</span> : null}</div></article>
      <article className="destination-card"><div className="geography-card-heading"><div><span>Destinations</span><h2>{selectedState === "All states" ? "All markets" : data?.states.find((state) => state.code === selectedState)?.name ?? selectedState}</h2></div><em>{destinations.length}</em></div><label className="destination-search"><Search size={15} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Find city or order…" /></label><div className="destination-list">{destinations.map((destination) => <button className={selected?.key === destination.key ? "active" : ""} onClick={() => setSelectedKey(destination.key)} key={destination.key}><i><MapPin size={14} /></i><span><strong>{destination.city}, {destination.state}</strong><small>{destination.count} order{destination.count === 1 ? "" : "s"}</small></span><ChevronRight size={14} /></button>)}{!destinations.length ? <div className="geography-empty compact"><CircleDot size={22} /><strong>No matching destinations</strong><span>Try another state or city.</span></div> : null}</div></article>
      <article className="destination-detail-card">{selected ? <><div className="destination-hero"><i><MapPin size={19} /></i><div><span>Destination market</span><h2>{selected.city}, {selected.state}</h2><p>{selected.state_name} · {selected.count} order{selected.count === 1 ? "" : "s"}</p></div></div><div className="destination-orders"><div><h3>Orders to this market</h3><span>{selected.orders.length}</span></div>{selected.orders.map((order) => <button onClick={() => onOpenOrder(order.id)} key={order.id}><span><strong>{order.number}</strong><small>{order.customer} · {order.status}</small></span><em>{money(order.total)}</em><ChevronRight size={14} /></button>)}{selected.orders.length < selected.order_numbers.length ? <p>{selected.order_numbers.length - selected.orders.length} older order{selected.order_numbers.length - selected.orders.length === 1 ? "" : "s"} included in the map total.</p> : null}</div></> : <div className="geography-empty"><MapPin size={24} /><strong>No destinations yet</strong><span>Orders with a recognizable city and U.S. state will appear here automatically.</span></div>}</article>
    </section>}
  </div>;
}
