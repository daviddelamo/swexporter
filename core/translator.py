import os
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)

# Cache en memoria para evitar llamadas redundantes a la API
_translation_cache = {}

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

def translate_to_spanish(text: str) -> str:
    """
    Traduce un texto al español usando Grok API (xAI) con contexto de Savage Pathfinder.
    Utiliza un caché en memoria para mejorar el rendimiento.
    """
    if not text or not isinstance(text, str) or not text.strip():
        return text
        
    text = text.strip()
    
    if text in _translation_cache:
        return _translation_cache[text]
        
    api_key = os.environ.get("XAI_API_KEY")
    if not api_key:
        logger.warning("No se encontró XAI_API_KEY en las variables de entorno. Devolviendo texto original.")
        return text

    try:
        client = OpenAI(
            api_key=api_key,
            base_url="https://api.x.ai/v1",
        )
        response = client.chat.completions.create(
            model="grok-4-1-fast-non-reasoning",
            messages=[
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {"role": "user", "content": text},
            ],
            temperature=0.1
        )
        translated = response.choices[0].message.content.strip()
        if translated:
            _translation_cache[text] = translated
            return translated
        return text
    except Exception as e:
        logger.error(f"Error durante la traducción con Grok: {e}")
        return text

def translate_field(data_dict: dict, field_name: str):
    """
    Traduce un campo específico dentro de un diccionario si existe y es un string.
    Modifica el diccionario en su lugar.
    """
    if field_name in data_dict and isinstance(data_dict[field_name], str):
        data_dict[field_name] = translate_to_spanish(data_dict[field_name])


