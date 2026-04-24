import { useEffect, useMemo, useRef, useState } from "react";
import { Move, ZoomIn, ZoomOut } from "lucide-react";
import { Circle, Group, Image as KonvaImage, Layer, Line, Path, Rect, Stage, Text } from "react-konva";
import type { KonvaEventObject } from "konva/lib/Node";
import type { Stage as KonvaStage } from "konva/lib/Stage";

import { Button } from "./ui/button";

type Bounds2D = {
  x_min: number;
  y_min: number;
  x_max: number;
  y_max: number;
};

type ViewBox = {
  x: number;
  y: number;
  width: number;
  height: number;
};

type Point = {
  x: number;
  y: number;
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
  selection_bounds_mm: Bounds2D;
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

type SceneItem = {
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
    };
    dimensions: PreviewDimension[];
  };
  scene_graph: {
    layers: Record<string, SceneItem[]>;
  };
  views: PreviewViewState[];
};

type DrawingCommand = {
  id: string;
  kind: string;
  target_id: string;
  before: Record<string, unknown>;
  after: Record<string, unknown>;
};

type DrawingCanvasProps = {
  preview: DrawingPreview;
  selectedViewId: string | null;
  busy?: boolean;
  onSelectView: (viewId: string | null) => void;
  onApplyCommands: (commands: DrawingCommand[]) => Promise<boolean> | boolean;
};

type Sheet = DrawingPreview["document"]["sheet"];

type Item =
  | { id: string; type: "view"; view: PreviewViewState }
  | { id: string; type: "dimension"; dimension: PreviewDimension };

type Marquee = { x: number; y: number; width: number; height: number };

type Interaction =
  | null
  | { type: "pan"; startClient: Point; startViewBox: ViewBox }
  | { type: "marquee"; start: Point; current: Point }
  | {
      type: "drag-selection";
      start: Point;
      current: Point;
      targetIds: string[];
      initialPositions: Record<string, Point>;
    };

type CommitDrafts = {
  views: Record<string, PreviewViewState>;
  dimensions: Record<string, PreviewDimension>;
};

type ScreenPoint = {
  x: number;
  y: number;
};

type ScreenRect = {
  x: number;
  y: number;
  width: number;
  height: number;
};

const GRID = 20;
const CANVAS_HEIGHT = 780;

