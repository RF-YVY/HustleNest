"use client";

import { AlertTriangle, CheckCircle2, ChevronRight, Database, Download, RefreshCw, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { bridgeUrl } from "../lib/hustlenest";
import type { HealthCenterData, WorkspaceView } from "../lib/hustlenest";

export function DataHealthSettingsCard({ onNavigate }: { onNavigate: (view: WorkspaceView, id?: number, settingId?: string) => void }) {
  const [data, setData] = useState<HealthCenterData | null>(null);
  const [working, setWorking] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setWorking(true); setError("");
    try {
      const response = await fetch(`${bridgeUrl}/api/health-center`);
      const payload = await response.json() as { ok: boolean; data?: HealthCenterData; error?: { message: string } };
      if (!response.ok || !payload.ok || !payload.data) throw new Error(payload.error?.message || "Health checks could not be completed.");
      setData(payload.data);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Health checks could not be completed."); }
    finally { setWorking(false); }
  };

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${bridgeUrl}/api/health-center`, { signal: controller.signal })
      .then(async (response) => {
        const payload = await response.json() as { ok: boolean; data?: HealthCenterData; error?: { message: string } };
        if (!response.ok || !payload.ok || !payload.data) throw new Error(payload.error?.message || "Health checks could not be completed.");
        setData(payload.data);
      })
      .catch((caught) => { if (!(caught instanceof DOMException && caught.name === "AbortError")) setError(caught instanceof Error ? caught.message : "Health checks could not be completed."); })
      .finally(() => { if (!controller.signal.aborted) setWorking(false); });
    return () => controller.abort();
  }, []);

  const downloadDiagnostics = async () => {
    setWorking(true); setError("");
    try {
      const response = await fetch(`${bridgeUrl}/api/diagnostics/export`);
      if (!response.ok) throw new Error("Diagnostics could not be exported.");
      const blob = await response.blob();
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = response.headers.get("Content-Disposition")?.match(/filename="?([^";]+)"?/)?.[1] || "HustleNest_Diagnostics.json";
      link.click(); window.setTimeout(() => URL.revokeObjectURL(link.href), 1000);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Diagnostics could not be exported."); }
    finally { setWorking(false); }
  };

  const statusIcon = data?.status === "healthy" ? CheckCircle2 : AlertTriangle;
  const StatusIcon = statusIcon;
  return <article className="settings-card data-health-card" id="settings-data-health">
    <div className="settings-card-heading"><span className={`setting-icon ${data?.status === "healthy" ? "" : "rose"}`}><ShieldCheck size={19} /></span><div><h2>Data health center</h2><p>Workspace readiness, protection, and record quality</p></div><button className="secondary-button setting-save" onClick={() => void load()} disabled={working}><RefreshCw size={14} />{working ? "Checking…" : "Run checks"}</button></div>
    {error ? <div className="settings-feedback error" role="status"><AlertTriangle size={15} />{error}</div> : null}
    <div className={`health-score ${data?.status ?? "loading"}`}><StatusIcon size={22} /><span><strong>{data ? `${data.score}/100` : "Checking…"}</strong><small>{data?.status === "healthy" ? "Workspace is healthy" : data?.status === "critical" ? "Immediate attention recommended" : "A few items need attention"}</small></span><div><b>{data?.metrics.critical ?? 0}</b><small>critical</small></div><div><b>{data?.metrics.warnings ?? 0}</b><small>warnings</small></div><div><b>{data?.metrics.records_checked ?? 0}</b><small>records checked</small></div></div>
    <div className="health-issues">
      {data?.issues.map((issue) => <button key={issue.key} onClick={() => onNavigate(issue.target_view, issue.target_id ?? undefined, issue.setting_id || undefined)}><i className={issue.severity}>{issue.severity === "critical" ? <AlertTriangle size={16} /> : issue.severity === "warning" ? <AlertTriangle size={16} /> : <Database size={16} />}</i><span><strong>{issue.title}</strong><small>{issue.detail}</small></span><ChevronRight size={15} /></button>)}
      {data && !data.issues.length ? <div className="health-clear"><CheckCircle2 size={20} /><span><strong>No issues found</strong><small>Database, backups, configuration, and operational records passed their checks.</small></span></div> : null}
    </div>
    <div className="health-footer"><span><ShieldCheck size={14} /> Diagnostics exclude customer records, credentials, and filesystem paths.</span><button className="secondary-button" onClick={() => void downloadDiagnostics()} disabled={working}><Download size={14} /> Export diagnostics</button></div>
  </article>;
}
