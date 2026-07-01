import json
from ml.ocr.extractor import get_extractor
from ml.nlp.entity_extractor import get_entity_extractor

def main():
    print("Initializing OCR Extractor...")
    ocr = get_extractor()
    print("Running OCR on test.jpg...")
    ocr_res = ocr.extract_from_image("test.jpg")
    raw_text = ocr_res.get("raw_text", "")
    print(f"Raw text characters: {len(raw_text)}")
    print("--- RAW TEXT ---")
    print(raw_text)
    print("----------------")

    print("Initializing NLP Extractor...")
    nlp = get_entity_extractor()
    print("Running NLP extraction...")
    nlp_res = nlp.extract(raw_text)
    print("--- EXTRACTED ENTITIES ---")
    print(json.dumps(nlp_res, indent=2))

if __name__ == "__main__":
    main()
