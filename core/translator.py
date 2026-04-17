import logging
from deep_translator import GoogleTranslator
from deep_translator.exceptions import TranslationNotFound

logger = logging.getLogger(__name__)

# Cache en memoria para evitar llamadas redundantes a la API de traducción
_translation_cache = {}

def translate_to_spanish(text: str) -> str:
    """
    Traduce un texto al español usando Google Translate.
    Utiliza un caché en memoria para mejorar el rendimiento.
    """
    if not text or not isinstance(text, str) or not text.strip():
        return text
        
    text = text.strip()
    
    # Comprobar si ya está en caché
    if text in _translation_cache:
        return _translation_cache[text]
        
    try:
        # Se asume que el origen es auto o inglés. Aquí usamos 'auto'
        translated = GoogleTranslator(source='auto', target='es').translate(text)
        if translated:
            _translation_cache[text] = translated
            return translated
        return text
    except TranslationNotFound:
        # Si no puede traducir, devuelve el original
        logger.warning("No se pudo traducir el texto (TranslationNotFound)")
        return text
    except Exception as e:
        logger.error(f"Error durante la traducción: {e}")
        return text

def translate_field(data_dict: dict, field_name: str):
    """
    Traduce un campo específico dentro de un diccionario si existe y es un string.
    Modifica el diccionario en su lugar.
    """
    if field_name in data_dict and isinstance(data_dict[field_name], str):
        data_dict[field_name] = translate_to_spanish(data_dict[field_name])

