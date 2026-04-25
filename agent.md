# Agent Handoff: TechDraw-Style Dimensioning

## Mission

Implement and harden a Python-first TechDraw-style dimensioning system for `auto-drawing`, using the checked-out FreeCAD TechDraw source as the behavioral reference while keeping the implementation independent from a FreeCAD runtime.

The first production slice should support:
- Auto-generated default dimensions on drawing previews.
- Dimension document objects linked to projected view references.
- Editable placement through the existing preview command API.
- SVG/HTML export of dimension graphics.
- React/Konva rendering and simple toolbar-driven dimension creation.

## FreeCAD Research Anchors

- `FreeCAD/src/Mod/TechDraw/App/DrawViewDimension.*`
  - Stores `Type`, `MeasureType`, `References2D`, `References3D`, format/tolerance fields, and placement.
  - `execute()` resolves references into linear, radial/diameter, or angular measurement geometry.
- `FreeCAD/src/Mod/TechDraw/App/DimensionGeometry.*`
  - Provides containers for `pointPair`, `anglePoints`, `arcPoints`, and area points.
- `FreeCAD/src/Mod/TechDraw/App/DimensionReferences.*`
  - Models object plus subelement references.
- `FreeCAD/src/Mod/TechDraw/App/DrawDimHelper.*`
  - Creates extent and distance dimensions from selected/projected references.
- `FreeCAD/src/Mod/TechDraw/Gui/CommandCreateDims.cpp`
  - Validates selected geometry before dimension creation.
- `FreeCAD/src/Mod/TechDraw/Gui/QGIViewDimension.*`
  - Renders dimension lines, extension lines, leaders, arcs, arrows, and text by dimension type.

## Completed

- [x] Restored the expected test fixture layout under `fixtures/step` from the existing frontend sample fixtures.
- [x] Extended `DimensionObject` in `autodrawing/contracts.py` with:
  - `dimension_type`
  - `measurement_type`
  - `references_2d`
  - `references_3d`
  - `computed_geometry`
  - `formatted_text`
  - `format_spec`
- [x] Added dimension command kinds:
  - `CreateDimension`
  - `DeleteDimension`
  - `MoveDimensionText`
  - `SetDimensionFormat`
  - `SetDimensionMeasurementType`
- [x] Added `autodrawing/dimensions.py`.
  - Generates default extent dimensions for the anchor orthographic view.
  - Generates diameter dimensions for projected circles.
  - Normalizes manual dimensions.
  - Computes angular values from `Angle` / `Angle3Pt` geometry.
  - Updates computed label/line geometry when text placement changes.
- [x] Wired default dimension generation into `DrawingDocumentService.create_document`.
- [x] Wired create/delete/move/format/measurement-type commands into document undo/redo.
- [x] Updated `SceneGraphService` so dimensions emit real scene primitives instead of a single text item.
- [x] Updated HTML/SVG export CSS for dimension lines, extension lines, leaders, arrowheads, and labels.
- [x] Set `dimension_editing_available=True` in preview payloads.
- [x] Updated backend/API tests for default dimensions and dimension commands.
- [x] Updated the React canvas type model for richer dimensions.
- [x] Updated React dimension rendering to prefer `computed_geometry`.
- [x] Added frontend toolbar buttons for horizontal, vertical, aligned, radius, diameter, angle, 3-point angle, and delete dimension.
- [x] Added simple toolbar-driven dimension creation from the selected view/circle.
- [x] Fixed the canvas selection sync so a newly created/selected dimension is not immediately replaced by its parent view selection.
- [x] Added `frontend/public/fixtures/cube.step` as the browser/upload smoke sample.
- [x] Added `?autoload=cube` support in the React app so the cube sample can be loaded deterministically in browser previews.
- [x] Updated the frontend smoke/screenshot scripts to upload `public/fixtures/cube.step`.
- [x] Fixed first-angle layout for plate-like parts:
  - Front view now sits above the broad top view.
  - Right view now sits left of the front view.
  - Plate right-view axes now show depth horizontally and thickness vertically instead of a rotated tall strip.
- [x] Promoted detected through-hole profiles from source-edge STEP imports to projected circles so dimension generation can create hole callouts.
- [x] Added a grouped hole callout for repeated same-size holes, e.g. `4x ⌀4.17 THRU`.
- [x] Added an automatic plate thickness dimension on the front view when the broad top view is the dimension anchor.
- [x] Made title-block defaults more explicit for guideline review:
  - General tolerances now include units, e.g. `ISO 2768-m / mm`.
  - Missing material now renders as `Not specified` instead of a blank field.
- [x] Tuned hidden-line rendering to a finer, lighter dashed thin line in the editor and HTML/SVG export.

## Verification Status

- [x] Backend tests pass:
  - Command: `python -m unittest discover -s tests -v`
  - Latest result: `35 tests OK`
- [x] Frontend build passes:
  - Command: `npm run build` from `frontend/`
  - Latest result: clean zero exit; Vite warns about a large bundle chunk.
- [x] Browser smoke verification with Browser Use was completed:
  - Opened `http://127.0.0.1:5173/?autoload=cube`.
  - Confirmed the sheet renders the `cube.step` title block and default `30 mm` cube dimensions.
  - Confirmed the toolbar is visible with pan, zoom, dimension creation, and delete controls.
  - Confirmed toolbar-driven horizontal dimension creation changes dimension overlays from 2 to 3, enables delete, and deletion returns the overlay count to 2.
  - Checked the Model tab; the cube fixture falls back to server-side sheet rendering and shows the expected backend fallback notice instead of a 3D model.
