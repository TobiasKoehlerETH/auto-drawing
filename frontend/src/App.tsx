import { startTransition, useMemo, useRef, useState } from "react";
import { Loader2, MoveDiagonal, Ruler, SquareStack, Upload } from "lucide-react";

import { DrawingCanvas } from "./components/DrawingCanvas";
import { StepViewer } from "./components/StepViewer";
import { Button } from "./components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./components/ui/card";
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

type DrawingPreview = {
  preview_id: string;
  document: {
    sheet: {
      width_mm: number;
      height_mm: number;
    };
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
  const inputRef = useRef<HTMLInputElement | null>(null);
  const busy = loadingModel || savingPreview;

  const selectedView = useMemo(
    () => preview?.views.find((view) => view.id === selectedViewId) ?? preview?.views[0] ?? null,
    [preview?.views, selectedViewId],
  );

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
      });
      return true;
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to update drawing");
      return false;
    } finally {
      setSavingPreview(false);
    }
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
                  selectedViewId={selectedView?.id ?? null}
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
