"use client";

import {
  ArrowUpRight,
  BadgeDollarSign,
  Ban,
  Bell,
  CalendarDays,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleAlert,
  CircleDollarSign,
  ClipboardList,
  Cloud,
  FileText,
  Mail,
  MapPin,
  Moon,
  MoreHorizontal,
  Package,
  PackageCheck,
  Paperclip,
  Phone,
  Plus,
  Search,
  SlidersHorizontal,
  Sparkles,
  Sun,
  Trash2,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { AppNavigation } from "./components/app-navigation";
import { CustomersWorkspace } from "./components/customers-workspace";
import { DocumentsWorkspace } from "./components/documents-workspace";
import { FinanceWorkspace } from "./components/finance-workspace";
import { GlobalSearch, type GlobalSearchResult } from "./components/global-search";
import { GoalPanel } from "./components/goal-panel";
import { GeographyWorkspace } from "./components/geography-workspace";
import { HistoryWorkspace } from "./components/history-workspace";
import { HomeWorkspace } from "./components/home-workspace";
import { InventoryAdjustmentPanel } from "./components/inventory-adjustment-panel";
import { MaterialsWorkspace } from "./components/materials-workspace";
import { ProductsWorkspace } from "./components/products-workspace";
import { QuickAddPanel, type EditableRecord, type QuickAddType } from "./components/quick-add-panel";
import { ReportsWorkspace } from "./components/reports-workspace";
import { SettingsWorkspace } from "./components/settings-workspace";
import { TrashWorkspace } from "./components/trash-workspace";
import { VendorsWorkspace } from "./components/vendors-workspace";
import { bridgeUrl } from "./lib/hustlenest";
import type {
  BridgeOrder,
  BridgeState,
  CustomerDetail,
  CustomerOption,
  DocumentsWorkspaceData,
  FinanceWorkspaceData,
  HomeWorkspaceData,
  MaterialDetail,
  MaterialOption,
  Order,
  OrderMetrics,
  OrderOptions,
  OrderStatus,
  ProductOption,
  ReportsWorkspaceData,
  SettingsWorkspaceData,
  VendorOption,
  WorkspaceView,
} from "./lib/hustlenest";

const initialOrders: Order[] = [
  {
    id: 1,
    number: "HN-1048",
    customer: "Willow & Pine Studio",
    initials: "WP",
    email: "orders@willowandpine.co",
    phone: "(512) 555-0144",
    location: "Austin, TX",
    date: "Jul 15",
    due: "Jul 18",
    total: 684,
    status: "Processing",
    paid: true,
    items: [
      { name: "Hand-stamped copper tags", detail: "Custom 2 in · antique finish", quantity: 40, price: 12 },
      { name: "Gift packaging set", detail: "Kraft box + moss ribbon", quantity: 12, price: 17 },
    ],
    note: "Match the finish from their spring order. Send a photo before packing.",
  },
  {
    id: 2,
    number: "HN-1047",
    customer: "Mara Jensen",
    initials: "MJ",
    email: "mara.jensen@example.com",
    phone: "(816) 555-0198",
    location: "Kansas City, MO",
    date: "Jul 14",
    due: "Today",
    total: 248.5,
    status: "Ready to Ship",
    paid: true,
    items: [
      { name: "Botanical wall hanging", detail: "Large · walnut · fern pattern", quantity: 1, price: 198.5 },
      { name: "Priority shipping", detail: "Insured", quantity: 1, price: 50 },
    ],
    note: "Leave package at the side entrance if no one answers.",
  },
  {
    id: 3,
    number: "HN-1046",
    customer: "The Little Lantern",
    initials: "LL",
    email: "hello@littlelantern.shop",
    phone: "(615) 555-0112",
    location: "Nashville, TN",
    date: "Jul 13",
    due: "Jul 17",
    total: 1120,
    status: "Received",
    paid: false,
    items: [
      { name: "Brass constellation cards", detail: "Wholesale pack · assorted", quantity: 80, price: 14 },
    ],
    note: "First wholesale order. Confirm tax exemption certificate before production.",
  },
  {
    id: 4,
    number: "HN-1045",
    customer: "Rowan Market Co.",
    initials: "RM",
    email: "purchasing@rowanmarket.co",
    phone: "(918) 555-0166",
    location: "Tulsa, OK",
    date: "Jul 11",
    due: "Jul 15",
    total: 396,
    status: "Processing",
    paid: false,
    items: [
      { name: "Leather key fobs", detail: "Cognac · brass hardware", quantity: 24, price: 16.5 },
    ],
    note: "Payment reminder sent July 14.",
  },
  {
    id: 5,
    number: "HN-1044",
    customer: "Nora Bell",
    initials: "NB",
    email: "nora.bell@example.com",
    phone: "(314) 555-0137",
    location: "St. Louis, MO",
    date: "Jul 10",
    due: "Jul 16",
    total: 172,
    status: "Shipped",
    paid: true,
    items: [
      { name: "Pressed flower frame", detail: "8 × 10 · oak", quantity: 2, price: 86 },
    ],
    note: "Tracking: 1Z HN5 03A 92 1182 4356",
  },
];

const stages: OrderStatus[] = ["Received", "Paid", "Processing", "Ready to Ship", "Shipped"];
const filters = ["All orders", "Open", "Overdue", "Unpaid", "Ready to ship"];

function currency(value: number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

function statusClass(status: OrderStatus) {
  return `status status-${status.toLowerCase().replaceAll(" ", "-")}`;
}

function displayDate(value: string) {
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric" }).format(
    new Date(`${value}T12:00:00`),
  );
}

function displayDue(value: string | null) {
  if (!value) return "Not set";
  const today = new Date();
  const todayKey = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
  if (value === todayKey) return "Today";
  return displayDate(value);
}

function initials(name: string) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}

function mapBridgeOrder(order: BridgeOrder): Order {
  return {
    id: order.id,
    number: order.number,
    customer: order.customer_name,
    initials: initials(order.customer_name),
    email: order.customer.email || "No email on file",
    phone: order.customer.phone || "No phone on file",
    location: order.customer.address || "No address on file",
    customerId: order.customer_id,
    orderDate: order.order_date,
    targetDate: order.target_completion_date,
    carrier: order.shipping.carrier,
    trackingNumber: order.shipping.tracking_number,
    date: displayDate(order.order_date),
    due: displayDue(order.target_completion_date),
    total: Number(order.total),
    subtotal: Number(order.subtotal),
    taxAmount: Number(order.tax_amount),
    status: order.status,
    paid: order.payment_status === "paid",
    items: order.items.map((item) => ({
      productId: item.product_id,
      sku: item.sku,
      name: item.name,
      detail: [item.sku, item.description].filter(Boolean).join(" · "),
      quantity: item.quantity,
      price: Number(item.unit_price),
    })),
    note: order.notes || "No internal notes yet.",
    activity: order.activity,
    overdue: order.attention_reasons.includes("overdue") || order.attention_reasons.includes("due_today"),
    live: true,
  };
}

