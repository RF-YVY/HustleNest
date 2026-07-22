import { ArchiveRestore, Check, DatabaseBackup, Download, HardDrive, RefreshCw, Save, ShieldAlert, X } from "lucide-react";
import { useEffect, useState } from "react";
import { bridgeUrl, getBridgeData } from "../lib/hustlenest";
import type { BackupWorkspaceData } from "../lib/hustlenest";

const size = (bytes: number) => bytes < 1024 * 1024 ? `${(bytes / 1024).toFixed(0)} KB` : `${(bytes / 1024 / 1024).toFixed(2)} MB`;

export function BackupSettingsCard() {
  const [data, setData] = useState<BackupWorkspaceData | null>(null);
  const [draft, setDraft] = useState<BackupWorkspaceData["settings"] | null>(null);
  const [working, setWorking] = useState("");
  const [message, setMessage] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const [restore, setRestore] = useState<BackupWorkspaceData["backups"][number] | null>(null);
  const [confirmation, setConfirmation] = useState("");
  const [restartRequired, setRestartRequired] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    getBridgeData<BackupWorkspaceData>("/api/backups", controller.signal).then((payload) => { setData(payload); setDraft(payload.settings); }).catch((error) => { if (!(error instanceof DOMException && error.name === "AbortError")) setMessage({ tone: "error", text: error instanceof Error ? error.message : "Backups could not be loaded." }); });
    return () => controller.abort();
  }, []);

  const accept = (payload: BackupWorkspaceData, text: string) => { setData(payload); setDraft(payload.settings); setMessage({ tone: "success", text }); };
  const request = async (method: "PUT" | "POST", path: string, body: object, label: string) => {
    setWorking(label); setMessage(null);
    try {
      const response = await fetch(`${bridgeUrl}${path}`, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const payload = await response.json() as { ok: boolean; data?: BackupWorkspaceData; error?: { message: string } };
      if (!response.ok || !payload.ok || !payload.data) throw new Error(payload.error?.message || "Backup maintenance could not be completed.");
      accept(payload.data, label === "save" ? "Backup settings saved." : "A fresh database backup was created.");
    } catch (error) { setMessage({ tone: "error", text: error instanceof Error ? error.message : "Backup maintenance could not be completed." }); }
    finally { setWorking(""); }
  };

  const download = async (item: BackupWorkspaceData["backups"][number]) => {
    setWorking(`download-${item.id}`);
    try {
      const response = await fetch(`${bridgeUrl}/api/backups/${item.id}/download`);
      if (!response.ok) throw new Error("The backup could not be downloaded.");
      const url = URL.createObjectURL(await response.blob()); const link = document.createElement("a"); link.href = url; link.download = item.filename; link.click(); URL.revokeObjectURL(url);
    } catch (error) { setMessage({ tone: "error", text: error instanceof Error ? error.message : "The backup could not be downloaded." }); }
    finally { setWorking(""); }
  };

  const restoreSelected = async () => {
    if (!restore || !data) return;
    setWorking("restore"); setMessage(null);
    try {
      const response = await fetch(`${bridgeUrl}/api/backups/${restore.id}/restore`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expected_revision: data.revision, confirmation }) });
      const payload = await response.json() as { ok: boolean; data?: { restart_required: boolean }; error?: { message: string } };
      if (!response.ok || !payload.ok || !payload.data) throw new Error(payload.error?.message || "The backup could not be restored.");
      setRestore(null); setConfirmation(""); setRestartRequired(payload.data.restart_required); setMessage({ tone: "success", text: "Backup restored. Restart HustleNest before continuing work." });
    } catch (error) { setMessage({ tone: "error", text: error instanceof Error ? error.message : "The backup could not be restored." }); }
    finally { setWorking(""); }
  };

  return <>
    <article className="settings-card backup-settings-card" id="settings-backups">
      <div className="settings-card-heading"><span className="setting-icon violet"><DatabaseBackup size={19} /></span><div><h2>Backups & recovery</h2><p>Automatic local database protection</p></div><button className="secondary-button setting-save" disabled={!data || !draft || Boolean(working) || restartRequired} onClick={() => draft && data && void request("PUT", "/api/backups", { expected_revision: data.revision, values: draft }, "save")}><Save size={14} />{working === "save" ? "Saving…" : "Save"}</button></div>
      {restartRequired ? <div className="backup-restart"><ShieldAlert size={18} /><div><strong>Restart required</strong><span>The restored database is in place. Close and restart the backend and refresh this browser before making changes.</span></div></div> : null}
      {message ? <div className={`settings-feedback ${message.tone}`} role="status">{message.tone === "success" ? <Check size={15} /> : <ShieldAlert size={15} />}{message.text}</div> : null}
      {draft ? <div className="backup-config"><label className="setting-check"><input type="checkbox" checked={draft.enabled} disabled={restartRequired} onChange={(event) => setDraft({ ...draft, enabled: event.target.checked })} /><span>Enable automatic backups while the browser backend is running</span></label><div className="backup-config-row"><label><span>Frequency</span><select value={draft.frequency} onChange={(event) => setDraft({ ...draft, frequency: event.target.value as typeof draft.frequency })}><option value="daily">Daily</option><option value="weekly">Weekly</option><option value="manual">Manual only</option></select></label><label><span>Keep latest</span><input type="number" min={1} max={100} value={draft.max_backups} onChange={(event) => setDraft({ ...draft, max_backups: Number(event.target.value) })} /></label></div><label className="setting-check"><input type="checkbox" checked={draft.using_managed_folder} onChange={(event) => setDraft({ ...draft, using_managed_folder: event.target.checked })} /><span>Use HustleNest managed backup folder</span></label><label><span>Backup folder</span><input disabled={draft.using_managed_folder} value={draft.folder} onChange={(event) => setDraft({ ...draft, folder: event.target.value })} /></label></div> : null}
      <div className="backup-actions"><div><HardDrive size={16} /><span><strong>{data?.summary.count ?? 0} backups</strong><small>{size(data?.summary.total_bytes ?? 0)} stored · {data?.settings.last_backup ? `Last ${new Date(data.settings.last_backup).toLocaleString()}` : "No completed backup yet"}</small></span></div><button className="primary-button" disabled={!data || Boolean(working) || restartRequired} onClick={() => data && void request("POST", "/api/backups", { expected_revision: data.revision }, "backup")}><RefreshCw size={15} />{working === "backup" ? "Backing up…" : "Back up now"}</button></div>
      <div className="backup-list">{data?.backups.map((item) => <div key={item.id}><DatabaseBackup size={17} /><span><strong>{item.filename}</strong><small>{new Date(item.created_at).toLocaleString()} · {size(item.size_bytes)}{item.includes_media ? " · backgrounds included" : ""}</small></span><button className="icon-button" aria-label={`Download ${item.filename}`} onClick={() => void download(item)} disabled={Boolean(working)}><Download size={15} /></button><button className="secondary-button" onClick={() => { setRestore(item); setConfirmation(""); }} disabled={Boolean(working) || restartRequired}><ArchiveRestore size={14} /> Restore</button></div>)}{data && !data.backups.length ? <p>No backups yet. Create one before major changes.</p> : null}</div>
    </article>
    {restore ? <div className="composer-backdrop lifecycle-dialog-backdrop" role="presentation"><section className="lifecycle-dialog backup-restore-dialog" role="alertdialog" aria-modal="true" aria-labelledby="restore-backup-title"><button className="dialog-close" aria-label="Close" onClick={() => setRestore(null)}><X size={18} /></button><span className="lifecycle-dialog-icon danger"><ArchiveRestore size={22} /></span><h2 id="restore-backup-title">Restore this database?</h2><p>This replaces all current data with <strong>{restore.filename}</strong>. A safety copy is created first. Type the full phrase below.</p><label><span>RESTORE {restore.filename}</span><input autoFocus value={confirmation} onChange={(event) => setConfirmation(event.target.value)} /></label><div><button className="secondary-button" onClick={() => setRestore(null)} disabled={working === "restore"}>Cancel</button><button className="danger-button" onClick={() => void restoreSelected()} disabled={working === "restore" || confirmation !== `RESTORE ${restore.filename}`}>{working === "restore" ? "Restoring…" : "Restore database"}</button></div></section></div> : null}
  </>;
}
