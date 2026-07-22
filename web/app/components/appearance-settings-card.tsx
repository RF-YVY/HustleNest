/* eslint-disable @next/next/no-img-element */
import { ArrowDown, ArrowUp, Check, Eye, Image as ImageIcon, MonitorCog, Save, Sparkles, Trash2, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { bridgeUrl } from "../lib/hustlenest";
import type { SettingsWorkspaceData } from "../lib/hustlenest";

type Props = { settings: SettingsWorkspaceData; onUpdated: (settings: SettingsWorkspaceData) => void };
type Draft = SettingsWorkspaceData["appearance"];
type Theme = Draft["theme"];
type Background = Draft["backgrounds"][Theme];

const textSizes = [
  { value: 1, label: "Default", detail: "100%" },
  { value: 1.1, label: "Comfortable", detail: "110%" },
  { value: 1.25, label: "Large", detail: "125%" },
  { value: 1.4, label: "Extra large", detail: "140%" },
];

const themes: Array<{ value: Theme; label: string; description: string }> = [
  { value: "light", label: "HustleNest Light", description: "Bright studio workspace" },
  { value: "dark", label: "HustleNest Dark", description: "Low-light workspace" },
  { value: "minty", label: "Minty", description: "Fresh and botanical" },
  { value: "solar", label: "Solar", description: "Warm solarized contrast" },
  { value: "mission-control", label: "Mission Control", description: "Orbital operations console" },
  { value: "glass", label: "Glass", description: "Neon translucent layers" },
];

const presets: Array<{ value: Background["preset"]; label: string }> = [
  { value: "aurora", label: "Aurora" },
  { value: "nebula", label: "Nebula" },
  { value: "prism", label: "Prism" },
  { value: "sunset", label: "Sunset" },
];

const defaultBackground = (): Background => ({ enabled: false, source: "none", preset: "aurora", custom_path: "", custom_configured: false, custom_available: false, fit: "cover", position_x: 50, position_y: 50, dim: 38, tone: "dark" });
const normalizeAppearance = (appearance: Draft): Draft => {
  const incoming = appearance as Draft & { backgrounds?: Partial<Draft["backgrounds"]> };
  const backgrounds = Object.fromEntries(themes.map(({ value }) => [value, { ...defaultBackground(), ...(incoming.backgrounds?.[value] ?? {}) }])) as Draft["backgrounds"];
  return {
    ...appearance,
    glass_intensity: appearance.glass_intensity ?? "balanced",
    reduce_transparency: appearance.reduce_transparency ?? false,
    reduce_motion: appearance.reduce_motion ?? false,
    backgrounds,
    active_background: backgrounds[appearance.theme],
  };
};

const readFile = (file: File) => new Promise<{ name: string; content_base64: string }>((resolve, reject) => {
  const reader = new FileReader();
  reader.onerror = () => reject(new Error("The image could not be read."));
  reader.onload = () => {
    const encoded = String(reader.result ?? "").split(",", 2)[1];
    if (!encoded) reject(new Error("The image is empty.")); else resolve({ name: file.name, content_base64: encoded });
  };
  reader.readAsDataURL(file);
});

const optimizeBackground = async (file: File) => {
  const source = URL.createObjectURL(file);
  try {
    const image = await new Promise<HTMLImageElement>((resolve, reject) => {
      const element = new Image();
      element.onload = () => resolve(element);
      element.onerror = () => reject(new Error("The background image could not be decoded."));
      element.src = source;
    });
    const scale = Math.min(1, 2560 / Math.max(image.naturalWidth, image.naturalHeight));
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(image.naturalWidth * scale));
    canvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
    const context = canvas.getContext("2d", { alpha: false });
    if (!context) throw new Error("Image optimization is unavailable.");
    context.drawImage(image, 0, 0, canvas.width, canvas.height);
    const sample = document.createElement("canvas"); sample.width = 24; sample.height = 24;
    const sampleContext = sample.getContext("2d", { willReadFrequently: true });
    sampleContext?.drawImage(canvas, 0, 0, 24, 24);
    const pixels = sampleContext?.getImageData(0, 0, 24, 24).data;
    let luminance = 0;
    if (pixels) for (let index = 0; index < pixels.length; index += 4) luminance += pixels[index] * .2126 + pixels[index + 1] * .7152 + pixels[index + 2] * .0722;
    const tone: Background["tone"] = pixels && luminance / (pixels.length / 4) > 145 ? "light" : "dark";
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/webp", .86));
    if (!blob) return { ...(await readFile(file)), tone };
    return { ...(await readFile(new File([blob], `${file.name.replace(/\.[^.]+$/, "") || "background"}.webp`, { type: "image/webp" }))), tone };
  } finally { URL.revokeObjectURL(source); }
};

