import { useEffect, useMemo, useRef, useState } from "react";
import type { PointerEvent as ReactPointerEvent, ReactNode } from "react";
import { createPortal } from "react-dom";
import { Check, CircleDot, Diameter, DraftingCompass, Move, Radius, Ruler, ScanSearch, Trash2, Triangle, X, ZoomIn, ZoomOut } from "lucide-react";
import { Circle, Group, Image as KonvaImage, Layer, Line, Path, Rect, Stage, Text } from "react-konva";
import type { KonvaEventObject } from "konva/lib/Node";
import type { Stage as KonvaStage } from "konva/lib/Stage";

import { Button } from "./ui/button";
import { Input } from "./ui/input";

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

type DimensionType = "Distance" | "DistanceX" | "DistanceY" | "Radius" | "Diameter" | "Angle" | "Angle3Pt";
type DimensionTool = "DistanceX" | "DistanceY" | "Distance" | "Radius" | "Diameter" | "Angle" | "Angle3Pt";

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
  source_ref?: {
    id: string;
    shape_id: string;
    role: string;
    entity_kind?: string;
  };
};

type PreviewDimension = {
  id: string;
  view_id: string;
  label: string;
  value: number;
  units: string;
  dimension_type?: DimensionType;
  measurement_type?: "Projected" | "True";
  references?: string[];
  references_2d?: string[];
  references_3d?: string[];
  computed_geometry?: Record<string, unknown>;
  formatted_text?: string | null;
  format_spec?: string | null;
  placement: {
    x_mm: number;
    y_mm: number;
    user_locked?: boolean;
  };
  anchor_a: {
    view_id?: string;
    primitive_id?: string;
    role: string;
  };
  anchor_b: {
    view_id?: string;
    primitive_id?: string;
    role: string;
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

type TitleBlockFieldMetadata = {
  x_mm?: number | null;
  y_mm?: number | null;
  default_value?: string;
  autofill_key?: string | null;
  width_mm?: number | null;
  font_size_mm?: number | null;
  text_anchor?: string | null;
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
      editable_metadata?: Record<string, TitleBlockFieldMetadata>;
    };
    title_block_fields: PreviewTitleBlockField[];
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

type CommandApplyOptions = {
  quiet?: boolean;
};

type DrawingCanvasProps = {
  preview: DrawingPreview;
  selectedViewId: string | null;
  busy?: boolean;
  toolbarPortal?: HTMLElement | null;
  onSelectView: (viewId: string | null) => void;
  onApplyCommands: (commands: DrawingCommand[], options?: CommandApplyOptions) => Promise<boolean> | boolean;
};

type Sheet = DrawingPreview["document"]["sheet"];

type Item =
  | { id: string; type: "view"; view: PreviewViewState }
  | { id: string; type: "dimension"; dimension: PreviewDimension };

type Marquee = { x: number; y: number; width: number; height: number };
type NavigationMode = "select" | "pan" | "zoom-box";

type Interaction =
  | null
  | { type: "pan"; startClient: Point; startViewBox: ViewBox }
  | { type: "marquee"; start: Point; current: Point }
  | { type: "zoom-box"; start: Point; current: Point }
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

type ActiveTitleBlockEdit = {
  fieldId: string;
  draft: string;
};

type ViewRenderTransform = {
  x: number;
  y: number;
  scale: number;
};

const CANVAS_HEIGHT = 560;
const CANVAS_HEIGHT_STYLE = "clamp(300px, calc(100vh - 220px), 780px)";
const TITLE_BLOCK_FONT_FAMILY = "Segoe UI";
const TITLE_BLOCK_TEXT_GROUP_IDS = ["title_block_labels", "title_block_data_fields"];
const MIN_ZOOM_BOX_WORLD_SIZE = 1;
const ZOOM_BOX_PADDING = 1.05;
const DIMENSION_TEXT_OFFSET_PX = 12;
const RADIAL_TEXT_GAP_PX = 6;
const LINEAR_DIMENSION_OFFSET_MM = 10;
const LINEAR_LABEL_OFFSET_MM = 8;

export function DrawingCanvas({ preview, selectedViewId, busy = false, toolbarPortal, onSelectView, onApplyCommands }: DrawingCanvasProps) {
  const stageRef = useRef<KonvaStage | null>(null);
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const titleBlockInputRef = useRef<HTMLInputElement | null>(null);
  const finishingInteractionRef = useRef(false);
  const sheet = preview.document.sheet;
  const [selectedIds, setSelectedIds] = useState<string[]>(selectedViewId ? [selectedViewId] : []);
  const [hoveredDimensionId, setHoveredDimensionId] = useState<string | null>(null);
  const [hoveredSketchItemId, setHoveredSketchItemId] = useState<string | null>(null);
  const [hoveredTitleBlockFieldId, setHoveredTitleBlockFieldId] = useState<string | null>(null);
  const [activeTitleBlockEdit, setActiveTitleBlockEdit] = useState<ActiveTitleBlockEdit | null>(null);
  const [savingTitleBlockFieldId, setSavingTitleBlockFieldId] = useState<string | null>(null);
  const [interaction, setInteraction] = useState<Interaction>(null);
  const [commitDrafts, setCommitDrafts] = useState<CommitDrafts | null>(null);
  const [titleBlockCommitDrafts, setTitleBlockCommitDrafts] = useState<Record<string, string>>({});
  const [navigationMode, setNavigationMode] = useState<NavigationMode>("select");
  const [viewBox, setViewBox] = useState<ViewBox>(() => createSheetViewBox(sheet));
  const [viewportSize, setViewportSize] = useState({ width: 1, height: CANVAS_HEIGHT });

  const sceneLayers = preview.scene_graph.layers;
  const renderedTitleBlockFields = useMemo(
    () =>
      preview.document.title_block_fields.map((field) =>
        titleBlockCommitDrafts[field.id] === undefined ? field : { ...field, value: titleBlockCommitDrafts[field.id] },
      ),
    [preview.document.title_block_fields, titleBlockCommitDrafts],
  );
  const exactTemplateSvg = useMemo(
    () => applyTitleBlockFieldDraftsToSvg(preview.document.page_template?.svg_source ?? "", renderedTitleBlockFields),
    [preview.document.page_template?.svg_source, renderedTitleBlockFields],
  );
  const hasExactTemplate = Boolean(preview.document.page_template?.source_path && exactTemplateSvg.trim());
  const templateImageKey = useMemo(() => hashString(exactTemplateSvg), [exactTemplateSvg]);
  const templateImage = useSvgTemplateImage(hasExactTemplate ? exactTemplateSvg : null);

  useEffect(() => {
    stageRef.current?.batchDraw();
  }, [exactTemplateSvg, templateImage]);

  useEffect(() => {
    setViewBox(createSheetViewBox(sheet));
    setCommitDrafts(null);
    setTitleBlockCommitDrafts({});
    setActiveTitleBlockEdit(null);
    setSavingTitleBlockFieldId(null);
    setHoveredSketchItemId(null);
  }, [preview.preview_id, sheet.height_mm, sheet.width_mm]);

  useEffect(() => {
    if (!activeTitleBlockEdit) return;
    titleBlockInputRef.current?.focus();
    titleBlockInputRef.current?.select();
  }, [activeTitleBlockEdit?.fieldId]);

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
    const node = wrapperRef.current;
    if (!node) return;

    const handleWheel = (event: WheelEvent) => {
      // Stop the page from scrolling underneath the canvas.
      event.preventDefault();

      // Normalize delta across deltaMode (pixels / lines / pages).
      const lineHeightPx = 16;
      const pageHeightPx = node.clientHeight || 600;
      const deltaPx =
        event.deltaMode === 1
          ? event.deltaY * lineHeightPx
          : event.deltaMode === 2
            ? event.deltaY * pageHeightPx
            : event.deltaY;

      // Smooth exponential zoom; clamp per-event so a fast wheel flick
      // doesn't jump in huge increments. deltaY > 0 (scroll down) => zoom out.
      const rawFactor = Math.pow(1.0015, deltaPx);
      const zoomFactor = Math.min(2, Math.max(0.5, rawFactor));

      const focusPoint = worldPointFromClient(event.clientX, event.clientY, node, viewBox);
      zoomViewBox(zoomFactor, focusPoint ?? undefined);
    };

    node.addEventListener("wheel", handleWheel, { passive: false });
    return () => node.removeEventListener("wheel", handleWheel);
  }, [viewBox, sheet]);

  useEffect(() => {
    setSelectedIds((current) => {
      if (!selectedViewId) {
        return current.length === 0 ? current : [];
      }
      const hasSelectionForView = current.some((id) => {
        if (id === selectedViewId) return true;
        return preview.document.dimensions.some((dimension) => dimension.id === id && dimension.view_id === selectedViewId);
      }) || current.some((id) => sketchItemBelongsToView(id, selectedViewId, sceneLayers));
      if (hasSelectionForView) {
        return current;
      }
      return [selectedViewId];
    });
  }, [preview.document.dimensions, preview.preview_id, sceneLayers, selectedViewId]);

  useEffect(() => {
    if (!commitDrafts) return;
    if (previewMatchesCommitDrafts(preview, commitDrafts)) {
      setCommitDrafts(null);
    }
  }, [commitDrafts, preview]);

  useEffect(() => {
    if (Object.keys(titleBlockCommitDrafts).length === 0) return;
    setTitleBlockCommitDrafts((current) => {
      const next = Object.fromEntries(
        Object.entries(current).filter(([id, value]) => {
          const previewField = preview.document.title_block_fields.find((field) => field.id === id);
          return previewField && previewField.value !== value;
        }),
      );
      return sameStringRecord(current, next) ? current : next;
    });
  }, [preview.document.title_block_fields, titleBlockCommitDrafts]);

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

      if (interaction.type === "marquee" || interaction.type === "zoom-box") {
        const next = { ...interaction, current: point };
        setInteraction(next);
        if (next.type === "marquee") {
          selectByMarquee(normalizeRect(next.start, next.current));
        }
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
        const startCamera = makeCamera(interaction.startViewBox, { width: rect.width, height: rect.height });
        const dx = dxPx / startCamera.scaleX;
        const dy = dyPx / startCamera.scaleY;
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
    if (!interaction || (interaction.type !== "marquee" && interaction.type !== "zoom-box")) return null;
    return {
      mode: interaction.type,
      rect: normalizeRect(interaction.start, interaction.current),
    };
  }, [interaction]);

  const viewDrafts = useMemo(() => {
    const drafts: Record<string, PreviewViewState> = {};
    if (!interaction || interaction.type !== "drag-selection") {
      return drafts;
    }

    const dx = interaction.current.x - interaction.start.x;
    const dy = interaction.current.y - interaction.start.y;
    const primaryViewId = findPrimaryViewId(preview.views);
    const primaryIsDragged = primaryViewId != null && primaryViewId in interaction.initialPositions;

    for (const view of preview.views) {
      const startPos = interaction.initialPositions[view.id];
      if (!startPos) continue;

      let viewDx = dx;
      let viewDy = dy;

      if (!primaryIsDragged) {
        if (view.kind === "right") {
          viewDy = 0;
        } else if ((view.kind === "front" || view.kind === "top") && view.id !== primaryViewId) {
          viewDx = 0;
        }
      }

      drafts[view.id] = {
        ...view,
        x_mm: round2(startPos.x + viewDx),
        y_mm: round2(startPos.y + viewDy),
        selection_bounds_mm: shiftBounds(view.selection_bounds_mm, viewDx, viewDy),
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
      const viewIsDragged = dimension.view_id in interaction.initialPositions;

      // When the parent view is being dragged, translate the dimension by the
      // view's actual delta so it stays anchored to the view (this also
      // respects orthographic linking constraints applied to the view).
      if (viewIsDragged) {
        const previewView = preview.views.find((candidate) => candidate.id === dimension.view_id);
        const draftView = viewDrafts[dimension.view_id];
        if (previewView && draftView) {
          const viewDx = draftView.x_mm - previewView.x_mm;
          const viewDy = draftView.y_mm - previewView.y_mm;
          if (viewDx !== 0 || viewDy !== 0) {
            drafts[dimension.id] = translateDimension(dimension, viewDx, viewDy);
          }
        }
        continue;
      }

      if (startPos) {
        const orientation = getDimensionOrientation(dimension);
        const nextPlacement =
          orientation === "horizontal"
            ? { x_mm: startPos.x, y_mm: round2(startPos.y + dy) }
            : orientation === "vertical"
              ? { x_mm: round2(startPos.x + dx), y_mm: startPos.y }
              : { x_mm: round2(startPos.x + dx), y_mm: round2(startPos.y + dy) };
        drafts[dimension.id] = withDimensionPlacement(dimension, nextPlacement.x_mm, nextPlacement.y_mm);
        continue;
      }

      const previewView = preview.views.find((candidate) => candidate.id === dimension.view_id);
      const draftView = viewDrafts[dimension.view_id];
      if (!previewView || !draftView) {
        continue;
      }

      const viewDx = draftView.x_mm - previewView.x_mm;
      const viewDy = draftView.y_mm - previewView.y_mm;
      if (viewDx !== 0 || viewDy !== 0) {
        drafts[dimension.id] = translateDimension(dimension, viewDx, viewDy);
      }
    }
    return drafts;
  }, [interaction, preview.document.dimensions, preview.views, viewDrafts]);

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

  const titleBlockFieldOverlays = useMemo(
    () =>
      renderedTitleBlockFields
        .filter((field) => field.editable)
        .map((field) => ({
          field,
          rect: worldRectToScreen(getTitleBlockFieldBounds(field, preview.document.page_template.editable_metadata), camera),
        })),
    [camera, preview.document.page_template.editable_metadata, renderedTitleBlockFields],
  );

  const sketchItemsByView = useMemo(() => {
    const grouped: Record<string, SceneItem[]> = {};
    for (const view of renderedViews) {
      grouped[view.id] = (itemsByView[view.id] ?? []).filter(isSelectableSketchItem);
    }
    return grouped;
  }, [itemsByView, renderedViews]);

  const activeTitleBlockField = activeTitleBlockEdit
    ? (renderedTitleBlockFields.find((field) => field.id === activeTitleBlockEdit.fieldId) ?? null)
    : null;

  const activeTitleBlockOverlay = activeTitleBlockEdit
    ? (titleBlockFieldOverlays.find(({ field }) => field.id === activeTitleBlockEdit.fieldId) ?? null)
    : null;

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

  function startZoomBox(clientX: number, clientY: number) {
    const point = worldPointFromClient(clientX, clientY, wrapperRef.current, viewBox);
    if (!point) return;
    setInteraction({ type: "zoom-box", start: point, current: point });
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

  function zoomToWorldRect(rect: Marquee) {
    if (rect.width < MIN_ZOOM_BOX_WORLD_SIZE || rect.height < MIN_ZOOM_BOX_WORLD_SIZE) {
      return;
    }
    setViewBox(fitViewBoxToRect(rect, viewportSize, sheet));
  }

  function onBackgroundPointerDown(clientX: number, clientY: number, button: number) {
    if (busy) return;
    if (shouldStartPan(button)) {
      startPan(clientX, clientY);
      return;
    }
    if (button !== 0) return;
    if (navigationMode === "zoom-box") {
      startZoomBox(clientX, clientY);
      return;
    }
    const point = worldPointFromClient(clientX, clientY, wrapperRef.current, viewBox);
    if (!point) return;
    setSelectedIds([]);
    onSelectView(null);
    setInteraction({ type: "marquee", start: point, current: point });
  }

  function beginDragSelection(dragTargetIds: string[], start: Point) {
    const initialPositions: Record<string, Point> = {};
    for (const id of dragTargetIds) {
      const view = renderedViews.find((candidate) => candidate.id === id);
      const dimension = renderedDimensions.find((candidate) => candidate.id === id);
      if (view) {
        initialPositions[id] = { x: view.x_mm, y: view.y_mm };
      }
      if (dimension) {
        initialPositions[id] = { x: dimension.placement.x_mm, y: dimension.placement.y_mm };
      }
    }
    setInteraction({ type: "drag-selection", start, current: start, targetIds: dragTargetIds, initialPositions });
  }

  function onViewPointerDown(clientX: number, clientY: number, button: number, view: PreviewViewState) {
    if (busy) return;
    if (shouldStartPan(button)) {
      startPan(clientX, clientY);
      return;
    }
    if (button !== 0) return;
    if (navigationMode === "zoom-box") {
      startZoomBox(clientX, clientY);
      return;
    }
    const point = worldPointFromClient(clientX, clientY, wrapperRef.current, viewBox);
    if (!point) return;
    const nextSelected = selectedIds.includes(view.id) ? selectedIds : [view.id];
    const viewDragTargetIds = getViewDragTargetIds(view, nextSelected, renderedViews);
    const viewDragSet = new Set(viewDragTargetIds);
    const attachedDimensionIds = renderedDimensions
      .filter((dimension) => viewDragSet.has(dimension.view_id))
      .map((dimension) => dimension.id);
    const dragTargetIds = [...viewDragTargetIds, ...attachedDimensionIds];
    setSelectedIds(nextSelected);
    onSelectView(view.id);
    beginDragSelection(dragTargetIds, point);
  }

  function onDimensionPointerDown(clientX: number, clientY: number, button: number, dimension: PreviewDimension) {
    if (busy) return;
    if (shouldStartPan(button)) {
      startPan(clientX, clientY);
      return;
    }
    if (button !== 0) return;
    if (navigationMode === "zoom-box") {
      startZoomBox(clientX, clientY);
      return;
    }
    const point = worldPointFromClient(clientX, clientY, wrapperRef.current, viewBox);
    if (!point) return;
    const nextSelected = selectedIds.includes(dimension.id) ? selectedIds : [dimension.id];
    setSelectedIds(nextSelected);
    onSelectView(dimension.view_id);
    beginDragSelection(nextSelected, point);
  }

  function onSketchItemPointerDown(clientX: number, clientY: number, button: number, item: SceneItem) {
    if (busy) return;
    if (shouldStartPan(button)) {
      startPan(clientX, clientY);
      return;
    }
    if (button !== 0) return;
    if (navigationMode === "zoom-box") {
      startZoomBox(clientX, clientY);
      return;
    }
    const viewId = getSceneItemViewId(item);
    setInteraction(null);
    setSelectedIds([item.id]);
    setHoveredSketchItemId(item.id);
    onSelectView(viewId);
  }

  function onTitleBlockFieldPointerDown(clientX: number, clientY: number, button: number, field: PreviewTitleBlockField) {
    if (busy) return;
    if (shouldStartPan(button)) {
      startPan(clientX, clientY);
      return;
    }
    if (button !== 0) return;
    if (navigationMode === "zoom-box") {
      startZoomBox(clientX, clientY);
      return;
    }
    setInteraction(null);
    setSelectedIds([]);
    onSelectView(null);
    setActiveTitleBlockEdit({ fieldId: field.id, draft: field.value });
  }

  async function applyTitleBlockFieldEdit() {
    if (!activeTitleBlockEdit || !activeTitleBlockField || busy || savingTitleBlockFieldId) return;
    const nextValue = activeTitleBlockEdit.draft;
    if (nextValue === activeTitleBlockField.value) {
      setActiveTitleBlockEdit(null);
      return;
    }
    const persistedField = preview.document.title_block_fields.find((field) => field.id === activeTitleBlockField.id);
    setTitleBlockCommitDrafts((current) => ({ ...current, [activeTitleBlockField.id]: nextValue }));
    setSavingTitleBlockFieldId(activeTitleBlockField.id);
    const applied = await onApplyCommands(
      [
        {
          id: `cmd-title-field-${activeTitleBlockField.id}-${Date.now()}`,
          kind: "SetTitleBlockField",
          target_id: activeTitleBlockField.id,
          before: { value: persistedField?.value ?? activeTitleBlockField.value },
          after: { value: nextValue },
        },
      ],
      { quiet: true },
    );
    if (applied !== false) {
      setActiveTitleBlockEdit(null);
    } else {
      setTitleBlockCommitDrafts((current) => {
        const next = { ...current };
        delete next[activeTitleBlockField.id];
        return next;
      });
    }
    setSavingTitleBlockFieldId(null);
  }

  async function createDimensionFromTool(tool: DimensionTool) {
    if (busy) return;
    const viewId = selectedIds.find((id) => renderedViews.some((view) => view.id === id)) ?? selectedViewId ?? renderedViews.find((view) => view.kind !== "isometric")?.id;
    const view = renderedViews.find((candidate) => candidate.id === viewId);
    if (!view) return;
    const dimension = buildDimensionFromTool(tool, view, sceneLayers);
    if (!dimension) return;
    const applied = await onApplyCommands([
      {
        id: `cmd-create-${dimension.id}-${Date.now()}`,
        kind: "CreateDimension",
        target_id: dimension.id,
        before: {},
        after: { dimension },
      },
    ]);
    if (applied !== false) {
      setSelectedIds([dimension.id]);
      onSelectView(dimension.view_id);
    }
  }

  async function deleteSelectedDimensions() {
    if (busy) return;
    const dimensions = renderedDimensions.filter((dimension) => selectedIds.includes(dimension.id));
    if (!dimensions.length) return;
    const applied = await onApplyCommands(
      dimensions.map((dimension) => ({
        id: `cmd-delete-${dimension.id}-${Date.now()}`,
        kind: "DeleteDimension",
        target_id: dimension.id,
        before: { dimension },
        after: {},
      })),
    );
    if (applied !== false) {
      setSelectedIds([]);
    }
  }

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Delete" && event.key !== "Backspace") return;
      if (busy || activeTitleBlockEdit) return;
      if (isEditableKeyboardTarget(event.target)) return;
      if (!selectedIds.some((id) => renderedDimensions.some((dimension) => dimension.id === id))) return;

      event.preventDefault();
      void deleteSelectedDimensions();
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [activeTitleBlockEdit, busy, renderedDimensions, selectedIds]);

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
          for (const dimension of renderedDimensions) {
            const previewDimension = preview.document.dimensions.find((candidate) => candidate.id === dimension.id);
            if (!previewDimension) {
              continue;
            }
            if (
              previewDimension.placement.x_mm !== dimension.placement.x_mm ||
              previewDimension.placement.y_mm !== dimension.placement.y_mm
            ) {
              nextCommitDrafts.dimensions[dimension.id] = dimension;
            }
          }
          setCommitDrafts(nextCommitDrafts);
          const applied = await onApplyCommands(commands);
          if (applied === false) {
            setCommitDrafts(null);
          }
        }
        return;
      }

      if (interaction.type === "zoom-box") {
        zoomToWorldRect(normalizeRect(interaction.start, interaction.current));
        setInteraction(null);
        return;
      }

      setInteraction(null);
    } finally {
      finishingInteractionRef.current = false;
    }
  }

  function onStageMouseDown(event: KonvaEventObject<MouseEvent>) {
    if (event.target !== event.target.getStage()) return;
    onBackgroundPointerDown(event.evt.clientX, event.evt.clientY, event.evt.button);
  }

  const selectedDimensionCount = selectedIds.filter((id) => renderedDimensions.some((dimension) => dimension.id === id)).length;
  const dimensionTools: Array<{ tool: DimensionTool; label: string; icon: ReactNode }> = [
    { tool: "DistanceX", label: "Horizontal dimension", icon: <Ruler /> },
    { tool: "DistanceY", label: "Vertical dimension", icon: <Ruler className="rotate-90" /> },
    { tool: "Distance", label: "Aligned dimension", icon: <DraftingCompass /> },
    { tool: "Diameter", label: "Diameter dimension", icon: <Diameter /> },
    { tool: "Radius", label: "Radius dimension", icon: <Radius /> },
    { tool: "Angle", label: "Angle dimension", icon: <Triangle /> },
    { tool: "Angle3Pt", label: "3-point angle dimension", icon: <CircleDot /> },
  ];

  const toolbar = (
    <div className="flex items-center gap-1 rounded-[8px] border bg-background/95 p-1 shadow-sm backdrop-blur">
      <Button
        type="button"
        size="icon-sm"
        variant={navigationMode === "pan" ? "default" : "outline"}
        aria-label="Pan canvas"
        aria-pressed={navigationMode === "pan"}
        title="Pan canvas"
        onClick={() => setNavigationMode((mode) => (mode === "pan" ? "select" : "pan"))}
      >
        <Move />
      </Button>
      <Button
        type="button"
        size="icon-sm"
        variant={navigationMode === "zoom-box" ? "default" : "outline"}
        aria-label="Zoom to rectangle"
        aria-pressed={navigationMode === "zoom-box"}
        title="Zoom to rectangle"
        onClick={() => setNavigationMode((mode) => (mode === "zoom-box" ? "select" : "zoom-box"))}
      >
        <ScanSearch />
      </Button>
      <Button type="button" size="icon-sm" variant="outline" aria-label="Zoom in" title="Zoom in" onClick={() => zoomViewBox(0.9)}>
        <ZoomIn />
      </Button>
      <Button type="button" size="icon-sm" variant="outline" aria-label="Zoom out" title="Zoom out" onClick={() => zoomViewBox(1.1)}>
        <ZoomOut />
      </Button>
      <div className="mx-1 h-6 w-px bg-border" />
      {dimensionTools.map((tool) => (
        <Button
          key={tool.tool}
          type="button"
          size="icon-sm"
          variant="outline"
          aria-label={tool.label}
          title={tool.label}
          disabled={busy}
          onClick={() => void createDimensionFromTool(tool.tool)}
        >
          {tool.icon}
        </Button>
      ))}
      <Button
        type="button"
        size="icon-sm"
        variant="outline"
        aria-label="Delete selected dimensions"
        title="Delete selected dimensions"
        disabled={busy || selectedDimensionCount === 0}
        onClick={() => void deleteSelectedDimensions()}
      >
        <Trash2 />
      </Button>
    </div>
  );

  return (
    <div className="grid min-h-0 gap-4">
      {toolbarPortal ? createPortal(toolbar, toolbarPortal) : null}
      <div
        ref={wrapperRef}
        data-preview-id={preview.preview_id}
        className={`relative overflow-hidden rounded-[8px] border bg-white ${
          navigationMode === "pan" ? "cursor-grab" : navigationMode === "zoom-box" ? "cursor-crosshair" : ""
        }`}
        style={{ height: CANVAS_HEIGHT_STYLE }}
      >
        {!toolbarPortal ? <div className="pointer-events-auto absolute right-3 top-3 z-10">{toolbar}</div> : null}

        <Stage ref={stageRef} width={viewportSize.width} height={viewportSize.height} onMouseDown={onStageMouseDown}>
          <Layer listening={false}>
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
                key={`template-${templateImageKey}`}
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
                const transform = getViewRenderTransform(view, originalView);
                return (
                  <Group key={view.id} x={transform.x} y={transform.y} scaleX={transform.scale} scaleY={transform.scale}>
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
                x={worldToScreen({ x: marquee.rect.x, y: marquee.rect.y }, camera).x}
                y={worldToScreen({ x: marquee.rect.x, y: marquee.rect.y }, camera).y}
                width={marquee.rect.width * camera.scaleX}
                height={marquee.rect.height * camera.scaleY}
                fill={marquee.mode === "zoom-box" ? "#0f172a14" : "#3b82f620"}
                stroke={marquee.mode === "zoom-box" ? "#0f172a" : "#2563eb"}
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
              data-view-kind={view.kind}
              data-view-x-mm={view.x_mm}
              data-view-y-mm={view.y_mm}
              className="pointer-events-auto absolute"
              style={{
                left: rect.x,
                top: rect.y,
                width: rect.width,
                height: rect.height,
                cursor: navigationMode === "zoom-box" ? "crosshair" : "grab",
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
                  cursor: navigationMode === "zoom-box" ? "crosshair" : navigationMode === "pan" ? "grab" : "pointer",
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

          <svg
            className="pointer-events-none absolute inset-0"
            width={viewportSize.width}
            height={viewportSize.height}
            aria-hidden="true"
          >
            <g transform={`matrix(${camera.scaleX} 0 0 ${camera.scaleY} ${camera.offsetX} ${camera.offsetY})`}>
              {renderedViews.map((view) => {
                const originalView = preview.views.find((candidate) => candidate.id === view.id) ?? view;
                const transform = getViewRenderTransform(view, originalView);
                return (
                  <g key={`sketch-hit-group-${view.id}`} transform={`translate(${transform.x} ${transform.y}) scale(${transform.scale})`}>
                    {(sketchItemsByView[view.id] ?? []).map((item) => {
                      const selected = selectedIds.includes(item.id);
                      const hovered = hoveredSketchItemId === item.id;
                      return (
                        <SketchItemHitTarget
                          key={`sketch-hit-${item.id}`}
                          item={item}
                          hovered={hovered}
                          selected={selected}
                          cursor={navigationMode === "zoom-box" ? "crosshair" : navigationMode === "pan" ? "grab" : "pointer"}
                          onPointerDown={(event) => {
                            event.stopPropagation();
                            onSketchItemPointerDown(event.clientX, event.clientY, event.button, item);
                          }}
                          onPointerEnter={() => setHoveredSketchItemId(item.id)}
                          onPointerLeave={() => setHoveredSketchItemId((current) => (current === item.id ? null : current))}
                        />
                      );
                    })}
                  </g>
                );
              })}
            </g>
          </svg>

          {titleBlockFieldOverlays.map(({ field, rect }) => {
            const active = activeTitleBlockEdit?.fieldId === field.id;
            const hovered = hoveredTitleBlockFieldId === field.id;
            return (
              <button
                key={`overlay-title-block-${field.id}`}
                type="button"
                data-title-block-hitbox={field.id}
                className={`pointer-events-auto absolute rounded-[3px] border text-left transition-colors ${
                  active
                    ? "border-blue-500 bg-blue-500/10"
                    : hovered
                      ? "border-blue-400 bg-blue-400/10"
                      : "border-transparent bg-transparent"
                }`}
                style={{
                  left: rect.x,
                  top: rect.y,
                  width: Math.max(rect.width, 18),
                  height: Math.max(rect.height, 14),
                  cursor: navigationMode === "zoom-box" ? "crosshair" : navigationMode === "pan" ? "grab" : "text",
                }}
                aria-label={`Edit ${field.label}`}
                title={`Edit ${field.label}`}
                disabled={busy}
                onPointerDown={(event) => {
                  event.stopPropagation();
                  onTitleBlockFieldPointerDown(event.clientX, event.clientY, event.button, field);
                }}
                onPointerEnter={() => setHoveredTitleBlockFieldId(field.id)}
                onPointerLeave={() => setHoveredTitleBlockFieldId((current) => (current === field.id ? null : current))}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    setActiveTitleBlockEdit({ fieldId: field.id, draft: field.value });
                  }
                }}
              />
            );
          })}
        </div>

        {activeTitleBlockEdit && activeTitleBlockField && activeTitleBlockOverlay ? (
          <div
            className="absolute z-20 rounded-lg border border-slate-200 bg-white p-2 shadow-xl"
            style={getTitleBlockPopupStyle(activeTitleBlockOverlay.rect, viewportSize)}
            data-title-block-popup={activeTitleBlockField.id}
            onPointerDown={(event) => event.stopPropagation()}
            onWheel={(event) => event.stopPropagation()}
          >
            <p className="mb-1.5 truncate text-xs font-medium text-slate-500">{activeTitleBlockField.label}</p>
            <div className="flex items-center gap-1">
              <Input
                ref={titleBlockInputRef}
                value={activeTitleBlockEdit.draft}
                disabled={busy || savingTitleBlockFieldId === activeTitleBlockField.id}
                autoComplete="off"
                className="h-8 min-w-0 flex-1 text-sm"
                data-title-block-popup-input={activeTitleBlockField.id}
                onChange={(event) => setActiveTitleBlockEdit((current) => (current ? { ...current, draft: event.target.value } : current))}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    void applyTitleBlockFieldEdit();
                  }
                  if (event.key === "Escape") {
                    event.preventDefault();
                    setActiveTitleBlockEdit(null);
                  }
                }}
              />
              <Button
                type="button"
                size="icon"
                className="size-8 shrink-0"
                onClick={() => void applyTitleBlockFieldEdit()}
                disabled={busy || savingTitleBlockFieldId === activeTitleBlockField.id || activeTitleBlockEdit.draft === activeTitleBlockField.value}
                aria-label="Apply"
                data-title-block-popup-apply={activeTitleBlockField.id}
              >
                <Check className="size-4" />
              </Button>
              <Button
                type="button"
                size="icon"
                variant="ghost"
                className="size-8 shrink-0"
                aria-label="Close title block editor"
                onClick={() => setActiveTitleBlockEdit(null)}
              >
                <X className="size-4" />
              </Button>
            </div>
          </div>
        ) : null}
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

