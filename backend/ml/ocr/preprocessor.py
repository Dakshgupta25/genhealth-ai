"""
Image preprocessing pipeline for medical document OCR.

Applies a series of classical computer-vision transformations to maximize
Tesseract and EasyOCR accuracy on prescription photos and scan images.
"""

import logging
from typing import Optional, Tuple

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


def load_image(image_path: str) -> np.ndarray:
    """
    Load an image from disk, handling JPEG, PNG, WEBP, HEIC, and BMP.

    For HEIC files, pillow-heif is used as a bridge to Pillow.

    Args:
        image_path: Absolute or relative path to the image file.

    Returns:
        BGR numpy array (OpenCV format).

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file cannot be decoded as an image.
    """
    path_lower = image_path.lower()

    # HEIC / HEIF support (common on iPhone photos)
    if path_lower.endswith((".heic", ".heif")):
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
        except ImportError:
            logger.warning("pillow-heif not installed. HEIC support unavailable.")
        pil_img = Image.open(image_path).convert("RGB")
        return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    # Standard image loading via OpenCV
    img = cv2.imread(image_path)
    if img is None:
        # Fallback: use Pillow (handles some formats OpenCV misses)
        try:
            pil_img = Image.open(image_path).convert("RGB")
            img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        except Exception as e:
            raise ValueError(f"Cannot decode image at '{image_path}': {e}") from e

    if img is None:
        raise FileNotFoundError(f"Image not found or unreadable: '{image_path}'")

    return img


def to_grayscale(image: np.ndarray) -> np.ndarray:
    """Convert a BGR image to grayscale. No-op if already grayscale."""
    if len(image.shape) == 3 and image.shape[2] == 3:
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return image


def deskew(image: np.ndarray) -> np.ndarray:
    """
    Detect and correct the rotation angle of a scanned document.

    Algorithm:
    1. Apply Canny edge detection.
    2. Run probabilistic Hough Line Transform to detect dominant line angles.
    3. Compute the median angle from the most horizontal lines.
    4. Rotate the image by the negative of this angle to straighten it.

    Args:
        image: Grayscale numpy array.

    Returns:
        Deskewed grayscale numpy array (same shape, black padding on edges).
    """
    edges = cv2.Canny(image, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(
        edges, 1, np.pi / 180, threshold=80,
        minLineLength=max(50, image.shape[1] // 10),
        maxLineGap=10,
    )

    if lines is None or len(lines) == 0:
        logger.debug("Deskew: No lines detected, skipping rotation.")
        return image

    angles = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        if x2 != x1:  # Avoid vertical lines
            angle_deg = np.degrees(np.arctan2(y2 - y1, x2 - x1))
            # Only include near-horizontal lines (±30°)
            if -30 <= angle_deg <= 30:
                angles.append(angle_deg)

    if not angles:
        return image

    median_angle = float(np.median(angles))

    # Ignore tiny angles to avoid over-correction
    if abs(median_angle) < 0.4:
        logger.debug("Deskew: Angle %.2f° too small, skipping.", median_angle)
        return image

    logger.debug("Deskew: Correcting rotation by %.2f°.", median_angle)
    h, w = image.shape[:2]
    center = (w // 2, h // 2)
    rotation_matrix = cv2.getRotationMatrix2D(center, median_angle, 1.0)
    rotated = cv2.warpAffine(
        image, rotation_matrix, (w, h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=255,  # White background
    )
    return rotated


def denoise(image: np.ndarray) -> np.ndarray:
    """
    Apply non-local means denoising to reduce scan noise.

    Uses cv2.fastNlMeansDenoising with parameters tuned for text documents.

    Args:
        image: Grayscale numpy array.

    Returns:
        Denoised grayscale numpy array.
    """
    return cv2.fastNlMeansDenoising(image, None, h=10, templateWindowSize=7, searchWindowSize=21)


def adaptive_threshold(image: np.ndarray) -> np.ndarray:
    """
    Apply Gaussian adaptive thresholding to binarize the image.

    Adaptive thresholding handles uneven lighting better than global methods,
    which is critical for photos taken in varying ambient light.

    Args:
        image: Grayscale numpy array.

    Returns:
        Binary (0/255) numpy array.
    """
    return cv2.adaptiveThreshold(
        image,
        maxValue=255,
        adaptiveMethod=cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        thresholdType=cv2.THRESH_BINARY,
        blockSize=11,  # Neighbourhood size (must be odd)
        C=2,           # Constant subtracted from mean
    )


def morphological_sharpen(binary_image: np.ndarray) -> np.ndarray:
    """
    Apply morphological erosion followed by dilation to sharpen text strokes.

    The erode-then-dilate cycle (opening) removes isolated noise pixels
    while preserving text stroke width.

    Args:
        binary_image: Binarized numpy array.

    Returns:
        Morphologically processed numpy array.
    """
    kernel = np.ones((1, 1), np.uint8)
    eroded = cv2.erode(binary_image, kernel, iterations=1)
    dilated = cv2.dilate(eroded, kernel, iterations=1)
    return dilated


def scale_to_min_dpi(image: np.ndarray, target_dpi: int = 300, assumed_dpi: int = 72) -> np.ndarray:
    """
    Upscale the image if it appears to be below the target DPI.

    Tesseract accuracy degrades below ~200 DPI. We assume phone photos
    are captured at 72 DPI equivalent and scale to 300 DPI.

    Args:
        image:       Grayscale or binary numpy array.
        target_dpi:  Desired DPI (default 300).
        assumed_dpi: Assumed source DPI for small images (default 72).

    Returns:
        Potentially upscaled numpy array.
    """
    h, w = image.shape[:2]
    scale_factor = target_dpi / assumed_dpi

    # Only upscale if the image is small enough to benefit
    if w < 1500 or h < 1000:
        new_w = int(w * scale_factor)
        new_h = int(h * scale_factor)
        logger.debug("Scaling image from (%d, %d) to (%d, %d).", w, h, new_w, new_h)
        return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_CUBIC)

    return image


def preprocess_image(image_path: str) -> np.ndarray:
    """
    Full preprocessing pipeline for medical document images.

    Steps applied in order:
    1. Load image (JPEG, PNG, WEBP, HEIC)
    2. Convert to grayscale
    3. Scale to at least 300 DPI equivalent
    4. Deskew (detect and correct rotation via Hough transform)
    5. Denoise (NL-means denoising)
    6. Adaptive thresholding (ADAPTIVE_THRESH_GAUSSIAN_C)
    7. Morphological operations (erode + dilate, kernel 1×1)

    Args:
        image_path: Path to the input image file.

    Returns:
        Processed binary numpy array ready for OCR.

    Example:
        >>> processed = preprocess_image("/path/to/prescription.jpg")
        >>> text = pytesseract.image_to_string(processed)
    """
    logger.info("Preprocessing image: %s", image_path)

    img = load_image(image_path)
    gray = to_grayscale(img)
    scaled = scale_to_min_dpi(gray)
    deskewed = deskew(scaled)
    denoised = denoise(deskewed)
    binary = adaptive_threshold(denoised)
    sharpened = morphological_sharpen(binary)

    logger.info(
        "Preprocessing complete. Output shape: %s",
        sharpened.shape,
    )
    return sharpened


def detect_document_corners(image: np.ndarray) -> Optional[np.ndarray]:
    """
    Detect the 4 corners of a document in a photograph for perspective correction.

    Uses Canny edge detection + contour finding + Douglas-Peucker approximation
    to locate the largest quadrilateral in the image (assumed to be the document).

    Args:
        image: BGR or grayscale numpy array (original, not binarized).

    Returns:
        4×2 numpy array of corner points (top-left, top-right, bottom-right, bottom-left)
        ordered clockwise, or None if no quadrilateral found.
    """
    # Work on grayscale
    gray = to_grayscale(image) if len(image.shape) == 3 else image.copy()

    # Blur to reduce noise before edge detection
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 75, 200)

    # Find contours, take the largest ones
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]

    for contour in contours:
        # Approximate contour to polygon
        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)

        if len(approx) == 4:
            logger.info("Document corners detected.")
            return approx.reshape(4, 2).astype(np.float32)

    logger.debug("No document quadrilateral found.")
    return None