- [x] Browser/sample guideline verification was completed:
  - Loaded `http://127.0.0.1:5173/?autoload=sample&check=guidelines&fixed=1`.
  - Verified first-angle placement on `sample.step`: front above top, right left of front.
  - Verified added `10 mm` thickness dimension and grouped `4x ⌀4.17 THRU` hole callout.
  - Verified hidden edges render finer and lighter.
  - Visual screenshot: `frontend/.generated/fixed-sample-guidelines.png`
- [x] Frontend upload/layout smoke passes:
  - Command: `npm run smoke:view-layout` from `frontend/`
  - Latest result: clean zero exit.
  - Screenshot: `frontend/.generated/smoke-view-layout.png`
- [x] Frontend screenshot QA passes:
  - Command: `npm run screenshots:ui` from `frontend/`
  - Latest result: clean zero exit.
  - Upload fixture screenshot: `frontend/.generated/ui-screenshots/upload-fixture-desktop.png`
  - Mobile screenshot: `frontend/.generated/ui-screenshots/autoload-mobile.png`
- [x] Visual inspection completed for `cube.step` and `hole-pattern.step` generated dimensions from browser/smoke screenshots.
- [x] Visual inspection completed for `sample.step` after guideline fixes.
- [ ] Visual inspection of generated dimensions on `simple-block.step` is still needed.

## Next To Do

- [x] Re-run `npm run build` from `frontend/` with a longer timeout and record the result.
- [x] Start the backend and frontend dev servers.
- [x] Open the app and verify:
  - Default extent dimensions render on the drawing sheet.
  - Diameter callouts render on hole/circle views in the smoke screenshot.
  - View dragging updates placement through the command API.
- [x] Verify interactive dimension editing details:
  - Toolbar-created dimensions appear and survive preview refresh.
  - Deleting a selected toolbar-created dimension removes it from the preview.
- [x] Run or update the existing frontend smoke scripts:
  - `npm run smoke:view-layout`
  - `npm run screenshots:ui`
- [ ] Open the app and verify dragging dimension text updates placement through the command API.
- [ ] Check the exported SVG/HTML visually to ensure dimension arrowheads are filled and text is readable over the exact TechDraw template.
- [ ] Tighten manual creation behavior:
  - Add actual edge/circle/point hit-testing instead of creating dimensions from the selected view bounds.
  - Use selected projected primitives for `references_2d`.
  - Disable tools when no valid target reference exists.
- [ ] Improve backend validation:
  - Reject invalid reference combinations for each dimension type.
  - Validate radial dimensions require circle/arc geometry.
  - Validate angular dimensions require two edges or three points.
- [ ] Improve dimension layout:
  - De-duplicate repeated equal hole callouts where appropriate.
  - Avoid overlapping diameter labels in hole patterns.
  - Add collision checks against view geometry and other dimensions.
- [ ] Add richer tests:
  - Dedicated tests for radius dimensions.
  - Dedicated tests for two-line `Angle` dimensions.
  - API tests for `CreateDimension` and `DeleteDimension`.
  - Frontend interaction smoke test for text-anchor drag and delete.
- [ ] Revisit exact-runtime integration later:
  - Keep v1 projected-only.
  - When an OCC/FreeCAD runtime is available, add true 3D references and `MeasureType=True` measurement computation.

## Known Limitations

- Manual frontend creation is currently a useful first pass, not full TechDraw selection parity.
- The frontend creates dimensions from selected view bounds or first visible circle rather than from explicit snapped primitive selections.
- `computed_geometry` is intentionally dictionary-shaped for speed of iteration; a stricter typed schema should be added once the behavior settles.
- True 3D measurement is schema-compatible but not implemented because this environment still lacks a working importable exact geometry runtime.
- Default diameter generation can be noisy on hole-pattern views and needs grouping/collision logic.
- The tiny `cube.step` smoke fixture currently uses backend fallback for the Model tab; the sheet preview and upload flow are verified, but browser-side OCCT triangulation does not produce a model for that fixture.
- Local API tests require `httpx` because `fastapi.testclient` imports Starlette's TestClient. It was installed in the current Python environment during this pass.
- If TypeScript reports deleted UI component files after simplifying the frontend shell, remove ignored `frontend/*.tsbuildinfo` cache files and rerun the build.

## Files Changed In This Slice

- `autodrawing/contracts.py`
- `autodrawing/dimensions.py`
- `autodrawing/documents.py`
- `autodrawing/scene.py`
- `autodrawing/exporters.py`
- `autodrawing/preview.py`
- `frontend/src/components/DrawingCanvas.tsx`
- `frontend/src/App.tsx`
- `frontend/public/fixtures/cube.step`
- `frontend/scripts/smoke-view-layout.mjs`
- `frontend/scripts/screenshot-ui.mjs`
- `tests/test_document_commands.py`
- `tests/test_preview_api.py`
- `fixtures/step/*`

Current working tree note:
- Several unused shadcn/dashboard scaffold files are absent from the local app shell and are not imported by the current UI. Review that scaffold set before committing if dashboard components need to be preserved.

## Suggested Resume Order

1. Run `git status --short` and inspect current diffs.
2. Re-run backend tests.
3. Re-run frontend build with a longer timeout.
4. Launch the app at `http://127.0.0.1:5173/?autoload=cube` and verify the cube sheet preview.
5. Run `npm run smoke:view-layout` and `npm run screenshots:ui` from `frontend/`.
6. Tighten frontend primitive selection and backend validation.
