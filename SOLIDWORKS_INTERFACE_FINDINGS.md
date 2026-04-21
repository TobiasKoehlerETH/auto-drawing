# SolidWorks Agent Interface Findings

## Goal

Evaluate the SolidWorks API access patterns and the four SolidWorks-related MCP/server examples in this workspace, then identify the best combination of features for a new agent-facing interface that can create compliant drawings from STEP or SolidWorks files using the ISO/DIN guideline set in `guidelines/`.

## Evaluated Inputs

- `solidworks-mcp`
- `SolidworksMCP-python`
- `SolidworksMCP-TS`
- `swapi-pilot-solidworks-mcp`
- `guidelines/`
- Live SolidWorks tests on `sample_part/sample.SLDPRT`

## Executive Recommendation

Use a hybrid architecture:

1. Use `swapi-pilot` as the API lookup and method-discovery lane.
2. Use `SolidworksMCP-python` as the current best live-execution reference because it reached real SolidWorks and we verified actual drawing creation/view export paths locally.
3. Use `SolidworksMCP-TS` as the best TypeScript design base for a future custom interface because its drawing/template modules are the strongest structured TS surface.
4. Treat `solidworks-mcp` mainly as an older VBA/pattern source, not the foundation.
5. Treat `guidelines/` as a mandatory workflow gate before annotation and before completion, not as background documentation.

## What We Verified Live

### A. Direct SolidWorks helper path on `sample_part/sample.SLDPRT`

Live tests were run against:

- `C:\Code\auto-drawing\sample_part\sample.SLDPRT`

Results:

- Open sample part: PASS
- Create blank drawing document: PASS
- Save blank drawing as `.SLDDRW`: PASS
- Standard 3rd-angle view creation from sample part: PASS
- Manual `*Front` view creation: PASS
- Manual `*Isometric` view creation: PASS
- Export drawing to PDF using a direct `sw.GetExportFileData(1)` + `Extension.SaveAs(...)` path: PASS
- Auto-dimension insertion via `InsertModelAnnotations3`: FAIL
- One helper PDF export path using `model.GetSldWorksObject()`: FAIL

Interpretation:

- The core SolidWorks drawing pipeline is viable right now for drawing creation, view placement, save, and PDF export.
- The fragile part is auto-dimension/annotation automation, not drawing document creation itself.

### A.1 Latest real drawing iteration on `sample_part/sample.SLDPRT`

Live file outputs:

- `C:\Code\auto-drawing\.generated\guideline_drawing\sample_guideline_attempt.SLDDRW`
- `C:\Code\auto-drawing\.generated\guideline_drawing\sample_guideline_attempt.pdf`

Current script:

- `C:\Code\auto-drawing\scripts\generate_guideline_drawing.py`

What this script now proves:

- Opens a real SolidWorks part and creates a real `.SLDDRW`: PASS
- Creates an A3 ISO sheet with a live `.slddrt` sheet format: PASS
- Places manual first-angle views in the correct logical arrangement:
  - front
  - top below front
  - right to the left of front
  - isometric identification view
- Saves the drawing reliably after closing prior open copies: PASS
- Exports PDF when the output file is not locked by an external viewer: PASS
- Adds readable standards metadata notes without title-block overlap: PASS
- Auto-dimensions at least one main manufacturing view: PASS

Key screenshot-based lessons from the final iterations:

- Enlarging the orthographic views improved readability more than adding more annotation logic.
- Populating the title block directly with many tiny notes was a mistake; a compact metadata block above the native title block works much better visually.
- Limiting auto-dimensioning to the clearest manufacturing view is better than auto-dimensioning every orthographic view.
- Dual-display settings on generated dimensions create the most confusing visual failure mode. Even when the drawing is metric, on-screen results can still look like mixed inch/mm dimensions if dual formatting is not normalized aggressively.
- SolidWorks window redraw is not always trustworthy as the only truth source; the saved artifact and exported text/PDF evidence are often more reliable than the live canvas.
- A compact isometric recognition view at `1:2` works better for this project than an enlarged `2:1` isometric because it protects the bottom-right/title-block zone.

Best current recipe for a future agent interface:

