import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowLeftRight,
  Axis3d,
  Box,
  Boxes,
  ChevronRight,
  Contrast,
  Eye,
  Grid3x3,
  Layers,
  Loader2,
} from "lucide-react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
// The OpenCascadeInstance type is huge; treat it as `any` and access members
// by name. We keep this tight by isolating all `oc.` access inside helpers.
type OC = any; // eslint-disable-line @typescript-eslint/no-explicit-any

let occPromise: Promise<OC> | null = null;
function getOcc(): Promise<OC> {
  if (!occPromise) {
    // Dynamic import keeps the 60+ MB Emscripten factory out of the main
    // bundle — it's only fetched when the user actually loads a STEP file.
    // The package's index.js does a raw `import "./dist/opencascade.wasm.wasm"`
    // which Vite doesn't understand, so we pull the factory JS directly and
    // override `locateFile` to serve the WASM from /public.
    occPromise = import(
      /* @vite-ignore */ "opencascade.js/dist/opencascade.wasm.js"
    ).then((mod: { default: (opts: { locateFile: (p: string) => string }) => Promise<OC> }) =>
      mod.default({
        locateFile: (p: string) => (p.endsWith(".wasm") ? "/opencascade.wasm" : p),
      }),
    );
  }
  return occPromise!;
}

type ViewMode = "shaded" | "shaded-edges" | "wireframe" | "transparent" | "hidden-line";

type Preset = {
  id: string;
  label: string;
  position: [number, number, number];
  up?: [number, number, number];
};

const VIEW_PRESETS: Preset[] = [
  { id: "iso", label: "Iso", position: [1, 0.8, 1.1] },
  { id: "front", label: "Front", position: [0, 0, 1] },
  { id: "back", label: "Back", position: [0, 0, -1] },
  { id: "right", label: "Right", position: [1, 0, 0] },
  { id: "left", label: "Left", position: [-1, 0, 0] },
  { id: "top", label: "Top", position: [0, 1, 0], up: [0, 0, -1] },
  { id: "bottom", label: "Bottom", position: [0, -1, 0], up: [0, 0, 1] },
];

const VIEW_MODES: { id: ViewMode; label: string; icon: typeof Box }[] = [
  { id: "shaded", label: "Shaded", icon: Box },
  { id: "shaded-edges", label: "Edges", icon: Boxes },
  { id: "wireframe", label: "Wireframe", icon: Grid3x3 },
  { id: "transparent", label: "Transparent", icon: Eye },
  { id: "hidden-line", label: "B&W", icon: Contrast },
];

// TopAbs_ShapeEnum numeric values (stable across OCCT releases).
// 0=COMPOUND 1=COMPSOLID 2=SOLID 3=SHELL 4=FACE 5=WIRE 6=EDGE 7=VERTEX 8=SHAPE
type TopoKind =
  | "COMPOUND"
  | "COMPSOLID"
  | "SOLID"
  | "SHELL"
  | "FACE"
  | "WIRE"
  | "EDGE"
  | "VERTEX"
  | "SHAPE";

const TOPO_KIND: Record<number, TopoKind> = {
  0: "COMPOUND",
  1: "COMPSOLID",
  2: "SOLID",
  3: "SHELL",
  4: "FACE",
  5: "WIRE",
  6: "EDGE",
  7: "VERTEX",
  8: "SHAPE",
};

type TopoNode = {
  /** Stable path id for React keys (e.g. "0/2/1"). */
  id: string;
  kind: TopoKind;
  /** OCCT hash — stable for the session, not globally unique. */
  hash: number;
  children: TopoNode[];
};

interface StepViewerProps {
  source: ArrayBuffer | null;
}

