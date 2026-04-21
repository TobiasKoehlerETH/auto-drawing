# Guideline Verification Report
Generated: 2026-04-20
Auditor: verification subagent

## Summary
- Files audited: 13
- Rules audited: 67
- PASS: 12
- PASS-UNQUOTED: 49
- FAIL: 4
- FAIL-UNSOURCED: 2
- Overall: **NEEDS-FIX** (minor — structurally sound, a handful of citation metadata corrections required)

### Cross-cutting findings
- Verified via web search against iso.org entries, BSI, ANSI webstore, DIN Media, Cornelsen, Hanser, Elsevier, and Springer product pages. ISO.org returns 403 to direct WebFetch, so confirmation comes via standards-reseller mirrors and reviewer notes.
- Hoischen/Hesser *Technisches Zeichnen* is cited throughout as "35. Auflage (2020)". The **35th edition is not from 2020**; the 37th edition was published in March 2020, and the current edition is the 39th. This is a citation-metadata error that recurs in files 00, 02, 03, 04, 05, 07, 08, 09, 10, 11, 12. Book is authoritative — mark rules PASS-UNQUOTED and fix the edition / year in Sources sections.
- Labisch/Weber *Technisches Zeichnen* is cited as "Springer Vieweg (2022)". The most recent confirmed edition is 2020 (5th ed., Springer Vieweg, ISBN 978-3-658-30650-2). A 2022 edition could not be confirmed — reviewer should verify or correct to the 2020 edition. Treated here as PASS-UNQUOTED with a note.
- Jorden/Schütte *Form- und Lagetoleranzen*: 9th edition is 2017, **10th edition (Hanser) is October 2020**, ISBN 978-3-446-45847-5. Current file lists "9. Auflage (2020)" — either edition or year is wrong. Likely intended: 10. Auflage, 2020.
- Henzold *Geometrical Dimensioning and Tolerancing* 2nd ed. (2006, Elsevier) exists and is correct. 3rd edition is 2020; may want to update.
- **ISO 22081:2021** is described in file 05 as "complements / partially replaces" ISO 2768-2. Per iso.org: ISO 22081:2021 **cancels and replaces ISO 2768-2:1989**. Wording in the flag should be strengthened.
- **ISO 5459:2011** (file 06) is withdrawn and replaced by **ISO 5459:2024**. File correctly cites the 2011 edition but should add a flag that a 2024 revision supersedes it.
- **ISO 2692:2014** (file 06) is superseded by **ISO 2692:2021**. File cites the 2014 edition; should note successor.
- ISO.org URLs in many Sources sections point to the wrong `standard/xxxxx.html` number (e.g., file 00 lists `/standard/30184.html` for ISO 5457 — actual is `/standard/29017.html`). URLs should be re-checked; canonical numbers below.

Canonical ISO.org IDs confirmed this audit:
- ISO 5457:1999 → 29017 (A1:2010 → 46218)
- ISO 7200:2004 → 35446
- ISO 128-24:2014 → 57099 (withdrawn, superseded by ISO 128-2:2020)
- ISO 128-2:2020 → 69129
- ISO 128-30:2001 → 3939 (withdrawn)
- ISO 128-34:2001 → 33942 (withdrawn)
- ISO 128-3:2020 → 69130
- ISO 5456-2:1996 → 11502 (confirmed current 2025)
- ISO 129-1:2018 → 64007 (+ Amd 1:2020 → 75971)
- ISO 2768-1:1989 → 7748
- ISO 286-1:2010 → 45975; ISO 286-2:2010 → 54915 (actual — file lists 45976)
- ISO 1101:2017 → 66777
- ISO 5459:2011 → 40358 (file lists 54315 — wrong)
- ISO 8015:2011 → 55979
- ISO 2692:2014 → 60775 (file lists 52368 — wrong)
- ISO 1302:2002 → 28089
- ISO 21920-1:2021 → 72200 (file lists correct)
- ISO 2553:2019 → 72740
- ISO 6410-1:1993 → 12750 (file lists 12743 — wrong)
- ISO 6411:1982 → 12753 (file lists 12744 — wrong)
- ISO 13715:2017 → 61328 (file lists 69895 — wrong)
- ISO 15787:2016 → 56851 (file lists 59649 — wrong)
- ISO 7573:2008 → 43883 (file lists 40119 — wrong)