function applyTitleBlockFieldDraftsToSvg(svgSource: string, fields: PreviewTitleBlockField[]) {
  if (!svgSource.trim() || fields.length === 0) {
    return applyTitleBlockFontToSvg(svgSource);
  }

  try {
    const parser = new DOMParser();
    const document = parser.parseFromString(svgSource, "image/svg+xml");

    if (document.querySelector("parsererror")) {
      return svgSource;
    }

    const valuesByEditableName = new Map(fields.map((field) => [editableNameFromTitleBlockFieldId(field.id), field.value]));
    let changed = false;

    for (const element of Array.from(document.querySelectorAll("text"))) {
      const editableName = element.getAttribute("freecad:editable") ?? element.getAttributeNS("http://www.freecad.org/wiki/index.php?title=Svg_Namespace", "editable");
      if (!editableName || !valuesByEditableName.has(editableName)) {
        continue;
      }

      let tspan = element.querySelector("tspan");
      if (!tspan) {
        tspan = document.createElementNS("http://www.w3.org/2000/svg", "tspan");
        element.appendChild(tspan);
      }
      const nextText = valuesByEditableName.get(editableName) ?? "";
      if (tspan.textContent !== nextText) {
        tspan.textContent = nextText;
        changed = true;
      }
    }

    const fontChanged = applyTitleBlockFontToDocument(document);
    return changed || fontChanged ? new XMLSerializer().serializeToString(document) : svgSource;
  } catch {
    return applyTitleBlockFontToSvg(svgSource);
  }
}

