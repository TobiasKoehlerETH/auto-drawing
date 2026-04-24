# Agent Handoff

## Mission
Implement a Python-first TechDraw-style backend in this repository that mirrors the FreeCAD TechDraw App-layer structure as directly as practical, integrates into the existing FastAPI and React application, and progressively replaces the current lightweight drawing pipeline with a richer, more standards-aware document model.

## Current Status
- `autodrawing.techdraw_exact` now exists and is integrated into the main pipeline as the document-decoration layer for TechDraw-style templates, page metadata, view wrappers, and runtime status.
- FreeCAD TechDraw asset files are copied into `autodrawing/techdraw_exact/assets` and the default ISO A3 template is parsed for editable field metadata.
- The backend pipeline now emits the `techdraw-native` adapter identity, richer template metadata, and TechDraw runtime details through the existing contracts and preview payloads.
- The React canvas now renders `document.page_template.svg_source` as the sheet background and suppresses legacy frame/title-block layers whenever an exact template is active.
- `SceneGraphService` no longer emits synthetic frame/title-block items for TechDraw-backed pages, so preview payloads do not duplicate the copied FreeCAD title block.
- The backend test suite and frontend production build currently pass after the TechDraw template wiring changes.
- The largest remaining gap is still exact geometry/runtime parity: there is no working FreeCAD runtime on this machine, and OCC Python bindings are still not importable in a usable way here.
- The next real unblocker is replacing the heuristic geometry/projection path with a stable exact-kernel path, or explicitly codifying that fallback boundary in the package.

## Completed
- [x] Created the initial TechDraw asset area inside the repo.
- [x] Identified and copied the FreeCAD ISO A3 template, PAT resources, line groups, and symbols.
- [x] Defined the `agent.md` handoff structure required for future sessions.
- [x] Added `autodrawing.techdraw_exact` modules for assets, runtime detection, SVG template parsing, model wrappers, and document decoration.
- [x] Integrated the TechDraw layer into `autodrawing/pipeline.py` so pipeline bundles now emit `techdraw-native`.
- [x] Extended contracts with template metadata, runtime metadata, and richer TechDraw-oriented fields.
- [x] Updated preview/export behavior so rendered SVG uses the processed copied FreeCAD template content.
- [x] Added TechDraw-focused tests and restored the expected fixture layout under `fixtures/step`.
- [x] Verified the backend test suite with `python -m unittest discover -s tests -v`.
- [x] Switched the canvas to use the copied FreeCAD TechDraw SVG template as the live sheet background.
- [x] Suppressed duplicate legacy frame/title-block scene items when an exact template is present.
- [x] Verified the updated frontend with `npm run build`.

## In Progress
- [ ] Investigate and stabilize a true exact OCC runtime import path for the new backend.
- [ ] Replace the current heuristic projection geometry with exact topology extraction behind `autodrawing.techdraw_exact`.
- [ ] Validate remaining export-stack rendering differences between `document.page_template.svg_source` and the assembled `svg` export payload.

## Next Session TODO
- [ ] Probe the installed OCC wheels again and either make `OCP` importable or document a clean optional-runtime contract in `autodrawing/techdraw_exact/runtime.py`.
- [ ] Add an exact shape extractor module inside `autodrawing/techdraw_exact` and start routing STEP-derived bounds/edges through it when the runtime is available.
- [ ] Add a regression test that compares the canvas/template path against a saved fixture payload, not only exporter string assertions.
- [ ] Investigate why standalone rendering of the assembled export `svg` still looks visually compressed even though `page_template.svg_source` and preview metadata are correct.
- [ ] Extend the TechDraw wrapper layer beyond page/template/view metadata into section/detail/balloon document objects with contract coverage.

## Open Decisions
- Should the exact-kernel runtime remain optional for now, or should a later session spend time making `OCP` importable on this machine before deeper geometry work continues?

## Risks / Blockers
- The environment still lacks a working importable exact OCC Python runtime despite multiple package installation attempts.
- FreeCAD is only present as a checked-out source tree, not as an executable or importable runtime.
- A full semantic port of TechDraw geometry and dimensioning is much larger than the current landing chunk, so intermediate compatibility layers will exist for a while.
- The repo originally lacked the `fixtures/step` layout expected by tests, so future sessions should avoid deleting or relocating those restored fixtures without updating tests.
- The assembled export `svg` still has rendering quirks when opened standalone in a browser, so the canvas template path is currently the more trustworthy exact-template verification surface.

## Key References
- `FreeCAD/src/Mod/TechDraw/App`
- `FreeCAD/src/Mod/TechDraw/Templates`
- `autodrawing/pipeline.py`
- `autodrawing/contracts.py`
- `autodrawing/techdraw_exact`
- `autodrawing/scene.py`
- `frontend/src/components/DrawingCanvas.tsx`

## Verification Status
- TechDraw asset copy is complete.
- Runtime probing confirmed no usable FreeCAD runtime and no stable exact OCC import yet.
- `python -m unittest discover -s tests -v` currently passes.
- `npm run build` in `frontend/` currently passes.
- Preview API now verifies that TechDraw-backed previews expose `page_template.source_path` and omit duplicate `frame` and `titleBlock` scene layers.
- Direct backend preview for `sample_part/cube.STEP` still reports adapter `techdraw-native` and points at `autodrawing/techdraw_exact/assets/Templates/ISO/A3_Landscape_ISO5457_minimal.svg`.
- Standalone browser rendering of the assembled export `svg` remains visually suspect and is still unverified against FreeCAD output.
