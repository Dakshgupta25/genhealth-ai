import cv2
import pytesseract

def main():
    img = cv2.imread("test.jpg")
    print("Running Tesseract OSD...")
    try:
        osd = pytesseract.image_to_osd(img)
        print("--- OSD OUTPUT ---")
        print(osd)
        print("----------------")
    except Exception as e:
        print("OSD Failed:", e)

if __name__ == "__main__":
    main()
