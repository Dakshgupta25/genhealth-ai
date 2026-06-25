"""
Main OCR orchestrator for GenHealth AI.

Runs a dual-engine pipeline (Tesseract + EasyOCR), merges results using
bounding-box IOU alignment, and applies medical-specific post-processing.
"""

import logging
import os
import re
import tempfile
import time
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from ml.ocr.preprocessor import preprocess_image, preprocess_handwritten
from ml.ocr.pdf_handler import PDFHandler
from ml.utils.medical_constants import OCR_CORRECTIONS
from ml.utils.confidence import aggregate_ocr_confidence

logger = logging.getLogger(__name__)

# ── Optional dependency guards ────────────────────────────────────────────────

try:
    import pytesseract
    _TESSERACT_AVAILABLE = True
except ImportError:
    logger.warning("pytesseract not installed. Tesseract OCR unavailable.")
    _TESSERACT_AVAILABLE = False

try:
    import easyocr
    _EASYOCR_AVAILABLE = True
except ImportError:
    logger.warning("easyocr not installed. EasyOCR unavailable.")
    _EASYOCR_AVAILABLE = False


# ─── OCR Result Types ─────────────────────────────────────────────────────────

WordResult = Dict[str, Any]  # {text, bbox, confidence}

OCRResult = Dict[str, Any]
"""
{
  "raw_text": str,
  "words": List[WordResult],
  "overall_confidence": float,
  "language_detected": str,
  "engine": str,  # "tesseract" | "easyocr" | "merged"
  "processing_time_ms": int,
}
"""


