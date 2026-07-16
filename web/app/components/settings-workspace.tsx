import {
  BadgeInfo,
  Building2,
  Check,
  ChevronRight,
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
  Save,
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
import { OwnerProfileSettingsCard } from "./owner-profile-settings-card";

type EditableSection = "business" | "orders" | "invoice" | "tax" | "payments" | "browser";
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

export function SettingsWorkspace({ initialSettings, onSettingsUpdated }: { initialSettings: SettingsWorkspaceData | null; onSettingsUpdated?: (settings: SettingsWorkspaceData) => void }) {
  const settings = initialSettings;
  const [draft, setDraft] = useState(() => draftFrom(initialSettings));
  const [saving, setSaving] = useState<EditableSection | null>(null);
  const [notice, setNotice] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const [about, setAbout] = useState<{ app_version: string; browser_version: string; repository_url: string; releases_url: string; runtime: string } | null>(null);
  useEffect(() => { fetch(`${bridgeUrl}/api/about`).then((response) => response.json()).then((payload: { ok: boolean; data?: typeof about }) => { if (payload.ok && payload.data) setAbout(payload.data); }).catch(() => undefined); }, []);

  const saveSection = async (section: EditableSection) => {
    if (!settings) return;
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
  const saveButton = (section: EditableSection) => <button className="secondary-button setting-save" onClick={() => void saveSection(section)} disabled={!settings || saving !== null}><Save size={14} />{saving === section ? "Saving…" : "Save"}</button>;
  const refreshSettings = async () => {
    const response = await fetch(`${bridgeUrl}/api/settings`);
    const payload = await response.json() as { ok: boolean; data?: SettingsWorkspaceData };
    if (response.ok && payload.ok && payload.data) onSettingsUpdated?.(payload.data);
  };

  return (
    <div className="workspace settings-page">
      <div className="page-heading"><div><div className="eyebrow"><span>Workspace</span><ChevronRight size={14} /><span>Settings</span></div><h1>Settings</h1><p>Control the business rules that shape every workflow.</p></div></div>
      <div className="settings-notice"><MonitorCog size={18} /><div><strong>Browser editing is enabled</strong><span>Business, invoice, order, tax, payment, and launch preferences save directly to the local database. Credentials and file-based settings remain protected.</span></div><em>Local only</em></div>
      {notice ? <div className={`settings-feedback ${notice.tone}`} role="status">{notice.tone === "success" ? <Check size={15} /> : <LockKeyhole size={15} />}{notice.text}</div> : null}
      <section className="material-metrics settings-metrics" aria-label="Settings summary">
        <article><Building2 size={19} /><div><span>Business</span><strong>{settings?.business.name || "Not configured"}</strong></div></article>
        <article><Hash size={19} /><div><span>Next order</span><strong>{settings?.orders.next_number || "—"}</strong></div></article>
        <article><CircleDollarSign size={19} /><div><span>Sales tax</span><strong>{settings?.tax.rate_percent ?? "0.00"}%</strong></div></article>
        <article><Globe2 size={19} /><div><span>Browser launch</span><strong>{settings?.browser.launch_mode === "none" ? "Manual" : settings?.browser.launch_mode === "specific" ? settings.browser.available.find((item) => item.id === settings.browser.browser_id)?.label || "Selected" : "System default"}</strong></div></article>
      </section>
      <section className="settings-grid">
        {settings ? <OwnerProfileSettingsCard settings={settings} onUpdated={(updated) => onSettingsUpdated?.(updated)} /> : null}
        <BackupSettingsCard />
        <ImportSettingsCard />
        {settings ? <AppearanceSettingsCard settings={settings} onUpdated={(updated) => onSettingsUpdated?.(updated)} /> : null}
        <article className="settings-card">
          <div className="settings-card-heading"><span className="setting-icon"><Building2 size={19} /></span><div><h2>Business identity</h2><p>Brand and home location</p></div>{saveButton("business")}</div>
          <div className="settings-form"><label><span>Business name</span><input value={draft.business.name} onChange={(event) => setDraft((value) => ({ ...value, business: { ...value.business, name: event.target.value } }))} /></label><div className="settings-form-pair"><label><span>Home city</span><input value={draft.business.home_city} onChange={(event) => setDraft((value) => ({ ...value, business: { ...value.business, home_city: event.target.value } }))} /></label><label><span>State</span><input maxLength={2} value={draft.business.home_state} onChange={(event) => setDraft((value) => ({ ...value, business: { ...value.business, home_state: event.target.value.toUpperCase() } }))} /></label></div><label className="setting-check"><input type="checkbox" checked={draft.business.show_name_on_dashboard} onChange={(event) => setDraft((value) => ({ ...value, business: { ...value.business, show_name_on_dashboard: event.target.checked } }))} /><span>Show business name on dashboard</span></label></div>
        </article>

        <article className="settings-card">
          <div className="settings-card-heading"><span className="setting-icon violet"><ReceiptText size={19} /></span><div><h2>Orders and inventory</h2><p>Numbering and stock rules</p></div>{saveButton("orders")}</div>
          <div className="settings-form"><label><span>Order number format</span><input value={draft.orders.number_format} onChange={(event) => setDraft((value) => ({ ...value, orders: { ...value.orders, number_format: event.target.value } }))} /><small>Include <code>{"{seq}"}</code> or a formatted variant such as <code>{"{seq:04d}"}</code>.</small></label><div className="settings-form-pair"><label><span>Next sequence</span><input type="number" min={1} value={draft.orders.next_sequence} onChange={(event) => setDraft((value) => ({ ...value, orders: { ...value.orders, next_sequence: Number(event.target.value) } }))} /></label><label><span>Low inventory threshold</span><input type="number" min={0} value={draft.orders.low_inventory_threshold} onChange={(event) => setDraft((value) => ({ ...value, orders: { ...value.orders, low_inventory_threshold: Number(event.target.value) } }))} /></label></div><div className="setting-preview"><Hash size={14} /><span>Next order preview</span><strong>{settings?.orders.next_number || "—"}</strong></div></div>
        </article>

        <article className="settings-card invoice-settings-card">
          <div className="settings-card-heading"><span className="setting-icon amber"><FileText size={19} /></span><div><h2>Invoice presentation</h2><p>Customer-facing document details</p></div>{saveButton("invoice")}</div>
          <div className="settings-form invoice-form"><label><span>Slogan</span><input value={draft.invoice.slogan} onChange={(event) => setDraft((value) => ({ ...value, invoice: { ...value.invoice, slogan: event.target.value } }))} /></label><label><span>Street</span><input value={draft.invoice.street} onChange={(event) => setDraft((value) => ({ ...value, invoice: { ...value.invoice, street: event.target.value } }))} /></label><label><span>City</span><input value={draft.invoice.city} onChange={(event) => setDraft((value) => ({ ...value, invoice: { ...value.invoice, city: event.target.value } }))} /></label><label><span>State</span><input maxLength={2} value={draft.invoice.state} onChange={(event) => setDraft((value) => ({ ...value, invoice: { ...value.invoice, state: event.target.value.toUpperCase() } }))} /></label><label><span>ZIP</span><input value={draft.invoice.zip} onChange={(event) => setDraft((value) => ({ ...value, invoice: { ...value.invoice, zip: event.target.value } }))} /></label><label><span>Phone</span><input value={draft.invoice.phone} onChange={(event) => setDraft((value) => ({ ...value, invoice: { ...value.invoice, phone: event.target.value } }))} /></label><label><span>Contact name</span><input value={draft.invoice.contact_name} onChange={(event) => setDraft((value) => ({ ...value, invoice: { ...value.invoice, contact_name: event.target.value } }))} /></label><label><span>Contact email</span><input type="email" value={draft.invoice.contact_email} onChange={(event) => setDraft((value) => ({ ...value, invoice: { ...value.invoice, contact_email: event.target.value } }))} /></label><label><span>Payment terms</span><input value={draft.invoice.terms} onChange={(event) => setDraft((value) => ({ ...value, invoice: { ...value.invoice, terms: event.target.value } }))} /></label><label className="wide"><span>Default comments</span><textarea value={draft.invoice.comments} onChange={(event) => setDraft((value) => ({ ...value, invoice: { ...value.invoice, comments: event.target.value } }))} /></label></div>
        </article>

        <article className="settings-card">
          <div className="settings-card-heading"><span className="setting-icon rose"><CircleDollarSign size={19} /></span><div><h2>Tax</h2><p>Checkout and invoice behavior</p></div>{saveButton("tax")}</div>
          <div className="settings-form"><label><span>Sales tax rate (%)</span><input type="number" min={0} max={100} step="0.01" value={draft.tax.rate_percent} onChange={(event) => setDraft((value) => ({ ...value, tax: { ...value.tax, rate_percent: event.target.value } }))} /></label><label className="setting-check"><input type="checkbox" checked={draft.tax.show_on_invoice} onChange={(event) => setDraft((value) => ({ ...value, tax: { ...value.tax, show_on_invoice: event.target.checked } }))} /><span>Show tax on invoices</span></label><label className="setting-check"><input type="checkbox" checked={draft.tax.add_to_total} onChange={(event) => setDraft((value) => ({ ...value, tax: { ...value.tax, add_to_total: event.target.checked } }))} /><span>Add tax to order totals</span></label></div>
        </article>

        <article className="settings-card payment-settings-card">
          <div className="settings-card-heading"><span className="setting-icon amber"><CreditCard size={19} /></span><div><h2>Invoice payment methods</h2><p>Destinations shown to customers</p></div>{saveButton("payments")}</div>
          <div className="payment-security-note"><ShieldCheck size={16} /><span><strong>Saved destinations stay masked.</strong> Leave replacement blank to keep the current value.</span></div>
          <div className="payment-method-editor">
            {draft.payments.methods.map((method, index) => <div className="payment-method-row" key={`${method.source_index ?? "new"}-${index}`}><label><span>Method label</span><input value={method.label} placeholder="ACH, PayPal, check…" onChange={(event) => setDraft((value) => ({ ...value, payments: { ...value.payments, methods: value.payments.methods.map((item, row) => row === index ? { ...item, label: event.target.value } : item) } }))} /></label><label><span>{method.source_index === null ? "Payment destination" : "Replace saved destination"}</span><input type="password" value={method.replacement} placeholder={method.source_index === null ? "Account, email, or payment link" : "Leave blank to keep saved value"} onChange={(event) => setDraft((value) => ({ ...value, payments: { ...value.payments, methods: value.payments.methods.map((item, row) => row === index ? { ...item, replacement: event.target.value } : item) } }))} /></label><button className="icon-button payment-remove" aria-label={`Remove ${method.label || "payment method"}`} onClick={() => setDraft((value) => ({ ...value, payments: { ...value.payments, methods: value.payments.methods.filter((_item, row) => row !== index) } }))}><Trash2 size={16} /></button></div>)}
            {!draft.payments.methods.length ? <p className="payment-empty">No payment methods configured. Invoices will use the business name for check payments.</p> : null}
            <button className="secondary-button payment-add" onClick={() => setDraft((value) => ({ ...value, payments: { ...value.payments, methods: [...value.payments.methods, { source_index: null, label: "", replacement: "" }] } }))} disabled={draft.payments.methods.length >= 12}><Plus size={15} /> Add payment method</button>
          </div>
          <div className="payment-notes-editor"><div><strong>Additional payment notes</strong><span>{settings?.payments.other_configured ? "Saved notes are configured but remain masked." : "No additional notes are configured."}</span></div><div className="payment-note-actions"><label><input type="radio" name="payment-notes" checked={draft.payments.other_action === "keep"} onChange={() => setDraft((value) => ({ ...value, payments: { ...value.payments, other_action: "keep", other_replacement: "" } }))} /> Keep saved notes</label><label><input type="radio" name="payment-notes" checked={draft.payments.other_action === "replace"} onChange={() => setDraft((value) => ({ ...value, payments: { ...value.payments, other_action: "replace" } }))} /> Replace notes</label><label><input type="radio" name="payment-notes" checked={draft.payments.other_action === "remove"} onChange={() => setDraft((value) => ({ ...value, payments: { ...value.payments, other_action: "remove", other_replacement: "" } }))} /> Remove notes</label></div>{draft.payments.other_action === "replace" ? <textarea value={draft.payments.other_replacement} placeholder="Payment instructions shown on invoices" onChange={(event) => setDraft((value) => ({ ...value, payments: { ...value.payments, other_replacement: event.target.value } }))} /> : null}</div>
        </article>

        <article className="settings-card browser-settings-card">
          <div className="settings-card-heading"><span className="setting-icon violet"><Globe2 size={19} /></span><div><h2>Browser launch</h2><p>Separate work and personal browsing</p></div>{saveButton("browser")}</div>
          <div className="browser-mode-options"><label><input type="radio" name="browser-mode" checked={draft.browser.launch_mode === "system"} onChange={() => setDraft((value) => ({ ...value, browser: { ...value.browser, launch_mode: "system", browser_id: "system" } }))} /><span><strong>System default</strong><small>Use the current Windows default browser.</small></span></label><label><input type="radio" name="browser-mode" checked={draft.browser.launch_mode === "specific"} onChange={() => setDraft((value) => ({ ...value, browser: { ...value.browser, launch_mode: "specific", browser_id: value.browser.browser_id === "system" ? settings?.browser.available.find((item) => item.id !== "system")?.id || "system" : value.browser.browser_id } }))} /><span><strong>Selected work browser</strong><small>Always open HustleNest in the browser chosen below.</small></span></label><label><input type="radio" name="browser-mode" checked={draft.browser.launch_mode === "none"} onChange={() => setDraft((value) => ({ ...value, browser: { ...value.browser, launch_mode: "none", browser_id: "system" } }))} /><span><strong>Don’t open automatically</strong><small>Start the backend and open the address yourself.</small></span></label></div><label className="browser-select"><span>Work browser</span><select disabled={draft.browser.launch_mode !== "specific"} value={draft.browser.browser_id} onChange={(event) => setDraft((value) => ({ ...value, browser: { ...value.browser, browser_id: event.target.value } }))}><option value="system" disabled>Select an installed browser</option>{settings?.browser.available.filter((item) => item.id !== "system").map((item) => <option value={item.id} key={item.id}>{item.label}</option>)}</select></label>
        </article>

        <CloudSyncSettingsCard onChanged={() => void refreshSettings()} />

        <article className="settings-card settings-summary-card">
          <div className="settings-card-heading"><span className="setting-icon violet"><Settings size={19} /></span><div><h2>Configuration health</h2><p>High-level readiness</p></div></div><div className="settings-readiness"><div><strong>{settings?.summary.configured_sections ?? 0}/5</strong><span>sections configured</span></div><i><b style={{ width: `${(settings?.summary.configured_sections ?? 0) / 5 * 100}%` }} /></i></div><div className="settings-privacy neutral"><LockKeyhole size={17} /><span><strong>Revision protected</strong><small>Each save checks for changes made in another window before writing.</small></span></div>
        </article>
        <article className="settings-card settings-summary-card">
          <div className="settings-card-heading"><span className="setting-icon"><BadgeInfo size={19} /></span><div><h2>About HustleNest</h2><p>{about?.runtime || "Local browser workspace"}</p></div></div><div className="settings-readiness"><div><strong>{about?.app_version || "v3.0"}</strong><span>application · browser {about?.browser_version || "0.35.0"}</span></div></div><div className="settings-about-links"><a className="secondary-button" href={about?.repository_url || "https://github.com/RF-YVY/HustleNest"} target="_blank" rel="noreferrer">Source <ExternalLink size={13} /></a><a className="secondary-button" href={about?.releases_url || "https://github.com/RF-YVY/HustleNest/releases"} target="_blank" rel="noreferrer">Updates and releases <ExternalLink size={13} /></a></div>
        </article>
      </section>
    </div>
  );
}
