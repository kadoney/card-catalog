# OCR configuration — shared by all ETL scripts that need Tesseract + Poppler
# Installed 2026-04-06 via winget

TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

POPPLER_PATH = (
    r"C:\Users\kdone\AppData\Local\Microsoft\WinGet\Packages"
    r"\oschwartz10612.Poppler_Microsoft.Winget.Source_8wekyb3d8bbwe"
    r"\poppler-25.07.0\Library\bin"
)


def configure_ocr():
    """Call once at startup to configure pytesseract."""
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
