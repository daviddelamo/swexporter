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
import json
import os
import re
import tempfile
from pathlib import Path

import qrcode

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, HTMLResponse, Response
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
DATA_DIR = PROJECT_ROOT / "data" / "characters"
DATA_DIR.mkdir(parents=True, exist_ok=True)

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

class SyncCharacterRequest(BaseModel):
    uuid: str
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


@app.post("/sync-character")
async def sync_character(request: SyncCharacterRequest):
    """
    Sincroniza los datos de un personaje con el servidor.
    Extrae la información y la guarda en disco.
    """
    try:
        context = build_context(request.actor_data)
        
        # Para la web, guardamos la imagen en base64 directamente en el contexto
        if request.img_base64:
            # Asegurar que tiene el prefijo de data URI
            if not request.img_base64.startswith("data:image"):
                context["info"]["img_local"] = f"data:image/webp;base64,{request.img_base64}"
            else:
                context["info"]["img_local"] = request.img_base64
        else:
            context["info"]["img_local"] = ""
            
        file_path = DATA_DIR / f"{request.uuid}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(context, f, ensure_ascii=False, indent=2)
            
        return {"status": "success", "uuid": request.uuid}
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in sync_character:\n{error_details}")
        raise HTTPException(status_code=500, detail=f"Error sincronizando personaje: {str(e)}\n\nTraceback:\n{error_details}")


@app.get("/qr/{uuid}")
async def get_qr(uuid: str, request: Request):
    """Genera y devuelve el código QR apuntando a la URL del personaje."""
    base_url = str(request.base_url).rstrip("/")
    view_url = f"{base_url}/view/{uuid}"
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(view_url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr = img_byte_arr.getvalue()
    
    return Response(content=img_byte_arr, media_type="image/png")


@app.get("/view/{uuid}", response_class=HTMLResponse)
async def view_character(uuid: str):
    """Renderiza la hoja de personaje en la web usando los datos sincronizados."""
    file_path = DATA_DIR / f"{uuid}.json"
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Personaje no encontrado")
        
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            context = json.load(f)
            
        env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
        # Intentará cargar web_view.html, si no existe todavía, lo haremos en el siguiente paso.
        template = env.get_template("web_view.html")
        html_content = template.render(**context)
        
        return HTMLResponse(content=html_content)
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error rendering web view:\n{error_details}")
        raise HTTPException(status_code=500, detail=f"Error renderizando la vista web: {str(e)}\n\nTraceback:\n{error_details}")
