import unicodedata
import re
import logging

# ---- Logger setup ----
logger = logging.getLogger(__name__)

# ---- Text functions ----
def normalize_text(text: str) -> str:
    """
    Normalizes text by removing diacritics (accents) and converting to lowercase.
    Example: "Éxito" -> "exito"
    """
    if not isinstance(text, str):
        logger.warning(f"normalize_text received non-string input: {type(text)}. Returning as is.")
        return str(text)
    try:
        # Decompose into base characters and diacritics
        nfkd_form = unicodedata.normalize('NFKD', text)
        normalized_string = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
        return normalized_string.lower()
    except Exception as e:
        logger.error(f"Error normalizing text '{text[:50]}...': {e}", exc_info=True)
        return text.lower() # Fallback to simple lowercase

def validate_general_text_input(response: str) -> bool:
    """
    Validates if the response consists of common text characters, numbers, hyphens, and spaces.
    This is a very generic validation.
    """
    if not isinstance(response, str):
        return False
    # Allows letters (Unicode), numbers, spaces, hyphens.
    # Adjust regex as needed for more specific validation.
    return re.match(r"^[-\w\s]+$", response, re.UNICODE) is not None
  