export function StepViewer({ source }: StepViewerProps) {
  const mountRef = useRef<HTMLDivElement | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const faceGroupRef = useRef<THREE.Group | null>(null);
  const edgeGroupRef = useRef<THREE.Group | null>(null);
  const gridRef = useRef<THREE.GridHelper | null>(null);
  const axesRef = useRef<THREE.AxesHelper | null>(null);

  const [loading, setLoading] = useState<boolean>(false);
  const [loadingMessage, setLoadingMessage] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState<{ triangles: number; bbox: THREE.Vector3 } | null>(null);
  const [topology, setTopology] = useState<TopoNode | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>("shaded-edges");
  const [showHelpers, setShowHelpers] = useState<boolean>(true);
  const [treeOpen, setTreeOpen] = useState<boolean>(true);

  // One-time scene setup
  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xffffff);
    sceneRef.current = scene;

    const width = mount.clientWidth || 800;
    const height = mount.clientHeight || 600;

    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 20000);
    camera.position.set(200, 180, 240);
    cameraRef.current = camera;

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.setSize(width, height);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.0;
    mount.replaceChildren(renderer.domElement);
    rendererRef.current = renderer;

    const pmrem = new THREE.PMREMGenerator(renderer);
    scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controlsRef.current = controls;

    const hemi = new THREE.HemisphereLight(0xffffff, 0xe2e8f0, 0.6);
    scene.add(hemi);
    const key = new THREE.DirectionalLight(0xffffff, 1.1);
    key.position.set(200, 400, 300);
    scene.add(key);
    const fill = new THREE.DirectionalLight(0xffffff, 0.45);
    fill.position.set(-300, 100, -200);
    scene.add(fill);

    const grid = new THREE.GridHelper(1000, 50, 0xcbd5e1, 0xe2e8f0);
    (grid.material as THREE.Material).transparent = true;
    (grid.material as THREE.Material).opacity = 0.8;
    scene.add(grid);
    gridRef.current = grid;

    const axes = new THREE.AxesHelper(80);
    scene.add(axes);
    axesRef.current = axes;

    const faceGroup = new THREE.Group();
    const edgeGroup = new THREE.Group();
    scene.add(faceGroup);
    scene.add(edgeGroup);
    faceGroupRef.current = faceGroup;
    edgeGroupRef.current = edgeGroup;

    let raf = 0;
    const tick = () => {
      controls.update();
      renderer.render(scene, camera);
      raf = requestAnimationFrame(tick);
    };
    tick();

    const ro = new ResizeObserver(() => {
      const w = mount.clientWidth || 800;
      const h = mount.clientHeight || 600;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    });
    ro.observe(mount);

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      controls.dispose();
      renderer.dispose();
      mount.replaceChildren();
      rendererRef.current = null;
      sceneRef.current = null;
      cameraRef.current = null;
      controlsRef.current = null;
      faceGroupRef.current = null;
      edgeGroupRef.current = null;
      gridRef.current = null;
      axesRef.current = null;
    };
  }, []);

  // Toggle helper visibility
  useEffect(() => {
    if (gridRef.current) gridRef.current.visible = showHelpers;
    if (axesRef.current) axesRef.current.visible = showHelpers;
  }, [showHelpers]);

  // Load geometry whenever source changes
  useEffect(() => {
    const faceGroup = faceGroupRef.current;
    const edgeGroup = edgeGroupRef.current;
    const camera = cameraRef.current;
    const controls = controlsRef.current;
    if (!faceGroup || !edgeGroup || !camera || !controls) return;

    const disposeGroup = (group: THREE.Group) => {
      group.traverse((obj) => {
        const mesh = obj as THREE.Mesh & { material?: THREE.Material | THREE.Material[] };
        if (mesh.geometry) mesh.geometry.dispose();
        if (Array.isArray(mesh.material)) mesh.material.forEach((m) => m.dispose());
        else if (mesh.material) mesh.material.dispose();
      });
      group.clear();
    };

    disposeGroup(faceGroup);
    disposeGroup(edgeGroup);

    if (!source) {
      setStats(null);
      setTopology(null);
      setLoading(false);
      setLoadingMessage("");
      setError(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setLoadingMessage("Initializing OpenCascade…");
    setError(null);

    (async () => {
      let shape: OC | null = null;
      try {
        const oc = await getOcc();
        if (cancelled) return;

        setLoadingMessage("Parsing STEP…");
        shape = parseStep(oc, new Uint8Array(source));
        if (cancelled) return;

        setLoadingMessage("Meshing…");
        const meshResult = meshShape(oc, shape, faceGroup, edgeGroup);
        if (cancelled) return;

        setLoadingMessage("Walking topology…");
        const tree = buildTopology(oc, shape);

        // Center model on origin
        faceGroup.position.sub(meshResult.center);
        edgeGroup.position.sub(meshResult.center);

        // Fit camera
        const maxDim = Math.max(meshResult.bbox.x, meshResult.bbox.y, meshResult.bbox.z) || 100;
        const dist = maxDim * 2.2;
        camera.position.set(dist, dist * 0.8, dist * 1.1);
        camera.near = Math.max(0.1, maxDim / 500);
        camera.far = maxDim * 50;
        camera.updateProjectionMatrix();
        controls.target.set(0, 0, 0);
        controls.update();

        setStats({ triangles: meshResult.triangles, bbox: meshResult.bbox });
        setTopology(tree);
        setLoading(false);
        setLoadingMessage("");
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Failed to load");
        setLoading(false);
        setLoadingMessage("");
      } finally {
        if (shape && typeof shape.delete === "function") {
          try {
            shape.delete();
          } catch {
            /* some embind objects refuse explicit deletes — ignore */
          }
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [source]);

  // Apply view mode whenever it or the loaded geometry changes
  useEffect(() => {
    const faceGroup = faceGroupRef.current;
    const edgeGroup = edgeGroupRef.current;
    const scene = sceneRef.current;
    if (!faceGroup || !edgeGroup || !scene) return;

    faceGroup.visible = viewMode !== "wireframe";
    edgeGroup.visible = viewMode !== "shaded";

    faceGroup.traverse((obj) => {
      const mesh = obj as THREE.Mesh;
      if (!mesh.isMesh) return;
      const mat = mesh.material as THREE.MeshStandardMaterial;
      if (!mat) return;

      const baseColor =
        (mesh.userData.baseColor as THREE.Color | undefined) ?? new THREE.Color(0xc8d4ea);

      switch (viewMode) {
        case "shaded":
        case "shaded-edges":
          mat.color.copy(baseColor);
          mat.metalness = 0.3;
          mat.roughness = 0.55;
          mat.transparent = false;
          mat.opacity = 1;
          mat.depthWrite = true;
          mat.envMapIntensity = 1;
          break;
        case "transparent":
          mat.color.copy(baseColor);
          mat.metalness = 0.1;
          mat.roughness = 0.35;
          mat.transparent = true;
          mat.opacity = 0.25;
          mat.depthWrite = false;
          mat.envMapIntensity = 0.8;
          break;
        case "hidden-line":
          mat.color.set(0xffffff);
          mat.metalness = 0;
          mat.roughness = 1;
          mat.transparent = false;
          mat.opacity = 1;
          mat.depthWrite = true;
          mat.envMapIntensity = 0;
          break;
        case "wireframe":
          mat.color.copy(baseColor);
          mat.transparent = false;
          mat.opacity = 1;
          break;
      }
      mat.needsUpdate = true;
    });

    edgeGroup.traverse((obj) => {
      const seg = obj as THREE.LineSegments;
      if (!seg.isLineSegments) return;
      const mat = seg.material as THREE.LineBasicMaterial;
      if (!mat) return;

      switch (viewMode) {
        case "shaded-edges":
          mat.color.set(0x0f172a);
          mat.transparent = true;
          mat.opacity = 0.5;
          break;
        case "wireframe":
          mat.color.set(0x0f172a);
          mat.transparent = true;
          mat.opacity = 0.9;
          break;
        case "transparent":
          mat.color.set(0x1e293b);
          mat.transparent = true;
          mat.opacity = 0.8;
          break;
        case "hidden-line":
          mat.color.set(0x000000);
          mat.transparent = false;
          mat.opacity = 1;
          break;
        case "shaded":
          break;
      }
      mat.needsUpdate = true;
    });

    scene.background = new THREE.Color(0xffffff);
  }, [viewMode, stats]);

  function applyPreset(preset: Preset) {
    const camera = cameraRef.current;
    const controls = controlsRef.current;
    if (!camera || !controls || !stats) return;
    const maxDim = Math.max(stats.bbox.x, stats.bbox.y, stats.bbox.z) || 100;
    const dist = maxDim * 2.2;
    const [dx, dy, dz] = preset.position;
    const dir = new THREE.Vector3(dx, dy, dz).normalize();
    camera.position.copy(dir).multiplyScalar(dist);
    camera.up.set(...(preset.up ?? [0, 1, 0]));
    controls.target.set(0, 0, 0);
    camera.lookAt(0, 0, 0);
    controls.update();
  }

  return (
    <div className="relative h-full w-full">
      <div ref={mountRef} className="h-full w-full" />

      <div className="absolute right-3 top-3 flex items-center gap-2">
        <button
          type="button"
          title={showHelpers ? "Hide grid & axes" : "Show grid & axes"}
          aria-label="Toggle grid and axes"
          aria-pressed={showHelpers}
          onClick={() => setShowHelpers((v) => !v)}
          className={
            "grid h-10 w-10 place-items-center rounded-lg bg-white/95 shadow ring-1 ring-slate-200 backdrop-blur transition " +
            (showHelpers ? "text-slate-900" : "text-slate-400 hover:text-slate-900")
          }
        >
          <Axis3d className="h-4 w-4" />
        </button>
        <div className="flex rounded-lg bg-white/95 p-1 shadow ring-1 ring-slate-200 backdrop-blur">
          {VIEW_MODES.map((mode) => {
            const Icon = mode.icon;
            const active = viewMode === mode.id;
            return (
              <button
                key={mode.id}
                type="button"
                title={mode.label}
                aria-label={mode.label}
                aria-pressed={active}
                onClick={() => setViewMode(mode.id)}
                className={
                  "grid h-8 w-8 place-items-center rounded-md transition " +
                  (active
                    ? "bg-slate-900 text-white"
                    : "text-slate-500 hover:bg-slate-100 hover:text-slate-900")
                }
              >
                <Icon className="h-4 w-4" />
              </button>
            );
          })}
        </div>
      </div>

      {loading ? (
        <div className="pointer-events-none absolute inset-0 grid place-items-center bg-white/60 backdrop-blur-[1px]">
          <div className="flex flex-col items-center gap-2">
            <Loader2 className="h-10 w-10 animate-spin text-slate-700" />
            {loadingMessage ? (
              <span className="rounded-md bg-white/90 px-2 py-0.5 text-xs font-medium text-slate-600 shadow ring-1 ring-slate-200">
                {loadingMessage}
              </span>
            ) : null}
          </div>
        </div>
      ) : null}
      {error ? (
        <div className="pointer-events-none absolute left-3 top-3 rounded-md bg-red-500 px-3 py-1.5 text-xs font-medium text-white shadow">
          {error}
        </div>
      ) : null}
      {stats && !loading ? (
        <div className="pointer-events-none absolute bottom-3 left-3 rounded-md bg-white/90 px-3 py-1.5 text-xs font-medium text-slate-700 shadow ring-1 ring-slate-200">
          {stats.bbox.x.toFixed(0)} × {stats.bbox.y.toFixed(0)} × {stats.bbox.z.toFixed(0)} mm
        </div>
      ) : null}

      {stats ? (
        <div className="absolute bottom-3 right-3 flex rounded-lg bg-white/95 p-1 shadow ring-1 ring-slate-200 backdrop-blur">
          {VIEW_PRESETS.map((preset) => (
            <button
              key={preset.id}
              type="button"
              title={preset.label}
              aria-label={`View ${preset.label}`}
              onClick={() => applyPreset(preset)}
              className="rounded-md px-2.5 py-1 text-xs font-medium text-slate-600 transition hover:bg-slate-100 hover:text-slate-900"
            >
              {preset.label}
            </button>
          ))}
        </div>
      ) : null}

      {topology ? (
        <TopologyTreePanel
          root={topology}
          open={treeOpen}
          onToggle={() => setTreeOpen((v) => !v)}
        />
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Topology tree panel
// ---------------------------------------------------------------------------

const KIND_COLOR: Record<TopoKind, string> = {
  COMPOUND: "bg-slate-100 text-slate-700 ring-slate-200",
  COMPSOLID: "bg-slate-100 text-slate-700 ring-slate-200",
  SOLID: "bg-indigo-100 text-indigo-700 ring-indigo-200",
  SHELL: "bg-blue-100 text-blue-700 ring-blue-200",
  FACE: "bg-emerald-100 text-emerald-700 ring-emerald-200",
  WIRE: "bg-amber-100 text-amber-700 ring-amber-200",
  EDGE: "bg-orange-100 text-orange-700 ring-orange-200",
  VERTEX: "bg-rose-100 text-rose-700 ring-rose-200",
  SHAPE: "bg-slate-100 text-slate-700 ring-slate-200",
};

function TopologyTreePanel({
  root,
  open,
  onToggle,
}: {
  root: TopoNode;
  open: boolean;
  onToggle: () => void;
}) {
  const counts = useMemo(() => countKinds(root), [root]);

  return (
    <div className="absolute left-3 top-3 flex max-h-[calc(100%-24px)] flex-col rounded-lg bg-white/95 shadow ring-1 ring-slate-200 backdrop-blur">
      <button
        type="button"
        onClick={onToggle}
        className="flex items-center gap-2 rounded-t-lg px-3 py-2 text-left text-sm font-semibold text-slate-800 hover:bg-slate-50"
        aria-expanded={open}
      >
        <Layers className="h-4 w-4" />
        <span>Topology</span>
        <span className="ml-2 text-xs font-normal text-slate-500">
          {counts.SOLID ?? 0}S · {counts.FACE ?? 0}F · {counts.EDGE ?? 0}E · {counts.VERTEX ?? 0}V
        </span>
        <ArrowLeftRight
          className={
            "ml-auto h-3.5 w-3.5 text-slate-400 transition-transform " +
            (open ? "" : "rotate-180")
          }
        />
      </button>
      {open ? (
        <div className="min-w-[260px] max-w-[360px] overflow-auto border-t border-slate-200 px-1 py-1 text-xs">
          <TopoRow node={root} depth={0} path={root.id} defaultOpenUntilDepth={2} />
        </div>
      ) : null}
    </div>
  );
}

function TopoRow({
  node,
  depth,
  path,
  defaultOpenUntilDepth,
}: {
  node: TopoNode;
  depth: number;
  path: string;
  defaultOpenUntilDepth: number;
}) {
  const [open, setOpen] = useState<boolean>(depth < defaultOpenUntilDepth);
  const hasChildren = node.children.length > 0;

  return (
    <div>
      <div
        className="flex items-center gap-1 rounded px-1 py-0.5 hover:bg-slate-100"
        style={{ paddingLeft: `${depth * 12 + 4}px` }}
      >
        {hasChildren ? (
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            className="grid h-4 w-4 place-items-center rounded hover:bg-slate-200"
            aria-label={open ? "Collapse" : "Expand"}
          >
            <ChevronRight
              className={"h-3 w-3 text-slate-500 transition-transform " + (open ? "rotate-90" : "")}
            />
          </button>
        ) : (
          <span className="inline-block h-4 w-4" />
        )}
        <span
          className={
            "rounded px-1.5 py-[1px] text-[10px] font-semibold uppercase tracking-wide ring-1 " +
            KIND_COLOR[node.kind]
          }
        >
          {node.kind}
        </span>
        {hasChildren ? (
          <span className="text-slate-400">· {node.children.length}</span>
        ) : null}
        <span className="ml-auto font-mono text-[10px] text-slate-400">#{node.hash}</span>
      </div>
      {open && hasChildren ? (
        <div>
          {node.children.map((c, i) => (
            <TopoRow
              key={c.id}
              node={c}
              depth={depth + 1}
              path={`${path}/${i}`}
              defaultOpenUntilDepth={defaultOpenUntilDepth}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}

function countKinds(node: TopoNode, acc: Partial<Record<TopoKind, number>> = {}): Partial<Record<TopoKind, number>> {
  acc[node.kind] = (acc[node.kind] ?? 0) + 1;
  for (const c of node.children) countKinds(c, acc);
  return acc;
}

// ---------------------------------------------------------------------------
// OpenCascade helpers
// ---------------------------------------------------------------------------

const HASH_UPPER_BOUND = 0x7fffffff;

/** Write STEP bytes into the in-memory FS and read via STEPControl_Reader. */
function parseStep(oc: OC, bytes: Uint8Array): OC {
  // Absolute path — STEPControl_Reader.ReadFile uses C-string path resolution
  // and relative names can miss depending on the WASM cwd.
  const path = `/model-${Date.now()}.step`;
  if (typeof oc.FS.writeFile === "function") {
    oc.FS.writeFile(path, bytes);
  } else {
    // Older Emscripten builds: fall back to createDataFile.
    oc.FS.createDataFile("/", path.slice(1), bytes, true, true, true);
  }

  const reader = new oc.STEPControl_Reader_1();
  let status: unknown;
  try {
    status = reader.ReadFile(path);
  } finally {
    try {
      oc.FS.unlink(path);
    } catch {
      /* best effort */
    }
  }

  const statusValue =
    typeof status === "number" ? status : (status as { value?: number } | undefined)?.value ?? -1;
  // IFSelect_ReturnStatus: 0=Void, 1=Done, 2=Error, 3=Fail, 4=Stop
  const IFSELECT_NAMES: Record<number, string> = {
    0: "RetVoid",
    1: "RetDone",
    2: "RetError (path/IO)",
    3: "RetFail (parse)",
    4: "RetStop",
  };
  if (statusValue !== 1) {
    reader.delete();
    throw new Error(
      `STEP read failed: IFSelect ${statusValue} (${IFSELECT_NAMES[statusValue] ?? "unknown"})`,
    );
  }

  // TransferRoots wants a Message_ProgressRange; the default-constructed one
  // is a no-op progress sink.
  const progress = new oc.Message_ProgressRange_1();
  reader.TransferRoots(progress);
  progress.delete();

  const shape = reader.OneShape();
  reader.delete();
  return shape;
}

/**
 * Mesh every FACE of `shape` and push a single combined THREE.Mesh onto
 * `faceGroup` plus edge line segments onto `edgeGroup`. Each face's triangle
 * range is recorded in `mesh.userData.faceRanges` so it can be highlighted
 * later.
 */
function meshShape(
  oc: OC,
  shape: OC,
  faceGroup: THREE.Group,
  edgeGroup: THREE.Group,
): { bbox: THREE.Vector3; center: THREE.Vector3; triangles: number } {
  // Rough bbox in OCCT units to derive a sensible linear deflection.
  const bndBox = new oc.Bnd_Box_1();
  oc.BRepBndLib.Add(shape, bndBox, false);
  let diag = 100;
  if (!bndBox.IsVoid()) {
    const cmin = bndBox.CornerMin();
    const cmax = bndBox.CornerMax();
    diag = cmin.Distance(cmax) || 100;
    cmin.delete?.();
    cmax.delete?.();
  }
  bndBox.delete();

  const linDefl = Math.max(diag / 800, 0.01);
  const angDefl = 0.5;

  const mesher = new oc.BRepMesh_IncrementalMesh_2(shape, linDefl, false, angDefl, false);
  mesher.delete();

  const positions: number[] = [];
  const indices: number[] = [];
  const faceRanges: Array<{ start: number; count: number; hash: number }> = [];
  let vertOffset = 0;

  const explorer = new oc.TopExp_Explorer_2(
    shape,
    oc.TopAbs_ShapeEnum.TopAbs_FACE,
    oc.TopAbs_ShapeEnum.TopAbs_SHAPE,
  );
  while (explorer.More()) {
    const faceShape = explorer.Current();
    const face = oc.TopoDS.Face_1(faceShape);
    const location = new oc.TopLoc_Location_1();
    // BRep_Tool::Triangulation has a 2-arg form in older OCCT and a 3-arg
    // form (with Poly_MeshPurpose) in ≥7.5. Try the richer signature first.
    let handle: OC;
    try {
      const meshPurpose = oc.Poly_MeshPurpose?.Poly_MeshPurpose_NONE ?? 0;
      handle = oc.BRep_Tool.Triangulation(face, location, meshPurpose);
    } catch {
      handle = oc.BRep_Tool.Triangulation(face, location);
    }

    if (!handle.IsNull()) {
      const tri = handle.get();
      const nbNodes = tri.NbNodes();
      const nbTri = tri.NbTriangles();
      const trsf = location.Transformation();
      const reversed =
        (typeof face.Orientation_1 === "function"
          ? face.Orientation_1()
          : face.Orientation?.()) ===
        (oc.TopAbs_Orientation?.TopAbs_REVERSED?.value ?? 1);

      for (let i = 1; i <= nbNodes; i++) {
        const p = tri.Node(i);
        const pt = p.Transformed(trsf);
        positions.push(pt.X(), pt.Y(), pt.Z());
        pt.delete?.();
        p.delete?.();
      }

      const idxStart = indices.length;
      for (let i = 1; i <= nbTri; i++) {
        const t = tri.Triangle(i);
        let a = t.Value(1) - 1 + vertOffset;
        let b = t.Value(2) - 1 + vertOffset;
        let c = t.Value(3) - 1 + vertOffset;
        if (reversed) {
          const tmp = b;
          b = c;
          c = tmp;
        }
        indices.push(a, b, c);
        t.delete?.();
      }
      faceRanges.push({
        start: idxStart,
        count: nbTri * 3,
        hash: face.HashCode(HASH_UPPER_BOUND),
      });
      vertOffset += nbNodes;
    }

    handle.delete?.();
    location.delete();
    explorer.Next();
  }
  explorer.delete();

  const geom = new THREE.BufferGeometry();
  geom.setAttribute("position", new THREE.BufferAttribute(new Float32Array(positions), 3));
  geom.setIndex(new THREE.BufferAttribute(new Uint32Array(indices), 1));
  geom.computeVertexNormals();

  const color = new THREE.Color(0xc8d4ea);
  const faceMat = new THREE.MeshStandardMaterial({ color, metalness: 0.3, roughness: 0.55 });
  const mesh = new THREE.Mesh(geom, faceMat);
  mesh.userData.baseColor = color.clone();
  mesh.userData.faceRanges = faceRanges;
  faceGroup.add(mesh);

  const edgeGeom = new THREE.EdgesGeometry(geom, 30);
  const edgeMat = new THREE.LineBasicMaterial({
    color: 0x0f172a,
    transparent: true,
    opacity: 0.55,
  });
  edgeGroup.add(new THREE.LineSegments(edgeGeom, edgeMat));

  const box = new THREE.Box3().setFromObject(faceGroup);
  const size = new THREE.Vector3();
  const center = new THREE.Vector3();
  box.getSize(size);
  box.getCenter(center);

  return { bbox: size, center, triangles: indices.length / 3 };
}

/**
 * Walk the full B-rep topology via TopoDS_Iterator.
 * The resulting tree follows OCCT's natural containment:
 * Compound → Solid → Shell → Face → Wire → Edge → Vertex.
 *
 * Note: the same edge/vertex can appear under multiple parents (e.g. an edge
 * shared by two faces) — that is the honest topology and we don't dedupe.
 * We do cap the traversal at a hard node budget so pathological inputs
 * can't crash the UI.
 */
function buildTopology(oc: OC, shape: OC): TopoNode {
  const MAX_NODES = 50_000;
  let produced = 0;

  const visit = (s: OC, path: string): TopoNode => {
    produced++;
    const kindNum: number =
      typeof s.ShapeType === "function" ? s.ShapeType() : (s.ShapeType as number);
    const kind: TopoKind = TOPO_KIND[kindNum] ?? "SHAPE";
    const hash: number = s.HashCode(HASH_UPPER_BOUND);

    const children: TopoNode[] = [];
    if (kind !== "VERTEX" && produced < MAX_NODES) {
      const it = new oc.TopoDS_Iterator_2(s, true, true);
      let i = 0;
      while (it.More() && produced < MAX_NODES) {
        const child = it.Value();
        children.push(visit(child, `${path}/${i}`));
        it.Next();
        i++;
      }
      it.delete();
    }

    return { id: path, kind, hash, children };
  };

  return visit(shape, "0");
}