function editableNameFromTitleBlockFieldId(fieldId: string) {
  return fieldId.startsWith("tb-") ? fieldId.slice(3) : fieldId;
}

function applyTitleBlockFontToSvg(svgSource: string) {
  if (!svgSource.trim()) {
    return svgSource;
  }

  try {
    const parser = new DOMParser();
    const document = parser.parseFromString(svgSource, "image/svg+xml");
    if (document.querySelector("parsererror")) {
      return svgSource;
    }
    return applyTitleBlockFontToDocument(document) ? new XMLSerializer().serializeToString(document) : svgSource;
  } catch {
    return svgSource;
  }
}

function applyTitleBlockFontToDocument(document: Document) {
  let changed = false;
  for (const id of TITLE_BLOCK_TEXT_GROUP_IDS) {
    const element = document.getElementById(id);
    if (!element) continue;
    const currentStyle = element.getAttribute("style") ?? "";
    const nextStyle = setStyleValue(currentStyle, "font-family", TITLE_BLOCK_FONT_FAMILY);
    if (nextStyle !== currentStyle) {
      element.setAttribute("style", nextStyle);
      changed = true;
    }
  }
  return changed;
}

function setStyleValue(style: string, key: string, value: string) {
  const entries = style
    .split(";")
    .map((entry) => entry.trim())
    .filter(Boolean)
    .map((entry) => entry.split(":"));
  const styles = new Map(entries.filter((entry) => entry.length >= 2).map(([styleKey, ...styleValue]) => [styleKey.trim(), styleValue.join(":").trim()]));
  styles.set(key, value);
  return Array.from(styles.entries())
    .map(([styleKey, styleValue]) => `${styleKey}:${styleValue}`)
    .join(";");
}