class OCRExtractor:
    """
    Dual-engine OCR extractor optimized for Indian medical prescriptions.

    Runs both Tesseract and EasyOCR in parallel, then merges results
    by choosing the higher-confidence output for each text region.

    Attributes:
        easy_reader:       Initialized EasyOCR reader (lazy-loaded).
        tesseract_config:  Tesseract CLI config string.
        dpi:               DPI for preprocessing target.
        use_handwriting:   Whether to apply handwriting-enhanced preprocessing.
    """

    TESSERACT_CONFIG = "--oem 3 --psm 6 -l eng+hin"
    TESSERACT_CONFIG_SIMPLE = "--oem 3 --psm 6 -l eng"

    # Common IOU threshold for bounding box overlap matching
    IOU_MERGE_THRESHOLD = 0.3

    def __init__(
        self,
        languages: List[str] = None,
        gpu: bool = False,
        use_handwriting: bool = False,
    ) -> None:
        self.languages = languages or ["en", "hi"]
        self.gpu = gpu
        self.use_handwriting = use_handwriting
        self._easy_reader: Optional[Any] = None  # Lazy-initialized
        self.pdf_handler = PDFHandler(dpi=300)
        logger.info(
            "OCRExtractor initialized. Tesseract=%s, EasyOCR=%s, GPU=%s.",
            _TESSERACT_AVAILABLE, _EASYOCR_AVAILABLE, gpu,
        )

    def __repr__(self) -> str:
        return (
            f"OCRExtractor(languages={self.languages}, gpu={self.gpu}, "
            f"tesseract={_TESSERACT_AVAILABLE}, easyocr={_EASYOCR_AVAILABLE})"
        )

    def health_check(self) -> dict:
        """Return the status of both OCR engines."""
        status = {
            "tesseract_available": _TESSERACT_AVAILABLE,
            "easyocr_available": _EASYOCR_AVAILABLE,
            "languages": self.languages,
            "gpu": self.gpu,
        }
        if _TESSERACT_AVAILABLE:
            try:
                status["tesseract_version"] = pytesseract.get_tesseract_version().vstring
            except Exception:
                status["tesseract_version"] = "unknown"
        return status

    # ─── EasyOCR lazy init ───────────────────────────────────────────────────

    @property
    def easy_reader(self):
        """Lazy-initialize the EasyOCR reader (heavy object, ~1–2GB model)."""
        if self._easy_reader is None and _EASYOCR_AVAILABLE:
            logger.info("Initializing EasyOCR reader (first call, may take 30–60s)...")
            try:
                self._easy_reader = easyocr.Reader(self.languages, gpu=self.gpu)
                logger.info("EasyOCR reader initialized.")
            except Exception as exc:
                logger.error("EasyOCR initialization failed: %s", exc)
        return self._easy_reader

    # ─── Public API ──────────────────────────────────────────────────────────

    def extract_from_image(self, image_path: str) -> OCRResult:
        """
        Run dual OCR on a single image file and return merged results.

        Pipeline:
        1. Preprocess image (deskew, denoise, threshold).
        2. Run Tesseract with word-level confidence + bounding boxes.
        3. Run EasyOCR for word-level results.
        4. Merge: for overlapping regions, prefer higher-confidence engine.
        5. Post-process: fix common medical OCR errors.

        Args:
            image_path: Path to the image file (JPEG, PNG, PDF page, HEIC).

        Returns:
            OCRResult dict with raw_text, words, confidence, and language.
        """
        t_start = time.perf_counter()
        logger.info("Extracting text from: %s", image_path)

        # Step 1: Preprocess
        preprocessor = preprocess_handwritten if self.use_handwriting else preprocess_image
        processed_img = preprocessor(image_path)

        # Step 2: Run both engines
        tess_result = self._run_tesseract(processed_img)
        easy_result = self._run_easyocr(processed_img)

        # Step 3: Merge
        merged = self._merge_ocr_results(tess_result, easy_result)

        # Step 4: Post-process text
        merged["raw_text"] = self._fix_medical_ocr_errors(merged["raw_text"])

        # Step 5: Compute overall confidence
        merged["overall_confidence"] = aggregate_ocr_confidence(
            tess_result.get("words", []),
            easy_result.get("words", []),
        )

        elapsed_ms = int((time.perf_counter() - t_start) * 1000)
        merged["processing_time_ms"] = elapsed_ms

        logger.info(
            "OCR complete. Confidence=%.2f, Words=%d, Time=%dms.",
            merged["overall_confidence"],
            len(merged.get("words", [])),
            elapsed_ms,
        )
        return merged

    def extract_from_pdf(self, pdf_path: str) -> OCRResult:
        """
        Convert PDF to images (300 DPI) and run OCR on each page.

        Merges all page results into a single OCRResult, preserving
        page order and annotating words with their source page number.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            Merged OCRResult covering all pages.
        """
        logger.info("Extracting from PDF: %s", pdf_path)

        page_images = self.pdf_handler.convert_to_images(pdf_path)
        if not page_images:
            return self._empty_result()

        all_text_parts: List[str] = []
        all_words: List[WordResult] = []
        total_confidence = 0.0

        for page_num, img_bgr in enumerate(page_images, start=1):
            logger.info("Processing PDF page %d/%d.", page_num, len(page_images))

            # Save page to temp file for extract_from_image (which handles path input)
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = tmp.name
            try:
                cv2.imwrite(tmp_path, img_bgr)
                page_result = self.extract_from_image(tmp_path)
            finally:
                os.unlink(tmp_path)

            all_text_parts.append(f"--- Page {page_num} ---\n{page_result['raw_text']}")

            # Tag each word with its page
            for word in page_result.get("words", []):
                word["page"] = page_num
                all_words.append(word)

            total_confidence += page_result.get("overall_confidence", 0.0)

        return {
            "raw_text": "\n\n".join(all_text_parts),
            "words": all_words,
            "overall_confidence": round(total_confidence / len(page_images), 3),
            "language_detected": "en",
            "engine": "merged",
            "page_count": len(page_images),
            "processing_time_ms": 0,  # Summed across pages
        }

    def extract_from_bytes(self, image_bytes: bytes, file_ext: str = "jpg") -> OCRResult:
        """
        Extract text from raw image bytes (e.g., from S3 download).

        Writes bytes to a temp file, runs extraction, then deletes temp file.

        Args:
            image_bytes: Raw file content.
            file_ext:    File extension without dot (e.g., 'jpg', 'png', 'pdf').

        Returns:
            OCRResult dict.
        """
        with tempfile.NamedTemporaryFile(suffix=f".{file_ext}", delete=False) as tmp:
            tmp.write(image_bytes)
            tmp_path = tmp.name

        try:
            if file_ext.lower() == "pdf":
                return self.extract_from_pdf(tmp_path)
            else:
                return self.extract_from_image(tmp_path)
        finally:
            os.unlink(tmp_path)

    # ─── Engine runners ──────────────────────────────────────────────────────

    def _run_tesseract(self, image: np.ndarray) -> OCRResult:
        """
        Run Tesseract OCR and extract word-level results with bounding boxes.

        Args:
            image: Preprocessed binary numpy array.

        Returns:
            OCRResult with word-level data from Tesseract.
        """
        if not _TESSERACT_AVAILABLE:
            return self._empty_result(engine="tesseract")

        try:
            config = self.TESSERACT_CONFIG
            # Get word-level data with confidence and bounding boxes
            data = pytesseract.image_to_data(
                image,
                config=config,
                output_type=pytesseract.Output.DICT,
            )

            words: List[WordResult] = []
            raw_text_lines: List[str] = []

            n = len(data["text"])
            for i in range(n):
                text = str(data["text"][i]).strip()
                conf = int(data["conf"][i])

                if not text or conf < 0:
                    continue

                bbox = [
                    data["left"][i],
                    data["top"][i],
                    data["left"][i] + data["width"][i],
                    data["top"][i] + data["height"][i],
                ]
                words.append({
                    "text": text,
                    "bbox": bbox,
                    "confidence": conf / 100.0,  # Normalize to 0-1
                    "engine": "tesseract",
                })
                raw_text_lines.append(text)

            return {
                "raw_text": " ".join(raw_text_lines),
                "words": words,
                "overall_confidence": 0.0,  # Computed later
                "language_detected": "en",
                "engine": "tesseract",
            }

        except Exception as exc:
            logger.error("Tesseract OCR failed: %s", exc)
            return self._empty_result(engine="tesseract")

    def _run_easyocr(self, image: np.ndarray) -> OCRResult:
        """
        Run EasyOCR and extract word/phrase-level results.

        EasyOCR returns (bbox, text, confidence) tuples where bbox is
        a list of 4 corner points [[x1,y1],[x2,y2],[x3,y3],[x4,y4]].

        Args:
            image: Preprocessed binary numpy array.

        Returns:
            OCRResult with word-level data from EasyOCR.
        """
        if not _EASYOCR_AVAILABLE or self.easy_reader is None:
            return self._empty_result(engine="easyocr")

        try:
            results = self.easy_reader.readtext(image, detail=1)
            words: List[WordResult] = []
            raw_parts: List[str] = []

            for bbox_pts, text, confidence in results:
                text = text.strip()
                if not text:
                    continue

                # Convert 4-point bbox to [x_min, y_min, x_max, y_max]
                xs = [p[0] for p in bbox_pts]
                ys = [p[1] for p in bbox_pts]
                bbox = [min(xs), min(ys), max(xs), max(ys)]

                words.append({
                    "text": text,
                    "bbox": bbox,
                    "confidence": float(confidence),
                    "engine": "easyocr",
                })
                raw_parts.append(text)

            return {
                "raw_text": " ".join(raw_parts),
                "words": words,
                "overall_confidence": 0.0,
                "language_detected": "en",
                "engine": "easyocr",
            }

        except Exception as exc:
            logger.error("EasyOCR failed: %s", exc)
            return self._empty_result(engine="easyocr")

    # ─── Merge ───────────────────────────────────────────────────────────────

    def _merge_ocr_results(
        self, tesseract_result: OCRResult, easyocr_result: OCRResult
    ) -> OCRResult:
        """
        Merge Tesseract and EasyOCR results using bounding box IOU alignment.

        For each EasyOCR word region, we look for an overlapping Tesseract word.
        - If IOU >= threshold and EasyOCR confidence >= Tesseract → keep EasyOCR
        - Otherwise → keep Tesseract word
        - Unmatched EasyOCR words (no overlap found) → include with penalty

        If only one engine produced results, that engine's output is returned.

        Args:
            tesseract_result: OCRResult from Tesseract engine.
            easyocr_result:   OCRResult from EasyOCR engine.

        Returns:
            Merged OCRResult.
        """
        tess_words = tesseract_result.get("words", [])
        easy_words = easyocr_result.get("words", [])

        # Fallback if one engine produced nothing
        if not tess_words:
            return {**easyocr_result, "engine": "easyocr"}
        if not easy_words:
            return {**tesseract_result, "engine": "tesseract"}

        merged_words: List[WordResult] = []
        used_tess_indices = set()

        for easy_word in easy_words:
            best_iou = 0.0
            best_tess_idx = -1

            for i, tess_word in enumerate(tess_words):
                if i in used_tess_indices:
                    continue
                iou = _compute_iou(easy_word["bbox"], tess_word["bbox"])
                if iou > best_iou:
                    best_iou = iou
                    best_tess_idx = i

            if best_iou >= self.IOU_MERGE_THRESHOLD and best_tess_idx >= 0:
                tess_word = tess_words[best_tess_idx]
                used_tess_indices.add(best_tess_idx)

                # Pick higher-confidence result
                if easy_word["confidence"] >= tess_word["confidence"]:
                    merged_words.append({**easy_word, "engine": "easyocr"})
                else:
                    merged_words.append({**tess_word, "engine": "tesseract"})
            else:
                # No match found — include EasyOCR with slight confidence penalty
                merged_words.append({
                    **easy_word,
                    "confidence": easy_word["confidence"] * 0.85,
                    "engine": "easyocr_unmatched",
                })

        # Include Tesseract words that had no EasyOCR match
        for i, tess_word in enumerate(tess_words):
            if i not in used_tess_indices:
                merged_words.append({**tess_word, "engine": "tesseract_unmatched"})

        # Sort words left-to-right, top-to-bottom for natural reading order
        merged_words.sort(key=lambda w: (w["bbox"][1] // 20, w["bbox"][0]))

        raw_text = " ".join(w["text"] for w in merged_words)

        return {
            "raw_text": raw_text,
            "words": merged_words,
            "overall_confidence": 0.0,  # Set by caller
            "language_detected": "en",
            "engine": "merged",
        }

    # ─── Post-processing ─────────────────────────────────────────────────────

    def _fix_medical_ocr_errors(self, text: str) -> str:
        """
        Apply sequential regex corrections for common medical OCR mistakes.

        Corrections are defined in medical_constants.OCR_CORRECTIONS.
        Applied in order, so earlier patterns are not affected by later ones.

        Args:
            text: Raw OCR output string.

        Returns:
            Corrected text string.
        """
        for pattern, replacement in OCR_CORRECTIONS:
            try:
                text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
            except re.error as e:
                logger.debug("Regex error in OCR correction (%s): %s", pattern, e)
        return text

    # ─── Helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _empty_result(engine: str = "none") -> OCRResult:
        """Return an empty OCR result structure."""
        return {
            "raw_text": "",
            "words": [],
            "overall_confidence": 0.0,
            "language_detected": "unknown",
            "engine": engine,
            "processing_time_ms": 0,
        }


# ─── IOU Helper ──────────────────────────────────────────────────────────────

def _compute_iou(box_a: List[float], box_b: List[float]) -> float:
    """
    Compute Intersection over Union for two axis-aligned bounding boxes.

    Args:
        box_a: [x_min, y_min, x_max, y_max]
        box_b: [x_min, y_min, x_max, y_max]

    Returns:
        IOU float in [0.0, 1.0].
    """
    xa = max(box_a[0], box_b[0])
    ya = max(box_a[1], box_b[1])
    xb = min(box_a[2], box_b[2])
    yb = min(box_a[3], box_b[3])

    inter_area = max(0.0, xb - xa) * max(0.0, yb - ya)
    if inter_area == 0.0:
        return 0.0

    area_a = max(0.0, box_a[2] - box_a[0]) * max(0.0, box_a[3] - box_a[1])
    area_b = max(0.0, box_b[2] - box_b[0]) * max(0.0, box_b[3] - box_b[1])
    union_area = area_a + area_b - inter_area

    if union_area <= 0.0:
        return 0.0
    return inter_area / union_area


# ─── Module-level singleton ───────────────────────────────────────────────────

_extractor: Optional[OCRExtractor] = None


def get_extractor(
    languages: List[str] = None,
    gpu: bool = False,
) -> OCRExtractor:
    """Return (or lazily create) the module-level OCRExtractor singleton."""
    global _extractor
    if _extractor is None:
        _extractor = OCRExtractor(languages=languages, gpu=gpu)
    return _extractor
