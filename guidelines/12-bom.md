---
topic: Parts list / Bill of Materials
standards:
  - ISO 7573:2008 — Technical product documentation — Parts lists
flags:
  - Standard-part designations defer to their own product standards (e.g. ISO 4017 for hexagon bolts)
last_verified: 2026-04-20
confidence: high
---

# 12 — Parts List / BOM

## Rules

1. **Location**: the parts list sits directly **above the title block**, read upward — so that the **header row is at the bottom**, adjacent to the title block. For complex assemblies, the parts list may live on a separate document and be referenced by document number in the title block. [1][2]
2. **Mandatory columns**: item number (matches balloon), quantity, designation / description, part number or reference to a sub-drawing, material or remarks. Optional: mass, supplier, stock size. [1][2]
3. **Balloons** on the assembly are circles ≈ 10 mm diameter, thin line, with a leader to each identified part. Balloons carry the item number. Leaders should not cross each other; balloons arranged in tidy rows / columns. [1][2]
4. **Sort order**: main assembly → sub-assemblies → individual parts → standard parts (screws, washers, pins) listed **last**; or strictly ascending item number. [1][2]
5. **Standard parts** cite their product standard in the designation column, e.g. `Hexagon bolt ISO 4017 – M8×25 – 8.8`. The parts list is the single source for the exact callout. [1]
6. **Separate BOM document** under ISO 7573 format may be used; if so, reference its document number in the title block so the drawing and the list are traceable to each other. [1]

## Sources

1. ISO 7573:2008 — "Technical product documentation — Parts lists" — https://www.iso.org/standard/43883.html
2. Hoischen, H.; Hesser, W. — *Technisches Zeichnen*, 37. Auflage (2020), chapter 17 "Stücklisten".
3. Labisch, S.; Weber, C. — *Technisches Zeichnen*, 5. Auflage, Springer Vieweg (2020).

## Confidence / flags

- **Confidence: high**.