function hashString(value: string) {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) | 0;
  }
  return hash.toString(36);
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

function SketchItemHitTarget({
  item,
  hovered,
  selected,
  cursor,
  onPointerDown,
  onPointerEnter,
  onPointerLeave,
}: {
  item: SceneItem;
  hovered: boolean;
  selected: boolean;
  cursor: string;
  onPointerDown: (event: ReactPointerEvent<SVGElement>) => void;
  onPointerEnter: () => void;
  onPointerLeave: () => void;
}) {
  const active = hovered || selected;
  const highlightStroke = selected ? "#dc2626" : "#2563eb";

  return (
    <g
      data-sketch-item-id={item.id}
      data-sketch-view-id={getSceneItemViewId(item) ?? ""}
      data-sketch-hovered={hovered ? "true" : "false"}
      data-sketch-selected={selected ? "true" : "false"}
    >
      {active ? renderSvgSketchItem(item, highlightStroke, selected ? 2.8 : 2.3, "none") : null}
      {renderSvgSketchItem(item, "transparent", 12, "stroke", {
        cursor,
        onPointerDown,
        onPointerEnter,
        onPointerLeave,
        "data-sketch-hitbox": item.id,
      })}
    </g>
  );
}

function renderSvgSketchItem(
  item: SceneItem,
  stroke: string,
  strokeWidth: number,
  pointerEvents: "none" | "stroke",
  eventProps: Record<string, unknown> = {},
) {
  const commonProps = {
    stroke,
    strokeWidth,
    fill: "none",
    vectorEffect: "non-scaling-stroke" as const,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    pointerEvents,
    ...eventProps,
  };

  if (item.kind === "path") {
    return <path d={item.path_data ?? ""} {...commonProps} />;
  }
  if (item.kind === "rect") {
    return <rect x={item.x ?? 0} y={item.y ?? 0} width={item.width ?? 0} height={item.height ?? 0} {...commonProps} />;
  }
  if (item.kind === "circle") {
    return <circle cx={item.x ?? 0} cy={item.y ?? 0} r={item.radius ?? 0} {...commonProps} />;
  }
  return null;
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
  const geometry = dimension.computed_geometry ?? {};
  const helperStroke = hovered ? "#60a5fa" : "#64748b";
  const mainStroke = selected ? "#dc2626" : hovered ? "#2563eb" : "#334155";
  const mainStrokeWidth = selected || hovered ? 1.5 : 1;
  const label = geometryPoint(geometry["label"]) ?? { x: dimension.placement.x_mm, y: dimension.placement.y_mm };
  const labelScreen = worldToScreen(label, camera);
  const text = dimension.formatted_text || dimension.label;
  const labelWidth = Math.max(34 * camera.scaleX, 42, text.length * 6.4);
  const labelHeight = Math.max(9 * camera.scaleY, 18);

  if (geometry["kind"] === "linear") {
    const extensionStart = geometryPoint(geometry["extension_start"]);
    const extensionEnd = geometryPoint(geometry["extension_end"]);
    const lineStart = geometryPoint(geometry["line_start"]);
    const lineEnd = geometryPoint(geometry["line_end"]);
    if (extensionStart && extensionEnd && lineStart && lineEnd) {
      const extStart = worldToScreen(extensionStart, camera);
      const extEnd = worldToScreen(extensionEnd, camera);
      const a = worldToScreen(lineStart, camera);
      const b = worldToScreen(lineEnd, camera);
      const labelAnchor = offsetDimensionLabel(labelScreen, a, b);
      return (
        <Group key={dimension.id} listening={false}>
          <Line points={[extStart.x, extStart.y, a.x, a.y]} stroke={helperStroke} dash={[4, 4]} strokeWidth={hovered ? 1.2 : 0.8} />
          <Line points={[extEnd.x, extEnd.y, b.x, b.y]} stroke={helperStroke} dash={[4, 4]} strokeWidth={hovered ? 1.2 : 0.8} />
          <Line points={[a.x, a.y, b.x, b.y]} stroke={mainStroke} strokeWidth={mainStrokeWidth} />
          {renderArrowHead(a, b, mainStroke)}
          {renderArrowHead(b, a, mainStroke)}
          {renderDimensionLabel(labelAnchor, labelWidth, labelHeight, text, mainStroke)}
        </Group>
      );
    }
  }

  if (geometry["kind"] === "radial") {
    const anchor = geometryPoint(geometry["anchor"]);
    if (anchor) {
      const anchorScreen = worldToScreen(anchor, camera);
      const leaderEnd = leaderEndBeforeLabel(anchorScreen, labelScreen, labelWidth, labelHeight);
      return (
        <Group key={dimension.id} listening={false}>
          <Line points={[anchorScreen.x, anchorScreen.y, leaderEnd.x, leaderEnd.y]} stroke={mainStroke} strokeWidth={mainStrokeWidth} />
          {renderArrowHead(anchorScreen, leaderEnd, mainStroke)}
          {renderDimensionLabel(labelScreen, labelWidth, labelHeight, text, mainStroke)}
        </Group>
      );
    }
  }

  if (geometry["kind"] === "angular") {
    const vertex = geometryPoint(geometry["vertex"]);
    const first = geometryPoint(geometry["first"]);
    const second = geometryPoint(geometry["second"]);
    if (vertex && first && second) {
      const v = worldToScreen(vertex, camera);
      const a = worldToScreen(first, camera);
      const b = worldToScreen(second, camera);
      const radius = Math.max(18, Math.min(distance(a, v), distance(b, v), distance(labelScreen, v)));
      const start = pointOnRay(v, a, radius);
      const end = pointOnRay(v, b, radius);
      const largeArc = angleBetween(v, start, end) > Math.PI ? 1 : 0;
      const arcPath = `M ${start.x} ${start.y} A ${radius} ${radius} 0 ${largeArc} 1 ${end.x} ${end.y}`;
      return (
        <Group key={dimension.id} listening={false}>
          <Line points={[v.x, v.y, a.x, a.y]} stroke={helperStroke} dash={[4, 4]} strokeWidth={hovered ? 1.2 : 0.8} />
          <Line points={[v.x, v.y, b.x, b.y]} stroke={helperStroke} dash={[4, 4]} strokeWidth={hovered ? 1.2 : 0.8} />
          <Path data={arcPath} stroke={mainStroke} strokeWidth={mainStrokeWidth} />
          {renderArrowHead(start, end, mainStroke)}
          {renderArrowHead(end, start, mainStroke)}
          {renderDimensionLabel(labelScreen, labelWidth, labelHeight, text, mainStroke)}
        </Group>
      );
    }
  }

  const view = views.find((candidate) => candidate.id === dimension.view_id);
  if (!view) return null;

  const a = worldToScreen(getAnchorWorld(view, dimension.anchor_a.role), camera);
  const b = worldToScreen(getAnchorWorld(view, dimension.anchor_b.role), camera);
  const horizontal = getDimensionOrientation(dimension) === "horizontal";

  if (horizontal) {
    const y = worldToScreen({ x: 0, y: dimension.placement.y_mm }, camera).y;
    const midX = (a.x + b.x) / 2;
    const labelAnchor = offsetDimensionLabel({ x: midX, y }, { x: a.x, y }, { x: b.x, y });
    return (
      <Group key={dimension.id} listening={false}>
        <Line points={[a.x, a.y, a.x, y]} stroke={helperStroke} dash={[4, 4]} strokeWidth={hovered ? 1.2 : 0.8} />
        <Line points={[b.x, b.y, b.x, y]} stroke={helperStroke} dash={[4, 4]} strokeWidth={hovered ? 1.2 : 0.8} />
        <Line points={[a.x, y, b.x, y]} stroke={mainStroke} strokeWidth={mainStrokeWidth} />
        {renderArrowHead({ x: a.x, y }, { x: b.x, y }, mainStroke)}
        {renderArrowHead({ x: b.x, y }, { x: a.x, y }, mainStroke)}
        {renderDimensionLabel(labelAnchor, labelWidth, labelHeight, text, mainStroke)}
      </Group>
    );
  }

  const x = worldToScreen({ x: dimension.placement.x_mm, y: 0 }, camera).x;
  const midY = (a.y + b.y) / 2;
  const labelAnchor = offsetDimensionLabel({ x, y: midY }, { x, y: a.y }, { x, y: b.y });
  return (
    <Group key={dimension.id} listening={false}>
      <Line points={[a.x, a.y, x, a.y]} stroke={helperStroke} dash={[4, 4]} strokeWidth={hovered ? 1.2 : 0.8} />
      <Line points={[b.x, b.y, x, b.y]} stroke={helperStroke} dash={[4, 4]} strokeWidth={hovered ? 1.2 : 0.8} />
      <Line points={[x, a.y, x, b.y]} stroke={mainStroke} strokeWidth={mainStrokeWidth} />
      {renderArrowHead({ x, y: a.y }, { x, y: b.y }, mainStroke)}
      {renderArrowHead({ x, y: b.y }, { x, y: a.y }, mainStroke)}
      {renderDimensionLabel(labelAnchor, labelWidth, labelHeight, text, mainStroke)}
    </Group>
  );
}

