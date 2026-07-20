import {
  Boxes,
  CalendarClock,
  ChevronRight,
  CircleAlert,
  CircleDollarSign,
  CreditCard,
  Factory,
  Package,
  Pencil,
  ReceiptText,
  Repeat2,
  Search,
  Tags,
  TrendingDown,
  UserRound,
} from "lucide-react";
import { useMemo, useState } from "react";
import type { ExpenseOption, FinanceWorkspaceData, LossOption, RecurringExpenseOption } from "../lib/hustlenest";

type FinanceMode = "expenses" | "recurring" | "losses";
type FinanceRow = ExpenseOption | RecurringExpenseOption | LossOption;
const money = (value: string | number) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(value));
const shortDate = (value: string | null) => value ? new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric" }).format(new Date(`${value}T12:00:00`)) : "Not scheduled";
const emptyExpenses: ExpenseOption[] = [];
const emptyRecurring: RecurringExpenseOption[] = [];
const emptyLosses: LossOption[] = [];

export function FinanceWorkspace({
  finance,
  onOpenOrder,
  onOpenMaterial,
  focusMode,
  focusId,
  onEditExpense,
  onEditRecurring,
  onEditLoss,
}: {
  finance: FinanceWorkspaceData | null;
  onOpenOrder: (id: number) => void;
  onOpenMaterial: (id: number) => void;
  focusMode?: FinanceMode | null;
  focusId?: number | null;
  onEditExpense: (expense: ExpenseOption) => void;
  onEditRecurring: (recurring: RecurringExpenseOption) => void;
  onEditLoss: (loss: LossOption) => void;
}) {
  const [mode, setMode] = useState<FinanceMode>(focusMode ?? "expenses");
  const [search, setSearch] = useState("");
  const [selectedKey, setSelectedKey] = useState<string | null>(focusMode && focusId ? `${focusMode}:${focusId}` : null);
  const expenses = finance?.expenses ?? emptyExpenses;
  const recurring = finance?.recurring ?? emptyRecurring;
  const losses = finance?.losses ?? emptyLosses;
  const rows = useMemo<FinanceRow[]>(() => {
    const term = search.trim().toLowerCase();
    if (mode === "expenses") return expenses.filter((item) => !term || [item.category, item.notes, item.vendor?.name, item.material?.name, item.description].join(" ").toLowerCase().includes(term));
    if (mode === "recurring") return recurring.filter((item) => !term || [item.category, item.notes, item.vendor?.name, item.frequency].join(" ").toLowerCase().includes(term));
    return losses.filter((item) => !term || [item.category, item.description, item.details, item.product_name, item.material_name, item.recorded_by].join(" ").toLowerCase().includes(term));
  }, [expenses, losses, mode, recurring, search]);
  const currentKey = selectedKey?.startsWith(`${mode}:`) ? selectedKey : rows[0] ? `${mode}:${rows[0].id}` : null;
  const selected = rows.find((item) => `${mode}:${item.id}` === currentKey) ?? rows[0];
  const expense = mode === "expenses" ? selected as ExpenseOption | undefined : undefined;
  const obligation = mode === "recurring" ? selected as RecurringExpenseOption | undefined : undefined;
  const loss = mode === "losses" ? selected as LossOption | undefined : undefined;
  const categories = loss ? finance?.loss_categories : finance?.categories;
  const categoryCount = loss ? finance?.metrics.loss_category_count : finance?.metrics.category_count;
  const switchMode = (next: FinanceMode) => { setMode(next); setSelectedKey(null); };

  return (
    <div className="workspace entity-page finance-page">
      <div className="page-heading">
        <div><div className="eyebrow"><span>Business</span><ChevronRight size={14} /><span>Finance</span></div><h1>Finance</h1><p>Understand spending, obligations, and operational losses in one place.</p></div>{expense ? <button className="secondary-button" onClick={() => onEditExpense(expense)}><Pencil size={16} /> Edit expense</button> : obligation ? <button className="secondary-button" onClick={() => onEditRecurring(obligation)}><Pencil size={16} /> Edit recurring</button> : loss ? <button className="secondary-button" onClick={() => onEditLoss(loss)}><Pencil size={16} /> Edit loss</button> : null}
      </div>
      <section className="material-metrics finance-metrics" aria-label="Finance summary">
        <article><TrendingDown size={19} /><div><span>YTD expenses</span><strong>{money(finance?.metrics.year_to_date_expenses ?? 0)}</strong></div></article>
        <article><CircleAlert size={19} /><div><span>YTD losses</span><strong>{money(finance?.metrics.year_to_date_losses ?? 0)}</strong></div></article>
        <article><Repeat2 size={19} /><div><span>Monthly recurring</span><strong>{money(finance?.metrics.recurring_monthly_estimate ?? 0)}</strong></div></article>
        <article><CalendarClock size={19} /><div><span>Due next 30 days</span><strong>{money(finance?.metrics.upcoming_30_days ?? 0)}</strong></div></article>
      </section>
      <section className="entity-workspace finance-workspace">
        <div className="entity-list-panel">
          <div className="finance-tabs three" role="tablist" aria-label="Finance records">
            <button className={mode === "expenses" ? "active" : ""} onClick={() => switchMode("expenses")} role="tab" aria-selected={mode === "expenses"}>Expenses <span>{expenses.length}</span></button>
            <button className={mode === "recurring" ? "active" : ""} onClick={() => switchMode("recurring")} role="tab" aria-selected={mode === "recurring"}>Recurring <span>{recurring.length}</span></button>
            <button className={mode === "losses" ? "active loss-tab" : "loss-tab"} onClick={() => switchMode("losses")} role="tab" aria-selected={mode === "losses"}>Losses <span>{losses.length}</span></button>
          </div>
          <label className="entity-search"><Search size={17} /><input aria-label="Search finance records" placeholder="Search category, context, or notes…" value={search} onChange={(event) => setSearch(event.target.value)} /></label>
          <div className="entity-list-heading"><span>{rows.length} {mode}</span><span>Amount</span></div>
          <div className="entity-rows">
            {rows.map((item) => {
              const key = `${mode}:${item.id}`;
              const rowExpense = mode === "expenses" ? item as ExpenseOption : null;
              const rowRecurring = mode === "recurring" ? item as RecurringExpenseOption : null;
              const rowLoss = mode === "losses" ? item as LossOption : null;
              const subtitle = rowExpense ? `${shortDate(rowExpense.expense_date)} · ${rowExpense.vendor?.name || rowExpense.description || "No vendor"}` : rowRecurring ? `${rowRecurring.frequency} · ${rowRecurring.vendor?.name || shortDate(rowRecurring.next_occurrence)}` : `${shortDate(rowLoss?.loss_date ?? null)} · ${rowLoss?.product_name || rowLoss?.material_name || rowLoss?.description || "Operational loss"}`;
              const Icon = rowRecurring ? Repeat2 : rowLoss ? CircleAlert : ReceiptText;
              return <button className={key === currentKey ? "entity-row selected" : "entity-row"} onClick={() => setSelectedKey(key)} key={key}><span className={rowRecurring ? "finance-mark recurring" : rowLoss ? "finance-mark loss" : "finance-mark"}><Icon size={17} /></span><span><strong>{item.category || "Uncategorized"}</strong><small>{subtitle}</small></span><em>{money(item.amount)}</em></button>;
            })}
            {!rows.length ? <div className="empty-state"><ReceiptText size={24} /><strong>No {mode} found</strong><span>Recorded finance activity will appear here.</span></div> : null}
          </div>
        </div>
        <aside className="entity-detail">
          {selected ? <>
            <div className="entity-hero"><div className={obligation ? "finance-mark recurring entity-avatar" : loss ? "finance-mark loss entity-avatar" : "finance-mark entity-avatar"}>{obligation ? <Repeat2 size={24} /> : loss ? <CircleAlert size={24} /> : <ReceiptText size={24} />}</div><div><span>{obligation ? "Recurring obligation" : loss ? "Recorded loss" : "Recorded expense"}</span><h2>{selected.category || "Uncategorized"}</h2><p>{expense ? shortDate(expense.expense_date) : obligation ? `${obligation.frequency} · next ${shortDate(obligation.next_occurrence)}` : shortDate(loss?.loss_date ?? null)}</p></div></div>
            <div className="finance-amount"><span>{obligation ? `Every ${obligation.frequency.toLowerCase()}` : loss ? "Value lost" : "Amount paid"}</span><strong>{money(selected.amount)}</strong></div>
            {expense ? <>
              <div className="detail-section customer-summary"><div className="section-heading"><h3>Transaction context</h3></div><p><Factory size={15} /> {expense.vendor?.name || "No vendor assigned"}</p><p><Boxes size={15} /> {expense.material?.name || "No material linked"}</p><p><CreditCard size={15} /> {expense.payment_method || "Payment method not recorded"}</p><p><Repeat2 size={15} /> {expense.is_recurring ? "Created from a recurring expense" : "One-time expense"}</p>{expense.description ? <p><ReceiptText size={15} /> {expense.description}</p> : null}{expense.material_id ? <button className="finance-context-link" onClick={() => onOpenMaterial(expense.material_id!)}>Open linked material <ChevronRight size={14} /></button> : null}</div>
              {expense.tags.length ? <div className="detail-section"><div className="section-heading"><h3>Tags</h3></div><div className="finance-tags">{expense.tags.map((tag) => <span key={tag}><Tags size={12} />{tag}</span>)}</div></div> : null}
            </> : obligation ? <div className="detail-section customer-summary"><div className="section-heading"><h3>Schedule and owner</h3></div><p><Factory size={15} /> {obligation.vendor?.name || "No vendor assigned"}</p><p><CalendarClock size={15} /> Starts {shortDate(obligation.start_date)}</p><p><CircleDollarSign size={15} /> {obligation.auto_record ? "Automatically records when due" : "Manual recording"}</p>{obligation.end_date ? <p><CalendarClock size={15} /> Ends {shortDate(obligation.end_date)}</p> : null}</div> : loss ? <div className="detail-section customer-summary"><div className="section-heading"><h3>Operational context</h3></div><p><Package size={15} /> {loss.product_name || "No product linked"}</p><p><Boxes size={15} /> {loss.material_name || "No material linked"}</p><p><TrendingDown size={15} /> {loss.quantity ? `${loss.quantity} ${loss.unit || "units"} affected` : "Quantity not recorded"}</p><p><UserRound size={15} /> {loss.recorded_by || "Recorder not identified"}</p>{loss.description ? <p><ReceiptText size={15} /> {loss.description}</p> : null}{loss.order_id ? <button className="finance-context-link" onClick={() => onOpenOrder(loss.order_id!)}>Open linked order <ChevronRight size={14} /></button> : null}{loss.material_id ? <button className="finance-context-link" onClick={() => onOpenMaterial(loss.material_id!)}>Open linked material <ChevronRight size={14} /></button> : null}</div> : null}
            {(expense?.notes || obligation?.notes || loss?.details) ? <div className="detail-section note-card"><div className="section-heading"><h3>Notes</h3></div><p>{expense?.notes || obligation?.notes || loss?.details}</p></div> : null}
            {categories?.length ? <div className="detail-section category-breakdown"><div className="section-heading"><h3>Year-to-date {loss ? "loss" : "expense"} categories</h3><span>{categoryCount}</span></div>{categories.slice(0, 5).map((category) => <div className="category-row" key={category.name}><div><span><strong>{category.name}</strong><em>{money(category.total)}</em></span><i><b style={{ width: `${category.percent}%` }} /></i></div><small>{category.percent}%</small></div>)}</div> : null}
          </> : <div className="empty-state"><ReceiptText size={24} /><strong>No finance record selected</strong><span>Add activity in the desktop app to review it here.</span></div>}
        </aside>
      </section>
    </div>
  );
}
