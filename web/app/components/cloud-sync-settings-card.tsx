import { Check, Cloud, CloudDownload, CloudUpload, KeyRound, LockKeyhole, RefreshCw, Save, ShieldAlert, X } from "lucide-react";
import { useEffect, useState } from "react";
import { bridgeUrl, getBridgeData } from "../lib/hustlenest";
import type { CloudSyncWorkspaceData } from "../lib/hustlenest";

type FieldDraft = { action: "keep" | "replace" | "remove"; replacement: string };

export function CloudSyncSettingsCard({ onChanged }: { onChanged: () => void }) {
  const [data, setData] = useState<CloudSyncWorkspaceData | null>(null);
  const [enabled, setEnabled] = useState(false);
  const [provider, setProvider] = useState("");
  const [interval, setInterval] = useState(5);
  const [fields, setFields] = useState<Record<string, FieldDraft>>({});
  const [working, setWorking] = useState("");
  const [message, setMessage] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const [pullOpen, setPullOpen] = useState(false);
  const [confirmation, setConfirmation] = useState("");
  const [restartRequired, setRestartRequired] = useState(false);

  const selectProvider = (next: string, source?: CloudSyncWorkspaceData) => {
    const workspace = source ?? data;
    setProvider(next);
    const definition = workspace?.providers.find((item) => item.key === next);
    setFields(Object.fromEntries((definition?.fields ?? []).map((field) => [field.key, { action: field.configured ? "keep" : "replace", replacement: field.configured ? "" : field.default }] satisfies [string, FieldDraft])));
  };
  const accept = (workspace: CloudSyncWorkspaceData) => { setData(workspace); setEnabled(workspace.enabled); setInterval(workspace.interval_minutes); selectProvider(workspace.provider, workspace); };
  useEffect(() => { const controller = new AbortController(); getBridgeData<CloudSyncWorkspaceData>("/api/sync-settings", controller.signal).then((workspace) => { setData(workspace); setEnabled(workspace.enabled); setProvider(workspace.provider); setInterval(workspace.interval_minutes); const definition = workspace.providers.find((item) => item.key === workspace.provider); setFields(Object.fromEntries((definition?.fields ?? []).map((field) => [field.key, { action: field.configured ? "keep" : "replace", replacement: field.configured ? "" : field.default }]))); }).catch((error) => { if (!(error instanceof DOMException && error.name === "AbortError")) setMessage({ tone: "error", text: error instanceof Error ? error.message : "Cloud sync settings could not be loaded." }); }); return () => controller.abort(); }, []);
  const active = data?.providers.find((item) => item.key === provider);
  const pendingProviderValues = Object.values(fields).some((field) => field.action === "remove" || (field.action === "replace" && Boolean(field.replacement.trim())));
  const savedReady = Boolean(data?.ready && provider === data.provider && !pendingProviderValues);

  const request = async (path: string, body: object, success: string) => {
    setWorking(path); setMessage(null);
    try {
      const response = await fetch(`${bridgeUrl}${path}`, { method: path === "/api/sync-settings" ? "PUT" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const payload = await response.json() as { ok: boolean; data?: CloudSyncWorkspaceData | { message: string; uploaded?: boolean; downloaded?: boolean; restart_required?: boolean; workspace?: CloudSyncWorkspaceData }; error?: { message: string } };
      if (!response.ok || !payload.ok || !payload.data) throw new Error(payload.error?.message || "Cloud sync could not be updated.");
      const result = payload.data;
      if ("providers" in result) accept(result); else if (result.workspace) accept(result.workspace);
      const requiresRestart = "restart_required" in result && Boolean(result.restart_required);
      if (requiresRestart) setRestartRequired(true);
      setMessage({ tone: "success", text: "message" in result && result.message ? result.message : success });
      if (!requiresRestart) onChanged();
      return true;
    } catch (error) { setMessage({ tone: "error", text: error instanceof Error ? error.message : "Cloud sync could not be updated." }); return false; }
    finally { setWorking(""); }
  };
  const save = () => data && request("/api/sync-settings", { expected_revision: data.revision, enabled, provider, interval_minutes: interval, fields: Object.entries(fields).map(([key, value]) => ({ key, ...value })) }, "Cloud sync settings saved.");
  const runPull = async () => { if (!data) return; const success = await request("/api/sync-settings/pull", { expected_revision: data.revision, confirmation }, "Cloud data checked."); if (success) { setPullOpen(false); setConfirmation(""); } };

  return <>
    <article className="settings-card cloud-sync-settings-card" id="settings-cloud-sync">
      <div className="settings-card-heading"><span className="setting-icon"><Cloud size={19} /></span><div><h2>Cloud sync</h2><p>Masked provider setup and guarded database transfers</p></div><button className="secondary-button setting-save" onClick={() => void save()} disabled={!data || Boolean(working) || restartRequired}><Save size={14} />{working === "/api/sync-settings" ? "Saving…" : "Save"}</button></div>
      {restartRequired ? <div className="backup-restart"><ShieldAlert size={18} /><div><strong>Restart required</strong><span>Cloud data replaced the local database. Restart the backend before continuing.</span></div></div> : null}
      {message ? <div className={`settings-feedback ${message.tone}`} role="status">{message.tone === "success" ? <Check size={15} /> : <ShieldAlert size={15} />}{message.text}</div> : null}
      <div className="sync-top"><label className="setting-check"><input type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} /><span>Enable periodic cloud sync</span></label><label><span>Provider</span><select value={provider} onChange={(event) => selectProvider(event.target.value)}><option value="">Select provider</option>{data?.providers.map((item) => <option key={item.key} value={item.key}>{item.label}</option>)}</select></label><label><span>Interval</span><div><input type="number" min={1} max={1440} value={interval} onChange={(event) => setInterval(Number(event.target.value))} /><em>minutes</em></div></label></div>
      {active ? <div className="sync-field-list">{active.fields.map((field) => { const draft = fields[field.key] ?? { action: field.configured ? "keep" : "replace", replacement: "" }; return <div key={field.key}><span><strong>{field.label}{field.required ? " *" : ""}</strong><small>{field.configured ? "Saved value is configured and masked" : field.default ? `Suggested: ${field.default}` : "Not configured"}</small></span><select aria-label={`${field.label} action`} value={draft.action} onChange={(event) => setFields((current) => ({ ...current, [field.key]: { ...draft, action: event.target.value as FieldDraft["action"] } }))}><option value="keep" disabled={!field.configured}>Keep saved</option><option value="replace">{field.configured ? "Replace" : "Enter value"}</option><option value="remove" disabled={!field.configured}>Remove</option></select>{draft.action === "replace" ? <input type={field.sensitive ? "password" : "text"} value={draft.replacement} placeholder={field.default || `Enter ${field.label.toLowerCase()}`} onChange={(event) => setFields((current) => ({ ...current, [field.key]: { ...draft, replacement: event.target.value } }))} /> : <span className="sync-masked"><LockKeyhole size={13} />{draft.action === "remove" ? "Will be removed" : "Value remains hidden"}</span>}</div>; })}</div> : <div className="sync-empty"><Cloud size={21} /><span>Select a provider to configure its connection.</span></div>}
      <div className="settings-privacy"><LockKeyhole size={17} /><span><strong>Saved values never return to the browser</strong><small>Tokens, passwords, paths, account identifiers, and provider values use keep, replace, or remove actions.</small></span></div>
      <div className="sync-actions"><span>{savedReady ? <><Check size={14} /> Saved provider fields are ready</> : <><ShieldAlert size={14} /> Complete and save required fields first</>}</span><div>{provider === "google-drive" ? <button className="secondary-button" disabled={!savedReady || Boolean(working) || restartRequired} onClick={() => data && void request("/api/sync-settings/authorize-google", { expected_revision: data.revision }, "Google Drive authorized.")}><KeyRound size={14} /> Authorize</button> : null}<button className="secondary-button" disabled={!savedReady || !data?.enabled || Boolean(working) || restartRequired} onClick={() => data && void request("/api/sync-settings/upload", { expected_revision: data.revision }, "Database uploaded.")}><CloudUpload size={14} /> Upload now</button><button className="secondary-button" disabled={!savedReady || !data?.enabled || Boolean(working) || restartRequired} onClick={() => setPullOpen(true)}><CloudDownload size={14} /> Pull latest</button></div></div>
    </article>
    {pullOpen ? <div className="composer-backdrop"><section className="lifecycle-dialog sync-pull-dialog" role="alertdialog" aria-modal="true" aria-labelledby="sync-pull-title"><button className="dialog-close" aria-label="Close" onClick={() => setPullOpen(false)}><X size={18} /></button><span className="lifecycle-dialog-icon danger"><CloudDownload size={22} /></span><h2 id="sync-pull-title">Replace local data from cloud?</h2><p>HustleNest creates a local safety backup first and validates the downloaded database. Type <strong>PULL CLOUD DATA</strong> to continue.</p><label><span>PULL CLOUD DATA</span><input autoFocus value={confirmation} onChange={(event) => setConfirmation(event.target.value)} /></label><div><button className="secondary-button" onClick={() => setPullOpen(false)}>Cancel</button><button className="danger-button" disabled={confirmation !== "PULL CLOUD DATA" || Boolean(working)} onClick={() => void runPull()}>{working ? <RefreshCw size={14} /> : null} Pull cloud data</button></div></section></div> : null}
  </>;
}
