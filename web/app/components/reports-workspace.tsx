import {
  ArrowUpRight,
  BarChart3,
  Download,
  ChevronRight,
  CircleDollarSign,
  PackageCheck,
  ReceiptText,
  TrendingUp,
  Users,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { bridgeUrl, getBridgeData } from "../lib/hustlenest";
import type { ReportsWorkspaceData } from "../lib/hustlenest";

const money = (value: string | number) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(value));
const periods = [
  ["this_month", "This month"],
  ["last_month", "Last month"],
  ["last_year", "Last year"],
  ["last_30_days", "Last 30 days"],
  ["this_quarter", "This quarter"],
  ["last_quarter", "Last quarter"],
  ["this_year", "This year"],
  ["last_90_days", "Last 90 days"],
  ["all_time", "All time"],
  ["custom_range", "Custom range"],
];
const reportExports = [
  ["cpa_zip", "CPA package (ZIP)"],
  ["orders_csv", "Order detail CSV"],
  ["sales_pdf", "Sales report PDF"],
  ["inventory_pdf", "Inventory PDF (current snapshot)"],
  ["pnl_pdf", "Profit & loss PDF"],
  ["customer_pdf", "Customer report PDF"],
  ["comparison_pdf", "Period comparison PDF"],
  ["tax_csv", "Sales tax CSV"],
  ["tax_pdf", "Sales tax PDF"],
];

const cpaOptions = [
  ["summary_csv", "Order performance summary CSV"], ["books_csv", "Bookkeeping journal CSV"], ["books_summary_csv", "Bookkeeping financial summary CSV"], ["accounts_csv", "Account balances CSV"], ["bank_csv", "Bank statement matches CSV"], ["bank_corrections_csv", "Statement import correction history CSV"], ["reconciliations_csv", "Bank reconciliations CSV"], ["expense_review_csv", "Expense classifications CSV"], ["loss_review_csv", "Write-off classifications CSV"], ["orders_csv", "Order detail CSV"],
  ["expenses_csv", "Expenses CSV"], ["losses_csv", "Recorded losses CSV"],
  ["zero_sale_csv", "$0 replacement items CSV"], ["sales_pdf", "Sales report PDF"],
  ["pnl_pdf", "Profit & loss PDF"], ["customer_pdf", "Customer report PDF"],
  ["tax_pdf", "Sales tax PDF"], ["comparison_pdf", "Period comparison PDF"],
  ["inventory_pdf", "Inventory PDF (current snapshot)"],
];

function CPAPackageDialog({ query, onClose }: { query: string; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [selected, setSelected] = useState(cpaOptions.filter(([key]) => !["comparison_pdf", "inventory_pdf"].includes(key)).map(([key]) => key));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const allTime = new URLSearchParams(query).get("period") === "all_time";
  useEffect(() => { dialog.current?.showModal(); }, []);
  const generate = async () => {
    setBusy(true); setError("");
    try {
      const params = new URLSearchParams(query);
      selected.forEach((key) => params.append("include", key));
      const response = await fetch(`${bridgeUrl}/api/reports/export?${params}`);
      if (!response.ok) throw new Error("Could not generate the CPA package. Please try again.");
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = response.headers.get("Content-Disposition")?.match(/filename="?([^";]+)/)?.[1] ?? "CPA_Package.zip";
      document.body.appendChild(link); link.click(); link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 60000);
      onClose();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Download failed."); }
    finally { setBusy(false); }
  };
  return <dialog className="cpa-package-dialog" ref={dialog} aria-labelledby="cpa-package-title" onCancel={(event) => { if (busy) event.preventDefault(); }} onClose={onClose}>
    <h2 id="cpa-package-title">Choose CPA package contents</h2>
    <p>Choose the CSV details and PDF reports to include. Reports use the applied dates; inventory is a current snapshot. Reporting notes are always included.</p>
    <fieldset disabled={busy}><legend>Include in ZIP</legend>{cpaOptions.map(([key, label]) => <label key={key}><input type="checkbox" checked={selected.includes(key)} disabled={allTime && key === "comparison_pdf"} onChange={(event) => setSelected((current) => event.target.checked ? [...current, key] : current.filter((item) => item !== key))} />{label}</label>)}</fieldset>
    {allTime ? <p>Choose a bounded date range to include a period comparison.</p> : null}
    {error ? <p role="alert">{error}</p> : null}
    <div className="cpa-package-actions"><button className="secondary-button" disabled={busy} onClick={onClose}>Cancel</button><button className="primary-button" disabled={busy || !selected.length} onClick={() => void generate()}>{busy ? "Generating ZIP…" : "Generate ZIP"}</button></div>
  </dialog>;
}

