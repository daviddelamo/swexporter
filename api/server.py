"""
SWADE PDF Exporter — FastAPI Server
=====================================
REST API que recibe datos de un actor de Foundry VTT (SWADE)
y devuelve una hoja de personaje en formato PDF.

Uso:
    uvicorn api.server:app --host 0.0.0.0 --port 5050
"""

import base64
import io
import os
import re
import tempfile
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel
from weasyprint import HTML

# Importar la lógica de extracción compartida
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.extractor import build_context

# ─────────────────────────────────────────────────
# Configuración
# ─────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
TEMPLATE_DIR = PROJECT_ROOT / "templates"

app = FastAPI(
    title="SWADE PDF Exporter API",
    description="Genera hojas de personaje PDF a partir de datos de Foundry VTT (SWADE).",
    version="1.0.0",
)

# CORS — permitir todas las origins (el usuario configurará en producción)
ALLOWED_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────
# Modelos de request
# ─────────────────────────────────────────────────

class GeneratePDFRequest(BaseModel):
    actor_data: dict
    img_base64: str | None = None


# ─────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    """Health check para verificar que el servicio está activo."""
    return {"status": "ok", "service": "swade-pdf-exporter"}


@app.post("/generate-pdf")
async def generate_pdf(request: GeneratePDFRequest):
    """
    Genera un PDF de hoja de personaje a partir de datos SWADE de Foundry VTT.

    - **actor_data**: JSON completo del actor exportado desde Foundry VTT
    - **img_base64**: (Opcional) Imagen del personaje codificada en base64
    """
    try:
        # Extraer datos del personaje
        context = build_context(request.actor_data)

        # Manejar imagen del personaje
        temp_img_path = None
        if request.img_base64:
            try:
                # Puede venir como "data:image/webp;base64,..." o directamente base64
                img_data = request.img_base64
                if "," in img_data:
                    img_data = img_data.split(",", 1)[1]

                img_bytes = base64.b64decode(img_data)

                # Determinar extensión desde el header base64 o usar webp
                ext = ".webp"
                if request.img_base64.startswith("data:image/png"):
                    ext = ".png"
                elif request.img_base64.startswith("data:image/jpeg") or request.img_base64.startswith("data:image/jpg"):
                    ext = ".jpg"

                # Guardar en archivo temporal
                temp_file = tempfile.NamedTemporaryFile(
                    delete=False, suffix=ext, prefix="swade_portrait_"
                )
                temp_file.write(img_bytes)
                temp_file.close()
                temp_img_path = temp_file.name
                context["info"]["img_local"] = temp_img_path
            except Exception:
                # Si falla el procesamiento de imagen, continuar sin ella
                context["info"]["img_local"] = ""
        else:
            context["info"]["img_local"] = ""

        # Renderizar HTML
        env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
        template = env.get_template("plantilla.html")
        html_content = template.render(**context)

        # Generar PDF en memoria
        html_doc = HTML(string=html_content, base_url=str(PROJECT_ROOT))
        pdf_bytes = html_doc.write_pdf()

        # Limpiar archivo temporal de imagen
        if temp_img_path and os.path.exists(temp_img_path):
            os.unlink(temp_img_path)

        # Generar nombre del archivo
        char_name = context["info"].get("name", "personaje")
        safe_name = re.sub(r'[^\w\s-]', '', char_name).strip().replace(' ', '_')
        filename = f"{safe_name}.pdf"

        # Devolver PDF como streaming response
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(pdf_bytes)),
            },
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando PDF: {str(e)}")
