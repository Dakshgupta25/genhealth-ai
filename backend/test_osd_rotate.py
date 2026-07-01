import cv2
import pytesseract
import json
from ml.ocr.extractor import get_extractor
from ml.nlp.entity_extractor import get_entity_extractor

def rotate_image(image, angle):
    if angle == 90:
        return cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
    elif angle == 180:
        return cv2.rotate(image, cv2.ROTATE_180)
    elif angle == 270:
        return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
    return image

def main():
    img = cv2.imread("test.jpg")
    print("Running Tesseract OSD...")
    angle = 0
    try:
        osd = pytesseract.image_to_osd(img)
        print("OSD Output:")
        print(osd)
        for line in osd.split("\n"):
            if "Orientation in degrees:" in line:
                angle = int(line.split(":")[1].strip())
                print(f"Detected orientation angle: {angle}")
                break
    except Exception as e:
        print("OSD Failed:", e)

    if angle != 0:
        print(f"Rotating image by {angle} equivalent correction...")
        img = rotate_image(img, angle)
        cv2.imwrite("test_fixed.jpg", img)
    else:
        cv2.imwrite("test_fixed.jpg", img)

    print("Running OCR on test_fixed.jpg...")
    ocr = get_extractor()
    ocr_res = ocr.extract_from_image("test_fixed.jpg")
    raw_text = ocr_res.get("raw_text", "")
    print(f"Raw text characters: {len(raw_text)}")
    print("--- RAW TEXT ---")
    print(raw_text[:500])
    print("----------------")

    print("Running NLP extraction...")
    nlp = get_entity_extractor()
    nlp_res = nlp.extract(raw_text)
    print("--- EXTRACTED ENTITIES ---")
    print(json.dumps(nlp_res, indent=2))

if __name__ == "__main__":
    main()