def perspective_correct(image: np.ndarray, corners: np.ndarray) -> np.ndarray:
    """
    Apply perspective transform to get a top-down view of a document.

    Args:
        image:   Original BGR or grayscale image.
        corners: 4×2 array of corner points.

    Returns:
        Perspective-corrected image (A4 aspect ratio: 595×842 pixels).
    """
    output_w, output_h = 595, 842  # A4 at 72 DPI

    # Order corners: top-left, top-right, bottom-right, bottom-left
    rect = _order_points(corners)
    dst = np.array([
        [0, 0],
        [output_w - 1, 0],
        [output_w - 1, output_h - 1],
        [0, output_h - 1],
    ], dtype=np.float32)

    M = cv2.getPerspectiveTransform(rect, dst)
    warped = cv2.warpPerspective(image, M, (output_w, output_h))
    return warped


def enhance_for_handwriting(image: np.ndarray) -> np.ndarray:
    """
    Apply additional enhancement optimized for handwritten prescriptions.

    Handwriting has lower contrast and more variation than printed text.
    This function applies:
    - CLAHE (Contrast Limited Adaptive Histogram Equalization) for local contrast
    - Bilateral filtering to preserve sharp pen stroke edges while smoothing noise

    Args:
        image: Grayscale numpy array (not yet binarized).

    Returns:
        Enhanced grayscale numpy array.
    """
    # CLAHE: adaptive contrast enhancement
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    equalized = clahe.apply(image)

    # Bilateral filter: edge-preserving smoothing (preserves pen strokes)
    smoothed = cv2.bilateralFilter(equalized, d=9, sigmaColor=75, sigmaSpace=75)

    return smoothed


def preprocess_handwritten(image_path: str) -> np.ndarray:
    """
    Full preprocessing pipeline for handwritten prescription photos.

    Extends the standard pipeline with CLAHE + bilateral filtering
    before binarization for better handwriting legibility.

    Args:
        image_path: Path to the handwritten prescription image.

    Returns:
        Processed binary numpy array.
    """
    img = load_image(image_path)
    gray = to_grayscale(img)
    scaled = scale_to_min_dpi(gray)
    deskewed = deskew(scaled)
    enhanced = enhance_for_handwriting(deskewed)
    denoised = denoise(enhanced)
    binary = adaptive_threshold(denoised)
    return morphological_sharpen(binary)


# ─── Private helpers ──────────────────────────────────────────────────────────

def _order_points(pts: np.ndarray) -> np.ndarray:
    """
    Order 4 corner points as: top-left, top-right, bottom-right, bottom-left.

    Args:
        pts: 4×2 array of unordered corner points.

    Returns:
        4×2 array in clockwise order starting from top-left.
    """
    rect = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]   # Top-left: smallest x+y
    rect[2] = pts[np.argmax(s)]   # Bottom-right: largest x+y
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]  # Top-right: smallest y-x
    rect[3] = pts[np.argmax(diff)]  # Bottom-left: largest y-x
    return rect