function renderArrowHead(tip: ScreenPoint, tail: ScreenPoint, fill: string) {
  const dx = tail.x - tip.x;
  const dy = tail.y - tip.y;
  const length = Math.max(Math.hypot(dx, dy), 0.001);
  const ux = dx / length;
  const uy = dy / length;
  const px = -uy;
  const py = ux;
  const arrowLength = 10;
  const arrowWidth = 2;
  return (
    <Line
      points={[
        tip.x,
        tip.y,
        tip.x + ux * arrowLength + px * arrowWidth,
        tip.y + uy * arrowLength + py * arrowWidth,
        tip.x + ux * arrowLength - px * arrowWidth,
        tip.y + uy * arrowLength - py * arrowWidth,
      ]}
      fill={fill}
      closed
    />
  );
}

function renderDimensionLabel(center: ScreenPoint, width: number, height: number, text: string, fill: string) {
  return (
    <Text
      x={center.x - width / 2}
      y={center.y - height / 2}
      width={width}
      height={height}
      text={text}
      align="center"
      verticalAlign="middle"
      fontSize={Math.max(Math.min(height * 0.52, 13), 10)}
      fontStyle="bold"
      fill={fill}
    />
  );
}

function offsetDimensionLabel(label: ScreenPoint, lineStart: ScreenPoint, lineEnd: ScreenPoint): ScreenPoint {
  const dx = lineEnd.x - lineStart.x;
  const dy = lineEnd.y - lineStart.y;
  const length = Math.max(Math.hypot(dx, dy), 0.001);
  if (Math.abs(dy) <= Math.abs(dx) * 0.25) {
    return { x: label.x, y: label.y - DIMENSION_TEXT_OFFSET_PX };
  }
  if (Math.abs(dx) <= Math.abs(dy) * 0.25) {
    return { x: label.x + DIMENSION_TEXT_OFFSET_PX, y: label.y };
  }
  return {
    x: label.x + (-dy / length) * DIMENSION_TEXT_OFFSET_PX,
    y: label.y + (dx / length) * DIMENSION_TEXT_OFFSET_PX,
  };
}