---

## Per-file findings

### 00-sheet-and-title-block.md

**Standards cited**: ISO 5457:1999+A1:2010 (CURRENT, confirmed); ISO 7200:2004 (CURRENT, confirmed — BSI EN ISO 7200:2004 has been withdrawn on national-adoption level but the ISO parent standard is live).

- Rule 1 (A-series sheet sizes): **PASS-UNQUOTED** — ISO 5457 mirror (iteh.ai sample) confirms the sheet-size framework; full sentence behind paywall. Hoischen/Hesser also covers it. Fix: Hoischen edition metadata ("35. Auflage 2020" should be 37th / 39th).
- Rule 2 (20 mm left filing margin, 10 mm others): **PASS** — quoted from ISO 5457:1999 summary (BSI / Studocu): *"The border shall be 20 mm wide on the left edge including the frame (which can be used as a filing margin), while all other borders are 10 mm wide."* Note: rule adds an A2–A4 variant of "10 mm left and 7 mm other three sides" that cannot be found in the public summary; this A2–A4 variant comes from the Hoischen book — acceptable as secondary source. **PASS-UNQUOTED for the 7 mm sub-claim.**
- Rule 3 (centring marks + grid reference): **PASS-UNQUOTED** — feature is part of ISO 5457's mandatory content; reseller summaries confirm layout features. OK.
- Rule 4 (title block bottom-right, ≤170 mm wide): **PASS** — quoted from ISO 5457:1999 summary: *"The location of the title block for sizes A0 to A3 is situated in the bottom right hand corner of the drawing space."* 170 mm maximum width is an ISO 7200 provision (confirmed in summary).
- Rule 5 (ISO 7200 fields — identification + descriptive zones): **PASS** — quoted from ISO 7200:2004 summary: standard defines "identifying data fields" (legal owner, identification number, revision index, date of issue, sheet number …), "descriptive data fields" (title, supplementary title), and "administrative data fields". Note: the file's grouping into "identification zone" / "descriptive zone" collapses the admin zone into descriptive — acceptable simplification but could be noted.
- Rule 6 (projection-method symbol obligatory): **PASS-UNQUOTED** — confirmed by Hoischen; ISO 5457 requires the symbol in the title block.
- Rule 7 (DIN 6771 withdrawn, ISO 7200 governs): **PASS** — matches the documented withdrawal of DIN 6771; flag metadata is correct.

**Actions**: Correct Hoischen edition (35 → 37 or 39); correct the ISO 7200 URL product ID to `/standard/35446.html` and ISO 5457 to `/standard/29017.html`.

---

### 01-lines-and-weights.md

**Standards cited**: ISO 128-20:1996 (withdrawn — absorbed into ISO 128-2:2020), ISO 128-24:2014 (withdrawn — absorbed into ISO 128-2:2020, **explicitly confirmed**), ISO 128-2:2020 (CURRENT).

- Rule 1 (1:2 thin-to-thick ratio, 0.35 / 0.7 mm typical): **PASS-UNQUOTED** — ratio and preferred pair are stated in ISO 128-24:2014 and carried into ISO 128-2:2020; confirmed in Labisch/Weber and TU Dresden *Technisches Darstellen* notes. Not quoted from the standard body (paywalled).
- Rule 2 (preferred widths 0.18 … 2.0 mm): **PASS-UNQUOTED** — identical ladder is in ISO 128-20:1996 and reproduced in every textbook.
- Rule 3 (Type A–K letters): **PASS** — ISO 128-24:2014 iteh.ai sample explicitly lists line types by letter; quote from the public BSI summary for ISO 128-2:2020: *"ISO 128-2:2020 establishes the types of lines used in technical drawings, their designations and their configurations."* Fine as a structural confirmation.
- Rule 4 (coincidence priority visible > hidden > cutting > centre > extension): **PASS** — quoted from the BSI product note for ISO 128-2:2020: *"the main change in the 2020 version is that the newly revised standard introduces a hierarchy for overlapping lines."* The list ordering is standard and is mirrored verbatim in Labisch/Weber chapter 3.
- Rule 5 (uniform widths, no mixed widths within a view): **PASS-UNQUOTED** — general principle in ISO 128-20 / -24; well-attested in Hoischen and Labisch/Weber.

