# Learnings

## SolidWorks display modes in this workspace

- For this SolidWorks setup, orthographic `hidden lines visible` behaves like display mode `1`.
- For this SolidWorks setup, the small colored isometric preview behaves like display mode `3`.
- Earlier assumptions that orthographic mode should be `2` and isometric shaded-with-edges should be `5` did not match the actual rendered output for this sample.
- Always verify view display modes by exported preview image, not by enum-name assumptions alone.

## Drawing-specific visual rules confirmed by testing

- Only the small isometric recognition view should be shaded / colored.
- Orthographic views should stay line-based and show hidden lines visible.
- The isometric recognition view should not inherit hidden-line presentation from the orthographic views.

## Dimensioning behavior learned from the sample part

- Vertical and horizontal ordinate dimensions should be the top-priority dimensioning style wherever the geometry allows.
- Auto-generated dimension layouts can easily create overlapping dimension lines, leaders, and value text, so exported previews must be checked visually.
- Bracketed or parenthesized dimension values are not acceptable for this project output.
- Some SolidWorks auto-dimension schemes create parenthesized values for this sample part even when the overall layout looks cleaner.
- Auto-dimension scheme `0` produced a much cleaner baseline than some other schemes for the sample part, but it still generated at least one parenthesized value and therefore still needs cleanup.

## Auto-dimension retest summary

- Retested built-in SolidWorks `AutoDimension` schemes `0` through `5` against the sample part by exporting preview PNGs for each result.
- Scheme `2` produced no useful visible dimensions for the sample sheet and is not a viable default.
- Schemes `0`, `1`, `3`, `4`, and `5` all still produced at least one parenthesized value on the sample sheet.
- Because the project rule is now "do not use bracketed or parenthesized dimension values", the current built-in auto-dimensioning path does **not** qualify as "works well" for this repository.
- Do not document SolidWorks auto-dimensioning as a recommended default in the main guidelines until there is a reliable cleanup or replacement step that enforces the project rules.

## COM / automation quirks observed

- The generic Python `CDispatch` object is sufficient for creating views and saving drawings, but drawing-specific traversal methods were unreliable in the current helper flow.
- After creating the drawing and replacing sheets, calls such as `GetCurrentSheet()` and `GetFirstView()` could return `Member not found` even though the drawing itself was valid and savable.
- `GetSheetNames` remained callable even when `GetCurrentSheet` and `GetFirstView` were not.
- `CastTo(..., "DrawingDoc")` was blocked because the object could not automate the `makepy` process in the current environment.
- This means post-processing dimensions from Python should not assume that a newly created drawing can always be traversed through the drawing-specific COM interface without extra setup.

## Workflow lessons

- Exporting a fresh PNG preview as part of the drawing script is essential; stale previews caused false conclusions during early iterations.
- When behavior looks wrong, use tiny focused probes that export PNGs for each candidate display mode or dimensioning scheme.
- Keep the guidelines and checklist synchronized with discovered behavior so the repo standard reflects what the automation actually needs to enforce.

## DimXpert and SolidWorks-native auto-dimension retest

- A reliable DimXpert access path does exist in Python once the SolidWorks and DimXpert type libraries are generated with `makepy` and the raw COM objects are wrapped with typed interfaces.
- The working live call chain for this workspace is:
  - typed `IModelDocExtension`
  - `DimXpertManager(configuration_name, True)`
  - `IDimXpertManager.DimXpertPart`
- On the sample part copy used for this repository, that access path is real enough to read the schema name, which reported `Scheme2`.
- However, the actual part-side auto-dimensioning step is still blocked on this sample:
  - `IDimXpertPart.GetAutoDimSchemeOption()` can throw a SolidWorks server exception.
  - Earlier probes where `GetAutoDimSchemeOption()` succeeded still produced `AutoDimensionScheme(...) = False`.
  - After the full retest pass, the sample working copy still contained `0` DimXpert annotations.
- Practical conclusion: keep the DimXpert attempt in the automation as a first-pass native tool, but do **not** treat it as a working source of usable sample-part dimensions in this repo until it creates real annotations on the part.

## Typed COM wrappers improved drawing automation

- After generating the SolidWorks type library with `makepy`, wrapping raw `_oleobj_` handles with typed interfaces made drawing traversal more reliable than the earlier dynamic-only path.
- Typed `IDrawingDoc`, `IView`, `IModelDoc2`, `IAnnotation`, and `IDisplayDimension` wrappers were sufficient to:
  - call drawing-specific methods consistently
  - traverse display dimensions
  - normalize display-dimension properties after auto-dimensioning
- This typed-wrapper approach is the current best Python path for any future drawing post-processing in this workspace.

## What actually worked in the latest SolidWorks-native pass

- The latest generator now creates a disposable working part copy first:
  - `C:\Code\auto-drawing\.generated\guideline_drawing\sample_guideline_attempt.source.SLDPRT`
- This keeps the original sample part untouched while still letting SolidWorks native tools try part-side dimension generation.
- The final drawing is still recreated from scratch each run and exported fresh:
  - `C:\Code\auto-drawing\.generated\guideline_drawing\sample_guideline_attempt.SLDDRW`
  - `C:\Code\auto-drawing\.generated\guideline_drawing\sample_guideline_attempt.pdf`
  - `C:\Code\auto-drawing\.generated\guideline_drawing\sample_guideline_attempt.preview.png`

## Drawing-side native tool behavior in the latest pass

- `InsertModelAnnotations3(...)` with `dimensions marked for drawing` is still worth trying first because a focused single-view probe showed that it can create dimensions on this sample.
- In the full A3 guideline drawing pass, that import path did not produce detectable visible dimensions before the follow-up auto-dimension step, so it is not sufficient by itself for the full sheet layout.
- `InsertModelAnnotations4(...)` with a broad dimension import combination did not improve the full-sheet result for this sample.
- `IDrawingDoc.AutoDimension(...)` with SolidWorks' native ordinate-oriented settings is currently the only SolidWorks-native tool in this repo that reliably populated all three orthographic views in the final pass.
- On the latest run, the drawing-side auto-dimension call produced visible dimensions on:
  - front view
  - top view
  - right view

## Parentheses and ordinate cleanup that finally helped

- SolidWorks-native auto-dimensioning still tends to create ordinate/reference-style outputs that want to show parentheses by default.
- The latest pass improved that by applying both document-level and display-dimension-level cleanup:
  - document toggles:
    - `swDetailingDimsShowParenthesisByDefault = False`
    - `swDetailingDimensionsToleranceUseParentheses = False`
    - `swDetailingDimensionsAngularToleranceUseParentheses = False`
    - `swDetailingDimsAutoJogOrdinates = True`
    - `swDetailingOrdinateDisplayAsChain = False`
  - display-dimension cleanup:
    - `ShowParenthesis = False`
    - `ShowLowerParenthesis = False`
    - `ShowTolParenthesis = False`
- This combination materially improved the exported preview and removed the visible parenthesized values in the latest drawing export.

## Current status after the latest native-only pass

- Confirmed working:
  - orthographic views use hidden lines visible
  - only the small isometric preview is shaded/colored
  - SolidWorks-native auto-dimensioning can populate the orthographic views
  - visible parenthesized values were removed in the latest exported preview after display-dimension cleanup
- Still not fully solved:
  - the native dimension layout is still somewhat crowded in places
  - part-side DimXpert auto-dimensioning is still not producing usable annotations on the sample part
  - drawing-side native tools are good enough for a stronger automatic baseline, but not yet fully guideline-perfect without smarter layout pruning or selective repositioning
