export type WorkspaceView = "home" | "orders" | "customers" | "products" | "materials" | "vendors" | "finance" | "reports" | "history" | "geography" | "documents" | "trash" | "settings";

export type OrderActivity = {
  id: number;
  order_id: number | null;
  order_number: string;
  event_type: string;
  description: string;
  amount_delta: string;
  created_at: string;
  tone: "positive" | "critical" | "neutral";
  order_available: boolean;
};

export type OrderStatus = "Received" | "Paid" | "Processing" | "Ready to Ship" | "Shipped" | "Cancelled";

export type Order = {
  id: number;
  number: string;
  customer: string;
  initials: string;
  email: string;
  phone: string;
  location: string;
  customerId?: number | null;
  orderDate?: string;
  targetDate?: string | null;
  carrier?: string;
  trackingNumber?: string;
  date: string;
  due: string;
  total: number;
  subtotal?: number;
  taxAmount?: number;
  status: OrderStatus;
  paid: boolean;
  items: Array<{
    productId?: number | null;
    sku?: string;
    name: string;
    detail: string;
    quantity: number;
    price: number;
  }>;
  note: string;
  overdue?: boolean;
  live?: boolean;
  activity?: OrderActivity[];
};

export type BridgeOrder = {
  id: number;
  number: string;
  customer_id: number | null;
  customer_name: string;
  customer: { email: string; phone: string; address: string };
  order_date: string;
  target_completion_date: string | null;
  status: OrderStatus;
  payment_status: "paid" | "unpaid" | "partial";
  subtotal: string;
  tax_amount: string;
  total: string;
  attention_reasons: string[];
  items: Array<{
    product_id: number | null;
    name: string;
    description: string;
    quantity: number;
    unit_price: string;
    sku: string;
  }>;
  notes: string;
  shipping: { carrier: string; tracking_number: string };
  activity: OrderActivity[];
};

export type OrderMetrics = {
  open_orders: number;
  awaiting_payment: string;
  awaiting_payment_count: number;
  ready_to_ship: number;
  needs_attention: number;
};

export type BridgeState = "connecting" | "connected" | "demo" | "error";

export type CustomerOption = {
  id: number | null;
  key: string;
  name: string;
  company: string;
  email: string;
  phone: string;
  address: string;
  notes: string;
  last_contacted: string | null;
  next_follow_up: string | null;
  preferred_channel: string;
  revision: string;
};

export type CustomerDetail = CustomerOption & {
  interactions: Array<{
    id: number;
    contact_id: number;
    interaction_date: string;
    channel: string;
    summary: string;
    follow_up_date: string | null;
    follow_up_action: string;
    order_id: number | null;
    revision: string;
  }>;
};

export type VendorSummary = {
  id: number;
  name: string;
  contact_name: string;
  email: string;
  phone: string;
  website: string;
  account_number: string;
  notes: string;
  preferred_payment_method: string;
  revision: string;
};

export type VendorOption = VendorSummary & {
  material_count: number;
  inventory_value: string;
  reorder_count: number;
};

export type VendorDetail = VendorOption & {
  materials: MaterialOption[];
};

export type ExpenseOption = {
  id: number;
  category: string;
  amount: string;
  expense_date: string;
  description: string;
  payment_method: string;
  vendor_id: number | null;
  vendor: VendorSummary | null;
  is_recurring: boolean;
  tags: string[];
  notes: string;
  revision: string;
};

export type RecurringExpenseOption = {
  id: number;
  category: string;
  amount: string;
  frequency: string;
  start_date: string | null;
  end_date: string | null;
  day_of_month: number | null;
  next_occurrence: string | null;
  auto_record: boolean;
  notes: string;
  vendor_id: number | null;
  vendor: VendorSummary | null;
  revision: string;
};

export type LossOption = {
  id: number;
  category: string;
  amount: string;
  loss_date: string;
  description: string;
  details: string;
  is_product_loss: boolean;
  recorded_by: string;
  quantity: number;
  unit: string;
  order_id: number | null;
  product_id: number | null;
  material_id: number | null;
  product_name: string;
  material_name: string;
  revision: string;
};

export type FinanceWorkspaceData = {
  expenses: ExpenseOption[];
  recurring: RecurringExpenseOption[];
  losses: LossOption[];
  categories: Array<{ name: string; total: string; count: number; percent: number }>;
  loss_categories: Array<{ name: string; total: string; count: number; percent: number }>;
  metrics: {
    year_to_date_expenses: string;
    month_expenses: string;
    recurring_monthly_estimate: string;
    upcoming_30_days: string;
    category_count: number;
    year_to_date_losses: string;
    month_losses: string;
    loss_category_count: number;
  };
};