export function ReportsWorkspace({ initialReports, onOpenOrder }: { initialReports: ReportsWorkspaceData | null; onOpenOrder: (id: number) => void }) {
  const [cpaDialog, setCpaDialog] = useState(false);
  const [reports, setReports] = useState(initialReports);
  const [period, setPeriod] = useState(initialReports?.period.key ?? "this_year");
  const [loading, setLoading] = useState(false);
  const [exportKind, setExportKind] = useState("orders_csv");
  const [customStart, setCustomStart] = useState(initialReports?.period.start ?? "");
  const [customEnd, setCustomEnd] = useState(initialReports?.period.end ?? new Date().toISOString().slice(0, 10));
  const reportQuery = (nextPeriod: string) => {
    const query = new URLSearchParams({ period: nextPeriod });
    if (nextPeriod === "custom_range") {
      query.set("start", customStart);
      query.set("end", customEnd);
    }
    return query.toString();
  };
  const selectPeriod = async (nextPeriod: string) => {
    setPeriod(nextPeriod);
    if (nextPeriod === "custom_range") return;
    setLoading(true);
    try { setReports(await getBridgeData<ReportsWorkspaceData>(`/api/reports?${reportQuery(nextPeriod)}`)); }
    finally { setLoading(false); }
  };
  const applyCustomRange = async () => {
    if (!customStart || !customEnd || customEnd < customStart) return;
    setLoading(true);
    try { setReports(await getBridgeData<ReportsWorkspaceData>(`/api/reports?${reportQuery("custom_range")}`)); }
    finally { setLoading(false); }
  };
  const exportQuery = new URLSearchParams({ kind: exportKind, period: reports?.period.key ?? period });
  if (reports?.period.key === "custom_range") {
    exportQuery.set("start", reports.period.start ?? "");
    exportQuery.set("end", reports.period.end);
  }
  const maxTrend = Math.max(...(reports?.trend.map((item) => Number(item.revenue)) ?? [0]), 1);
  const totalFulfillment = reports?.fulfillment.reduce((sum, item) => sum + item.count, 0) ?? 0;

  return (
    <div className="workspace reports-page">
      {cpaDialog ? <CPAPackageDialog query={exportQuery.toString()} onClose={() => setCpaDialog(false)} /> : null}
      <div className="page-heading reports-heading">
        <div><div className="eyebrow"><span>Understand</span><ChevronRight size={14} /><span>Reports</span></div><h1>Reports</h1><p>Order performance based on order dates. Use Books & Banking for dated financial transactions.</p></div>
        <div className="report-heading-actions"><label className="report-period"><span>Reporting period</span><select aria-label="Reporting period" value={period} onChange={(event) => void selectPeriod(event.target.value)} disabled={loading}>{periods.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>{period === "custom_range" ? <><label className="report-date"><span>From</span><input aria-label="Report start date" type="date" value={customStart} max={customEnd || undefined} onChange={(event) => setCustomStart(event.target.value)} /></label><label className="report-date"><span>To</span><input aria-label="Report end date" type="date" value={customEnd} min={customStart || undefined} onChange={(event) => setCustomEnd(event.target.value)} /></label><button className="secondary-button report-apply" onClick={() => void applyCustomRange()} disabled={loading || !customStart || !customEnd || customEnd < customStart}>Apply</button></> : null}<label className="report-period"><span>Export</span><select aria-label="Report export type" value={exportKind} onChange={(event) => setExportKind(event.target.value)}>{reportExports.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label><a className="secondary-button report-download" aria-disabled={loading} onClick={(event) => { if (loading || exportKind === "cpa_zip") event.preventDefault(); if (!loading && exportKind === "cpa_zip") setCpaDialog(true); }} href={`${bridgeUrl}/api/reports/export?${exportQuery.toString()}`}><Download size={15} /> Download</a></div>
      </div>
      <p className="quiet-empty">Applied dates: {reports?.period.start ?? "All history"} through {reports?.period.end ?? "today"} (inclusive). Downloads use these applied dates. Inventory is a current snapshot; comparisons use the preceding period of the same length.</p>
      <section className={loading ? "metric-grid reports-metrics loading" : "metric-grid reports-metrics"} aria-label="Report summary">
        <article className="metric-card accent-card"><div className="metric-icon"><CircleDollarSign size={20} /></div><div><span>Revenue</span><strong>{money(reports?.metrics.revenue ?? 0)}</strong><small><ArrowUpRight size={13} /> {reports?.metrics.revenue_change ?? 0}% vs prior period</small></div></article>
        <article className="metric-card"><div className="metric-icon violet"><TrendingUp size={20} /></div><div><span>Gross profit</span><strong>{money(reports?.metrics.gross_profit ?? 0)}</strong><small>{reports?.metrics.gross_margin ?? 0}% margin</small></div></article>
        <article className="metric-card"><div className="metric-icon amber"><ReceiptText size={20} /></div><div><span>Overhead + losses</span><strong>{money(Number(reports?.metrics.expenses ?? 0) + Number(reports?.metrics.losses ?? 0))}</strong><small>{money(reports?.metrics.expenses ?? 0)} recorded expenses</small></div></article>
        <article className="metric-card"><div className="metric-icon rose"><BarChart3 size={20} /></div><div><span>Net after overhead</span><strong>{money(reports?.metrics.net_after_overhead ?? 0)}</strong><small>{reports?.metrics.order_count ?? 0} orders · {money(reports?.metrics.average_order ?? 0)} average</small></div></article>
      </section>

      <article className="report-card">
        <div className="report-card-heading"><h2>Completed $0 items / replacement costs</h2><strong>{money(reports?.metrics.zero_sale_cost ?? 0)}</strong></div>
        <p>Cost of goods: {money(reports?.metrics.cost_of_goods ?? 0)}. Replacement costs below are already included in gross profit and are not deducted again.</p>
        {reports?.zero_sale_items?.map((item, index) => <p key={`${item.order_id}-${index}`}><button className="secondary-button" onClick={() => onOpenOrder(item.order_id)}>{item.number} · {item.customer} · {item.product} × {item.quantity} · $0.00 revenue · {money(item.cost)} cost · {money(item.profit)} contribution</button></p>)}
        {!reports?.zero_sale_items?.length ? <p>No completed $0 items in this period.</p> : null}
        <p>Record replacement items at $0 with actual costs and a remake note; mark Shipped when fulfilled. Download the CPA package for summary and supporting order, expense, and loss details.</p>
      </article>
      <section className="reports-grid">
        <article className="report-card revenue-trend">
          <div className="report-card-heading"><div><span>Performance</span><h2>Revenue and gross profit</h2></div><strong>{reports?.period.label ?? "This year"}</strong></div>
          {reports?.trend.length ? <div className="trend-chart" aria-label="Revenue trend">{reports.trend.map((item) => <div className="trend-column" key={item.label}><div className="trend-values"><i style={{ height: `${Math.max(Number(item.revenue) / maxTrend * 100, 4)}%` }} /><b style={{ height: `${Math.max(Number(item.profit) / maxTrend * 100, 2)}%` }} /></div><span>{item.label}</span><small>{money(item.revenue)}</small></div>)}</div> : <div className="report-empty"><BarChart3 size={24} /><strong>No sales in this period</strong><span>Choose another reporting period to compare activity.</span></div>}
          <div className="chart-legend"><span><i /> Revenue</span><span><i className="profit" /> Gross profit</span></div>
        </article>

        <article className="report-card fulfillment-card">
          <div className="report-card-heading"><div><span>Operations</span><h2>Fulfillment mix</h2></div><PackageCheck size={19} /></div>
          <div className="fulfillment-stack">{reports?.fulfillment.map((item) => <div style={{ width: `${totalFulfillment ? item.count / totalFulfillment * 100 : 0}%` }} title={`${item.status}: ${item.count}`} key={item.status} />)}</div>
          <div className="fulfillment-list">{reports?.fulfillment.map((item) => <div key={item.status}><span><i />{item.status}</span><strong>{item.count}</strong><small>{money(item.revenue)}</small></div>)}</div>
          {!reports?.fulfillment.length ? <p className="quiet-empty">No fulfillment activity in this period.</p> : null}
        </article>

        <article className="report-card ranking-card">
          <div className="report-card-heading"><div><span>Sales mix</span><h2>Top products</h2></div><BarChart3 size={19} /></div>
          <div className="report-table-heading"><span>Product</span><span>Units</span><span>Revenue</span><span>Margin</span></div>
          {reports?.products.map((item, index) => <div className="report-table-row" key={item.name}><span><em>{index + 1}</em><strong>{item.name}</strong></span><span>{item.quantity}</span><span>{money(item.revenue)}</span><span>{item.margin}%</span></div>)}
          {!reports?.products.length ? <p className="quiet-empty">No product sales to rank yet.</p> : null}
        </article>

        <article className="report-card ranking-card">
          <div className="report-card-heading"><div><span>Relationships</span><h2>Top customers</h2></div><Users size={19} /></div>
          <div className="report-table-heading customer-ranking"><span>Customer</span><span>Orders</span><span>Revenue</span><span>Profit</span></div>
          {reports?.customers.map((item, index) => <div className="report-table-row customer-ranking" key={item.name}><span><em>{index + 1}</em><strong>{item.name}</strong></span><span>{item.orders}</span><span>{money(item.revenue)}</span><span>{money(item.profit)}</span></div>)}
          {!reports?.customers.length ? <p className="quiet-empty">No customer sales to rank yet.</p> : null}
        </article>

        <article className="report-card recent-report-orders">
          <div className="report-card-heading"><div><span>Drill down</span><h2>Orders in this period</h2></div><strong>{reports?.recent_orders.length ?? 0} orders</strong></div>
          {reports?.recent_orders.map((order) => <button onClick={() => onOpenOrder(order.id)} key={order.id}><span><strong>{order.customer}</strong><small>{order.number} · {order.date}</small></span><em>{order.status}</em><span><strong>{money(order.revenue)}</strong><small>{money(order.profit)} profit</small></span><ChevronRight size={15} /></button>)}
          {!reports?.recent_orders.length ? <p className="quiet-empty">No orders to review in this period.</p> : null}
        </article>
      </section>
    </div>
  );
}
