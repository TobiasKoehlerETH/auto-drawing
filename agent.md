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

## Verification Status

- [x] Backend tests pass:
  - Command: `python -m unittest discover -s tests -v`
  - Latest result: `33 tests OK`
- [x] Frontend build passes:
  - Command: `npm run build` from `frontend/`
  - Latest result: clean zero exit; Vite warns about a large bundle chunk.
- [ ] Browser smoke verification is still needed after the frontend build is rerun.
- [ ] Visual inspection of generated dimensions on `cube-30.step`, `simple-block.step`, and `hole-pattern.step` is still needed.

## Next To Do

- [x] Re-run `npm run build` from `frontend/` with a longer timeout and record the result.
- [ ] Start the backend and frontend dev servers.
- [ ] Open the app and verify:
  - Default extent dimensions render on the drawing sheet.
  - Diameter callouts render on hole/circle views.
  - Dragging dimension text updates placement through the command API.
  - Deleting a selected dimension removes it from the preview.
  - Toolbar-created dimensions appear and survive preview refresh.
- [ ] Run or update the existing frontend smoke scripts:
  - `npm run smoke:view-layout`
  - `npm run screenshots:ui`
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

## Files Changed In This Slice

- `autodrawing/contracts.py`
- `autodrawing/dimensions.py`
- `autodrawing/documents.py`
- `autodrawing/scene.py`
- `autodrawing/exporters.py`
- `autodrawing/preview.py`
- `frontend/src/components/DrawingCanvas.tsx`
- `tests/test_document_commands.py`
- `tests/test_preview_api.py`
- `fixtures/step/*`

Current working tree note:
- `frontend/src/App.tsx` is modified in the worktree, but it was not part of the dimensioning edits described above. Review it separately before committing.

## Suggested Resume Order

1. Run `git status --short` and inspect current diffs.
2. Re-run backend tests.
3. Re-run frontend build with a longer timeout.
4. Launch the app and visually verify dimensions.
5. Tighten frontend primitive selection and backend validation.
