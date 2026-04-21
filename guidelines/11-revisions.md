---
topic: Revisions / change notes
standards:
  - ISO 7200:2004 — Title block fields including revision index
industry_practice:
  - VDA 4953 (German automotive) — revision-table conventions
flags:
  - Layout of the revision table itself is industry convention, not an ISO standard
last_verified: 2026-04-20
confidence: medium
---

# 11 — Revisions

## Rules

1. **Revision index** is a mandatory ISO 7200 title-block field. Its value **must match** the latest row of the revision table. [1][3]
2. **Revision table** is typically placed directly **above the title block**, or in the upper-right corner. Columns: revision index, description of change, date, drawn by, approved by, (optional) ECO / ECN number. Rows are read bottom-up so the newest revision is nearest the title block. [3]
3. **Revision balloons** (triangle, hexagon, or circle containing the rev letter) are placed on the drawing next to each changed feature so the change is visually traceable. [3]
4. **Revision-letter skip list**: do **not** use `I`, `O`, `Q`, `S`, `X`, `Z` — they are ambiguous with numerals or each other. Sequence: A, B, C, D, E, F, G, H, J, K, L, M, N, P, R, T, U, V, W, Y. [3]
5. **First release** is conventionally `-`, `0`, or `A` depending on company PDM rules. Major changes (form / fit / function) increment the main index; minor editorial changes may use a sub-index (A → A1 → A2). [3]
6. **Superseded drawings** are archived — never erased. Controlled drawings retain full revision history. [3]

## Sources

1. ISO 7200:2004 — "Technical product documentation — Data fields in title blocks and document headers" — https://www.iso.org/standard/38265.html
2. VDA 4953 — recommendation on drawing management, German automotive industry association.
3. Hoischen, H.; Hesser, W. — *Technisches Zeichnen*, 37. Auflage (2020), chapter on "Änderungsdienst".

## Confidence / flags

- **Flag (convention)**: ISO 7200 defines the **field**; the layout of the revision table is company / industry convention. Rules 2–5 above are widely followed in German and European industry but are not strictly mandated by an ISO standard.
- **Confidence: medium** — do not cite these rules as ISO requirements without qualifying them as convention.
