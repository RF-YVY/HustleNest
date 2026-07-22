/* eslint-disable @next/next/no-img-element */
import { BriefcaseBusiness, Camera, Check, Mail, Save, Trash2, Upload, UserRound } from "lucide-react";
import { useRef, useState } from "react";
import { bridgeUrl } from "../lib/hustlenest";
import type { SettingsWorkspaceData } from "../lib/hustlenest";

type Props = { settings: SettingsWorkspaceData; onUpdated: (settings: SettingsWorkspaceData) => void };

const readFile = (file: File) => new Promise<{ name: string; content_base64: string }>((resolve, reject) => {
  const reader = new FileReader();
  reader.onerror = () => reject(new Error("The profile photo could not be read."));
  reader.onload = () => {
    const encoded = String(reader.result ?? "").split(",", 2)[1];
    if (!encoded) reject(new Error("The profile photo is empty.")); else resolve({ name: file.name, content_base64: encoded });
  };
  reader.readAsDataURL(file);
});

export function OwnerProfileSettingsCard({ settings, onUpdated }: Props) {
  const input = useRef<HTMLInputElement>(null);
  const [draft, setDraft] = useState(() => ({ display_name: settings.profile.display_name, role: settings.profile.role, email: settings.profile.email }));
  const [sourceRevision, setSourceRevision] = useState(settings.summary.revision);
  const [working, setWorking] = useState("");
  const [message, setMessage] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  if (sourceRevision !== settings.summary.revision) {
    setSourceRevision(settings.summary.revision);
    setDraft({ display_name: settings.profile.display_name, role: settings.profile.role, email: settings.profile.email });
  }

  const accept = (updated: SettingsWorkspaceData, text: string) => { onUpdated(updated); setMessage({ tone: "success", text }); };
  const save = async () => {
    setWorking("save"); setMessage(null);
    try {
      const response = await fetch(`${bridgeUrl}/api/settings`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ section: "profile", values: draft, expected_revision: settings.summary.revision }) });
      const payload = await response.json() as { ok: boolean; data?: SettingsWorkspaceData; error?: { message: string } };
      if (!response.ok || !payload.ok || !payload.data) throw new Error(payload.error?.message || "The owner profile could not be saved.");
      accept(payload.data, "Owner profile saved.");
    } catch (error) { setMessage({ tone: "error", text: error instanceof Error ? error.message : "The owner profile could not be saved." }); }
    finally { setWorking(""); }
  };
  const avatarRequest = async (method: "POST" | "DELETE", file?: File) => {
    setWorking("avatar"); setMessage(null);
    try {
      const body: Record<string, unknown> = { expected_revision: settings.summary.revision };
      if (file) body.file = await readFile(file);
      const response = await fetch(`${bridgeUrl}/api/settings/profile/avatar`, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const payload = await response.json() as { ok: boolean; data?: SettingsWorkspaceData; error?: { message: string } };
      if (!response.ok || !payload.ok || !payload.data) throw new Error(payload.error?.message || "The profile photo could not be updated.");
      accept(payload.data, method === "DELETE" ? "Profile photo removed." : "Profile photo updated.");
    } catch (error) { setMessage({ tone: "error", text: error instanceof Error ? error.message : "The profile photo could not be updated." }); }
    finally { setWorking(""); if (input.current) input.current.value = ""; }
  };

  return <article className="settings-card owner-profile-card" id="settings-owner-profile">
    <div className="settings-card-heading"><span className="setting-icon"><UserRound size={19} /></span><div><h2>Owner profile</h2><p>The identity shown in the navigation footer</p></div><button className="secondary-button setting-save" onClick={() => void save()} disabled={Boolean(working)}><Save size={14} />{working === "save" ? "Saving…" : "Save"}</button></div>
    {message ? <div className={`settings-feedback ${message.tone}`} role="status"><Check size={15} />{message.text}</div> : null}
    <div className="owner-profile-layout">
      <div className="owner-avatar-editor">
        <div className={`owner-avatar-preview${settings.profile.avatar_available ? " has-photo" : ""}`}>{settings.profile.avatar_available ? <img src={`${bridgeUrl}/api/settings/profile/avatar?v=${settings.summary.revision}`} alt="Current owner profile" /> : <span>{settings.profile.initials}</span>}</div>
        <input ref={input} className="visually-hidden" type="file" accept="image/png,image/jpeg,image/gif,image/webp" onChange={(event) => { const file = event.target.files?.[0]; if (file) void avatarRequest("POST", file); }} />
        <div><button className="secondary-button" onClick={() => input.current?.click()} disabled={Boolean(working)}>{settings.profile.avatar_configured ? <Camera size={14} /> : <Upload size={14} />}{settings.profile.avatar_configured ? "Replace photo" : "Add photo"}</button>{settings.profile.avatar_configured ? <button className="icon-button payment-remove" aria-label="Remove profile photo" onClick={() => void avatarRequest("DELETE")} disabled={Boolean(working)}><Trash2 size={15} /></button> : null}</div>
        <small>PNG, JPEG, GIF, or WebP · 5 MB maximum</small>
      </div>
      <div className="settings-form owner-profile-fields">
        <label><span><UserRound size={13} /> Display name</span><input value={draft.display_name} maxLength={160} onChange={(event) => setDraft((value) => ({ ...value, display_name: event.target.value }))} /></label>
        <label><span><BriefcaseBusiness size={13} /> Role</span><input value={draft.role} maxLength={100} onChange={(event) => setDraft((value) => ({ ...value, role: event.target.value }))} /></label>
        <label><span><Mail size={13} /> Email <em>optional</em></span><input type="email" value={draft.email} maxLength={254} onChange={(event) => setDraft((value) => ({ ...value, email: event.target.value }))} /></label>
      </div>
    </div>
  </article>;
}
