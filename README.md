# auto-drawing

OSS-first automatic drawing creation from STEP files, with a browser-based editor and HTML/SVG/PDF export.

The repo now has two lanes:

- **OSS web lane**: STEP import -> canonical model -> projected drawing -> interactive web editor -> HTML/PDF export
- **Legacy SolidWorks lane**: the earlier COM automation prototype, preserved as reference material for a future native `.slddrw` worker

## Current architecture

### OSS web lane

- Python domain and API layer in `autodrawing/`
- React + TypeScript editor in `frontend/`
- Fixture corpus and schema-first tests in `fixtures/` and `tests/`

### Legacy SolidWorks lane

- COM automation prototype in `autodrawing/engine.py`
- helper script in `scripts/generate_guideline_drawing.py`
- design notes in `learnings.md` and `SOLIDWORKS_INTERFACE_FINDINGS.md`

## Repo layout

| Path | Contents |
|------|----------|
| `autodrawing/` | canonical contracts, STEP importer, projection pipeline, drawing document service, scene graph, export service, FastAPI app |
| `frontend/` | React + TypeScript drawing editor with SVG sheet canvas and three.js review pane |
| `fixtures/` | STEP fixtures used by the OSS pipeline tests |
| `guidelines/` | ISO/DIN drafting rules and drafting references |
| `tests/` | importer, schema, command, and legacy feature extraction tests |
| `scripts/` | legacy SolidWorks helper scripts |

## Requirements

### Python

- Python 3.11+
- `fastapi`, `uvicorn`, `python-multipart`

Install:

```bash
python -m pip install fastapi uvicorn python-multipart
```

### Frontend

- Node.js 24+

Install:

```bash
cd frontend
npm install
```

## Running the OSS web app

Start the backend:

```bash
uvicorn autodrawing.api:app --reload --host 127.0.0.1 --port 8000
```

Start the frontend:

```bash
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

Then open `http://127.0.0.1:5173`.

## CLI pipeline

You can also generate a bundle and standalone HTML document directly:

```bash
python -m autodrawing.web_cli --input fixtures/step/hole-pattern.step --out-dir .generated/oss-demo --mode final
```

## Tests

```bash
python -m unittest discover -s tests -v
```

## Notes

- The STEP importer is schema-first and deterministic, with a clean seam for swapping in pythonOCC/OCCT later.
- The current PDF export path uses a Puppeteer script in `frontend/scripts/export-pdf.mjs`.
- Native SolidWorks `.slddrw` export is still intentionally outside the OSS runtime path.