1. Create drawing from a known-good metric template.
2. Create the sheet explicitly with `NewSheet4(...)`.
3. Place views manually with `CreateDrawViewFromModelView3(...)` instead of relying on unavailable convenience methods.
4. Add only the minimum standards metadata needed for readability.
5. Auto-dimension the primary view first, then selectively add more only if needed.
6. Normalize display-dimension formatting immediately after creation.
7. Keep the isometric view compact (`1:2`) and treat it as recognition-only.
8. Close/reopen or otherwise verify the saved drawing before treating the visual state as final.

Remaining blockers before calling the drawing flow "guideline-grade":

- Auto-dimension output is still too noisy for clean manufacturing presentation without more selective placement or manual pruning.
- A true projection symbol is not yet being inserted; the workflow currently uses explicit first-angle text.
- Section/detail view creation has not yet been added for the sample part.
- PDF export is vulnerable to file locks when the previous export is open in another viewer.
- There is still a mismatch between what SolidWorks shows on-screen and what the saved/exported artifact appears to represent, so the future interface should include a deliberate post-save verification step.

### B. `SolidworksMCP-python` MCP tool layer

Live tool-layer checks:

- `open_model(sample.SLDPRT)`: PASS
- `create_drawing(...)`: FAIL
- `save_as(...SLDDRW)`: FAIL in the tested sequence
- `create_drawing_view(...)`: returns success, but the implementation is simulated rather than proven COM-backed

Observed failure:

- `create_drawing` failed with:
  - `CircuitBreakerAdapter.create_drawing() takes 1 positional argument but 2 were given`

Interpretation:

- The Python repo has real adapter capability underneath.
- The MCP façade currently misroutes at least one drawing call and includes simulated success paths that can mislead an agent.

### C. Existing example script in `SolidworksMCP-python`

We also ran:

- `examples/generated/create_impressive_rotor_drawing.py`

Result:

- The script connected to SolidWorks and created a new drawing document.
- It then failed on `create_standard_views(...)` for the rotor example part.

Interpretation:

- There is real execution intent here, but the generated/example layer is not yet dependable enough to use as the main interface contract.

## Findings By Implementation

## 1. `SolidworksMCP-python`

### Best parts

- Best live evidence of real Windows/SolidWorks connectivity in this workspace.
- Strong low-level COM adapter surface for:
  - opening models
  - creating drawings
  - exporting files
  - macro execution fallback
- Good shape for a Python execution engine behind a future interface.

### Weak parts

- A significant part of the drawing tool layer is simulated or fallback-generated success rather than guaranteed real execution.
- `docs_discovery` under-discovered the live COM surface during testing and hit a callable/property mismatch bug while reading the SolidWorks version.
- The checked-in “dimensioned sheet” artifact is screenshot/PIL-based, not proof of a native SolidWorks drawing automation loop.

### Verdict

- Best current live execution reference.
- Not yet trustworthy as-is for agent-facing drawing automation without tightening the tool façade and removing simulated-success ambiguity.

## 2. `SolidworksMCP-TS`

### Best parts

- Strongest TypeScript structure for a future interface.
- Broader and cleaner drawing-adjacent module design:
  - `src/tools/drawing.ts`
  - `src/tools/template-manager.ts`
  - `src/tools/vba-drawing.ts`
- Installed successfully here.
- Built successfully here.
- Mock/unit test suite passed here.

### Weak parts

- Live SolidWorks behavior remains largely unproven.
- README and testing docs are honest that drawing/export paths are still untested against real SolidWorks.
- `winax` is optional in `package.json`, but the code still imports it directly in the runtime path, so native-runtime failure remains a real risk.

### Verdict

- Best TypeScript base for the new self-built interface.
- Should be treated as architecture/prototype-quality until real integration tests exist.

## 3. `solidworks-mcp`

### Best parts

- Rich VBA-generation ideas, especially in `src/tools/vba-drawing.ts`.
- Useful as a pattern/source repo for drawing macro generation concepts.

### Weak parts

- Installation failed locally because `winax` is a hard dependency and native build prerequisites were not fully satisfied on this machine.
- Harder dependency posture than `SolidworksMCP-TS`.
- Higher doc drift risk between README claims and what is concretely exposed/tested.

