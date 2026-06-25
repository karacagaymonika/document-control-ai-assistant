from __future__ import annotations

import io
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from dateutil import parser as date_parser
from pypdf import PdfReader


BASE_FIELD_ALIASES = {
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
        "date received",
    ],
    "due_date": [
        "response due date",
        "review due date",
        "due date",
    ],
}


LANGUAGE_FIELD_ALIASES = {
    "English": {},
    "Polish": {
        "document_number": [
            "numer dokumentu",
            "nr dokumentu",
            "numer rysunku",
            "nr rysunku",
        ],
        "title": [
            "tytuł dokumentu",
            "tytul dokumentu",
            "tytuł rysunku",
            "tytul rysunku",
            "nazwa dokumentu",
            "tytuł",
            "tytul",
        ],
        "revision": ["rewizja", "wersja", "wydanie"],
        "project": ["nazwa projektu", "projekt", "kontrakt"],
        "discipline": ["branża", "branza", "dyscyplina", "dział", "dzial"],
        "status": ["status dokumentu", "cel wydania", "status"],
        "owner": [
            "właściciel dokumentu",
            "wlasciciel dokumentu",
            "osoba odpowiedzialna",
            "odpowiedzialny",
        ],
        "originator": [
            "autor",
            "opracował",
            "opracowal",
            "sporządził",
            "sporzadzil",
            "firma",
            "organizacja",
        ],
        "created_date": [
            "data utworzenia",
            "data wydania",
            "data dokumentu",
            "data otrzymania",
        ],
        "due_date": ["termin", "data wymagana", "termin odpowiedzi"],
    },
    "Arabic": {
        "document_number": ["رقم الوثيقة", "رقم المستند", "رقم الرسم"],
        "title": ["عنوان الوثيقة", "عنوان المستند", "عنوان الرسم", "العنوان"],
        "revision": ["المراجعة", "الإصدار", "النسخة"],
        "project": ["اسم المشروع", "المشروع", "العقد"],
        "discipline": ["التخصص", "القسم", "المجال"],
        "status": ["حالة الوثيقة", "حالة المستند", "غرض الإصدار", "الحالة"],
        "owner": ["مالك الوثيقة", "مالك المستند", "المسؤول"],
        "originator": [
            "المنشئ",
            "أعد بواسطة",
            "إعداد",
            "المؤلف",
            "الشركة",
            "المنظمة",
        ],
        "created_date": [
            "تاريخ الإنشاء",
            "تاريخ الإصدار",
            "تاريخ الوثيقة",
            "تاريخ الاستلام",
        ],
        "due_date": ["تاريخ الاستحقاق", "موعد الرد", "تاريخ المراجعة"],
    },
    "Other": {},
}


DISCIPLINE_KEYWORDS = {
    "Engineering": ["engineering", "engineer", "inżynieria", "inzynieria", "هندسة"],
    "Design": ["design", "designer", "projektowanie", "تصميم"],
    "Quality": ["quality", "qa", "qc", "jakość", "jakosc", "جودة"],
    "HSE": [
        "hse",
        "health and safety",
        "health & safety",
        "environment",
        "bhp",
        "bezpieczeństwo",
        "bezpieczenstwo",
        "سلامة",
        "بيئة",
    ],
    "Commercial": ["commercial", "cost", "quantity surveying", "komercyjny", "تجاري"],
    "Project Controls": [
        "project controls",
        "planning",
        "planner",
        "schedule",
        "harmonogram",
        "planowanie",
        "ضبط المشروع",
        "تخطيط",
    ],
    "Construction": ["construction", "site", "budowa", "wykonawstwo", "إنشاءات", "موقع"],
    "Mechanical": ["mechanical", "mech", "mechaniczna", "mechaniczny", "ميكانيكا"],
    "Electrical": ["electrical", "elec", "elektryczna", "elektryczny", "كهرباء"],
    "Civil": [
        "civil",
        "structural",
        "structure",
        "budowlana",
        "konstrukcyjna",
        "مدني",
        "إنشائي",
    ],
}