export function DrawingCanvas({ preview, selectedViewId, busy = false, onSelectView, onApplyCommands }: DrawingCanvasProps) {
  const stageRef = useRef<KonvaStage | null>(null);
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const finishingInteractionRef = useRef(false);
  const sheet = preview.document.sheet;
  const [selectedIds, setSelectedIds] = useState<string[]>(selectedViewId ? [selectedViewId] : []);
  const [hoveredDimensionId, setHoveredDimensionId] = useState<string | null>(null);
  const [interaction, setInteraction] = useState<Interaction>(null);
  const [commitDrafts, setCommitDrafts] = useState<CommitDrafts | null>(null);
  const [navigationMode, setNavigationMode] = useState<"select" | "pan">("select");
  const [viewBox, setViewBox] = useState<ViewBox>(() => createSheetViewBox(sheet));
  const [viewportSize, setViewportSize] = useState({ width: 1, height: CANVAS_HEIGHT });

  const sceneLayers = preview.scene_graph.layers;
  const exactTemplateSvg = preview.document.page_template?.svg_source ?? "";
  const hasExactTemplate = Boolean(preview.document.page_template?.source_path && exactTemplateSvg.trim());
  const templateImage = useSvgTemplateImage(hasExactTemplate ? exactTemplateSvg : null);

  useEffect(() => {
    setViewBox(createSheetViewBox(sheet));
    setCommitDrafts(null);
  }, [preview.preview_id, sheet.height_mm, sheet.width_mm]);

  useEffect(() => {
    const node = wrapperRef.current;
    if (!node) return;
    const update = () => {
      setViewportSize({
        width: Math.max(node.clientWidth, 1),
        height: Math.max(node.clientHeight, 1),
      });
    };
    update();
    const observer = new ResizeObserver(update);
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!selectedViewId) {
      setSelectedIds([]);
      return;
    }
    if (!selectedIds.includes(selectedViewId)) {
      setSelectedIds([selectedViewId]);
    }
  }, [selectedIds, selectedViewId]);

  useEffect(() => {
    if (!commitDrafts) return;
    if (previewMatchesCommitDrafts(preview, commitDrafts)) {
      setCommitDrafts(null);
    }
  }, [commitDrafts, preview]);

  const items = useMemo<Item[]>(
    () => [
      ...preview.views.map((view) => ({ id: view.id, type: "view" as const, view })),
      ...preview.document.dimensions.map((dimension) => ({ id: dimension.id, type: "dimension" as const, dimension })),
    ],
    [preview.document.dimensions, preview.views],
  );

  useEffect(() => {
    if (!interaction) return;

    const handleWindowMove = (event: PointerEvent) => {
      const point = worldPointFromClient(event.clientX, event.clientY, wrapperRef.current, viewBox);
      if (!point) return;

      if (interaction.type === "marquee") {
        const next = { ...interaction, current: point };
        setInteraction(next);
        selectByMarquee(normalizeRect(next.start, next.current));
        return;
      }

      if (interaction.type === "drag-selection") {
        setInteraction({ ...interaction, current: point });
        return;
      }

      if (interaction.type === "pan") {
        const node = wrapperRef.current;
        if (!node) return;
        const rect = node.getBoundingClientRect();
        const dxPx = event.clientX - interaction.startClient.x;
        const dyPx = event.clientY - interaction.startClient.y;
        const dx = (dxPx / rect.width) * interaction.startViewBox.width;
        const dy = (dyPx / rect.height) * interaction.startViewBox.height;
        setViewBox(
          clampViewBoxToSheet(
            {
              ...interaction.startViewBox,
              x: interaction.startViewBox.x - dx,
              y: interaction.startViewBox.y - dy,
            },
            sheet,
          ),
        );
      }
    };

    const handleWindowUp = () => {
      void onPointerUp();
    };

    window.addEventListener("pointermove", handleWindowMove);
    window.addEventListener("pointerup", handleWindowUp);
    return () => {
      window.removeEventListener("pointermove", handleWindowMove);
      window.removeEventListener("pointerup", handleWindowUp);
    };
  }, [interaction, preview.views, preview.document.dimensions, sheet.height_mm, sheet.width_mm, viewBox]);

  const marquee = useMemo(() => {
    if (!interaction || interaction.type !== "marquee") return null;
    return normalizeRect(interaction.start, interaction.current);
  }, [interaction]);

  const viewDrafts = useMemo(() => {
    const drafts: Record<string, PreviewViewState> = {};
    if (!interaction || interaction.type !== "drag-selection") {
      return drafts;
    }

    const dx = interaction.current.x - interaction.start.x;
    const dy = interaction.current.y - interaction.start.y;
    for (const view of preview.views) {
      const startPos = interaction.initialPositions[view.id];
      if (!startPos) continue;
      drafts[view.id] = {
        ...view,
        x_mm: round2(startPos.x + dx),
        y_mm: round2(startPos.y + dy),
        selection_bounds_mm: shiftBounds(view.selection_bounds_mm, dx, dy),
      };
    }
    return drafts;
  }, [interaction, preview.views]);

  const dimensionDrafts = useMemo(() => {
    const drafts: Record<string, PreviewDimension> = {};
    if (!interaction || interaction.type !== "drag-selection") {
      return drafts;
    }

    const dx = interaction.current.x - interaction.start.x;
    const dy = interaction.current.y - interaction.start.y;
    for (const dimension of preview.document.dimensions) {
      const startPos = interaction.initialPositions[dimension.id];
      if (!startPos) continue;
      const orientation = getDimensionOrientation(dimension);
      drafts[dimension.id] = {
        ...dimension,
        placement: {
          x_mm: orientation === "vertical" ? round2(startPos.x + dx) : startPos.x,
          y_mm: orientation === "horizontal" ? round2(startPos.y + dy) : startPos.y,
        },
      };
    }
    return drafts;
  }, [interaction, preview.document.dimensions]);

  const renderedViews = useMemo(
    () => preview.views.map((view) => viewDrafts[view.id] ?? commitDrafts?.views[view.id] ?? view),
    [commitDrafts?.views, preview.views, viewDrafts],
  );

  const renderedDimensions = useMemo(
    () => preview.document.dimensions.map((dimension) => dimensionDrafts[dimension.id] ?? commitDrafts?.dimensions[dimension.id] ?? dimension),
    [commitDrafts?.dimensions, dimensionDrafts, preview.document.dimensions],
  );

  const globalItems = useMemo(
    () => [
      ...(hasExactTemplate ? [] : (sceneLayers.frame ?? [])),
      ...(hasExactTemplate ? [] : (sceneLayers.titleBlock ?? [])),
      ...(sceneLayers.notes ?? []).filter((item) => !item.group_id && !item.meta?.view_id),
    ],
    [hasExactTemplate, sceneLayers.frame, sceneLayers.notes, sceneLayers.titleBlock],
  );

  const itemsByView = useMemo(() => {
    const grouped: Record<string, SceneItem[]> = {};
    const layers = [
      ...(sceneLayers.viewGeometryVisible ?? []),
      ...(sceneLayers.viewGeometryHidden ?? []),
      ...(sceneLayers.sectionHatch ?? []),
      ...(sceneLayers.centerlines ?? []),
      ...(sceneLayers.notes ?? []).filter((item) => !!item.group_id || !!item.meta?.view_id),
    ];
    for (const item of layers) {
      const viewId = (item.group_id as string | undefined) ?? (typeof item.meta?.view_id === "string" ? (item.meta.view_id as string) : undefined);
      if (!viewId) continue;
      grouped[viewId] ??= [];
      grouped[viewId].push(item);
    }
    return grouped;
  }, [sceneLayers.centerlines, sceneLayers.notes, sceneLayers.sectionHatch, sceneLayers.viewGeometryHidden, sceneLayers.viewGeometryVisible]);

  const camera = useMemo(() => makeCamera(viewBox, viewportSize), [viewBox, viewportSize]);
  const gridLines = useMemo(() => getGridLines(viewBox), [viewBox]);
  const sheetScreenRect = useMemo(
    () => worldRectToScreen({ x: 0, y: 0, width: sheet.width_mm, height: sheet.height_mm }, camera),
    [camera, sheet.height_mm, sheet.width_mm],
  );

  const viewOverlays = useMemo(
    () =>
      renderedViews.map((view) => ({
        view,
        rect: worldRectToScreen(boundsToRect(view.selection_bounds_mm), camera),
      })),
    [camera, renderedViews],
  );

  const dimensionOverlays = useMemo(
    () =>
      renderedDimensions.map((dimension) => ({
        dimension,
        rect: worldRectToScreen(getDimensionBounds(dimension, renderedViews), camera),
      })),
    [camera, renderedDimensions, renderedViews],
  );

  function itemBounds(item: Item): Marquee {
    if (item.type === "view") {
      return boundsToRect(renderedViews.find((view) => view.id === item.view.id)?.selection_bounds_mm ?? item.view.selection_bounds_mm);
    }
    return getDimensionBounds(renderedDimensions.find((dimension) => dimension.id === item.dimension.id) ?? item.dimension, renderedViews);
  }

  function selectByMarquee(nextMarquee: Marquee) {
    const ids = items.filter((item) => rectsIntersect(nextMarquee, itemBounds(item))).map((item) => item.id);
    setSelectedIds(ids);
    syncSelectedView(ids);
  }

  function syncSelectedView(ids: string[]) {
    const viewId = ids.find((id) => renderedViews.some((view) => view.id === id));
    if (viewId) {
      onSelectView(viewId);
      return;
    }
    const dimension = renderedDimensions.find((candidate) => ids.includes(candidate.id));
    if (dimension) {
      onSelectView(dimension.view_id);
      return;
    }
    onSelectView(null);
  }

  function startPan(clientX: number, clientY: number) {
    setInteraction({ type: "pan", startClient: { x: clientX, y: clientY }, startViewBox: viewBox });
  }

  function shouldStartPan(button: number) {
    return button === 1 || (button === 0 && navigationMode === "pan");
  }

  function zoomViewBox(zoomFactor: number, focusPoint?: Point) {
    setViewBox((current) => {
      const pointer = focusPoint ?? { x: current.x + current.width / 2, y: current.y + current.height / 2 };
      return clampViewBoxToSheet(
        {
          x: pointer.x - (pointer.x - current.x) * zoomFactor,
          y: pointer.y - (pointer.y - current.y) * zoomFactor,
          width: current.width * zoomFactor,
          height: current.height * zoomFactor,
        },
        sheet,
      );
    });
  }

  function zoomFromClientPosition(clientX: number, clientY: number, deltaY: number) {
    const node = wrapperRef.current;
    if (!node) return;
    const rect = node.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return;
    const sx = clamp((clientX - rect.left) / rect.width, 0, 1);
    const sy = clamp((clientY - rect.top) / rect.height, 0, 1);
    const zoomFactor = deltaY < 0 ? 0.9 : 1.1;
    setViewBox((current) => {
      const pointer = {
        x: current.x + sx * current.width,
        y: current.y + sy * current.height,
      };
      return clampViewBoxToSheet(
        {
          x: pointer.x - (pointer.x - current.x) * zoomFactor,
          y: pointer.y - (pointer.y - current.y) * zoomFactor,
          width: current.width * zoomFactor,
          height: current.height * zoomFactor,
        },
        sheet,
      );
    });
  }

  function onBackgroundPointerDown(clientX: number, clientY: number, button: number) {
    if (busy) return;
    if (shouldStartPan(button)) {
      startPan(clientX, clientY);
      return;
    }
    if (button !== 0) return;
    const point = worldPointFromClient(clientX, clientY, wrapperRef.current, viewBox);
    if (!point) return;
    setSelectedIds([]);
    onSelectView(null);
    setInteraction({ type: "marquee", start: point, current: point });
  }

  function beginDragSelection(nextSelected: string[], start: Point) {
    const initialPositions: Record<string, Point> = {};
    for (const id of nextSelected) {
      const view = renderedViews.find((candidate) => candidate.id === id);
      const dimension = renderedDimensions.find((candidate) => candidate.id === id);
      if (view) {
        initialPositions[id] = { x: view.x_mm, y: view.y_mm };
      }
      if (dimension) {
        initialPositions[id] = { x: dimension.placement.x_mm, y: dimension.placement.y_mm };
      }
    }
    setInteraction({ type: "drag-selection", start, current: start, targetIds: nextSelected, initialPositions });
  }

  function onViewPointerDown(clientX: number, clientY: number, button: number, view: PreviewViewState) {
    if (busy) return;
    if (shouldStartPan(button)) {
      startPan(clientX, clientY);
      return;
    }
    if (button !== 0) return;
    const point = worldPointFromClient(clientX, clientY, wrapperRef.current, viewBox);
    if (!point) return;
    const nextSelected = selectedIds.includes(view.id) ? selectedIds : [view.id];
    setSelectedIds(nextSelected);
    onSelectView(view.id);
    beginDragSelection(nextSelected, point);
  }

  function onDimensionPointerDown(clientX: number, clientY: number, button: number, dimension: PreviewDimension) {
    if (busy) return;
    if (shouldStartPan(button)) {
      startPan(clientX, clientY);
      return;
    }
    if (button !== 0) return;
    const point = worldPointFromClient(clientX, clientY, wrapperRef.current, viewBox);
    if (!point) return;
    const nextSelected = selectedIds.includes(dimension.id) ? selectedIds : [dimension.id];
    setSelectedIds(nextSelected);
    onSelectView(dimension.view_id);
    beginDragSelection(nextSelected, point);
  }

  async function onPointerUp() {
    if (!interaction || finishingInteractionRef.current) {
      return;
    }
    finishingInteractionRef.current = true;

    try {
      if (interaction.type === "drag-selection") {
        const commands: DrawingCommand[] = [];
        const nextCommitDrafts: CommitDrafts = { views: {}, dimensions: {} };
        for (const id of interaction.targetIds) {
          const view = preview.views.find((candidate) => candidate.id === id);
          const draftView = renderedViews.find((candidate) => candidate.id === id);
          if (view && draftView && (view.x_mm !== draftView.x_mm || view.y_mm !== draftView.y_mm)) {
            nextCommitDrafts.views[id] = draftView;
            commands.push({
              id: `cmd-move-${id}-${Date.now()}`,
              kind: "MoveView",
              target_id: id,
              before: { x_mm: view.x_mm, y_mm: view.y_mm },
              after: { x_mm: draftView.x_mm, y_mm: draftView.y_mm },
            });
            continue;
          }

          const dimension = preview.document.dimensions.find((candidate) => candidate.id === id);
          const draftDimension = renderedDimensions.find((candidate) => candidate.id === id);
          if (dimension && draftDimension && (dimension.placement.x_mm !== draftDimension.placement.x_mm || dimension.placement.y_mm !== draftDimension.placement.y_mm)) {
            nextCommitDrafts.dimensions[id] = draftDimension;
            commands.push({
              id: `cmd-dimension-${id}-${Date.now()}`,
              kind: "MoveDimensionText",
              target_id: id,
              before: { x_mm: dimension.placement.x_mm, y_mm: dimension.placement.y_mm },
              after: { x_mm: draftDimension.placement.x_mm, y_mm: draftDimension.placement.y_mm },
            });
          }
        }
        setInteraction(null);
        if (commands.length) {
          setCommitDrafts(nextCommitDrafts);
          const applied = await onApplyCommands(commands);
          if (applied === false) {
            setCommitDrafts(null);
          }
        }
        return;
      }

      setInteraction(null);
    } finally {
      finishingInteractionRef.current = false;
    }
  }

  function onWrapperWheel(event: React.WheelEvent<HTMLDivElement>) {
    event.preventDefault();
    event.stopPropagation();
    zoomFromClientPosition(event.clientX, event.clientY, event.deltaY);
  }

  function onStageMouseDown(event: KonvaEventObject<MouseEvent>) {
    if (event.target !== event.target.getStage()) return;
    onBackgroundPointerDown(event.evt.clientX, event.evt.clientY, event.evt.button);
  }

  return (
    <div className="grid gap-4">
      <div
        ref={wrapperRef}
        className={`relative h-[780px] overflow-hidden rounded-2xl border border-slate-200 bg-white ${navigationMode === "pan" ? "cursor-grab" : ""}`}
        onWheelCapture={onWrapperWheel}
      >
        <div className="pointer-events-none absolute right-4 top-4 z-10">
          <div className="pointer-events-auto flex items-center gap-1 rounded-xl border border-slate-200/90 bg-white/95 p-1 shadow-lg backdrop-blur">
            <Button
              type="button"
              size="icon"
              variant={navigationMode === "pan" ? "default" : "outline"}
              aria-label="Pan canvas"
              aria-pressed={navigationMode === "pan"}
              title="Pan canvas"
              onClick={() => setNavigationMode((mode) => (mode === "pan" ? "select" : "pan"))}
            >
              <Move />
            </Button>
            <Button type="button" size="icon" variant="outline" aria-label="Zoom in" title="Zoom in" onClick={() => zoomViewBox(0.9)}>
              <ZoomIn />
            </Button>
            <Button type="button" size="icon" variant="outline" aria-label="Zoom out" title="Zoom out" onClick={() => zoomViewBox(1.1)}>
              <ZoomOut />
            </Button>
          </div>
        </div>

        <Stage ref={stageRef} width={viewportSize.width} height={viewportSize.height} onMouseDown={onStageMouseDown}>
          <Layer listening={false}>
            {gridLines.vertical.map((x) => (
              <Line key={`grid-v-${x}`} points={[x, 0, x, viewportSize.height]} stroke="#e2e8f0" strokeWidth={1} />
            ))}
            {gridLines.horizontal.map((y) => (
              <Line key={`grid-h-${y}`} points={[0, y, viewportSize.width, y]} stroke="#e2e8f0" strokeWidth={1} />
            ))}
            <Rect
              x={sheetScreenRect.x}
              y={sheetScreenRect.y}
              width={sheetScreenRect.width}
              height={sheetScreenRect.height}
              fill="#ffffff"
              stroke={hasExactTemplate ? undefined : "#cbd5e1"}
              strokeWidth={hasExactTemplate ? 0 : 1.2}
            />
            {templateImage ? (
              <KonvaImage
                x={sheetScreenRect.x}
                y={sheetScreenRect.y}
                width={sheetScreenRect.width}
                height={sheetScreenRect.height}
                image={templateImage}
                listening={false}
              />
            ) : null}
          </Layer>

          <Layer listening={false}>
            <Group x={camera.offsetX} y={camera.offsetY} scaleX={camera.scaleX} scaleY={camera.scaleY}>
              {globalItems.map((item) => renderSceneItem(item))}
              {renderedViews.map((view) => {
                const originalView = preview.views.find((candidate) => candidate.id === view.id) ?? view;
                const originalBounds = originalView.selection_bounds_mm;
                const dx = view.selection_bounds_mm.x_min - originalBounds.x_min;
                const dy = view.selection_bounds_mm.y_min - originalBounds.y_min;
                const scaleFactor = originalView.scale > 0 ? view.scale / originalView.scale : 1;
                const groupX = dx + originalBounds.x_min * (1 - scaleFactor);
                const groupY = dy + originalBounds.y_min * (1 - scaleFactor);
                return (
                  <Group key={view.id} x={groupX} y={groupY} scaleX={scaleFactor} scaleY={scaleFactor}>
                    {(itemsByView[view.id] ?? []).map((item) => renderSceneItem(item))}
                  </Group>
                );
              })}
            </Group>
          </Layer>

          <Layer listening={false}>
            {renderedViews.map((view) => {
              const selected = selectedIds.includes(view.id);
              const bounds = worldRectToScreen(boundsToRect(view.selection_bounds_mm), camera);
              if (!selected) return null;
              const selectionPadding = 3;
              return (
                <Rect
                  key={`selection-${view.id}`}
                  x={bounds.x - selectionPadding}
                  y={bounds.y - selectionPadding}
                  width={bounds.width + selectionPadding * 2}
                  height={bounds.height + selectionPadding * 2}
                  cornerRadius={6}
                  stroke="#2563eb"
                  dash={[4, 3]}
                  strokeWidth={1.1}
                />
              );
            })}

            {renderedDimensions.map((dimension) => {
              const bounds = getDimensionBounds(dimension, renderedViews);
              const selected = selectedIds.includes(dimension.id);
              const hovered = hoveredDimensionId === dimension.id;
              return renderDimension(dimension, renderedViews, bounds, selected, hovered, camera);
            })}

            {marquee ? (
              <Rect
                x={worldToScreen({ x: marquee.x, y: marquee.y }, camera).x}
                y={worldToScreen({ x: marquee.x, y: marquee.y }, camera).y}
                width={marquee.width * camera.scaleX}
                height={marquee.height * camera.scaleY}
                fill="#3b82f620"
                stroke="#2563eb"
                dash={[8, 6]}
                strokeWidth={1.5}
              />
            ) : null}

          </Layer>
        </Stage>

        <div className="pointer-events-none absolute inset-0">
          {viewOverlays.map(({ view, rect }) => (
            <div
              key={`overlay-view-${view.id}`}
              data-hitbox-for={view.id}
              className="pointer-events-auto absolute"
              style={{
                left: rect.x,
                top: rect.y,
                width: rect.width,
                height: rect.height,
                cursor: "grab",
                background: "transparent",
              }}
              onPointerDown={(event) => {
                event.stopPropagation();
                onViewPointerDown(event.clientX, event.clientY, event.button, view);
              }}
            />
          ))}

          {dimensionOverlays.map(({ dimension, rect }) => {
            const anchor = getDimensionOverlayAnchor(dimension, renderedViews);
            return (
              <div
                key={`overlay-dimension-${dimension.id}`}
                data-dimension-id={dimension.id}
                data-dimension-x={anchor.x}
                data-dimension-y={anchor.y}
                className="pointer-events-auto absolute"
                style={{
                  left: rect.x,
                  top: rect.y,
                  width: rect.width,
                  height: rect.height,
                  cursor: navigationMode === "pan" ? "grab" : "pointer",
                  background: "transparent",
                }}
                onPointerDown={(event) => {
                  event.stopPropagation();
                  onDimensionPointerDown(event.clientX, event.clientY, event.button, dimension);
                }}
                onPointerEnter={() => setHoveredDimensionId(dimension.id)}
                onPointerLeave={() => setHoveredDimensionId((current) => (current === dimension.id ? null : current))}
              />
            );
          })}
        </div>
      </div>
    </div>
  );
}

