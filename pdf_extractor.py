from __future__ import annotations

import io
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from dateutil import parser as date_parser
from pypdf import PdfReader


FIELD_ALIASES = {
    "document_number": [
        "document number",
        "document no.",
        "document no",
        "doc number",
        "doc no.",
        "doc no",
        "drawing number",
        "drawing no.",
        "drawing no",
        "dwg number",
        "dwg no.",
        "dwg no",
        "sheet number",
        "sheet no.",
        "sheet no",
    ],
    "title": [
        "document title",
        "drawing title",
        "sheet title",
        "title",
    ],
    "revision": [
        "current revision",
        "document revision",
        "revision",
        "rev.",
        "rev",
    ],
    "project": [
        "project name",
        "project",
        "job name",
        "contract",
    ],
    "discipline": [
        "document discipline",
        "discipline",
        "department",
    ],
    "status": [
        "document status",
        "purpose of issue",
        "suitability status",
        "suitability",
        "status",
    ],
    "owner": [
        "document owner",
        "owner",
        "responsible person",
    ],
    "originator": [
        "originator",
        "prepared by",
        "author",
        "organisation",
        "organization",
        "company",
    ],
    "created_date": [
        "created date",
        "issue date",
        "document date",
        "date issued",
    ],
    "due_date": [
        "response due date",
        "review due date",
        "due date",
    ],
}


DISCIPLINE_KEYWORDS = {
    "Engineering": ["engineering", "engineer"],
    "Design": ["design", "designer"],
    "Quality": ["quality", "qa", "qc"],
    "HSE": ["hse", "health and safety", "health & safety", "environment"],
    "Commercial": ["commercial", "cost", "quantity surveying"],
    "Project Controls": ["project controls", "planning", "planner", "schedule"],
    "Construction": ["construction", "site"],
    "Mechanical": ["mechanical", "mech"],
    "Electrical": ["electrical", "elec"],
    "Civil": ["civil", "structural", "structure"],
}


STATUS_KEYWORDS = {
    "Draft": ["draft", "work in progress", "wip"],
    "For Review": ["for review", "review", "s3"],
    "For Information": ["for information", "information", "s2"],
    "Approved": ["approved", "accepted", "a1"],
    "Approved with Comments": [
        "approved with comments",
        "accepted with comments",
        "a2",
    ],
    "Rejected": ["rejected", "not accepted", "a3"],
    "Superseded": ["superseded", "obsolete"],
    "Missing Information": ["missing information", "incomplete"],
    "Closed": ["closed"],
}