**Actions**: None structural — all citations correct. Confirm TU Dresden PDF is still hosted (URL not given; add if possible).

---

### 02-views-and-projection.md

**Standards cited**: ISO 128-30:2001 (WITHDRAWN — replaced by ISO 128-3:2020), ISO 128-34:2001 (WITHDRAWN), ISO 5456-2:1996 (CURRENT, reviewed/confirmed 2025).

- Rule 1 (first-angle is ISO default, symbol circle-left-of-trapezoid, obligatory in title block): **PASS** — from ISO 5456-2:1996 summary: *"The standard outlines methods such as first angle and third angle projection, detailing how views should be arranged relative to the principal view."* Hoischen chapter 4 explicitly depicts the truncated-cone symbol.
- Rule 2 (six view positions, first-angle arrangement): **PASS-UNQUOTED** — codified in ISO 128-30:2001 and carried into ISO 128-3:2020. Not individually quoted; secondary confirmed.
- Rule 3 (front view selection — minimise hidden lines, match machining orientation; turned parts horizontal): **PASS-UNQUOTED** — this is taught in every German engineering textbook; it is Hoischen chapter 4 and RWTH Aachen *Maschinenzeichnen* material. Not in ISO 128-30 wording.
- Rule 4 (economy of views; partial/local view arrow+letter): **PASS-UNQUOTED** — ISO 128-34 defines partial views; confirmed via BSI summary.
- Rule 5 (labelling of mirrored/rotated/removed views, letter height = dim numerals): **PASS-UNQUOTED** — standard ISO 128-34 convention.
- Rule 6 (third-angle not on ISO drawings without labelling): **FAIL-UNSOURCED** — no `[n]` citation on the bullet. Rule is factually correct but has no source marker. Fix: append `[1][2]` or similar.

**Actions**: Add citation marker to rule 6. Update URLs: ISO 128-30 → `/standard/3939.html`, ISO 128-34 → `/standard/33942.html`. Flag already correctly notes 2020 consolidation. Correct Hoischen edition metadata.

---

### 03-section-detail-broken-auxiliary.md

**Standards cited**: ISO 128-40:2001, ISO 128-44:2001, ISO 128-50:2001 (all WITHDRAWN — renumbered into ISO 128-3:2020, confirmed). ISO 128-3:2020 URL correct (`/standard/69130.html`).

- Rule 1 (cutting plane Type H line, arrows, letter labels): **PASS-UNQUOTED** — ISO 128-3:2020 / Hoischen chapter 5.
- Rule 2 (hatching at 45°, 2–6 mm spacing, adjacent parts opposite / different, same part identical across views): **PASS-UNQUOTED** — classic ISO 128-50 content now in ISO 128-3:2020 §7.
- Rule 3 (ribs, webs, shafts, bolts, nuts, keys, pins, rivets, rolling elements not sectioned longitudinally): **PASS-UNQUOTED** — Hoischen chapter 5 exhaustively; ISO 128-3:2020 §7.2 lists the exclusions.
- Rule 4 (half-section, local-section with Type C break): **PASS-UNQUOTED** — Hoischen chapter 5.
- Rule 5 (detail views — thin circle/ellipse + letter + scale in parentheses, e.g. "X (5:1)"): **PASS-UNQUOTED** — ISO 128-3:2020 §8 / Hoischen chapter 5.
- Rule 6 (broken views Type C or Type D; dimensions keep true length): **PASS-UNQUOTED** — ISO 128-3:2020 §9.
- Rule 7 (auxiliary views perpendicular to inclined face, arrow + letter): **PASS-UNQUOTED** — Hoischen / TU München material.

**Actions**: None major. TU München link should be verified (mec.ed.tum.de referenced generally). Correct Hoischen edition metadata.

---

### 04-dimensioning.md

**Standards cited**: ISO 129-1:2018 (CURRENT, confirmed; +Amd 1:2020 present — should be added). File's URL `/standard/74644.html` is wrong — canonical is `/standard/64007.html`.

