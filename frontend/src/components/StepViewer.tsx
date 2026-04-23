import { useEffect, useRef, useState } from "react";
import { Axis3d, Box, Boxes, Contrast, Eye, Grid3x3, Loader2 } from "lucide-react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";

import type { ImportResult, ImportedMesh } from "../lib/occtStepImport";

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

interface StepViewerProps {
  model: ImportResult | null;
  loading?: boolean;
}

export function StepViewer({ model, loading = false }: StepViewerProps) {
  const mountRef = useRef<HTMLDivElement | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.OrthographicCamera | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const faceGroupRef = useRef<THREE.Group | null>(null);
  const edgeGroupRef = useRef<THREE.Group | null>(null);
  const gridRef = useRef<THREE.GridHelper | null>(null);
  const axesRef = useRef<THREE.AxesHelper | null>(null);

  const [loadingMessage, setLoadingMessage] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState<{ bbox: THREE.Vector3; meshes: number; triangles: number } | null>(
    null,
  );
  const [viewMode, setViewMode] = useState<ViewMode>("shaded-edges");
  const [showHelpers, setShowHelpers] = useState<boolean>(true);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xffffff);
    sceneRef.current = scene;

    const width = mount.clientWidth || 800;
    const height = mount.clientHeight || 600;

    const camera = new THREE.OrthographicCamera(-400 * (width / height), 400 * (width / height), 400, -400, 0.1, 20000);
    camera.userData.frustumSize = 800;
    camera.position.set(200, 180, 240);
    camera.lookAt(0, 0, 0);
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
      const nextWidth = mount.clientWidth || 800;
      const nextHeight = mount.clientHeight || 600;
      updateOrthographicFrustum(camera, nextWidth / nextHeight);
      renderer.setSize(nextWidth, nextHeight);
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

  useEffect(() => {
    if (gridRef.current) gridRef.current.visible = showHelpers;
    if (axesRef.current) axesRef.current.visible = showHelpers;
  }, [showHelpers]);

  useEffect(() => {
    const faceGroup = faceGroupRef.current;
    const edgeGroup = edgeGroupRef.current;
    const camera = cameraRef.current;
    const controls = controlsRef.current;
    if (!faceGroup || !edgeGroup || !camera || !controls) return;

    disposeGroup(faceGroup);
    disposeGroup(edgeGroup);

    if (!model) {
      setStats(null);
      setLoadingMessage("");
      setError(null);
      return;
    }

    setError(null);
    setLoadingMessage("Building scene...");
    try {
      const meshResult = addImportedMeshes(model.meshes ?? [], faceGroup, edgeGroup);

      faceGroup.position.sub(meshResult.center);
      edgeGroup.position.sub(meshResult.center);

      const maxDim = Math.max(meshResult.bbox.x, meshResult.bbox.y, meshResult.bbox.z) || 100;
      const dist = maxDim * 2.2;
      camera.position.set(dist, dist * 0.8, dist * 1.1);
      camera.near = Math.max(0.1, maxDim / 500);
      camera.far = maxDim * 50;
      camera.userData.frustumSize = maxDim * 1.85;
      updateOrthographicFrustum(camera, getCameraAspect(camera));
      controls.target.set(0, 0, 0);
      camera.lookAt(0, 0, 0);
      controls.update();

      setStats({
        bbox: meshResult.bbox,
        meshes: model.meshes?.length ?? 0,
        triangles: meshResult.triangles,
      });
      setLoadingMessage("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
      setLoadingMessage("");
    }
  }, [model]);

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
  }, [stats, viewMode]);

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
          title={showHelpers ? "Hide grid and axes" : "Show grid and axes"}
          aria-label="Toggle grid and axes"
          aria-pressed={showHelpers}
          onClick={() => setShowHelpers((value) => !value)}
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
          {stats.bbox.x.toFixed(0)} x {stats.bbox.y.toFixed(0)} x {stats.bbox.z.toFixed(0)} mm
          {" · "}
          {stats.meshes} mesh{stats.meshes === 1 ? "" : "es"}
          {" · "}
          {stats.triangles.toLocaleString()} tris
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
    </div>
  );
}

function disposeGroup(group: THREE.Group) {
  group.traverse((obj) => {
    const candidate = obj as THREE.Mesh & { material?: THREE.Material | THREE.Material[] };
    if (candidate.geometry) candidate.geometry.dispose();
    if (Array.isArray(candidate.material)) candidate.material.forEach((material) => material.dispose());
    else if (candidate.material) candidate.material.dispose();
  });
  group.clear();
}

function addImportedMeshes(
  meshes: ImportedMesh[],
  faceGroup: THREE.Group,
  edgeGroup: THREE.Group,
): { bbox: THREE.Vector3; center: THREE.Vector3; triangles: number } {
  let triangles = 0;

  for (const mesh of meshes) {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute(
      "position",
      new THREE.BufferAttribute(new Float32Array(mesh.attributes.position.array), 3),
    );
    geometry.setIndex(new THREE.BufferAttribute(new Uint32Array(mesh.index.array), 1));

    if (mesh.attributes.normal?.array?.length) {
      geometry.setAttribute(
        "normal",
        new THREE.BufferAttribute(new Float32Array(mesh.attributes.normal.array), 3),
      );
    } else {
      geometry.computeVertexNormals();
    }

    const baseColor = mesh.color ? new THREE.Color(...mesh.color) : new THREE.Color(0xc8d4ea);
    const material = new THREE.MeshStandardMaterial({
      color: baseColor,
      metalness: 0.3,
      roughness: 0.55,
    });
    const threeMesh = new THREE.Mesh(geometry, material);
    threeMesh.name = mesh.name ?? "";
    threeMesh.userData.baseColor = baseColor.clone();
    faceGroup.add(threeMesh);

    const edgeGeometry = new THREE.EdgesGeometry(geometry, 30);
    const edgeMaterial = new THREE.LineBasicMaterial({
      color: 0x0f172a,
      transparent: true,
      opacity: 0.55,
    });
    const edgeLines = new THREE.LineSegments(edgeGeometry, edgeMaterial);
    edgeLines.name = threeMesh.name;
    edgeGroup.add(edgeLines);

    triangles += mesh.index.array.length / 3;
  }

  const box = new THREE.Box3().setFromObject(faceGroup);
  const bbox = new THREE.Vector3();
  const center = new THREE.Vector3();
  box.getSize(bbox);
  box.getCenter(center);

  return { bbox, center, triangles };
}

function updateOrthographicFrustum(camera: THREE.OrthographicCamera, aspect: number) {
  const frustumSize = typeof camera.userData.frustumSize === "number" ? camera.userData.frustumSize : 800;
  camera.left = (-frustumSize * aspect) / 2;
  camera.right = (frustumSize * aspect) / 2;
  camera.top = frustumSize / 2;
  camera.bottom = -frustumSize / 2;
  camera.updateProjectionMatrix();
}

function getCameraAspect(camera: THREE.OrthographicCamera) {
  const width = camera.right - camera.left;
  const height = camera.top - camera.bottom;
  return height === 0 ? 1 : width / height;
}
