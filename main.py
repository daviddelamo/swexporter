#!/usr/bin/env python3
"""
SWADE Character Sheet Exporter — CLI
======================================
Lee un archivo JSON exportado desde Foundry VTT (sistema SWADE / Savage Pathfinder)
y genera una hoja de personaje completa en formato PDF con estética de fantasía épica.

Uso:
    python main.py <archivo_personaje.json> [--output <nombre_salida.pdf>] [--img <imagen.webp>]
"""

import argparse
import json
import re
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

from core.extractor import build_context


def render_html(context: dict, template_dir: str) -> str:
    """Renderiza la plantilla Jinja2 con el contexto dado."""
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template("plantilla.html")
    return template.render(**context)


def generate_pdf(html_content: str, output_path: str, base_url: str):
    """Genera el PDF a partir del HTML renderizado."""
    html_doc = HTML(string=html_content, base_url=base_url)
    html_doc.write_pdf(output_path)


def main():
    parser = argparse.ArgumentParser(
        description="Genera una hoja de personaje PDF a partir de un JSON exportado de Foundry VTT (SWADE)."
    )
    parser.add_argument(
        "input_file",
        help="Ruta al archivo JSON del personaje exportado desde Foundry VTT.",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Nombre del archivo PDF de salida (por defecto: <nombre_personaje>.pdf).",
    )
    parser.add_argument(
        "--img", "-i",
        default=None,
        help="Ruta a la imagen/artwork del personaje (webp, png, jpg).",
    )
    args = parser.parse_args()

    # Validar que el archivo de entrada existe
    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f"❌ Error: No se encontró el archivo '{input_path}'.", file=sys.stderr)
        sys.exit(1)

    # Leer y parsear JSON
    print(f"📖 Leyendo archivo: {input_path}")
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Construir contexto
    print("⚙️  Extrayendo datos del personaje...")
    context = build_context(data)

    # Imagen del personaje
    if args.img:
        img_path = Path(args.img).resolve()
        if img_path.exists():
            context["info"]["img_local"] = str(img_path)
            print(f"🖼️  Usando imagen: {img_path}")
        else:
            print(f"⚠️  Imagen no encontrada: {img_path}", file=sys.stderr)
            context["info"]["img_local"] = ""
    else:
        context["info"]["img_local"] = ""

    # Renderizar HTML
    script_dir = Path(__file__).parent.resolve()
    template_dir = script_dir / "templates"
    if not template_dir.exists():
        print(f"❌ Error: No se encontró el directorio de plantillas '{template_dir}'.", file=sys.stderr)
        sys.exit(1)

    print("🎨 Renderizando plantilla HTML...")
    html_content = render_html(context, str(template_dir))

    # Determinar nombre de salida
    if args.output:
        output_path = Path(args.output)
    else:
        safe_name = re.sub(r'[^\w\s-]', '', context["info"]["name"]).strip().replace(' ', '_')
        output_path = Path(f"{safe_name}.pdf")

    # Generar PDF
    print(f"📄 Generando PDF: {output_path}")
    generate_pdf(html_content, str(output_path), base_url=str(script_dir))

    print(f"✅ ¡Hoja de personaje generada exitosamente! → {output_path}")


if __name__ == "__main__":
    main()