function leaderEndBeforeLabel(anchor: ScreenPoint, label: ScreenPoint, labelWidth: number, labelHeight: number): ScreenPoint {
  const dx = anchor.x - label.x;
  const dy = anchor.y - label.y;
  const length = Math.max(Math.hypot(dx, dy), 0.001);
  const ux = dx / length;
  const uy = dy / length;
  const edgeX = Math.abs(ux) > 0.001 ? labelWidth / 2 / Math.abs(ux) : Number.POSITIVE_INFINITY;
  const edgeY = Math.abs(uy) > 0.001 ? labelHeight / 2 / Math.abs(uy) : Number.POSITIVE_INFINITY;
  const edgeDistance = Math.min(edgeX, edgeY);
  const clearance = Math.min(edgeDistance + RADIAL_TEXT_GAP_PX, Math.max(length - 2, 0));
  return {
    x: label.x + ux * clearance,
    y: label.y + uy * clearance,
  };
}

function geometryPoint(value: unknown): Point | null {
  if (!value || typeof value !== "object") return null;
  const candidate = value as Record<string, unknown>;
  const x = Number(candidate.x);
  const y = Number(candidate.y);
  if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
  return { x, y };
}

function pointOnRay(origin: ScreenPoint, through: ScreenPoint, radius: number): ScreenPoint {
  const dx = through.x - origin.x;
  const dy = through.y - origin.y;
  const length = Math.max(Math.hypot(dx, dy), 0.001);
  return {
    x: origin.x + (dx / length) * radius,
    y: origin.y + (dy / length) * radius,
  };
}

function angleBetween(origin: ScreenPoint, start: ScreenPoint, end: ScreenPoint) {
  const a0 = Math.atan2(start.y - origin.y, start.x - origin.x);
  const a1 = Math.atan2(end.y - origin.y, end.x - origin.x);
  return Math.abs(a1 - a0);
}

