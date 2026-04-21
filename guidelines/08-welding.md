---
topic: Welding symbols
standards:
  - ISO 2553:2019 — Welded, brazed and soldered joints — Symbolic representation on drawings
  - ISO 4063:2023 — Welding processes — numerical reference (prior edition: ISO 4063:2009)
flags:
  - ISO 2553 defines System A (ISO default) and System B (mirror of AWS A2.4). The system in use MUST be declared on the drawing.
last_verified: 2026-04-20
confidence: high
---

# 08 — Welding Symbols

## Rules

1. **Reference line** is horizontal and continuous; the **arrow line** branches from one end of the reference line and points at the joint. An **identification line** (dashed) runs above or below the reference line for the "other side". [1][2]
2. **System A (ISO default)**: elementary symbol on the **solid** reference line → weld on the arrow side; symbol on the **dashed** line → weld on the other side. **System B (mirror of AWS A2.4)** uses a single reference line with above/below placement. The drawing must state which system is used (assume System A if not stated on an ISO drawing). [1][2]
3. **Elementary symbols**: fillet (▷ triangle), butt welds (square, V, bevel, U, J, flare), plug / slot (□), spot (○), seam (⊕), backing, surfacing. Combined symbols stack elementary symbols about the reference line. [1][2]
4. **Supplementary symbols** on top of the elementary symbol: flat finish (—), convex (◠), concave (◡), flush (□), **weld all around** (circle at the arrow/reference junction), **site / field weld** (flag at the junction). [1][2]
5. **Weld dimensions**:
   - **Left of the symbol** — cross-section: `a` = design throat (fillet), `z` = leg length, `s` = penetration.
   - **Right of the symbol** — longitudinal: total length, number × length (pitch), e.g. `a4 ▷ 5×100(50)` for an intermittent fillet with throat 4 mm, five welds of 100 mm at 50 mm pitch. [1][2]
6. **Tail fork** at the open end of the reference line carries: welding process number (ISO 4063), filler metal, welding position, and a pointer to the WPS or applicable standard. [1]

## Sources

1. ISO 2553:2019 — "Welding and allied processes — Symbolic representation on drawings — Welded joints" — https://www.iso.org/standard/72740.html
2. Hoischen, H.; Hesser, W. — *Technisches Zeichnen*, 37. Auflage (2020), chapter 15 "Schweißverbindungen".
3. Schweißtechnische Lehr- und Versuchsanstalt (SLV) München — training material on ISO 2553.

## Confidence / flags

- **Flag (system)**: ISO 2553 System A ≠ System B (≈ AWS). On ISO drawings default to System A and declare it if any ambiguity exists.
- **Confidence: high**.