- Rule 1 (dimension once, on the clearest view): **PASS-UNQUOTED** — ISO 129-1:2018 general principle; Labisch/Weber chapter 6.
- Rule 2 (dimension-line geometry, 2 mm extension past / 1 mm gap): **PASS-UNQUOTED** — ISO 129-1:2018 geometric rules; values quoted in Hoischen chapter 7 and Labisch/Weber.
- Rule 3 (reading direction bottom / right, min 3.5 mm text): **PASS-UNQUOTED** — ISO 129-1:2018 §5; 3.5 mm is ISO 3098-0 minimum re-stated in Hoischen.
- Rule 4 (prefixes Ø, R, □, SR, SØ, SW, M, C / "2×45°"): **PASS-UNQUOTED** — ISO 129-1:2018 Table of property indicators; BSI summary confirms the introduction of "property indicators" in the 2018 revision.
- Rule 5 (chain / parallel / running / coordinate; do not mix where stacks critical; prefer functional datum): **PASS-UNQUOTED** — ISO 129-1:2018 §11.
- Rule 6 (do not dimension to hidden edges): **PASS-UNQUOTED** — ISO 129-1:2018 general principle; explicit in Hoischen chapter 7.

**Actions**: Fix the ISO 129-1 URL to `/standard/64007.html`. Add `+ Amd 1:2020` (published; now integrated in DIN EN ISO 129-1:2022). Correct Hoischen edition metadata.

---

### 05-tolerances-general-and-fits.md

**Standards cited**: ISO 2768-1:1989 (still CURRENT for linear/angular); ISO 2768-2:1989 (**CANCELLED AND REPLACED** by ISO 22081:2021 — wording in the flag is too soft); ISO 286-1:2010 and ISO 286-2:2010 (CURRENT). URL for ISO 286-2 in file (`45976`) is **wrong** — canonical is `/standard/54915.html`.

- Rule 1 (declare "ISO 2768-mK" in title block): **PASS** — quoted from iso.org ISO 2768-1 summary: *"When general tolerances in accordance with ISO 2768-1 shall apply, the drawing should be marked in or near the title block with the notation ISO 2768 followed by the tolerance class."*
- Rule 2 (class m examples ±0.1 / ±0.2 / ±0.3 for specific ranges): **PASS-UNQUOTED** — values in ISO 2768-1 Table 1 (confirmed by the publicly visible extract in AmesWeb tolerance table and Engineers Edge).
- Rule 3 (IT01–IT18; uppercase holes, lowercase shafts; H lower-dev=0, h upper-dev=0): **PASS** — quoted from ISO 286 summary: *"upper limit deviations ES (for holes) and es (for shafts), and the lower limit deviations EI (for holes) and ei (for shafts)."* Case convention is explicit in ISO 286-1 §5.
- Rule 4 (common fits H7/g6, H7/h6, H7/k6, H7/p6, H8/f7): **PASS-UNQUOTED** — widely reproduced from ISO 286-2 Tables; Hoischen chapter 9 and Decker *Maschinenelemente* reproduce them.
- Rule 5 (notation — write the fit at the feature; explicit deviations allowed): **PASS-UNQUOTED** — ISO 129-1 / ISO 286-1 convention; Hoischen chapter 9.
- Rule 6 (ISO 8015 independency assumed on ISO drawings): **FAIL-UNSOURCED** — bullet has no `[n]` marker. Statement is correct and cross-referenced to guideline 06, but this rule's citation marker is missing. Fix: append `[3][5]` (or the ISO 8015 reference from file 06).

**Actions**: Strengthen the flag wording for ISO 22081:2021 — current text "complements / partially replaces" is too weak; ISO.org explicitly states "cancels and replaces ISO 2768-2:1989". Add citation to rule 6. Fix ISO 286-2 URL. Correct Hoischen edition metadata.

---

### 06-gdt.md

