"use client";

import { CalendarCheck2, Check, ChevronRight, Flag, Plus, Target, Trash2, X } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { bridgeUrl, type Goal, type GoalsWorkspaceData } from "../lib/hustlenest";

const localDate = () => new Date().toLocaleDateString("en-CA");
const yearEnd = () => `${new Date().getFullYear()}-12-31`;
const emptyDraft = () => ({ name: "", metric_type: "revenue", target_value: "", current_value: "0", start_date: localDate(), end_date: yearEnd(), owner: "", progress_notes: "", threshold_warning: "0.5", threshold_critical: "0.25", auto_calculate: true });

type GoalDraft = ReturnType<typeof emptyDraft>;

const draftFromGoal = (goal: Goal): GoalDraft => ({
  name: goal.name, metric_type: goal.metric_type, target_value: goal.target_value, current_value: goal.current_value,
  start_date: goal.start_date ?? "", end_date: goal.end_date ?? "", owner: goal.owner,
  progress_notes: goal.progress_notes, threshold_warning: String(goal.threshold_warning),
  threshold_critical: String(goal.threshold_critical), auto_calculate: goal.auto_calculate,
});

export function GoalPanel({ onClose, onChanged }: { onClose: () => void; onChanged: (message: string) => void }) {
  const [workspace, setWorkspace] = useState<GoalsWorkspaceData | null>(null);
  const [selected, setSelected] = useState<Goal | null>(null);
  const [draft, setDraft] = useState<GoalDraft>(emptyDraft);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [deleteArmed, setDeleteArmed] = useState(false);
  const [checkpointOpen, setCheckpointOpen] = useState(false);
  const [checkpoint, setCheckpoint] = useState({ checkpoint_date: localDate(), actual_value: "", forecast_value: "", notes: "" });

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${bridgeUrl}/api/goals`, { signal: controller.signal }).then(async (response) => {
      const payload = (await response.json()) as { ok: boolean; data?: GoalsWorkspaceData; error?: { message: string } };
      if (!response.ok || !payload.ok || !payload.data) throw new Error(payload.error?.message || "Goals could not be loaded.");
      setWorkspace(payload.data);
      if (payload.data.goals[0]) { setSelected(payload.data.goals[0]); setDraft(draftFromGoal(payload.data.goals[0])); }
    }).catch((caught: unknown) => { if (!(caught instanceof DOMException && caught.name === "AbortError")) setError(caught instanceof Error ? caught.message : "Goals could not be loaded."); });
    return () => controller.abort();
  }, []);

  const choose = (goal: Goal | null) => {
    setSelected(goal); setDraft(goal ? draftFromGoal(goal) : emptyDraft()); setError(""); setDeleteArmed(false); setCheckpointOpen(false);
  };
  const field = <K extends keyof GoalDraft>(name: K, value: GoalDraft[K]) => setDraft((current) => ({ ...current, [name]: value }));
  const replaceSaved = (goal: Goal) => {
    setWorkspace((current) => current ? { ...current, goals: current.goals.some((item) => item.id === goal.id) ? current.goals.map((item) => item.id === goal.id ? goal : item) : [...current.goals, goal] } : current);
    setSelected(goal); setDraft(draftFromGoal(goal));
  };
  const request = async (url: string, method: string, body: object) => {
    const response = await fetch(url, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const payload = (await response.json()) as { ok: boolean; data?: Goal; error?: { message: string } };
    if (!response.ok || !payload.ok || !payload.data) throw new Error(payload.error?.message || "The goal could not be saved.");
    return payload.data;
  };
  const saveGoal = async (event: FormEvent) => {
    event.preventDefault(); setSaving(true); setError("");
    try {
      const saved = await request(`${bridgeUrl}/api/goals${selected ? `/${selected.id}` : ""}`, selected ? "PUT" : "POST", { expected_revision: selected?.revision, values: draft });
      replaceSaved(saved); onChanged(`${saved.name} saved.`);
    } catch (caught: unknown) { setError(caught instanceof Error ? caught.message : "The goal could not be saved."); } finally { setSaving(false); }
  };
  const saveCheckpoint = async () => {
    if (!selected) return; setSaving(true); setError("");
    try {
      const saved = await request(`${bridgeUrl}/api/goals/${selected.id}/checkpoints`, "POST", { expected_revision: selected.revision, values: checkpoint });
      replaceSaved(saved); setCheckpoint({ checkpoint_date: localDate(), actual_value: "", forecast_value: "", notes: "" }); setCheckpointOpen(false); onChanged(`Checkpoint added to ${saved.name}.`);
    } catch (caught: unknown) { setError(caught instanceof Error ? caught.message : "The checkpoint could not be saved."); } finally { setSaving(false); }
  };
  const deleteGoal = async () => {
    if (!selected) return; setSaving(true); setError("");
    try {
      const response = await fetch(`${bridgeUrl}/api/goals/${selected.id}`, { method: "DELETE", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expected_revision: selected.revision }) });
      const payload = (await response.json()) as { ok: boolean; error?: { message: string } };
      if (!response.ok || !payload.ok) throw new Error(payload.error?.message || "The goal could not be deleted.");
      const remaining = workspace?.goals.filter((item) => item.id !== selected.id) ?? [];
      setWorkspace((current) => current ? { ...current, goals: remaining } : current); choose(remaining[0] ?? null); onChanged(`${selected.name} deleted.`);
    } catch (caught: unknown) { setError(caught instanceof Error ? caught.message : "The goal could not be deleted."); } finally { setSaving(false); }
  };

  return <div className="composer-backdrop quick-add-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <aside className="quick-add-panel goal-panel" role="dialog" aria-modal="true" aria-labelledby="goal-panel-title">
      <div className="quick-add-heading"><div><span>Business planning</span><h2 id="goal-panel-title">Goals & checkpoints</h2><p>Set targets and keep progress reviews in one place.</p></div><button className="icon-button" onClick={onClose} aria-label="Close goal manager"><X size={20} /></button></div>
      <div className="goal-picker"><button className={!selected ? "active" : ""} onClick={() => choose(null)}><Plus size={15} /> New goal</button>{workspace?.goals.map((goal) => <button className={selected?.id === goal.id ? "active" : ""} onClick={() => choose(goal)} key={goal.id}><span><strong>{goal.name}</strong><small>{goal.progress_percent}% · {goal.status.replace("-", " ")}</small></span><ChevronRight size={14} /></button>)}</div>
      <form className="quick-add-form goal-form" onSubmit={saveGoal}>
        <div className="goal-form-intro"><Target size={18} /><div><strong>{selected ? "Update this goal" : "Create a measurable goal"}</strong><span>Automatic goals calculate from business records; manual goals use the value entered here.</span></div></div>
        <label><span>Goal name *</span><input autoFocus value={draft.name} onChange={(event) => field("name", event.target.value)} required placeholder="Annual revenue" /></label>
        <div className="quick-form-pair"><label><span>Metric *</span><select value={draft.metric_type} onChange={(event) => field("metric_type", event.target.value)}>{(workspace?.metric_options ?? ["revenue", "sales", "profit", "orders", "expenses", "losses", "crm-followups"]).map((metric) => <option value={metric} key={metric}>{metric.replace("crm-", "CRM ")}</option>)}</select></label><label><span>Target *</span><input type="number" min="0.01" step="0.01" value={draft.target_value} onChange={(event) => field("target_value", event.target.value)} required /></label></div>
        <label className="setting-check"><input type="checkbox" checked={draft.auto_calculate} onChange={(event) => field("auto_calculate", event.target.checked)} /><span><strong>Calculate progress automatically</strong><small>Uses orders, finance, or CRM activity for the selected metric.</small></span></label>
        {!draft.auto_calculate ? <label><span>Current value</span><input type="number" min="0" step="0.01" value={draft.current_value} onChange={(event) => field("current_value", event.target.value)} /></label> : null}
        <div className="quick-form-pair"><label><span>Start date</span><input type="date" value={draft.start_date} onChange={(event) => field("start_date", event.target.value)} /></label><label><span>Target date</span><input type="date" min={draft.start_date} value={draft.end_date} onChange={(event) => field("end_date", event.target.value)} /></label></div>
        <div className="quick-form-pair"><label><span>Owner</span><input value={draft.owner} onChange={(event) => field("owner", event.target.value)} placeholder="Optional" /></label><label><span>Warning / critical</span><span className="goal-thresholds"><input aria-label="Warning threshold" type="number" min="0" max="1" step="0.05" value={draft.threshold_warning} onChange={(event) => field("threshold_warning", event.target.value)} /><input aria-label="Critical threshold" type="number" min="0" max="1" step="0.05" value={draft.threshold_critical} onChange={(event) => field("threshold_critical", event.target.value)} /></span></label></div>
        <label><span>Progress notes</span><textarea rows={3} value={draft.progress_notes} onChange={(event) => field("progress_notes", event.target.value)} placeholder="What matters about this target?" /></label>
        {selected ? <section className="goal-checkpoints"><div><span><Flag size={15} /><strong>Checkpoints</strong><small>{selected.checkpoints.length} progress reviews</small></span><button type="button" onClick={() => setCheckpointOpen((value) => !value)}>{checkpointOpen ? "Cancel" : "Add checkpoint"}</button></div>{checkpointOpen ? <div className="checkpoint-form"><div className="quick-form-triple"><label><span>Date</span><input type="date" value={checkpoint.checkpoint_date} onChange={(event) => setCheckpoint((current) => ({ ...current, checkpoint_date: event.target.value }))} required /></label><label><span>Actual</span><input type="number" min="0" step="0.01" value={checkpoint.actual_value} onChange={(event) => setCheckpoint((current) => ({ ...current, actual_value: event.target.value }))} required /></label><label><span>Forecast</span><input type="number" min="0" step="0.01" value={checkpoint.forecast_value} onChange={(event) => setCheckpoint((current) => ({ ...current, forecast_value: event.target.value }))} /></label></div><label><span>Review note</span><input value={checkpoint.notes} onChange={(event) => setCheckpoint((current) => ({ ...current, notes: event.target.value }))} placeholder="What changed?" /></label><button type="button" className="secondary-button" onClick={() => void saveCheckpoint()} disabled={saving || !checkpoint.actual_value}><CalendarCheck2 size={14} /> Save checkpoint</button></div> : null}{selected.checkpoints.slice(0, 4).map((item) => <article key={item.id}><Check size={13} /><span><strong>{item.actual_value} actual · {item.forecast_value} forecast</strong><small>{item.checkpoint_date}{item.notes ? ` · ${item.notes}` : ""}</small></span></article>)}</section> : null}
        {error ? <p className="quick-add-error" role="alert">{error}</p> : null}
        <div className="quick-add-actions goal-actions">{selected ? (!deleteArmed ? <button type="button" className="danger-text-button" onClick={() => setDeleteArmed(true)}><Trash2 size={14} /> Delete</button> : <button type="button" className="danger-button" onClick={() => void deleteGoal()} disabled={saving}>Confirm delete</button>) : null}<span /><button type="button" className="secondary-button" onClick={onClose}>Close</button><button className="primary-button" disabled={saving}>{saving ? "Saving…" : selected ? "Save changes" : "Create goal"}</button></div>
      </form>
    </aside>
  </div>;
}
