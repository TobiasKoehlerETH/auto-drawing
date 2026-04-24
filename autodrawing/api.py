from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from .contracts import DrawingCommand, DrawingPreview, OcctDrawingPreviewRequest, PipelineBundle
from .exporters import PdfExportService
from .importers import StepImportError
from .pipeline import AutodrawingPipeline
from .preview import PreviewService, PreviewStore

app = FastAPI(title="autodrawing", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pipeline = AutodrawingPipeline()
preview_store = PreviewStore()
preview_service = PreviewService()


class PipelineCommandRequest(BaseModel):
    bundle: PipelineBundle
    command: DrawingCommand


class PipelineCommandsRequest(BaseModel):
    bundle: PipelineBundle
    commands: list[DrawingCommand]


class PipelineOnlyRequest(BaseModel):
    bundle: PipelineBundle


class PreviewCommandRequest(BaseModel):
    command: DrawingCommand


class PreviewCommandsRequest(BaseModel):
    commands: list[DrawingCommand]


@app.get("/api/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "preview_store_entries": len(preview_store._bundles),  # noqa: SLF001 - lightweight app-local diagnostics
        "runtime_backed": False,
    }


@app.post("/api/pipeline/from-upload")
async def pipeline_from_upload(file: UploadFile = File(...), mode: str = "preview") -> PipelineBundle:
    text = (await file.read()).decode("utf-8", errors="ignore")
    try:
        return pipeline.from_step_text(text, source_name=file.filename or "uploaded.step", mode=mode)
    except StepImportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/document/apply-command")
def apply_command(payload: PipelineCommandRequest) -> PipelineBundle:
    return pipeline.apply_command(payload.bundle, payload.command)


@app.post("/api/document/apply-commands")
def apply_commands(payload: PipelineCommandsRequest) -> PipelineBundle:
    return pipeline.apply_commands(payload.bundle, payload.commands)


@app.post("/api/document/undo")
def undo(payload: PipelineOnlyRequest) -> PipelineBundle:
    return pipeline.undo(payload.bundle)


@app.post("/api/document/redo")
def redo(payload: PipelineOnlyRequest) -> PipelineBundle:
    return pipeline.redo(payload.bundle)


@app.post("/api/export/html", response_class=HTMLResponse)
def export_html(payload: PipelineOnlyRequest) -> str:
    return pipeline.render_html(payload.bundle)


@app.post("/api/studio/drawing-preview", response_model=DrawingPreview)
async def drawing_preview(file: UploadFile = File(...), mode: str = "preview") -> DrawingPreview:
    text = (await file.read()).decode("utf-8", errors="ignore")
    try:
        bundle = pipeline.from_step_text(text, source_name=file.filename or "uploaded.step", mode=mode)
    except StepImportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}") from exc
    preview_id = preview_store.create(bundle)
    try:
        return preview_service.build_preview(preview_id, bundle)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}") from exc


@app.post("/api/studio/drawing-preview-from-occt", response_model=DrawingPreview)
def drawing_preview_from_occt(payload: OcctDrawingPreviewRequest) -> DrawingPreview:
    try:
        bundle = pipeline.from_occt_meshes(
            payload.meshes,
            source_name=payload.source_name,
            units=payload.units,
            mode=payload.mode,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}") from exc
    preview_id = preview_store.create(bundle)
    try:
        return preview_service.build_preview(preview_id, bundle)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}") from exc


@app.get("/api/studio/drawing-previews/{preview_id}", response_model=DrawingPreview)
def get_drawing_preview(preview_id: str) -> DrawingPreview:
    try:
        bundle = preview_store.get(preview_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown preview: {preview_id}") from exc
    return preview_service.build_preview(preview_id, bundle)


@app.post("/api/studio/drawing-previews/{preview_id}/command", response_model=DrawingPreview)
def apply_preview_command(preview_id: str, payload: PreviewCommandRequest) -> DrawingPreview:
    try:
        bundle = preview_store.get(preview_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown preview: {preview_id}") from exc
    try:
        updated = pipeline.apply_command(bundle, payload.command)
        preview_store.put(preview_id, updated)
        return preview_service.build_preview(preview_id, updated)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}") from exc


@app.post("/api/studio/drawing-previews/{preview_id}/commands", response_model=DrawingPreview)
def apply_preview_commands(preview_id: str, payload: PreviewCommandsRequest) -> DrawingPreview:
    try:
        bundle = preview_store.get(preview_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown preview: {preview_id}") from exc
    try:
        updated = pipeline.apply_commands(bundle, payload.commands)
        preview_store.put(preview_id, updated)
        return preview_service.build_preview(preview_id, updated)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}") from exc


@app.post("/api/export/pdf")
def export_pdf(payload: PipelineOnlyRequest) -> JSONResponse:
    frontend_dir = Path.cwd() / "frontend"
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / payload.bundle.document.export_settings.pdf_filename
            exported = PdfExportService().export_pdf(payload.bundle, output_path, frontend_dir)
            data = exported.read_bytes()
        return JSONResponse(
            {
                "supported": True,
                "filename": payload.bundle.document.export_settings.pdf_filename,
                "content_base64": data.hex(),
                "encoding": "hex",
            }
        )
    except Exception as exc:
        return JSONResponse({"supported": False, "error": str(exc)}, status_code=501)
