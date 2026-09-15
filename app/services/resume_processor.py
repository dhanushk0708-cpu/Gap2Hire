import re

import fitz  # PyMuPDF


class NoExtractableTextError(Exception):
    pass


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    normalized = re.sub(r"\n{3,}", "\n\n", "\n".join(lines))
    return normalized.strip()


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        raise NoExtractableTextError("Failed to open or parse PDF document") from exc

    page_texts = []
    for page in doc:
        text = page.get_text("text")
        if text:
            page_texts.append(text)

    combined_text = "\n\n".join(page_texts)
    normalized = normalize_text(combined_text)

    if not normalized or len(re.sub(r"\s+", "", normalized)) < 10:
        raise NoExtractableTextError("No extractable text found in resume. Scanned PDFs are not currently supported.")

    return normalized
