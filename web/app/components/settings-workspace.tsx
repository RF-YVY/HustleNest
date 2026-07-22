import {
  BadgeInfo,
  ArrowUp,
  Building2,
  Check,
  ChevronsDown,
  ChevronsUp,
  ChevronRight,
  ChevronLeft,
  CircleDollarSign,
  CreditCard,
  FileText,
  ExternalLink,
  Globe2,
  Hash,
  LockKeyhole,
  MonitorCog,
  Plus,
  ReceiptText,
  RefreshCw,
  Save,
  Search,
  Settings,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import { useEffect, useState } from "react";
import { bridgeUrl } from "../lib/hustlenest";
import type { SettingsWorkspaceData } from "../lib/hustlenest";
import { BackupSettingsCard } from "./backup-settings-card";
import { ImportSettingsCard } from "./import-settings-card";
import { AppearanceSettingsCard } from "./appearance-settings-card";
import { CloudSyncSettingsCard } from "./cloud-sync-settings-card";
import { DataHealthSettingsCard } from "./data-health-settings-card";
import { OwnerProfileSettingsCard } from "./owner-profile-settings-card";

type EditableSection = "business" | "orders" | "invoice" | "tax" | "payments" | "browser";
const settingJumps = [
  ["settings-data-health", "Data health"],
  ["settings-owner-profile", "Owner profile"],
  ["settings-backups", "Backups & recovery"],
  ["settings-import", "Import data"],
  ["settings-appearance", "Appearance & themes"],
  ["settings-dashboard", "Dashboard layout"],
  ["settings-business", "Business identity"],
  ["settings-orders", "Orders & inventory"],
  ["settings-invoice", "Invoice presentation"],
  ["settings-tax", "Tax"],
  ["settings-payments", "Payment methods"],
  ["settings-browser", "Browser launch"],
  ["settings-cloud-sync", "Cloud sync"],
  ["settings-health", "Configuration health"],
  ["settings-about", "About"],
] as const;
type PaymentDraft = { source_index: number | null; label: string; replacement: string };
type Draft = {
  business: { name: string; home_city: string; home_state: string; show_name_on_dashboard: boolean };
  orders: { number_format: string; next_sequence: number; low_inventory_threshold: number };
  invoice: { slogan: string; street: string; city: string; state: string; zip: string; phone: string; fax: string; terms: string; comments: string; contact_name: string; contact_phone: string; contact_email: string };
  tax: { rate_percent: string; show_on_invoice: boolean; add_to_total: boolean };
  payments: { methods: PaymentDraft[]; other_action: "keep" | "replace" | "remove"; other_replacement: string };
  browser: { launch_mode: "system" | "specific" | "none"; browser_id: string };
};

function draftFrom(settings: SettingsWorkspaceData | null): Draft {
  const location = settings?.business.home_location.split(",").map((value) => value.trim()) ?? [];
  return {
    business: { name: settings?.business.name ?? "", home_city: location[0] ?? "", home_state: location[1] ?? "", show_name_on_dashboard: settings?.business.show_name_on_dashboard ?? true },
    orders: { number_format: settings?.orders.number_format ?? "ORD-{seq:04d}", next_sequence: settings?.orders.next_sequence ?? 1, low_inventory_threshold: settings?.orders.low_inventory_threshold ?? 5 },
    invoice: { slogan: settings?.invoice.slogan ?? "", street: settings?.invoice.street ?? "", city: settings?.invoice.city ?? "", state: settings?.invoice.state ?? "", zip: settings?.invoice.zip ?? "", phone: settings?.invoice.phone ?? "", fax: settings?.invoice.fax ?? "", terms: settings?.invoice.terms ?? "Due on receipt", comments: settings?.invoice.comments ?? "", contact_name: settings?.invoice.contact_name ?? "", contact_phone: settings?.invoice.contact_phone ?? "", contact_email: settings?.invoice.contact_email ?? "" },
    tax: { rate_percent: settings?.tax.rate_percent ?? "0.00", show_on_invoice: settings?.tax.show_on_invoice ?? false, add_to_total: settings?.tax.add_to_total ?? false },
    payments: { methods: settings?.payments.methods.map((item) => ({ source_index: item.source_index, label: item.label, replacement: "" })) ?? [], other_action: "keep", other_replacement: "" },
    browser: { launch_mode: settings?.browser.launch_mode ?? "system", browser_id: settings?.browser.browser_id ?? "system" },
  };
}

export function SettingsWorkspace({ initialSettings, onSettingsUpdated, onNavigate, onDirtyChange }: { initialSettings: SettingsWorkspaceData | null; onSettingsUpdated?: (settings: SettingsWorkspaceData) => void; onNavigate?: (view: import("../lib/hustlenest").WorkspaceView, id?: number, settingId?: string) => void; onDirtyChange?: (dirty: boolean) => void }) {
  const settings = initialSettings;
  const [draft, setDraft] = useState(() => draftFrom(initialSettings));
  const [saving, setSaving] = useState<EditableSection | null>(null);
  const [notice, setNotice] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const [settingQuery, setSettingQuery] = useState("");
  const [activeSetting, setActiveSetting] = useState<string>(settingJumps[0][0]);
  const [panesCollapsed, setPanesCollapsed] = useState(false);
  const [about, setAbout] = useState<{ app_version: string; browser_version: string; repository_url: string; releases_url: string; runtime: string } | null>(null);
  const [updateCheck, setUpdateCheck] = useState<{ working: boolean; text: string; url: string }>({ working: false, text: "", url: "" });
  useEffect(() => { fetch(`${bridgeUrl}/api/about`).then((response) => response.json()).then((payload: { ok: boolean; data?: typeof about }) => { if (payload.ok && payload.data) setAbout(payload.data); }).catch(() => undefined); }, []);

  const savedDraft = draftFrom(settings);
  const dirtySections = new Set<EditableSection>((["business", "orders", "invoice", "tax", "payments", "browser"] as EditableSection[]).filter((section) => JSON.stringify(draft[section]) !== JSON.stringify(savedDraft[section])));
  const hasUnsavedChanges = dirtySections.size > 0;
  const visibleJumps = settingJumps.filter(([, label]) => label.toLocaleLowerCase().includes(settingQuery.trim().toLocaleLowerCase()));
  const activeJumpIndex = settingJumps.findIndex(([id]) => id === activeSetting);
  const jumpTo = (id: string) => { window.location.hash = id; document.getElementById(id)?.scrollIntoView({ behavior: settings?.appearance.reduce_motion ? "auto" : "smooth", block: "start" }); };

  useEffect(() => {
    const normalizedQuery = settingQuery.trim().toLocaleLowerCase();
    const visibleIds = new Set(settingJumps.filter(([, label]) => label.toLocaleLowerCase().includes(normalizedQuery)).map(([id]) => id));
    settingJumps.forEach(([id]) => {
      if (id === "settings-dashboard") return;
      const visible = id === "settings-appearance" ? visibleIds.has(id) || visibleIds.has("settings-dashboard") : visibleIds.has(id);
      document.getElementById(id)?.classList.toggle("settings-filtered-out", !visible);
    });
  }, [settingQuery]);

  useEffect(() => {
    const observer = new IntersectionObserver((entries) => {
      const visible = entries.filter((entry) => entry.isIntersecting).sort((left, right) => Math.abs(left.boundingClientRect.top - 145) - Math.abs(right.boundingClientRect.top - 145));
      if (visible[0]) setActiveSetting(visible[0].target.id);
    }, { rootMargin: "-135px 0px -55% 0px", threshold: [0, 0.05] });
    settingJumps.forEach(([id]) => { const pane = document.getElementById(id); if (pane) observer.observe(pane); });
    return () => observer.disconnect();
  }, [settings]);

  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => { if (hasUnsavedChanges) event.preventDefault(); };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [hasUnsavedChanges]);
  useEffect(() => { onDirtyChange?.(hasUnsavedChanges); return () => onDirtyChange?.(false); }, [hasUnsavedChanges, onDirtyChange]);

  useEffect(() => { window.localStorage.setItem("hustlenest.settings.panes-collapsed", panesCollapsed ? "1" : "0"); }, [panesCollapsed]);

  const validateSection = (section: EditableSection): string | null => {
    if (section === "business") {
      if (!draft.business.name.trim()) return "Enter a business name before saving.";
      if (draft.business.home_state && draft.business.home_state.trim().length !== 2) return "Use a two-letter state abbreviation.";
    }
    if (section === "orders") {
      if (!/\{seq(?::[^}]+)?\}/.test(draft.orders.number_format)) return "Order number format must include {seq} or a formatted variant such as {seq:04d}.";
      if (draft.orders.next_sequence < 1 || draft.orders.low_inventory_threshold < 0) return "Order sequence must be at least 1 and the inventory threshold cannot be negative.";
    }
    if (section === "invoice") {
      if (draft.invoice.state && draft.invoice.state.trim().length !== 2) return "Use a two-letter invoice state abbreviation.";
      if (draft.invoice.contact_email && !/^\S+@\S+\.\S+$/.test(draft.invoice.contact_email)) return "Enter a valid invoice contact email.";
    }
    if (section === "tax" && (Number(draft.tax.rate_percent) < 0 || Number(draft.tax.rate_percent) > 100)) return "Sales tax must be between 0% and 100%.";
    if (section === "payments" && draft.payments.methods.some((method) => !method.label.trim() || (method.source_index === null && !method.replacement.trim()))) return "Every payment method needs a label and new methods need a destination.";
    if (section === "browser" && draft.browser.launch_mode === "specific" && draft.browser.browser_id === "system") return "Choose an installed work browser.";
    return null;
  };

  const saveSection = async (section: EditableSection) => {
    if (!settings) return;
    const validationError = validateSection(section);
    if (validationError) { setNotice({ tone: "error", text: validationError }); return; }
    setSaving(section);
    setNotice(null);
    try {
      const response = await fetch(`${bridgeUrl}/api/settings`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ section, values: draft[section], expected_revision: settings.summary.revision }) });
      const payload = await response.json() as { ok: boolean; data?: SettingsWorkspaceData; error?: { message: string } };
      if (!response.ok || !payload.ok || !payload.data) throw new Error(payload.error?.message || "Settings could not be saved.");
      onSettingsUpdated?.(payload.data);
      setDraft(draftFrom(payload.data));
      setNotice({ tone: "success", text: `${section[0].toUpperCase()}${section.slice(1)} settings saved.` });
    } catch (error) {
      setNotice({ tone: "error", text: error instanceof Error ? error.message : "Settings could not be saved." });
    } finally { setSaving(null); }
  };
  const saveButton = (section: EditableSection) => <button className={`secondary-button setting-save${dirtySections.has(section) ? " has-changes" : ""}`} onClick={() => void saveSection(section)} disabled={!settings || saving !== null || !dirtySections.has(section)}><Save size={14} />{saving === section ? "Saving…" : dirtySections.has(section) ? "Save changes" : "Saved"}</button>;
  const refreshSettings = async () => {
    const response = await fetch(`${bridgeUrl}/api/settings`);
    const payload = await response.json() as { ok: boolean; data?: SettingsWorkspaceData };
    if (response.ok && payload.ok && payload.data) onSettingsUpdated?.(payload.data);
  };
  const checkUpdates = async () => {
    setUpdateCheck({ working: true, text: "Checking for updates…", url: "" });
    try {
      const response = await fetch(`${bridgeUrl}/api/updates/check`);
      const payload = await response.json() as { ok: boolean; data?: { is_newer: boolean; latest_version: string | null; download_url: string; error: string | null } };
      if (!response.ok || !payload.ok || !payload.data) throw new Error("Update check failed.");
      setUpdateCheck({ working: false, text: payload.data.error || (payload.data.is_newer ? `${payload.data.latest_version} is available.` : `You’re up to date${payload.data.latest_version ? ` (${payload.data.latest_version})` : ""}.`), url: payload.data.is_newer ? payload.data.download_url : "" });
    } catch (error) { setUpdateCheck({ working: false, text: error instanceof Error ? error.message : "Update check failed.", url: "" }); }
  };

  useEffect(() => {
    const saveShortcut = (event: KeyboardEvent) => {
      if (!(event.ctrlKey || event.metaKey) || event.key.toLocaleLowerCase() !== "s") return;
      const activeSection = activeSetting.replace("settings-", "") as EditableSection;
      if (dirtySections.has(activeSection)) { event.preventDefault(); void saveSection(activeSection); }
    };
    window.addEventListener("keydown", saveShortcut);
    return () => window.removeEventListener("keydown", saveShortcut);
  });

  return (
    <div className={`workspace settings-page${panesCollapsed ? " compact-panes" : ""}`}>
      <div className="page-heading"><div><div className="eyebrow"><span>Workspace</span><ChevronRight size={14} /><span>Settings</span></div><h1>Settings</h1><p>Control the business rules that shape every workflow.</p></div></div>
      <nav className="settings-quick-jump" aria-label="Jump to a settings pane">
        <strong>Quick jump</strong>
        <label><Search size={14} /><input type="search" value={settingQuery} onChange={(event) => setSettingQuery(event.target.value)} placeholder="Search settings" aria-label="Search settings" /></label>
        <div>{visibleJumps.map(([id, label]) => <a href={`#${id}`} className={activeSetting === id ? "active" : undefined} aria-current={activeSetting === id ? "location" : undefined} key={id}>{label}</a>)}</div>
        <button type="button" className="settings-collapse-all" onClick={() => setPanesCollapsed((value) => !value)}>{panesCollapsed ? <ChevronsDown size={14} /> : <ChevronsUp size={14} />}{panesCollapsed ? "Expand" : "Collapse"}</button>
      </nav>
      {settingQuery && !visibleJumps.length ? <div className="settings-search-empty">No settings panes match “{settingQuery}”.</div> : null}
      <div className="settings-notice"><MonitorCog size={18} /><div><strong>Browser editing is enabled</strong><span>Business, invoice, order, tax, payment, and launch preferences save directly to the local database. Credentials and file-based settings remain protected.</span></div><em>Local only</em></div>
      {notice ? <div className={`settings-feedback ${notice.tone}`} role="status">{notice.tone === "success" ? <Check size={15} /> : <LockKeyhole size={15} />}{notice.text}</div> : null}
      <section className="material-metrics settings-metrics" aria-label="Settings summary">
        <article><Building2 size={19} /><div><span>Business</span><strong>{settings?.business.name || "Not configured"}</strong></div></article>
        <article><Hash size={19} /><div><span>Next order</span><strong>{settings?.orders.next_number || "—"}</strong></div></article>
        <article><CircleDollarSign size={19} /><div><span>Sales tax</span><strong>{settings?.tax.rate_percent ?? "0.00"}%</strong></div></article>
        <article><Globe2 size={19} /><div><span>Browser launch</span><strong>{settings?.browser.launch_mode === "none" ? "Manual" : settings?.browser.launch_mode === "specific" ? settings.browser.available.find((item) => item.id === settings.browser.browser_id)?.label || "Selected" : "System default"}</strong></div></article>
      </section>
      <section className="settings-grid">
        <DataHealthSettingsCard onNavigate={(view, id, settingId) => onNavigate?.(view, id, settingId)} />
        {settings ? <OwnerProfileSettingsCard settings={settings} onUpdated={(updated) => onSettingsUpdated?.(updated)} /> : null}
        <BackupSettingsCard />
        <ImportSettingsCard />
        {settings ? <AppearanceSettingsCard settings={settings} onUpdated={(updated) => onSettingsUpdated?.(updated)} /> : null}
        <article className="settings-card" id="settings-business">
          <div className="settings-card-heading"><span className="setting-icon"><Building2 size={19} /></span><div><h2>Business identity</h2><p>Brand and home location</p></div>{saveButton("business")}</div>
          <div className="settings-form"><label><span>Business name</span><input value={draft.business.name} onChange={(event) => setDraft((value) => ({ ...value, business: { ...value.business, name: event.target.value } }))} /></label><div className="settings-form-pair"><label><span>Home city</span><input value={draft.business.home_city} onChange={(event) => setDraft((value) => ({ ...value, business: { ...value.business, home_city: event.target.value } }))} /></label><label><span>State</span><input maxLength={2} value={draft.business.home_state} onChange={(event) => setDraft((value) => ({ ...value, business: { ...value.business, home_state: event.target.value.toUpperCase() } }))} /></label></div><label className="setting-check"><input type="checkbox" checked={draft.business.show_name_on_dashboard} onChange={(event) => setDraft((value) => ({ ...value, business: { ...value.business, show_name_on_dashboard: event.target.checked } }))} /><span>Show business name on dashboard</span></label></div>
        </article>

        <article className="settings-card" id="settings-orders">
          <div className="settings-card-heading"><span className="setting-icon violet"><ReceiptText size={19} /></span><div><h2>Orders and inventory</h2><p>Numbering and stock rules</p></div>{saveButton("orders")}</div>
          <div className="settings-form"><label><span>Order number format</span><input value={draft.orders.number_format} onChange={(event) => setDraft((value) => ({ ...value, orders: { ...value.orders, number_format: event.target.value } }))} /><small>Include <code>{"{seq}"}</code> or a formatted variant such as <code>{"{seq:04d}"}</code>.</small></label><div className="settings-form-pair"><label><span>Next sequence</span><input type="number" min={1} value={draft.orders.next_sequence} onChange={(event) => setDraft((value) => ({ ...value, orders: { ...value.orders, next_sequence: Number(event.target.value) } }))} /></label><label><span>Low inventory threshold</span><input type="number" min={0} value={draft.orders.low_inventory_threshold} onChange={(event) => setDraft((value) => ({ ...value, orders: { ...value.orders, low_inventory_threshold: Number(event.target.value) } }))} /></label></div><div className="setting-preview"><Hash size={14} /><span>Next order preview</span><strong>{settings?.orders.next_number || "—"}</strong></div></div>
        </article>

        <article className="settings-card invoice-settings-card" id="settings-invoice">
          <div className="settings-card-heading"><span className="setting-icon amber"><FileText size={19} /></span><div><h2>Invoice presentation</h2><p>Customer-facing document details</p></div>{saveButton("invoice")}</div>
          <div className="settings-form invoice-form"><label><span>Slogan</span><input value={draft.invoice.slogan} onChange={(event) => setDraft((value) => ({ ...value, invoice: { ...value.invoice, slogan: event.target.value } }))} /></label><label><span>Street</span><input value={draft.invoice.street} onChange={(event) => setDraft((value) => ({ ...value, invoice: { ...value.invoice, street: event.target.value } }))} /></label><label><span>City</span><input value={draft.invoice.city} onChange={(event) => setDraft((value) => ({ ...value, invoice: { ...value.invoice, city: event.target.value } }))} /></label><label><span>State</span><input maxLength={2} value={draft.invoice.state} onChange={(event) => setDraft((value) => ({ ...value, invoice: { ...value.invoice, state: event.target.value.toUpperCase() } }))} /></label><label><span>ZIP</span><input value={draft.invoice.zip} onChange={(event) => setDraft((value) => ({ ...value, invoice: { ...value.invoice, zip: event.target.value } }))} /></label><label><span>Phone</span><input value={draft.invoice.phone} onChange={(event) => setDraft((value) => ({ ...value, invoice: { ...value.invoice, phone: event.target.value } }))} /></label><label><span>Contact name</span><input value={draft.invoice.contact_name} onChange={(event) => setDraft((value) => ({ ...value, invoice: { ...value.invoice, contact_name: event.target.value } }))} /></label><label><span>Contact email</span><input type="email" value={draft.invoice.contact_email} onChange={(event) => setDraft((value) => ({ ...value, invoice: { ...value.invoice, contact_email: event.target.value } }))} /></label><label><span>Payment terms</span><input value={draft.invoice.terms} onChange={(event) => setDraft((value) => ({ ...value, invoice: { ...value.invoice, terms: event.target.value } }))} /></label><label className="wide"><span>Default comments</span><textarea value={draft.invoice.comments} onChange={(event) => setDraft((value) => ({ ...value, invoice: { ...value.invoice, comments: event.target.value } }))} /></label></div>
        </article>

        <article className="settings-card" id="settings-tax">
          <div className="settings-card-heading"><span className="setting-icon rose"><CircleDollarSign size={19} /></span><div><h2>Tax</h2><p>Checkout and invoice behavior</p></div>{saveButton("tax")}</div>
          <div className="settings-form"><label><span>Sales tax rate (%)</span><input type="number" min={0} max={100} step="0.01" value={draft.tax.rate_percent} onChange={(event) => setDraft((value) => ({ ...value, tax: { ...value.tax, rate_percent: event.target.value } }))} /></label><label className="setting-check"><input type="checkbox" checked={draft.tax.show_on_invoice} onChange={(event) => setDraft((value) => ({ ...value, tax: { ...value.tax, show_on_invoice: event.target.checked } }))} /><span>Show tax on invoices</span></label><label className="setting-check"><input type="checkbox" checked={draft.tax.add_to_total} onChange={(event) => setDraft((value) => ({ ...value, tax: { ...value.tax, add_to_total: event.target.checked } }))} /><span>Add tax to order totals</span></label></div>
        </article>

        <article className="settings-card payment-settings-card" id="settings-payments">
          <div className="settings-card-heading"><span className="setting-icon amber"><CreditCard size={19} /></span><div><h2>Invoice payment methods</h2><p>Destinations shown to customers</p></div>{saveButton("payments")}</div>
          <div className="payment-security-note"><ShieldCheck size={16} /><span><strong>Saved destinations stay masked.</strong> Leave replacement blank to keep the current value.</span></div>
          <div className="payment-method-editor">
            {draft.payments.methods.map((method, index) => <div className="payment-method-row" key={`${method.source_index ?? "new"}-${index}`}><label><span>Method label</span><input value={method.label} placeholder="ACH, PayPal, check…" onChange={(event) => setDraft((value) => ({ ...value, payments: { ...value.payments, methods: value.payments.methods.map((item, row) => row === index ? { ...item, label: event.target.value } : item) } }))} /></label><label><span>{method.source_index === null ? "Payment destination" : "Replace saved destination"}</span><input type="password" value={method.replacement} placeholder={method.source_index === null ? "Account, email, or payment link" : "Leave blank to keep saved value"} onChange={(event) => setDraft((value) => ({ ...value, payments: { ...value.payments, methods: value.payments.methods.map((item, row) => row === index ? { ...item, replacement: event.target.value } : item) } }))} /></label><button className="icon-button payment-remove" aria-label={`Remove ${method.label || "payment method"}`} onClick={() => setDraft((value) => ({ ...value, payments: { ...value.payments, methods: value.payments.methods.filter((_item, row) => row !== index) } }))}><Trash2 size={16} /></button></div>)}
            {!draft.payments.methods.length ? <p className="payment-empty">No payment methods configured. Invoices will use the business name for check payments.</p> : null}
            <button className="secondary-button payment-add" onClick={() => setDraft((value) => ({ ...value, payments: { ...value.payments, methods: [...value.payments.methods, { source_index: null, label: "", replacement: "" }] } }))} disabled={draft.payments.methods.length >= 12}><Plus size={15} /> Add payment method</button>
          </div>
          <div className="payment-notes-editor"><div><strong>Additional payment notes</strong><span>{settings?.payments.other_configured ? "Saved notes are configured but remain masked." : "No additional notes are configured."}</span></div><div className="payment-note-actions"><label><input type="radio" name="payment-notes" checked={draft.payments.other_action === "keep"} onChange={() => setDraft((value) => ({ ...value, payments: { ...value.payments, other_action: "keep", other_replacement: "" } }))} /> Keep saved notes</label><label><input type="radio" name="payment-notes" checked={draft.payments.other_action === "replace"} onChange={() => setDraft((value) => ({ ...value, payments: { ...value.payments, other_action: "replace" } }))} /> Replace notes</label><label><input type="radio" name="payment-notes" checked={draft.payments.other_action === "remove"} onChange={() => setDraft((value) => ({ ...value, payments: { ...value.payments, other_action: "remove", other_replacement: "" } }))} /> Remove notes</label></div>{draft.payments.other_action === "replace" ? <textarea value={draft.payments.other_replacement} placeholder="Payment instructions shown on invoices" onChange={(event) => setDraft((value) => ({ ...value, payments: { ...value.payments, other_replacement: event.target.value } }))} /> : null}</div>
        </article>

        <article className="settings-card browser-settings-card" id="settings-browser">
          <div className="settings-card-heading"><span className="setting-icon violet"><Globe2 size={19} /></span><div><h2>Browser launch</h2><p>Separate work and personal browsing</p></div>{saveButton("browser")}</div>
          <div className="browser-mode-options"><label><input type="radio" name="browser-mode" checked={draft.browser.launch_mode === "system"} onChange={() => setDraft((value) => ({ ...value, browser: { ...value.browser, launch_mode: "system", browser_id: "system" } }))} /><span><strong>System default</strong><small>Use the current Windows default browser.</small></span></label><label><input type="radio" name="browser-mode" checked={draft.browser.launch_mode === "specific"} onChange={() => setDraft((value) => ({ ...value, browser: { ...value.browser, launch_mode: "specific", browser_id: value.browser.browser_id === "system" ? settings?.browser.available.find((item) => item.id !== "system")?.id || "system" : value.browser.browser_id } }))} /><span><strong>Selected work browser</strong><small>Always open HustleNest in the browser chosen below.</small></span></label><label><input type="radio" name="browser-mode" checked={draft.browser.launch_mode === "none"} onChange={() => setDraft((value) => ({ ...value, browser: { ...value.browser, launch_mode: "none", browser_id: "system" } }))} /><span><strong>Don’t open automatically</strong><small>Start the backend and open the address yourself.</small></span></label></div><label className="browser-select"><span>Work browser</span><select disabled={draft.browser.launch_mode !== "specific"} value={draft.browser.browser_id} onChange={(event) => setDraft((value) => ({ ...value, browser: { ...value.browser, browser_id: event.target.value } }))}><option value="system" disabled>Select an installed browser</option>{settings?.browser.available.filter((item) => item.id !== "system").map((item) => <option value={item.id} key={item.id}>{item.label}</option>)}</select></label>
        </article>

        <CloudSyncSettingsCard onChanged={() => void refreshSettings()} />

        <article className="settings-card settings-summary-card" id="settings-health">
          <div className="settings-card-heading"><span className="setting-icon violet"><Settings size={19} /></span><div><h2>Configuration health</h2><p>High-level readiness</p></div></div><div className="settings-readiness"><div><strong>{settings?.summary.configured_sections ?? 0}/5</strong><span>sections configured</span></div><i><b style={{ width: `${(settings?.summary.configured_sections ?? 0) / 5 * 100}%` }} /></i></div><div className="settings-privacy neutral"><LockKeyhole size={17} /><span><strong>Revision protected</strong><small>Each save checks for changes made in another window before writing.</small></span></div>
        </article>
        <article className="settings-card settings-summary-card" id="settings-about">
          <div className="settings-card-heading"><span className="setting-icon"><BadgeInfo size={19} /></span><div><h2>About HustleNest</h2><p>{about?.runtime || "Local browser workspace"}</p></div><button className="secondary-button setting-save" onClick={() => void checkUpdates()} disabled={updateCheck.working}><RefreshCw size={14} />{updateCheck.working ? "Checking…" : "Check updates"}</button></div><div className="settings-readiness"><div><strong>{about?.app_version || "v4.2"}</strong><span>application · browser {about?.browser_version || "4.2.0"}</span></div></div>{updateCheck.text ? <div className="update-check-result"><span>{updateCheck.text}</span>{updateCheck.url ? <a href={updateCheck.url} target="_blank" rel="noreferrer">View release <ExternalLink size={13} /></a> : null}</div> : null}<div className="settings-about-links"><a className="secondary-button" href={about?.repository_url || "https://github.com/RF-YVY/HustleNest"} target="_blank" rel="noreferrer">Source <ExternalLink size={13} /></a><a className="secondary-button" href={about?.releases_url || "https://github.com/RF-YVY/HustleNest/releases"} target="_blank" rel="noreferrer">Updates and releases <ExternalLink size={13} /></a></div>
        </article>
      </section>
      <nav className="settings-pager" aria-label="Settings pane navigation"><button disabled={activeJumpIndex <= 0} onClick={() => activeJumpIndex > 0 && jumpTo(settingJumps[activeJumpIndex - 1][0])}><ChevronLeft size={14} /> Previous pane</button><button onClick={() => window.scrollTo({ top: 0, behavior: settings?.appearance.reduce_motion ? "auto" : "smooth" })}><ArrowUp size={14} /> Back to top</button><button disabled={activeJumpIndex < 0 || activeJumpIndex >= settingJumps.length - 1} onClick={() => activeJumpIndex >= 0 && activeJumpIndex < settingJumps.length - 1 && jumpTo(settingJumps[activeJumpIndex + 1][0])}>Next pane <ChevronRight size={14} /></button></nav>
    </div>
  );
}
