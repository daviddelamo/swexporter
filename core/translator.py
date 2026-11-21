import os
import re
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_TRANSLATION_MODEL = "google/gemma-4-31b-it"

# Cache en memoria para evitar llamadas redundantes a la API
_translation_cache = {}
_thought_block_re = re.compile(r"<\|channel>thought[\s\S]*?<channel\|>")

SYSTEM_INSTRUCTION = """
Eres un traductor experto del juego de rol de mesa "Savage Worlds Adventure Edition" (SWADE) y específicamente de la ambientación "Savage Pathfinder". 
Traduce el siguiente texto en inglés al español.
Debes mantener un tono de fantasía épica y usar la terminología oficial del juego en español.
Términos obligatorios:
- "Soak" -> "Absorber"
- "Spellcasting" -> "Hechicería"
- "Edge" -> "Ventaja"
- "Hindrance" -> "Complicación"
- "Toughness" -> "Dureza"
- "Parry" -> "Parada"
- "Pace" -> "Paso"

Responde ÚNICAMENTE con la traducción directa. No añadas notas, explicaciones, ni comillas extra.
"""


def _clean_model_output(content: str | None) -> str:
    """Elimina bloques de razonamiento y espacios sobrantes de la respuesta."""
    if not content:
        return ""
    cleaned = _thought_block_re.sub("", content)
    return cleaned.strip()


def translate_to_spanish(text: str) -> str:
    """
    Traduce un texto al español usando NVIDIA NIM API con contexto de Savage Pathfinder.
    Utiliza un caché en memoria para mejorar el rendimiento.
    """
    if not text or not isinstance(text, str) or not text.strip():
        return text

    text = text.strip()

    if text in _translation_cache:
        return _translation_cache[text]

    api_key = os.environ.get("RIVA_API_KEY")
    if not api_key:
        logger.warning("No se encontró RIVA_API_KEY en las variables de entorno. Devolviendo texto original.")
        return text

    model = os.environ.get("RIVA_MODEL", DEFAULT_TRANSLATION_MODEL)

    try:
        logger.info(f"Llamando a la IA ({model}) para traducir: {text}")
        client = OpenAI(
            api_key=api_key,
            base_url=NVIDIA_BASE_URL,
        )
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {"role": "user", "content": text},
            ],
            temperature=0.2,
            max_tokens=4096,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            stream=False,
        )

        logger.info(f"Respuesta de la IA: {response}")

        translated = _clean_model_output(response.choices[0].message.content)
        if translated:
            _translation_cache[text] = translated
            return translated
        return text
    except Exception as e:
        logger.error(f"Error durante la traducción con NVIDIA API: {e}")
        return text

def translate_field(data_dict: dict, field_name: str):
    """
    Traduce un campo específico dentro de un diccionario si existe y es un string.
    Modifica el diccionario en su lugar.
    """
    if field_name in data_dict and isinstance(data_dict[field_name], str):
        data_dict[field_name] = translate_to_spanish(data_dict[field_name])