export type ReportsWorkspaceData = {
  period: { key: string; label: string; start: string | null; end: string };
  metrics: {
    revenue: string;
    revenue_change: number;
    gross_profit: string;
    gross_margin: number;
    expenses: string;
    losses: string;
    net_after_overhead: string;
    order_count: number;
    average_order: string;
  };
  trend: Array<{ label: string; revenue: string; profit: string }>;
  products: Array<{ name: string; quantity: number; revenue: string; profit: string; margin: number }>;
  customers: Array<{ name: string; orders: number; revenue: string; profit: string }>;
  fulfillment: Array<{ status: string; count: number; revenue: string }>;
  recent_orders: Array<{ id: number; number: string; customer: string; date: string; status: string; revenue: string; profit: string }>;
};

export type HomeWorkspaceData = {
  metrics: {
    open_orders: number;
    revenue_ytd: string;
    net_ytd: string;
    cash_projection_30: string;
    inventory_value: string;
  };
  priorities: Array<{
    key: string;
    kind: "order" | "material" | "customer" | "finance";
    severity: "critical" | "warning" | "info";
    title: string;
    detail: string;
    value: string | null;
    target_view: WorkspaceView;
    target_id: number | null;
  }>;
  goals: Array<{
    id: number;
    name: string;
    metric_type: string;
    current_value: string;
    target_value: string;
    progress_percent: number;
    status: "complete" | "critical" | "warning" | "on-track";
    end_date: string | null;
    owner: string;
  }>;
  sales_trend: Array<{ label: string; revenue: string; profit: string }>;
  fulfillment: Array<{ status: string; count: number; revenue: string }>;
  recent_orders: ReportsWorkspaceData["recent_orders"];
  counts: { customers: number; products: number; materials_needing_attention: number; priorities: number };
};

export type Goal = {
  id: number;
  name: string;
  metric_type: string;
  target_value: string;
  current_value: string;
  display_target: string;
  display_current: string;
  start_date: string | null;
  end_date: string | null;
  owner: string;
  progress_notes: string;
  threshold_warning: number;
  threshold_critical: number;
  auto_calculate: boolean;
  progress_percent: number;
  status: "complete" | "critical" | "warning" | "on-track";
  revision: string;
  checkpoints: Array<{ id: number; checkpoint_date: string; actual_value: string; forecast_value: string; notes: string }>;
};

export type GoalsWorkspaceData = {
  goals: Goal[];
  metric_options: string[];
};

export type HistoryWorkspaceData = {
  events: OrderActivity[];
  event_types: Array<{ name: string; count: number }>;
  metrics: { total: number; orders: number; net_change: string; latest_at: string | null };
  filters: { query: string; start_date: string | null; end_date: string | null };
};

export type GeographyWorkspaceData = {
  destinations: Array<{
    key: string;
    city: string;
    state: string;
    state_name: string;
    count: number;
    order_numbers: string[];
    orders: Array<{ id: number; number: string; customer: string; status: string; total: string }>;
  }>;
  states: Array<{ code: string; name: string; count: number }>;
  home: { city: string; state: string; configured: boolean };
  metrics: { mapped_orders: number; destinations: number; states: number; top_state: string | null };
};

export type DocumentsWorkspaceData = {
  documents: Array<{
    id: number;
    name: string;
    extension: string;
    path: string;
    exists: boolean;
    size_bytes: number | null;
    category: string;
    description: string;
    tags: string[];
    stored_at: string;
    checksum: string;
    created_at: string | null;
    managed: boolean;
    revision: string;
    entity: { type: string; id: number | null; label: string; detail: string; target_view: WorkspaceView | null };
  }>;
  categories: Array<{ name: string; count: number }>;
  entity_types: Array<{ name: string; count: number }>;
  metrics: { total: number; linked: number; missing: number; category_count: number };
};