function distance(a: ScreenPoint, b: ScreenPoint) {
  return Math.hypot(a.x - b.x, a.y - b.y);
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

function fitViewBoxToRect(rect: Marquee, viewportSize: { width: number; height: number }, sheet: Sheet): ViewBox {
  const center = {
    x: rect.x + rect.width / 2,
    y: rect.y + rect.height / 2,
  };
  const viewportAspect = viewportSize.height > 0 ? viewportSize.width / viewportSize.height : 1;
  let width = Math.max(rect.width * ZOOM_BOX_PADDING, MIN_ZOOM_BOX_WORLD_SIZE);
  let height = Math.max(rect.height * ZOOM_BOX_PADDING, MIN_ZOOM_BOX_WORLD_SIZE);
  const rectAspect = width / height;

  if (rectAspect > viewportAspect) {
    height = width / viewportAspect;
  } else {
    width = height * viewportAspect;
  }

  return clampViewBoxToSheet(
    {
      x: center.x - width / 2,
      y: center.y - height / 2,
      width,
      height,
    },
    sheet,
  );
}

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

function makeCamera(viewBox: ViewBox, viewportSize: { width: number; height: number }): Camera {
  const scale = Math.min(viewportSize.width / viewBox.width, viewportSize.height / viewBox.height);
  return {
    scaleX: scale,
    scaleY: scale,
    offsetX: (viewportSize.width - viewBox.width * scale) / 2 - viewBox.x * scale,
    offsetY: (viewportSize.height - viewBox.height * scale) / 2 - viewBox.y * scale,
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
  if (rect.width <= 0 || rect.height <= 0) return null;
  const camera = makeCamera(viewBox, { width: rect.width, height: rect.height });
  return {
    x: (clientX - rect.left - camera.offsetX) / camera.scaleX,
    y: (clientY - rect.top - camera.offsetY) / camera.scaleY,
  };
}

function getTitleBlockFieldBounds(field: PreviewTitleBlockField, metadata?: Record<string, TitleBlockFieldMetadata>): Marquee {
  const fieldMetadata = findTitleBlockFieldMetadata(field, metadata);
  const x = fieldMetadata?.x_mm ?? field.placement.x_mm;
  const y = fieldMetadata?.y_mm ?? field.placement.y_mm;
  const width = Math.max(fieldMetadata?.width_mm ?? field.width_mm ?? 28, 8);
  const fontSize = Math.max(fieldMetadata?.font_size_mm ?? 4, 2.5);
  const height = Math.max(fontSize * 2.1, 5);
  const anchor = fieldMetadata?.text_anchor ?? "start";
  const left = anchor === "middle" ? x - width / 2 : anchor === "end" ? x - width : x;
  return {
    x: left - 1.5,
    y: y - height * 0.72,
    width: width + 3,
    height,
  };
}

function findTitleBlockFieldMetadata(field: PreviewTitleBlockField, metadata?: Record<string, TitleBlockFieldMetadata>) {
  if (!metadata) return undefined;
  if (metadata[field.id]) return metadata[field.id];
  const editableName = field.id.startsWith("tb-") ? field.id.slice(3) : field.id;
  return metadata[editableName];
}

function getTitleBlockPopupStyle(rect: ScreenRect, viewportSize: { width: number; height: number }): React.CSSProperties {
  const width = Math.min(300, Math.max(viewportSize.width - 24, 220));
  const gap = 8;
  const preferredTop = rect.y - 154;
  const top = preferredTop >= 12 ? preferredTop : rect.y + rect.height + gap;
  return {
    width,
    left: clamp(rect.x + Math.min(rect.width, 48), 12, Math.max(viewportSize.width - width - 12, 12)),
    top: clamp(top, 12, Math.max(viewportSize.height - 172, 12)),
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

function getViewRenderTransform(view: PreviewViewState, originalView: PreviewViewState): ViewRenderTransform {
  const originalBounds = originalView.selection_bounds_mm;
  const dx = view.selection_bounds_mm.x_min - originalBounds.x_min;
  const dy = view.selection_bounds_mm.y_min - originalBounds.y_min;
  const scale = originalView.scale > 0 ? view.scale / originalView.scale : 1;
  return {
    x: dx + originalBounds.x_min * (1 - scale),
    y: dy + originalBounds.y_min * (1 - scale),
    scale,
  };
}

function isSelectableSketchItem(item: SceneItem) {
  if (item.kind !== "path" && item.kind !== "rect" && item.kind !== "circle") {
    return false;
  }
  if (!getSceneItemViewId(item)) {
    return false;
  }
  return !item.classes.some((className) => className === "view-isometric-shaded-face" || className === "view-label" || className === "note");
}

function getSceneItemViewId(item: SceneItem) {
  return item.group_id ?? (typeof item.meta?.view_id === "string" ? item.meta.view_id : null);
}

function sketchItemBelongsToView(itemId: string, viewId: string, sceneLayers: Record<string, SceneItem[]>) {
  const sketchLayers = [
    ...(sceneLayers.viewGeometryVisible ?? []),
    ...(sceneLayers.viewGeometryHidden ?? []),
    ...(sceneLayers.sectionHatch ?? []),
    ...(sceneLayers.centerlines ?? []),
  ];
  return sketchLayers.some((item) => item.id === itemId && getSceneItemViewId(item) === viewId);
}

function getViewDragTargetIds(activeView: PreviewViewState, selectedIds: string[], views: PreviewViewState[]) {
  const targetIds = new Set(selectedIds);
  const primaryViewId = findPrimaryViewId(views);
  if (activeView.id !== primaryViewId) {
    return Array.from(targetIds);
  }

  for (const view of views) {
    if (isLinkedOrthographicView(view, primaryViewId)) {
      targetIds.add(view.id);
    }
  }
  return Array.from(targetIds);
}

function isLinkedOrthographicView(view: PreviewViewState, primaryViewId: string | null) {
  if (!primaryViewId || view.kind === "isometric") {
    return false;
  }
  if (view.id === primaryViewId || view.kind === "right") {
    return true;
  }
  return view.kind === "front" || view.kind === "top";
}

function findPrimaryViewId(views: PreviewViewState[]) {
  const candidates = views.filter((view) => view.kind === "front" || view.kind === "top");
  if (candidates.length === 0) {
    return null;
  }
  if (candidates.length === 1) {
    return candidates[0].id;
  }

  const rightView = views.find((view) => view.kind === "right");
  const scored = candidates.map((view) => {
    const verticalCompanion = candidates.find((candidate) => candidate.id !== view.id);
    let score = 0;
    if (rightView && nearlyEqual(view.y_mm, rightView.y_mm)) {
      score += 3;
    }
    if (verticalCompanion && nearlyEqual(view.x_mm, verticalCompanion.x_mm)) {
      score += 2;
    }
    if (view.kind === "front") {
      score += 1;
    }
    return { view, score };
  });

  scored.sort((left, right) => right.score - left.score);
  return scored[0].view.id;
}

function nearlyEqual(left: number, right: number, tolerance = 0.75) {
  return Math.abs(left - right) <= tolerance;
}

function sameStringRecord(left: Record<string, string>, right: Record<string, string>) {
  const leftKeys = Object.keys(left);
  const rightKeys = Object.keys(right);
  if (leftKeys.length !== rightKeys.length) {
    return false;
  }
  return rightKeys.every((key) => left[key] === right[key]);
}

function isEditableKeyboardTarget(target: EventTarget | null) {
  if (!(target instanceof HTMLElement)) {
    return false;
  }
  const tagName = target.tagName.toLowerCase();
  return tagName === "input" || tagName === "textarea" || tagName === "select" || target.isContentEditable;
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
  const geometry = dimension.computed_geometry ?? {};
  if (geometry["kind"] === "linear" && typeof geometry["orientation"] === "string") {
    if (geometry["orientation"] === "horizontal") return "horizontal";
    if (geometry["orientation"] === "vertical") return "vertical";
    return "free";
  }
  const type = dimension.dimension_type;
  if (type === "DistanceX") return "horizontal";
  if (type === "DistanceY") return "vertical";
  if (type === "Radius" || type === "Diameter" || type === "Angle" || type === "Angle3Pt") return "free";
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
  const geometryBounds = getComputedDimensionBounds(dimension);
  if (geometryBounds) return geometryBounds;

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

function getDimensionOverlayAnchor(dimension: PreviewDimension, views: PreviewViewState[]) {
  const label = geometryPoint(dimension.computed_geometry?.["label"]);
  if (label) {
    return label;
  }
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

function getComputedDimensionBounds(dimension: PreviewDimension): Marquee | null {
  const geometry = dimension.computed_geometry ?? {};
  const keys =
    geometry["kind"] === "linear"
      ? ["extension_start", "extension_end", "line_start", "line_end", "label"]
      : geometry["kind"] === "radial"
        ? ["center", "anchor", "label"]
        : geometry["kind"] === "angular"
          ? ["vertex", "first", "second", "label"]
          : [];
  const points = keys.map((key) => geometryPoint(geometry[key])).filter((point): point is Point => Boolean(point));
  if (!points.length) return null;
  const xs = points.map((point) => point.x);
  const ys = points.map((point) => point.y);
  const padding = 5;
  return {
    x: Math.min(...xs) - padding,
    y: Math.min(...ys) - padding,
    width: Math.max(...xs) - Math.min(...xs) + padding * 2,
    height: Math.max(...ys) - Math.min(...ys) + padding * 2,
  };
}

function withDimensionPlacement(dimension: PreviewDimension, x_mm: number, y_mm: number): PreviewDimension {
  const computed = { ...(dimension.computed_geometry ?? {}) };
  computed["label"] = { x: x_mm, y: y_mm };
  return {
    ...dimension,
    placement: { ...dimension.placement, x_mm, y_mm },
    computed_geometry: computed,
  };
}

function translateDimension(dimension: PreviewDimension, dx_mm: number, dy_mm: number): PreviewDimension {
  if (dx_mm === 0 && dy_mm === 0) {
    return dimension;
  }
  return {
    ...dimension,
    placement: {
      ...dimension.placement,
      x_mm: round2(dimension.placement.x_mm + dx_mm),
      y_mm: round2(dimension.placement.y_mm + dy_mm),
    },
    computed_geometry: translateDimensionGeometry(dimension.computed_geometry ?? {}, dx_mm, dy_mm) as Record<string, unknown>,
  };
}

function translateDimensionGeometry(value: unknown, dx_mm: number, dy_mm: number): unknown {
  if (Array.isArray(value)) {
    return value.map((item) => translateDimensionGeometry(item, dx_mm, dy_mm));
  }
  if (!value || typeof value !== "object") {
    return value;
  }

  const translated = Object.fromEntries(
    Object.entries(value as Record<string, unknown>).map(([key, item]) => [key, translateDimensionGeometry(item, dx_mm, dy_mm)]),
  );
  const x = translated.x;
  const y = translated.y;
  if (typeof x === "number" && typeof y === "number") {
    translated.x = round2(x + dx_mm);
    translated.y = round2(y + dy_mm);
  }
  return translated;
}

function linearLabelPlacement(orientation: string, extensionStart: Point, extensionEnd: Point, lineStart: Point, lineEnd: Point): Point {
  if (orientation === "horizontal") {
    const direction = lineStart.y + lineEnd.y >= extensionStart.y + extensionEnd.y ? 1 : -1;
    return {
      x: (lineStart.x + lineEnd.x) / 2,
      y: (lineStart.y + lineEnd.y) / 2 + direction * LINEAR_LABEL_OFFSET_MM,
    };
  }
  if (orientation === "vertical") {
    const direction = lineStart.x + lineEnd.x >= extensionStart.x + extensionEnd.x ? 1 : -1;
    return {
      x: (lineStart.x + lineEnd.x) / 2 + direction * LINEAR_LABEL_OFFSET_MM,
      y: (lineStart.y + lineEnd.y) / 2,
    };
  }

  const dx = lineEnd.x - lineStart.x;
  const dy = lineEnd.y - lineStart.y;
  const length = Math.max(Math.hypot(dx, dy), 0.001);
  return {
    x: (lineStart.x + lineEnd.x) / 2 + (-dy / length) * LINEAR_LABEL_OFFSET_MM,
    y: (lineStart.y + lineEnd.y) / 2 + (dx / length) * LINEAR_LABEL_OFFSET_MM,
  };
}

function offsetLinePoint(point: Point, lineStart: Point, lineEnd: Point, offset: number): Point {
  const dx = lineEnd.x - lineStart.x;
  const dy = lineEnd.y - lineStart.y;
  const length = Math.max(Math.hypot(dx, dy), 0.001);
  return {
    x: point.x + (-dy / length) * offset,
    y: point.y + (dx / length) * offset,
  };
}

function buildDimensionFromTool(tool: DimensionTool, view: PreviewViewState, sceneLayers: Record<string, SceneItem[]>): PreviewDimension | null {
  const bounds = view.selection_bounds_mm;
  const scale = view.scale || 1;
  const baseId = `dim-${view.id}-${tool.toLowerCase()}-${Date.now()}`;
  const primitiveId = view.source_ref?.id ?? view.id;

  if (tool === "DistanceX" || tool === "DistanceY" || tool === "Distance") {
    const horizontal = tool === "DistanceX";
    const vertical = tool === "DistanceY";
    const extensionStart = horizontal
      ? { x: bounds.x_min, y: bounds.y_max }
      : vertical
        ? { x: bounds.x_max, y: bounds.y_min }
        : { x: bounds.x_min, y: bounds.y_max };
    const extensionEnd = horizontal
      ? { x: bounds.x_max, y: bounds.y_max }
      : vertical
        ? { x: bounds.x_max, y: bounds.y_max }
        : { x: bounds.x_max, y: bounds.y_min };
    const lineStart = horizontal
      ? { x: extensionStart.x, y: bounds.y_max + LINEAR_DIMENSION_OFFSET_MM }
      : vertical
        ? { x: bounds.x_max + LINEAR_DIMENSION_OFFSET_MM, y: extensionStart.y }
        : offsetLinePoint(extensionStart, extensionStart, extensionEnd, LINEAR_DIMENSION_OFFSET_MM);
    const lineEnd = horizontal
      ? { x: extensionEnd.x, y: bounds.y_max + LINEAR_DIMENSION_OFFSET_MM }
      : vertical
        ? { x: bounds.x_max + LINEAR_DIMENSION_OFFSET_MM, y: extensionEnd.y }
        : offsetLinePoint(extensionEnd, extensionStart, extensionEnd, LINEAR_DIMENSION_OFFSET_MM);
    const orientation = horizontal ? "horizontal" : vertical ? "vertical" : "aligned";
    const label = linearLabelPlacement(orientation, extensionStart, extensionEnd, lineStart, lineEnd);
    const value = horizontal
      ? (bounds.x_max - bounds.x_min) / scale
      : vertical
        ? (bounds.y_max - bounds.y_min) / scale
        : Math.hypot(bounds.x_max - bounds.x_min, bounds.y_max - bounds.y_min) / scale;
    const formattedText = formatDimensionText(tool, value);
    return {
      id: baseId,
      view_id: view.id,
      label: formattedText,
      value: round2(value),
      units: "mm",
      dimension_type: tool,
      measurement_type: "Projected",
      references: [primitiveId],
      references_2d: [primitiveId],
      references_3d: [],
      anchor_a: { view_id: view.id, primitive_id: primitiveId, role: horizontal ? "min-x" : "min-y" },
      anchor_b: { view_id: view.id, primitive_id: primitiveId, role: horizontal ? "max-x" : "max-y" },
      placement: { x_mm: label.x, y_mm: label.y },
      computed_geometry: {
        kind: "linear",
        orientation,
        extension_start: extensionStart,
        extension_end: extensionEnd,
        line_start: lineStart,
        line_end: lineEnd,
        label,
      },
      formatted_text: formattedText,
      format_spec: "%.2f",
    };
  }

  if (tool === "Radius" || tool === "Diameter") {
    const circle = findFirstCircleForView(view.id, sceneLayers);
    const width = bounds.x_max - bounds.x_min;
    const height = bounds.y_max - bounds.y_min;
    const radius = circle?.radius ?? Math.min(width, height) / 6;
    const center = circle ? { x: circle.x ?? bounds.x_min + width / 2, y: circle.y ?? bounds.y_min + height / 2 } : { x: bounds.x_min + width / 2, y: bounds.y_min + height / 2 };
    const anchor = { x: center.x + radius, y: center.y };
    const label = { x: center.x + radius + 12, y: center.y - radius - 12 };
    const value = tool === "Diameter" ? (radius * 2) / scale : radius / scale;
    const formattedText = formatDimensionText(tool, value);
    return {
      id: baseId,
      view_id: view.id,
      label: formattedText,
      value: round2(value),
      units: "mm",
      dimension_type: tool,
      measurement_type: "Projected",
      references: [circle?.id ?? primitiveId],
      references_2d: [circle?.id ?? primitiveId],
      references_3d: [],
      anchor_a: { view_id: view.id, primitive_id: circle?.id ?? primitiveId, role: "center" },
      anchor_b: { view_id: view.id, primitive_id: circle?.id ?? primitiveId, role: "circle" },
      placement: { x_mm: label.x, y_mm: label.y },
      computed_geometry: { kind: "radial", center, radius, anchor, label },
      formatted_text: formattedText,
      format_spec: "%.2f",
    };
  }

  const vertex = { x: bounds.x_min, y: bounds.y_max };
  const first = { x: bounds.x_max, y: bounds.y_max };
  const width = bounds.x_max - bounds.x_min;
  const height = bounds.y_max - bounds.y_min;
  const second = tool === "Angle3Pt" ? { x: bounds.x_min, y: bounds.y_min } : { x: bounds.x_min + width * 0.72, y: bounds.y_min };
  const label = { x: bounds.x_min + width * 0.35, y: bounds.y_max - height * 0.35 };
  const value = angleFromPoints(vertex, first, second);
  const formattedText = formatDimensionText(tool, value);
  return {
    id: baseId,
    view_id: view.id,
    label: formattedText,
    value: round2(value),
    units: "mm",
    dimension_type: tool,
    measurement_type: "Projected",
    references: [primitiveId],
    references_2d: [primitiveId],
    references_3d: [],
    anchor_a: { view_id: view.id, primitive_id: primitiveId, role: "angle-a" },
    anchor_b: { view_id: view.id, primitive_id: primitiveId, role: "angle-b" },
    placement: { x_mm: label.x, y_mm: label.y },
    computed_geometry: { kind: "angular", vertex, first, second, label },
    formatted_text: formattedText,
    format_spec: "%.2f",
  };
}

function findFirstCircleForView(viewId: string, sceneLayers: Record<string, SceneItem[]>) {
  return (sceneLayers.viewGeometryVisible ?? []).find((item) => item.kind === "circle" && item.group_id === viewId);
}

function formatDimensionText(type: DimensionType, value: number) {
  const formatted = round2(value).toString();
  if (type === "Radius") return `R${formatted}`;
  if (type === "Diameter") return `\u2300${formatted}`;
  if (type === "Angle" || type === "Angle3Pt") return `${formatted}\u00b0`;
  return formatted;
}

function angleFromPoints(vertex: Point, first: Point, second: Point) {
  const a0 = Math.atan2(first.y - vertex.y, first.x - vertex.x);
  const a1 = Math.atan2(second.y - vertex.y, second.x - vertex.x);
  const angle = Math.abs(((a1 - a0) * 180) / Math.PI) % 360;
  return angle > 180 ? 360 - angle : angle;
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
    stroke = "#475569";
    strokeWidth = 0.32;
    dash = [2, 1.25];
    opacity = 0.58;
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
