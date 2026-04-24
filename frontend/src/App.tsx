import { startTransition, useEffect, useMemo, useRef, useState, type ChangeEvent, type CSSProperties, type RefObject } from "react";
import {
  AlertTriangle,
  Box,
  ChevronDown,
  CircleDot,
  FileInput,
  Layers3,
  Loader2,
  Ruler,
  SquareStack,
  Upload,
} from "lucide-react";

import { DrawingCanvas } from "@/components/DrawingCanvas";
import { StepViewer } from "@/components/StepViewer";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Separator } from "@/components/ui/separator";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarRail,
  SidebarSeparator,
  useSidebar,
} from "@/components/ui/sidebar";
import { importStepBuffer, type ImportResult } from "@/lib/occtStepImport";
import { cn } from "@/lib/utils";

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

type CommandApplyOptions = {
  quiet?: boolean;
};

const VIEW_SCALE_OPTIONS = [
  { label: "4:1", value: 4 },
  { label: "2:1", value: 2 },
  { label: "1:1", value: 1 },
  { label: "1:2", value: 0.5 },
  { label: "1:4", value: 0.25 },
];

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

type PreviewDimension = {
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
    title_block_fields: Array<{
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
    }>;
    dimensions: PreviewDimension[];
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

type ScaleState = {
  orthographicViews: PreviewViewState[];
  orthographicScale: number | null;
  isometricView: PreviewViewState | null;
  selectedScaleOption: string;
  selectedScaleLabel: string;
  onApplyOrthographicScale: (nextScale: number) => Promise<void>;
};

export default function App() {
  const [source, setSource] = useState<LoadedSource | null>(null);
  const [preview, setPreview] = useState<DrawingPreview | null>(null);
  const [selectedViewId, setSelectedViewId] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const [loadingModel, setLoadingModel] = useState(false);
  const [savingPreview, setSavingPreview] = useState(false);
  const [drawingToolbarPortal, setDrawingToolbarPortal] = useState<HTMLDivElement | null>(null);
  const [modelViewToolbarPortal, setModelViewToolbarPortal] = useState<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const autoloadAttemptedRef = useRef(false);
  const busy = loadingModel || savingPreview;

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

  const isometricView = useMemo(
    () => preview?.views.find((view) => view.kind === "isometric") ?? null,
    [preview?.views],
  );

  const selectedScaleOption = useMemo(() => {
    if (orthographicScale === null) {
      return orthographicViews.length > 0 ? "mixed" : "1";
    }
    const matchingOption = VIEW_SCALE_OPTIONS.find((option) => Math.abs(option.value - orthographicScale) < 0.0001);
    return matchingOption ? String(matchingOption.value) : "custom";
  }, [orthographicScale, orthographicViews.length]);

  const selectedScaleLabel = useMemo(() => {
    if (selectedScaleOption === "mixed") {
      return "Mixed";
    }
    if (selectedScaleOption === "custom" && orthographicScale !== null) {
      return formatScaleRatio(orthographicScale);
    }
    return VIEW_SCALE_OPTIONS.find((option) => String(option.value) === selectedScaleOption)?.label ?? "1:1";
  }, [orthographicScale, selectedScaleOption]);

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

  async function handleUpload(event: ChangeEvent<HTMLInputElement>) {
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

  async function applyCommands(commands: DrawingCommand[], options: CommandApplyOptions = {}) {
    if (!preview || commands.length === 0) return false;
    if (!options.quiet) {
      setSavingPreview(true);
    }
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
      if (!options.quiet) {
        setSavingPreview(false);
      }
    }
  }

  async function applyOrthographicScale(nextScale: number) {
    if (!preview || orthographicViews.length === 0) return;
    if (!Number.isFinite(nextScale) || nextScale <= 0) {
      setStatus("Choose a valid view scale.");
      return;
    }
    const timestamp = Date.now();
    await applyCommands(
      orthographicViews.map((view, index) => ({
        id: `cmd-ortho-scale-${view.id}-${timestamp}-${index}`,
        kind: "ChangeViewScale",
        target_id: view.id,
        before: { scale: view.scale },
        after: { scale: nextScale },
      })),
    );
  }

  const scaleState: ScaleState = {
    orthographicViews,
    orthographicScale,
    isometricView,
    selectedScaleOption,
    selectedScaleLabel,
    onApplyOrthographicScale: applyOrthographicScale,
  };

  return (
    <SidebarProvider
      className="bg-sidebar"
      style={
        {
          "--sidebar-width": "18rem",
        } as CSSProperties
      }
    >
      <input
        ref={inputRef}
        type="file"
        accept=".step,.stp,.STEP,.STP,.sldprt,.SLDPRT"
        onChange={handleUpload}
        disabled={busy}
        className="hidden"
      />
      <WorkbenchSidebar
        source={source}
        preview={preview}
        status={status}
        busy={busy}
        loadingModel={loadingModel}
        savingPreview={savingPreview}
        inputRef={inputRef}
        scaleState={scaleState}
      />
      <SidebarInset className="min-w-0 overflow-hidden bg-muted/30">
        <div className="flex min-h-0 flex-1 flex-col gap-3 p-3 md:gap-4 md:p-4 xl:grid xl:h-svh xl:grid-cols-[minmax(0,1fr)_minmax(320px,380px)] xl:overflow-hidden">
          <main className="min-w-0 xl:min-h-0">
            <Card className="h-full gap-0 overflow-hidden rounded-[8px] border-border/80 bg-card py-0 shadow-sm">
              <CardHeader className="border-b px-4 py-3 md:px-5">
                <div className="flex min-w-0 items-center justify-between gap-3">
                  <div className="min-w-0">
                    <CardTitle className="truncate text-sm">Drawing Sheet</CardTitle>
                    <CardDescription className="truncate text-xs">
                      {preview
                        ? `${preview.document.sheet.width_mm} x ${preview.document.sheet.height_mm} mm, ${preview.views.length} views`
                        : "Load a STEP model to generate the first sheet"}
                    </CardDescription>
                  </div>
                  <div ref={setDrawingToolbarPortal} className={cn("min-h-8 shrink-0", !preview && "hidden")} />
                </div>
              </CardHeader>
              <CardContent className="min-h-0 flex-1 p-2 md:p-3">
                {preview ? (
                  <DrawingCanvas
                    preview={preview}
                    selectedViewId={selectedViewId}
                    busy={busy}
                    toolbarPortal={drawingToolbarPortal}
                    onSelectView={setSelectedViewId}
                    onApplyCommands={applyCommands}
                  />
                ) : (
                  <EmptyDrawingState onUpload={() => inputRef.current?.click()} busy={busy} />
                )}
              </CardContent>
            </Card>
          </main>

          <aside className="min-w-0 xl:min-h-0 xl:overflow-hidden">
            <Card className="h-full gap-0 overflow-hidden rounded-[8px] border-border/80 bg-card py-0 shadow-sm xl:min-h-0">
              <CardHeader className="border-b px-4 py-3">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <CardTitle className="text-sm">3D Model</CardTitle>
                  </div>
                  <Badge variant="outline" className="rounded-[6px]">
                    <Box className="size-3" />
                    3D
                  </Badge>
                </div>
                <div ref={setModelViewToolbarPortal} className={cn("min-h-8", !source?.imported && "hidden")} />
              </CardHeader>
              <CardContent className="min-h-0 p-0">
                <div className="h-[320px] md:h-[420px] xl:h-full xl:min-h-[360px]">
                  <StepViewer model={source?.imported ?? null} loading={loadingModel} viewToolbarPortal={modelViewToolbarPortal} />
                </div>
              </CardContent>
              {source && source.viewerMode === "backend-fallback" ? (
                <div className="border-t bg-amber-50 px-4 py-3 text-xs text-amber-900">
                  Browser STEP import was not available for this file. The drawing sheet is shown from the backend preview, and the 3D viewer may be blank.
                </div>
              ) : null}
            </Card>
          </aside>
        </div>
      </SidebarInset>
    </SidebarProvider>
  );
}

function WorkbenchSidebar({
  source,
  preview,
  status,
  busy,
  loadingModel,
  savingPreview,
  inputRef,
  scaleState,
}: {
  source: LoadedSource | null;
  preview: DrawingPreview | null;
  status: string;
  busy: boolean;
  loadingModel: boolean;
  savingPreview: boolean;
  inputRef: RefObject<HTMLInputElement | null>;
  scaleState: ScaleState;
}) {
  const { isMobile, toggleSidebar } = useSidebar();
  const warningCount = preview?.validation.warnings.length ?? 0;
  const errorCount = preview?.validation.errors.length ?? 0;

  return (
    <Sidebar collapsible="icon" variant="inset">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              type="button"
              size="lg"
              tooltip="AutoDrawing"
              aria-label="Toggle AutoDrawing sidebar"
              className="gap-3 group-data-[collapsible=icon]:justify-center"
              onClick={toggleSidebar}
            >
              <div className="grid size-8 shrink-0 place-items-center rounded-[8px] bg-primary text-primary-foreground">
                <SquareStack className="size-4" />
              </div>
              <div className="grid min-w-0 flex-1 text-left text-sm leading-tight group-data-[collapsible=icon]:hidden">
                <span className="truncate font-semibold">AutoDrawing</span>
                <span className="truncate text-xs text-sidebar-foreground/60">CAD workbench</span>
              </div>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Workspace</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton
                  type="button"
                  tooltip={loadingModel ? "Uploading model" : "Upload STEP or SLDPRT"}
                  onClick={() => inputRef.current?.click()}
                  disabled={busy}
                  isActive={!source}
                >
                  {loadingModel ? <Loader2 className="animate-spin" /> : <Upload />}
                  <span>{loadingModel ? "Working" : "Upload model"}</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton type="button" tooltip="Drawing sheet" isActive={Boolean(preview)}>
                  <Ruler />
                  <span>Drawing sheet</span>
                  {preview ? <SidebarPill>{preview.views.length}</SidebarPill> : null}
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton type="button" tooltip="Model viewer" isActive={Boolean(source)}>
                  <Layers3 />
                  <span>Model viewer</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton type="button" tooltip="Validation">
                  <AlertTriangle />
                  <span>Validation</span>
                  {warningCount + errorCount > 0 ? <SidebarPill>{warningCount + errorCount}</SidebarPill> : null}
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarSeparator />

        {preview ? (
          <SidebarGroup>
            <SidebarGroupLabel>Scale</SidebarGroupLabel>
            <SidebarGroupContent className="grid gap-2 group-data-[collapsible=icon]:hidden">
              <ScaleControl scaleState={scaleState} busy={busy} savingPreview={savingPreview} />
            </SidebarGroupContent>
          </SidebarGroup>
        ) : null}
      </SidebarContent>
      <SidebarRail />
    </Sidebar>
  );
}

function EmptyDrawingState({ onUpload, busy }: { onUpload: () => void; busy: boolean }) {
  return (
    <div className="grid min-h-[420px] place-items-center rounded-[8px] border border-dashed bg-background text-center md:min-h-[calc(100vh-11rem)]">
      <div className="grid max-w-md gap-4 px-6">
        <div className="mx-auto grid size-12 place-items-center rounded-[8px] border bg-muted">
          <FileInput className="size-5 text-muted-foreground" />
        </div>
        <div className="grid gap-2">
          <p className="text-lg font-semibold">Load a model to open the sheet canvas</p>
          <p className="text-sm text-muted-foreground">
            The editor supports box selection, panning, zooming, linked view movement, title block edits, and direct sheet manipulation.
          </p>
        </div>
        <div className="flex justify-center">
          <Button type="button" className="rounded-[8px]" onClick={onUpload} disabled={busy}>
            {busy ? <Loader2 className="animate-spin" /> : <Upload />}
            Upload model
          </Button>
        </div>
      </div>
    </div>
  );
}

function ScaleControl({
  scaleState,
  busy,
  savingPreview,
}: {
  scaleState: ScaleState;
  busy: boolean;
  savingPreview: boolean;
}) {
  const { orthographicViews, selectedScaleOption, selectedScaleLabel, onApplyOrthographicScale } = scaleState;

  if (orthographicViews.length === 0) {
    return null;
  }

  return (
    <div className="grid gap-2 rounded-[8px] border bg-background p-2" data-orthographic-scale-editor>
      <div className="flex items-center justify-between gap-2 text-xs">
        <span className="font-medium">Scale</span>
      </div>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="w-full justify-between rounded-[8px] bg-background px-3"
            disabled={busy}
            data-orthographic-scale-input
          >
            <span>{selectedScaleLabel}</span>
            <ChevronDown className="size-4 text-muted-foreground" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="w-[var(--radix-dropdown-menu-trigger-width)]">
          <DropdownMenuLabel>View scale</DropdownMenuLabel>
          {(selectedScaleOption === "mixed" || selectedScaleOption === "custom") && (
            <>
              <DropdownMenuRadioGroup value={selectedScaleOption}>
                <DropdownMenuRadioItem value={selectedScaleOption} disabled>
                  {selectedScaleLabel}
                </DropdownMenuRadioItem>
              </DropdownMenuRadioGroup>
              <DropdownMenuSeparator />
            </>
          )}
          <DropdownMenuRadioGroup
            value={selectedScaleOption}
            onValueChange={(value) => {
              const nextScale = Number.parseFloat(value);
              if (Number.isFinite(nextScale)) {
                void onApplyOrthographicScale(nextScale);
              }
            }}
          >
            {VIEW_SCALE_OPTIONS.map((option) => (
              <DropdownMenuRadioItem key={option.label} value={String(option.value)}>
                {option.label}
              </DropdownMenuRadioItem>
            ))}
          </DropdownMenuRadioGroup>
        </DropdownMenuContent>
      </DropdownMenu>
      {savingPreview ? (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Loader2 className="size-3.5 animate-spin" />
          Applying scale
        </div>
      ) : null}
    </div>
  );
}

function StatusNote({ status, busy }: { status: string; busy: boolean }) {
  return (
    <div className="flex items-start gap-2 rounded-[8px] border bg-background p-3 text-xs text-muted-foreground">
      {busy ? <Loader2 className="mt-0.5 size-3.5 shrink-0 animate-spin" /> : <CircleDot className="mt-0.5 size-3.5 shrink-0" />}
      <span className="min-w-0">{status}</span>
    </div>
  );
}

function SidebarPill({ children }: { children: string | number }) {
  return (
    <span className="ml-auto rounded-[6px] border bg-background px-1.5 text-[10px] font-medium text-muted-foreground group-data-[collapsible=icon]:hidden">
      {children}
    </span>
  );
}

function formatScaleRatio(scale: number) {
  if (scale >= 1) {
    return `${formatRatioNumber(scale)}:1`;
  }
  return `1:${formatRatioNumber(1 / scale)}`;
}

function formatRatioNumber(value: number) {
  return Number.isInteger(value) ? String(value) : value.toFixed(2);
}

function MetricRow({ label, value, metric }: { label: string; value: string; metric?: string }) {
  return (
    <div className="flex min-w-0 items-center justify-between gap-3 rounded-[6px] border bg-card px-2.5 py-1.5 text-xs">
      <span className="shrink-0 text-muted-foreground">{label}</span>
      <span className="min-w-0 truncate font-medium text-foreground" data-view-metric={metric}>
        {value}
      </span>
    </div>
  );
}
