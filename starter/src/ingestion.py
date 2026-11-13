"""Read physical PDF pages. Preserve line structure; log empty/failed pages."""

import logging
import re
import unicodedata
from pathlib import Path
from pypdf import PdfReader
from .models import DocumentPage

logger = logging.getLogger(__name__)


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\x00", "")
    lines = [re.sub(r"[^\S\n]+", " ", line).strip() for line in text.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def load_pdf(path: Path, document_id: str, source: str) -> list[DocumentPage]:
    reader = PdfReader(path)
    pages = []
    for number, page in enumerate(reader.pages, 1):
        try:
            text = normalize_text(page.extract_text() or "")
        except Exception:
            logger.exception(
                "PDF extraction failed: %s physical page %s", source, number
            )
            raise
        if not text:
            logger.warning("No extractable text: %s physical page %s", source, number)
        pages.append(DocumentPage(document_id, source, number, text))
    return pages
