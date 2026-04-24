import { startTransition, useEffect, useMemo, useRef, useState } from "react";
import { Loader2, MoveDiagonal, Ruler, SquareStack, Upload } from "lucide-react";

import { DrawingCanvas } from "./components/DrawingCanvas";
import { StepViewer } from "./components/StepViewer";
import { Button } from "./components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./components/ui/card";
import { Input } from "./components/ui/input";
import { Separator } from "./components/ui/separator";
import { importStepBuffer, type ImportResult } from "./lib/occtStepImport";

type LoadedSource = {
  buffer: ArrayBuffer;
  label: string;
  bytes: number;
  imported: ImportResult | null;
  viewerMode: "occt" | "backend-fallback";
};

type DrawingCommand = {
  id: string;
  kind: string;
  target_id: string;
  before: Record<string, unknown>;
  after: Record<string, unknown>;
};

type PreviewViewState = {
  id: string;
  kind: string;
  label: string;
  x_mm: number;
  y_mm: number;
  scale: number;
  width_mm: number;
  height_mm: number;
  selection_bounds_mm: {
    x_min: number;
    y_min: number;
    x_max: number;
    y_max: number;
  };
};

type PreviewTitleBlockField = {
  id: string;
  label: string;
  value: string;
  placement: {
    x_mm: number;
    y_mm: number;
  };
  width_mm: number;
  editable: boolean;
  autofill_key?: string | null;
};

type DrawingPreview = {
  preview_id: string;
  document: {
    sheet: {
      width_mm: number;
      height_mm: number;
    };
    page_template: {
      id: string;
      name: string;
      svg_source: string;
      source_path?: string | null;
      editable_metadata: Record<
        string,
        {
          x_mm: number;
          y_mm: number;
          default_value: string;
          autofill_key?: string | null;
          width_mm?: number | null;
          font_size_mm?: number | null;
          text_anchor?: string | null;
        }
      >;
    };
    title_block_fields: PreviewTitleBlockField[];
    dimensions: Array<{
      id: string;
      view_id: string;
      label: string;
      value: number;
      units: string;
      placement: {
        x_mm: number;
        y_mm: number;
      };
      anchor_a: {
        role: string;
      };
      anchor_b: {
        role: string;
      };
    }>;
  };
  scene_graph: {
    layers: Record<
      string,
      Array<{
        id: string;
        layer: string;
        kind: "rect" | "circle" | "text" | "path";
        group_id?: string | null;
        x?: number | null;
        y?: number | null;
        width?: number | null;
        height?: number | null;
        radius?: number | null;
        path_data?: string | null;
        text?: string | null;
        classes: string[];
        meta: Record<string, unknown>;
      }>
    >;
  };
  views: PreviewViewState[];
  validation: {
    status: string;
    warnings: string[];
    errors: string[];
  };
};