### Verdict

- Useful reference material.
- Not the right foundation for the new interface.

## 4. `swapi-pilot-solidworks-mcp`

### Best parts

- Best suited as an API lookup lane for method names, signatures, enums, and example discovery.
- Helps an agent avoid hallucinating SolidWorks API calls.

### Weak parts

- It is not the control plane.
- It should not be trusted to represent successful CAD state changes by itself.

### Verdict

- Keep it, but scope it to retrieval/advisory use only.

## 5. `guidelines/`

### Best parts

- Clear ISO/DIN drawing standard target:
  - first-angle projection
  - metric
  - ISO 8015
  - ISO 2768-mK
- `CHECKLIST.md` is especially valuable because it can serve as a machine-checkable verification rubric.

### Best use in the new interface

- Load relevant guideline topic files before placing each callout family.
- Run the checklist before completion/export signoff.
- Put declared standards directly into the title block/output metadata.

## What Works Best Right Now

For real work today, the strongest combination is:

- API lookup: `swapi-pilot`
- Live CAD execution: Python COM/helper path
- Future UI/interface design base: `SolidworksMCP-TS`
- Standards and verification: `guidelines/`

That combination is stronger than any single repo in the folder.

## Best Features To Reuse

### Reuse from `SolidworksMCP-python`

- Real COM adapter and template resolution
- File export/save logic
- Macro execution fallback path
- Pydantic-style tool input contracts

### Reuse from `SolidworksMCP-TS`

- Drawing creation orchestration
- Template-manager concepts
- TS module boundaries for drawing vs template vs macro generation
- Rich drawing VBA generators

### Reuse from `swapi-pilot`

- API search before code generation or tool routing
- Enum/member/method lookup before execution

### Reuse from `guidelines/`

- Topic-based annotation rule loading
- Checklist-driven drawing verification
- Required standards declaration in title block

## Features To Avoid Copying Blindly

- Simulated drawing-success responses in the Python tool layer
- Screenshot-based “drawing” generation as a substitute for native drawing automation
- Any path that claims drawing automation success without saving a real `.SLDDRW` or exported PDF
- Any install path that hard-requires brittle native `winax` compilation before basic evaluation can even begin

## Proposed New Interface Shape

Use a 4-stage pipeline:

1. Ingest
   - Accept STEP, SLDPRT, SLDASM, or SLDDRW.
   - Normalize the file type and intended output.

2. Plan
   - Use `swapi-pilot` and local docs discovery only to resolve API details.
   - Decide whether each action should use direct COM or macro/VBA fallback.

3. Execute
   - Use a local execution engine with explicit modes:
     - model import/open
     - drawing create/open
     - view placement
     - annotation/dimension
     - save/export

4. Verify
   - Structural verification:
     - drawing file saved
     - views exist
     - export produced
   - Standards verification:
     - projection method
     - title block
     - dimensioning/tolerances/GD&T as applicable
     - checklist pass/fail

## Recommended Tool Routing Rules

- If the job is `drawing`, expose only drawing creation, annotation, export, and drawing-analysis tools.
- Keep model-editing tools out of the active toolset unless the agent explicitly needs to repair the source model first.
- Do not mark a drawing task successful until:
  - `.SLDDRW` exists
  - exported PDF exists
  - checklist verification has run

## Priority Build Plan For The New Interface

1. Start from `SolidworksMCP-TS` structure.
2. Vendor or port the proven Python/COM execution pieces that actually worked live.
3. Keep macro/VBA fallback as a first-class recovery strategy.
4. Add strict result contracts so simulated success cannot masquerade as real completion.
5. Add guideline-aware verification before final export.

## Bottom Line

No single example in this folder is the complete answer.

The best path is to combine:

- `SolidworksMCP-TS` for interface/module design,
- `SolidworksMCP-python` for the currently most credible live execution path,
- `swapi-pilot` for API retrieval,
- `guidelines/` for standards enforcement and verification.

That is the most practical route to a good agent-to-SolidWorks drawing interface for automated drawing creation from STEP or SolidWorks files.