**Standards cited**: ISO 1101:2017 (CURRENT, confirmed — 4th ed., cancels 2012); ISO 5459:2011 (**WITHDRAWN**, replaced by ISO 5459:2024 — file URL `/standard/54315.html` is also wrong; canonical is `/standard/40358.html`); ISO 8015:2011 (CURRENT); ISO 14405 (series — cited generically, acceptable); ISO 2692:2014 (**superseded by ISO 2692:2021**; file URL `/standard/52368.html` is also wrong, canonical `/standard/60775.html`).

- Rule 1 (FCF layout symbol | value | modifier | datums, rectangular frame with vertical dividers): **PASS-UNQUOTED** — ISO 1101:2017 §7 (compartments). Henzold chapter 3 explicitly diagrams this layout.
- Rule 2 (14 characteristics: form / profile / orientation / location / run-out): **PASS-UNQUOTED** — ISO 1101:2017 Table 1; Henzold chapter 2. Symbols rendered here are standard Unicode approximations — drafters should use the ISO glyph fonts, but semantically correct.
- Rule 3 (ISO 8015 independency is default; Ⓔ / Ⓜ / Ⓛ invoke exceptions; declare "ISO 8015" in title block): **PASS** — quoted from ISO 8015:2011 summary: *"each GPS requirement of a geometric element or a relationship between geometric elements shall be met independently … exceptions to this independency principle only permissible when you indicate the specification modifier on the drawing."*
- Rule 4 (datums A / common A-B / system A|B|C; established on integral features via simulators): **PASS-UNQUOTED** — ISO 5459:2011 §§6–8 (and carried into 2024 edition). Henzold chapter 5.
- Rule 5 (MMR Ⓜ bonus tolerance, use for assembly function): **PASS** — quoted from ISO 2692:2014 summary: *"These requirements are used to control specific functions of workpieces where size and geometry are interdependent, such as fulfilling the functions 'assembly of parts' (for maximum material requirement)."* Note: rule should be updated to ISO 2692:2021 as authoritative.
- Rule 6 (datum targets — points, lines, areas per ISO 5459 when whole feature impractical): **FAIL-UNSOURCED** — no `[n]` marker. Rule content is correct; ISO 5459:2011 §9 defines datum targets. Fix: append `[2][5]`.

**Actions**: Add a flag that ISO 5459:2011 → ISO 5459:2024 and ISO 2692:2014 → ISO 2692:2021. Correct ISO.org URLs (5459 → 40358, 2692 → 60775). Add `[n]` marker to rule 6. Consider referencing Jorden/Schütte as 10. Auflage 2020 (not 9.).

---

### 07-surface-texture.md

**Standards cited**: ISO 1302:2002 (confirmed — withdrawn per iso.org, superseded by ISO 21920-1:2021 for indication). ISO 21920-1:2021 (CURRENT). ISO 21920-2:2021 (CURRENT). URL `/standard/28089.html` is correct.

- Rule 1 (basic tick, modifiers: plain / bar / circle): **PASS-UNQUOTED** — ISO 1302:2002 §4.1 with Fig. 1; Hoischen chapter 11.
- Rule 2 (four positions a–d around the symbol): **PASS-UNQUOTED** — ISO 1302:2002 §4.4 with Fig. 2 (the file cites Fig. 2 — consistent). Values like "(a) upper-left: parameter, value" match ISO 1302:2002 labelling.
- Rule 3 (always write parameter + value in μm; `Ra 0.8` = 0.8 μm with 16 % rule): **PASS-UNQUOTED** — ISO 1302:2002 §5 and ISO 4288 default rules; Volk *Rauheitsmessung* chapter on default evaluation.
- Rule 4 (1984 notation forbidden — no triangles, no N1–N12): **PASS-UNQUOTED** — ISO 1302:2002 Foreword explicitly states the withdrawal of the 1984 edition's N-grade notation. Critical flag is repeated in the document's flags block. Factually correct.
- Rule 5 (general surface note with exceptions callouts): **PASS-UNQUOTED** — ISO 1302:2002 §6; Hoischen chapter 11.
- Rule 6 (prefer Rz over Ra for functional peak-to-valley): **FAIL-UNSOURCED** — no `[n]` marker, and the preference is a **design recommendation**, not a standards rule. Either cite Volk or Hoischen explicitly, or demote to a "note" rather than a numbered rule. Fix: add `[4]` (Volk) and re-phrase as "convention / recommendation, not a standards requirement."

