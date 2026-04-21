# Drawing Verification Checklist

Flat, testable checklist derived from the topic guides in this folder. Used by the optical feedback loop as the rubric when auditing an exported PNG.

Every item is a binary PASS / FAIL with visible evidence.

---

## A. Sheet & Title Block — [guideline 00](00-sheet-and-title-block.md)

- [ ] A.1 Sheet size matches declared size.
- [ ] A.2 Border and filing margin are present.
- [ ] A.3 Centring marks are visible.
- [ ] A.4 Title block is in the bottom-right corner.
- [ ] A.5 Units, scale, material, revision, and sheet numbering are filled.
- [ ] A.6 General tolerance note is present.
- [ ] A.7 Projection symbol is present and matches the layout.
- [ ] A.8 No text or model lines overlap the title block.

## B. Lines — [guideline 01](01-lines-and-weights.md)

- [ ] B.1 Visible edges are thicker than hidden and centre lines.
- [ ] B.2 Hidden lines are dashed thin.
- [ ] B.3 Centre lines are present on circular features.
- [ ] B.4 Cutting plane lines are visually distinct.
- [ ] B.5 Dimension, extension, leader, and hatching lines are thin.

## C. Views & Projection — [guideline 02](02-views-and-projection.md)

- [ ] C.1 Front view shows the functional orientation.
- [ ] C.2 Views follow the declared first-angle or third-angle layout.
- [ ] C.3 No redundant full views are present when sections or details would be clearer.
- [ ] C.4 Removed or rotated views are lettered.
- [ ] C.5 Pictorial view, if present, is supplementary only.
- [ ] C.6 Orthographic views use hidden lines visible.
- [ ] C.7 The isometric view is compact, bottom-right, shaded with edges, and scaled `1:2`.
- [ ] C.8 Only the isometric recognition view is shaded / colored; orthographic views are not.

## D. Sections / Details / Auxiliaries — [guideline 03](03-section-detail-broken-auxiliary.md)

- [ ] D.1 Section views have labelled cutting planes.
- [ ] D.2 Hatching is consistent and readable.
- [ ] D.3 Exempt parts such as shafts or fasteners are not incorrectly sectioned longitudinally.
- [ ] D.4 Detail views show the parent location and scale.
- [ ] D.5 Broken or auxiliary views are clearly identified.

## E. Dimensioning — [guideline 04](04-dimensioning.md)

- [ ] E.1 Every essential dimension appears once.
- [ ] E.2 Extension and dimension lines are drawn cleanly.
- [ ] E.3 Text orientation is consistent enough to read.
- [ ] E.4 Correct symbols are used: `Ø`, `R`, `SR`, `SØ`, `□`, `M`, `C`.
- [ ] E.5 Hidden lines are not used as the primary dimension target.
- [ ] E.6 Vertical and horizontal ordinate dimensions are used as the top-priority method where the geometry allows.
- [ ] E.7 Radius variants are explicit where needed: `R`, `RMIN`, `RMAX`, `CR`, or `SR`.
- [ ] E.8 Repeated features use `2×`, `4×`, `TYP`, or similar multiplicity.
- [ ] E.9 Dimension values are not shown in brackets or parentheses.
- [ ] E.10 Dimension lines, leaders, and value text do not overlap each other.

## F. Tolerances & Fits — [guideline 05](05-tolerances-general-and-fits.md)

- [ ] F.1 Title block declares a general-tolerance class such as `ISO 2768-mK`.
- [ ] F.2 Fit callouts use correct case: uppercase for holes, lowercase for shafts.
- [ ] F.3 Deviation style is consistent: `±`, unilateral, limit, or fit code.
- [ ] F.4 Reference dimensions are clearly non-controlling.
- [ ] F.5 Basic dimensions are boxed and paired with GD&T where required.

## G. GD&T — [guideline 06](06-gdt.md)

- [ ] G.1 Title block declares `ISO 8015` when GD&T is used.
- [ ] G.2 Feature control frames read left-to-right with symbol, value, modifier, and datums.
- [ ] G.3 Datum letters are clearly attached to real datum features.
- [ ] G.4 `Ⓜ` or `Ⓛ` is placed after the tolerance value when used.
- [ ] G.5 `Ø` is shown only for cylindrical or spherical zones.

## H. Surface Texture — [guideline 07](07-surface-texture.md)

- [ ] H.1 Surface symbols use parameter + value notation.
- [ ] H.2 The parameter name is explicit (`Ra`, `Rz`, etc.).
- [ ] H.3 Local surface notes override a clear general default.
- [ ] H.4 Bar and circle variants match process intent.
- [ ] H.5 Lay is specified where the surface function depends on it.

## I. Welding — [guideline 08](08-welding.md)

- [ ] I.1 Weld symbols, if used, declare the intended ISO system.
- [ ] I.2 Arrow-side / other-side placement is correct.
- [ ] I.3 Size and length / pitch are placed on the correct sides of the symbol.

## J. Threads & Machining — [guideline 09](09-machining-threads.md)

- [ ] J.1 Internal and external thread graphics are not swapped.
- [ ] J.2 Thread family, size, pitch or TPI, and class are complete.
- [ ] J.3 `LH`, depth, or `THRU` is stated when applicable.
- [ ] J.4 Pipe thread family is explicit where sealing depends on it.
- [ ] J.5 Counterbores, countersinks, spotfaces, and thread reliefs are called out when function requires them.

## K. Material & Processes — [guideline 10](10-material-and-heat-treatment.md)

- [ ] K.1 Material callout is present and unambiguous.
- [ ] K.2 Heat-treatment notes state target hardness or case depth where relevant.
- [ ] K.3 Coatings or finishing steps state class / color / thickness where needed.
- [ ] K.4 Masked or no-coat zones are identified when the process requires them.

## L. Revisions — [guideline 11](11-revisions.md)

- [ ] L.1 Title block revision matches the latest revision row.
- [ ] L.2 Revision table contains index, description, date, and approval fields.
- [ ] L.3 Revision balloons are present for changed areas.

## M. BOM — [guideline 12](12-bom.md)

- [ ] M.1 Assembly drawings include a readable parts list.
- [ ] M.2 Item numbers match balloons.
- [ ] M.3 Standard parts are clearly identified.

## N. Symbols & Notes — [guidelines 13–14](13-symbols-and-notation.md), [14-edges-and-notes.md](14-edges-and-notes.md)

- [ ] N.1 Symbol usage is internally consistent.
- [ ] N.2 General notes define defaults; local leadered notes override only the pointed feature.
- [ ] N.3 Edge-break or deburr rule is stated globally or locally where sharp edges matter.
- [ ] N.4 Critical seating or sealing edges use explicit chamfer or radius callouts instead of vague `deburr`.

## O. Sheet Metal Bends — [guideline 15](15-sheet-metal-bends.md)

- [ ] O.1 Bend direction, angle, and inside radius are clear.
- [ ] O.2 Bend order is shown where sequence matters.
- [ ] O.3 Relief is present where material would otherwise tear or bulge.
- [ ] O.4 Flat-pattern basis is stated when non-default bend data is required.

## P. Project Overrides

- [ ] P.1 Dimension text is not duplicated by dual-unit or stacked display formatting.
- [ ] P.2 The exported sheet was regenerated from the current automation pass, not reused from a stale drawing file.
- [ ] P.3 If DimXpert was attempted, it is only treated as valid when it produced real usable annotations; otherwise the drawing relies on the verified drawing-side native path.
- [ ] P.4 Visible parenthesized dimension text has been removed after the final cleanup pass.
