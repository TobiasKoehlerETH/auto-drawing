export type ImportParams = {
  angularDeflection?: number;
  linearDeflection?: number;
  linearDeflectionType?: "bounding_box_ratio" | "absolute_value";
  linearUnit?: "millimeter" | "centimeter" | "meter" | "inch" | "foot";
};

export type ImportedMesh = {
  color?: [number, number, number];
  index: {
    array: number[];
  };
  name?: string;
  attributes: {
    normal?: {
      array: number[];
    };
    position: {
      array: number[];
    };
  };
};

export type ImportResult = {
  meshes?: ImportedMesh[];
  root?: unknown;
  success: boolean;
};

type OcctImportModule = {
  ReadStepFile(content: Uint8Array, params: ImportParams | null): ImportResult;
};

declare global {
  interface Window {
    occtimportjs?: (options?: { locateFile?: (path: string) => string }) => Promise<OcctImportModule>;
  }
}

export const IMPORT_PARAMS: ImportParams = {
  angularDeflection: 0.5,
  linearDeflection: 0.0025,
  linearDeflectionType: "bounding_box_ratio",
  linearUnit: "millimeter",
};

let importerScriptPromise: Promise<void> | null = null;
let importerPromise: Promise<OcctImportModule> | null = null;

export function loadImporterScript(): Promise<void> {
  if (!importerScriptPromise) {
    importerScriptPromise = new Promise((resolve, reject) => {
      if (window.occtimportjs) {
        resolve();
        return;
      }

      const existing = document.querySelector<HTMLScriptElement>('script[data-occt-import="true"]');
      if (existing) {
        existing.addEventListener("load", () => resolve(), { once: true });
        existing.addEventListener("error", () => reject(new Error("Failed to load STEP importer")), {
          once: true,
        });
        return;
      }

      const script = document.createElement("script");
      script.src = "/occt-import-js.js";
      script.async = true;
      script.dataset.occtImport = "true";
      script.onload = () => resolve();
      script.onerror = () => reject(new Error("Failed to load STEP importer"));
      document.head.appendChild(script);
    });
  }

  return importerScriptPromise;
}

export function getImporter(): Promise<OcctImportModule> {
  if (!importerPromise) {
    importerPromise = loadImporterScript().then(() => {
      if (!window.occtimportjs) {
        throw new Error("STEP importer runtime is unavailable");
      }

      return window.occtimportjs({
        locateFile: (path: string) => (path.endsWith(".wasm") ? "/occt-import-js.wasm" : path),
      });
    });
  }

  return importerPromise;
}

export async function importStepBuffer(buffer: ArrayBuffer, params: ImportParams | null = IMPORT_PARAMS): Promise<ImportResult> {
  const importer = await getImporter();
  const result = importer.ReadStepFile(new Uint8Array(buffer), params);
  if (!result.success || !result.meshes?.length) {
    throw new Error("STEP import failed");
  }
  return result;
}