export default function App() {
  const [source, setSource] = useState<LoadedSource | null>(null);
  const [preview, setPreview] = useState<DrawingPreview | null>(null);
  const [selectedViewId, setSelectedViewId] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const [loadingModel, setLoadingModel] = useState(false);
  const [savingPreview, setSavingPreview] = useState(false);
  const [orthographicScaleDraft, setOrthographicScaleDraft] = useState("");
  const [titleBlockDrafts, setTitleBlockDrafts] = useState<Record<string, string>>({});
  const inputRef = useRef<HTMLInputElement | null>(null);
  const autoloadAttemptedRef = useRef(false);
  const lastSyncedTitleBlockValuesRef = useRef<Record<string, string>>({});
  const busy = loadingModel || savingPreview;

  const editableTitleBlockFields = useMemo(
    () => preview?.document.title_block_fields.filter((field) => field.editable) ?? [],
    [preview?.document.title_block_fields],
  );

  const selectedView = useMemo(
    () => {
      if (!preview || !selectedViewId) return null;
      return preview.views.find((view) => view.id === selectedViewId) ?? null;
    },
    [preview?.views, selectedViewId],
  );

  const orthographicViews = useMemo(
    () => preview?.views.filter((view) => view.kind !== "isometric") ?? [],
    [preview?.views],
  );

  const orthographicScale = useMemo(() => {
    if (orthographicViews.length === 0) {
      return null;
    }
    const [first, ...rest] = orthographicViews.map((view) => Number(view.scale.toFixed(4)));
    return rest.every((scale) => scale === first) ? first : null;
  }, [orthographicViews]);

  const changedTitleBlockFields = useMemo(
    () => editableTitleBlockFields.filter((field) => (titleBlockDrafts[field.id] ?? field.value) !== field.value),
    [editableTitleBlockFields, titleBlockDrafts],
  );

  useEffect(() => {
    setOrthographicScaleDraft(orthographicScale === null ? "" : orthographicScale.toFixed(2));
  }, [orthographicScale, preview?.preview_id]);

  useEffect(() => {
    const syncedValues = buildTitleBlockDraftMap(editableTitleBlockFields);
    setTitleBlockDrafts((current) => {
      const next: Record<string, string> = {};
      for (const field of editableTitleBlockFields) {
        const previousSyncedValue = lastSyncedTitleBlockValuesRef.current[field.id];
        const currentDraft = current[field.id];
        const shouldPreserveDraft =
          currentDraft !== undefined && previousSyncedValue !== undefined && currentDraft !== previousSyncedValue && previousSyncedValue === field.value;
        next[field.id] = shouldPreserveDraft ? currentDraft : field.value;
      }
      return sameStringRecord(current, next) ? current : next;
    });
    lastSyncedTitleBlockValuesRef.current = syncedValues;
  }, [editableTitleBlockFields, preview?.preview_id]);

  useEffect(() => {
    if (autoloadAttemptedRef.current || source || preview) {
      return;
    }

    const params = new URLSearchParams(window.location.search);
    const autoload = params.get("autoload");
    if (autoload !== "sample") {
      return;
    }

    autoloadAttemptedRef.current = true;
    setLoadingModel(true);
    setStatus("Loading bundled sample.STEP...");

    void fetch("/sample.STEP")
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`Sample load failed (${response.status})`);
        }
        const buffer = await response.arrayBuffer();
        await createPreview(buffer, "sample.STEP");
      })
      .catch((error: unknown) => {
        setStatus(error instanceof Error ? error.message : "Failed to load bundled sample");
      })
      .finally(() => {
        setLoadingModel(false);
      });
  }, [preview, source]);

  async function handleUpload(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setLoadingModel(true);
    try {
      const isSldprt = /\.sldprt$/i.test(file.name);
      if (isSldprt) {
        setStatus(`Converting ${file.name}...`);
        const form = new FormData();
        form.append("file", file);
        const res = await fetch("/api/convert/sldprt", { method: "POST", body: form });
        if (!res.ok) {
          throw new Error(`Conversion failed (${res.status}): ${await res.text()}`);
        }
        const buffer = await res.arrayBuffer();
        await createPreview(buffer, file.name.replace(/\.sldprt$/i, ".step"));
      } else {
        const buffer = await file.arrayBuffer();
        await createPreview(buffer, file.name);
      }
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to upload model");
    } finally {
      setLoadingModel(false);
      event.target.value = "";
    }
  }

  async function createPreview(buffer: ArrayBuffer, label: string) {
    let imported: ImportResult | null = null;
    let viewerMode: LoadedSource["viewerMode"] = "backend-fallback";
    let response: Response;
    try {
      setStatus(`Triangulating ${label}...`);
      imported = await importStepBuffer(buffer);
      viewerMode = "occt";
      setStatus(`Creating drawing preview for ${label}...`);
      response = await fetch("/api/studio/drawing-preview-from-occt", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_name: label,
          meshes: imported.meshes ?? [],
          units: "mm",
          mode: "final",
        }),
      });
    } catch {
      setStatus(`Creating drawing preview for ${label}...`);
      const file = new File([buffer], label, { type: "application/step" });
      const form = new FormData();
      form.append("file", file);
      response = await fetch("/api/studio/drawing-preview?mode=final", {
        method: "POST",
        body: form,
      });
    }
    if (!response.ok) {
      throw new Error(`Preview failed (${response.status}): ${await response.text()}`);
    }
    const nextPreview: DrawingPreview = await response.json();
    startTransition(() => {
      setSource({ buffer, label, bytes: buffer.byteLength, imported, viewerMode });
      setPreview(nextPreview);
      setSelectedViewId(nextPreview.views[0]?.id ?? null);
      setStatus("");
    });
  }

  async function applyCommands(commands: DrawingCommand[]) {
    if (!preview || commands.length === 0) return false;
    setSavingPreview(true);
    try {
      const endpoint = commands.length === 1 ? "command" : "commands";
      const payload = commands.length === 1 ? { command: commands[0] } : { commands };
      const response = await fetch(`/api/studio/drawing-previews/${preview.preview_id}/${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        throw new Error(`Update failed (${response.status}): ${await response.text()}`);
      }
      const nextPreview: DrawingPreview = await response.json();
      startTransition(() => {
        setPreview(nextPreview);
        setStatus("");
      });
      return true;
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to update drawing");
      return false;
    } finally {
      setSavingPreview(false);
    }
  }

  function resetTitleBlockDrafts() {
    setTitleBlockDrafts(buildTitleBlockDraftMap(editableTitleBlockFields));
  }

  async function applyTitleBlockEdits() {
    if (!preview || changedTitleBlockFields.length === 0) return;
    const timestamp = Date.now();
    const commands = changedTitleBlockFields.map((field, index) => ({
      id: `cmd-title-field-${field.id}-${timestamp}-${index}`,
      kind: "SetTitleBlockField",
      target_id: field.id,
      before: { value: field.value },
      after: { value: titleBlockDrafts[field.id] ?? field.value },
    }));
    await applyCommands(commands);
  }

  async function applyOrthographicScale() {
    if (!preview || orthographicViews.length === 0) return;
    const nextScale = Number.parseFloat(orthographicScaleDraft);
    if (!Number.isFinite(nextScale) || nextScale <= 0) {
      setStatus("Enter a positive scale for the orthographic views.");
      return;
    }
    const timestamp = Date.now();
    const commands = orthographicViews.map((view, index) => ({
      id: `cmd-ortho-scale-${view.id}-${timestamp}-${index}`,
      kind: "ChangeViewScale",
      target_id: view.id,
      before: { scale: view.scale },
      after: { scale: nextScale },
    }));
    await applyCommands(commands);
  }

  return (
    <div className="min-h-screen bg-white text-slate-950">
      <header className="sticky top-0 z-30 border-b border-slate-200/80 bg-white/95 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-[1800px] items-center justify-between gap-4 px-4 lg:px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-950 text-white shadow-sm">
              <SquareStack className="h-4 w-4" />
            </div>
            <div>
              <p className="text-sm font-semibold tracking-[0.18em] text-slate-500 uppercase">TechDraw-Inspired</p>
              <p className="text-base font-semibold">autodrawing canvas</p>
            </div>
          </div>
          {busy ? <Loader2 className="h-4 w-4 animate-spin text-slate-500" /> : null}
        </div>
      </header>

      <div className="mx-auto grid min-h-[calc(100vh-64px)] max-w-[1800px] gap-4 p-4 lg:grid-cols-[310px_minmax(0,1fr)_360px] lg:p-6">
        <aside className="grid gap-4 self-start">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Model</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3">
              <input
                ref={inputRef}
                type="file"
                accept=".step,.stp,.STEP,.STP,.sldprt,.SLDPRT"
                onChange={handleUpload}
                disabled={busy}
                className="hidden"
              />
              <Button onClick={() => inputRef.current?.click()} disabled={busy} className="w-full justify-center">
                {loadingModel ? <Loader2 className="animate-spin" /> : <Upload />}
                {loadingModel ? "Working" : "Upload STEP"}
              </Button>
              {source ? (
                <div className="grid gap-2 rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm">
                  <MetricRow label="Name" value={source.label} />
                  <MetricRow label="Size" value={`${(source.bytes / 1024).toFixed(1)} KB`} />
                </div>
              ) : null}
              {status ? <p className="text-xs text-slate-500">{status}</p> : null}
              {(preview?.validation.warnings ?? []).map((warning) => (
                <p key={warning} className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-900">
                  {warning}
                </p>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Selection</CardTitle>
              <CardDescription>Use the canvas or the buttons below to focus a drawing view.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3">
              <div className="grid gap-2">
                {preview?.views.map((view) => {
                  const active = view.id === selectedView?.id;
                  return (
                    <Button
                      key={view.id}
                      variant={active ? "default" : "outline"}
                      onClick={() => setSelectedViewId(view.id)}
                      aria-label={`Select ${view.kind} view`}
                      className="justify-between"
                    >
                      <span>{view.label}</span>
                      <span className="text-xs opacity-80">{view.kind}</span>
                    </Button>
                  );
                }) ?? <p className="text-sm text-slate-500">Load a model to populate the sheet.</p>}
              </div>

              <div className="grid gap-2 rounded-xl border border-slate-200 bg-slate-50 p-3" data-selected-view-id={selectedView?.id ?? ""}>
                <div className="flex items-center gap-2 text-sm font-medium text-slate-700">
                  <MoveDiagonal className="h-4 w-4" />
                  Selected view
                </div>
                <MetricRow label="Label" value={selectedView?.label ?? "None"} />
                <MetricRow label="X" value={`${selectedView?.x_mm.toFixed(1) ?? "0.0"} mm`} metric="x" />
                <MetricRow label="Y" value={`${selectedView?.y_mm.toFixed(1) ?? "0.0"} mm`} metric="y" />
                <MetricRow label="Scale" value={`${selectedView?.scale.toFixed(2) ?? "0.00"} x`} metric="scale" />
              </div>

              <Separator />

              <div className="grid gap-3 rounded-xl border border-slate-200 bg-slate-50 p-3" data-orthographic-scale-editor>
                <div className="space-y-1">
                  <p className="text-sm font-medium text-slate-700">Orthographic scale</p>
                  <p className="text-xs text-slate-500">Applies to every view except the isometric view.</p>
                </div>
                <MetricRow
                  label="Current"
                  value={orthographicScale === null ? "Mixed" : `${orthographicScale.toFixed(2)} x`}
                  metric="orthographic-scale"
                />
                <div className="flex items-center gap-2">
                  <Input
                    type="number"
                    min="0.1"
                    step="0.05"
                    value={orthographicScaleDraft}
                    onChange={(event) => setOrthographicScaleDraft(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") {
                        event.preventDefault();
                        void applyOrthographicScale();
                      }
                    }}
                    disabled={busy || orthographicViews.length === 0}
                    placeholder="1.00"
                    data-orthographic-scale-input
                  />
                  <Button
                    type="button"
                    onClick={() => void applyOrthographicScale()}
                    disabled={busy || orthographicViews.length === 0 || orthographicScaleDraft.trim().length === 0}
                    data-orthographic-scale-apply
                  >
                    {savingPreview ? <Loader2 className="animate-spin" /> : null}
                    Apply
                  </Button>
                </div>
              </div>

              <Separator />

              <div className="grid gap-3 rounded-xl border border-slate-200 bg-slate-50 p-3" data-title-block-editor>
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-1">
                    <p className="text-sm font-medium text-slate-700">Title block</p>
                    <p className="text-xs text-slate-500">Edit sheet text here instead of typing directly on the canvas.</p>
                  </div>
                  {changedTitleBlockFields.length > 0 ? (
                    <span className="rounded-full bg-amber-100 px-2 py-1 text-[11px] font-semibold text-amber-900">
                      {changedTitleBlockFields.length} pending
                    </span>
                  ) : null}
                </div>

                {editableTitleBlockFields.length > 0 ? (
                  <>
                    <div className="grid max-h-[320px] gap-3 overflow-y-auto pr-1">
                      {editableTitleBlockFields.map((field) => (
                        <label key={field.id} className="grid gap-1.5" data-title-block-field={field.id}>
                          <span className="text-[11px] font-semibold tracking-[0.14em] text-slate-500 uppercase">{field.label}</span>
                          <Input
                            value={titleBlockDrafts[field.id] ?? field.value}
                            onChange={(event) =>
                              setTitleBlockDrafts((current) => ({
                                ...current,
                                [field.id]: event.target.value,
                              }))
                            }
                            onKeyDown={(event) => {
                              if (event.key === "Enter") {
                                event.preventDefault();
                                void applyTitleBlockEdits();
                                return;
                              }
                              if (event.key === "Escape") {
                                event.preventDefault();
                                setTitleBlockDrafts((current) => ({
                                  ...current,
                                  [field.id]: field.value,
                                }));
                              }
                            }}
                            disabled={busy}
                            autoComplete="off"
                            data-title-block-input={field.id}
                          />
                        </label>
                      ))}
                    </div>

                    <div className="flex items-center gap-2">
                      <Button type="button" variant="outline" onClick={resetTitleBlockDrafts} disabled={busy || changedTitleBlockFields.length === 0}>
                        Reset
                      </Button>
                      <Button
                        type="button"
                        className="flex-1 justify-center"
                        onClick={() => void applyTitleBlockEdits()}
                        disabled={busy || changedTitleBlockFields.length === 0}
                        data-title-block-apply
                      >
                        {savingPreview ? <Loader2 className="animate-spin" /> : null}
                        {savingPreview ? "Applying..." : changedTitleBlockFields.length > 1 ? "Apply Title Block Fields" : "Apply Title Block"}
                      </Button>
                    </div>
                  </>
                ) : (
                  <p className="text-sm text-slate-500">Load a drawing with editable title block fields to update them here.</p>
                )}
              </div>
            </CardContent>
          </Card>
        </aside>

        <main className="grid gap-4 self-start">
          <Card className="overflow-hidden border-slate-200/80 bg-white">
            <CardHeader className="border-b border-slate-200/80">
              <CardTitle className="text-base">Drawing</CardTitle>
            </CardHeader>
            <CardContent className="p-4">
              {preview ? (
                <DrawingCanvas
                  preview={preview}
                  selectedViewId={selectedViewId}
                  busy={busy}
                  onSelectView={setSelectedViewId}
                  onApplyCommands={applyCommands}
                />
              ) : (
                <div className="grid h-full min-h-[600px] place-items-center rounded-[28px] border border-dashed border-slate-300 bg-slate-50/80 text-center">
                  <div className="max-w-sm space-y-3 px-6">
                    <Ruler className="mx-auto h-9 w-9 text-slate-400" />
                    <p className="text-lg font-semibold">Load a STEP model to open the sheet canvas.</p>
                    <p className="text-sm text-slate-500">The drawing editor supports box selection, panning, zooming, and direct manipulation on the sheet.</p>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </main>

        <aside className="grid gap-4 self-start">
          <Card className="overflow-hidden">
            <CardHeader>
              <CardTitle className="text-base">3D</CardTitle>
            </CardHeader>
            <CardContent className="h-[720px] p-0">
              <div className="h-full">
                <StepViewer model={source?.imported ?? null} />
              </div>
            </CardContent>
            {source && source.viewerMode === "backend-fallback" ? (
              <div className="border-t border-slate-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                Browser STEP import was not available for this file. The drawing sheet is shown from the backend preview, and the 3D viewer may be blank.
              </div>
            ) : null}
          </Card>
        </aside>
      </div>
    </div>
  );
}

function MetricRow({ label, value, metric }: { label: string; value: string; metric?: string }) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm">
      <span className="text-slate-500">{label}</span>
      <span className="max-w-[180px] truncate font-medium text-slate-900" data-view-metric={metric}>
        {value}
      </span>
    </div>
  );
}

function buildTitleBlockDraftMap(fields: PreviewTitleBlockField[]) {
  return Object.fromEntries(fields.map((field) => [field.id, field.value]));
}

function sameStringRecord(left: Record<string, string>, right: Record<string, string>) {
  const leftKeys = Object.keys(left);
  const rightKeys = Object.keys(right);
  if (leftKeys.length !== rightKeys.length) {
    return false;
  }
  return rightKeys.every((key) => left[key] === right[key]);
}
