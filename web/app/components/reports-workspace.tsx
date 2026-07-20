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
import { useState } from "react";
import { bridgeUrl, getBridgeData } from "../lib/hustlenest";
import type { ReportsWorkspaceData } from "../lib/hustlenest";

const money = (value: string | number) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(value));
const periods = [
  ["this_month", "This month"],
  ["this_quarter", "This quarter"],
  ["last_quarter", "Last quarter"],
  ["this_year", "This year"],
  ["last_90_days", "Last 90 days"],
  ["all_time", "All time"],
  ["custom_range", "Custom range"],
];
const reportExports = [
  ["orders_csv", "Order detail CSV"],
  ["sales_pdf", "Sales report PDF"],
  ["inventory_pdf", "Inventory report PDF"],
  ["pnl_pdf", "Profit & loss PDF"],
  ["customer_pdf", "Customer report PDF"],
  ["comparison_pdf", "Period comparison PDF"],
  ["tax_csv", "Sales tax CSV"],
  ["tax_pdf", "Sales tax PDF"],
];

export function ReportsWorkspace({ initialReports, onOpenOrder }: { initialReports: ReportsWorkspaceData | null; onOpenOrder: (id: number) => void }) {
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
  const exportQuery = new URLSearchParams({ kind: exportKind, period });
  if (period === "custom_range") {
    exportQuery.set("start", customStart);
    exportQuery.set("end", customEnd);
  }
  const maxTrend = Math.max(...(reports?.trend.map((item) => Number(item.revenue)) ?? [0]), 1);
  const totalFulfillment = reports?.fulfillment.reduce((sum, item) => sum + item.count, 0) ?? 0;

  return (
    <div className="workspace reports-page">
      <div className="page-heading reports-heading">
        <div><div className="eyebrow"><span>Understand</span><ChevronRight size={14} /><span>Reports</span></div><h1>Reports</h1><p>Turn sales, costs, and fulfillment activity into the next useful decision.</p></div>
        <div className="report-heading-actions"><label className="report-period"><span>Reporting period</span><select aria-label="Reporting period" value={period} onChange={(event) => void selectPeriod(event.target.value)} disabled={loading}>{periods.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>{period === "custom_range" ? <><label className="report-date"><span>From</span><input aria-label="Report start date" type="date" value={customStart} max={customEnd || undefined} onChange={(event) => setCustomStart(event.target.value)} /></label><label className="report-date"><span>To</span><input aria-label="Report end date" type="date" value={customEnd} min={customStart || undefined} onChange={(event) => setCustomEnd(event.target.value)} /></label><button className="secondary-button report-apply" onClick={() => void applyCustomRange()} disabled={loading || !customStart || !customEnd || customEnd < customStart}>Apply</button></> : null}<label className="report-period"><span>Export</span><select aria-label="Report export type" value={exportKind} onChange={(event) => setExportKind(event.target.value)}>{reportExports.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label><a className="secondary-button report-download" href={`${bridgeUrl}/api/reports/export?${exportQuery.toString()}`}><Download size={15} /> Download</a></div>
      </div>
      <section className={loading ? "metric-grid reports-metrics loading" : "metric-grid reports-metrics"} aria-label="Report summary">
        <article className="metric-card accent-card"><div className="metric-icon"><CircleDollarSign size={20} /></div><div><span>Revenue</span><strong>{money(reports?.metrics.revenue ?? 0)}</strong><small><ArrowUpRight size={13} /> {reports?.metrics.revenue_change ?? 0}% vs prior period</small></div></article>
        <article className="metric-card"><div className="metric-icon violet"><TrendingUp size={20} /></div><div><span>Gross profit</span><strong>{money(reports?.metrics.gross_profit ?? 0)}</strong><small>{reports?.metrics.gross_margin ?? 0}% margin</small></div></article>
        <article className="metric-card"><div className="metric-icon amber"><ReceiptText size={20} /></div><div><span>Overhead + losses</span><strong>{money(Number(reports?.metrics.expenses ?? 0) + Number(reports?.metrics.losses ?? 0))}</strong><small>{money(reports?.metrics.expenses ?? 0)} recorded expenses</small></div></article>
        <article className="metric-card"><div className="metric-icon rose"><BarChart3 size={20} /></div><div><span>Net after overhead</span><strong>{money(reports?.metrics.net_after_overhead ?? 0)}</strong><small>{reports?.metrics.order_count ?? 0} orders · {money(reports?.metrics.average_order ?? 0)} average</small></div></article>
      </section>

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
