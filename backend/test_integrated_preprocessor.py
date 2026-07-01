import cv2
from ml.ocr.preprocessor import preprocess_image

def main():
    print("Running integrated preprocessor on test.jpg...")
    try:
        binary = preprocess_image("test.jpg")
        print(f"Preprocessed successfully! Shape: {binary.shape}")
        cv2.imwrite("test_integrated_output.jpg", binary)
        print("Saved to test_integrated_output.jpg")
    except Exception as e:
        print("Failed:", e)

if __name__ == "__main__":
    main()
