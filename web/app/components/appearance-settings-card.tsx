/* eslint-disable @next/next/no-img-element */
import { Check, Image as ImageIcon, MonitorCog, Save, Trash2, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { bridgeUrl } from "../lib/hustlenest";
import type { SettingsWorkspaceData } from "../lib/hustlenest";

type Props = { settings: SettingsWorkspaceData; onUpdated: (settings: SettingsWorkspaceData) => void };
type Draft = SettingsWorkspaceData["appearance"];
type Theme = Draft["theme"];

const themes: Array<{ value: Theme; label: string; description: string }> = [
  { value: "light", label: "HustleNest Light", description: "Bright studio workspace" },
  { value: "dark", label: "HustleNest Dark", description: "Low-light workspace" },
  { value: "minty", label: "Minty", description: "Fresh palette from CyberLabLog" },
  { value: "solar", label: "Solar", description: "Solarized palette from CyberLabLog" },
  { value: "mission-control", label: "Mission Control", description: "Orbital console from APRS-PropView" },
  { value: "glass", label: "Glass", description: "Frosted layers inspired by iOS and macOS" },
];

const readFile = (file: File) => new Promise<{ name: string; content_base64: string }>((resolve, reject) => {
  const reader = new FileReader();
  reader.onerror = () => reject(new Error("The logo could not be read."));
  reader.onload = () => {
    const encoded = String(reader.result ?? "").split(",", 2)[1];
    if (!encoded) reject(new Error("The logo is empty.")); else resolve({ name: file.name, content_base64: encoded });
  };
  reader.readAsDataURL(file);
});

export function AppearanceSettingsCard({ settings, onUpdated }: Props) {
  const input = useRef<HTMLInputElement>(null);
  const [draft, setDraft] = useState<Draft>(settings.appearance);
  const [sourceRevision, setSourceRevision] = useState(settings.summary.revision);
  const [working, setWorking] = useState("");
  const [message, setMessage] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  if (sourceRevision !== settings.summary.revision) { setSourceRevision(settings.summary.revision); setDraft(settings.appearance); }

  const accept = (updated: SettingsWorkspaceData, text: string) => { onUpdated(updated); setDraft(updated.appearance); setMessage({ tone: "success", text }); };
  const save = async () => {
    setWorking("save"); setMessage(null);
    try {
      const response = await fetch(`${bridgeUrl}/api/settings`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ section: "appearance", values: draft, expected_revision: settings.summary.revision }) });
      const payload = await response.json() as { ok: boolean; data?: SettingsWorkspaceData; error?: { message: string } };
      if (!response.ok || !payload.ok || !payload.data) throw new Error(payload.error?.message || "Appearance settings could not be saved.");
      accept(payload.data, "Appearance and dashboard preferences saved.");
    } catch (error) { setMessage({ tone: "error", text: error instanceof Error ? error.message : "Appearance settings could not be saved." }); }
    finally { setWorking(""); }
  };
  const chooseTheme = async (theme: Theme) => {
    setDraft((current) => ({ ...current, theme })); setWorking("theme"); setMessage(null);
    try {
      const response = await fetch(`${bridgeUrl}/api/settings`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ section: "appearance", values: { theme }, expected_revision: settings.summary.revision }) });
      const payload = await response.json() as { ok: boolean; data?: SettingsWorkspaceData; error?: { message: string } };
      if (!response.ok || !payload.ok || !payload.data) throw new Error(payload.error?.message || "The theme could not be applied.");
      accept(payload.data, "Theme applied.");
    } catch (error) {
      setDraft((current) => ({ ...current, theme: settings.appearance.theme }));
      setMessage({ tone: "error", text: error instanceof Error ? error.message : "The theme could not be applied." });
    } finally { setWorking(""); }
  };
  const logoRequest = async (method: "POST" | "DELETE", file?: File) => {
    setWorking("logo"); setMessage(null);
    try {
      const body: Record<string, unknown> = { expected_revision: settings.summary.revision };
      if (file) body.file = await readFile(file);
      const response = await fetch(`${bridgeUrl}/api/settings/logo`, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const payload = await response.json() as { ok: boolean; data?: SettingsWorkspaceData; error?: { message: string } };
      if (!response.ok || !payload.ok || !payload.data) throw new Error(payload.error?.message || "The business logo could not be updated.");
      accept(payload.data, method === "DELETE" ? "Business logo removed." : "Business logo updated.");
    } catch (error) { setMessage({ tone: "error", text: error instanceof Error ? error.message : "The business logo could not be updated." }); }
    finally { setWorking(""); if (input.current) input.current.value = ""; }
  };
  const updateSection = (key: string, field: "visible" | "collapsed", value: boolean) => setDraft((current) => ({ ...current, dashboard_sections: current.dashboard_sections.map((item) => item.key === key ? { ...item, [field]: value } : item) }));

  return <article className="settings-card appearance-settings-card">
    <div className="settings-card-heading"><span className="setting-icon violet"><MonitorCog size={19} /></span><div><h2>Appearance & dashboard</h2><p>Saved theme, business logo, and desktop fallback layout</p></div><button className="secondary-button setting-save" onClick={() => void save()} disabled={Boolean(working)}><Save size={14} />{working === "save" ? "Saving…" : "Save"}</button></div>
    {message ? <div className={`settings-feedback ${message.tone}`} role="status"><Check size={15} />{message.text}</div> : null}
    <div className="appearance-grid">
      <section><h3>Color theme</h3><p className="theme-hint">Choose a theme to save and apply it immediately.</p><div className="theme-options">{themes.map((theme) => <label key={theme.value}><input type="radio" name="saved-theme" checked={draft.theme === theme.value} disabled={Boolean(working)} onChange={() => void chooseTheme(theme.value)} /><span><i className={`theme-swatch ${theme.value}`} /><strong>{theme.label}</strong><small>{theme.description}</small></span></label>)}</div></section>
      <section><h3>Business logo</h3><div className={`logo-preview logo-${draft.logo_alignment}`}>{settings.business.logo_available ? <img src={`${bridgeUrl}/api/settings/logo?v=${settings.summary.revision}`} alt="Current business logo" style={{ maxWidth: `${Math.min(draft.logo_size, 180)}px`, maxHeight: `${Math.min(draft.logo_size, 90)}px` }} /> : <span><ImageIcon size={22} />No logo uploaded</span>}</div><input ref={input} className="visually-hidden" type="file" accept="image/png,image/jpeg,image/gif,image/webp" onChange={(event) => { const file = event.target.files?.[0]; if (file) void logoRequest("POST", file); }} /><div className="logo-actions"><button className="secondary-button" onClick={() => input.current?.click()} disabled={Boolean(working)}><Upload size={14} />{settings.business.logo_configured ? "Replace" : "Upload"}</button>{settings.business.logo_configured ? <button className="icon-button payment-remove" aria-label="Remove business logo" onClick={() => void logoRequest("DELETE")} disabled={Boolean(working)}><Trash2 size={15} /></button> : null}</div><div className="appearance-fields"><label><span>Alignment</span><select value={draft.logo_alignment} onChange={(event) => setDraft({ ...draft, logo_alignment: event.target.value as Draft["logo_alignment"] })}><option value="top-left">Top left</option><option value="top-center">Top center</option><option value="top-right">Top right</option><option value="bottom-left">Bottom left</option><option value="bottom-center">Bottom center</option><option value="bottom-right">Bottom right</option></select></label><label><span>Desktop size</span><input type="number" min={24} max={1024} value={draft.logo_size} onChange={(event) => setDraft({ ...draft, logo_size: Number(event.target.value) })} /></label></div></section>
    </div>
    <details className="dashboard-section-settings"><summary>Desktop fallback dashboard sections</summary><p>These controls keep the existing desktop dashboard configured while browser parity is being verified.</p><div><strong>Section</strong><strong>Show</strong><strong>Start collapsed</strong></div>{draft.dashboard_sections.map((section) => <label key={section.key}><span>{section.label}</span><input type="checkbox" checked={section.visible} onChange={(event) => updateSection(section.key, "visible", event.target.checked)} /><input type="checkbox" checked={section.collapsed} onChange={(event) => updateSection(section.key, "collapsed", event.target.checked)} /></label>)}</details>
  </article>;
}