STATUS_KEYWORDS = {
    "Draft": ["draft", "work in progress", "wip", "roboczy", "projekt", "مسودة"],
    "For Review": ["for review", "review", "s3", "do przeglądu", "do przegladu", "للمراجعة"],
    "For Information": [
        "for information",
        "information",
        "s2",
        "do informacji",
        "للمعلومات",
    ],
    "Approved": ["approved", "accepted", "a1", "zatwierdzony", "zaakceptowany", "معتمد"],
    "Approved with Comments": [
        "approved with comments",
        "accepted with comments",
        "a2",
        "zatwierdzony z uwagami",
        "معتمد مع ملاحظات",
    ],
    "For Construction": ["for construction", "afc", "do budowy", "للتنفيذ"],
    "As Built": ["as built", "powykonawczy", "powykonawcza", "كما تم التنفيذ"],
    "Rejected": ["rejected", "not accepted", "a3", "odrzucony", "مرفوض"],
    "Superseded": ["superseded", "obsolete", "zastąpiony", "zastapiony", "ملغى"],
    "Missing Information": ["missing information", "incomplete", "brak danych", "معلومات ناقصة"],
    "Closed": ["closed", "zamknięty", "zamkniety", "مغلق"],
}


CONFIDENCE_HIGH = "high"
CONFIDENCE_CHECK = "check"
CONFIDENCE_NOT_FOUND = "not_found"