function useSvgTemplateImage(svgSource: string | null) {
  const [image, setImage] = useState<HTMLImageElement | null>(null);
  const sanitizedSvgSource = useMemo(() => sanitizeTemplateSvg(svgSource), [svgSource]);
  const dataUrl = useMemo(
    () => (sanitizedSvgSource ? `data:image/svg+xml;charset=utf-8,${encodeURIComponent(sanitizedSvgSource)}` : null),
    [sanitizedSvgSource],
  );

  useEffect(() => {
    if (!dataUrl) {
      setImage(null);
      return;
    }

    const nextImage = new window.Image();
    nextImage.decoding = "async";
    nextImage.onload = () => setImage(nextImage);
    nextImage.onerror = () => setImage(null);
    nextImage.src = dataUrl;

    return () => {
      nextImage.onload = null;
      nextImage.onerror = null;
    };
  }, [dataUrl]);

  return image;
}

function sanitizeTemplateSvg(svgSource: string | null) {
  if (!svgSource?.trim()) {
    return svgSource;
  }

  try {
    const parser = new DOMParser();
    const document = parser.parseFromString(svgSource, "image/svg+xml");

    if (document.querySelector("parsererror")) {
      return stripTrimMarks(svgSource);
    }

    for (const id of ["trimming_marks", "top_left_trimming", "top_right_trimming", "bottom_right_trimming", "bottom_left_trimming"]) {
      document.querySelector(`[id="${id}"]`)?.remove();
    }

    return new XMLSerializer().serializeToString(document);
  } catch {
    return stripTrimMarks(svgSource);
  }
}