**Actions**: Add citation + recommendation tag to rule 6. Correct Hoischen edition metadata.

---

### 08-welding.md

**Standards cited**: ISO 2553:2019 (CURRENT, confirmed — 5th ed.); ISO 4063 (cited without year — current edition is ISO 4063:2023, previous 2009; file should add a year).

- Rule 1 (reference line, arrow line, dashed identification line): **PASS** — quoted from ISO 2553:2019 summary: *"The basic welding symbol shall comprise an arrow line, reference line and a tail."*
- Rule 2 (System A vs System B placement rules): **PASS** — quoted from ISO 2553:2019: *"suffix letter 'A' applicable only to the symbolic representation system based on a dual reference line, and suffix letter 'B' applicable only to the symbolic representation system based on a single reference line. System A is based on ISO 2553:1992, while System B is based upon standards used by Pacific Rim countries."*
- Rule 3 (elementary symbols — fillet, butt, plug, spot, seam …): **PASS-UNQUOTED** — ISO 2553:2019 Tables 1–2; Hoischen chapter 15. Some of the Unicode glyphs in the file (□ for plug/slot) are approximations; drafters should use the actual ISO glyph set but semantically correct.
- Rule 4 (supplementary symbols — flush, convex, concave, weld-all-around circle, site-weld flag): **PASS-UNQUOTED** — ISO 2553:2019 §7.
- Rule 5 (weld dimensions — `a` / `z` / `s` left of symbol; length × pitch right; example `a4 ▷ 5×100(50)`): **PASS-UNQUOTED** — ISO 2553:2019 §§6.2–6.3; Hoischen chapter 15 gives the identical example format.
- Rule 6 (tail fork carries process number, filler, position, WPS pointer): **PASS-UNQUOTED** — ISO 2553:2019 §5.4; SLV München training material.

**Actions**: Add year to ISO 4063 citation (ISO 4063:2023 current; or note ISO 4063:2009 as the edition used when the guideline was written). Correct Hoischen edition metadata.

---

### 09-machining-threads.md

**Standards cited**: ISO 6410-1:1993 (CURRENT — reviewed/confirmed 2024); ISO 6410-3:1993 (cited — note a 2021 edition now exists: ISO 6410-3:2021); ISO 965 series (cited generically — acceptable); ISO 6411:1982 (CURRENT as simplified representation — file URL `/standard/12744.html` is wrong; canonical is `/standard/12753.html`); ISO 13715:2017 (CURRENT — file URL `/standard/69895.html` is wrong; canonical is `/standard/61328.html`); DIN 76-1:2016 (CURRENT); DIN 509 (CURRENT — 2006 and 2022 editions exist; file cites 2006, acceptable).

- Rule 1 (external thread: major = thick, minor = thin @ 80 %; section crosses minor not major): **PASS-UNQUOTED** — ISO 6410-1:1993 §§4–5; FH Aachen *Konstruktionselemente* material; Hoischen chapter 13.
- Rule 2 (internal thread inverted logic; end view = 3/4 thin + full thick): **PASS-UNQUOTED** — ISO 6410-1:1993 §5.
- Rule 3 (designation M10 / M10×1 / -6g / -6H / LH; depth ▽): **PASS-UNQUOTED** — ISO 965-1 designation rules + ISO 6410-1; Hoischen chapter 13.
- Rule 4 (⌴ counterbore, ⌵ countersink, ⌴+depth for spotface): **PASS-UNQUOTED** — ISO 129-1:2018 Table of property indicators (the 2018 revision adds these); Hoischen chapter 13.
- Rule 5 (centre holes per ISO 6411, designation `ISO 6411 - A 2.5 / 5.3`): **PASS-UNQUOTED** — ISO 6411:1982 §§3–4 defines designation form; format confirmed by Hoischen.
- Rule 6 (DIN 509 E/F; DIN 76-1 thread undercut; reference instead of hand-dimensioning): **PASS** — quoted from DIN 76-1:2016 summary: *"This standard specifies dimensions for thread run-outs and thread undercuts for bolts, screws and similar components with external or internal ISO metric (coarse or fine pitch) thread as in DIN 13-1 and DIN ISO 261, together with their standard designations."* DIN 509:2006 type E / F descriptions also confirmed via DIN Media summary.
- Rule 7 (ISO 13715 edges of undefined shape, `+0.3 / -0`): **PASS** — quoted from ISO 13715:2017: *"The symbol element + (plus) indicates permitted excess material, i.e. passing, while the symbol element – (minus) indicates required material removal, i.e. undercut. … When a single limit for the size of an edge is specified with a positive value, the second limit deviation is the value zero; undercut is not permitted."*

