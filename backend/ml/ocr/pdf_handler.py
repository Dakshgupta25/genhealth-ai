"""
PDF to image conversion for the GenHealth AI OCR pipeline.

Converts multi-page PDFs to a sequence of high-resolution PIL images
using pdf2image (Poppler backend).
"""

import logging
import os
import tempfile
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

_PDF2IMAGE_AVAILABLE = False
try:
    from pdf2image import convert_from_path, pdfinfo_from_path
    _PDF2IMAGE_AVAILABLE = True
except ImportError:
    logger.warning(
        "pdf2image is not installed. PDF OCR will be unavailable. "
        "Install with: pip install pdf2image  (and apt install poppler-utils)"
    )


class PDFHandler:
    """
    Handles conversion of PDF documents to images for OCR processing.

    Each page is converted to a high-DPI PIL Image, which is then passed
    to the OCR extractor for text extraction.

    Attributes:
        dpi:        Output resolution in DPI (default 300 for OCR accuracy).
        fmt:        Image format to use ('PNG' is lossless, preferred for text).
        max_pages:  Maximum pages to process per document (safety limit).
    """

    def __init__(
        self,
        dpi: int = 300,
        fmt: str = "PNG",
        max_pages: int = 30,
    ) -> None:
        self.dpi = dpi
        self.fmt = fmt
        self.max_pages = max_pages

    def __repr__(self) -> str:
        return f"PDFHandler(dpi={self.dpi}, fmt='{self.fmt}', max_pages={self.max_pages})"

    def health_check(self) -> dict:
        """Return the status of the PDF handler and its dependencies."""
        return {
            "pdf2image_available": _PDF2IMAGE_AVAILABLE,
            "dpi": self.dpi,
            "max_pages": self.max_pages,
            "status": "ready" if _PDF2IMAGE_AVAILABLE else "degraded",
        }

    def get_page_count(self, pdf_path: str) -> int:
        """
        Get the total number of pages in a PDF.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            Number of pages, or 0 if the file cannot be read.
        """
        if not _PDF2IMAGE_AVAILABLE:
            return 0
        try:
            info = pdfinfo_from_path(pdf_path)
            return info.get("Pages", 0)
        except Exception as exc:
            logger.error("Failed to get PDF page count for '%s': %s", pdf_path, exc)
            return 0

    def convert_to_images(
        self,
        pdf_path: str,
        page_range: Optional[Tuple[int, int]] = None,
    ) -> List[np.ndarray]:
        """
        Convert a PDF document to a list of numpy arrays (one per page).

        Args:
            pdf_path:   Path to the input PDF file.
            page_range: Optional (first_page, last_page) tuple (1-indexed).
                        If None, converts all pages up to max_pages.

        Returns:
            List of BGR numpy arrays, one per page.

        Raises:
            FileNotFoundError: If pdf_path does not exist.
            RuntimeError: If pdf2image is not available.
        """
        if not _PDF2IMAGE_AVAILABLE:
            raise RuntimeError(
                "pdf2image is not installed. Cannot convert PDF. "
                "Install with: pip install pdf2image"
            )

        pdf_path = str(pdf_path)
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF not found: '{pdf_path}'")

        # Determine page range
        total_pages = self.get_page_count(pdf_path)
        if total_pages == 0:
            logger.warning("Could not determine page count for '%s'.", pdf_path)
            total_pages = self.max_pages

        if page_range:
            first, last = page_range
            last = min(last, total_pages, self.max_pages)
        else:
            first, last = 1, min(total_pages, self.max_pages)

        logger.info(
            "Converting PDF '%s' pages %d–%d at %d DPI.",
            Path(pdf_path).name, first, last, self.dpi,
        )

        try:
            pil_images: List[Image.Image] = convert_from_path(
                pdf_path,
                dpi=self.dpi,
                first_page=first,
                last_page=last,
                fmt=self.fmt,
                thread_count=2,
            )
        except Exception as exc:
            logger.exception("PDF conversion failed for '%s': %s", pdf_path, exc)
            raise RuntimeError(f"PDF conversion error: {exc}") from exc

        # Convert PIL Images to BGR numpy arrays (OpenCV format)
        images = []
        for i, pil_img in enumerate(pil_images, start=first):
            img_rgb = pil_img.convert("RGB")
            img_bgr = np.array(img_rgb)[:, :, ::-1].copy()  # RGB → BGR
            images.append(img_bgr)
            logger.debug("Page %d converted: shape=%s", i, img_bgr.shape)

        logger.info("Converted %d page(s) from '%s'.", len(images), Path(pdf_path).name)
        return images

    def convert_to_pil_images(
        self,
        pdf_path: str,
        page_range: Optional[Tuple[int, int]] = None,
    ) -> List[Image.Image]:
        """
        Convert PDF pages to PIL Images (useful for direct Pillow processing).

        Args:
            pdf_path:   Path to the PDF.
            page_range: Optional page range tuple.

        Returns:
            List of PIL Image objects (RGB).
        """
        if not _PDF2IMAGE_AVAILABLE:
            raise RuntimeError("pdf2image is not installed.")

        total_pages = self.get_page_count(pdf_path) or self.max_pages
        if page_range:
            first, last = page_range[0], min(page_range[1], total_pages, self.max_pages)
        else:
            first, last = 1, min(total_pages, self.max_pages)

        return convert_from_path(
            pdf_path, dpi=self.dpi,
            first_page=first, last_page=last,
            fmt=self.fmt,
        )

    def iter_pages(
        self,
        pdf_path: str,
    ) -> Iterator[Tuple[int, np.ndarray]]:
        """
        Iterate over PDF pages, yielding (page_number, image) tuples.

        Memory-efficient: processes one page at a time via temp files.

        Args:
            pdf_path: Path to the PDF file.

        Yields:
            Tuples of (1-indexed page number, BGR numpy array).
        """
        images = self.convert_to_images(pdf_path)
        for page_num, img in enumerate(images, start=1):
            yield page_num, img

    def save_page_images(
        self,
        pdf_path: str,
        output_dir: str,
        prefix: str = "page",
    ) -> List[str]:
        """
        Convert PDF pages and save each as a PNG file.

        Useful for debugging or batch OCR preprocessing.

        Args:
            pdf_path:   Path to the input PDF.
            output_dir: Directory to save page images.
            prefix:     Filename prefix (default 'page').

        Returns:
            List of saved file paths.
        """
        os.makedirs(output_dir, exist_ok=True)
        images = self.convert_to_images(pdf_path)
        saved_paths = []

        for i, img_bgr in enumerate(images, start=1):
            import cv2
            out_path = os.path.join(output_dir, f"{prefix}_{i:03d}.png")
            cv2.imwrite(out_path, img_bgr)
            saved_paths.append(out_path)
            logger.debug("Saved page %d to '%s'.", i, out_path)

        return saved_paths


# Module-level singleton for convenience
_handler: Optional[PDFHandler] = None


def get_pdf_handler(dpi: int = 300) -> PDFHandler:
    """Return (or create) the module-level PDFHandler singleton."""
    global _handler
    if _handler is None or _handler.dpi != dpi:
        _handler = PDFHandler(dpi=dpi)
    return _handler


def pdf_to_images(
    pdf_path: str,
    dpi: int = 300,
    max_pages: int = 30,
) -> List[np.ndarray]:
    """
    Convenience function: convert a PDF to a list of BGR numpy arrays.

    Args:
        pdf_path:  Path to the PDF file.
        dpi:       Output DPI (default 300).
        max_pages: Maximum pages to convert.

    Returns:
        List of BGR numpy arrays.
    """
    handler = PDFHandler(dpi=dpi, max_pages=max_pages)
    return handler.convert_to_images(pdf_path)
