# auto-drawing

Automated SolidWorks drawing generation from STEP or `.SLDPRT` files, following ISO/DIN drafting guidelines.

## What this is

An agent-driven pipeline that opens a part in SolidWorks via COM automation, creates a compliant 2D drawing (standard orthographic views + isometric recognition view), applies dimensions, and exports to PDF/PNG — all without manual SolidWorks interaction.

## Repo layout

| Path | Contents |
|------|----------|
| `guidelines/` | ISO/DIN drafting rules (views, dimensions, GD&T, tolerances, BOM, …) |
| `scripts/` | Python COM automation scripts |
| `sample_part/` | Sample `.SLDPRT` used for development and testing |
| `learnings.md` | Empirical notes from live SolidWorks tests |
| `SOLIDWORKS_INTERFACE_FINDINGS.md` | Evaluation of SolidWorks API access patterns and architecture recommendation |

## Key decisions

- **COM via Python `win32com`** — direct SolidWorks automation without a running MCP server
- **Ordinate dimensioning preferred** — auto-dimension schemes that produce parenthesized values are rejected
- **View modes**: orthographic views use *hidden lines visible* (mode 1); isometric recognition view uses shaded (mode 3)

## Requirements

- Windows + SolidWorks installed and licensed
- Python 3.x with `pywin32` (`pip install pywin32`)

## Usage

```bash
python scripts/generate_guideline_drawing.py
```