export default function HustleNestWorkspace() {
  const [activeView, setActiveView] = useState<WorkspaceView>("home");
  const [orders, setOrders] = useState(initialOrders);
  const [customers, setCustomers] = useState<CustomerOption[]>([]);
  const [products, setProducts] = useState<ProductOption[]>([]);
  const [materials, setMaterials] = useState<MaterialOption[]>([]);
  const [vendors, setVendors] = useState<VendorOption[]>([]);
  const [finance, setFinance] = useState<FinanceWorkspaceData | null>(null);
  const [reports, setReports] = useState<ReportsWorkspaceData | null>(null);
  const [home, setHome] = useState<HomeWorkspaceData | null>(null);
  const [documents, setDocuments] = useState<DocumentsWorkspaceData | null>(null);
  const [settings, setSettings] = useState<SettingsWorkspaceData | null>(null);
  const [focusedMaterialId, setFocusedMaterialId] = useState<number | null>(null);
  const [focusedCustomerKey, setFocusedCustomerKey] = useState<string | null>(null);
  const [focusedProductId, setFocusedProductId] = useState<number | null>(null);
  const [focusedVendorId, setFocusedVendorId] = useState<number | null>(null);
  const [focusedFinance, setFocusedFinance] = useState<{ mode: "expenses" | "recurring" | "losses"; id: number } | null>(null);
  const [focusedDocumentId, setFocusedDocumentId] = useState<number | null>(null);
  const [selectedId, setSelectedId] = useState(2);
  const [filter, setFilter] = useState("All orders");
  const [composerOpen, setComposerOpen] = useState(false);
  const [quickAddOpen, setQuickAddOpen] = useState(false);
  const [goalPanelOpen, setGoalPanelOpen] = useState(false);
  const [editingRecord, setEditingRecord] = useState<EditableRecord | null>(null);
  const [adjustingMaterial, setAdjustingMaterial] = useState<MaterialOption | null>(null);
  const [editingOrder, setEditingOrder] = useState<Order | null>(null);
  const [seedCustomer, setSeedCustomer] = useState<CustomerOption | null>(null);
  const [seedProduct, setSeedProduct] = useState<ProductOption | null>(null);
  const [darkMode, setDarkMode] = useState(false);
  const [bridgeState, setBridgeState] = useState<BridgeState>("connecting");
  const [bridgeMessage, setBridgeMessage] = useState("Connecting to your HustleNest data…");
  const [metrics, setMetrics] = useState<OrderMetrics | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [advancing, setAdvancing] = useState(false);
  const [lifecycleAction, setLifecycleAction] = useState<"payment" | "invoice" | "cancel" | null>(null);
  const [cancelCandidate, setCancelCandidate] = useState<Order | null>(null);
  const [trashCandidate, setTrashCandidate] = useState<{ type: "order"; record: Order } | { type: "product"; record: ProductOption } | null>(null);
  const [trashWorking, setTrashWorking] = useState(false);

  useEffect(() => {
    const controller = new AbortController();

    Promise.all([
      fetch(`${bridgeUrl}/api/orders?limit=100`, { signal: controller.signal }),
      fetch(`${bridgeUrl}/api/orders/metrics`, { signal: controller.signal }),
      fetch(`${bridgeUrl}/api/customers?limit=200`, { signal: controller.signal }),
      fetch(`${bridgeUrl}/api/products?limit=200`, { signal: controller.signal }),
      fetch(`${bridgeUrl}/api/materials?limit=200`, { signal: controller.signal }),
      fetch(`${bridgeUrl}/api/vendors?limit=200`, { signal: controller.signal }),
      fetch(`${bridgeUrl}/api/finance?limit=200`, { signal: controller.signal }),
      fetch(`${bridgeUrl}/api/reports?period=this_year`, { signal: controller.signal }),
      fetch(`${bridgeUrl}/api/home`, { signal: controller.signal }),
      fetch(`${bridgeUrl}/api/documents`, { signal: controller.signal }),
      fetch(`${bridgeUrl}/api/settings`, { signal: controller.signal }),
    ])
      .then(async ([ordersResponse, metricsResponse, customersResponse, productsResponse, materialsResponse, vendorsResponse, financeResponse, reportsResponse, homeResponse, documentsResponse, settingsResponse]) => {
        if ([ordersResponse, metricsResponse, customersResponse, productsResponse, materialsResponse, vendorsResponse, financeResponse, reportsResponse, homeResponse, documentsResponse, settingsResponse].some((response) => !response.ok)) throw new Error("Bridge request failed");
        const ordersPayload = (await ordersResponse.json()) as { ok: boolean; data: BridgeOrder[] };
        const metricsPayload = (await metricsResponse.json()) as { ok: boolean; data: OrderMetrics };
        const customersPayload = (await customersResponse.json()) as { ok: boolean; data: CustomerOption[] };
        const productsPayload = (await productsResponse.json()) as { ok: boolean; data: ProductOption[] };
        const materialsPayload = (await materialsResponse.json()) as { ok: boolean; data: MaterialOption[] };
        const vendorsPayload = (await vendorsResponse.json()) as { ok: boolean; data: VendorOption[] };
        const financePayload = (await financeResponse.json()) as { ok: boolean; data: FinanceWorkspaceData };
        const reportsPayload = (await reportsResponse.json()) as { ok: boolean; data: ReportsWorkspaceData };
        const homePayload = (await homeResponse.json()) as { ok: boolean; data: HomeWorkspaceData };
        const documentsPayload = (await documentsResponse.json()) as { ok: boolean; data: DocumentsWorkspaceData };
        const settingsPayload = (await settingsResponse.json()) as { ok: boolean; data: SettingsWorkspaceData };
        if (!ordersPayload.ok || !metricsPayload.ok || !customersPayload.ok || !productsPayload.ok || !materialsPayload.ok || !vendorsPayload.ok || !financePayload.ok || !reportsPayload.ok || !homePayload.ok || !documentsPayload.ok || !settingsPayload.ok) throw new Error("Bridge response failed");
        setMetrics(metricsPayload.data);
        setCustomers(customersPayload.data);
        setProducts(productsPayload.data);
        setMaterials(materialsPayload.data);
        setVendors(vendorsPayload.data);
        setFinance(financePayload.data);
        setReports(reportsPayload.data);
        setHome(homePayload.data);
        setDocuments(documentsPayload.data);
        setSettings(settingsPayload.data);
        setDarkMode(settingsPayload.data.appearance.theme === "dark");
        if (ordersPayload.data.length === 0) {
          setBridgeState("demo");
          setBridgeMessage("Your database has no orders yet. Showing sample data for workflow review.");
          return;
        }
        const connectedOrders = ordersPayload.data.map(mapBridgeOrder);
        setOrders((current) => connectedOrders.map((order) => ({ ...order, activity: current.find((item) => item.id === order.id && item.live)?.activity ?? order.activity })));
        setSelectedId(connectedOrders[0].id);
        setBridgeState("connected");
        setBridgeMessage(`${connectedOrders.length} live orders loaded from your local database.`);
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setBridgeState("error");
        setBridgeMessage("The local data bridge is offline. Sample data remains available.");
      });

    return () => controller.abort();
  }, [reloadKey]);

  useEffect(() => {
    if (bridgeState !== "connected") return;
    const controller = new AbortController();
    fetch(`${bridgeUrl}/api/orders/${selectedId}`, { signal: controller.signal })
      .then(async (response) => {
        const payload = (await response.json()) as { ok: boolean; data?: BridgeOrder };
        if (!response.ok || !payload.ok || !payload.data) return;
        const detailed = mapBridgeOrder(payload.data);
        setOrders((current) => current.map((item) => item.id === detailed.id && item.live ? detailed : item));
      })
      .catch(() => undefined);
    return () => controller.abort();
  }, [bridgeState, reloadKey, selectedId]);

  const selected = orders.find((order) => order.id === selectedId) ?? orders[0];

  const globalSearchResults = useMemo<GlobalSearchResult[]>(() => {
    const result = (kind: GlobalSearchResult["kind"], id: number | string, title: string, subtitle: string, terms: Array<string | number | null | undefined>): GlobalSearchResult => ({
      key: `${kind}:${id}`,
      kind,
      id,
      title,
      subtitle,
      searchText: [title, subtitle, ...terms].join(" ").toLocaleLowerCase(),
    });
    return [
      ...orders.map((order) => result("order", order.id, order.number, `${order.customer} · ${order.status} · ${currency(order.total)}`, [order.customer, order.location, order.note, ...order.items.map((item) => `${item.sku ?? ""} ${item.name}`)])),
      ...customers.map((customer) => result("customer", customer.key, customer.name, customer.company || customer.email || "Customer", [customer.email, customer.phone, customer.address, customer.notes])),
      ...products.map((product) => result("product", product.id, product.name, `${product.sku} · ${product.inventory_count} in stock`, [product.sku, product.description, product.status])),
      ...materials.map((material) => result("material", material.id, material.name, `${material.sku} · ${material.quantity_on_hand} ${material.unit_of_measure}`, [material.category, material.description, material.vendor?.name, material.notes])),
      ...vendors.map((vendor) => result("vendor", vendor.id, vendor.name, vendor.contact_name || vendor.email || "Vendor", [vendor.email, vendor.phone, vendor.account_number, vendor.notes])),
      ...(finance?.expenses ?? []).map((expense) => result("expense", expense.id, expense.category, `${currency(Number(expense.amount))} · ${expense.expense_date}`, [expense.description, expense.vendor?.name, expense.payment_method, expense.notes, ...expense.tags])),
      ...(finance?.recurring ?? []).map((item) => result("recurring", item.id, item.category, `${currency(Number(item.amount))} · ${item.frequency}`, [item.vendor?.name, item.notes, item.next_occurrence])),
      ...(finance?.losses ?? []).map((loss) => result("loss", loss.id, loss.category, `${currency(Number(loss.amount))} · ${loss.loss_date}`, [loss.description, loss.details, loss.product_name, loss.material_name, loss.recorded_by])),
      ...(documents?.documents ?? []).map((document) => result("document", document.id, document.name, `${document.category} · ${document.entity.label}`, [document.description, document.extension, document.entity.detail, ...document.tags])),
    ];
  }, [customers, documents, finance, materials, orders, products, vendors]);

  const filteredOrders = useMemo(() => {
    return orders.filter((order) => {
      if (filter === "Open") return order.status !== "Shipped" && order.status !== "Cancelled";
      if (filter === "Overdue") return Boolean(order.overdue) || order.due === "Today";
      if (filter === "Unpaid") return !order.paid;
      if (filter === "Ready to ship") return order.status === "Ready to Ship";
      return true;
    });
  }, [filter, orders]);

  const advanceSelectedOrder = async () => {
    if (selected.live) {
      setAdvancing(true);
      try {
        const response = await fetch(`${bridgeUrl}/api/orders/${selected.id}/advance`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ expected_status: selected.status }),
        });
        const payload = (await response.json()) as {
          ok: boolean;
          data?: BridgeOrder;
          error?: { message: string };
        };
        if (!response.ok || !payload.ok || !payload.data) {
          throw new Error(payload.error?.message || "The order could not be updated.");
        }
        const updated = mapBridgeOrder(payload.data);
        setOrders((current) => current.map((order) => (order.id === updated.id ? updated : order)));
        const metricsResponse = await fetch(`${bridgeUrl}/api/orders/metrics`);
        if (metricsResponse.ok) {
          const metricsPayload = (await metricsResponse.json()) as { ok: boolean; data: OrderMetrics };
          if (metricsPayload.ok) setMetrics(metricsPayload.data);
        }
        setBridgeMessage(`${updated.number} advanced to ${updated.status}.`);
      } catch (error: unknown) {
        setBridgeState("error");
        setBridgeMessage(error instanceof Error ? error.message : "The order could not be updated.");
      } finally {
        setAdvancing(false);
      }
      return;
    }
    const index = stages.indexOf(selected.status);
    const nextStatus = stages[Math.min(index + 1, stages.length - 1)];
    setOrders((current) =>
      current.map((order) =>
        order.id === selected.id
          ? { ...order, status: nextStatus, paid: nextStatus === "Paid" ? true : order.paid }
          : order,
      ),
    );
  };

  const handleOrderSaved = async (savedOrder: BridgeOrder) => {
    const mapped = mapBridgeOrder(savedOrder);
    setOrders((current) => {
      const exists = current.some((order) => order.id === mapped.id && order.live);
      return exists
        ? current.map((order) => (order.id === mapped.id && order.live ? mapped : order))
        : [mapped, ...current.filter((order) => order.live)];
    });
    setSelectedId(mapped.id);
    setComposerOpen(false);
    setEditingOrder(null);
    setSeedCustomer(null);
    setSeedProduct(null);
    setActiveView("orders");
    setBridgeState("connected");
    setBridgeMessage(`${mapped.number} ${editingOrder ? "updated" : "created"} successfully.`);
    try {
      const response = await fetch(`${bridgeUrl}/api/orders/metrics`);
      const payload = (await response.json()) as { ok: boolean; data: OrderMetrics };
      if (response.ok && payload.ok) setMetrics(payload.data);
      const [customerResponse, productResponse] = await Promise.all([
        fetch(`${bridgeUrl}/api/customers?limit=200`),
        fetch(`${bridgeUrl}/api/products?limit=200`),
      ]);
      if (customerResponse.ok) {
        const customerPayload = (await customerResponse.json()) as { ok: boolean; data: CustomerOption[] };
        if (customerPayload.ok) setCustomers(customerPayload.data);
      }
      if (productResponse.ok) {
        const productPayload = (await productResponse.json()) as { ok: boolean; data: ProductOption[] };
        if (productPayload.ok) setProducts(productPayload.data);
      }
    } catch {
      // The saved order remains visible even if the metric refresh is unavailable.
    }
  };

  const openCount = metrics?.open_orders ?? orders.filter((order) => order.status !== "Shipped" && order.status !== "Cancelled").length;
  const awaitingPayment = metrics ? Number(metrics.awaiting_payment) : orders.filter((order) => !order.paid).reduce((sum, order) => sum + order.total, 0);
  const unpaidCount = metrics?.awaiting_payment_count ?? orders.filter((order) => !order.paid).length;
  const readyCount = metrics?.ready_to_ship ?? orders.filter((order) => order.status === "Ready to Ship").length;
  const attentionCount = metrics?.needs_attention ?? orders.filter((order) => order.overdue).length;

  const toggleTheme = async () => {
    const next = darkMode ? "light" : "dark";
    setDarkMode(next === "dark");
    if (!settings) return;
    try {
      const response = await fetch(`${bridgeUrl}/api/settings`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ section: "appearance", values: { theme: next }, expected_revision: settings.summary.revision }) });
      const payload = await response.json() as { ok: boolean; data?: SettingsWorkspaceData; error?: { message: string } };
      if (!response.ok || !payload.ok || !payload.data) throw new Error(payload.error?.message || "Theme preference could not be saved.");
      setSettings(payload.data);
    } catch (error) { setBridgeMessage(error instanceof Error ? error.message : "Theme preference could not be saved."); }
  };

  const openOrder = (orderId: number) => {
    setSelectedId(orderId);
    setActiveView("orders");
  };

  const startOrder = (customer?: CustomerOption, product?: ProductOption) => {
    setEditingOrder(null);
    setSeedCustomer(customer ?? null);
    setSeedProduct(product ?? null);
    setComposerOpen(true);
  };

  const openMaterial = (materialId: number) => {
    setFocusedMaterialId(materialId);
    setActiveView("materials");
  };

  const refreshOrderMetrics = async () => {
    const response = await fetch(`${bridgeUrl}/api/orders/metrics`);
    if (!response.ok) return;
    const payload = (await response.json()) as { ok: boolean; data: OrderMetrics };
    if (payload.ok) setMetrics(payload.data);
  };

  const toggleSelectedPayment = async () => {
    if (!selected.live) return;
    setLifecycleAction("payment");
    try {
      const requested = selected.paid ? "unpaid" : "paid";
      const response = await fetch(`${bridgeUrl}/api/orders/${selected.id}/payment`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expected_payment_status: selected.paid ? "paid" : "unpaid", payment_status: requested }) });
      const payload = (await response.json()) as { ok: boolean; data?: BridgeOrder; error?: { message: string } };
      if (!response.ok || !payload.ok || !payload.data) throw new Error(payload.error?.message || "Payment status could not be updated.");
      const updated = mapBridgeOrder(payload.data);
      setOrders((current) => current.map((order) => order.id === updated.id && order.live ? updated : order));
      await refreshOrderMetrics();
      setBridgeMessage(`${updated.number} marked ${requested}.`);
    } catch (error: unknown) {
      setBridgeMessage(error instanceof Error ? error.message : "Payment status could not be updated.");
    } finally { setLifecycleAction(null); }
  };

  const downloadSelectedInvoice = async () => {
    if (!selected.live) return;
    setLifecycleAction("invoice");
    try {
      const response = await fetch(`${bridgeUrl}/api/orders/${selected.id}/invoice`);
      if (!response.ok) {
        const payload = await response.json() as { error?: { message: string } };
        throw new Error(payload.error?.message || "The invoice could not be generated.");
      }
      const blob = await response.blob();
      const disposition = response.headers.get("Content-Disposition") ?? "";
      const filename = disposition.match(/filename="([^"]+)"/)?.[1] ?? `${selected.number}_${selected.paid ? "receipt" : "invoice"}.pdf`;
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      setBridgeMessage(`${filename} generated.`);
    } catch (error: unknown) {
      setBridgeMessage(error instanceof Error ? error.message : "The invoice could not be generated.");
    } finally { setLifecycleAction(null); }
  };

  const cancelSelectedOrder = async () => {
    const order = cancelCandidate;
    if (!order?.live) return;
    setLifecycleAction("cancel");
    try {
      const response = await fetch(`${bridgeUrl}/api/orders/${order.id}/cancel`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expected_status: order.status }) });
      const payload = (await response.json()) as { ok: boolean; data?: BridgeOrder; error?: { message: string } };
      if (!response.ok || !payload.ok || !payload.data) throw new Error(payload.error?.message || "The order could not be cancelled.");
      const updated = mapBridgeOrder(payload.data);
      setOrders((current) => current.map((item) => item.id === updated.id && item.live ? updated : item));
      setCancelCandidate(null);
      await refreshOrderMetrics();
      setBridgeMessage(`${updated.number} cancelled and its product inventory restored.`);
      setReloadKey((value) => value + 1);
    } catch (error: unknown) {
      setBridgeMessage(error instanceof Error ? error.message : "The order could not be cancelled.");
      setCancelCandidate(null);
    } finally { setLifecycleAction(null); }
  };

  const moveCandidateToTrash = async () => {
    if (!trashCandidate) return;
    setTrashWorking(true);
    const item = trashCandidate.record;
    try {
      const url = trashCandidate.type === "order" ? `${bridgeUrl}/api/orders/${item.id}` : `${bridgeUrl}/api/records/product/${item.id}`;
      const guard = trashCandidate.type === "order"
        ? { expected_status: trashCandidate.record.status }
        : { expected_revision: trashCandidate.record.revision };
      const response = await fetch(url, { method: "DELETE", headers: { "Content-Type": "application/json" }, body: JSON.stringify(guard) });
      const payload = await response.json() as { ok: boolean; error?: { message: string } };
      if (!response.ok || !payload.ok) throw new Error(payload.error?.message || "The item could not be moved to trash.");
      const label = trashCandidate.type === "order" ? trashCandidate.record.number : trashCandidate.record.name;
      setTrashCandidate(null);
      setBridgeMessage(`${label} moved to trash. It can be restored from Recently deleted.`);
      setReloadKey((value) => value + 1);
    } catch (error) {
      setBridgeMessage(error instanceof Error ? error.message : "The item could not be moved to trash.");
      setTrashCandidate(null);
    } finally { setTrashWorking(false); }
  };

  const openSearchResult = (result: GlobalSearchResult) => {
    if (result.kind === "order") return openOrder(Number(result.id));
    if (result.kind === "customer") { setFocusedCustomerKey(String(result.id)); setActiveView("customers"); return; }
    if (result.kind === "product") { setFocusedProductId(Number(result.id)); setActiveView("products"); return; }
    if (result.kind === "material") { setFocusedMaterialId(Number(result.id)); setActiveView("materials"); return; }
    if (result.kind === "vendor") { setFocusedVendorId(Number(result.id)); setActiveView("vendors"); return; }
    if (result.kind === "expense" || result.kind === "recurring" || result.kind === "loss") {
      setFocusedFinance({ mode: result.kind === "expense" ? "expenses" : result.kind === "recurring" ? "recurring" : "losses", id: Number(result.id) });
      setActiveView("finance");
      return;
    }
    setFocusedDocumentId(Number(result.id));
    setActiveView("documents");
  };

  const editCustomer = (customer: CustomerOption) => {
    if (!customer.id) return;
    setEditingRecord({ id: customer.id, type: "customer", revision: customer.revision, values: { name: customer.name, company: customer.company, email: customer.email, phone: customer.phone, address: customer.address, notes: customer.notes } });
  };
  const editProduct = (product: ProductOption) => setEditingRecord({ id: product.id, type: "product", revision: product.revision, values: { sku: product.sku, name: product.name, description: product.description, inventory_count: String(product.inventory_count), unit_cost: product.base_unit_cost, unit_price: product.unit_price, status: product.status, cost_components: JSON.stringify(product.cost_components) } });
  const editMaterial = (material: MaterialOption) => setEditingRecord({ id: material.id, type: "material", revision: material.revision, values: { sku: material.sku, name: material.name, category: material.category, description: material.description, unit_of_measure: material.unit_of_measure, quantity_on_hand: String(material.quantity_on_hand), reorder_point: String(material.reorder_point), cost_per_unit: material.cost_per_unit, vendor_id: material.vendor_id ? String(material.vendor_id) : "", notes: material.notes } });
  const editVendor = (vendor: VendorOption) => setEditingRecord({ id: vendor.id, type: "vendor", revision: vendor.revision, values: { name: vendor.name, contact_name: vendor.contact_name, email: vendor.email, phone: vendor.phone, website: vendor.website, account_number: vendor.account_number, preferred_payment_method: vendor.preferred_payment_method, notes: vendor.notes } });
  const editExpense = (expense: FinanceWorkspaceData["expenses"][number]) => setEditingRecord({ id: expense.id, type: "expense", revision: expense.revision, values: { category: expense.category, amount: expense.amount, date: expense.expense_date, description: expense.description, vendor_id: expense.vendor_id ? String(expense.vendor_id) : "", payment_method: expense.payment_method, notes: expense.notes } });
  const editRecurring = (item: FinanceWorkspaceData["recurring"][number]) => setEditingRecord({ id: item.id, type: "recurring", revision: item.revision, values: { category: item.category, amount: item.amount, frequency: item.frequency.toLowerCase(), start_date: item.start_date ?? "", next_occurrence: item.next_occurrence ?? "", end_date: item.end_date ?? "", auto_record: String(item.auto_record), vendor_id: item.vendor_id ? String(item.vendor_id) : "", notes: item.notes } });
  const editLoss = (loss: FinanceWorkspaceData["losses"][number]) => setEditingRecord({ id: loss.id, type: "loss", revision: loss.revision, values: { category: loss.category, amount: loss.amount, date: loss.loss_date, description: loss.description, notes: loss.details } });
  const handleInteractionSaved = (customer: CustomerDetail) => {
    setCustomers((current) => current.map((item) => item.id === customer.id ? customer : item));
    setFocusedCustomerKey(customer.key);
    setBridgeMessage(`Interaction with ${customer.name} saved. Follow-up activity refreshed.`);
    setReloadKey((value) => value + 1);
  };
  const handleCustomerPromoted = (customer: CustomerOption) => {
    setFocusedCustomerKey(customer.key);
    setBridgeState("connecting");
    setBridgeMessage(`${customer.name} added to contacts. Refreshing customer history…`);
    setReloadKey((value) => value + 1);
  };
  const handleInventoryAdjusted = (material: MaterialDetail) => {
    setAdjustingMaterial(null);
    setFocusedMaterialId(material.id);
    setActiveView("materials");
    setBridgeState("connecting");
    setBridgeMessage(`${material.name} inventory updated. Refreshing activity…`);
    setReloadKey((value) => value + 1);
  };

  const handleQuickAddSaved = (type: QuickAddType, id: number, label: string) => {
    const target: Record<QuickAddType, WorkspaceView> = {
      customer: "customers",
      product: "products",
      material: "materials",
      vendor: "vendors",
      expense: "finance",
      recurring: "finance",
      loss: "finance",
    };
    if (type === "customer") setFocusedCustomerKey(`crm:${id}`);
    if (type === "product") setFocusedProductId(id);
    if (type === "material") setFocusedMaterialId(id);
    if (type === "vendor") setFocusedVendorId(id);
    if (type === "expense" || type === "recurring" || type === "loss") setFocusedFinance({ mode: type === "expense" ? "expenses" : type === "recurring" ? "recurring" : "losses", id });
    setQuickAddOpen(false);
    setEditingRecord(null);
    setActiveView(target[type]);
    setBridgeState("connecting");
    setBridgeMessage(`${label} saved. Refreshing your workspace…`);
    setReloadKey((value) => value + 1);
  };
  const handleQuickAddDeleted = (type: QuickAddType) => {
    setQuickAddOpen(false);
    setEditingRecord(null);
    if (type === "customer") setFocusedCustomerKey(null);
    if (type === "product") setFocusedProductId(null);
    if (type === "material") setFocusedMaterialId(null);
    if (type === "vendor") setFocusedVendorId(null);
    if (type === "expense" || type === "recurring" || type === "loss") setFocusedFinance(null);
    setBridgeState("connecting");
    setBridgeMessage(type === "product" ? "Product moved to Recently deleted. Refreshing your workspace…" : `${type[0].toUpperCase()}${type.slice(1)} deleted. Refreshing your workspace…`);
    setReloadKey((value) => value + 1);
  };

  return (
    <main className={darkMode ? "app-shell dark" : "app-shell"}>
      <AppNavigation
        activeView={activeView}
        onNavigate={setActiveView}
        orderCount={openCount}
        customerCount={customers.length}
        productCount={products.length}
        materialCount={materials.length}
        vendorCount={vendors.length}
        expenseCount={finance?.expenses.length ?? 0}
        businessName={settings?.business.name}
        showBusinessName={settings?.business.show_name_on_dashboard}
        logoAvailable={settings?.business.logo_available}
        brandingRevision={settings?.summary.revision}
      />

      <section className="main-column">
        <header className="topbar">
          <GlobalSearch results={globalSearchResults} onSelect={openSearchResult} />
          <div className="top-actions">
            <span className={`sync-state bridge-${bridgeState}`}>
              <Cloud size={16} />
              {bridgeState === "connected" ? "Local data connected" : bridgeState === "connecting" ? "Connecting…" : "Demo data"}
            </span>
            <button className="icon-button" aria-label="Toggle theme" onClick={() => void toggleTheme()}>
              {darkMode ? <Sun size={19} /> : <Moon size={19} />}
            </button>
            <button className="icon-button notification-button" aria-label="Open priorities and notifications" onClick={() => setActiveView("home")}>
              <Bell size={19} />
              <span />
            </button>
            <button className="primary-button" onClick={() => startOrder()} data-testid="quick-add-order">
              <Plus size={18} /> New order
            </button>
            <button className="secondary-button quick-add-button" onClick={() => setQuickAddOpen(true)} data-testid="quick-add-record">
              <Sparkles size={17} /> Quick add
            </button>
          </div>
        </header>

        {activeView === "home" ? (
          <HomeWorkspace home={home} onNavigate={setActiveView} onOpenOrder={openOrder} onOpenMaterial={openMaterial} onNewOrder={() => startOrder()} onManageGoals={() => setGoalPanelOpen(true)} />
        ) : activeView === "orders" ? (
        <div className="workspace">
          <div className="page-heading">
            <div>
              <div className="eyebrow"><span>Sales</span><ChevronRight size={14} /><span>Orders</span></div>
              <h1>Orders</h1>
              <p>Keep every promise, payment, and package moving.</p>
            </div>
            <button className="secondary-button" onClick={() => void downloadSelectedInvoice()} disabled={!selected.live || lifecycleAction === "invoice"}><FileText size={17} /> {lifecycleAction === "invoice" ? "Generating…" : "Invoice PDF"}</button>
          </div>

          <div className={`bridge-banner bridge-${bridgeState}`} role="status" data-testid="bridge-status">
            <div>
              {bridgeState === "connected" ? <CheckCircle2 size={18} /> : bridgeState === "connecting" ? <Cloud size={18} /> : <CircleAlert size={18} />}
              <span>{bridgeMessage}</span>
            </div>
            {bridgeState === "error" ? (
              <button onClick={() => {
                setBridgeState("connecting");
                setBridgeMessage("Connecting to your HustleNest data…");
                setReloadKey((value) => value + 1);
              }}>Try again</button>
            ) : null}
          </div>

          <section className="metric-grid" aria-label="Order summary">
            <article className="metric-card accent-card">
              <div className="metric-icon"><ClipboardList size={20} /></div>
              <div><span>Open orders</span><strong>{openCount}</strong><small><ArrowUpRight size={13} /> Active fulfillment queue</small></div>
            </article>
            <article className="metric-card">
              <div className="metric-icon amber"><CircleDollarSign size={20} /></div>
              <div><span>Awaiting payment</span><strong>{currency(awaitingPayment)}</strong><small>{unpaidCount} customer balances</small></div>
            </article>
            <article className="metric-card">
              <div className="metric-icon violet"><PackageCheck size={20} /></div>
              <div><span>Ready to ship</span><strong>{readyCount}</strong><small>Prepared for fulfillment</small></div>
            </article>
            <article className="metric-card">
              <div className="metric-icon rose"><CircleAlert size={20} /></div>
              <div><span>Needs attention</span><strong>{attentionCount}</strong><small>Due today, overdue, or unpaid</small></div>
            </article>
          </section>

          <section className="orders-workspace">
            <div className="orders-list-panel">
              <div className="panel-toolbar">
                <div className="filter-tabs" role="tablist" aria-label="Order filters">
                  {filters.map((item) => (
                    <button
                      role="tab"
                      aria-selected={filter === item}
                      className={filter === item ? "active" : ""}
                      onClick={() => setFilter(item)}
                      key={item}
                    >
                      {item}
                    </button>
                  ))}
                </div>
                <button className="icon-button bordered" aria-label="More filters"><SlidersHorizontal size={17} /></button>
              </div>

              <div className="table-header order-grid">
                <span>Customer</span><span>Status</span><span>Due</span><span>Total</span><span />
              </div>

              <div className="order-rows">
                {filteredOrders.map((order) => (
                  <button
                    className={order.id === selected.id ? "order-row order-grid selected" : "order-row order-grid"}
                    key={order.id}
                    onClick={() => setSelectedId(order.id)}
                    data-testid={`order-${order.number}`}
                  >
                    <span className="customer-cell">
                      <span className={`avatar avatar-${order.id}`}>{order.initials}</span>
                      <span><strong>{order.customer}</strong><small>{order.number} · {order.date}</small></span>
                    </span>
                    <span><em className={statusClass(order.status)}>{order.status}</em></span>
                    <span className={order.due === "Today" || order.due === "Jul 15" ? "due urgent" : "due"}>{order.due}</span>
                    <span className="amount">{currency(order.total)}</span>
                    <span><ChevronRight size={17} /></span>
                  </button>
                ))}
                {filteredOrders.length === 0 ? (
                  <div className="empty-state"><Search size={25} /><strong>No orders found</strong><span>Try another name, number, or filter.</span></div>
                ) : null}
              </div>
            </div>

            <aside className="order-detail" aria-label={`Order ${selected.number} details`}>
              <div className="detail-topline">
                <span className={statusClass(selected.status)}>{selected.status}</span>
                <button className="icon-button" aria-label="More order actions"><MoreHorizontal size={19} /></button>
              </div>
              <div className="detail-title">
                <div><span>{selected.number}</span><h2>{selected.customer}</h2></div>
                <strong>{currency(selected.total)}</strong>
              </div>

              {selected.status === "Cancelled" ? <div className="cancelled-order-callout"><Ban size={17} /><div><strong>Order cancelled</strong><span>Its product inventory has been restored and the order is excluded from active totals.</span></div></div> : <div className="status-track" aria-label="Order progress">
                {stages.map((stage, index) => {
                  const currentIndex = stages.indexOf(selected.status);
                  const complete = index <= currentIndex;
                  return (
                    <div className={complete ? "stage complete" : "stage"} key={stage}>
                      <span>{complete ? <Check size={12} /> : index + 1}</span>
                      <small>{stage === "Ready to Ship" ? "Ready" : stage}</small>
                    </div>
                  );
                })}
              </div>}

              <div className="detail-actions">
                <button className="primary-button flex-button" onClick={advanceSelectedOrder} disabled={selected.status === "Shipped" || selected.status === "Cancelled" || advancing}>
                  {advancing ? "Updating…" : selected.status === "Cancelled" ? "Order cancelled" : selected.status === "Shipped" ? "Order complete" : "Advance status"}<ChevronRight size={17} />
                </button>
                <button className="secondary-button" onClick={() => void downloadSelectedInvoice()} disabled={!selected.live || lifecycleAction === "invoice"}><FileText size={17} /> {selected.paid ? "Receipt" : "Invoice"}</button>
                <button className="secondary-button" onClick={() => void toggleSelectedPayment()} disabled={!selected.live || selected.status === "Cancelled" || lifecycleAction === "payment"}><BadgeDollarSign size={17} /> {lifecycleAction === "payment" ? "Saving…" : selected.paid ? "Mark unpaid" : "Mark paid"}</button>
                {selected.live && selected.status !== "Cancelled" ? (
                  <button className="secondary-button" onClick={() => { setEditingOrder(selected); setComposerOpen(true); }}>
                    Edit order
                  </button>
                ) : null}
              </div>

              <div className="detail-section customer-summary">
                <div className="section-heading"><h3>Customer</h3><button>Edit</button></div>
                <p><Mail size={15} /> {selected.email}</p>
                <p><Phone size={15} /> {selected.phone}</p>
                <p><MapPin size={15} /> {selected.location}</p>
              </div>

              <div className="detail-section">
                <div className="section-heading"><h3>Items</h3><span>{selected.items.reduce((sum, item) => sum + item.quantity, 0)} units</span></div>
                {selected.items.map((item) => (
                  <div className="line-item" key={`${selected.id}-${item.name}`}>
                    <div className="product-thumb"><Package size={18} /></div>
                    <div><strong>{item.name}</strong><span>{item.detail}</span><small>{item.quantity} × {currency(item.price)}</small></div>
                    <strong>{currency(item.quantity * item.price)}</strong>
                  </div>
                ))}
              </div>

              <div className="detail-section totals">
                <p><span>Subtotal</span><strong>{currency(selected.subtotal ?? selected.total)}</strong></p>
                <p><span>Tax</span><strong>{currency(selected.taxAmount ?? 0)}</strong></p>
                <p className="total-line"><span>Total</span><strong>{currency(selected.total)}</strong></p>
                <p className={selected.paid ? "payment paid" : "payment unpaid"}>
                  {selected.paid ? <CheckCircle2 size={15} /> : <CircleAlert size={15} />}
                  {selected.paid ? "Paid in full" : "Payment outstanding"}
                </p>
              </div>

              <div className="detail-section note-card">
                <div className="section-heading"><h3>Internal note</h3><Paperclip size={15} /></div>
                <p>{selected.note}</p>
              </div>
              <div className="detail-section order-activity"><div className="section-heading"><h3>Order activity</h3><span>{selected.activity?.length ?? 0}</span></div>{selected.activity?.length ? selected.activity.slice(0, 8).map((event) => <div className="order-activity-row" key={event.id}><i className={`history-tone ${event.tone}`}><FileText size={13} /></i><div><span><strong>{event.event_type}</strong><time>{new Date(event.created_at).toLocaleString()}</time></span><p>{event.description}</p></div>{Number(event.amount_delta) ? <em>{Number(event.amount_delta) > 0 ? "+" : ""}{currency(Number(event.amount_delta))}</em> : null}</div>) : <p className="quiet-empty">No recorded changes for this order yet.</p>}</div>
              {selected.live && selected.status !== "Cancelled" && selected.status !== "Shipped" ? <button className="order-cancel-action" onClick={() => setCancelCandidate(selected)}><Ban size={15} /> Cancel order and restore inventory</button> : null}
              {selected.live ? <button className="order-trash-action" onClick={() => setTrashCandidate({ type: "order", record: selected })}><Trash2 size={15} /> Move order to trash</button> : null}
            </aside>
          </section>
        </div>
        ) : activeView === "customers" ? (
          <CustomersWorkspace
            key={`customers-${focusedCustomerKey ?? "list"}-${reloadKey}`}
            customers={customers}
            orders={orders.filter((order) => order.live)}
            onCreateOrder={(customer) => startOrder(customer)}
            onOpenOrder={openOrder}
            focusCustomerKey={focusedCustomerKey}
            onEdit={editCustomer}
            onInteractionSaved={handleInteractionSaved}
            onPromoted={handleCustomerPromoted}
          />
        ) : activeView === "products" ? (
          <ProductsWorkspace
            key={`products-${focusedProductId ?? "list"}-${reloadKey}`}
            products={products}
            orders={orders.filter((order) => order.live)}
            onCreateOrder={(product) => startOrder(undefined, product)}
            onOpenOrder={openOrder}
            focusProductId={focusedProductId}
            onEdit={editProduct}
            onTrash={(product) => setTrashCandidate({ type: "product", record: product })}
            onChanged={(message) => { setBridgeMessage(message); setReloadKey((value) => value + 1); }}
          />
        ) : activeView === "materials" ? (
          <MaterialsWorkspace key={`materials-${focusedMaterialId ?? "list"}-${reloadKey}`} materials={materials} focusMaterialId={focusedMaterialId} onEdit={editMaterial} onAdjust={setAdjustingMaterial} />
        ) : activeView === "vendors" ? (
          <VendorsWorkspace key={`vendors-${focusedVendorId ?? "list"}-${reloadKey}`} vendors={vendors} onOpenMaterial={openMaterial} focusVendorId={focusedVendorId} onEdit={editVendor} />
        ) : activeView === "finance" ? (
          <FinanceWorkspace key={`finance-${focusedFinance?.mode ?? "list"}-${focusedFinance?.id ?? 0}-${reloadKey}`} finance={finance} onOpenOrder={openOrder} onOpenMaterial={openMaterial} focusMode={focusedFinance?.mode} focusId={focusedFinance?.id} onEditExpense={editExpense} onEditRecurring={editRecurring} onEditLoss={editLoss} />
        ) : activeView === "reports" ? (
          <ReportsWorkspace key={reports ? "connected-reports" : "loading-reports"} initialReports={reports} onOpenOrder={openOrder} />
        ) : activeView === "history" ? (
          <HistoryWorkspace onOpenOrder={openOrder} />
        ) : activeView === "geography" ? (
          <GeographyWorkspace onOpenOrder={openOrder} onOpenSettings={() => setActiveView("settings")} />
        ) : activeView === "documents" ? (
          <DocumentsWorkspace
            key={`documents-${focusedDocumentId ?? "list"}-${reloadKey}`}
            data={documents}
            onNavigate={setActiveView}
            onOpenOrder={openOrder}
            onOpenMaterial={openMaterial}
            focusDocumentId={focusedDocumentId}
            linkOptions={{
              order: orders.filter((item) => item.live).map((item) => ({ id: item.id, label: item.number, detail: item.customer })),
              customer: customers.flatMap((item) => item.id ? [{ id: item.id, label: item.name, detail: item.company || item.email || "Customer" }] : []),
              product: products.map((item) => ({ id: item.id, label: item.name, detail: item.sku })),
              material: materials.map((item) => ({ id: item.id, label: item.name, detail: item.sku })),
              vendor: vendors.map((item) => ({ id: item.id, label: item.name, detail: item.contact_name || item.email || "Vendor" })),
            }}
            onChanged={(message, id) => { setBridgeMessage(message); setFocusedDocumentId(id ?? null); setReloadKey((value) => value + 1); }}
          />
        ) : activeView === "trash" ? (
          <TrashWorkspace key={`trash-${reloadKey}`} onChanged={(message) => { setBridgeMessage(message); setReloadKey((value) => value + 1); }} />
        ) : (
          <SettingsWorkspace key={settings ? "connected-settings" : "loading-settings"} initialSettings={settings} onSettingsUpdated={(updated) => { setSettings(updated); setDarkMode(updated.appearance.theme === "dark"); }} />
        )}
      </section>

      {composerOpen ? (
        <OrderComposer
          initialOrder={editingOrder}
          seedCustomer={seedCustomer}
          seedProduct={seedProduct}
          onClose={() => { setComposerOpen(false); setEditingOrder(null); setSeedCustomer(null); setSeedProduct(null); }}
          onSaved={handleOrderSaved}
        />
      ) : null}
      {quickAddOpen || editingRecord ? <QuickAddPanel editRecord={editingRecord} vendors={vendors} onClose={() => { setQuickAddOpen(false); setEditingRecord(null); }} onSaved={handleQuickAddSaved} onDeleted={handleQuickAddDeleted} /> : null}
      {goalPanelOpen ? <GoalPanel onClose={() => setGoalPanelOpen(false)} onChanged={(message) => { setBridgeMessage(message); setReloadKey((value) => value + 1); }} /> : null}
      {adjustingMaterial ? <InventoryAdjustmentPanel material={adjustingMaterial} onClose={() => setAdjustingMaterial(null)} onSaved={handleInventoryAdjusted} /> : null}
      {cancelCandidate ? <div className="composer-backdrop lifecycle-dialog-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget && lifecycleAction !== "cancel") setCancelCandidate(null); }}><section className="lifecycle-dialog" role="alertdialog" aria-modal="true" aria-labelledby="cancel-order-title"><span className="lifecycle-dialog-icon"><Ban size={22} /></span><h2 id="cancel-order-title">Cancel {cancelCandidate.number}?</h2><p>This stops the order and restores all of its product quantities. The order remains available for your records.</p><div><button className="secondary-button" onClick={() => setCancelCandidate(null)} disabled={lifecycleAction === "cancel"}>Keep order</button><button className="danger-button" onClick={() => void cancelSelectedOrder()} disabled={lifecycleAction === "cancel"}>{lifecycleAction === "cancel" ? "Cancelling…" : "Cancel order"}</button></div></section></div> : null}
      {trashCandidate ? <div className="composer-backdrop lifecycle-dialog-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget && !trashWorking) setTrashCandidate(null); }}><section className="lifecycle-dialog" role="alertdialog" aria-modal="true" aria-labelledby="move-trash-title"><span className="lifecycle-dialog-icon danger"><Trash2 size={22} /></span><h2 id="move-trash-title">Move {trashCandidate.type === "order" ? trashCandidate.record.number : trashCandidate.record.name} to trash?</h2><p>{trashCandidate.type === "order" ? "The order will disappear from active workspaces but can be restored. Inventory is not changed; cancel the order first if stock should be returned." : "The product will disappear from product choices but can be restored from Recently deleted."}</p><div><button className="secondary-button" onClick={() => setTrashCandidate(null)} disabled={trashWorking}>Keep item</button><button className="danger-button" onClick={() => void moveCandidateToTrash()} disabled={trashWorking}>{trashWorking ? "Moving…" : "Move to trash"}</button></div></section></div> : null}
    </main>
  );
}

type DraftLine = { productId: number | null; quantity: number; unitPrice: string };

function OrderComposer({
  initialOrder,
  seedCustomer,
  seedProduct,
  onClose,
  onSaved,
}: {
  initialOrder: Order | null;
  seedCustomer: CustomerOption | null;
  seedProduct: ProductOption | null;
  onClose: () => void;
  onSaved: (order: BridgeOrder) => void;
}) {
  const [step, setStep] = useState(1);
  const [customers, setCustomers] = useState<CustomerOption[]>([]);
  const [products, setProducts] = useState<ProductOption[]>([]);
  const [options, setOptions] = useState<OrderOptions | null>(null);
  const [customerId, setCustomerId] = useState<number | null>(initialOrder?.customerId ?? seedCustomer?.id ?? null);
  const [customerName, setCustomerName] = useState(initialOrder?.customer ?? seedCustomer?.name ?? "");
  const [email, setEmail] = useState(initialOrder?.email.startsWith("No ") ? "" : initialOrder?.email ?? seedCustomer?.email ?? "");
  const [phone, setPhone] = useState(initialOrder?.phone.startsWith("No ") ? "" : initialOrder?.phone ?? seedCustomer?.phone ?? "");
  const [address, setAddress] = useState(initialOrder?.location.startsWith("No ") ? "" : initialOrder?.location ?? seedCustomer?.address ?? "");
  const [orderDate, setOrderDate] = useState(initialOrder?.orderDate ?? new Date().toISOString().slice(0, 10));
  const [targetDate, setTargetDate] = useState(initialOrder?.targetDate ?? "");
  const [status, setStatus] = useState<OrderStatus>(initialOrder?.status ?? "Received");
  const [paymentStatus, setPaymentStatus] = useState(initialOrder?.paid ? "paid" : "unpaid");
  const [carrier, setCarrier] = useState(initialOrder?.carrier ?? "");
  const [trackingNumber, setTrackingNumber] = useState(initialOrder?.trackingNumber ?? "");
  const [notes, setNotes] = useState(initialOrder?.note === "No internal notes yet." ? "" : initialOrder?.note ?? "");
  const [lines, setLines] = useState<DraftLine[]>(
    initialOrder?.items.map((item) => ({
      productId: item.productId ?? null,
      quantity: item.quantity,
      unitPrice: item.price.toFixed(2),
    })) ?? [{ productId: seedProduct?.id ?? null, quantity: 1, unitPrice: seedProduct?.unit_price ?? "0.00" }],
  );
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      fetch(`${bridgeUrl}/api/customers?limit=50`, { signal: controller.signal }),
      fetch(`${bridgeUrl}/api/products?limit=100`, { signal: controller.signal }),
      fetch(`${bridgeUrl}/api/order-options`, { signal: controller.signal }),
    ]).then(async (responses) => {
      if (responses.some((response) => !response.ok)) throw new Error("Composer data unavailable");
      const [customerPayload, productPayload, optionPayload] = await Promise.all(
        responses.map((response) => response.json()),
      );
      setCustomers(customerPayload.data as CustomerOption[]);
      setProducts(productPayload.data as ProductOption[]);
      setOptions(optionPayload.data as OrderOptions);
    }).catch((error: unknown) => {
      if (error instanceof DOMException && error.name === "AbortError") return;
      setFormError("The local product and customer lists could not be loaded.");
    });
    return () => controller.abort();
  }, []);

  const subtotal = lines.reduce((sum, line) => sum + line.quantity * (Number(line.unitPrice) || 0), 0);
  const tax = subtotal * (Number(options?.tax_rate_percent ?? 0) / 100);
  const total = subtotal + (options?.tax_add_to_total ? tax : 0);
  const itemCount = lines.reduce((sum, line) => sum + Math.max(0, line.quantity), 0);
  const estimatedCost = lines.reduce((sum, line) => {
    const product = products.find((item) => item.id === line.productId);
    return sum + line.quantity * Number(product?.unit_cost ?? 0);
  }, 0);

  const chooseCustomer = (name: string) => {
    setCustomerName(name);
    const customer = customers.find((item) => item.name.toLowerCase() === name.trim().toLowerCase());
    if (!customer) {
      setCustomerId(null);
      return;
    }
    setCustomerId(customer.id);
    setEmail(customer.email);
    setPhone(customer.phone);
    setAddress(customer.address);
  };

  const updateLine = (index: number, changes: Partial<DraftLine>) => {
    setLines((current) => current.map((line, lineIndex) => lineIndex === index ? { ...line, ...changes } : line));
  };

  const chooseProduct = (index: number, productId: number) => {
    const product = products.find((item) => item.id === productId);
    updateLine(index, { productId, unitPrice: product?.unit_price ?? "0.00" });
  };

  const saveOrder = async () => {
    setFormError("");
    if (!customerName.trim() || !address.trim()) {
      setStep(1);
      setFormError("Customer name and shipping address are required.");
      return;
    }
    if (!lines.length || lines.some((line) => !line.productId || line.quantity <= 0)) {
      setStep(2);
      setFormError("Choose a product and positive quantity for every line.");
      return;
    }
    setSaving(true);
    try {
      const response = await fetch(
        initialOrder ? `${bridgeUrl}/api/orders/${initialOrder.id}` : `${bridgeUrl}/api/orders`,
        {
          method: initialOrder ? "PUT" : "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            expected_status: initialOrder?.status,
            customer: { id: customerId, name: customerName, email, phone, address },
            order_date: orderDate,
            target_completion_date: targetDate || null,
            status,
            payment_status: paymentStatus,
            carrier,
            tracking_number: trackingNumber,
            notes,
            items: lines.map((line) => ({
              product_id: line.productId,
              quantity: line.quantity,
              unit_price: line.unitPrice,
            })),
          }),
        },
      );
      const payload = (await response.json()) as { ok: boolean; data?: BridgeOrder; error?: { message: string } };
      if (!response.ok || !payload.ok || !payload.data) throw new Error(payload.error?.message || "Order could not be saved.");
      onSaved(payload.data);
    } catch (error: unknown) {
      setFormError(error instanceof Error ? error.message : "Order could not be saved.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="composer-backdrop" role="presentation">
      <section className="composer" role="dialog" aria-modal="true" aria-labelledby="composer-title">
        <header className="composer-header">
          <div>
            <span className="eyebrow-label"><Sparkles size={14} /> {initialOrder ? "Edit sales order" : "New sales order"}</span>
            <h2 id="composer-title">{initialOrder ? `Update ${initialOrder.number}` : "Build an order"}</h2>
            <p>Everything the customer, shop, and shipping team need.</p>
          </div>
          <button className="icon-button" aria-label="Close order composer" onClick={onClose}><X size={20} /></button>
        </header>

        <div className="composer-steps" aria-label="Order sections">
          {["Customer", "Items", "Payment", "Fulfillment"].map((label, index) => (
            <button className={step === index + 1 ? "active" : step > index + 1 ? "done" : ""} onClick={() => setStep(index + 1)} key={label}>
              <span>{step > index + 1 ? <Check size={13} /> : index + 1}</span>{label}
            </button>
          ))}
        </div>

        <div className="composer-body">
          <div className="composer-main">
            {step === 1 ? (
              <div className="form-section">
                <div className="form-heading"><div><span>01</span><div><h3>Who is this for?</h3><p>Choose an existing customer or add a new one.</p></div></div></div>
                <label className="field wide"><span>Customer</span><div className="input-with-icon"><Search size={17} /><input list="customer-options" value={customerName} onChange={(event) => chooseCustomer(event.target.value)} placeholder="Search or enter a customer" /></div></label>
                <datalist id="customer-options">{customers.map((customer) => <option value={customer.name} key={customer.key}>{customer.company || customer.email}</option>)}</datalist>
                <div className="form-grid">
                  <label className="field"><span>Email</span><input type="email" value={email} onChange={(event) => setEmail(event.target.value)} /></label>
                  <label className="field"><span>Phone</span><input value={phone} onChange={(event) => setPhone(event.target.value)} /></label>
                  <label className="field wide"><span>Shipping address</span><textarea value={address} onChange={(event) => setAddress(event.target.value)} /></label>
                </div>
              </div>
            ) : null}

            {step === 2 ? (
              <div className="form-section">
                <div className="form-heading"><div><span>02</span><div><h3>What are they ordering?</h3><p>Choose live products and confirm quantities and pricing.</p></div></div></div>
                {lines.map((line, index) => {
                  const product = products.find((item) => item.id === line.productId);
                  return (
                    <div className="composer-item" key={`${index}-${line.productId ?? "new"}`}>
                      <div className="product-thumb large"><Package size={20} /></div>
                      <div className="composer-product-choice">
                        <select value={line.productId ?? ""} onChange={(event) => chooseProduct(index, Number(event.target.value))}>
                          <option value="">Choose a product…</option>
                          {products.map((item) => <option value={item.id} key={item.id}>{item.sku} · {item.name}</option>)}
                        </select>
                        <span>{product ? `${product.inventory_count} available · ${product.description || "No description"}` : "Select from the product catalog"}</span>
                      </div>
                      <label><span>Qty</span><input type="number" min="1" value={line.quantity} onChange={(event) => updateLine(index, { quantity: Number(event.target.value) })} /></label>
                      <label><span>Price</span><input type="number" min="0" step="0.01" value={line.unitPrice} onChange={(event) => updateLine(index, { unitPrice: event.target.value })} /></label>
                      <strong>{currency(line.quantity * (Number(line.unitPrice) || 0))}</strong>
                      <button className="icon-button" aria-label="Remove line" disabled={lines.length === 1} onClick={() => setLines((current) => current.filter((_, lineIndex) => lineIndex !== index))}><X size={17} /></button>
                    </div>
                  );
                })}
                <button className="add-line-button" onClick={() => setLines((current) => [...current, { productId: null, quantity: 1, unitPrice: "0.00" }])}><Plus size={17} /> Add another item</button>
              </div>
            ) : null}

            {step === 3 ? (
              <div className="form-section">
                <div className="form-heading"><div><span>03</span><div><h3>Payment and totals</h3><p>Confirm pricing and how payment will be collected.</p></div></div></div>
                <div className="form-grid">
                  <label className="field"><span>Order date</span><input type="date" value={orderDate} onChange={(event) => setOrderDate(event.target.value)} /></label>
                  <label className="field"><span>Workflow status</span><select value={status} onChange={(event) => setStatus(event.target.value as OrderStatus)}>{(options?.statuses ?? stages).map((item) => <option key={item}>{item}</option>)}</select></label>
                  <label className="field"><span>Payment status</span><select value={paymentStatus} onChange={(event) => setPaymentStatus(event.target.value)}><option value="unpaid">Awaiting payment</option><option value="paid">Paid in full</option></select></label>
                  <label className="field"><span>Sales tax</span><input readOnly value={`${options?.tax_rate_percent ?? "0.00"}% · ${currency(tax)}`} /></label>
                </div>
              </div>
            ) : null}

            {step === 4 ? (
              <div className="form-section">
                <div className="form-heading"><div><span>04</span><div><h3>Fulfillment promise</h3><p>Set expectations before work begins.</p></div></div></div>
                <div className="form-grid">
                  <label className="field"><span>Target completion</span><div className="input-with-icon"><CalendarDays size={17} /><input type="date" value={targetDate} onChange={(event) => setTargetDate(event.target.value)} /></div></label>
                  <label className="field"><span>Carrier / method</span><select value={carrier} onChange={(event) => setCarrier(event.target.value)}><option value="">Choose later</option>{(options?.carriers ?? []).map((item) => <option key={item}>{item}</option>)}</select></label>
                  <label className="field wide"><span>Tracking number</span><input value={trackingNumber} onChange={(event) => setTrackingNumber(event.target.value)} /></label>
                  <label className="field wide"><span>Internal note</span><textarea value={notes} onChange={(event) => setNotes(event.target.value)} /></label>
                </div>
              </div>
            ) : null}
          </div>

          <aside className="composer-summary">
            <span>Order preview</span>
            <h3>{initialOrder?.number ?? options?.next_order_number ?? "Next order"}</h3>
            <div className="summary-customer"><div className="avatar avatar-6">{initials(customerName || "New customer")}</div><div><strong>{customerName || "Choose a customer"}</strong><span>{address || "Shipping address needed"}</span></div></div>
            <div className="summary-line"><span>{itemCount} items</span><strong>{currency(subtotal)}</strong></div>
            <div className="summary-line"><span>Carrier</span><strong>{carrier || "Choose later"}</strong></div>
            <div className="summary-line"><span>Tax</span><strong>{currency(tax)}</strong></div>
            <div className="summary-total"><span>Total</span><strong>{currency(total)}</strong></div>
            <div className="margin-callout"><BadgeDollarSign size={18} /><div><span>Estimated profit</span><strong>{currency(subtotal - estimatedCost)} · {subtotal > 0 ? `${(((subtotal - estimatedCost) / subtotal) * 100).toFixed(1)}% margin` : "Add products"}</strong></div></div>
          </aside>
        </div>

        <footer className="composer-footer">
          <div className="composer-feedback">{formError ? <span role="alert"><CircleAlert size={15} /> {formError}</span> : <span>{products.length ? `${products.length} products available` : "Loading catalog…"}</span>}</div>
          <div>
            {step > 1 ? <button className="secondary-button" onClick={() => setStep((value) => value - 1)}>Back</button> : null}
            {step < 4 ? (
              <button className="primary-button" onClick={() => setStep((value) => value + 1)}>Continue <ChevronRight size={17} /></button>
            ) : (
              <button className="primary-button" disabled={saving || !products.length} onClick={saveOrder}>{saving ? "Saving…" : initialOrder ? "Save changes" : "Create order"} <ChevronRight size={17} /></button>
            )}
          </div>
        </footer>
      </section>
    </div>
  );
}