def _clean_value(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\x00", " ").strip()
    text = re.sub(r"\s+", " ", text)
    return text.strip(" |:;,-")


def _normalise_label(value: str) -> str:
    value = str(value).casefold()
    value = re.sub(r"[\W_]+", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


def _field_aliases(language: str) -> dict[str, list[str]]:
    selected = language if language in LANGUAGE_FIELD_ALIASES else "Other"
    combined: dict[str, list[str]] = {}
    for field, aliases in BASE_FIELD_ALIASES.items():
        combined[field] = list(aliases)
        combined[field].extend(LANGUAGE_FIELD_ALIASES[selected].get(field, []))
    return combined


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
    all_aliases: dict[str, list[str]],
) -> tuple[str, str]:
    sorted_aliases = sorted(set(aliases), key=len, reverse=True)
    all_normalised_aliases = {
        _normalise_label(alias)
        for field_aliases in all_aliases.values()
        for alias in field_aliases
    }

    for index, line in enumerate(lines):
        normalised_line = _normalise_label(line)

        for alias in sorted_aliases:
            normalised_alias = _normalise_label(alias)

            same_line_patterns = [
                rf"^\s*{re.escape(alias)}\s*[:\-–—]\s*(.+)$",
                rf"^\s*{re.escape(alias)}\s+(.+)$",
            ]
            for pattern in same_line_patterns:
                match = re.match(pattern, line, flags=re.IGNORECASE | re.UNICODE)
                if match:
                    value = _clean_value(match.group(1))
                    if value and _normalise_label(value) != normalised_alias:
                        return value, f"PDF label: {alias}"

            if normalised_line == normalised_alias:
                for next_index in range(index + 1, min(index + 3, len(lines))):
                    candidate = _clean_value(lines[next_index])
                    if candidate and _normalise_label(candidate) not in all_normalised_aliases:
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
    value = re.sub(
        r"^(REVISION|REV\.?|REV|REWIZJA|WERSJA|المراجعة|الإصدار)\s*",
        "",
        value,
        flags=re.IGNORECASE | re.UNICODE,
    )
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
            if normalised == keyword_normalised or keyword_normalised in normalised:
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
    if re.fullmatch(r"[\W\d_]+", value, flags=re.UNICODE):
        return False
    return True


def _confidence_for_field(field: str, value: str, source: str) -> str:
    if not _clean_value(value):
        return CONFIDENCE_NOT_FOUND

    if source.startswith("PDF label:"):
        if field == "document_number" and not re.search(r"\d", value):
            return CONFIDENCE_CHECK
        if field == "revision" and len(value) > 12:
            return CONFIDENCE_CHECK
        return CONFIDENCE_HIGH

    if source in {"Uploaded filename", "PDF document properties"}:
        return CONFIDENCE_CHECK

    if source.startswith("Keyword found"):
        return CONFIDENCE_CHECK

    if field in {"file_name", "notes"}:
        return CONFIDENCE_HIGH

    return CONFIDENCE_CHECK


def _language_note(language: str, has_text: bool) -> str:
    if not has_text:
        return (
            "No selectable text was found. Scanned or image-only PDFs are not OCR-processed "
            "in this version, so the metadata must be entered manually."
        )
    if language == "Arabic":
        return (
            "Arabic labels are recognised in text-based PDFs. Results depend on how the "
            "Arabic text was embedded in the source PDF, so extracted values should be checked."
        )
    if language == "Polish":
        return (
            "Polish and English document labels are recognised in text-based PDFs. "
            "Scanned PDFs still require manual entry in this version."
        )
    if language == "Other":
        return (
            "The selected language does not have a dedicated label dictionary yet. "
            "English labels, filename clues and manual review will be used."
        )
    return (
        "English labels are recognised in text-based PDFs. Scanned PDFs still require "
        "manual entry in this version."
    )


def extract_pdf_metadata(
    file_bytes: bytes,
    file_name: str,
    max_pages: int = 5,
    language: str = "English",
) -> dict[str, Any]:
    """
    Extract suggested document-control metadata from a text-based PDF.

    The returned values are suggestions only. Confidence is expressed using
    user-friendly levels: high, check, or not_found. A person must review and
    approve the values before the record is saved.
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
    aliases = _field_aliases(language)

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
    sources: dict[str, str] = {field: "" for field in metadata}
    sources["file_name"] = "Uploaded filename"

    for field, field_aliases in aliases.items():
        value, source = _extract_labelled_value(lines, field_aliases, aliases)
        metadata[field] = value
        sources[field] = source

    metadata["revision"] = _normalise_revision(metadata["revision"])
    metadata["discipline"] = _map_controlled_value(
        metadata["discipline"], DISCIPLINE_KEYWORDS
    )
    metadata["status"] = _map_controlled_value(metadata["status"], STATUS_KEYWORDS)
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
        mapped_discipline = _map_controlled_value(text, DISCIPLINE_KEYWORDS)
        if mapped_discipline and mapped_discipline != _clean_value(text):
            metadata["discipline"] = mapped_discipline
            sources["discipline"] = "Keyword found in PDF text"

    warnings: list[str] = []
    has_text = bool(text.strip())

    if not has_text:
        warnings.append(
            "No selectable text was found. This may be a scanned or image-only PDF."
        )

    missing_key_fields = [
        field
        for field in ["document_number", "title", "revision"]
        if not metadata[field]
    ]
    if missing_key_fields:
        warnings.append(
            "Please enter or confirm: "
            + ", ".join(field.replace("_", " ").title() for field in missing_key_fields)
            + "."
        )

    metadata["notes"] = (
        f"Metadata was suggested from a {language} PDF and reviewed by a person "
        "before saving."
    )
    sources["notes"] = "System note"

    confidence = {
        field: _confidence_for_field(field, metadata.get(field, ""), sources.get(field, ""))
        for field in metadata
    }

    attention_fields = [
        field
        for field in [
            "document_number",
            "title",
            "project",
            "discipline",
            "revision",
            "status",
            "owner",
            "originator",
            "created_date",
        ]
        if confidence.get(field) != CONFIDENCE_HIGH
    ]

    return {
        "metadata": metadata,
        "sources": sources,
        "confidence": confidence,
        "attention_fields": attention_fields,
        "pages_read": pages_to_read,
        "total_pages": len(reader.pages),
        "text_preview": text[:6000],
        "warnings": warnings,
        "language": language,
        "language_note": _language_note(language, has_text),
        "text_based_pdf": has_text,
    }