export function AppearanceSettingsCard({ settings, onUpdated }: Props) {
  const logoInput = useRef<HTMLInputElement>(null);
  const backgroundInput = useRef<HTMLInputElement>(null);
  const [draft, setDraft] = useState<Draft>(() => normalizeAppearance(settings.appearance));
  const [sourceRevision, setSourceRevision] = useState(settings.summary.revision);
  const [working, setWorking] = useState("");
  const [message, setMessage] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  if (sourceRevision !== settings.summary.revision) { setSourceRevision(settings.summary.revision); setDraft(normalizeAppearance(settings.appearance)); }

  const background = draft.backgrounds[draft.theme];
  const accept = (updated: SettingsWorkspaceData, text: string) => { onUpdated(updated); setDraft(normalizeAppearance(updated.appearance)); setMessage({ tone: "success", text }); };
  const patchBackground = (patch: Partial<Background>) => setDraft((current) => ({ ...current, backgrounds: { ...current.backgrounds, [current.theme]: { ...current.backgrounds[current.theme], ...patch } } }));
  const save = async () => {
    setWorking("save"); setMessage(null);
    try {
      const response = await fetch(`${bridgeUrl}/api/settings`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ section: "appearance", values: draft, expected_revision: settings.summary.revision }) });
      const payload = await response.json() as { ok: boolean; data?: SettingsWorkspaceData; error?: { message: string } };
      if (!response.ok || !payload.ok || !payload.data) throw new Error(payload.error?.message || "Appearance settings could not be saved.");
      accept(payload.data, "Appearance preferences applied.");
    } catch (error) { setMessage({ tone: "error", text: error instanceof Error ? error.message : "Appearance settings could not be saved." }); }
    finally { setWorking(""); }
  };
  const imageRequest = async (kind: "logo" | "background", method: "POST" | "DELETE", file?: File) => {
    setWorking(kind); setMessage(null);
    const selectedTheme = draft.theme;
    try {
      const body: Record<string, unknown> = { expected_revision: settings.summary.revision };
      if (kind === "background") body.theme = draft.theme;
      if (file) {
        if (kind === "background") { const optimized = await optimizeBackground(file); body.file = { name: optimized.name, content_base64: optimized.content_base64 }; body.tone = optimized.tone; }
        else body.file = await readFile(file);
      }
      const response = await fetch(`${bridgeUrl}/api/settings/${kind}`, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const payload = await response.json() as { ok: boolean; data?: SettingsWorkspaceData; error?: { message: string } };
      if (!response.ok || !payload.ok || !payload.data) throw new Error(payload.error?.message || `The ${kind} could not be updated.`);
      accept(payload.data, method === "DELETE" ? `${kind === "logo" ? "Business logo" : "Theme background"} removed.` : `${kind === "logo" ? "Business logo" : "Optimized theme background"} updated.`);
      if (kind === "background" && selectedTheme !== payload.data.appearance.theme) setDraft({ ...normalizeAppearance(payload.data.appearance), theme: selectedTheme });
    } catch (error) { setMessage({ tone: "error", text: error instanceof Error ? error.message : `The ${kind} could not be updated.` }); }
    finally { setWorking(""); if (logoInput.current) logoInput.current.value = ""; if (backgroundInput.current) backgroundInput.current.value = ""; }
  };
  const updateSection = (key: string, field: "visible" | "collapsed", value: boolean) => setDraft((current) => ({ ...current, dashboard_sections: current.dashboard_sections.map((item) => item.key === key ? { ...item, [field]: value } : item) }));
  const moveSection = (key: string, direction: -1 | 1) => setDraft((current) => {
    const sections = [...current.dashboard_sections].sort((left, right) => left.order - right.order);
    const index = sections.findIndex((item) => item.key === key);
    const target = index + direction;
    if (index < 0 || target < 0 || target >= sections.length) return current;
    [sections[index], sections[target]] = [sections[target], sections[index]];
    return { ...current, dashboard_sections: sections.map((item, order) => ({ ...item, order })) };
  });
  const applyDashboardPreset = (preset: "operations" | "finance" | "minimal") => setDraft((current) => {
    const layouts = {
      operations: ["summary_metrics", "priorities", "shortcuts", "goals", "recent_orders", "sales_trend"],
      finance: ["summary_metrics", "sales_trend", "goals", "recent_orders", "priorities", "shortcuts"],
      minimal: ["summary_metrics", "priorities", "recent_orders", "shortcuts", "sales_trend", "goals"],
    } as const;
    const order: readonly string[] = layouts[preset];
    return { ...current, dashboard_sections: current.dashboard_sections.map((item) => {
      const index = order.indexOf(item.key);
      if (index < 0) return item;
      return { ...item, order: index, visible: preset !== "minimal" || ["summary_metrics", "priorities", "recent_orders"].includes(item.key), collapsed: false };
    }) };
  });
  const previewImage = background.custom_available ? `${bridgeUrl}/api/settings/background?theme=${draft.theme}&v=${settings.summary.revision}` : "";
  const previewStyle = previewImage && background.source === "custom" ? { backgroundImage: `url("${previewImage}")`, backgroundSize: background.fit, backgroundPosition: `${background.position_x}% ${background.position_y}%` } : undefined;

  return <article className="settings-card appearance-settings-card" id="settings-appearance">
    <div className="settings-card-heading"><span className="setting-icon violet"><MonitorCog size={19} /></span><div><h2>Appearance & dashboard</h2><p>Preview themes, backgrounds, glass depth, and accessibility</p></div><button className="primary-button setting-save" onClick={() => void save()} disabled={Boolean(working)}><Save size={14} />{working === "save" ? "Applying…" : "Apply appearance"}</button></div>
    {message ? <div className={`settings-feedback ${message.tone}`} role="status"><Check size={15} />{message.text}</div> : null}
    <div className={`appearance-live-preview preview-${draft.theme} preview-glass-${draft.glass_intensity} ${draft.reduce_transparency ? "preview-reduce-transparency" : ""}`}>
      <div className={`preview-backdrop ${background.enabled ? `source-${background.source} preset-${background.preset}` : "source-none"} tone-${background.tone}`} style={previewStyle}><i style={{ opacity: background.enabled ? background.dim / 100 : 1 }} /></div>
      <aside><span>HN</span><b /><b /><b className="active" /><b /></aside><main><header><Eye size={13} /><span>Live workspace preview</span></header><section><article><Sparkles size={16} /><strong>Glass surface</strong><small>Readable over your background</small></article><article><strong>Today</strong><em>24</em><button>Primary action</button></article></section></main>
    </div>
    <div className="appearance-grid expanded">
      <section><h3>Color theme</h3><p className="theme-hint">Select a theme to preview. Apply when it looks right.</p><div className="theme-options">{themes.map((theme) => <label key={theme.value}><input type="radio" name="saved-theme" checked={draft.theme === theme.value} disabled={Boolean(working)} onChange={() => setDraft((current) => ({ ...current, theme: theme.value }))} /><span><i className={`theme-swatch ${theme.value}`} /><strong>{theme.label}</strong><small>{theme.description}</small></span></label>)}</div></section>
      <section className="background-settings"><h3>{themes.find((item) => item.value === draft.theme)?.label} background</h3><p className="theme-hint">Each theme remembers its own image, preset, position, and visibility.</p><label className="setting-check"><input type="checkbox" checked={background.enabled} onChange={(event) => patchBackground({ enabled: event.target.checked })} /><span>Show this theme&apos;s background</span></label><div className="background-source-options"><label><input type="radio" checked={background.source === "none"} onChange={() => patchBackground({ source: "none" })} />None</label><label><input type="radio" checked={background.source === "preset"} onChange={() => patchBackground({ source: "preset", enabled: true })} />Built-in</label><label><input type="radio" checked={background.source === "custom"} disabled={!background.custom_configured} onChange={() => patchBackground({ source: "custom", enabled: true })} />Custom</label></div>{background.source === "preset" ? <div className="background-presets">{presets.map((preset) => <button className={`${preset.value}${background.preset === preset.value ? " selected" : ""}`} onClick={() => patchBackground({ preset: preset.value, enabled: true })} key={preset.value}><i />{preset.label}</button>)}</div> : null}<div className={background.custom_available ? "background-preview has-image" : "background-preview"}>{background.custom_available ? <img src={`${bridgeUrl}/api/settings/background?theme=${draft.theme}&v=${settings.summary.revision}`} alt={`Custom ${draft.theme} background`} /> : <span><ImageIcon size={22} />No image saved for this theme</span>}<i aria-hidden="true" /></div><input ref={backgroundInput} className="visually-hidden" type="file" accept="image/png,image/jpeg,image/webp" onChange={(event) => { const file = event.target.files?.[0]; if (file) void imageRequest("background", "POST", file); }} /><div className="logo-actions"><button className="secondary-button" onClick={() => backgroundInput.current?.click()} disabled={Boolean(working)}><Upload size={14} />{background.custom_configured ? "Replace image" : "Choose image"}</button>{background.custom_configured ? <button className="icon-button payment-remove" aria-label={`Remove ${draft.theme} background image`} onClick={() => void imageRequest("background", "DELETE")} disabled={Boolean(working)}><Trash2 size={15} /></button> : null}</div></section>
      <section className="background-layout-settings"><h3>Background framing</h3><p className="theme-hint">Keep the important part of your image visible behind the workspace.</p><div className="appearance-fields"><label><span>Image fit</span><select value={background.fit} onChange={(event) => patchBackground({ fit: event.target.value as Background["fit"] })}><option value="cover">Fill workspace</option><option value="contain">Fit whole image</option></select></label><label><span>Dim {background.dim}%</span><input type="range" min={0} max={85} value={background.dim} onChange={(event) => patchBackground({ dim: Number(event.target.value) })} /></label></div><label className="range-setting"><span>Horizontal focal point <b>{background.position_x}%</b></span><input type="range" min={0} max={100} value={background.position_x} onChange={(event) => patchBackground({ position_x: Number(event.target.value) })} /></label><label className="range-setting"><span>Vertical focal point <b>{background.position_y}%</b></span><input type="range" min={0} max={100} value={background.position_y} onChange={(event) => patchBackground({ position_y: Number(event.target.value) })} /></label>{background.enabled && background.tone === "light" && background.dim < 55 ? <button type="button" className="contrast-recommendation" onClick={() => patchBackground({ dim: 60 })}><Sparkles size={14} /><span><strong>Improve text contrast</strong><small>This bright image may reduce readability. Apply a 60% overlay.</small></span></button> : null}<small className="optimization-note">Large uploads are resized to 2560 px and compressed to WebP automatically. Brightness is sampled to select a readable overlay.</small></section>
      <section><h3>Glass intensity</h3><p className="theme-hint">Control blur, transparency, glow, and surface depth.</p><div className="segmented-options">{(["subtle", "balanced", "vivid"] as const).map((value) => <label key={value}><input type="radio" checked={draft.glass_intensity === value} onChange={() => setDraft((current) => ({ ...current, glass_intensity: value }))} /><span>{value}</span></label>)}</div><div className="accessibility-options"><label className="setting-check"><input type="checkbox" checked={draft.reduce_transparency} onChange={(event) => setDraft((current) => ({ ...current, reduce_transparency: event.target.checked }))} /><span><strong>Reduce transparency</strong><small>Use more opaque surfaces and remove background blur.</small></span></label><label className="setting-check"><input type="checkbox" checked={draft.reduce_motion} onChange={(event) => setDraft((current) => ({ ...current, reduce_motion: event.target.checked }))} /><span><strong>Reduce motion</strong><small>Disable animated transitions and movement.</small></span></label></div></section>
      <section className="text-size-settings"><h3>Interface text size</h3><p className="theme-hint">Changes apply throughout navigation, cards, forms, and tables.</p><div className="text-size-preview" aria-hidden="true"><strong>Aa</strong><span>Preview text</span></div><div className="text-size-options">{textSizes.map((size) => <label key={size.value}><input type="radio" name="saved-text-size" checked={draft.text_scale === size.value} disabled={Boolean(working)} onChange={() => setDraft((current) => ({ ...current, text_scale: size.value }))} /><span><strong>{size.label}</strong><small>{size.detail}</small></span></label>)}</div></section>
      <section><h3>Business logo</h3><div className={`logo-preview logo-${draft.logo_alignment}`}>{settings.business.logo_available ? <img src={`${bridgeUrl}/api/settings/logo?v=${settings.summary.revision}`} alt="Current business logo" style={{ maxWidth: `${Math.min(draft.logo_size, 180)}px`, maxHeight: `${Math.min(draft.logo_size, 90)}px` }} /> : <span><ImageIcon size={22} />No logo uploaded</span>}</div><input ref={logoInput} className="visually-hidden" type="file" accept="image/png,image/jpeg,image/gif,image/webp" onChange={(event) => { const file = event.target.files?.[0]; if (file) void imageRequest("logo", "POST", file); }} /><div className="logo-actions"><button className="secondary-button" onClick={() => logoInput.current?.click()} disabled={Boolean(working)}><Upload size={14} />{settings.business.logo_configured ? "Replace" : "Upload"}</button>{settings.business.logo_configured ? <button className="icon-button payment-remove" aria-label="Remove business logo" onClick={() => void imageRequest("logo", "DELETE")} disabled={Boolean(working)}><Trash2 size={15} /></button> : null}</div><div className="appearance-fields"><label><span>Alignment</span><select value={draft.logo_alignment} onChange={(event) => setDraft({ ...draft, logo_alignment: event.target.value as Draft["logo_alignment"] })}><option value="top-left">Top left</option><option value="top-center">Top center</option><option value="top-right">Top right</option><option value="bottom-left">Bottom left</option><option value="bottom-center">Bottom center</option><option value="bottom-right">Bottom right</option></select></label><label><span>Desktop size</span><input type="number" min={24} max={1024} value={draft.logo_size} onChange={(event) => setDraft({ ...draft, logo_size: Number(event.target.value) })} /></label></div></section>
    </div>
    <details className="dashboard-section-settings" id="settings-dashboard" open><summary>Customize dashboard</summary><section className="dashboard-customizer-intro"><div><strong>Choose what appears on Home</strong><p>Start with a preset, then reorder, show, hide, or collapse individual dashboard sections.</p></div><button type="button" className="primary-button" onClick={() => void save()} disabled={Boolean(working)}><Save size={14} />{working === "save" ? "Applying…" : "Apply dashboard layout"}</button></section><div className="dashboard-layout-presets" aria-label="Dashboard layout presets"><button type="button" onClick={() => applyDashboardPreset("operations")}>Daily operations</button><button type="button" onClick={() => applyDashboardPreset("finance")}>Finance focus</button><button type="button" onClick={() => applyDashboardPreset("minimal")}>Minimal</button></div><div><strong>Section</strong><strong>Order</strong><strong>Show</strong><strong>Collapse</strong></div>{[...draft.dashboard_sections].sort((left, right) => left.order - right.order).map((section, index, sections) => <label key={section.key}><span>{section.label}</span><span className="dashboard-order-actions"><button type="button" aria-label={`Move ${section.label} up`} disabled={index === 0} onClick={() => moveSection(section.key, -1)}><ArrowUp size={13} /></button><button type="button" aria-label={`Move ${section.label} down`} disabled={index === sections.length - 1} onClick={() => moveSection(section.key, 1)}><ArrowDown size={13} /></button></span><input type="checkbox" aria-label={`Show ${section.label}`} checked={section.visible} onChange={(event) => updateSection(section.key, "visible", event.target.checked)} /><input type="checkbox" aria-label={`Collapse ${section.label}`} checked={section.collapsed} onChange={(event) => updateSection(section.key, "collapsed", event.target.checked)} /></label>)}</details>
  </article>;
}