def _clean_value(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\x00", " ").strip()
    text = re.sub(r"\s+", " ", text)
    return text.strip(" |:;,-")


def _normalise_label(value: str) -> str:
    value = value.casefold()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _useful_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw_line in text.splitlines():
        line = _clean_value(raw_line)
        if line and len(line) <= 300:
            lines.append(line)
    return lines


def _extract_labelled_value(
    lines: list[str],
    aliases: list[str],
) -> tuple[str, str]:
    sorted_aliases = sorted(aliases, key=len, reverse=True)

    for index, line in enumerate(lines):
        normalised_line = _normalise_label(line)

        for alias in sorted_aliases:
            normalised_alias = _normalise_label(alias)

            same_line_patterns = [
                rf"^\s*{re.escape(alias)}\s*[:\-]\s*(.+)$",
                rf"^\s*{re.escape(alias)}\s+(.+)$",
            ]
            for pattern in same_line_patterns:
                match = re.match(pattern, line, flags=re.IGNORECASE)
                if match:
                    value = _clean_value(match.group(1))
                    if value and _normalise_label(value) != normalised_alias:
                        return value, f"PDF label: {alias}"

            if normalised_line == normalised_alias:
                for next_index in range(index + 1, min(index + 3, len(lines))):
                    candidate = _clean_value(lines[next_index])
                    if candidate and not any(
                        _normalise_label(candidate) == _normalise_label(other)
                        for field_aliases in FIELD_ALIASES.values()
                        for other in field_aliases
                    ):
                        return candidate, f"PDF label: {alias}"

    return "", ""


def _safe_pdf_metadata_title(reader: PdfReader) -> str:
    try:
        metadata = reader.metadata
        if metadata and metadata.title:
            return _clean_value(metadata.title)
    except Exception:
        pass
    return ""


def _normalise_revision(value: str) -> str:
    value = _clean_value(value).upper()
    value = re.sub(r"^(REVISION|REV\.?|REV)\s*", "", value, flags=re.IGNORECASE)
    match = re.search(r"\b(?:P|C|S)?\d{1,3}\b|\b[A-Z]\d{1,2}\b|\b[A-Z]\b", value)
    return match.group(0).upper() if match else value[:30]


def _filename_fallbacks(file_name: str) -> dict[str, str]:
    stem = Path(file_name).stem.strip()
    result = {"document_number": "", "revision": "", "title": ""}

    revision_match = re.search(
        r"(?:^|[-_.\s])((?:P|C|S)\d{1,3}|[A-Z]\d{1,2}|[A-Z])$",
        stem,
        flags=re.IGNORECASE,
    )
    if revision_match:
        result["revision"] = revision_match.group(1).upper()
        possible_number = stem[: revision_match.start()].rstrip("-_. ")
    else:
        possible_number = stem

    if (
        re.search(r"\d", possible_number)
        and len(re.findall(r"[-_.]", possible_number)) >= 2
        and 5 <= len(possible_number) <= 120
    ):
        result["document_number"] = possible_number

    return result


def _map_controlled_value(
    raw_value: str,
    keyword_map: dict[str, list[str]],
) -> str:
    normalised = _normalise_label(raw_value)
    if not normalised:
        return ""

    for controlled_value, keywords in keyword_map.items():
        for keyword in keywords:
            keyword_normalised = _normalise_label(keyword)
            if (
                normalised == keyword_normalised
                or keyword_normalised in normalised
            ):
                return controlled_value

    return _clean_value(raw_value)


def _parse_date(value: str) -> str:
    value = _clean_value(value)
    if not value:
        return ""

    try:
        parsed = date_parser.parse(value, dayfirst=True, fuzzy=True)
    except (ValueError, TypeError, OverflowError):
        return ""

    if parsed.year < 1980 or parsed.year > datetime.now().year + 20:
        return ""

    return parsed.date().isoformat()


def _looks_like_title(value: str) -> bool:
    value = _clean_value(value)
    if not value or len(value) < 4 or len(value) > 180:
        return False
    if re.fullmatch(r"[\W\d_]+", value):
        return False
    return True


def extract_pdf_metadata(
    file_bytes: bytes,
    file_name: str,
    max_pages: int = 5,
) -> dict[str, Any]:
    """
    Extract suggested document-control metadata from a text-based PDF.

    The returned values are suggestions only and must be reviewed by a person
    before they are saved to the controlled register.
    """
    if not file_bytes.startswith(b"%PDF-"):
        raise ValueError("The selected file does not contain a valid PDF signature.")

    reader = PdfReader(io.BytesIO(file_bytes))

    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as error:
            raise ValueError(
                "The PDF is password protected and cannot be read."
            ) from error

    page_text: list[str] = []
    pages_to_read = min(len(reader.pages), max_pages)

    for page_number in range(pages_to_read):
        try:
            extracted = reader.pages[page_number].extract_text() or ""
        except Exception:
            extracted = ""
        if extracted.strip():
            page_text.append(extracted)

    text = "\n".join(page_text)
    lines = _useful_lines(text)
    metadata: dict[str, str] = {
        "document_number": "",
        "title": "",
        "project": "",
        "discipline": "",
        "revision": "",
        "status": "",
        "owner": "",
        "originator": "",
        "created_date": "",
        "due_date": "",
        "file_name": file_name,
        "notes": "",
    }
    sources: dict[str, str] = {
        field: "" for field in metadata
    }
    sources["file_name"] = "Uploaded filename"

    for field, aliases in FIELD_ALIASES.items():
        value, source = _extract_labelled_value(lines, aliases)
        metadata[field] = value
        sources[field] = source

    metadata["revision"] = _normalise_revision(metadata["revision"])
    metadata["discipline"] = _map_controlled_value(
        metadata["discipline"], DISCIPLINE_KEYWORDS
    )
    metadata["status"] = _map_controlled_value(
        metadata["status"], STATUS_KEYWORDS
    )
    metadata["created_date"] = _parse_date(metadata["created_date"])
    metadata["due_date"] = _parse_date(metadata["due_date"])

    filename_values = _filename_fallbacks(file_name)
    for field in ["document_number", "revision"]:
        if not metadata[field] and filename_values[field]:
            metadata[field] = filename_values[field]
            sources[field] = "Uploaded filename"

    pdf_title = _safe_pdf_metadata_title(reader)
    if not metadata["title"] and _looks_like_title(pdf_title):
        metadata["title"] = pdf_title
        sources["title"] = "PDF document properties"

    if not metadata["discipline"]:
        metadata["discipline"] = _map_controlled_value(text, DISCIPLINE_KEYWORDS)
        if metadata["discipline"]:
            sources["discipline"] = "Keyword found in PDF text"

    warnings: list[str] = []

    if not text.strip():
        warnings.append(
            "No selectable text was found. This may be a scanned/image PDF, "
            "so the metadata must be entered manually."
        )

    missing_key_fields = [
        field
        for field in ["document_number", "title", "revision"]
        if not metadata[field]
    ]
    if missing_key_fields:
        warnings.append(
            "The following fields were not confidently detected: "
            + ", ".join(field.replace("_", " ").title() for field in missing_key_fields)
            + "."
        )

    metadata["notes"] = (
        "Metadata was suggested from the uploaded PDF and reviewed by a person "
        "before saving."
    )
    sources["notes"] = "System note"

    return {
        "metadata": metadata,
        "sources": sources,
        "pages_read": pages_to_read,
        "total_pages": len(reader.pages),
        "text_preview": text[:6000],
        "warnings": warnings,
    }