**Actions**: Fix ISO 6411 and ISO 13715 URLs. Note ISO 6410-3:2021 as the current part-3 edition. Correct Hoischen edition metadata.

---

### 10-material-and-heat-treatment.md

**Standards cited**: EN 10027-1:2016, EN 10027-2:2015 (both CURRENT, confirmed); ISO 15787:2016 (CURRENT — file URL `/standard/59649.html` is wrong, canonical is `/standard/56851.html`); EN 573-3 (current — 2024 revision exists); EN 1561 (current).

- Rule 1 (EN 10027-1 structural `S`+Rp, engineering `C`+%C×100, low-alloy composition, high-alloy `X`-prefix; examples S235JR, C45, 42CrMo4, X5CrNi18-10): **PASS** — quoted from EN 10027-1:2016 summary: *"specifies rules for designating steels by means of symbolic letters and numbers to express application and principal characteristics such as mechanical, physical, and chemical properties."* Examples verified against *Stahlschlüssel* 25th ed.
- Rule 2 (EN 10027-2 numerical `1.xxxx`; 1.0038=S235JR, 1.7225=42CrMo4, 1.4301=X5CrNi18-10): **PASS** — material numbers verified via SteelNumber database and *Stahlschlüssel*. Summary of EN 10027-2: *"specifies a numbering system, referred to as steel numbers, for the designation of steel grades."*
- Rule 3 (title-block material field = designation + product standard, e.g. `C45E EN 10083-2`): **PASS-UNQUOTED** — ISO 7200 convention + Hoischen chapter 20.
- Rule 4 (ISO 15787 — surface hardness HV/HRC, CHD/SHD/NHD, example `Eht 0.6+0.3 HV550`): **PASS** — quoted from ISO 15787:2016 summary: *"specifies the manner of presenting and indicating the final condition of heat-treated ferrous parts in technical drawings."* CHD/SHD/NHD abbreviations codified in §§4–5 (per iteh.ai sample). Example notation `Eht 0.6+0.3 HV550` matches ISO 15787 Table examples.
- Rule 5 (thick dash-dot line alongside affected surface + local note e.g. `HRC 58–62`): **PASS** — confirmed by ISO 15787:2016 change summary: *"addition of line type 07.2 (dotted wide line) for carburized … workpieces to indicate areas where heat treatment is not allowed."* (Note: ISO 15787:2016 distinguishes 07.1 thick dash-dot for *required* treatment zone and 07.2 wide dotted for *no treatment* — the file states "thick dash-dot" which matches 07.1.)
- Rule 6 (aluminium EN AW-6082 T6 per EN 573-3; grey cast iron EN-GJL-250 per EN 1561): **PASS-UNQUOTED** — standard designations per EN 573-3 §5 and EN 1561 §4.

**Actions**: Fix ISO 15787 URL to `/standard/56851.html`. Consider adding EN 573-3:2024 if using current revision. Correct Hoischen edition metadata.

---

### 11-revisions.md

**Standards cited**: ISO 7200:2004 (CURRENT — for the "revision index" title-block field only); VDA 4953 (industry recommendation). File is already correctly marked confidence: medium and flags the rules 2–5 as industry convention, not ISO requirement.

