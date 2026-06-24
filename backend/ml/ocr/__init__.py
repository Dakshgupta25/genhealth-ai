"""
OCR Pipeline stub.

In Part 2, this module will implement:
  - Tesseract-based local OCR
  - Google Vision API integration for production
  - Image pre-processing (deskew, binarize, denoise)
  - PDF page extraction with PyMuPDF

Current stub: returns a placeholder extraction result.
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def extract_text_from_image(image_bytes: bytes, file_ext: str) -> str:
    """
    Extract raw text from a medical document image using OCR.

    Args:
        image_bytes: Raw bytes of the uploaded image or PDF.
        file_ext:    File extension ('jpg', 'png', 'pdf', 'heic').

    Returns:
        Raw OCR-extracted text string.
    """
    logger.info("OCR extraction called (stub). Implement in Part 2.")
    # TODO (Part 2): Replace with Tesseract / Google Vision integration
    return "Stub OCR output — to be implemented in Part 2."


def preprocess_image(image_bytes: bytes) -> bytes:
    """
    Pre-process a medical document image for optimal OCR accuracy.

    Applies: grayscale conversion, deskew, binarization, denoising.

    Args:
        image_bytes: Raw image bytes.

    Returns:
        Pre-processed image bytes.
    """
    # TODO (Part 2): Implement with Pillow + OpenCV
    return image_bytes