function stripTrimMarks(svgSource: string) {
  let sanitized = svgSource.replace(/<g\b[^>]*\bid=(['"])trimming_marks\1[^>]*>[\s\S]*?<\/g>/gi, "");
  for (const id of ["top_left_trimming", "top_right_trimming", "bottom_right_trimming", "bottom_left_trimming"]) {
    sanitized = sanitized.replace(new RegExp(`<[^>]+\\bid=(["'])${id}\\1[^>]*/>`, "gi"), "");
    sanitized = sanitized.replace(new RegExp(`<[^>]+\\bid=(["'])${id}\\1[^>]*>[\\s\\S]*?<\\/[^>]+>`, "gi"), "");
  }
  return sanitized;
}

function renderSceneItem(item: SceneItem) {
  const style = sceneStyle(item.classes);
  if (item.kind === "path") {
    return (
      <Path
        key={item.id}
        data={item.path_data ?? ""}
        stroke={style.stroke}
        strokeWidth={style.strokeWidth}
        fill={style.fill}
        opacity={style.opacity}
        dash={style.dash}
        listening={false}
      />
    );
  }
  if (item.kind === "rect") {
    return (
      <Rect
        key={item.id}
        x={item.x ?? 0}
        y={item.y ?? 0}
        width={item.width ?? 0}
        height={item.height ?? 0}
        stroke={style.stroke}
        strokeWidth={style.strokeWidth}
        fill={style.fill}
        opacity={style.opacity}
        dash={style.dash}
        listening={false}
      />
    );
  }
  if (item.kind === "circle") {
    return (
      <Circle
        key={item.id}
        x={item.x ?? 0}
        y={item.y ?? 0}
        radius={item.radius ?? 0}
        stroke={style.stroke}
        strokeWidth={style.strokeWidth}
        fill={style.fill}
        opacity={style.opacity}
        dash={style.dash}
        listening={false}
      />
    );
  }
  return (
    <Text
      key={item.id}
      x={item.x ?? 0}
      y={item.y ?? 0}
      text={item.text ?? ""}
      fill={style.textFill}
      fontSize={4}
      fontFamily="IBM Plex Sans, Segoe UI, sans-serif"
      listening={false}
    />
  );
}

function renderDimension(
  dimension: PreviewDimension,
  views: PreviewViewState[],
  bounds: Marquee,
  selected: boolean,
  hovered: boolean,
  camera: Camera,
) {
  const view = views.find((candidate) => candidate.id === dimension.view_id);
  if (!view) return null;

  const a = worldToScreen(getAnchorWorld(view, dimension.anchor_a.role), camera);
  const b = worldToScreen(getAnchorWorld(view, dimension.anchor_b.role), camera);
  const horizontal = getDimensionOrientation(dimension) === "horizontal";
  const helperStroke = hovered ? "#60a5fa" : "#64748b";
  const mainStroke = selected ? "#dc2626" : hovered ? "#2563eb" : "#334155";
  const labelStroke = selected ? "#fca5a5" : hovered ? "#93c5fd" : "#cbd5e1";
  const labelFill = hovered ? "#eff6ff" : "white";
  const mainStrokeWidth = selected || hovered ? 1.5 : 1;

  if (horizontal) {
    const y = worldToScreen({ x: 0, y: dimension.placement.y_mm }, camera).y;
    const midX = (a.x + b.x) / 2;
    const labelWidth = 36 * camera.scaleX;
    const labelHeight = 18 * camera.scaleY;
    return (
      <Group key={dimension.id} listening={false}>
        <Line points={[a.x, a.y, a.x, y]} stroke={helperStroke} dash={[4, 4]} strokeWidth={hovered ? 1.2 : 0.8} />
        <Line points={[b.x, b.y, b.x, y]} stroke={helperStroke} dash={[4, 4]} strokeWidth={hovered ? 1.2 : 0.8} />
        <Line points={[a.x, y, b.x, y]} stroke={mainStroke} strokeWidth={mainStrokeWidth} />
        <Line points={[a.x, y, a.x + 8, y - 4, a.x + 8, y + 4, a.x, y]} fill={mainStroke} closed />
        <Line points={[b.x, y, b.x - 8, y - 4, b.x - 8, y + 4, b.x, y]} fill={mainStroke} closed />
        <Rect x={midX - labelWidth / 2} y={y - labelHeight / 2} width={labelWidth} height={labelHeight} cornerRadius={4} fill={labelFill} stroke={labelStroke} strokeWidth={0.9} />
        <Text
          x={midX - labelWidth / 2}
          y={y - labelHeight / 2}
          width={labelWidth}
          height={labelHeight}
          text={dimension.label}
          align="center"
          verticalAlign="middle"
          fontSize={Math.max(6.5 * Math.min(camera.scaleX, camera.scaleY), 12)}
          fontStyle="bold"
          fill={mainStroke}
        />
      </Group>
    );
  }

  const x = worldToScreen({ x: dimension.placement.x_mm, y: 0 }, camera).x;
  const midY = (a.y + b.y) / 2;
  const labelWidth = 36 * camera.scaleX;
  const labelHeight = 18 * camera.scaleY;
  return (
    <Group key={dimension.id} listening={false}>
      <Line points={[a.x, a.y, x, a.y]} stroke={helperStroke} dash={[4, 4]} strokeWidth={hovered ? 1.2 : 0.8} />
      <Line points={[b.x, b.y, x, b.y]} stroke={helperStroke} dash={[4, 4]} strokeWidth={hovered ? 1.2 : 0.8} />
      <Line points={[x, a.y, x, b.y]} stroke={mainStroke} strokeWidth={mainStrokeWidth} />
      <Line points={[x, a.y, x - 4, a.y + 8, x + 4, a.y + 8, x, a.y]} fill={mainStroke} closed />
      <Line points={[x, b.y, x - 4, b.y - 8, x + 4, b.y - 8, x, b.y]} fill={mainStroke} closed />
      <Rect x={x - labelWidth / 2} y={midY - labelHeight / 2} width={labelWidth} height={labelHeight} cornerRadius={4} fill={labelFill} stroke={labelStroke} strokeWidth={0.9} />
      <Text
        x={x - labelWidth / 2}
        y={midY - labelHeight / 2}
        width={labelWidth}
        height={labelHeight}
        text={dimension.label}
        align="center"
        verticalAlign="middle"
        fontSize={Math.max(6.5 * Math.min(camera.scaleX, camera.scaleY), 12)}
        fontStyle="bold"
        fill={mainStroke}
      />
    </Group>
  );
}

type Camera = {
  scaleX: number;
  scaleY: number;
  offsetX: number;
  offsetY: number;
};

function createSheetViewBox(sheet: Sheet): ViewBox {
  return {
    x: 0,
    y: 0,
    width: sheet.width_mm,
    height: sheet.height_mm,
  };
}

function clampViewBoxToSheet(viewBox: ViewBox, sheet: Sheet): ViewBox {
  const width = clamp(viewBox.width, 1, sheet.width_mm);
  const height = clamp(viewBox.height, 1, sheet.height_mm);
  return {
    x: clamp(viewBox.x, 0, Math.max(sheet.width_mm - width, 0)),
    y: clamp(viewBox.y, 0, Math.max(sheet.height_mm - height, 0)),
    width,
    height,
  };
}

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

function makeCamera(viewBox: ViewBox, viewportSize: { width: number; height: number }): Camera {
  const scaleX = viewportSize.width / viewBox.width;
  const scaleY = viewportSize.height / viewBox.height;
  return {
    scaleX,
    scaleY,
    offsetX: -viewBox.x * scaleX,
    offsetY: -viewBox.y * scaleY,
  };
}

function worldToScreen(point: Point, camera: Camera): ScreenPoint {
  return {
    x: point.x * camera.scaleX + camera.offsetX,
    y: point.y * camera.scaleY + camera.offsetY,
  };
}

function worldRectToScreen(rect: Marquee, camera: Camera): ScreenRect {
  const topLeft = worldToScreen({ x: rect.x, y: rect.y }, camera);
  return {
    x: topLeft.x,
    y: topLeft.y,
    width: rect.width * camera.scaleX,
    height: rect.height * camera.scaleY,
  };
}

function worldPointFromClient(clientX: number, clientY: number, node: HTMLDivElement | null, viewBox: ViewBox) {
  if (!node) return null;
  const rect = node.getBoundingClientRect();
  const sx = (clientX - rect.left) / rect.width;
  const sy = (clientY - rect.top) / rect.height;
  return {
    x: viewBox.x + sx * viewBox.width,
    y: viewBox.y + sy * viewBox.height,
  };
}

function normalizeRect(a: Point, b: Point): Marquee {
  return {
    x: Math.min(a.x, b.x),
    y: Math.min(a.y, b.y),
    width: Math.abs(a.x - b.x),
    height: Math.abs(a.y - b.y),
  };
}

function rectsIntersect(a: Marquee, b: Marquee) {
  return a.x < b.x + b.width && a.x + a.width > b.x && a.y < b.y + b.height && a.y + a.height > b.y;
}

function previewMatchesCommitDrafts(preview: DrawingPreview, commitDrafts: CommitDrafts) {
  const viewsMatch = Object.entries(commitDrafts.views).every(([id, draft]) => {
    const previewView = preview.views.find((candidate) => candidate.id === id);
    return previewView && previewView.x_mm === draft.x_mm && previewView.y_mm === draft.y_mm && previewView.scale === draft.scale;
  });

  if (!viewsMatch) {
    return false;
  }

  return Object.entries(commitDrafts.dimensions).every(([id, draft]) => {
    const previewDimension = preview.document.dimensions.find((candidate) => candidate.id === id);
    return previewDimension && previewDimension.placement.x_mm === draft.placement.x_mm && previewDimension.placement.y_mm === draft.placement.y_mm;
  });
}

function shiftBounds(bounds: Bounds2D, dx: number, dy: number): Bounds2D {
  return {
    x_min: bounds.x_min + dx,
    y_min: bounds.y_min + dy,
    x_max: bounds.x_max + dx,
    y_max: bounds.y_max + dy,
  };
}

function boundsToRect(bounds: Bounds2D): Marquee {
  return {
    x: bounds.x_min,
    y: bounds.y_min,
    width: bounds.x_max - bounds.x_min,
    height: bounds.y_max - bounds.y_min,
  };
}

function getDimensionOrientation(dimension: PreviewDimension) {
  const roles = [dimension.anchor_a.role, dimension.anchor_b.role];
  if (roles.some((role) => role.includes("x"))) {
    return "horizontal";
  }
  return "vertical";
}

function getAnchorWorld(view: PreviewViewState, role: string): Point {
  const bounds = view.selection_bounds_mm;
  if (role === "min-x") {
    return { x: bounds.x_min, y: (bounds.y_min + bounds.y_max) / 2 };
  }
  if (role === "max-x") {
    return { x: bounds.x_max, y: (bounds.y_min + bounds.y_max) / 2 };
  }
  if (role === "min-y") {
    return { x: (bounds.x_min + bounds.x_max) / 2, y: bounds.y_max };
  }
  if (role === "max-y") {
    return { x: (bounds.x_min + bounds.x_max) / 2, y: bounds.y_min };
  }
  return { x: (bounds.x_min + bounds.x_max) / 2, y: (bounds.y_min + bounds.y_max) / 2 };
}

function getDimensionBounds(dimension: PreviewDimension, views: PreviewViewState[]): Marquee {
  const view = views.find((candidate) => candidate.id === dimension.view_id);
  if (!view) return { x: 0, y: 0, width: 0, height: 0 };
  const a = getAnchorWorld(view, dimension.anchor_a.role);
  const b = getAnchorWorld(view, dimension.anchor_b.role);

  if (getDimensionOrientation(dimension) === "horizontal") {
    const y = dimension.placement.y_mm;
    return {
      x: Math.min(a.x, b.x),
      y: Math.min(a.y, y) - 10,
      width: Math.abs(a.x - b.x),
      height: Math.abs(y - a.y) + 20,
    };
  }

  const x = dimension.placement.x_mm;
  return {
    x: Math.min(a.x, x) - 10,
    y: Math.min(a.y, b.y),
    width: Math.abs(x - a.x) + 20,
    height: Math.abs(a.y - b.y),
  };
}

function round2(value: number) {
  return Math.round(value * 100) / 100;
}

function getGridLines(viewBox: ViewBox) {
  const minX = Math.floor(viewBox.x / GRID) * GRID;
  const maxX = Math.ceil((viewBox.x + viewBox.width) / GRID) * GRID;
  const minY = Math.floor(viewBox.y / GRID) * GRID;
  const maxY = Math.ceil((viewBox.y + viewBox.height) / GRID) * GRID;
  const vertical: number[] = [];
  const horizontal: number[] = [];
  for (let x = minX; x <= maxX; x += GRID) {
    vertical.push(x);
  }
  for (let y = minY; y <= maxY; y += GRID) {
    horizontal.push(y);
  }
  return { vertical, horizontal };
}

function getDimensionOverlayAnchor(dimension: PreviewDimension, views: PreviewViewState[]) {
  const view = views.find((candidate) => candidate.id === dimension.view_id);
  if (!view) {
    return { x: Number.NaN, y: Number.NaN };
  }
  const a = getAnchorWorld(view, dimension.anchor_a.role);
  const b = getAnchorWorld(view, dimension.anchor_b.role);
  if (getDimensionOrientation(dimension) === "horizontal") {
    return { x: (a.x + b.x) / 2, y: dimension.placement.y_mm };
  }
  return { x: dimension.placement.x_mm, y: (a.y + b.y) / 2 };
}

function sceneStyle(classes: string[]) {
  const has = (name: string) => classes.includes(name);

  if (has("view-isometric-shaded-face")) {
    let fill = "#d9e0ea";
    if (has("iso-face-top")) fill = "#eef2f7";
    if (has("iso-face-front")) fill = "#d8e0eb";
    if (has("iso-face-right")) fill = "#c3cedc";
    return { stroke: undefined, strokeWidth: 0, fill, opacity: 0.88, dash: undefined, textFill: "#122033" };
  }

  if (has("view-label") || has("note") || has("title-block-field")) {
    return { stroke: undefined, strokeWidth: 0, fill: undefined, opacity: 1, dash: undefined, textFill: "#122033" };
  }

  let stroke = "#0f172a";
  let strokeWidth = 0.55;
  let fill: string | undefined;
  let opacity = 1;
  let dash: number[] | undefined;

  if (has("hidden")) {
    dash = [3, 2];
    opacity = 0.72;
  }

  if (has("centerline")) {
    stroke = "#334155";
    dash = [10, 3, 2, 3];
  }

  if (has("sheet-frame") || has("title-block") || has("title-block-grid") || has("projection-symbol")) {
    strokeWidth = 0.7;
  }

  return { stroke, strokeWidth, fill, opacity, dash, textFill: "#122033" };
}
