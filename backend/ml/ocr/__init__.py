"""
OCR package for GenHealth AI.

Provides dual-engine OCR (Tesseract + EasyOCR) with medical post-processing.
"""

from ml.ocr.extractor import OCRExtractor, get_extractor
from ml.ocr.preprocessor import preprocess_image, preprocess_handwritten
from ml.ocr.pdf_handler import PDFHandler, pdf_to_images

__all__ = [
    "OCRExtractor",
    "get_extractor",
    "preprocess_image",
    "preprocess_handwritten",
    "PDFHandler",
    "pdf_to_images",
]

