"""OCR extraction from images.

Default backend is Tesseract (free, self-hosted, per the scope doc's
preferred option). Google Vision / AWS Textract are stubbed as alternative
backends selectable via OCR_BACKEND, without changing any calling code.
"""
import io

from PIL import Image

from app.core.config import get_settings
from app.ingestion.models import ExtractedDocument, InputKind


def _ocr_tesseract(data: bytes) -> str:
    import pytesseract

    settings = get_settings()
    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd

    image = Image.open(io.BytesIO(data))
    return pytesseract.image_to_string(image).strip()


def _ocr_google_vision(data: bytes) -> str:
    raise NotImplementedError(
        "Google Cloud Vision OCR backend is not wired up yet. "
        "Set OCR_BACKEND=tesseract, or implement this using the google-cloud-vision SDK."
    )


def _ocr_aws_textract(data: bytes) -> str:
    raise NotImplementedError(
        "AWS Textract OCR backend is not wired up yet. "
        "Set OCR_BACKEND=tesseract, or implement this using boto3's textract client."
    )


def load_image(source_name: str, data: bytes) -> ExtractedDocument:
    settings = get_settings()
    backend = {
        "tesseract": _ocr_tesseract,
        "google_vision": _ocr_google_vision,
        "aws_textract": _ocr_aws_textract,
    }[settings.ocr_backend]

    text = backend(data)
    warnings = [] if text else ["OCR returned no text; the image may be low quality."]

    return ExtractedDocument(
        source_name=source_name, kind=InputKind.IMAGE, raw_text=text, warnings=warnings
    )
