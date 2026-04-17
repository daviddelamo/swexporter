import os
import logging
from google import genai

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
    Traduce un texto al español usando Gemini API con contexto de Savage Pathfinder.
    Utiliza un caché en memoria para mejorar el rendimiento.
    """
    if not text or not isinstance(text, str) or not text.strip():
        return text
        
    text = text.strip()
    
    if text in _translation_cache:
        return _translation_cache[text]
        
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.warning("No se encontró GEMINI_API_KEY en las variables de entorno. Devolviendo texto original.")
        return text

    try:
        client = genai.Client()
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=text,
            config=genai.types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=0.1
            ),
        )
        translated = response.text.strip()
        if translated:
            _translation_cache[text] = translated
            return translated
        return text
    except Exception as e:
        logger.error(f"Error durante la traducción con Gemini: {e}")
        return text

def translate_field(data_dict: dict, field_name: str):
    """
    Traduce un campo específico dentro de un diccionario si existe y es un string.
    Modifica el diccionario en su lugar.
    """
    if field_name in data_dict and isinstance(data_dict[field_name], str):
        data_dict[field_name] = translate_to_spanish(data_dict[field_name])


