import {
  ArrowUpRight,
  BarChart3,
  Boxes,
  CalendarClock,
  ChevronRight,
  CircleDollarSign,
  PackageCheck,
  Plus,
  ReceiptText,
  ShoppingBag,
  Target,
  TrendingUp,
  Users,
} from "lucide-react";
import type { HomeWorkspaceData, SettingsWorkspaceData, WorkspaceView } from "../lib/hustlenest";

const money = (value: string | number) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(value));
const priorityIcon = { order: ShoppingBag, material: Boxes, customer: Users, finance: ReceiptText };

export function HomeWorkspace({
  home,
  onNavigate,
  onOpenOrder,
  onOpenMaterial,
  onNewOrder,
  onManageGoals,
  dashboardSections,
}: {
  home: HomeWorkspaceData | null;
  onNavigate: (view: WorkspaceView) => void;
  onOpenOrder: (id: number) => void;
  onOpenMaterial: (id: number) => void;
  onNewOrder: () => void;
  onManageGoals: () => void;
  dashboardSections?: SettingsWorkspaceData["appearance"]["dashboard_sections"];
}) {
  const maxTrend = Math.max(...(home?.sales_trend.map((item) => Number(item.revenue)) ?? []), 1);
  const section = (key: string, fallbackOrder: number) => dashboardSections?.find((item) => item.key === key) ?? { key, label: key, visible: true, collapsed: false, order: fallbackOrder };
  const summarySection = section("summary_metrics", 0);
  const prioritySection = section("priorities", 1);
  const shortcutsSection = section("shortcuts", 2);
  const trendSection = section("sales_trend", 3);
  const goalsSection = section("goals", 4);
  const recentSection = section("recent_orders", 5);
  const openPriority = (item: HomeWorkspaceData["priorities"][number]) => {
    if (item.kind === "order" && item.target_id) return onOpenOrder(item.target_id);
    if (item.kind === "material" && item.target_id) return onOpenMaterial(item.target_id);
    onNavigate(item.target_view);
  };

  return (
    <div className="workspace home-page">
      <div className="page-heading home-heading">
        <div><div className="eyebrow"><span>Workspace</span><ChevronRight size={14} /><span>Home</span></div><h1>Today at a glance</h1><p>Start with what needs attention, then move the business forward.</p></div>
        <button className="primary-button" onClick={onNewOrder}><Plus size={17} /> New order</button>
      </div>
      {summarySection.visible ? <section className={`metric-grid home-metrics${summarySection.collapsed ? " is-collapsed" : ""}`} aria-label="Business summary" style={{ order: summarySection.order }}>
        <article className="metric-card accent-card"><div className="metric-icon"><ShoppingBag size={20} /></div><div><span>Open orders</span><strong>{home?.metrics.open_orders ?? 0}</strong><small><ArrowUpRight size={13} /> Active fulfillment queue</small></div></article>
        <article className="metric-card"><div className="metric-icon violet"><CircleDollarSign size={20} /></div><div><span>Revenue this year</span><strong>{money(home?.metrics.revenue_ytd ?? 0)}</strong><small>Connected order revenue</small></div></article>
        <article className="metric-card"><div className="metric-icon amber"><TrendingUp size={20} /></div><div><span>Net after overhead</span><strong>{money(home?.metrics.net_ytd ?? 0)}</strong><small>Profit less expenses and losses</small></div></article>
        <article className="metric-card"><div className="metric-icon rose"><CalendarClock size={20} /></div><div><span>30-day cash outlook</span><strong>{money(home?.metrics.cash_projection_30 ?? 0)}</strong><small>Sales, receivables, and obligations</small></div></article>
      </section> : null}

      <section className="home-grid">
        {prioritySection.visible ? <article className={`home-card priority-card${prioritySection.collapsed ? " is-collapsed" : ""}`} style={{ order: prioritySection.order }}>
          <div className="home-card-heading"><div><span>Focus now</span><h2>Needs your attention</h2></div><em>{home?.counts.priorities ?? 0} total</em></div>
          <div className="priority-list">
            {home?.priorities.slice(0, 7).map((item) => { const Icon = priorityIcon[item.kind]; return <button onClick={() => openPriority(item)} key={item.key}><i className={`priority-icon ${item.severity}`}><Icon size={16} /></i><span><strong>{item.title}</strong><small>{item.detail}</small></span>{item.value ? <em>{money(item.value)}</em> : null}<ChevronRight size={15} /></button>; })}
            {!home?.priorities.length ? <div className="home-empty"><PackageCheck size={23} /><strong>You’re caught up</strong><span>No urgent orders, stock issues, follow-ups, or recurring costs.</span></div> : null}
          </div>
        </article> : null}

        {shortcutsSection.visible ? <article className={`home-card quick-card${shortcutsSection.collapsed ? " is-collapsed" : ""}`} style={{ order: shortcutsSection.order }}>
          <div className="home-card-heading"><div><span>Shortcuts</span><h2>Keep moving</h2></div></div>
          <div className="quick-grid">
            <button onClick={onNewOrder}><ShoppingBag size={18} /><span><strong>Create order</strong><small>Start a sale</small></span></button>
            <button onClick={() => onNavigate("customers")}><Users size={18} /><span><strong>Customers</strong><small>{home?.counts.customers ?? 0} relationships</small></span></button>
            <button onClick={() => onNavigate("materials")}><Boxes size={18} /><span><strong>Materials</strong><small>{home?.counts.materials_needing_attention ?? 0} need attention</small></span></button>
            <button onClick={() => onNavigate("finance")}><ReceiptText size={18} /><span><strong>Expenses</strong><small>Review spending</small></span></button>
            <button onClick={() => onNavigate("reports")}><BarChart3 size={18} /><span><strong>Reports</strong><small>See performance</small></span></button>
          </div>
          <div className="inventory-summary"><span><Boxes size={16} /> Inventory value</span><strong>{money(home?.metrics.inventory_value ?? 0)}</strong></div>
        </article> : null}

        {trendSection.visible ? <article className={`home-card home-trend-card${trendSection.collapsed ? " is-collapsed" : ""}`} style={{ order: trendSection.order }}>
          <div className="home-card-heading"><div><span>Momentum</span><h2>Sales this year</h2></div><button onClick={() => onNavigate("reports")}>View reports <ChevronRight size={13} /></button></div>
          {home?.sales_trend.length ? <div className="home-trend">{home.sales_trend.map((item) => <div key={item.label}><i style={{ height: `${Math.max(Number(item.revenue) / maxTrend * 100, 5)}%` }} /><span>{item.label}</span><small>{money(item.revenue)}</small></div>)}</div> : <div className="home-empty"><BarChart3 size={23} /><strong>No sales yet this year</strong><span>New order activity will build this chart.</span></div>}
        </article> : null}

        {goalsSection.visible ? <article className={`home-card goals-card${goalsSection.collapsed ? " is-collapsed" : ""}`} style={{ order: goalsSection.order }}>
          <div className="home-card-heading"><div><span>Progress</span><h2>Business goals</h2></div><button onClick={onManageGoals}>Manage goals <ChevronRight size={13} /></button></div>
          {home?.goals.map((goal) => <div className="goal-row" key={goal.id}><div><span><strong>{goal.name}</strong><em className={`goal-${goal.status}`}>{goal.status.replace("-", " ")}</em></span><small>{goal.current_value} of {goal.target_value}{goal.end_date ? ` · due ${goal.end_date}` : ""}</small><i><b style={{ width: `${goal.progress_percent}%` }} /></i></div><strong>{goal.progress_percent}%</strong></div>)}
          {!home?.goals.length ? <div className="home-empty compact"><Target size={21} /><strong>No goals configured</strong><span>Create a goal here to start tracking progress.</span><button className="secondary-button" onClick={onManageGoals}>Create goal</button></div> : null}
        </article> : null}

        {recentSection.visible ? <article className={`home-card home-recent-orders${recentSection.collapsed ? " is-collapsed" : ""}`} style={{ order: recentSection.order }}>
          <div className="home-card-heading"><div><span>Recent activity</span><h2>Latest orders</h2></div><button onClick={() => onNavigate("orders")}>All orders <ChevronRight size={13} /></button></div>
          {home?.recent_orders.map((order) => <button onClick={() => onOpenOrder(order.id)} key={order.id}><span><strong>{order.customer}</strong><small>{order.number} · {order.date}</small></span><em>{order.status}</em><strong>{money(order.revenue)}</strong><ChevronRight size={15} /></button>)}
        </article> : null}
      </section>
    </div>
  );
}