export type SettingsWorkspaceData = {
  business: { name: string; home_location: string; show_name_on_dashboard: boolean; logo_configured: boolean; logo_available: boolean; logo_alignment: string; logo_size: number };
  appearance: { theme: "light" | "dark" | "minty" | "solar" | "mission-control" | "terminal-green"; logo_alignment: "top-left" | "top-center" | "top-right" | "bottom-left" | "bottom-center" | "bottom-right"; logo_size: number; dashboard_sections: Array<{ key: string; label: string; visible: boolean; collapsed: boolean }> };
  orders: { number_format: string; next_sequence: number; next_number: string; low_inventory_threshold: number };
  invoice: { slogan: string; address: string; street: string; city: string; state: string; zip: string; phone: string; fax: string; terms: string; comments: string; contact_name: string; contact_phone: string; contact_email: string };
  tax: { rate_percent: string; show_on_invoice: boolean; add_to_total: boolean };
  payments: { methods: Array<{ source_index: number; label: string; configured: boolean }>; other_configured: boolean };
  sync: { enabled: boolean; provider: string; interval_minutes: number; configured_field_count: number };
  browser: { launch_mode: "system" | "specific" | "none"; browser_id: string; available: Array<{ id: string; label: string }> };
  summary: { configured_sections: number; payment_method_count: number; sensitive_values_excluded: boolean; editing_surface: string; revision: string };
};

export type TrashWorkspaceData = {
  items: Array<{
    id: number;
    type: "order" | "product";
    name: string;
    details: string;
    deleted_at: string;
    revision: string;
  }>;
  metrics: { total: number; orders: number; products: number };
};

export type BackupWorkspaceData = {
  settings: { enabled: boolean; folder: string; using_managed_folder: boolean; frequency: "daily" | "weekly" | "manual"; max_backups: number; last_backup: string | null };
  backups: Array<{ id: string; filename: string; created_at: string; size_bytes: number }>;
  summary: { count: number; total_bytes: number };
  revision: string;
};

export type ImportPreviewData = {
  import_type: "products" | "orders" | "customers";
  file: { name: string; size_bytes: number; source_detail: string };
  columns: Array<{ index: number; name: string; sample_values: string[]; suggested_field: string }>;
  preview_rows: string[][];
  fields: Array<{ name: string; label: string; required: boolean; type: "text" | "number" | "date" | "boolean" }>;
};

export type ImportResultData = {
  success: boolean;
  imported_count: number;
  skipped_count: number;
  error_count: number;
  errors: string[];
  warnings: string[];
  messages_truncated: boolean;
};

export type CloudSyncWorkspaceData = {
  enabled: boolean;
  provider: string;
  interval_minutes: number;
  providers: Array<{ key: string; label: string; fields: Array<{ key: string; label: string; required: boolean; sensitive: boolean; default: string; configured: boolean }> }>;
  ready: boolean;
  configured_field_count: number;
  revision: string;
};

export type MaterialOption = {
  id: number;
  sku: string;
  name: string;
  category: string;
  description: string;
  unit_of_measure: string;
  quantity_on_hand: number;
  reorder_point: number;
  cost_per_unit: string;
  inventory_value: string;
  vendor: VendorSummary | null;
  vendor_id: number | null;
  last_restocked: string | null;
  lead_time_days: number;
  notes: string;
  stock_status: "healthy" | "low" | "reorder";
  revision: string;
};

export type MaterialDetail = MaterialOption & {
  transactions: Array<{
    id: number;
    transaction_date: string;
    quantity_delta: number;
    unit_cost: string;
    reason: string;
    reference_type: string;
    reference_id: number | null;
    notes: string;
  }>;
};

export type ProductOption = {
  id: number;
  sku: string;
  name: string;
  description: string;
  inventory_count: number;
  status: string;
  unit_price: string;
  base_unit_cost: string;
  unit_cost: string;
  additional_unit_cost: string;
  cost_components: Array<{ label: string; amount: string }>;
  photo_configured: boolean;
  photo_available: boolean;
  is_complete: boolean;
  forecast: { average_weekly_sales: number; days_until_stockout: number | null; needs_reorder: boolean };
  revision: string;
};

export type OrderOptions = {
  statuses: OrderStatus[];
  carriers: string[];
  tax_rate_percent: string;
  tax_add_to_total: boolean;
  next_order_number: string;
};

export const bridgeUrl = process.env.NEXT_PUBLIC_HUSTLENEST_API_URL ?? "http://127.0.0.1:8765";

export async function getBridgeData<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${bridgeUrl}${path}`, { signal });
  const payload = (await response.json()) as { ok: boolean; data?: T; error?: { message: string } };
  if (!response.ok || !payload.ok || payload.data === undefined) {
    throw new Error(payload.error?.message || "HustleNest data is unavailable.");
  }
  return payload.data;
}
