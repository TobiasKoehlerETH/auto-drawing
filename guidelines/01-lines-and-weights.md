---
topic: Line types and weights
standards:
  - ISO 128-20:1996 — Basic conventions for lines
  - ISO 128-24:2014 — Lines on mechanical engineering drawings
  - ISO 128-2:2020 — consolidated re-publication (supersedes 128-20/24)
flags:
  - DIN 15 is withdrawn; ISO 128-24 / ISO 128-2:2020 apply
  - In 2020 ISO 128 was restructured; cite both the historical part and the 2020 equivalent
last_verified: 2026-04-20
confidence: high
---

# 01 — Lines and Weights

## Rules

1. **Width ratio**: thin : thick = 1 : 2. A drawing uses a consistent pair throughout — typical mechanical drawings use 0.35 mm thin and 0.7 mm thick. [1][2]
2. **Preferred standard widths** (mm): 0.18, 0.25, 0.35, 0.5, 0.7, 1.0, 1.4, 2.0. [1]
3. **Line types by function** (ISO 128-24 type letters): [1][3]
   - Type A — continuous thick → visible edges and contours
   - Type B — continuous thin → dimension, extension, leader, hatching lines
   - Type C — continuous thin freehand → short break lines
   - Type D — continuous thin zig-zag → long break lines
   - Type E / F — dashed thin → hidden edges
   - Type G — long-dash short-dash thin → centre lines, symmetry axes
   - Type H — long-dash short-dash thin with thick ends → cutting planes
   - Type K — long-dash double-short-dash thin → phantom lines, alternative positions, adjacent parts
4. **Priority at coincidence** (highest first): visible > hidden > cutting plane > centre line > projection / extension line. Only the highest-priority line is drawn. [3]
5. **Consistency**: line widths and dash patterns must be uniform across all views on a drawing; mixed widths inside one view are forbidden. [1][3]

## Sources

1. ISO 128-24:2014 — "Technical drawings — General principles of presentation — Part 24: Lines on mechanical engineering drawings" — https://www.iso.org/standard/63228.html
2. TU Dresden, Prof. R. Stelzer — lecture *Technisches Darstellen* (available as PDF on tu-dresden.de).
3. Labisch, S.; Weber, C. — *Technisches Zeichnen*, 5. Auflage, Springer Vieweg (2020), chapter 3 "Linien".
4. ISO 128-2:2020 — "Technical product documentation (TPD) — General principles of representation — Part 2: Basic conventions for lines" — https://www.iso.org/standard/76034.html

## Confidence / flags

- **Flag (withdrawn)**: DIN 15 is fully superseded; do not cite.
- **Flag (restructure)**: ISO 128-24 content is now part of ISO 128-2:2020. Dual-cite.
- **Confidence: high**.
