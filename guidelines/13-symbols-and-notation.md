---
topic: Symbols and notation
standards:
  - ISO 129-1:2018
  - ISO 1302:2002
flags:
  - Compact quick-reference guide
last_verified: 2026-04-20
confidence: medium
---

# 13 — Symbols and Notation

## Fast reference

| Symbol | Meaning | Example |
|---|---|---|
| `Ø` | diameter | `Ø25` |
| `R` | radius | `R4` |
| `SR` | spherical radius | `SR20` |
| `SØ` | spherical diameter | `SØ20` |
| `□` | square section | `□12` |
| `SW` | across flats | `SW17` |
| `t` | thickness | `t2` |
| `C` | 45° chamfer | `C1.5` |
| `M` | metric thread | `M8×1.25` |
| `Ra` | roughness parameter | `Ra 1.6 µm` |

## Notation habits that reduce errors

- Pick one unit family for the whole sheet where possible.
- Add counts for repeated features: `4×`, `6×`, `TYP`.
- Use `R` for arcs and fillets, `Ø` for full circular size.
- Use `SR` and `SØ` only for spherical surfaces.
- If a chamfer is not 45°, write the angle explicitly.
- Use `REF` or parentheses only for informational values.

## Example bundle

```text
4× Ø6 THRU
2× C1.0
R3 TYP
SØ30
t2.5
SW17
```