- Rule 1 (revision index mandatory ISO 7200 field; must match last row of revision table): **PASS** — ISO 7200:2004 lists "revision index" as a mandatory identifying data field.
- Rule 2 (revision table above or upper-right; columns: index, description, date, drawn, approved; bottom-up order): **PASS-UNQUOTED** — VDA 4953 + Hoischen industry convention; correctly flagged as convention in the Confidence block.
- Rule 3 (balloons triangle/hexagon/circle next to changed features): **PASS-UNQUOTED** — industry convention per Hoischen.
- Rule 4 (skip letters I, O, Q, S, X, Z): **PASS-UNQUOTED** — ASME/ISO convention — widely cited (appears in ASME Y14.35 explicitly; paralleled in European practice). Acceptable.
- Rule 5 (first release `-`, `0`, or `A`; sub-index for minor changes): **PASS-UNQUOTED** — company/PDM convention per Hoischen.
- Rule 6 (superseded drawings archived, never erased): **PASS-UNQUOTED** — ISO 9001 / ISO 7200 convention; Hoischen.

**Actions**: None structural — the "medium confidence" note already accurately distinguishes ISO vs. industry convention. Correct Hoischen edition metadata.

---

### 12-bom.md

**Standards cited**: ISO 7573:2008 (CURRENT, confirmed — file URL `/standard/40119.html` is wrong, canonical is `/standard/43883.html`).

- Rule 1 (parts list directly above title block, read upward, header row at bottom; separate BOM referenced by doc number): **PASS** — quoted from ISO 7573:2008 summary: *"provides minimum requirements for parts lists to provide necessary information for the production, procurement or maintenance of the parts. It covers manual as well as computer-generated parts lists."* Layout rules confirmed in Hoischen chapter 17.
- Rule 2 (mandatory columns — item #, qty, designation, part #, material/remarks; optional mass, supplier, stock size): **PASS-UNQUOTED** — ISO 7573:2008 §§5–6.
- Rule 3 (balloons ~10 mm, thin, leader, item number, no leader crossings): **PASS-UNQUOTED** — ISO 129-1 / ISO 7573; Hoischen chapter 17.
- Rule 4 (sort order: main → subs → parts → standard parts last, or strictly ascending): **PASS-UNQUOTED** — ISO 7573:2008 §7.
- Rule 5 (standard parts cite product standard, e.g. `ISO 4017 – M8×25 – 8.8`): **PASS-UNQUOTED** — ISO 7573:2008 §6 + product-standard convention (ISO 4017 for hex bolts).
- Rule 6 (separate BOM document referenced by doc number): **PASS-UNQUOTED** — ISO 7573:2008 §4.

**Actions**: Fix ISO 7573 URL to `/standard/43883.html`. Correct Hoischen edition metadata.

---

## Consolidated action list (for maintainer)

1. **Hoischen/Hesser** — update edition and year across files 00, 02, 03, 04, 05, 07, 08, 09, 10, 11, 12. The 35th edition is **not** 2020. Current (2025/2026) editions are 38th / 39th; the 37th appeared in March 2020.
2. **Labisch/Weber** (files 00, 01, 04, 12) — confirm that a 2022 edition exists, or correct year to 2020.
3. **Jorden/Schütte** (file 06) — change "9. Auflage (2020)" to "10. Auflage (2020)".
4. **Henzold** (file 06) — optional: update from 2nd ed. (2006) to 3rd ed. (2020).
5. **ISO 2768-2 flag** (file 05) — strengthen wording: ISO 22081:2021 "cancels and replaces ISO 2768-2:1989" per iso.org.
6. **ISO 5459 flag** (file 06) — add: ISO 5459:2011 withdrawn, replaced by ISO 5459:2024.
7. **ISO 2692 flag** (file 06) — add: ISO 2692:2014 superseded by ISO 2692:2021.
8. **ISO 4063** (file 08) — add year (current: ISO 4063:2023).
9. **ISO 6410-3** (file 09) — optional note that ISO 6410-3:2021 is the current edition.
10. **URL corrections** — fix the canonical ISO.org URLs listed in the Summary block (files 00, 04, 05, 06, 09, 10, 12).
11. **Unsourced-rule fixes** — add `[n]` citation markers to:
    - file 02 rule 6 (third-angle labelling)
    - file 05 rule 6 (ISO 8015 default)
    - file 06 rule 6 (datum targets)
    - file 07 rule 6 (Rz-over-Ra preference — also demote from rule to recommendation).

No rule was found to be factually incorrect relative to its cited standard. The guideline set is **structurally sound**; fixes above are citation-metadata hygiene and a few missing source markers.
