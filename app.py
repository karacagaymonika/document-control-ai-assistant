import base64
import hashlib
import html
import io
import json
import re
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from pdf_extractor import extract_pdf_metadata

from database import (
    FILES_ROOT,
    add_document,
    add_document_file,
    archive_documents,
    delete_document_file,
    find_document_file_by_hash,
    get_archived_documents,
    get_audit_log,
    get_document_files,
    get_documents,
    get_review_actions,
    get_review_cases,
    get_register_comparison_items,
    get_register_comparisons,
    init_db,
    reassign_document_files,
    record_review_decision,
    restore_document,
    sync_review_cases,
    create_register_comparison,
    update_document_details,
    update_register_comparison_item_review,
    update_document_status,
)


st.set_page_config(
    page_title="Document Control AI Assistant",
    page_icon="📑",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_db()


REQUIRED_FIELDS = [
    "document_number",
    "title",
    "project",
    "discipline",
    "revision",
    "status",
    "owner",
]

CSV_COLUMNS = [
    "document_number",
    "title",
    "project",
    "discipline",
    "revision",
    "status",
    "owner",
    "originator",
    "created_date",
    "due_date",
    "file_name",
    "notes",
]

COMPARISON_METADATA_FIELDS = [
    "title",
    "revision",
    "status",
    "owner",
    "originator",
    "created_date",
    "file_name",
    "notes",
]

COMPARISON_DECISIONS = [
    "Approved – Register A accepted",
    "Approved – Register B accepted",
    "Approved – Both records valid",
    "Correction Required",
    "Escalated",
    "No Action Required",
]


STATUS_OPTIONS = [
    "Draft",
    "For Review",
    "For Information",
    "Approved",
    "Approved with Comments",
    "For Construction",
    "As Built",
    "Rejected",
    "Superseded",
    "Missing Information",
    "Closed",
]

WORKFLOW_STATUS_OPTIONS = [
    "Ready",
    "Needs checking",
    "Possible duplicate",
    "Archived",
]

DISCIPLINE_OPTIONS = [
    "Engineering",
    "Design",
    "Quality",
    "HSE",
    "Commercial",
    "Project Controls",
    "Construction",
    "Mechanical",
    "Electrical",
    "Civil",
    "Other",
]

COMPLETED_STATUSES = {
    "approved",
    "approved with comments",
    "closed",
    "superseded",
}

QUALITY_FIELDS = [
    "title",
    "project",
    "discipline",
    "status",
    "owner",
    "originator",
    "created_date",
    "file_name",
    "notes",
]

DISPLAY_COLUMNS = [
    "document_number",
    "title",
    "project",
    "discipline",
    "revision",
    "status",
    "owner",
    "originator",
    "created_date",
    "file_name",
    "pdf_count",
    "notes",
]


PDF_LANGUAGE_OPTIONS = ["English", "Polish", "Arabic", "Other"]

CONFIDENCE_PRESENTATION = {
    "high": {
        "label": "High confidence",
        "css_class": "confidence-high",
    },
    "check": {
        "label": "Please check",
        "css_class": "confidence-check",
    },
    "not_found": {
        "label": "Not found",
        "css_class": "confidence-missing",
    },
}

REGISTER_FIELD_LABELS = {
    "document_number": "Document Number",
    "title": "Document Title",
    "project": "Project",
    "discipline": "Discipline",
    "revision": "Revision",
    "status": "Official Status",
    "owner": "Owner",
    "originator": "Originator",
    "created_date": "Date Received",
    "due_date": "Due Date (optional)",
    "file_name": "File Name",
    "notes": "Notes",
}

REGISTER_COLUMN_ALIASES = {
    "document_number": [
        "document number", "document no", "doc number", "doc no",
        "drawing number", "drawing no", "sheet number", "number",
    ],
    "title": ["document title", "drawing title", "sheet title", "title", "description"],
    "project": ["project", "project name", "job", "job name", "contract"],
    "discipline": ["discipline", "department", "trade", "category"],
    "revision": ["revision", "rev", "version", "issue"],
    "status": ["status", "document status", "suitability", "purpose of issue"],
    "owner": ["owner", "document owner", "responsible person", "responsible"],
    "originator": ["originator", "author", "prepared by", "company", "organisation", "organization"],
    "created_date": ["created date", "date received", "received date", "issue date", "document date"],
    "due_date": ["due date", "review due date", "response due date"],
    "file_name": ["file name", "filename", "document file", "pdf name"],
    "notes": ["notes", "comments", "remarks", "comment"],
}


APP_CSS = """
<style>
    :root {
        --navy: #10243e;
        --navy-2: #183b63;
        --blue: #2f6fed;
        --pale-blue: #edf4ff;
        --surface: #ffffff;
        --background: #f4f7fb;
        --text: #172033;
        --muted: #65738b;
        --border: #dfe6ef;
        --green: #16845b;
        --amber: #a96800;
        --red: #b33a3a;
    }

    [data-testid="stAppViewContainer"] {
        background: var(--background);
    }

    [data-testid="stHeader"] {
        background: transparent;
    }

    .block-container {
        max-width: 1780px;
        padding-top: 1.35rem;
        padding-bottom: 3rem;
    }

    [data-testid="stSidebar"] {
        background: #0f2239;
        border-right: 1px solid rgba(255,255,255,0.08);
    }

    [data-testid="stSidebar"] * {
        color: #eef4ff;
    }

    [data-testid="stSidebar"] [role="radiogroup"] label {
        border-radius: 10px;
        padding: 0.45rem 0.6rem;
        margin-bottom: 0.15rem;
    }

    [data-testid="stSidebar"] [role="radiogroup"] label:hover {
        background: rgba(255,255,255,0.08);
    }

    /* Sidebar navigation buttons: always readable */
    [data-testid="stSidebar"] div.stButton > button {
        width: 100%;
        min-height: 2.55rem;
        height: auto;
        padding: 0.55rem 0.7rem;
        justify-content: flex-start;
        text-align: left;
        white-space: normal;
        line-height: 1.2;
        border-radius: 9px;
        background: rgba(255,255,255,0.07) !important;
        border: 1px solid rgba(255,255,255,0.16) !important;
        color: #f4f7fb !important;
        box-shadow: none !important;
    }

    [data-testid="stSidebar"] div.stButton > button p,
    [data-testid="stSidebar"] div.stButton > button span {
        color: #f4f7fb !important;
        font-weight: 650 !important;
        opacity: 1 !important;
    }

    [data-testid="stSidebar"] div.stButton > button:hover {
        background: rgba(255,255,255,0.14) !important;
        border-color: rgba(255,255,255,0.28) !important;
        color: #ffffff !important;
    }

    [data-testid="stSidebar"] div.stButton > button[kind="primary"] {
        background: #2f6fed !important;
        border-color: #2f6fed !important;
        color: #ffffff !important;
    }

    [data-testid="stSidebar"] div.stButton > button[kind="primary"] p,
    [data-testid="stSidebar"] div.stButton > button[kind="primary"] span {
        color: #ffffff !important;
    }

    [data-testid="stSidebar"] h4 {
        margin-top: 0.8rem;
        margin-bottom: 0.35rem;
        color: #ffffff !important;
    }

    .hero {
        padding: 1.65rem 1.9rem;
        border-radius: 18px;
        background: linear-gradient(120deg, #10243e 0%, #183b63 72%, #24558a 100%);
        box-shadow: 0 14px 38px rgba(16, 36, 62, 0.16);
        margin-bottom: 1.1rem;
    }

    .hero-kicker {
        color: #9fc1f8;
        font-size: 0.75rem;
        letter-spacing: 0.14em;
        font-weight: 700;
        margin-bottom: 0.35rem;
    }

    .hero h1 {
        color: white;
        font-size: 2rem;
        line-height: 1.15;
        margin: 0;
    }

    .hero p {
        color: #d6e3f5;
        max-width: 900px;
        font-size: 0.98rem;
        margin: 0.7rem 0 0;
    }

    .hero-badges {
        display: flex;
        flex-wrap: wrap;
        gap: 0.45rem;
        margin-top: 1rem;
    }

    .hero-badge {
        color: #eaf2ff;
        background: rgba(255,255,255,0.11);
        border: 1px solid rgba(255,255,255,0.14);
        border-radius: 999px;
        padding: 0.28rem 0.65rem;
        font-size: 0.75rem;
    }

    .section-card {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 16px;
        padding: 1.15rem 1.25rem;
        box-shadow: 0 6px 20px rgba(31, 51, 81, 0.05);
        margin-bottom: 1rem;
    }

    .section-title {
        color: var(--text);
        font-size: 1.12rem;
        font-weight: 750;
        margin: 0 0 0.25rem;
    }

    .section-copy {
        color: var(--muted);
        font-size: 0.88rem;
        margin: 0;
    }

    .metric-grid {
        display: grid;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        gap: 0.8rem;
        margin: 0.8rem 0 1rem;
    }

    .metric-card {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 14px;
        padding: 1rem 1.05rem;
        box-shadow: 0 4px 16px rgba(31, 51, 81, 0.045);
    }

    .metric-label {
        color: var(--muted);
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        font-weight: 700;
    }

    .metric-value {
        color: var(--text);
        font-size: 1.65rem;
        line-height: 1.1;
        font-weight: 780;
        margin-top: 0.38rem;
    }

    .metric-note {
        color: var(--muted);
        font-size: 0.72rem;
        margin-top: 0.32rem;
    }

    .health-good { color: var(--green); }
    .health-watch { color: var(--amber); }
    .health-risk { color: var(--red); }

    .notice {
        border-radius: 12px;
        padding: 0.8rem 0.95rem;
        margin: 0.6rem 0;
        font-size: 0.88rem;
    }

    .notice-info {
        background: var(--pale-blue);
        color: #274c7d;
        border: 1px solid #d3e3fb;
    }

    .notice-safe {
        background: #edf8f3;
        color: #1d6d4e;
        border: 1px solid #cfeadf;
    }

    div[data-testid="stForm"],
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: white;
        border-color: var(--border);
        border-radius: 14px;
    }

    .stButton > button,
    .stDownloadButton > button,
    .stFormSubmitButton > button {
        border-radius: 9px;
        min-height: 2.55rem;
        font-weight: 650;
    }

    .stButton > button[kind="primary"],
    .stFormSubmitButton > button[kind="primary"] {
        background: var(--blue);
        border-color: var(--blue);
    }

    [data-testid="stDataFrame"] {
        border: 1px solid var(--border);
        border-radius: 12px;
        overflow: hidden;
    }

    [data-testid="stMetric"] {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 14px;
        padding: 0.95rem 1rem;
        min-height: 118px;
        box-shadow: 0 4px 16px rgba(31, 51, 81, 0.045);
    }

    [data-testid="stMetricLabel"] {
        color: var(--muted);
        font-weight: 700;
    }

    [data-testid="stMetricValue"] {
        color: var(--text);
        font-weight: 780;
    }

    div.stButton > button[kind="primary"],
    div.stFormSubmitButton > button[kind="primary"],
    div[data-testid="stFormSubmitButton"] > button {
        background: var(--blue) !important;
        border-color: var(--blue) !important;
        color: #ffffff !important;
    }


    /* Stronger visibility for register filters and controls */
    [data-testid="stWidgetLabel"] p {
        color: var(--navy) !important;
        font-size: 0.9rem !important;
        font-weight: 750 !important;
    }

    div[data-testid="stTextInput"] input,
    div[data-testid="stMultiSelect"] [data-baseweb="select"] > div,
    div[data-testid="stSelectbox"] [data-baseweb="select"] > div {
        min-height: 46px;
        background: #ffffff;
        border-color: #b7c5d8 !important;
        box-shadow: 0 1px 2px rgba(16, 36, 62, 0.04);
    }

    div[data-testid="stTextInput"] input:focus,
    div[data-testid="stMultiSelect"] [data-baseweb="select"] > div:focus-within,
    div[data-testid="stSelectbox"] [data-baseweb="select"] > div:focus-within {
        border-color: var(--blue) !important;
        box-shadow: 0 0 0 2px rgba(47, 111, 237, 0.12);
    }

    .register-help {
        color: var(--muted);
        font-size: 0.82rem;
        margin: -0.15rem 0 0.65rem;
    }

    #MainMenu, footer {
        visibility: hidden;
    }

    @media (max-width: 1100px) {
        .metric-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }
    }

    @media (max-width: 700px) {
        .metric-grid {
            grid-template-columns: 1fr;
        }
        .hero h1 {
            font-size: 1.55rem;
        }
    }

    .confidence-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.5rem;
        margin: 0.15rem 0 0.28rem;
    }

    .confidence-field-name {
        color: var(--text);
        font-size: 0.78rem;
        font-weight: 750;
    }

    .confidence-badge {
        border-radius: 999px;
        padding: 0.18rem 0.5rem;
        font-size: 0.7rem;
        font-weight: 750;
        border: 1px solid transparent;
        white-space: nowrap;
    }

    .confidence-high {
        color: #176746;
        background: #eaf7f0;
        border-color: #bfe3d1;
    }

    .confidence-check {
        color: #855400;
        background: #fff5df;
        border-color: #f0d28f;
    }

    .confidence-missing {
        color: #9c2f2f;
        background: #fff0f0;
        border-color: #efc2c2;
    }

    .pdf-preview-shell {
        background: #ffffff;
        border: 1px solid var(--border);
        border-radius: 14px;
        padding: 0.55rem;
        box-shadow: 0 6px 20px rgba(31, 51, 81, 0.05);
    }

    .intake-step {
        color: var(--muted);
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        margin-bottom: 0.3rem;
    }

</style>
"""

st.markdown(APP_CSS, unsafe_allow_html=True)


# -----------------------------
# Data helpers
# -----------------------------

def clean_text(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def optional_date_value(value):
    text_value = clean_text(value)
    if not text_value:
        return None
    parsed = pd.to_datetime(text_value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date()


def select_options_with_current(base_options, current_value):
    current = clean_text(current_value)
    options = [""] + [value for value in base_options if value]
    if current and current not in options:
        options.append(current)
    return options, options.index(current) if current in options else 0


def normalized_key(value):
    return clean_text(value).casefold()


def make_document_key(
    document_number,
    title="",
    revision="",
    project="",
    discipline="",
):
    """Identify a true duplicate within its project and discipline context."""
    return (
        normalized_key(project),
        normalized_key(discipline),
        normalized_key(document_number),
        normalized_key(title),
        normalized_key(revision),
    )


def existing_document_keys(df):
    if df.empty:
        return set()

    return {
        make_document_key(
            row.get("document_number", ""),
            row.get("title", ""),
            row.get("revision", ""),
            row.get("project", ""),
            row.get("discipline", ""),
        )
        for _, row in df.iterrows()
    }


def make_record_signature(row):
    """Compare the complete register metadata, not only the document identity."""
    return tuple(normalized_key(row.get(column, "")) for column in CSV_COLUMNS)


def existing_record_signatures(df):
    if df.empty:
        return set()
    return {make_record_signature(row) for _, row in df.iterrows()}


def revision_sort_key(value):
    """Natural revision ordering for values such as P01, P02, C01, A and B."""
    text_value = clean_text(value).upper()
    if not text_value:
        return ((-1, ""),)

    tokens = re.findall(r"[A-Z]+|\d+", text_value)
    if not tokens:
        return ((1, text_value),)

    return tuple(
        (0, int(token)) if token.isdigit() else (1, token)
        for token in tokens
    )


def revision_family_key(row):
    return (
        normalized_key(row.get("project", "")),
        normalized_key(row.get("discipline", "")),
        normalized_key(row.get("document_number", "")),
        normalized_key(row.get("title", "")),
    )


def sort_revision_history(history):
    if history.empty:
        return history.copy()

    working = history.copy()
    working["_revision_sort"] = working["revision"].map(revision_sort_key)
    working["_created_sort"] = working["created_date"].fillna("").astype(str)
    working["_registered_sort"] = working["created_at"].fillna("").astype(str)
    ordered_indices = sorted(
        working.index,
        key=lambda index: (
            working.at[index, "_revision_sort"],
            working.at[index, "_created_sort"],
            working.at[index, "_registered_sort"],
            int(working.at[index, "id"]),
        ),
        reverse=True,
    )
    working = working.loc[ordered_indices].copy()
    working["revision_role"] = "Previous revision"
    if not working.empty:
        working.iloc[0, working.columns.get_loc("revision_role")] = "Current revision"
    return working.drop(columns=["_revision_sort", "_created_sort", "_registered_sort"])


def finding_key(issue_type, related_ids, detail=""):
    raw = "|".join(
        [
            normalized_key(issue_type),
            ",".join(str(value) for value in sorted({int(value) for value in related_ids})),
            normalized_key(detail),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def normalize_column_name(column_name):
    cleaned_name = (
        str(column_name)
        .replace("\ufeff", "")
        .strip()
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace("/", "_")
        .replace(".", "_")
    )

    while "__" in cleaned_name:
        cleaned_name = cleaned_name.replace("__", "_")

    return cleaned_name.strip("_")


def read_uploaded_csv(uploaded_file):
    file_bytes = uploaded_file.getvalue()
    last_error = None

    for encoding in ["utf-8-sig", "utf-8", "cp1252", "latin-1"]:
        try:
            uploaded_df = pd.read_csv(
                io.BytesIO(file_bytes),
                dtype=str,
                keep_default_na=False,
                sep=None,
                engine="python",
                encoding=encoding,
            )
            uploaded_df.columns = [
                normalize_column_name(column)
                for column in uploaded_df.columns
            ]
            return uploaded_df
        except (UnicodeDecodeError, pd.errors.ParserError) as error:
            last_error = error

    raise ValueError(
        "The CSV encoding or structure could not be recognised."
    ) from last_error


def prepare_uploaded_register(uploaded_df):
    prepared_df = uploaded_df.copy()

    for column in CSV_COLUMNS:
        if column not in prepared_df.columns:
            prepared_df[column] = ""

    prepared_df = prepared_df[CSV_COLUMNS].copy()

    for column in CSV_COLUMNS:
        prepared_df[column] = (
            prepared_df[column]
            .fillna("")
            .astype(str)
            .str.strip()
        )

    prepared_df.insert(0, "csv_row", range(2, len(prepared_df) + 2))
    return prepared_df



def comparison_identity_key(row):
    """Match the same controlled document across two registers."""
    return (
        normalized_key(row.get("project", "")),
        normalized_key(row.get("discipline", "")),
        normalized_key(row.get("document_number", "")),
    )


def comparison_record(row):
    return {
        column: clean_text(row.get(column, ""))
        for column in CSV_COLUMNS
    }


def comparison_history_records(group):
    if group is None or group.empty:
        return []

    working = group.copy()
    working["_created_date"] = pd.to_datetime(
        working["created_date"], errors="coerce"
    )
    working["_revision_sort"] = working["revision"].map(revision_sort_key)
    ordered_indices = sorted(
        working.index,
        key=lambda index: (
            working.at[index, "_created_date"].timestamp()
            if pd.notna(working.at[index, "_created_date"])
            else float("-inf"),
            working.at[index, "_revision_sort"],
            int(working.at[index, "csv_row"]),
        ),
        reverse=True,
    )
    ordered = working.loc[ordered_indices]
    return [comparison_record(row) for _, row in ordered.iterrows()]


def select_comparison_current_row(group):
    history = comparison_history_records(group)
    return history[0] if history else {}


def parse_revision_value(value):
    text_value = clean_text(value).upper()
    if not text_value:
        return None

    prefix_number = re.fullmatch(r"([A-Z]+)[\s._-]*0*(\d+)", text_value)
    if prefix_number:
        return ("prefix_number", prefix_number.group(1), int(prefix_number.group(2)))

    if re.fullmatch(r"\d+", text_value):
        return ("number", "", int(text_value))

    if re.fullmatch(r"[A-Z]+", text_value):
        score = 0
        for character in text_value:
            score = score * 26 + (ord(character) - ord("A") + 1)
        return ("letters", "", score)

    return None


def compare_revision_values(revision_a, revision_b, created_a="", created_b=""):
    """Compare revisions conservatively and explain the basis used."""
    a_text = clean_text(revision_a)
    b_text = clean_text(revision_b)

    if normalized_key(a_text) == normalized_key(b_text):
        return "same", "Same revision value"

    parsed_a = parse_revision_value(a_text)
    parsed_b = parse_revision_value(b_text)

    if parsed_a and parsed_b and parsed_a[:2] == parsed_b[:2]:
        if parsed_a[2] > parsed_b[2]:
            return "a_newer", "Comparable revision sequence"
        if parsed_b[2] > parsed_a[2]:
            return "b_newer", "Comparable revision sequence"

    date_a = pd.to_datetime(clean_text(created_a), errors="coerce")
    date_b = pd.to_datetime(clean_text(created_b), errors="coerce")
    if pd.notna(date_a) and pd.notna(date_b) and date_a != date_b:
        if date_a > date_b:
            return "a_newer", "Different revision formats; later Created Date used"
        return "b_newer", "Different revision formats; later Created Date used"

    return "unclear", "Revision order cannot be confirmed automatically"


def compare_metadata_records(record_a, record_b):
    differing = []
    for field in COMPARISON_METADATA_FIELDS:
        if normalized_key(record_a.get(field, "")) != normalized_key(record_b.get(field, "")):
            differing.append(field)
    return differing


def revision_values(group):
    if group is None or group.empty:
        return []
    values = {
        clean_text(value)
        for value in group["revision"].tolist()
        if clean_text(value)
    }
    return sorted(values, key=revision_sort_key)


def build_internal_register_issues(df, register_label):
    issues = []
    if df.empty:
        return pd.DataFrame()

    working = df.copy()
    working["_identity"] = working.apply(comparison_identity_key, axis=1)
    working["_title_key"] = working["title"].map(normalized_key)
    working["_revision_key"] = working["revision"].map(normalized_key)
    working["_signature"] = working.apply(make_record_signature, axis=1)

    missing_number = working[working["document_number"].map(clean_text) == ""]
    for _, row in missing_number.iterrows():
        issues.append(
            {
                "register": register_label,
                "project": clean_text(row["project"]),
                "discipline": clean_text(row["discipline"]),
                "document_number": "",
                "title": clean_text(row["title"]),
                "revision": clean_text(row["revision"]),
                "issue": "Document Number is missing; row cannot be reconciled reliably",
                "severity": "Critical",
                "csv_rows": str(int(row["csv_row"])),
            }
        )

    grouped = working[working["document_number"].map(clean_text) != ""].groupby(
        ["_identity", "_title_key", "_revision_key"], dropna=False
    )
    for _, group in grouped:
        if len(group) <= 1:
            continue
        exact = group["_signature"].nunique() == 1
        first = group.iloc[0]
        issues.append(
            {
                "register": register_label,
                "project": clean_text(first["project"]),
                "discipline": clean_text(first["discipline"]),
                "document_number": clean_text(first["document_number"]),
                "title": clean_text(first["title"]),
                "revision": clean_text(first["revision"]),
                "issue": (
                    "Repeated identical rows inside the register"
                    if exact
                    else "Same document identity and revision has conflicting metadata inside the register"
                ),
                "severity": "Warning" if exact else "Critical",
                "csv_rows": ", ".join(str(int(value)) for value in group["csv_row"]),
            }
        )

    return pd.DataFrame(issues)


def compare_master_registers(register_a, register_b, label_a, label_b):
    """Compare two registers without overwriting either source file."""
    a = register_a.copy()
    b = register_b.copy()
    a["_identity"] = a.apply(comparison_identity_key, axis=1)
    b["_identity"] = b.apply(comparison_identity_key, axis=1)

    valid_a = a[a["document_number"].map(clean_text) != ""].copy()
    valid_b = b[b["document_number"].map(clean_text) != ""].copy()

    groups_a = {key: group.copy() for key, group in valid_a.groupby("_identity", dropna=False)}
    groups_b = {key: group.copy() for key, group in valid_b.groupby("_identity", dropna=False)}

    results = []
    all_keys = sorted(set(groups_a) | set(groups_b))

    for key in all_keys:
        group_a = groups_a.get(key, pd.DataFrame(columns=a.columns))
        group_b = groups_b.get(key, pd.DataFrame(columns=b.columns))
        current_a = select_comparison_current_row(group_a)
        current_b = select_comparison_current_row(group_b)
        history_a = comparison_history_records(group_a)
        history_b = comparison_history_records(group_b)
        revisions_a = revision_values(group_a)
        revisions_b = revision_values(group_b)

        project = clean_text(current_a.get("project", "") or current_b.get("project", ""))
        discipline = clean_text(current_a.get("discipline", "") or current_b.get("discipline", ""))
        document_number = clean_text(
            current_a.get("document_number", "") or current_b.get("document_number", "")
        )
        title_a = clean_text(current_a.get("title", ""))
        title_b = clean_text(current_b.get("title", ""))
        revision_a = clean_text(current_a.get("revision", ""))
        revision_b = clean_text(current_b.get("revision", ""))
        differing_fields = []
        review_required = True

        if group_b.empty:
            classification = f"Only in {label_a}"
            severity = "Warning"
            recommended = f"Confirm whether this document should also exist in {label_b}."
        elif group_a.empty:
            classification = f"Only in {label_b}"
            severity = "Warning"
            recommended = f"Confirm whether this is a new document or missing from {label_a}."
        else:
            differing_fields = compare_metadata_records(current_a, current_b)
            revision_relation, revision_basis = compare_revision_values(
                revision_a,
                revision_b,
                current_a.get("created_date", ""),
                current_b.get("created_date", ""),
            )
            title_conflict = normalized_key(title_a) != normalized_key(title_b)
            revisions_only_a = [value for value in revisions_a if normalized_key(value) not in {normalized_key(v) for v in revisions_b}]
            revisions_only_b = [value for value in revisions_b if normalized_key(value) not in {normalized_key(v) for v in revisions_a}]

            if title_conflict:
                classification = "Title conflict – manual review"
                severity = "Critical"
                recommended = "Compare the source documents. Do not overwrite either register until the correct title is approved."
            elif revision_relation == "a_newer":
                classification = f"Newer revision in {label_a}"
                severity = "Review"
                recommended = f"Verify the revision sequence and confirm whether {label_b} needs updating. {revision_basis}."
            elif revision_relation == "b_newer":
                classification = f"Newer revision in {label_b}"
                severity = "Review"
                recommended = f"Verify the revision sequence and confirm whether {label_a} needs updating. {revision_basis}."
            elif revision_relation == "unclear":
                classification = "Revision difference – manual review"
                severity = "Warning"
                recommended = "Revision order is not safely comparable. Review the documents and dates manually."
            elif differing_fields:
                classification = "Same revision – metadata changed"
                severity = "Warning"
                recommended = "Compare the changed metadata fields and approve the correct value before reconciliation."
            elif revisions_only_a or revisions_only_b:
                classification = "Revision history differs"
                severity = "Review"
                recommended = "The current record matches, but one register has additional revision history. Confirm whether the missing history should be added."
            else:
                classification = "No change"
                severity = "Clear"
                recommended = "No reconciliation action is required."
                review_required = False

        item_key_raw = "|".join([*key, normalized_key(classification)])
        item_key = hashlib.sha256(item_key_raw.encode("utf-8")).hexdigest()
        revision_keys_a = {normalized_key(value) for value in revisions_a}
        revision_keys_b = {normalized_key(value) for value in revisions_b}
        revisions_only_a = [value for value in revisions_a if normalized_key(value) not in revision_keys_b]
        revisions_only_b = [value for value in revisions_b if normalized_key(value) not in revision_keys_a]

        results.append(
            {
                "item_key": item_key,
                "project": project,
                "discipline": discipline,
                "document_number": document_number,
                "title_a": title_a,
                "title_b": title_b,
                "revision_a": revision_a,
                "revision_b": revision_b,
                "status_a": clean_text(current_a.get("status", "")),
                "status_b": clean_text(current_b.get("status", "")),
                "classification": classification,
                "severity": severity,
                "differing_fields": ", ".join(differing_fields),
                "revisions_only_a": ", ".join(revisions_only_a),
                "revisions_only_b": ", ".join(revisions_only_b),
                "recommended_action": recommended,
                "review_required": review_required,
                "record_a": current_a,
                "record_b": current_b,
                "history_a": history_a,
                "history_b": history_b,
            }
        )

    results_df = pd.DataFrame(results)
    internal_issues = pd.concat(
        [
            build_internal_register_issues(a, label_a),
            build_internal_register_issues(b, label_b),
        ],
        ignore_index=True,
    )

    if results_df.empty:
        summary = {
            "total_documents": 0,
            "review_items": 0,
            "no_change_items": 0,
            "only_a": 0,
            "only_b": 0,
            "newer_a": 0,
            "newer_b": 0,
        }
    else:
        summary = {
            "total_documents": int(len(results_df)),
            "review_items": int(results_df["review_required"].sum()),
            "no_change_items": int((~results_df["review_required"]).sum()),
            "only_a": int(results_df["classification"].eq(f"Only in {label_a}").sum()),
            "only_b": int(results_df["classification"].eq(f"Only in {label_b}").sum()),
            "newer_a": int(results_df["classification"].eq(f"Newer revision in {label_a}").sum()),
            "newer_b": int(results_df["classification"].eq(f"Newer revision in {label_b}").sum()),
        }

    return results_df, internal_issues, summary


def comparison_export_dataframe(results_df, label_a, label_b):
    if results_df.empty:
        return pd.DataFrame()

    export = results_df.copy()
    export = export.rename(
        columns={
            "title_a": f"Title – {label_a}",
            "title_b": f"Title – {label_b}",
            "revision_a": f"Revision – {label_a}",
            "revision_b": f"Revision – {label_b}",
            "status_a": f"Status – {label_a}",
            "status_b": f"Status – {label_b}",
            "revisions_only_a": f"Revisions only in {label_a}",
            "revisions_only_b": f"Revisions only in {label_b}",
        }
    )
    export["Review Status"] = export["review_required"].map(
        {True: "Pending Review", False: "No Review Required"}
    )
    export["Reviewer"] = ""
    export["Review Comments"] = ""
    return export.drop(
        columns=[
            "item_key",
            "review_required",
            "record_a",
            "record_b",
            "history_a",
            "history_b",
        ],
        errors="ignore",
    )


def comparison_side_by_side_dataframe(record_a, record_b, label_a, label_b):
    rows = []
    for field in CSV_COLUMNS:
        value_a = clean_text(record_a.get(field, ""))
        value_b = clean_text(record_b.get(field, ""))
        rows.append(
            {
                "Field": field.replace("_", " ").title(),
                label_a: value_a,
                label_b: value_b,
                "Match": "Yes" if normalized_key(value_a) == normalized_key(value_b) else "No",
            }
        )
    return pd.DataFrame(rows)


def row_completeness(row):
    return sum(clean_text(row.get(field, "")) != "" for field in QUALITY_FIELDS)


def build_duplicate_cleanup_plan(df, strategy):
    columns = [
        "document_number",
        "revision",
        "keep_id",
        "remove_id",
        "kept_title",
        "removed_title",
        "reason",
    ]

    if df.empty:
        return pd.DataFrame(columns=columns)

    working = df.copy()
    working["_doc_key"] = working["document_number"].map(normalized_key)
    working["_rev_key"] = working["revision"].map(normalized_key)
    working["_completeness"] = working.apply(row_completeness, axis=1)

    duplicate_rows = working[
        working.duplicated(["_doc_key", "_rev_key"], keep=False)
    ]

    plan = []

    for _, group in duplicate_rows.groupby(["_doc_key", "_rev_key"], sort=True):
        if strategy == "Keep oldest record":
            ranked = group.sort_values(["id"], ascending=[True])
            reason = "Oldest database record retained"
        elif strategy == "Keep newest record":
            ranked = group.sort_values(["id"], ascending=[False])
            reason = "Newest database record retained"
        else:
            ranked = group.sort_values(
                ["_completeness", "id"],
                ascending=[False, True],
            )
            reason = "Most complete record retained; oldest wins ties"

        kept = ranked.iloc[0]

        for _, removed in ranked.iloc[1:].iterrows():
            plan.append(
                {
                    "document_number": clean_text(kept["document_number"]),
                    "revision": clean_text(kept["revision"]),
                    "keep_id": int(kept["id"]),
                    "remove_id": int(removed["id"]),
                    "kept_title": clean_text(kept["title"]),
                    "removed_title": clean_text(removed["title"]),
                    "reason": reason,
                }
            )

    return pd.DataFrame(plan, columns=columns)



def confidence_badge_html(level, source=""):
    details = CONFIDENCE_PRESENTATION.get(
        clean_text(level),
        CONFIDENCE_PRESENTATION["check"],
    )
    safe_source = html.escape(clean_text(source) or "No source detected", quote=True)
    return (
        f'<span class="confidence-badge {details["css_class"]}" '
        f'title="{safe_source}">{details["label"]}</span>'
    )


def render_confidence_label(field_name, level, source=""):
    st.markdown(
        f"""
        <div class="confidence-row">
            <span class="confidence-field-name">{html.escape(field_name)}</span>
            {confidence_badge_html(level, source)}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_pdf_preview(file_bytes, file_name, height=760):
    encoded_pdf = base64.b64encode(file_bytes).decode("ascii")
    safe_name = html.escape(clean_text(file_name) or "PDF preview")
    st.markdown(
        f"""
        <div class="pdf-preview-shell">
            <iframe
                title="{safe_name}"
                src="data:application/pdf;base64,{encoded_pdf}#toolbar=1&navpanes=0&scrollbar=1"
                width="100%"
                height="{int(height)}"
                style="border: 0; border-radius: 10px; background: white;"
            ></iframe>
        </div>
        """,
        unsafe_allow_html=True,
    )


def normalise_register_source_dataframe(source_df):
    working = source_df.copy()
    working.columns = [str(column).strip() for column in working.columns]
    working = working.fillna("")
    for column in working.columns:
        working[column] = working[column].astype(str).str.strip()
    return working


def read_uploaded_excel_sheet(uploaded_file, sheet_name):
    file_bytes = uploaded_file.getvalue()
    return pd.read_excel(
        io.BytesIO(file_bytes),
        sheet_name=sheet_name,
        dtype=str,
        keep_default_na=False,
    )


def get_excel_sheet_names(uploaded_file):
    with pd.ExcelFile(io.BytesIO(uploaded_file.getvalue())) as workbook:
        return workbook.sheet_names


def suggest_register_column_mapping(source_columns):
    source_columns = list(source_columns)
    normalised_sources = {
        source: normalize_column_name(source)
        for source in source_columns
    }
    mapping = {}

    for target_field, aliases in REGISTER_COLUMN_ALIASES.items():
        target_aliases = {
            normalize_column_name(target_field),
            *{normalize_column_name(alias) for alias in aliases},
        }
        exact_match = next(
            (
                source
                for source, normalised_source in normalised_sources.items()
                if normalised_source in target_aliases
            ),
            None,
        )
        if exact_match:
            mapping[target_field] = exact_match
            continue

        partial_match = next(
            (
                source
                for source, normalised_source in normalised_sources.items()
                if any(
                    alias and (
                        alias in normalised_source
                        or normalised_source in alias
                    )
                    for alias in target_aliases
                )
            ),
            None,
        )
        mapping[target_field] = partial_match or ""

    return mapping


def build_mapped_register(source_df, mapping):
    prepared = pd.DataFrame(index=source_df.index)

    for target_field in CSV_COLUMNS:
        source_column = clean_text(mapping.get(target_field, ""))
        if source_column and source_column in source_df.columns:
            prepared[target_field] = source_df[source_column]
        else:
            prepared[target_field] = ""

    for column in CSV_COLUMNS:
        prepared[column] = (
            prepared[column]
            .fillna("")
            .astype(str)
            .str.strip()
        )

    return prepared.reset_index(drop=True)


def relationship_display_name(relationship_type):
    labels = {
        "new_document": "New document",
        "new_revision": "New revision",
        "exact_duplicate": "Possible duplicate",
        "similar_document_number": "Similar document number",
    }
    return labels.get(clean_text(relationship_type), "Needs checking")


# -----------------------------
# Quality checks
# -----------------------------

def find_missing_metadata(df):
    rows = []

    for _, row in df.iterrows():
        missing_fields = [
            field
            for field in REQUIRED_FIELDS
            if clean_text(row.get(field, "")) == ""
        ]

        if missing_fields:
            rows.append(
                {
                    "id": int(row["id"]),
                    "document_number": clean_text(row["document_number"]),
                    "revision": clean_text(row["revision"]),
                    "title": clean_text(row["title"]),
                    "missing_fields": ", ".join(missing_fields),
                }
            )

    return pd.DataFrame(rows)


def find_exact_duplicates(df):
    """True duplicates require matching project, discipline, number, title and revision."""
    if df.empty:
        return pd.DataFrame()

    working = df.copy()
    key_columns = {
        "_project_key": "project",
        "_discipline_key": "discipline",
        "_doc_key": "document_number",
        "_title_key": "title",
        "_rev_key": "revision",
    }
    for key_column, source_column in key_columns.items():
        working[key_column] = working[source_column].map(normalized_key)

    duplicate_keys = list(key_columns.keys())
    duplicates = working[
        working.duplicated(duplicate_keys, keep=False)
    ].copy()

    if duplicates.empty:
        return pd.DataFrame()

    duplicates["duplicate_group"] = duplicates[duplicate_keys].astype(str).agg(" | ".join, axis=1)
    return duplicates.drop(columns=duplicate_keys).sort_values(
        ["project", "discipline", "document_number", "title", "revision", "id"]
    )


def find_metadata_conflicts(df):
    """Flag only genuine identity conflicts that require manual review.

    The same title may legitimately be used by several different documents.
    Therefore, different document numbers are never treated as a conflict just
    because the title and revision happen to match.

    A title conflict exists only when the same project, discipline, document
    number and revision are registered with different titles.
    """
    if df.empty:
        return pd.DataFrame()

    working = df.copy()
    for column in ["project", "discipline", "document_number", "title", "revision"]:
        working[f"_{column}_key"] = working[column].map(normalized_key)

    conflicts = []

    number_revision_keys = [
        "_project_key",
        "_discipline_key",
        "_document_number_key",
        "_revision_key",
    ]
    for _, group in working.groupby(number_revision_keys, dropna=False):
        distinct_titles = {
            normalized_key(value)
            for value in group["title"]
            if clean_text(value)
        }
        if len(group) > 1 and len(distinct_titles) > 1:
            conflicts.append(
                {
                    "conflict_type": "Title conflict",
                    "project": clean_text(group.iloc[0]["project"]),
                    "discipline": clean_text(group.iloc[0]["discipline"]),
                    "document_number": clean_text(group.iloc[0]["document_number"]),
                    "revision": clean_text(group.iloc[0]["revision"]),
                    "titles": " | ".join(
                        sorted({clean_text(value) for value in group["title"]})
                    ),
                    "related_document_ids": [
                        int(value) for value in group["id"].tolist()
                    ],
                }
            )

    return pd.DataFrame(conflicts)


def find_revision_groups(df):
    if df.empty:
        return pd.DataFrame()

    rows = []
    working = df.copy()
    working["_family_key"] = working.apply(revision_family_key, axis=1)

    for _, group in working.groupby("_family_key"):
        distinct_revisions = {
            clean_text(value)
            for value in group["revision"]
            if clean_text(value) != ""
        }
        if len(distinct_revisions) <= 1:
            continue

        ordered = sort_revision_history(group)
        current = ordered.iloc[0]
        ordered_revisions = [clean_text(value) for value in ordered["revision"] if clean_text(value)]
        rows.append(
            {
                "project": clean_text(current["project"]),
                "discipline": clean_text(current["discipline"]),
                "document_number": clean_text(current["document_number"]),
                "title": clean_text(current["title"]),
                "revision_count": len(distinct_revisions),
                "revisions": ", ".join(ordered_revisions),
                "current_revision": clean_text(current["revision"]),
                "current_created_date": clean_text(current["created_date"]),
                "current_registered_date": clean_text(current["created_at"]),
            }
        )

    return pd.DataFrame(rows)


def find_overdue_documents(df):
    if df.empty:
        return pd.DataFrame()

    working = df.copy()
    working["_due_date"] = pd.to_datetime(
        working["due_date"], errors="coerce"
    )
    today = pd.Timestamp(date.today())
    open_status = ~working["status"].map(normalized_key).isin(COMPLETED_STATUSES)

    overdue = working[
        working["_due_date"].notna()
        & (working["_due_date"] < today)
        & open_status
    ].copy()

    if overdue.empty:
        return pd.DataFrame()

    overdue["days_overdue"] = (today - overdue["_due_date"]).dt.days

    return overdue.drop(columns=["_due_date"]).sort_values(
        "days_overdue", ascending=False
    )


def find_date_sequence_issues(df):
    if df.empty:
        return pd.DataFrame()

    working = df.copy()
    working["_created"] = pd.to_datetime(
        working["created_date"], errors="coerce"
    )
    working["_due"] = pd.to_datetime(
        working["due_date"], errors="coerce"
    )

    issues = working[
        working["_created"].notna()
        & working["_due"].notna()
        & (working["_created"] > working["_due"])
    ].copy()

    if issues.empty:
        return pd.DataFrame()

    return issues.drop(columns=["_created", "_due"]).sort_values("id")


def filename_token(value):
    return re.sub(r"[^a-z0-9]", "", normalized_key(value))


def safe_folder_name(value):
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", clean_text(value))
    cleaned = cleaned.strip("._-")
    return cleaned or "Unassigned"


def human_file_size(size_bytes):
    size = float(size_bytes or 0)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size:.1f} GB"


def build_pdf_storage_path(record, original_file_name, file_hash):
    project_folder = safe_folder_name(record.get("project", ""))
    discipline_folder = safe_folder_name(record.get("discipline", ""))
    document_folder = safe_folder_name(record.get("document_number", ""))

    original_stem = Path(original_file_name).stem
    safe_stem = safe_folder_name(original_stem)
    stored_name = f"{safe_stem}_{file_hash[:10]}.pdf"

    target_folder = FILES_ROOT / project_folder / discipline_folder / document_folder
    target_folder.mkdir(parents=True, exist_ok=True)
    return target_folder / stored_name


def inspect_pdf_upload(uploaded_file, record):
    file_bytes = uploaded_file.getvalue()
    file_hash = hashlib.sha256(file_bytes).hexdigest()
    file_name = clean_text(uploaded_file.name)
    file_token = filename_token(file_name)
    document_number = clean_text(record.get("document_number", ""))
    revision = clean_text(record.get("revision", ""))

    valid_header = file_bytes.startswith(b"%PDF-")
    document_number_match = (
        bool(document_number)
        and filename_token(document_number) in file_token
    )
    revision_match = (
        not revision
        or filename_token(revision) in file_token
    )

    duplicate_file = find_document_file_by_hash(file_hash)

    return {
        "file_bytes": file_bytes,
        "file_hash": file_hash,
        "file_name": file_name,
        "file_size": len(file_bytes),
        "valid_header": valid_header,
        "document_number_match": document_number_match,
        "revision_match": revision_match,
        "duplicate_file": duplicate_file,
    }


def find_missing_pdf_records(df):
    if df.empty or "pdf_count" not in df.columns:
        return pd.DataFrame()

    missing = df[pd.to_numeric(df["pdf_count"], errors="coerce").fillna(0) == 0].copy()
    return missing.sort_values(["project", "discipline", "document_number", "revision"])


def find_filename_issues(df):
    rows = []

    for _, row in df.iterrows():
        file_name = clean_text(row.get("file_name", ""))
        document_number = clean_text(row.get("document_number", ""))
        revision = clean_text(row.get("revision", ""))

        if not file_name:
            continue

        file_token = filename_token(file_name)
        missing_parts = []

        if document_number and filename_token(document_number) not in file_token:
            missing_parts.append("document number")

        if revision and filename_token(revision) not in file_token:
            missing_parts.append("revision")

        if missing_parts:
            rows.append(
                {
                    "id": int(row["id"]),
                    "document_number": document_number,
                    "revision": revision,
                    "file_name": file_name,
                    "issue": "Filename does not contain " + " and ".join(missing_parts),
                }
            )

    return pd.DataFrame(rows)


def find_invalid_statuses(df):
    if df.empty:
        return pd.DataFrame()

    allowed = {normalized_key(status) for status in STATUS_OPTIONS}
    working = df.copy()
    status_key = working["status"].map(normalized_key)

    invalid = working[(status_key != "") & (~status_key.isin(allowed))].copy()

    if invalid.empty:
        return pd.DataFrame()

    return invalid.sort_values("id")


def build_review_queue(df):
    queue = []

    def source_details(record_id):
        match = df[df["id"] == int(record_id)]
        if match.empty:
            return {
                "project": "",
                "discipline": "",
                "title": "",
            }
        row = match.iloc[0]
        return {
            "project": clean_text(row.get("project", "")),
            "discipline": clean_text(row.get("discipline", "")),
            "title": clean_text(row.get("title", "")),
        }

    def add_finding(
        issue_type,
        severity,
        record_id,
        related_ids,
        document_number,
        revision,
        issue,
        recommended_action,
        detail="",
        project="",
        discipline="",
        title="",
    ):
        details = source_details(record_id)
        queue.append(
            {
                "issue_key": finding_key(issue_type, related_ids, detail),
                "issue_type": issue_type,
                "severity": severity,
                "record_id": int(record_id),
                "related_document_ids": sorted({int(value) for value in related_ids}),
                "project": project or details["project"],
                "discipline": discipline or details["discipline"],
                "document_number": clean_text(document_number),
                "title": title or details["title"],
                "revision": clean_text(revision),
                "issue": issue,
                "recommended_action": recommended_action,
            }
        )

    missing = find_missing_metadata(df)
    for _, row in missing.iterrows():
        add_finding(
            "Missing metadata",
            "Warning",
            row["id"],
            [row["id"]],
            row["document_number"],
            row["revision"],
            "Missing required metadata: " + row["missing_fields"],
            "Review the document and complete or approve the missing fields",
            detail=row["missing_fields"],
            title=row["title"],
        )

    duplicates = find_exact_duplicates(df)
    if not duplicates.empty:
        for _, group in duplicates.groupby("duplicate_group"):
            related_ids = [int(value) for value in group["id"].tolist()]
            first = group.iloc[0]
            add_finding(
                "Exact duplicate",
                "Critical",
                related_ids[0],
                related_ids,
                first["document_number"],
                first["revision"],
                "Matching project, discipline, document number, title and revision were found",
                "Compare the metadata and PDFs, add review comments, then approve or reject archiving",
                project=clean_text(first["project"]),
                discipline=clean_text(first["discipline"]),
                title=clean_text(first["title"]),
            )

    conflicts = find_metadata_conflicts(df)
    if not conflicts.empty:
        for _, conflict in conflicts.iterrows():
            related_ids = conflict["related_document_ids"]
            issue_type = clean_text(conflict["conflict_type"])
            add_finding(
                issue_type,
                "Critical",
                related_ids[0],
                related_ids,
                conflict["document_number"],
                conflict["revision"],
                f"{issue_type}: {clean_text(conflict['titles'])}",
                "Inspect the document records and PDFs manually; no automatic cleanup is allowed",
                project=clean_text(conflict["project"]),
                discipline=clean_text(conflict["discipline"]),
                title=clean_text(conflict["titles"]),
            )

    filename_issues = find_filename_issues(df)
    if not filename_issues.empty:
        for _, row in filename_issues.iterrows():
            add_finding(
                "Filename mismatch",
                "Review",
                row["id"],
                [row["id"]],
                row["document_number"],
                row["revision"],
                row["issue"],
                "Compare the register metadata with the PDF and file-naming convention",
                detail=row["issue"],
            )

    missing_pdfs = find_missing_pdf_records(df)
    if not missing_pdfs.empty:
        for _, row in missing_pdfs.iterrows():
            add_finding(
                "Missing controlled PDF",
                "Review",
                row["id"],
                [row["id"]],
                row["document_number"],
                row["revision"],
                "No PDF file is attached to this register record",
                "Verify whether a controlled PDF is required and record the review outcome",
            )

    invalid_statuses = find_invalid_statuses(df)
    if not invalid_statuses.empty:
        for _, row in invalid_statuses.iterrows():
            add_finding(
                "Invalid status",
                "Warning",
                row["id"],
                [row["id"]],
                row["document_number"],
                row["revision"],
                f"Unrecognised status: {clean_text(row['status'])}",
                "Review the record and approve the correct controlled status",
                detail=clean_text(row["status"]),
            )

    queue_df = pd.DataFrame(queue)
    if queue_df.empty:
        return pd.DataFrame(
            columns=[
                "issue_key",
                "issue_type",
                "severity",
                "record_id",
                "related_document_ids",
                "project",
                "discipline",
                "document_number",
                "title",
                "revision",
                "issue",
                "recommended_action",
            ]
        )

    order = {"Critical": 0, "Warning": 1, "Review": 2}
    queue_df["_order"] = queue_df["severity"].map(order).fillna(9)
    return queue_df.sort_values(["_order", "document_number", "revision"]).drop(columns="_order")


def calculate_health_score(df, review_queue):
    """Calculate a proportional register score instead of over-penalising large test files."""
    if df.empty:
        return 100

    if review_queue.empty:
        return 100

    total_records = max(len(df), 1)

    critical_records = review_queue.loc[
        review_queue["severity"] == "Critical", "record_id"
    ].nunique()
    warning_records = review_queue.loc[
        review_queue["severity"] == "Warning", "record_id"
    ].nunique()
    review_records = review_queue.loc[
        review_queue["severity"] == "Review", "record_id"
    ].nunique()

    critical_penalty = min(45, (critical_records / total_records) * 45)
    warning_penalty = min(30, (warning_records / total_records) * 30)
    review_penalty = min(15, (review_records / total_records) * 15)

    score = round(100 - critical_penalty - warning_penalty - review_penalty)
    return max(0, min(100, score))


def display_table(
    df,
    columns=None,
    rename=None,
    height=420,
    row_height=None,
    column_config=None,
    key=None,
):
    if df.empty:
        return

    display_df = df.copy()

    # Internal database identifiers are required behind the scenes, but should
    # never be shown to users in dashboards, tables, exports or review views.
    internal_id_columns = {
        "id",
        "record_id",
        "document_id",
        "file_id",
        "keep_id",
        "remove_id",
        "comparison_id",
        "comparison_item_id",
        "issue_key",
        "related_document_ids",
        "duplicate_group",
    }
    display_df = display_df.drop(
        columns=[
            column
            for column in display_df.columns
            if column in internal_id_columns
        ],
        errors="ignore",
    )

    if columns:
        available = [column for column in columns if column in display_df.columns]
        display_df = display_df[available]

    if rename:
        display_df = display_df.rename(columns=rename)

    dataframe_kwargs = {
        "use_container_width": True,
        "hide_index": True,
        "height": height,
    }

    if row_height is not None:
        dataframe_kwargs["row_height"] = row_height

    if column_config:
        dataframe_kwargs["column_config"] = column_config

    if key:
        dataframe_kwargs["key"] = key

    try:
        st.dataframe(display_df, **dataframe_kwargs)
    except TypeError:
        # Compatibility fallback for older Streamlit versions.
        dataframe_kwargs.pop("row_height", None)
        dataframe_kwargs.pop("key", None)
        st.dataframe(display_df, **dataframe_kwargs)


def render_section_header(title, copy):
    st.markdown(
        f"""
        <div class="section-card">
            <div class="section-title">{title}</div>
            <p class="section-copy">{copy}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_metric_cards(metrics):
    """Render reliable native Streamlit metrics without raw HTML leakage."""
    if not metrics:
        return

    columns = st.columns(len(metrics), gap="small")

    for column, (label, value, note, _value_class) in zip(columns, metrics):
        with column:
            st.metric(label=label, value=value)
            if note:
                st.caption(note)


def render_attached_files(files_df, key_prefix, allow_delete=False):
    if files_df.empty:
        st.info("No PDF files are attached to this selection.")
        return

    for _, file_row in files_df.iterrows():
        file_id = int(file_row["file_id"])
        stored_path = Path(clean_text(file_row["stored_path"]))
        title = clean_text(file_row.get("original_file_name", "PDF document"))
        details = (
            f"{clean_text(file_row.get('document_number', ''))} · "
            f"{clean_text(file_row.get('revision', '')) or 'No revision'} · "
            f"{human_file_size(file_row.get('file_size', 0))} · "
            f"Uploaded {clean_text(file_row.get('uploaded_at', ''))}"
        )

        with st.container(border=True):
            left, middle, right = st.columns([2.3, 1, 1])
            with left:
                st.markdown(f"**{title}**")
                st.caption(details)
            with middle:
                if stored_path.exists() and stored_path.is_file():
                    st.download_button(
                        "Download PDF",
                        data=stored_path.read_bytes(),
                        file_name=title,
                        mime="application/pdf",
                        key=f"{key_prefix}_download_{file_id}",
                        use_container_width=True,
                    )
                else:
                    st.error("Stored file is missing")
            with right:
                if allow_delete:
                    confirmed = st.checkbox(
                        "Confirm delete",
                        key=f"{key_prefix}_confirm_{file_id}",
                    )
                    if st.button(
                        "Delete file",
                        key=f"{key_prefix}_delete_{file_id}",
                        disabled=not confirmed,
                        use_container_width=True,
                    ):
                        delete_document_file(file_id)
                        st.session_state["flash_message"] = (
                            "success",
                            f"PDF file {title} was removed.",
                        )
                        st.rerun()


def build_record_choice_map(df):
    """Create clear, unique record labels while keeping database IDs hidden."""
    if df.empty:
        return {}

    sort_columns = [
        column
        for column in [
            "document_number",
            "revision",
            "title",
            "project",
            "discipline",
            "id",
        ]
        if column in df.columns
    ]
    ordered = df.sort_values(sort_columns).copy()

    records = []
    label_totals = {}

    for _, row in ordered.iterrows():
        document_number = clean_text(row.get("document_number", "")) or "Document number not set"
        revision = clean_text(row.get("revision", "")) or "No revision"
        title = clean_text(row.get("title", "")) or "Untitled document"
        project = clean_text(row.get("project", ""))
        discipline = clean_text(row.get("discipline", ""))

        label_parts = [document_number, revision, title]

        if project:
            label_parts.append(project)

        if discipline:
            label_parts.append(discipline)

        base_label = " · ".join(label_parts)
        label_totals[base_label] = label_totals.get(base_label, 0) + 1
        records.append((base_label, int(row["id"])))

    seen_labels = {}
    choices = {}

    for base_label, internal_id in records:
        seen_labels[base_label] = seen_labels.get(base_label, 0) + 1

        if label_totals[base_label] > 1:
            visible_label = f"{base_label} · Entry {seen_labels[base_label]}"
        else:
            visible_label = base_label

        choices[visible_label] = internal_id

    return choices


def build_review_case_choice_map(cases_df):
    choices = {}
    for position, (_, row) in enumerate(cases_df.iterrows(), start=1):
        label = (
            f"{clean_text(row.get('issue_type', 'Review'))} · "
            f"{clean_text(row.get('document_number', 'Document')) or 'Document not set'} · "
            f"{clean_text(row.get('revision', '')) or 'No revision'} · "
            f"{clean_text(row.get('status', 'Pending Review'))} · Case {position}"
        )
        choices[label] = int(row["id"])
    return choices


def decode_related_ids(value):
    if isinstance(value, list):
        return [int(item) for item in value]
    try:
        return [int(item) for item in json.loads(clean_text(value) or "[]")]
    except (json.JSONDecodeError, TypeError, ValueError):
        return []


def show_flash_message():
    flash = st.session_state.pop("flash_message", None)
    if not flash:
        return

    kind, message = flash
    if kind == "success":
        st.success(message)
    elif kind == "warning":
        st.warning(message)
    else:
        st.info(message)



# -----------------------------
# Phase 1 workflow helpers
# -----------------------------

def latest_revision_ids(df):
    """Return the internal IDs of the latest revision in each document family."""
    if df.empty:
        return set()

    latest_ids = set()
    working = df.copy()
    working["_family_key"] = working.apply(revision_family_key, axis=1)

    for _, family in working.groupby("_family_key", dropna=False):
        ordered = sort_revision_history(family)
        if not ordered.empty:
            latest_ids.add(int(ordered.iloc[0]["id"]))

    return latest_ids


def review_cases_for_document(document_id, cases_df):
    """Return open review cases linked to one document record."""
    if cases_df.empty:
        return cases_df.copy()

    matches = []
    for index, case_row in cases_df.iterrows():
        related_ids = decode_related_ids(case_row.get("related_document_ids", ""))
        record_id = case_row.get("record_id")
        try:
            if pd.notna(record_id):
                related_ids.append(int(record_id))
        except (TypeError, ValueError):
            pass

        if int(document_id) in set(related_ids):
            matches.append(index)

    return cases_df.loc[matches].copy() if matches else cases_df.iloc[0:0].copy()


def workflow_status_for_document(document_row, cases_df):
    """Keep official document status separate from app workflow status."""
    if int(document_row.get("is_archived", 0) or 0):
        return "Archived"

    linked_cases = review_cases_for_document(int(document_row["id"]), cases_df)
    if linked_cases.empty:
        return "Ready"

    issue_types = {
        normalized_key(value)
        for value in linked_cases.get("issue_type", pd.Series(dtype=str)).tolist()
    }
    if "exact duplicate" in issue_types:
        return "Possible duplicate"

    return "Needs checking"


def attention_action(issue_type):
    """Translate internal issue types into a clear user action."""
    issue_key = normalized_key(issue_type)
    action_map = {
        "missing metadata": "Correct the missing information",
        "exact duplicate": "Compare records",
        "title conflict": "Check and correct the title",
        "filename mismatch": "Check the PDF and filename",
        "missing controlled pdf": "Attach the controlled PDF",
        "invalid status": "Choose a valid document status",
        "pdf extraction uncertain": "Check the extracted value",
        "similar document number": "Compare document numbers",
    }
    return action_map.get(issue_key, "Review the document")


def attention_problem_label(issue_type):
    issue_key = normalized_key(issue_type)
    label_map = {
        "missing metadata": "Missing mandatory information",
        "exact duplicate": "Possible duplicate",
        "title conflict": "Conflicting document title",
        "filename mismatch": "PDF filename needs checking",
        "missing controlled pdf": "Controlled PDF is missing",
        "invalid status": "Document status needs checking",
        "pdf extraction uncertain": "PDF extraction needs checking",
        "similar document number": "Similar document number",
    }
    return label_map.get(issue_key, clean_text(issue_type) or "Document needs checking")


def attention_table(cases_df):
    if cases_df.empty:
        return pd.DataFrame()

    rows = []
    for _, case_row in cases_df.iterrows():
        document_number = clean_text(case_row.get("document_number", "")) or "Document number not set"
        revision = clean_text(case_row.get("revision", ""))
        document_label = document_number + (f" Rev {revision}" if revision else "")

        rows.append(
            {
                "Priority": clean_text(case_row.get("severity", "Review")),
                "Problem": attention_problem_label(case_row.get("issue_type", "")),
                "Document": document_label,
                "Title": clean_text(case_row.get("title", "")),
                "Project": clean_text(case_row.get("project", "")),
                "Explanation": clean_text(case_row.get("issue_summary", "")),
                "Next action": attention_action(case_row.get("issue_type", "")),
                "Review status": clean_text(case_row.get("status", "Pending Review")),
            }
        )

    return pd.DataFrame(rows)



def classify_incoming_document(record, df):
    """Classify an incoming record without treating a new revision as a duplicate."""
    if df.empty:
        return {"type": "new_document", "matches": pd.DataFrame()}

    project_key = normalized_key(record.get("project", ""))
    discipline_key = normalized_key(record.get("discipline", ""))
    number_key = normalized_key(record.get("document_number", ""))
    title_key = normalized_key(record.get("title", ""))
    revision_key = normalized_key(record.get("revision", ""))

    working = df.copy()
    for column in ["project", "discipline", "document_number", "title", "revision"]:
        working[f"_{column}_key"] = working[column].map(normalized_key)

    same_number = working[
        (working["_project_key"] == project_key)
        & (working["_discipline_key"] == discipline_key)
        & (working["_document_number_key"] == number_key)
    ].copy()

    if same_number.empty:
        return {"type": "new_document", "matches": same_number}

    same_title = same_number[same_number["_title_key"] == title_key].copy()
    same_revision = same_title[same_title["_revision_key"] == revision_key].copy()

    if not same_revision.empty:
        return {"type": "exact_duplicate", "matches": same_revision}

    if not same_title.empty:
        return {"type": "new_revision", "matches": same_title}

    return {"type": "similar_document_number", "matches": same_number}


# -----------------------------
# Current register state
# -----------------------------

documents_df = get_documents()
all_documents_df = get_documents(include_archived=True)
archived_documents_df = get_archived_documents()
all_pdf_files_df = get_document_files()
missing_pdf_df = find_missing_pdf_records(documents_df)
review_queue_df = build_review_queue(documents_df)
sync_review_cases(review_queue_df)
review_cases_df = get_review_cases()
open_review_cases_df = review_cases_df[
    review_cases_df["status"] != "Resolved"
].copy() if not review_cases_df.empty else pd.DataFrame()
exact_duplicates_df = find_exact_duplicates(documents_df)
metadata_conflicts_df = find_metadata_conflicts(documents_df)
revision_groups_df = find_revision_groups(documents_df)
health_score = calculate_health_score(documents_df, review_queue_df)

if health_score >= 85:
    health_class = "health-good"
    health_note = "Healthy register"
elif health_score >= 65:
    health_class = "health-watch"
    health_note = "Needs attention"
else:
    health_class = "health-risk"
    health_note = "Priority review needed"


# -----------------------------
# Sidebar and page shell
# -----------------------------

def set_active_page(target_page):
    st.session_state["active_page"] = target_page


valid_pages = {
    "Dashboard",
    "Add document",
    "Import CSV",
    "PDF intake",
    "Documents",
    "Register comparison",
    "Documents needing attention",
    "Revision history",
    "Administration",
}

if st.session_state.get("active_page") not in valid_pages:
    st.session_state["active_page"] = "Dashboard"


with st.sidebar:
    st.markdown("## Document Control")
    st.caption("Register governance workspace")

    active_page = st.session_state["active_page"]

    st.button(
        "Dashboard",
        key="nav_dashboard",
        type="primary" if active_page == "Dashboard" else "secondary",
        use_container_width=True,
        on_click=set_active_page,
        args=("Dashboard",),
    )

    st.markdown("#### Add document")
    st.button(
        "Add manually",
        key="nav_add_manually",
        type="primary" if active_page == "Add document" else "secondary",
        use_container_width=True,
        on_click=set_active_page,
        args=("Add document",),
    )
    st.button(
        "Upload Excel or CSV register",
        key="nav_import_csv",
        type="primary" if active_page == "Import CSV" else "secondary",
        use_container_width=True,
        on_click=set_active_page,
        args=("Import CSV",),
    )
    st.button(
        "Upload PDF and extract information",
        key="nav_pdf_intake",
        type="primary" if active_page == "PDF intake" else "secondary",
        use_container_width=True,
        on_click=set_active_page,
        args=("PDF intake",),
    )

    st.markdown("#### Manage")
    st.button(
        "Documents",
        key="nav_documents",
        type="primary" if active_page == "Documents" else "secondary",
        use_container_width=True,
        on_click=set_active_page,
        args=("Documents",),
    )
    st.button(
        "Register comparison",
        key="nav_register_comparison",
        type="primary" if active_page == "Register comparison" else "secondary",
        use_container_width=True,
        on_click=set_active_page,
        args=("Register comparison",),
    )

    st.markdown("#### Review")
    st.button(
        "Documents needing attention",
        key="nav_documents_attention",
        type="primary" if active_page == "Documents needing attention" else "secondary",
        use_container_width=True,
        on_click=set_active_page,
        args=("Documents needing attention",),
    )

    st.markdown("#### History and settings")
    st.button(
        "Revision history",
        key="nav_revision_history",
        type="primary" if active_page == "Revision history" else "secondary",
        use_container_width=True,
        on_click=set_active_page,
        args=("Revision history",),
    )
    st.button(
        "Administration",
        key="nav_administration",
        type="primary" if active_page == "Administration" else "secondary",
        use_container_width=True,
        on_click=set_active_page,
        args=("Administration",),
    )

    page = st.session_state["active_page"]

    st.divider()
    st.markdown("#### Workspace status")
    st.write(f"**{len(documents_df)}** active records")
    st.write(f"**{len(all_pdf_files_df)}** PDF files")
    st.write(f"**{len(open_review_cases_df)}** need attention")
    st.write(f"**{len(archived_documents_df)}** archived records")
    st.write(f"**{health_score}/100** register health")
    st.caption("Local SQLite database and file library - Demo data only")


st.markdown(
    """
    <div class="hero">
        <div class="hero-kicker">DOCUMENT GOVERNANCE · PORTFOLIO MVP</div>
        <h1>Document Control AI Assistant</h1>
        <p>
            A structured workspace for document registers, controlled PDF files,
            project and discipline grouping, revision visibility and review prioritisation.
        </p>
        <div class="hero-badges">
            <span class="hero-badge">Metadata validation</span>
            <span class="hero-badge">Duplicate protection</span>
            <span class="hero-badge">Revision tracking</span>
            <span class="hero-badge">Excel + CSV intake</span>
            <span class="hero-badge">Register comparison</span>
            <span class="hero-badge">PDF metadata extraction</span>
            <span class="hero-badge">PDF document library</span>
            <span class="hero-badge">Project + discipline folders</span>
            <span class="hero-badge">Manual review + approval</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

show_flash_message()


# -----------------------------
# Dashboard
# -----------------------------

if page == "Dashboard":
    render_section_header(
        "Register overview",
        "Monitor document volumes, data quality and the items that need attention first.",
    )

    unique_document_count = (
        documents_df["document_number"].map(normalized_key).nunique()
        if not documents_df.empty
        else 0
    )

    exact_duplicate_group_count = (
        exact_duplicates_df["duplicate_group"].nunique()
        if not exact_duplicates_df.empty
        else 0
    )

    render_metric_cards(
        [
            ("Stored records", len(documents_df), "All register rows", ""),
            ("Controlled PDF files", len(all_pdf_files_df), "Saved in the file library", ""),
            ("Records without PDF", len(missing_pdf_df), "Need a controlled file", "health-watch" if len(missing_pdf_df) else "health-good"),
            ("Manual review", len(open_review_cases_df), "Open approval cases", ""),
            ("Register health", f"{health_score}/100", health_note, health_class),
        ]
    )

    if documents_df.empty:
        st.info("The register is empty. Add a document manually or upload an Excel/CSV register.")
    else:
        left, right = st.columns([1.25, 1])

        with left:
            st.subheader("Priority actions")
            if open_review_cases_df.empty:
                st.success("No manual review cases are currently open.")
            else:
                display_table(
                    open_review_cases_df.head(10),
                    columns=[
                        "severity",
                        "status",
                        "issue_type",
                        "document_number",
                        "revision",
                        "issue_summary",
                        "recommended_action",
                    ],
                    rename={
                        "severity": "Severity",
                        "status": "Review Status",
                        "issue_type": "Issue Type",
                        "document_number": "Document Number",
                        "revision": "Revision",
                        "issue_summary": "Issue",
                        "recommended_action": "Recommended Action",
                    },
                    height=390,
                )

        with right:
            st.subheader("Status distribution")
            status_data = (
                documents_df.assign(
                    status_display=documents_df["status"].replace("", "Not set")
                )["status_display"]
                .value_counts()
                .rename_axis("Status")
                .to_frame("Records")
            )
            st.bar_chart(status_data)

        st.subheader("Recently registered")
        display_table(
            documents_df.head(8),
            columns=[
                "document_number",
                "title",
                "revision",
                "status",
                "owner",
                "due_date",
            ],
            rename={
                "document_number": "Document Number",
                "title": "Title",
                "revision": "Revision",
                "status": "Status",
                "owner": "Owner",
                "due_date": "Due Date",
            },
            height=310,
        )


# -----------------------------
# Add document
# -----------------------------

elif page == "Add document":
    render_section_header(
        "Add a controlled document",
        "Required fields are validated before the record is stored. A different revision of an existing document is allowed; an exact duplicate is blocked.",
    )

    with st.form("add_document_form", clear_on_submit=True, border=True):
        left, right = st.columns(2)

        with left:
            document_number = st.text_input(
                "Document Number *",
                placeholder="Example: RWE-ENG-DRG-0001",
            )
            title = st.text_input(
                "Document Title *",
                placeholder="Example: Site Layout Drawing",
            )
            project = st.text_input(
                "Project *",
                placeholder="Example: Offshore Wind Farm",
            )
            discipline = st.selectbox(
                "Discipline *",
                [""] + DISCIPLINE_OPTIONS,
            )
            revision = st.text_input(
                "Revision *",
                placeholder="Example: P01, C01, A or B",
            )

        with right:
            status = st.selectbox(
                "Status *",
                [""] + STATUS_OPTIONS,
            )
            owner = st.text_input(
                "Owner *",
                placeholder="Example: Document Control Team",
            )
            originator = st.text_input(
                "Originator",
                placeholder="Example: Design Contractor",
            )
            created_date = st.date_input("Created Date", value=None)
            due_date = st.date_input("Due Date (optional)", value=None)
            file_name = st.text_input(
                "File Name",
                placeholder="Example: RWE-ENG-DRG-0001_P01.pdf",
            )

        notes = st.text_area(
            "Notes",
            placeholder="Add review comments, workflow notes or actions.",
        )

        allow_possible_duplicate = st.checkbox(
            "Allow this possible duplicate to be saved for manual review",
            value=False,
            help=(
                "Use this only when another record has the same project, discipline, "
                "document number, title and revision but the metadata or PDF needs comparison."
            ),
        )

        submitted = st.form_submit_button(
            "Save document",
            type="primary",
            use_container_width=True,
        )

        if submitted:
            new_document = {
                "document_number": clean_text(document_number),
                "title": clean_text(title),
                "project": clean_text(project),
                "discipline": clean_text(discipline),
                "revision": clean_text(revision),
                "status": clean_text(status),
                "owner": clean_text(owner),
                "originator": clean_text(originator),
                "created_date": str(created_date) if created_date else "",
                "due_date": str(due_date) if due_date else "",
                "file_name": clean_text(file_name),
                "notes": clean_text(notes),
            }

            missing_required = [
                field
                for field in REQUIRED_FIELDS
                if new_document[field] == ""
            ]

            if missing_required:
                st.error(
                    "Complete all required fields: "
                    + ", ".join(field.replace("_", " ").title() for field in missing_required)
                )
            elif (
                created_date is not None
                and due_date is not None
                and created_date > due_date
            ):
                st.error("When a Due Date is provided, Created Date cannot be later than it.")
            else:
                relationship = classify_incoming_document(
                    new_document,
                    documents_df,
                )
                exact_same_metadata = make_record_signature(
                    new_document
                ) in existing_record_signatures(documents_df)
                possible_duplicate = relationship["type"] in {
                    "exact_duplicate",
                    "similar_document_number",
                }

                if exact_same_metadata:
                    st.error(
                        "The same document record is already stored. "
                        "No additional copy was created."
                    )
                elif (
                    relationship["type"] == "exact_duplicate"
                    and not allow_possible_duplicate
                ):
                    st.error(
                        "The same document number, title and revision already exist. "
                        "Compare the records before saving another copy."
                    )
                elif (
                    relationship["type"] == "similar_document_number"
                    and not allow_possible_duplicate
                ):
                    st.error(
                        "The same document number already exists with a different title. "
                        "Check whether this is a correction or a separate document."
                    )
                else:
                    add_document(new_document)

                    if relationship["type"] == "new_revision":
                        message = (
                            f"New revision {new_document['revision']} added. "
                            "It was not treated as a duplicate."
                        )
                    elif possible_duplicate:
                        message = (
                            "The possible duplicate was saved and added to "
                            "Documents needing attention."
                        )
                    else:
                        message = "Document saved successfully."

                    st.session_state["flash_message"] = (
                        "success",
                        message,
                    )
                    st.rerun()


# -----------------------------
# Excel and CSV register intake
# -----------------------------

elif page == "Import CSV":
    render_section_header(
        "Upload an Excel or CSV register",
        "Match the source columns, correct the records, review duplicate and revision analysis, then approve the rows you want to add.",
    )

    st.info(
        "Nothing is imported automatically. The source file is previewed and every row can be corrected before approval."
    )

    template_df = pd.DataFrame(
        [
            {
                "document_number": "RWE-ENG-DRG-0001",
                "title": "Site Layout Drawing",
                "project": "Offshore Wind Farm",
                "discipline": "Engineering",
                "revision": "P01",
                "status": "For Review",
                "owner": "Document Control Team",
                "originator": "Design Contractor",
                "created_date": "2026-06-19",
                "due_date": "",
                "file_name": "RWE-ENG-DRG-0001_P01.pdf",
                "notes": "Initial submission",
            }
        ]
    )

    template_left, template_right = st.columns(2)
    with template_left:
        st.download_button(
            "Download CSV template",
            data=template_df.to_csv(index=False).encode("utf-8-sig"),
            file_name="document_register_template.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with template_right:
        excel_template = io.BytesIO()
        with pd.ExcelWriter(excel_template, engine="openpyxl") as writer:
            template_df.to_excel(writer, index=False, sheet_name="Document Register")
        st.download_button(
            "Download Excel template",
            data=excel_template.getvalue(),
            file_name="document_register_template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    uploaded_register = st.file_uploader(
        "Upload an Excel or CSV document register",
        type=["xlsx", "xls", "csv"],
        key="register_intake_upload",
    )

    if uploaded_register is not None:
        try:
            extension = Path(uploaded_register.name).suffix.lower()
            selected_sheet = ""

            if extension == ".csv":
                raw_register = read_uploaded_csv(uploaded_register)
                source_type = "CSV"
            else:
                sheet_names = get_excel_sheet_names(uploaded_register)
                if not sheet_names:
                    raise ValueError("The Excel workbook does not contain a readable worksheet.")
                selected_sheet = st.selectbox(
                    "Choose the worksheet",
                    sheet_names,
                    key="register_intake_sheet",
                )
                raw_register = read_uploaded_excel_sheet(
                    uploaded_register,
                    selected_sheet,
                )
                source_type = "Excel"

            raw_register = normalise_register_source_dataframe(raw_register)

            if raw_register.empty:
                st.warning("The selected register does not contain any data rows.")
            else:
                st.markdown("### 1. Source preview")
                st.caption(
                    f"{source_type} file: {uploaded_register.name}"
                    + (f" · Worksheet: {selected_sheet}" if selected_sheet else "")
                    + f" · {len(raw_register)} row(s)"
                )
                st.dataframe(
                    raw_register.head(25),
                    use_container_width=True,
                    hide_index=True,
                    height=300,
                )

                source_columns = list(raw_register.columns)
                automatic_mapping = suggest_register_column_mapping(source_columns)
                file_key = hashlib.sha256(uploaded_register.getvalue()).hexdigest()[:10]
                mapping = {}

                with st.expander("2. Review column matching", expanded=True):
                    st.caption(
                        "The app has suggested a source column for each register field. "
                        "Change any incorrect match before continuing."
                    )
                    mapping_columns = st.columns(3)
                    options = ["Not mapped"] + source_columns

                    for position, target_field in enumerate(CSV_COLUMNS):
                        suggested_source = automatic_mapping.get(target_field, "")
                        default_index = (
                            options.index(suggested_source)
                            if suggested_source in options
                            else 0
                        )
                        with mapping_columns[position % 3]:
                            selected_source = st.selectbox(
                                REGISTER_FIELD_LABELS[target_field],
                                options,
                                index=default_index,
                                key=(
                                    f"register_map_{file_key}_"
                                    f"{normalize_column_name(selected_sheet)}_"
                                    f"{target_field}"
                                ),
                            )
                            mapping[target_field] = (
                                "" if selected_source == "Not mapped" else selected_source
                            )

                mapped_register = build_mapped_register(raw_register, mapping)

                st.markdown("### 3. Review and correct records")
                st.caption(
                    "Edit any value that was mapped incorrectly. Changes here affect only "
                    "the preview; the source file is never overwritten."
                )

                edited_register = st.data_editor(
                    mapped_register,
                    use_container_width=True,
                    hide_index=True,
                    num_rows="fixed",
                    height=420,
                    key=f"register_editor_{file_key}_{normalize_column_name(selected_sheet)}",
                    column_config={
                        "document_number": st.column_config.TextColumn("Document Number", width="medium"),
                        "title": st.column_config.TextColumn("Document Title", width="large"),
                        "project": st.column_config.TextColumn("Project", width="medium"),
                        "discipline": st.column_config.TextColumn("Discipline", width="medium"),
                        "revision": st.column_config.TextColumn("Revision", width="small"),
                        "status": st.column_config.TextColumn("Official Status", width="medium"),
                        "owner": st.column_config.TextColumn("Owner", width="medium"),
                        "originator": st.column_config.TextColumn("Originator", width="medium"),
                        "created_date": st.column_config.TextColumn("Date Received", width="small"),
                        "due_date": st.column_config.TextColumn("Due Date (optional)", width="small"),
                        "file_name": st.column_config.TextColumn("File Name", width="large"),
                        "notes": st.column_config.TextColumn("Notes", width="large"),
                    },
                )

                cleaned_register = edited_register.copy()
                for column in CSV_COLUMNS:
                    if column not in cleaned_register.columns:
                        cleaned_register[column] = ""
                    cleaned_register[column] = (
                        cleaned_register[column]
                        .fillna("")
                        .astype(str)
                        .str.strip()
                    )
                cleaned_register = cleaned_register[CSV_COLUMNS].reset_index(drop=True)

                database_signatures = existing_record_signatures(documents_df)
                seen_upload_signatures = set()
                analysis_rows = []

                for row_index, row in cleaned_register.iterrows():
                    record = {column: clean_text(row[column]) for column in CSV_COLUMNS}
                    signature = make_record_signature(record)
                    missing_fields = [
                        field
                        for field in REQUIRED_FIELDS
                        if not clean_text(record.get(field, ""))
                    ]
                    minimum_information_missing = (
                        not record["document_number"] or not record["title"]
                    )
                    repeated_in_upload = signature in seen_upload_signatures
                    already_stored = signature in database_signatures
                    relationship = classify_incoming_document(record, documents_df)

                    if minimum_information_missing:
                        analysis = "Cannot import"
                        detail = "Document number and title are required"
                        default_import = False
                    elif repeated_in_upload:
                        analysis = "Repeated in uploaded file"
                        detail = "An identical row already appears earlier in this upload"
                        default_import = False
                    elif already_stored:
                        analysis = "Already stored"
                        detail = "The complete record already exists in the app"
                        default_import = False
                    elif relationship["type"] == "exact_duplicate":
                        analysis = "Possible duplicate"
                        detail = "The same document number, title and revision already exist"
                        default_import = False
                    elif relationship["type"] == "new_revision":
                        analysis = "New revision"
                        detail = "The document exists, but this revision is new"
                        default_import = not missing_fields
                    elif relationship["type"] == "similar_document_number":
                        analysis = "Similar document number"
                        detail = "The document number exists with a different title"
                        default_import = False
                    elif missing_fields:
                        analysis = "Missing mandatory information"
                        detail = "Complete the highlighted fields before importing"
                        default_import = False
                    else:
                        analysis = "New document"
                        detail = "Ready to add to the register"
                        default_import = True

                    analysis_rows.append(
                        {
                            "Import": default_import,
                            "Source Row": row_index + 2,
                            "Document Number": record["document_number"],
                            "Title": record["title"],
                            "Revision": record["revision"],
                            "Analysis": analysis,
                            "Explanation": detail,
                            "Missing Information": ", ".join(
                                REGISTER_FIELD_LABELS.get(field, field)
                                for field in missing_fields
                            ),
                            "_row_index": row_index,
                            "_eligible": analysis not in {
                                "Cannot import",
                                "Repeated in uploaded file",
                                "Already stored",
                                "Possible duplicate",
                            },
                        }
                    )
                    seen_upload_signatures.add(signature)

                analysis_df = pd.DataFrame(analysis_rows)
                ready_count = int(analysis_df["Import"].sum()) if not analysis_df.empty else 0
                new_revision_count = int((analysis_df["Analysis"] == "New revision").sum()) if not analysis_df.empty else 0
                check_count = int(
                    analysis_df["Analysis"].isin(
                        ["Similar document number", "Missing mandatory information"]
                    ).sum()
                ) if not analysis_df.empty else 0
                duplicate_count = int(
                    analysis_df["Analysis"].isin(
                        ["Already stored", "Possible duplicate", "Repeated in uploaded file"]
                    ).sum()
                ) if not analysis_df.empty else 0

                render_metric_cards(
                    [
                        ("Rows found", len(cleaned_register), "In uploaded register", ""),
                        ("Ready to import", ready_count, "Selected by default", "health-good" if ready_count else ""),
                        ("New revisions", new_revision_count, "Not treated as duplicates", "health-good" if new_revision_count else ""),
                        ("Please check", check_count, "Needs correction or confirmation", "health-watch" if check_count else ""),
                        ("Duplicates skipped", duplicate_count, "Not selected for import", "health-risk" if duplicate_count else ""),
                    ]
                )

                st.markdown("### 4. Select records to import")
                st.caption(
                    "Rows marked as possible duplicates or already stored cannot be imported "
                    "from this screen. Correct the source values or compare the records first."
                )

                selection_df = st.data_editor(
                    analysis_df.drop(columns=["_row_index", "_eligible"]),
                    use_container_width=True,
                    hide_index=True,
                    num_rows="fixed",
                    height=360,
                    key=f"register_selection_{file_key}_{normalize_column_name(selected_sheet)}",
                    disabled=[
                        "Source Row",
                        "Document Number",
                        "Title",
                        "Revision",
                        "Analysis",
                        "Explanation",
                        "Missing Information",
                    ],
                    column_config={
                        "Import": st.column_config.CheckboxColumn("Import", width="small"),
                        "Source Row": st.column_config.NumberColumn("Row", width="small"),
                        "Document Number": st.column_config.TextColumn(width="medium"),
                        "Title": st.column_config.TextColumn(width="large"),
                        "Revision": st.column_config.TextColumn(width="small"),
                        "Analysis": st.column_config.TextColumn(width="medium"),
                        "Explanation": st.column_config.TextColumn(width="large"),
                        "Missing Information": st.column_config.TextColumn(width="large"),
                    },
                )

                selected_positions = [
                    position
                    for position, selected_value in enumerate(selection_df["Import"].tolist())
                    if bool(selected_value)
                ]
                selected_count = len(selected_positions)

                export_corrected, import_action = st.columns([1, 1])
                with export_corrected:
                    st.download_button(
                        "Download corrected preview",
                        data=cleaned_register.to_csv(index=False).encode("utf-8-sig"),
                        file_name="corrected_register_preview.csv",
                        mime="text/csv",
                        use_container_width=True,
                    )
                with import_action:
                    confirmed = st.checkbox(
                        f"I reviewed the analysis and want to import {selected_count} selected record(s).",
                        key=f"confirm_register_import_{file_key}",
                    )

                if st.button(
                    "Approve and add selected records",
                    type="primary",
                    disabled=not confirmed or selected_count == 0,
                    use_container_width=True,
                    key=f"approve_register_import_{file_key}",
                ):
                    imported_count = 0
                    skipped_count = 0

                    for position in selected_positions:
                        analysis_row = analysis_df.iloc[position]
                        source_row_index = int(analysis_row["_row_index"])
                        record = {
                            column: clean_text(cleaned_register.iloc[source_row_index][column])
                            for column in CSV_COLUMNS
                        }
                        relationship = classify_incoming_document(record, documents_df)
                        missing_fields = [
                            field for field in REQUIRED_FIELDS if not record[field]
                        ]
                        signature = make_record_signature(record)

                        if (
                            missing_fields
                            or not record["document_number"]
                            or not record["title"]
                            or signature in database_signatures
                            or relationship["type"] == "exact_duplicate"
                        ):
                            skipped_count += 1
                            continue

                        add_document(record)
                        imported_count += 1
                        database_signatures.add(signature)

                    st.session_state["flash_message"] = (
                        "success" if imported_count else "warning",
                        f"{imported_count} record(s) added to the register. "
                        f"{skipped_count} selected row(s) were skipped because they were incomplete or duplicated.",
                    )
                    st.rerun()

        except pd.errors.EmptyDataError:
            st.error("The uploaded register is empty.")
        except ImportError as error:
            st.error(
                "An Excel reader is missing. Install openpyxl for .xlsx files and xlrd for .xls files."
            )
            st.code(str(error))
        except Exception as error:
            st.error("The register could not be processed.")
            st.code(str(error))


# -----------------------------
# Register comparison
# -----------------------------

elif page == "Register comparison":
    render_section_header(
        "Master Register Comparison & Reconciliation",
        "Upload two independent CSV registers, compare them side by side and create an auditable reconciliation report. Neither source register is overwritten.",
    )

    st.info(
        "Matching uses Project + Discipline + Document Number. The app highlights differences, but uncertain results always require manual review and approval comments."
    )

    label_col_a, label_col_b = st.columns(2)
    with label_col_a:
        register_a_label = st.text_input(
            "Register A label",
            value="Register A",
            key="comparison_label_a",
        )
        register_a_file = st.file_uploader(
            "Upload Register A (CSV)",
            type=["csv"],
            key="comparison_file_a",
        )
    with label_col_b:
        register_b_label = st.text_input(
            "Register B label",
            value="Register B",
            key="comparison_label_b",
        )
        register_b_file = st.file_uploader(
            "Upload Register B (CSV)",
            type=["csv"],
            key="comparison_file_b",
        )

    current_results_df = pd.DataFrame()
    current_internal_issues_df = pd.DataFrame()
    current_summary = {}

    if register_a_file is not None and register_b_file is not None:
        try:
            raw_a = read_uploaded_csv(register_a_file)
            raw_b = read_uploaded_csv(register_b_file)

            missing_a = [column for column in ["document_number"] if column not in raw_a.columns]
            missing_b = [column for column in ["document_number"] if column not in raw_b.columns]

            if missing_a or missing_b:
                if missing_a:
                    st.error(f"{register_a_label} is missing: {', '.join(missing_a)}")
                if missing_b:
                    st.error(f"{register_b_label} is missing: {', '.join(missing_b)}")
            else:
                prepared_a = prepare_uploaded_register(raw_a)
                prepared_b = prepare_uploaded_register(raw_b)
                (
                    current_results_df,
                    current_internal_issues_df,
                    current_summary,
                ) = compare_master_registers(
                    prepared_a,
                    prepared_b,
                    register_a_label,
                    register_b_label,
                )

                render_metric_cards(
                    [
                        (f"Rows – {register_a_label}", len(prepared_a), "Source rows", ""),
                        (f"Rows – {register_b_label}", len(prepared_b), "Source rows", ""),
                        ("Documents compared", current_summary.get("total_documents", 0), "Matched by controlled identity", ""),
                        ("Manual review", current_summary.get("review_items", 0), "Differences needing a decision", "health-watch"),
                        ("No change", current_summary.get("no_change_items", 0), "Aligned records", "health-good"),
                    ]
                )

                overview_tab, review_tab, internal_tab, saved_tab = st.tabs(
                    [
                        "Comparison overview",
                        "Side-by-side review",
                        "Issues inside each register",
                        "Saved comparisons",
                    ]
                )

                with overview_tab:
                    filter_left, filter_middle, filter_right = st.columns(3)
                    with filter_left:
                        classification_options = sorted(
                            current_results_df["classification"].dropna().unique().tolist()
                        ) if not current_results_df.empty else []
                        selected_classifications = st.multiselect(
                            "Classification",
                            classification_options,
                            key="comparison_class_filter",
                        )
                    with filter_middle:
                        project_options = sorted(
                            value for value in current_results_df["project"].dropna().unique().tolist()
                            if clean_text(value)
                        ) if not current_results_df.empty else []
                        selected_projects = st.multiselect(
                            "Project",
                            project_options,
                            key="comparison_project_filter",
                        )
                    with filter_right:
                        discipline_options = sorted(
                            value for value in current_results_df["discipline"].dropna().unique().tolist()
                            if clean_text(value)
                        ) if not current_results_df.empty else []
                        selected_disciplines = st.multiselect(
                            "Discipline",
                            discipline_options,
                            key="comparison_discipline_filter",
                        )

                    filtered_comparison = current_results_df.copy()
                    if selected_classifications:
                        filtered_comparison = filtered_comparison[
                            filtered_comparison["classification"].isin(selected_classifications)
                        ]
                    if selected_projects:
                        filtered_comparison = filtered_comparison[
                            filtered_comparison["project"].isin(selected_projects)
                        ]
                    if selected_disciplines:
                        filtered_comparison = filtered_comparison[
                            filtered_comparison["discipline"].isin(selected_disciplines)
                        ]

                    display_table(
                        filtered_comparison,
                        columns=[
                            "project",
                            "discipline",
                            "document_number",
                            "title_a",
                            "title_b",
                            "revision_a",
                            "revision_b",
                            "status_a",
                            "status_b",
                            "classification",
                            "severity",
                            "differing_fields",
                            "revisions_only_a",
                            "revisions_only_b",
                            "recommended_action",
                        ],
                        rename={
                            "project": "Project",
                            "discipline": "Discipline",
                            "document_number": "Document Number",
                            "title_a": f"Title – {register_a_label}",
                            "title_b": f"Title – {register_b_label}",
                            "revision_a": f"Revision – {register_a_label}",
                            "revision_b": f"Revision – {register_b_label}",
                            "status_a": f"Status – {register_a_label}",
                            "status_b": f"Status – {register_b_label}",
                            "classification": "Comparison Result",
                            "severity": "Priority",
                            "differing_fields": "Changed Fields",
                            "revisions_only_a": f"Revisions only in {register_a_label}",
                            "revisions_only_b": f"Revisions only in {register_b_label}",
                            "recommended_action": "Recommended Manual Action",
                        },
                        height=650,
                        row_height=42,
                        key="current_comparison_overview",
                    )

                    export_df = comparison_export_dataframe(
                        filtered_comparison,
                        register_a_label,
                        register_b_label,
                    )
                    download_left, download_right = st.columns(2)
                    with download_left:
                        st.download_button(
                            "Download full reconciliation report",
                            data=export_df.to_csv(index=False).encode("utf-8-sig"),
                            file_name="master_register_reconciliation.csv",
                            mime="text/csv",
                            use_container_width=True,
                        )
                    with download_right:
                        issues_export = comparison_export_dataframe(
                            filtered_comparison[filtered_comparison["review_required"]],
                            register_a_label,
                            register_b_label,
                        )
                        st.download_button(
                            "Download manual-review items only",
                            data=issues_export.to_csv(index=False).encode("utf-8-sig"),
                            file_name="master_register_manual_review.csv",
                            mime="text/csv",
                            use_container_width=True,
                        )

                    with st.expander("Save this comparison for audited review", expanded=False):
                        comparison_name = st.text_input(
                            "Comparison name",
                            value=f"{register_a_label} vs {register_b_label}",
                            key="comparison_name",
                        )
                        comparison_creator = st.text_input(
                            "Prepared by",
                            placeholder="Reviewer or Document Controller name",
                            key="comparison_creator",
                        )
                        st.caption(
                            "Saving creates a permanent reconciliation session. Each difference can then be manually approved with reviewer comments."
                        )
                        if st.button(
                            "Save comparison session",
                            type="primary",
                            use_container_width=True,
                            key="save_comparison_session",
                        ):
                            if not clean_text(comparison_name):
                                st.error("Comparison name is required.")
                            elif not clean_text(comparison_creator):
                                st.error("Prepared by is required.")
                            else:
                                items = current_results_df.to_dict("records")
                                comparison_id = create_register_comparison(
                                    {
                                        "comparison_name": comparison_name,
                                        "register_a_label": register_a_label,
                                        "register_b_label": register_b_label,
                                        "register_a_filename": register_a_file.name,
                                        "register_b_filename": register_b_file.name,
                                        "created_by": comparison_creator,
                                        "total_items": len(current_results_df),
                                        "review_items": int(current_results_df["review_required"].sum()),
                                        "no_change_items": int((~current_results_df["review_required"]).sum()),
                                        "summary": current_summary,
                                    },
                                    items,
                                )
                                st.session_state["flash_message"] = (
                                    "success",
                                    f"Comparison session saved successfully. {current_summary.get('review_items', 0)} item(s) are ready for manual review.",
                                )
                                st.rerun()

                with review_tab:
                    review_candidates = current_results_df[
                        current_results_df["review_required"]
                    ].copy()
                    if review_candidates.empty:
                        st.success("The two registers are aligned. No manual comparison item was found.")
                    else:
                        choices = {}
                        for index, row in review_candidates.iterrows():
                            base_label = (
                                f"{clean_text(row['document_number'])} · "
                                f"{clean_text(row['classification'])} · "
                                f"{clean_text(row['project']) or 'No project'}"
                            )
                            label = base_label
                            counter = 2
                            while label in choices:
                                label = f"{base_label} · Entry {counter}"
                                counter += 1
                            choices[label] = index

                        selected_label = st.selectbox(
                            "Select a comparison item",
                            list(choices.keys()),
                            key="current_comparison_item",
                        )
                        selected = review_candidates.loc[choices[selected_label]]

                        st.warning(
                            f"{selected['classification']}: {selected['recommended_action']}"
                        )
                        side_by_side = comparison_side_by_side_dataframe(
                            selected["record_a"],
                            selected["record_b"],
                            register_a_label,
                            register_b_label,
                        )
                        display_table(
                            side_by_side,
                            height=520,
                            row_height=38,
                            key="current_side_by_side",
                        )

                        history_left, history_right = st.columns(2)
                        with history_left:
                            st.markdown(f"#### Revision history – {register_a_label}")
                            history_a_df = pd.DataFrame(selected["history_a"])
                            if history_a_df.empty:
                                st.info("No matching record.")
                            else:
                                display_table(
                                    history_a_df,
                                    columns=["document_number", "title", "revision", "status", "created_date", "due_date", "file_name"],
                                    height=260,
                                    key="current_history_a",
                                )
                        with history_right:
                            st.markdown(f"#### Revision history – {register_b_label}")
                            history_b_df = pd.DataFrame(selected["history_b"])
                            if history_b_df.empty:
                                st.info("No matching record.")
                            else:
                                display_table(
                                    history_b_df,
                                    columns=["document_number", "title", "revision", "status", "created_date", "due_date", "file_name"],
                                    height=260,
                                    key="current_history_b",
                                )

                        st.info(
                            "This live comparison is read-only. Save the comparison session from the Overview tab to record an approval decision and comments."
                        )

                with internal_tab:
                    if current_internal_issues_df.empty:
                        st.success("No repeated identities or unmatchable document-number rows were found inside either register.")
                    else:
                        st.warning(
                            "These findings exist inside an individual source register and should be corrected before final reconciliation."
                        )
                        display_table(
                            current_internal_issues_df,
                            rename={
                                "register": "Source Register",
                                "project": "Project",
                                "discipline": "Discipline",
                                "document_number": "Document Number",
                                "title": "Title",
                                "revision": "Revision",
                                "issue": "Issue",
                                "severity": "Priority",
                                "csv_rows": "CSV Rows",
                            },
                            height=500,
                            key="comparison_internal_issues",
                        )

                with saved_tab:
                    st.caption("Saved comparisons are also available below after either source file is removed.")

        except pd.errors.EmptyDataError:
            st.error("One of the uploaded CSV files is empty.")
        except Exception as error:
            st.error("The registers could not be compared.")
            st.code(str(error))

    st.divider()
    st.subheader("Saved comparison sessions")
    saved_comparisons_df = get_register_comparisons()

    if saved_comparisons_df.empty:
        st.info("No comparison session has been saved yet.")
    else:
        saved_choices = {}
        for _, row in saved_comparisons_df.iterrows():
            visible = (
                f"{clean_text(row['comparison_name'])} · "
                f"{clean_text(row['register_a_label'])} vs {clean_text(row['register_b_label'])} · "
                f"{clean_text(row['created_at'])}"
            )
            saved_choices[visible] = int(row["comparison_id"])

        selected_saved_label = st.selectbox(
            "Open saved comparison",
            list(saved_choices.keys()),
            key="saved_comparison_selector",
        )
        selected_comparison_id = saved_choices[selected_saved_label]
        saved_row = saved_comparisons_df[
            saved_comparisons_df["comparison_id"] == selected_comparison_id
        ].iloc[0]
        saved_items_df = get_register_comparison_items(selected_comparison_id)
        saved_label_a = clean_text(saved_row["register_a_label"])
        saved_label_b = clean_text(saved_row["register_b_label"])

        resolved_count = int(saved_items_df["review_status"].eq("Resolved").sum()) if not saved_items_df.empty else 0
        pending_count = int(saved_items_df["review_status"].isin(["Pending Review", "Correction Required", "Escalated"]).sum()) if not saved_items_df.empty else 0
        render_metric_cards(
            [
                ("Comparison items", len(saved_items_df), "All reconciled identities", ""),
                ("Pending decisions", pending_count, "Needs manual approval", "health-watch"),
                ("Resolved decisions", resolved_count, "Comments recorded", "health-good"),
                ("Prepared by", clean_text(saved_row["created_by"]), clean_text(saved_row["created_at"]), ""),
            ]
        )

        if saved_items_df.empty:
            st.info("This saved comparison contains no items.")
        else:
            saved_filter_col1, saved_filter_col2 = st.columns(2)
            with saved_filter_col1:
                saved_status_filter = st.multiselect(
                    "Review status",
                    sorted(saved_items_df["review_status"].dropna().unique().tolist()),
                    key="saved_comparison_status_filter",
                )
            with saved_filter_col2:
                saved_class_filter = st.multiselect(
                    "Comparison result",
                    sorted(saved_items_df["classification"].dropna().unique().tolist()),
                    key="saved_comparison_class_filter",
                )

            saved_filtered = saved_items_df.copy()
            if saved_status_filter:
                saved_filtered = saved_filtered[saved_filtered["review_status"].isin(saved_status_filter)]
            if saved_class_filter:
                saved_filtered = saved_filtered[saved_filtered["classification"].isin(saved_class_filter)]

            display_table(
                saved_filtered,
                columns=[
                    "project",
                    "discipline",
                    "document_number",
                    "title_a",
                    "title_b",
                    "revision_a",
                    "revision_b",
                    "classification",
                    "severity",
                    "differing_fields",
                    "review_status",
                    "review_decision",
                    "reviewer",
                    "comments",
                    "reviewed_at",
                ],
                rename={
                    "project": "Project",
                    "discipline": "Discipline",
                    "document_number": "Document Number",
                    "title_a": f"Title – {saved_label_a}",
                    "title_b": f"Title – {saved_label_b}",
                    "revision_a": f"Revision – {saved_label_a}",
                    "revision_b": f"Revision – {saved_label_b}",
                    "classification": "Comparison Result",
                    "severity": "Priority",
                    "differing_fields": "Changed Fields",
                    "review_status": "Review Status",
                    "review_decision": "Decision",
                    "reviewer": "Reviewer",
                    "comments": "Comments",
                    "reviewed_at": "Reviewed At",
                },
                height=520,
                row_height=42,
                key="saved_comparison_table",
            )

            reviewable_saved = saved_items_df[
                saved_items_df["review_required"] == 1
            ].copy()
            if not reviewable_saved.empty:
                saved_item_choices = {}
                for index, row in reviewable_saved.iterrows():
                    base = (
                        f"{clean_text(row['document_number'])} · "
                        f"{clean_text(row['classification'])} · "
                        f"{clean_text(row['review_status'])}"
                    )
                    visible = base
                    counter = 2
                    while visible in saved_item_choices:
                        visible = f"{base} · Entry {counter}"
                        counter += 1
                    saved_item_choices[visible] = index

                selected_saved_item_label = st.selectbox(
                    "Select an item for manual decision",
                    list(saved_item_choices.keys()),
                    key="saved_comparison_item_selector",
                )
                selected_saved_item = reviewable_saved.loc[
                    saved_item_choices[selected_saved_item_label]
                ]

                try:
                    saved_record_a = json.loads(clean_text(selected_saved_item["record_a_json"]) or "{}")
                    saved_record_b = json.loads(clean_text(selected_saved_item["record_b_json"]) or "{}")
                    saved_history_a = json.loads(clean_text(selected_saved_item["history_a_json"]) or "[]")
                    saved_history_b = json.loads(clean_text(selected_saved_item["history_b_json"]) or "[]")
                except json.JSONDecodeError:
                    saved_record_a, saved_record_b, saved_history_a, saved_history_b = {}, {}, [], []

                st.warning(
                    f"{clean_text(selected_saved_item['classification'])}: {clean_text(selected_saved_item['recommended_action'])}"
                )
                display_table(
                    comparison_side_by_side_dataframe(
                        saved_record_a,
                        saved_record_b,
                        saved_label_a,
                        saved_label_b,
                    ),
                    height=520,
                    row_height=38,
                    key="saved_side_by_side",
                )

                saved_history_col_a, saved_history_col_b = st.columns(2)
                with saved_history_col_a:
                    st.markdown(f"#### Revision history – {saved_label_a}")
                    if saved_history_a:
                        display_table(pd.DataFrame(saved_history_a), height=250, key="saved_history_a")
                    else:
                        st.info("No matching record.")
                with saved_history_col_b:
                    st.markdown(f"#### Revision history – {saved_label_b}")
                    if saved_history_b:
                        display_table(pd.DataFrame(saved_history_b), height=250, key="saved_history_b")
                    else:
                        st.info("No matching record.")

                with st.form("saved_comparison_review_form"):
                    decision = st.selectbox(
                        "Manual review decision",
                        COMPARISON_DECISIONS,
                    )
                    reviewer = st.text_input(
                        "Reviewer name",
                        value=clean_text(selected_saved_item.get("reviewer", "")),
                    )
                    comments = st.text_area(
                        "Mandatory approval comments",
                        value=clean_text(selected_saved_item.get("comments", "")),
                        placeholder="Explain what was compared, which register value was accepted and why.",
                    )
                    submit_review = st.form_submit_button(
                        "Save manual decision",
                        type="primary",
                        use_container_width=True,
                    )

                    if submit_review:
                        if not clean_text(reviewer):
                            st.error("Reviewer name is required.")
                        elif not clean_text(comments):
                            st.error("Approval comments are required.")
                        else:
                            update_register_comparison_item_review(
                                int(selected_saved_item["comparison_item_id"]),
                                decision,
                                reviewer,
                                comments,
                            )
                            st.session_state["flash_message"] = (
                                "success",
                                "The reconciliation decision and comments were saved.",
                            )
                            st.rerun()

            saved_export = saved_filtered.drop(
                columns=[
                    "comparison_item_id",
                    "comparison_id",
                    "item_key",
                    "record_a_json",
                    "record_b_json",
                    "history_a_json",
                    "history_b_json",
                ],
                errors="ignore",
            )
            st.download_button(
                "Download saved reconciliation with decisions",
                data=saved_export.to_csv(index=False).encode("utf-8-sig"),
                file_name="saved_master_register_reconciliation.csv",
                mime="text/csv",
                use_container_width=True,
            )



# -----------------------------
# PDF intake and metadata extraction
# -----------------------------

elif page == "PDF intake":
    render_section_header(
        "Upload PDF and extract information",
        "Choose the document language, extract suggested metadata, compare it with the PDF and approve the record only after checking every field.",
    )

    st.info(
        "The PDF is not added to the register until you select Approve and add to register. "
        "This version reads selectable text; scanned image PDFs still require manual entry."
    )

    if "pdf_intake_upload_version" not in st.session_state:
        st.session_state["pdf_intake_upload_version"] = 0

    intake_top_left, intake_top_right = st.columns([1, 2])
    with intake_top_left:
        selected_language = st.selectbox(
            "Document language",
            PDF_LANGUAGE_OPTIONS,
            key="pdf_intake_language",
            help=(
                "English, Polish and Arabic include dedicated document-label matching. "
                "Other uses general filename clues and manual review."
            ),
        )
    with intake_top_right:
        uploaded_intake_pdf = st.file_uploader(
            "Upload a PDF document",
            type=["pdf"],
            accept_multiple_files=False,
            key=f"pdf_intake_upload_{st.session_state['pdf_intake_upload_version']}",
        )

    if uploaded_intake_pdf is not None:
        intake_file_bytes = uploaded_intake_pdf.getvalue()
        intake_file_hash = hashlib.sha256(intake_file_bytes).hexdigest()
        existing_file = find_document_file_by_hash(intake_file_hash)

        previous_hash = st.session_state.get("pdf_intake_result_hash")
        previous_language = st.session_state.get("pdf_intake_result_language")
        if previous_hash != intake_file_hash or previous_language != selected_language:
            st.session_state.pop("pdf_intake_result", None)
            st.session_state["pdf_intake_result_hash"] = intake_file_hash
            st.session_state["pdf_intake_result_language"] = selected_language

        if existing_file:
            st.error(
                "This exact PDF is already stored against "
                f"{clean_text(existing_file.get('document_number', ''))} "
                f"revision {clean_text(existing_file.get('revision', '')) or 'not set'}."
            )
        elif not intake_file_bytes.startswith(b"%PDF-"):
            st.error("The selected file does not contain a valid PDF signature.")
        else:
            extract_col, cancel_col = st.columns([1, 1])
            with extract_col:
                extract_requested = st.button(
                    "Extract information",
                    type="primary",
                    use_container_width=True,
                    key="pdf_intake_extract",
                )
            with cancel_col:
                if st.button(
                    "Cancel upload",
                    use_container_width=True,
                    key="pdf_intake_cancel_before_review",
                ):
                    for state_key in [
                        "pdf_intake_result",
                        "pdf_intake_result_hash",
                        "pdf_intake_result_language",
                    ]:
                        st.session_state.pop(state_key, None)
                    st.session_state["pdf_intake_upload_version"] += 1
                    st.rerun()

            if extract_requested:
                try:
                    with st.spinner("Reading the PDF and preparing suggested metadata..."):
                        st.session_state["pdf_intake_result"] = extract_pdf_metadata(
                            intake_file_bytes,
                            uploaded_intake_pdf.name,
                            language=selected_language,
                        )
                        st.session_state["pdf_intake_result_hash"] = intake_file_hash
                        st.session_state["pdf_intake_result_language"] = selected_language
                except Exception as error:
                    st.error("The PDF could not be read.")
                    st.code(str(error))

            extraction = st.session_state.get("pdf_intake_result")

            if extraction is None:
                st.caption(
                    "Select Extract information to begin. No document record has been created."
                )
            else:
                extracted = extraction.get("metadata", {})
                extracted_sources = extraction.get("sources", {})
                extracted_confidence = extraction.get("confidence", {})

                st.success(
                    f"Read {extraction.get('pages_read', 0)} of "
                    f"{extraction.get('total_pages', 0)} page(s). "
                    "Review the PDF and suggested values side by side."
                )
                st.caption(extraction.get("language_note", ""))

                for warning in extraction.get("warnings", []):
                    st.warning(warning)

                confidence_values = [
                    extracted_confidence.get(field, "not_found")
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
                ]
                confidence_columns = st.columns(3)
                confidence_columns[0].metric(
                    "High confidence",
                    confidence_values.count("high"),
                )
                confidence_columns[1].metric(
                    "Please check",
                    confidence_values.count("check"),
                )
                confidence_columns[2].metric(
                    "Not found",
                    confidence_values.count("not_found"),
                )

                preview_column, metadata_column = st.columns([1.08, 1], gap="large")

                with preview_column:
                    st.markdown('<div class="intake-step">PDF preview</div>', unsafe_allow_html=True)
                    render_pdf_preview(
                        intake_file_bytes,
                        uploaded_intake_pdf.name,
                        height=820,
                    )
                    st.download_button(
                        "Download PDF preview",
                        data=intake_file_bytes,
                        file_name=uploaded_intake_pdf.name,
                        mime="application/pdf",
                        use_container_width=True,
                        key="pdf_intake_preview_download",
                    )
                    with st.expander("Extracted text preview", expanded=False):
                        if extraction.get("text_preview"):
                            st.text(extraction["text_preview"])
                        else:
                            st.info(
                                "No selectable text was found. Enter the metadata manually."
                            )

                with metadata_column:
                    st.markdown('<div class="intake-step">Review extracted information</div>', unsafe_allow_html=True)

                    reextract_col, reset_col = st.columns(2)
                    with reextract_col:
                        if st.button(
                            "Re-extract",
                            use_container_width=True,
                            key="pdf_intake_reextract",
                        ):
                            try:
                                with st.spinner("Re-reading the PDF..."):
                                    st.session_state["pdf_intake_result"] = extract_pdf_metadata(
                                        intake_file_bytes,
                                        uploaded_intake_pdf.name,
                                        language=selected_language,
                                    )
                                st.rerun()
                            except Exception as error:
                                st.error("The PDF could not be re-read.")
                                st.code(str(error))
                    with reset_col:
                        if st.button(
                            "Cancel",
                            use_container_width=True,
                            key="pdf_intake_cancel_review",
                        ):
                            for state_key in [
                                "pdf_intake_result",
                                "pdf_intake_result_hash",
                                "pdf_intake_result_language",
                            ]:
                                st.session_state.pop(state_key, None)
                            st.session_state["pdf_intake_upload_version"] += 1
                            st.rerun()

                    intake_discipline_options, intake_discipline_index = (
                        select_options_with_current(
                            DISCIPLINE_OPTIONS,
                            extracted.get("discipline", ""),
                        )
                    )
                    intake_status_options, intake_status_index = (
                        select_options_with_current(
                            STATUS_OPTIONS,
                            extracted.get("status", ""),
                        )
                    )

                    with st.form("pdf_intake_review_form", border=True):
                        st.markdown("#### Essential information")

                        render_confidence_label(
                            "Document Number",
                            extracted_confidence.get("document_number", "not_found"),
                            extracted_sources.get("document_number", ""),
                        )
                        intake_document_number = st.text_input(
                            "Document Number *",
                            value=clean_text(extracted.get("document_number", "")),
                            label_visibility="collapsed",
                        )

                        render_confidence_label(
                            "Document Title",
                            extracted_confidence.get("title", "not_found"),
                            extracted_sources.get("title", ""),
                        )
                        intake_title = st.text_input(
                            "Document Title *",
                            value=clean_text(extracted.get("title", "")),
                            label_visibility="collapsed",
                        )

                        essential_left, essential_right = st.columns(2)
                        with essential_left:
                            render_confidence_label(
                                "Revision",
                                extracted_confidence.get("revision", "not_found"),
                                extracted_sources.get("revision", ""),
                            )
                            intake_revision = st.text_input(
                                "Revision *",
                                value=clean_text(extracted.get("revision", "")),
                                label_visibility="collapsed",
                            )

                            render_confidence_label(
                                "Discipline",
                                extracted_confidence.get("discipline", "not_found"),
                                extracted_sources.get("discipline", ""),
                            )
                            intake_discipline = st.selectbox(
                                "Discipline *",
                                intake_discipline_options,
                                index=intake_discipline_index,
                                label_visibility="collapsed",
                            )

                            render_confidence_label(
                                "Official Status",
                                extracted_confidence.get("status", "not_found"),
                                extracted_sources.get("status", ""),
                            )
                            intake_status = st.selectbox(
                                "Official Status *",
                                intake_status_options,
                                index=intake_status_index,
                                label_visibility="collapsed",
                            )

                        with essential_right:
                            render_confidence_label(
                                "Project",
                                extracted_confidence.get("project", "not_found"),
                                extracted_sources.get("project", ""),
                            )
                            intake_project = st.text_input(
                                "Project *",
                                value=clean_text(extracted.get("project", "")),
                                label_visibility="collapsed",
                            )

                            render_confidence_label(
                                "Owner",
                                extracted_confidence.get("owner", "not_found"),
                                extracted_sources.get("owner", ""),
                            )
                            intake_owner = st.text_input(
                                "Owner *",
                                value=clean_text(extracted.get("owner", "")),
                                label_visibility="collapsed",
                            )

                            render_confidence_label(
                                "Originator",
                                extracted_confidence.get("originator", "not_found"),
                                extracted_sources.get("originator", ""),
                            )
                            intake_originator = st.text_input(
                                "Originator",
                                value=clean_text(extracted.get("originator", "")),
                                label_visibility="collapsed",
                            )

                        st.markdown("#### Additional information")
                        additional_left, additional_right = st.columns(2)

                        with additional_left:
                            render_confidence_label(
                                "Date Received",
                                extracted_confidence.get("created_date", "not_found"),
                                extracted_sources.get("created_date", ""),
                            )
                            intake_created_date = st.date_input(
                                "Date Received",
                                value=optional_date_value(
                                    extracted.get("created_date", "")
                                ),
                                label_visibility="collapsed",
                            )

                            intake_file_name = st.text_input(
                                "File Name",
                                value=uploaded_intake_pdf.name,
                            )

                        with additional_right:
                            intake_due_date = st.date_input(
                                "Due Date (optional)",
                                value=optional_date_value(
                                    extracted.get("due_date", "")
                                ),
                            )
                            intake_notes = st.text_area(
                                "Notes",
                                value=clean_text(extracted.get("notes", "")),
                                height=100,
                            )

                        allow_intake_duplicate = st.checkbox(
                            "Allow a possible duplicate to be saved for comparison",
                            value=False,
                            help=(
                                "Use this only when the record genuinely needs comparison "
                                "with an existing document."
                            ),
                        )
                        confirm_intake_review = st.checkbox(
                            "I reviewed the PDF and confirm that the corrected information is accurate."
                        )

                        save_intake = st.form_submit_button(
                            "Approve and add to register",
                            type="primary",
                            use_container_width=True,
                        )

                    if save_intake:
                        intake_document = {
                            "document_number": clean_text(intake_document_number),
                            "title": clean_text(intake_title),
                            "project": clean_text(intake_project),
                            "discipline": clean_text(intake_discipline),
                            "revision": clean_text(intake_revision),
                            "status": clean_text(intake_status),
                            "owner": clean_text(intake_owner),
                            "originator": clean_text(intake_originator),
                            "created_date": (
                                str(intake_created_date)
                                if intake_created_date
                                else ""
                            ),
                            "due_date": (
                                str(intake_due_date)
                                if intake_due_date
                                else ""
                            ),
                            "file_name": clean_text(intake_file_name),
                            "notes": clean_text(intake_notes),
                        }

                        missing_required = [
                            field
                            for field in REQUIRED_FIELDS
                            if not intake_document[field]
                        ]

                        if not confirm_intake_review:
                            st.error(
                                "Confirm that you reviewed the PDF and corrected information before approval."
                            )
                        elif missing_required:
                            st.error(
                                "Complete all required fields: "
                                + ", ".join(
                                    REGISTER_FIELD_LABELS.get(field, field)
                                    for field in missing_required
                                )
                            )
                        elif (
                            intake_created_date is not None
                            and intake_due_date is not None
                            and intake_created_date > intake_due_date
                        ):
                            st.error(
                                "When a Due Date is provided, Date Received cannot be later than it."
                            )
                        else:
                            relationship = classify_incoming_document(
                                intake_document,
                                documents_df,
                            )
                            possible_duplicate = relationship["type"] in {
                                "exact_duplicate",
                                "similar_document_number",
                            }
                            exact_same_metadata = (
                                make_record_signature(intake_document)
                                in existing_record_signatures(documents_df)
                            )

                            if exact_same_metadata:
                                st.error(
                                    "The same document record is already stored. "
                                    "No additional copy was created."
                                )
                            elif (
                                relationship["type"] == "exact_duplicate"
                                and not allow_intake_duplicate
                            ):
                                st.error(
                                    "The same document number, title and revision already exist. "
                                    "Compare the records before saving another copy."
                                )
                            elif (
                                relationship["type"] == "similar_document_number"
                                and not allow_intake_duplicate
                            ):
                                st.error(
                                    "The same document number exists with a different title. "
                                    "Check whether this is a correction or a separate document."
                                )
                            else:
                                target_path = build_pdf_storage_path(
                                    intake_document,
                                    uploaded_intake_pdf.name,
                                    intake_file_hash,
                                )

                                try:
                                    target_path.write_bytes(intake_file_bytes)
                                    intake_document_id = add_document(intake_document)
                                    add_document_file(
                                        {
                                            "document_id": intake_document_id,
                                            "project": intake_document["project"],
                                            "discipline": intake_document["discipline"],
                                            "original_file_name": uploaded_intake_pdf.name,
                                            "stored_file_name": target_path.name,
                                            "stored_path": str(target_path),
                                            "mime_type": "application/pdf",
                                            "file_size": len(intake_file_bytes),
                                            "sha256": intake_file_hash,
                                        }
                                    )
                                except Exception as error:
                                    if target_path.exists():
                                        target_path.unlink()
                                    st.error(
                                        "The record or PDF could not be saved. "
                                        "No PDF file was kept in the library."
                                    )
                                    st.code(str(error))
                                else:
                                    if relationship["type"] == "new_revision":
                                        success_message = (
                                            f"Revision {intake_document['revision']} was approved "
                                            "and added as a new revision with its controlled PDF."
                                        )
                                    elif possible_duplicate:
                                        success_message = (
                                            "The document was added and marked for comparison."
                                        )
                                    else:
                                        success_message = (
                                            "The reviewed document and controlled PDF were added to the register."
                                        )

                                    for state_key in [
                                        "pdf_intake_result",
                                        "pdf_intake_result_hash",
                                        "pdf_intake_result_language",
                                    ]:
                                        st.session_state.pop(state_key, None)
                                    st.session_state["pdf_intake_upload_version"] += 1
                                    st.session_state["flash_message"] = (
                                        "success",
                                        success_message,
                                    )
                                    st.rerun()


# -----------------------------
# Documents
# -----------------------------

elif page == "Documents":
    render_section_header(
        "Documents",
        "Manage document metadata, official status, workflow status, PDFs, revisions, archive state and audit history from one place.",
    )

    source_documents = all_documents_df.copy()

    if source_documents.empty:
        st.info(
            "No documents have been added yet. Use Add document to enter a record "
            "manually, import a register or extract information from a PDF."
        )
    else:
        latest_ids = latest_revision_ids(source_documents)
        source_documents["_is_latest"] = source_documents["id"].map(
            lambda value: int(value) in latest_ids
        )
        source_documents["record_state"] = source_documents["is_archived"].map(
            lambda value: "Archived" if int(value or 0) else "Active"
        )
        source_documents["workflow_status"] = source_documents.apply(
            lambda row: workflow_status_for_document(row, open_review_cases_df),
            axis=1,
        )
        source_documents["review_reason"] = source_documents["id"].map(
            lambda value: "; ".join(
                sorted(
                    {
                        attention_problem_label(issue)
                        for issue in review_cases_for_document(
                            int(value), open_review_cases_df
                        ).get("issue_type", pd.Series(dtype=str)).tolist()
                    }
                )
            )
        )

        def clear_documents_filters():
            st.session_state["documents_search"] = ""
            st.session_state["documents_projects"] = []
            st.session_state["documents_disciplines"] = []
            st.session_state["documents_official_statuses"] = []
            st.session_state["documents_workflow_statuses"] = []

        project_values = sorted(
            value
            for value in source_documents["project"].dropna().astype(str).unique()
            if clean_text(value)
        )
        discipline_values = sorted(
            value
            for value in source_documents["discipline"].dropna().astype(str).unique()
            if clean_text(value)
        )
        official_status_values = sorted(
            value
            for value in source_documents["status"].dropna().astype(str).unique()
            if clean_text(value)
        )
        workflow_status_values = [
            value
            for value in WORKFLOW_STATUS_OPTIONS
            if value in set(source_documents["workflow_status"].astype(str))
        ]

        with st.container(border=True):
            filter_header_left, filter_header_right = st.columns([5, 1])
            with filter_header_left:
                st.markdown("### Find documents")
                st.caption(
                    "The default view shows active documents and only the latest revision."
                )
            with filter_header_right:
                st.button(
                    "Clear filters",
                    on_click=clear_documents_filters,
                    use_container_width=True,
                    key="clear_documents_filters",
                )

            state_col, revision_col = st.columns(2)
            with state_col:
                record_state_filter = st.radio(
                    "Record state",
                    ["Active", "Archived", "All"],
                    horizontal=True,
                    key="documents_record_state",
                )
            with revision_col:
                revision_view = st.radio(
                    "Revision view",
                    ["Latest revisions only", "All revisions", "Previous revisions"],
                    horizontal=True,
                    key="documents_revision_view",
                )

            search_text = st.text_input(
                "Search by document number or title",
                placeholder="Enter a document number or document title",
                key="documents_search",
            )

            filter_one, filter_two, filter_three, filter_four = st.columns(4)
            with filter_one:
                selected_projects = st.multiselect(
                    "Project",
                    project_values,
                    placeholder="All projects",
                    key="documents_projects",
                )
            with filter_two:
                selected_disciplines = st.multiselect(
                    "Discipline",
                    discipline_values,
                    placeholder="All disciplines",
                    key="documents_disciplines",
                )
            with filter_three:
                selected_official_statuses = st.multiselect(
                    "Official document status",
                    official_status_values,
                    placeholder="All statuses",
                    key="documents_official_statuses",
                )
            with filter_four:
                selected_workflow_statuses = st.multiselect(
                    "App workflow status",
                    workflow_status_values,
                    placeholder="All workflow states",
                    key="documents_workflow_statuses",
                )

        filtered_documents = source_documents.copy()

        if record_state_filter != "All":
            filtered_documents = filtered_documents[
                filtered_documents["record_state"] == record_state_filter
            ]

        if revision_view == "Latest revisions only":
            filtered_documents = filtered_documents[
                filtered_documents["_is_latest"]
            ]
        elif revision_view == "Previous revisions":
            filtered_documents = filtered_documents[
                ~filtered_documents["_is_latest"]
            ]

        if search_text:
            search_key = normalized_key(search_text)
            searchable = (
                filtered_documents["document_number"].fillna("").astype(str)
                + " "
                + filtered_documents["title"].fillna("").astype(str)
            ).str.casefold()
            filtered_documents = filtered_documents[
                searchable.str.contains(re.escape(search_key), na=False)
            ]

        if selected_projects:
            filtered_documents = filtered_documents[
                filtered_documents["project"].isin(selected_projects)
            ]
        if selected_disciplines:
            filtered_documents = filtered_documents[
                filtered_documents["discipline"].isin(selected_disciplines)
            ]
        if selected_official_statuses:
            filtered_documents = filtered_documents[
                filtered_documents["status"].isin(selected_official_statuses)
            ]
        if selected_workflow_statuses:
            filtered_documents = filtered_documents[
                filtered_documents["workflow_status"].isin(selected_workflow_statuses)
            ]

        filtered_documents = filtered_documents.sort_values(
            ["project", "discipline", "document_number", "_is_latest", "revision", "id"],
            ascending=[True, True, True, False, False, False],
        )

        attention_count = int(
            filtered_documents["workflow_status"].isin(
                ["Needs checking", "Possible duplicate"]
            ).sum()
        )
        render_metric_cards(
            [
                ("Documents shown", len(filtered_documents), "Current filtered view", ""),
                (
                    "Latest revisions",
                    int(filtered_documents["_is_latest"].sum()),
                    "Latest in each document family",
                    "",
                ),
                (
                    "Need attention",
                    attention_count,
                    "Needs checking or possible duplicate",
                    "health-watch" if attention_count else "health-good",
                ),
                (
                    "PDF files",
                    int(
                        pd.to_numeric(
                            filtered_documents.get("pdf_count", 0),
                            errors="coerce",
                        ).fillna(0).sum()
                    ),
                    "Attached controlled files",
                    "",
                ),
                (
                    "Archived",
                    int((filtered_documents["record_state"] == "Archived").sum()),
                    "Visible in this view",
                    "",
                ),
            ]
        )

        st.subheader("Controlled documents")
        if filtered_documents.empty:
            st.info("No documents match the selected filters.")
        else:
            display_table(
                filtered_documents,
                columns=[
                    "document_number",
                    "title",
                    "revision",
                    "status",
                    "workflow_status",
                    "discipline",
                    "project",
                    "created_date",
                    "originator",
                    "pdf_count",
                    "record_state",
                    "review_reason",
                ],
                rename={
                    "document_number": "Document Number",
                    "title": "Title",
                    "revision": "Revision",
                    "status": "Official Status",
                    "workflow_status": "Workflow Status",
                    "discipline": "Discipline",
                    "project": "Project",
                    "created_date": "Date Received",
                    "originator": "Originator",
                    "pdf_count": "PDF Files",
                    "record_state": "Record State",
                    "review_reason": "Why It Needs Attention",
                },
                height=430,
                row_height=38,
                column_config={
                    "Document Number": st.column_config.TextColumn(width="medium"),
                    "Title": st.column_config.TextColumn(width="large"),
                    "Revision": st.column_config.TextColumn(width="small"),
                    "Official Status": st.column_config.TextColumn(width="medium"),
                    "Workflow Status": st.column_config.TextColumn(width="medium"),
                    "Why It Needs Attention": st.column_config.TextColumn(width="large"),
                },
                key="documents_register_table",
            )

            st.download_button(
                "Export current view",
                data=filtered_documents.drop(
                    columns=["id", "_is_latest"], errors="ignore"
                ).to_csv(index=False).encode("utf-8-sig"),
                file_name="document_register_export.csv",
                mime="text/csv",
                key="documents_export",
            )

            st.divider()
            st.subheader("Open one document")
            record_choices = build_record_choice_map(filtered_documents)
            selected_record_label = st.selectbox(
                "Select a document",
                list(record_choices.keys()),
                key="documents_selected_record",
            )
            selected_record_id = record_choices[selected_record_label]
            selected_record = source_documents[
                source_documents["id"] == selected_record_id
            ].iloc[0]
            selected_cases = review_cases_for_document(
                selected_record_id, open_review_cases_df
            )
            selected_files = get_document_files(document_id=int(selected_record_id))

            heading_left, heading_right = st.columns([3, 1])
            with heading_left:
                st.markdown(
                    f"## {clean_text(selected_record.get('document_number', '')) or 'Document number not set'}"
                )
                st.write(f"**{clean_text(selected_record.get('title', '')) or 'Untitled document'}**")
            with heading_right:
                workflow_value = workflow_status_for_document(
                    selected_record, open_review_cases_df
                )
                if workflow_value == "Ready":
                    st.success("Ready")
                elif workflow_value == "Archived":
                    st.info("Archived")
                elif workflow_value == "Possible duplicate":
                    st.error("Possible duplicate")
                else:
                    st.warning("Needs checking")

            detail_columns = st.columns(4)
            detail_columns[0].metric(
                "Revision",
                clean_text(selected_record.get("revision", "")) or "Not set",
            )
            detail_columns[1].metric(
                "Official status",
                clean_text(selected_record.get("status", "")) or "Not set",
            )
            detail_columns[2].metric(
                "Discipline",
                clean_text(selected_record.get("discipline", "")) or "Not set",
            )
            detail_columns[3].metric(
                "PDF files",
                int(selected_record.get("pdf_count", 0) or 0),
            )

            if selected_cases.empty:
                st.success("This document has no open review issues.")
            else:
                st.warning("This document needs attention.")
                display_table(
                    attention_table(selected_cases),
                    height=220,
                    key="selected_document_attention",
                )
                if st.button(
                    "Open Documents needing attention",
                    key="open_attention_from_documents",
                    type="primary",
                ):
                    st.session_state["active_page"] = "Documents needing attention"
                    st.rerun()

            files_tab, edit_tab, revisions_tab, audit_tab, archive_tab = st.tabs(
                [
                    "PDF files",
                    "Edit metadata",
                    "Revision history",
                    "Audit history",
                    "Archive",
                ]
            )

            with files_tab:
                st.markdown("#### Attached PDF")
                render_attached_files(
                    selected_files,
                    key_prefix=f"documents_{selected_record_id}",
                    allow_delete=False,
                )

                if not selected_files.empty and hasattr(st, "pdf"):
                    preview_row = selected_files.iloc[0]
                    preview_path = Path(clean_text(preview_row.get("stored_path", "")))
                    if preview_path.exists():
                        with st.expander("Open PDF preview", expanded=False):
                            st.pdf(preview_path.read_bytes())

                if int(selected_record.get("is_archived", 0) or 0):
                    st.info("Archived records cannot receive new PDF files.")
                else:
                    st.markdown("#### Attach another PDF")
                    uploaded_pdf = st.file_uploader(
                        "Choose the controlled PDF",
                        type=["pdf"],
                        accept_multiple_files=False,
                        key=f"documents_pdf_upload_{selected_record_id}",
                    )

                    if uploaded_pdf is not None:
                        inspection = inspect_pdf_upload(uploaded_pdf, selected_record)

                        if inspection["duplicate_file"]:
                            duplicate = inspection["duplicate_file"]
                            st.error(
                                "This is the same file already stored against "
                                f"{duplicate['document_number']} revision "
                                f"{duplicate['revision'] or 'not set'}."
                            )
                        elif not inspection["valid_header"]:
                            st.error("The uploaded file is not a valid PDF.")
                        else:
                            naming_matches = (
                                inspection["document_number_match"]
                                and inspection["revision_match"]
                            )
                            mismatch_confirmed = naming_matches
                            if not naming_matches:
                                st.warning(
                                    "The filename does not fully match the selected "
                                    "document number and revision."
                                )
                                mismatch_confirmed = st.checkbox(
                                    "I checked the file and confirm it belongs to this document.",
                                    key=f"documents_mismatch_{selected_record_id}",
                                )

                            if st.button(
                                "Add PDF",
                                type="primary",
                                use_container_width=True,
                                key=f"documents_save_pdf_{selected_record_id}",
                            ):
                                if not mismatch_confirmed:
                                    st.error("Confirm the filename mismatch before saving.")
                                else:
                                    target_path = build_pdf_storage_path(
                                        selected_record,
                                        inspection["file_name"],
                                        inspection["file_hash"],
                                    )
                                    target_path.write_bytes(inspection["file_bytes"])
                                    try:
                                        add_document_file(
                                            {
                                                "document_id": int(selected_record_id),
                                                "project": clean_text(
                                                    selected_record.get("project", "")
                                                ),
                                                "discipline": clean_text(
                                                    selected_record.get("discipline", "")
                                                ),
                                                "original_file_name": inspection["file_name"],
                                                "stored_file_name": target_path.name,
                                                "stored_path": str(target_path),
                                                "mime_type": "application/pdf",
                                                "file_size": inspection["file_size"],
                                                "sha256": inspection["file_hash"],
                                            }
                                        )
                                    except Exception:
                                        if target_path.exists():
                                            target_path.unlink()
                                        raise

                                    st.session_state["flash_message"] = (
                                        "success",
                                        "The PDF was attached to the document.",
                                    )
                                    st.rerun()

            with edit_tab:
                discipline_options, discipline_index = select_options_with_current(
                    DISCIPLINE_OPTIONS, selected_record.get("discipline", "")
                )
                status_options, status_index = select_options_with_current(
                    STATUS_OPTIONS, selected_record.get("status", "")
                )

                with st.form(f"documents_edit_{selected_record_id}", border=True):
                    edit_left, edit_right = st.columns(2)
                    with edit_left:
                        edit_document_number = st.text_input(
                            "Document Number *",
                            value=clean_text(selected_record.get("document_number", "")),
                        )
                        edit_title = st.text_input(
                            "Document Title *",
                            value=clean_text(selected_record.get("title", "")),
                        )
                        edit_revision = st.text_input(
                            "Revision *",
                            value=clean_text(selected_record.get("revision", "")),
                        )
                        edit_status = st.selectbox(
                            "Official document status *",
                            status_options,
                            index=status_index,
                        )
                        edit_discipline = st.selectbox(
                            "Discipline *",
                            discipline_options,
                            index=discipline_index,
                        )
                        edit_project = st.text_input(
                            "Project *",
                            value=clean_text(selected_record.get("project", "")),
                        )

                    with edit_right:
                        edit_originator = st.text_input(
                            "Originator",
                            value=clean_text(selected_record.get("originator", "")),
                        )
                        edit_date_received = st.date_input(
                            "Date received",
                            value=optional_date_value(
                                selected_record.get("created_date", "")
                            ),
                        )
                        edit_owner = st.text_input(
                            "Owner",
                            value=clean_text(selected_record.get("owner", "")),
                        )
                        edit_file_name = st.text_input(
                            "File Name",
                            value=clean_text(selected_record.get("file_name", "")),
                        )
                        edit_notes = st.text_area(
                            "Notes",
                            value=clean_text(selected_record.get("notes", "")),
                            height=110,
                        )

                    edit_reviewer = st.text_input(
                        "Updated by *",
                        placeholder="Document controller or reviewer name",
                    )
                    edit_comments = st.text_area(
                        "Reason for change *",
                        placeholder="Explain what was changed and why.",
                    )
                    edit_confirmed = st.checkbox(
                        "I checked the document information before saving."
                    )
                    edit_submitted = st.form_submit_button(
                        "Save changes",
                        type="primary",
                        use_container_width=True,
                    )

                if edit_submitted:
                    essential_values = {
                        "document_number": clean_text(edit_document_number),
                        "title": clean_text(edit_title),
                        "revision": clean_text(edit_revision),
                        "status": clean_text(edit_status),
                        "discipline": clean_text(edit_discipline),
                        "project": clean_text(edit_project),
                    }
                    missing_essential = [
                        label
                        for label, value in essential_values.items()
                        if not value
                    ]
                    if not edit_confirmed:
                        st.error("Confirm that you checked the information.")
                    elif missing_essential:
                        st.error(
                            "Complete the essential fields: "
                            + ", ".join(
                                value.replace("_", " ").title()
                                for value in missing_essential
                            )
                        )
                    elif not clean_text(edit_reviewer) or not clean_text(edit_comments):
                        st.error("Updated by and Reason for change are required.")
                    else:
                        updates = {
                            **essential_values,
                            "owner": clean_text(edit_owner),
                            "originator": clean_text(edit_originator),
                            "created_date": str(edit_date_received) if edit_date_received else "",
                            "due_date": clean_text(selected_record.get("due_date", "")),
                            "file_name": clean_text(edit_file_name),
                            "notes": clean_text(edit_notes),
                        }
                        changed = update_document_details(
                            selected_record_id,
                            updates,
                            clean_text(edit_reviewer),
                            clean_text(edit_comments),
                        )
                        st.session_state["flash_message"] = (
                            "success" if changed else "info",
                            "Document metadata updated."
                            if changed
                            else "No metadata values changed.",
                        )
                        st.rerun()

            with revisions_tab:
                family_key = revision_family_key(selected_record)
                family_rows = source_documents[
                    source_documents.apply(revision_family_key, axis=1) == family_key
                ].copy()
                family_rows = sort_revision_history(family_rows)
                if family_rows.empty:
                    st.info("No revision history is available.")
                else:
                    display_table(
                        family_rows,
                        columns=[
                            "revision_role",
                            "revision",
                            "status",
                            "created_date",
                            "created_at",
                            "record_state",
                            "pdf_count",
                            "notes",
                        ],
                        rename={
                            "revision_role": "Revision Role",
                            "revision": "Revision",
                            "status": "Official Status",
                            "created_date": "Date Received",
                            "created_at": "Registered Date",
                            "record_state": "Record State",
                            "pdf_count": "PDF Files",
                            "notes": "Notes",
                        },
                        height=300,
                    )

            with audit_tab:
                audit_history = get_audit_log()
                if audit_history.empty:
                    st.info("No audit events have been recorded.")
                else:
                    if "document_id" in audit_history.columns:
                        audit_history = audit_history[
                            audit_history["document_id"] == selected_record_id
                        ]
                    elif "record_id" in audit_history.columns:
                        audit_history = audit_history[
                            audit_history["record_id"] == selected_record_id
                        ]
                    elif "document_number" in audit_history.columns:
                        audit_history = audit_history[
                            audit_history["document_number"].map(normalized_key)
                            == normalized_key(
                                selected_record.get("document_number", "")
                            )
                        ]

                    if audit_history.empty:
                        st.info("No audit events are linked to this document.")
                    else:
                        display_table(
                            audit_history,
                            rename={
                                "event_type": "Event",
                                "document_number": "Document Number",
                                "created_at": "Event Date",
                            },
                            height=300,
                        )

            with archive_tab:
                if int(selected_record.get("is_archived", 0) or 0):
                    st.info(
                        "This record is archived. It remains available for audit and revision history."
                    )
                    with st.form(f"restore_document_{selected_record_id}"):
                        restore_reviewer = st.text_input("Restored by *")
                        restore_comments = st.text_area("Reason for restoration *")
                        restore_submit = st.form_submit_button(
                            "Restore document",
                            type="primary",
                            use_container_width=True,
                        )
                    if restore_submit:
                        if not clean_text(restore_reviewer) or not clean_text(restore_comments):
                            st.error("Restored by and Reason for restoration are required.")
                        else:
                            restore_document(
                                selected_record_id,
                                clean_text(restore_reviewer),
                                clean_text(restore_comments),
                            )
                            st.session_state["flash_message"] = (
                                "success",
                                "The document was restored to the active register.",
                            )
                            st.rerun()
                else:
                    st.warning(
                        "Archiving removes the record from the default active view, "
                        "but keeps its metadata, PDFs and history."
                    )
                    with st.form(f"archive_document_{selected_record_id}"):
                        archive_reviewer = st.text_input("Archived by *")
                        archive_reason = st.text_area("Reason for archiving *")
                        archive_confirmed = st.checkbox(
                            "I understand the document will remain accessible in Archived records."
                        )
                        archive_submit = st.form_submit_button(
                            "Archive document",
                            use_container_width=True,
                        )
                    if archive_submit:
                        if not archive_confirmed:
                            st.error("Confirm that you want to archive this record.")
                        elif not clean_text(archive_reviewer) or not clean_text(archive_reason):
                            st.error("Archived by and Reason for archiving are required.")
                        else:
                            archive_documents(
                                [selected_record_id],
                                clean_text(archive_reviewer),
                                clean_text(archive_reason),
                            )
                            st.session_state["flash_message"] = (
                                "success",
                                "The document was archived and remains available in history.",
                            )
                            st.rerun()


# -----------------------------
# Documents needing attention
# -----------------------------

elif page == "Documents needing attention":
    render_section_header(
        "Documents needing attention",
        "Review clear document problems in one place. Internal system IDs and technical review logic remain hidden.",
    )

    attention_cases = open_review_cases_df.copy()

    if attention_cases.empty:
        st.success("No documents currently need attention.")
    else:
        priority_order = {"Critical": 0, "Warning": 1, "Review": 2}
        attention_cases["_priority_order"] = (
            attention_cases["severity"].map(priority_order).fillna(9)
        )
        attention_cases = attention_cases.sort_values(
            ["_priority_order", "project", "document_number", "revision"]
        ).drop(columns="_priority_order")

        metric_columns = st.columns(4)
        metric_columns[0].metric(
            "Need attention",
            len(attention_cases),
        )
        metric_columns[1].metric(
            "Possible duplicates",
            int(
                attention_cases["issue_type"]
                .map(normalized_key)
                .eq("exact duplicate")
                .sum()
            ),
        )
        metric_columns[2].metric(
            "Missing information",
            int(
                attention_cases["issue_type"]
                .map(normalized_key)
                .eq("missing metadata")
                .sum()
            ),
        )
        metric_columns[3].metric(
            "Under review",
            int(attention_cases["status"].eq("Under Review").sum()),
        )

        filter_one, filter_two, filter_three = st.columns(3)
        with filter_one:
            selected_priorities = st.multiselect(
                "Priority",
                sorted(attention_cases["severity"].dropna().astype(str).unique()),
            )
        with filter_two:
            selected_problems = st.multiselect(
                "Problem",
                sorted(
                    {
                        attention_problem_label(value)
                        for value in attention_cases["issue_type"].tolist()
                    }
                ),
            )
        with filter_three:
            selected_projects = st.multiselect(
                "Project",
                sorted(
                    value
                    for value in attention_cases["project"].dropna().astype(str).unique()
                    if clean_text(value)
                ),
            )

        filtered_attention = attention_cases.copy()
        if selected_priorities:
            filtered_attention = filtered_attention[
                filtered_attention["severity"].isin(selected_priorities)
            ]
        if selected_problems:
            filtered_attention = filtered_attention[
                filtered_attention["issue_type"].map(attention_problem_label).isin(
                    selected_problems
                )
            ]
        if selected_projects:
            filtered_attention = filtered_attention[
                filtered_attention["project"].isin(selected_projects)
            ]

        st.subheader("Actions required")
        display_table(
            attention_table(filtered_attention),
            columns=[
                "Priority",
                "Problem",
                "Document",
                "Title",
                "Project",
                "Explanation",
                "Next action",
                "Review status",
            ],
            height=390,
            row_height=42,
            column_config={
                "Priority": st.column_config.TextColumn(width="small"),
                "Problem": st.column_config.TextColumn(width="medium"),
                "Document": st.column_config.TextColumn(width="medium"),
                "Title": st.column_config.TextColumn(width="large"),
                "Explanation": st.column_config.TextColumn(width="large"),
                "Next action": st.column_config.TextColumn(width="large"),
            },
            key="attention_table",
        )

        if filtered_attention.empty:
            st.info("No documents match the selected filters.")
        else:
            st.divider()
            st.subheader("Review one item")
            case_choices = build_review_case_choice_map(filtered_attention)
            selected_case_label = st.selectbox(
                "Select a document issue",
                list(case_choices.keys()),
            )
            selected_case_id = case_choices[selected_case_label]
            case_row = attention_cases[
                attention_cases["id"] == selected_case_id
            ].iloc[0]
            related_ids = decode_related_ids(case_row.get("related_document_ids", ""))
            case_documents = all_documents_df[
                all_documents_df["id"].isin(related_ids)
            ].copy()

            st.markdown(
                f"### {attention_problem_label(case_row.get('issue_type', ''))}"
            )
            st.write(
                f"**Document:** {clean_text(case_row.get('document_number', '')) or 'Not set'}"
                + (
                    f" Rev {clean_text(case_row.get('revision', ''))}"
                    if clean_text(case_row.get("revision", ""))
                    else ""
                )
            )
            st.write(
                f"**What was found:** {clean_text(case_row.get('issue_summary', ''))}"
            )
            st.write(
                f"**What to do:** {attention_action(case_row.get('issue_type', ''))}"
            )

            if not case_documents.empty:
                display_table(
                    case_documents,
                    columns=[
                        "document_number",
                        "title",
                        "revision",
                        "status",
                        "project",
                        "discipline",
                        "originator",
                        "created_date",
                        "pdf_count",
                        "is_archived",
                    ],
                    rename={
                        "document_number": "Document Number",
                        "revision": "Revision",
                        "status": "Official Status",
                        "created_date": "Date Received",
                        "pdf_count": "PDF Files",
                        "is_archived": "Archived",
                    },
                    height=230,
                )

                with st.expander("Open related PDFs", expanded=False):
                    for position, (_, document_row) in enumerate(
                        case_documents.iterrows(), start=1
                    ):
                        st.markdown(
                            f"**{clean_text(document_row.get('document_number', ''))} "
                            f"Rev {clean_text(document_row.get('revision', '')) or 'Not set'}**"
                        )
                        files = get_document_files(document_id=int(document_row["id"]))
                        render_attached_files(
                            files,
                            key_prefix=f"attention_{selected_case_id}_{position}",
                            allow_delete=False,
                        )

                with st.expander("Correct metadata", expanded=False):
                    correction_choices = build_record_choice_map(case_documents)
                    correction_label = st.selectbox(
                        "Record to correct",
                        list(correction_choices.keys()),
                        key=f"attention_correction_record_{selected_case_id}",
                    )
                    correction_id = correction_choices[correction_label]
                    correction_row = case_documents[
                        case_documents["id"] == correction_id
                    ].iloc[0]
                    discipline_options, discipline_index = select_options_with_current(
                        DISCIPLINE_OPTIONS, correction_row.get("discipline", "")
                    )
                    status_options, status_index = select_options_with_current(
                        STATUS_OPTIONS, correction_row.get("status", "")
                    )

                    with st.form(f"attention_correction_{selected_case_id}_{correction_id}"):
                        left, right = st.columns(2)
                        with left:
                            corrected_number = st.text_input(
                                "Document Number *",
                                value=clean_text(correction_row.get("document_number", "")),
                            )
                            corrected_title = st.text_input(
                                "Document Title *",
                                value=clean_text(correction_row.get("title", "")),
                            )
                            corrected_revision = st.text_input(
                                "Revision *",
                                value=clean_text(correction_row.get("revision", "")),
                            )
                            corrected_status = st.selectbox(
                                "Official document status *",
                                status_options,
                                index=status_index,
                            )
                        with right:
                            corrected_project = st.text_input(
                                "Project *",
                                value=clean_text(correction_row.get("project", "")),
                            )
                            corrected_discipline = st.selectbox(
                                "Discipline *",
                                discipline_options,
                                index=discipline_index,
                            )
                            corrected_originator = st.text_input(
                                "Originator",
                                value=clean_text(correction_row.get("originator", "")),
                            )
                            corrected_received = st.date_input(
                                "Date received",
                                value=optional_date_value(
                                    correction_row.get("created_date", "")
                                ),
                            )

                        corrected_owner = st.text_input(
                            "Owner",
                            value=clean_text(correction_row.get("owner", "")),
                        )
                        corrected_notes = st.text_area(
                            "Notes",
                            value=clean_text(correction_row.get("notes", "")),
                        )
                        correction_reviewer = st.text_input("Corrected by *")
                        correction_comments = st.text_area("Correction reason *")
                        correction_submit = st.form_submit_button(
                            "Correct document",
                            type="primary",
                            use_container_width=True,
                        )

                    if correction_submit:
                        required_values = [
                            corrected_number,
                            corrected_title,
                            corrected_revision,
                            corrected_status,
                            corrected_project,
                            corrected_discipline,
                        ]
                        if not all(clean_text(value) for value in required_values):
                            st.error("Complete all essential document information.")
                        elif not clean_text(correction_reviewer) or not clean_text(correction_comments):
                            st.error("Corrected by and Correction reason are required.")
                        else:
                            updates = {
                                "document_number": clean_text(corrected_number),
                                "title": clean_text(corrected_title),
                                "revision": clean_text(corrected_revision),
                                "status": clean_text(corrected_status),
                                "project": clean_text(corrected_project),
                                "discipline": clean_text(corrected_discipline),
                                "originator": clean_text(corrected_originator),
                                "owner": clean_text(corrected_owner),
                                "created_date": str(corrected_received) if corrected_received else "",
                                "due_date": clean_text(correction_row.get("due_date", "")),
                                "file_name": clean_text(correction_row.get("file_name", "")),
                                "notes": clean_text(corrected_notes),
                            }
                            update_document_details(
                                correction_id,
                                updates,
                                clean_text(correction_reviewer),
                                clean_text(correction_comments),
                                selected_case_id,
                            )
                            record_review_decision(
                                selected_case_id,
                                "Correction completed",
                                "Under Review",
                                clean_text(correction_reviewer),
                                clean_text(correction_comments),
                                {"corrected_document_id": correction_id},
                            )
                            st.session_state["flash_message"] = (
                                "success",
                                "The metadata was corrected. Approve the case when the issue is resolved.",
                            )
                            st.rerun()

            with st.form(f"attention_action_{selected_case_id}", border=True):
                action_options = ["Review", "Approve"]
                if normalized_key(case_row.get("issue_type", "")) == "exact duplicate":
                    action_options.extend(["Not a duplicate", "Archive duplicate"])
                selected_action = st.radio(
                    "Action",
                    action_options,
                    horizontal=True,
                )

                archive_document_id = None
                if selected_action == "Archive duplicate" and not case_documents.empty:
                    archive_choices = build_record_choice_map(
                        case_documents[
                            pd.to_numeric(
                                case_documents["is_archived"], errors="coerce"
                            ).fillna(0)
                            == 0
                        ]
                    )
                    if archive_choices:
                        archive_label = st.selectbox(
                            "Document copy to archive",
                            list(archive_choices.keys()),
                        )
                        archive_document_id = archive_choices[archive_label]

                reviewer = st.text_input("Completed by *")
                comments = st.text_area(
                    "Comments *",
                    placeholder="Explain what you checked and why this action is correct.",
                )
                action_submit = st.form_submit_button(
                    "Save action",
                    type="primary",
                    use_container_width=True,
                )

            if action_submit:
                if not clean_text(reviewer) or not clean_text(comments):
                    st.error("Completed by and Comments are required.")
                elif selected_action == "Archive duplicate" and archive_document_id is None:
                    st.error("Select the duplicate record to archive.")
                else:
                    if selected_action == "Review":
                        decision = "Start Review"
                        case_status = "Under Review"
                    elif selected_action == "Approve":
                        decision = "Approved"
                        case_status = "Resolved"
                    elif selected_action == "Not a duplicate":
                        decision = "Not a Duplicate"
                        case_status = "Resolved"
                    else:
                        archive_documents(
                            [archive_document_id],
                            clean_text(reviewer),
                            clean_text(comments),
                            selected_case_id,
                        )
                        decision = "Duplicate Archived"
                        case_status = "Resolved"

                    record_review_decision(
                        selected_case_id,
                        decision,
                        case_status,
                        clean_text(reviewer),
                        clean_text(comments),
                        {
                            "related_document_ids": related_ids,
                            "archived_document_id": archive_document_id,
                        },
                    )
                    st.session_state["flash_message"] = (
                        "success",
                        "The review action was saved to the audit history.",
                    )
                    st.rerun()


# -----------------------------
# Quality review
# -----------------------------

elif page == "Quality review":
    render_section_header(
        "Issues found",
        "See the register problems detected by the assistant. Nothing is changed automatically.",
    )

    duplicate_group_count = (
        exact_duplicates_df["duplicate_group"].nunique()
        if not exact_duplicates_df.empty
        else 0
    )

    missing_df = find_missing_metadata(documents_df)
    filename_issues_df = find_filename_issues(documents_df)

    render_metric_cards(
        [
            ("Health score", f"{health_score}/100", "Rule-based register indicator", health_class),
            ("Detected findings", len(review_queue_df), "Synced to manual review", "health-watch" if len(review_queue_df) else "health-good"),
            ("Exact duplicate groups", duplicate_group_count, "Same project + discipline + number + title + revision", "health-risk" if duplicate_group_count else "health-good"),
            ("Missing metadata", len(missing_df), "Records affected", "health-watch" if len(missing_df) else "health-good"),
            ("Missing PDF files", len(missing_pdf_df), "Register rows without attachment", "health-watch" if len(missing_pdf_df) else "health-good"),
        ]
    )

    st.subheader("Issues found")
    if review_queue_df.empty:
        st.success("No document issues are currently open.")
    else:
        st.caption(
            "These are possible issues found by the assistant. "
            "Internal reference numbers are hidden because they are not useful to the reviewer."
        )
        severity_filter = st.multiselect(
            "Show severity",
            ["Critical", "Warning", "Review"],
            default=["Critical", "Warning", "Review"],
        )
        filtered_queue = review_queue_df[
            review_queue_df["severity"].isin(severity_filter)
        ]
        display_table(
            filtered_queue,
            columns=[
                "severity",
                "issue_type",
                "project",
                "discipline",
                "document_number",
                "title",
                "revision",
                "issue",
                "recommended_action",
            ],
            rename={
                "severity": "Severity",
                "issue_type": "Issue Type",
                "project": "Project",
                "discipline": "Discipline",
                "document_number": "Document Number",
                "title": "Title",
                "revision": "Revision",
                "issue": "What Was Found",
                "recommended_action": "What To Do",
            },
            height=430,
            row_height=38,
            column_config={
                "Severity": st.column_config.TextColumn(width="small"),
                "Issue Type": st.column_config.TextColumn(width="medium"),
                "Project": st.column_config.TextColumn(width="medium"),
                "Discipline": st.column_config.TextColumn(width="small"),
                "Document Number": st.column_config.TextColumn(width="medium"),
                "Title": st.column_config.TextColumn(width="large"),
                "Revision": st.column_config.TextColumn(width="small"),
                "What Was Found": st.column_config.TextColumn(width="large"),
                "What To Do": st.column_config.TextColumn(width="large"),
            },
            key="quality_findings_table",
        )

    st.divider()

    st.subheader("1. Exact duplicate candidates — manual approval required")
    st.caption("Only records with matching project, discipline, document number, title and revision appear here. Nothing is archived automatically.")
    if exact_duplicates_df.empty:
        st.success("No exact duplicate document number and revision combinations were found.")
    else:
        display_table(
            exact_duplicates_df,
            columns=DISPLAY_COLUMNS,
            height=320,
        )
        st.info("Open Manual review to compare metadata and PDFs, add comments, and approve the outcome.")

    st.subheader("2. Revision history — information only")
    st.caption("A document number with different revisions is expected and is not treated as a duplicate error.")
    if revision_groups_df.empty:
        st.info("No documents currently have more than one registered revision.")
    else:
        display_table(
            revision_groups_df,
            rename={
                "document_number": "Document Number",
                "title": "Title",
                "revision_count": "Revision Count",
                "revisions": "Registered Revisions",
                "current_revision": "Current Revision",
                "current_created_date": "Current Created Date",
                "current_registered_date": "Current Registered Date",
            },
            height=300,
        )

    with st.expander("Missing metadata", expanded=False):
        if missing_df.empty:
            st.success("No required metadata is missing.")
        else:
            display_table(missing_df, height=300)

    with st.expander("Filename convention review", expanded=False):
        if filename_issues_df.empty:
            st.success("No filename mismatches were detected.")
        else:
            display_table(filename_issues_df, height=300)

    with st.expander("Register records without a PDF", expanded=False):
        if missing_pdf_df.empty:
            st.success("Every register record has at least one controlled PDF attached.")
        else:
            display_table(
                missing_pdf_df,
                columns=[
                    "project",
                    "discipline",
                    "document_number",
                    "revision",
                    "title",
                    "status",
                    "owner",
                ],
                height=340,
            )


# -----------------------------
# Manual review
# -----------------------------

elif page == "Manual review":
    render_section_header(
        "Review and decide",
        "Open a review case, inspect the record and attached PDF, choose a decision, add comments and save.",
    )

    with st.expander("How title conflicts are identified", expanded=False):
        st.info(
            "Documents may have the same title when their document numbers are different. "
            "A title conflict is raised only when the same project, discipline, document "
            "number and revision have different titles."
        )

    if review_cases_df.empty:
        st.success("No review cases have been created.")
    else:
        status_counts = review_cases_df["status"].value_counts()
        render_metric_cards(
            [
                ("Pending", int(status_counts.get("Pending Review", 0)), "Awaiting a reviewer", "health-watch"),
                ("Under review", int(status_counts.get("Under Review", 0)), "Review in progress", ""),
                ("Correction required", int(status_counts.get("Correction Required", 0)), "Record needs an update", "health-risk"),
                ("Escalated", int(status_counts.get("Escalated", 0)), "Further approval required", "health-risk"),
                ("Resolved", int(status_counts.get("Resolved", 0)), "Decision and comments saved", "health-good"),
            ]
        )

        filter_left, filter_middle, filter_right = st.columns(3)
        with filter_left:
            selected_statuses = st.multiselect(
                "Review status",
                sorted(review_cases_df["status"].dropna().astype(str).unique()),
                default=[
                    value
                    for value in ["Pending Review", "Under Review", "Correction Required", "Escalated"]
                    if value in set(review_cases_df["status"].astype(str))
                ],
            )
        with filter_middle:
            selected_issue_types = st.multiselect(
                "Issue type",
                sorted(review_cases_df["issue_type"].dropna().astype(str).unique()),
            )
        with filter_right:
            selected_projects = st.multiselect(
                "Project",
                sorted(
                    value
                    for value in review_cases_df["project"].dropna().astype(str).unique()
                    if clean_text(value)
                ),
            )

        filtered_cases = review_cases_df.copy()
        if selected_statuses:
            filtered_cases = filtered_cases[filtered_cases["status"].isin(selected_statuses)]
        if selected_issue_types:
            filtered_cases = filtered_cases[filtered_cases["issue_type"].isin(selected_issue_types)]
        if selected_projects:
            filtered_cases = filtered_cases[filtered_cases["project"].isin(selected_projects)]

        display_table(
            filtered_cases,
            columns=[
                "severity",
                "status",
                "issue_type",
                "project",
                "discipline",
                "document_number",
                "title",
                "revision",
                "issue_summary",
                "decision",
                "reviewer",
                "reviewed_at",
            ],
            rename={
                "status": "Review Status",
                "issue_type": "Issue Type",
                "document_number": "Document Number",
                "issue_summary": "Issue",
                "reviewed_at": "Reviewed At",
            },
            height=420,
        )

        if filtered_cases.empty:
            st.info("No review cases match the selected filters.")
        else:
            st.divider()
            st.subheader("Review one case")
            case_choices = build_review_case_choice_map(filtered_cases)
            selected_case_label = st.selectbox("Select a review case", list(case_choices.keys()))
            selected_case_id = case_choices[selected_case_label]
            case_row = review_cases_df[review_cases_df["id"] == selected_case_id].iloc[0]
            related_ids = decode_related_ids(case_row["related_document_ids"])
            case_documents = all_documents_df[all_documents_df["id"].isin(related_ids)].copy()

            detail_left, detail_right = st.columns([1.35, 1])
            with detail_left:
                st.markdown("#### Metadata comparison")
                if case_documents.empty:
                    st.warning("The linked register records are no longer available.")
                else:
                    comparison = case_documents.copy()
                    comparison["archive_state"] = comparison["is_archived"].map(
                        lambda value: "Archived" if int(value or 0) else "Active"
                    )
                    display_table(
                        comparison,
                        columns=[
                            "project",
                            "discipline",
                            "document_number",
                            "title",
                            "revision",
                            "status",
                            "owner",
                            "originator",
                            "created_date",
                            "due_date",
                            "created_at",
                            "file_name",
                            "pdf_count",
                            "archive_state",
                            "notes",
                        ],
                        rename={
                            "document_number": "Document Number",
                            "created_date": "Created Date",
                            "due_date": "Due Date",
                            "created_at": "Registered Date",
                            "file_name": "File Name",
                            "pdf_count": "PDF Count",
                            "archive_state": "Record State",
                        },
                        height=330,
                    )

            with detail_right:
                st.markdown("#### Case information")
                st.write(f"**Issue:** {clean_text(case_row['issue_summary'])}")
                st.write(f"**Recommended action:** {clean_text(case_row['recommended_action'])}")
                st.write(f"**Current status:** {clean_text(case_row['status'])}")
                if clean_text(case_row.get("decision", "")):
                    st.write(f"**Last decision:** {clean_text(case_row['decision'])}")
                if clean_text(case_row.get("reviewer", "")):
                    st.write(f"**Reviewer:** {clean_text(case_row['reviewer'])}")
                if clean_text(case_row.get("comments", "")):
                    st.write(f"**Comments:** {clean_text(case_row['comments'])}")

            st.markdown("#### Related controlled PDFs")
            if case_documents.empty:
                st.info("No linked records are available for PDF comparison.")
            else:
                for entry_number, (_, document_row) in enumerate(case_documents.iterrows(), start=1):
                    label = (
                        f"Entry {entry_number}: {clean_text(document_row['document_number'])} · "
                        f"{clean_text(document_row['revision']) or 'No revision'} · "
                        f"{clean_text(document_row['title'])}"
                    )
                    with st.expander(label, expanded=False):
                        files = get_document_files(document_id=int(document_row["id"]))
                        render_attached_files(
                            files,
                            key_prefix=f"review_{selected_case_id}_{entry_number}",
                            allow_delete=False,
                        )

            st.markdown("#### Correct document metadata")
            st.caption(
                "Use this only after checking the register entry and related PDF. "
                "Every correction requires a reviewer name and comments and is written to the audit history."
            )

            if case_documents.empty:
                st.info("No linked register record is available to correct.")
            else:
                correction_choices = build_record_choice_map(case_documents)
                correction_label = st.selectbox(
                    "Select the record that needs correction",
                    list(correction_choices.keys()),
                    key=f"correction_record_{selected_case_id}",
                )
                correction_document_id = correction_choices[correction_label]
                correction_row = case_documents[
                    case_documents["id"] == correction_document_id
                ].iloc[0]

                with st.expander("Open manual metadata editor", expanded=False):
                    discipline_options, discipline_index = select_options_with_current(
                        DISCIPLINE_OPTIONS, correction_row.get("discipline", "")
                    )
                    status_options, status_index = select_options_with_current(
                        STATUS_OPTIONS, correction_row.get("status", "")
                    )

                    with st.form(
                        f"manual_metadata_correction_{selected_case_id}_{correction_document_id}",
                        border=True,
                    ):
                        edit_left, edit_right = st.columns(2)
                        with edit_left:
                            corrected_document_number = st.text_input(
                                "Document Number *",
                                value=clean_text(correction_row.get("document_number", "")),
                            )
                            corrected_title = st.text_input(
                                "Document Title *",
                                value=clean_text(correction_row.get("title", "")),
                            )
                            corrected_project = st.text_input(
                                "Project",
                                value=clean_text(correction_row.get("project", "")),
                            )
                            corrected_discipline = st.selectbox(
                                "Discipline",
                                discipline_options,
                                index=discipline_index,
                            )
                            corrected_revision = st.text_input(
                                "Revision",
                                value=clean_text(correction_row.get("revision", "")),
                            )
                            corrected_status = st.selectbox(
                                "Status",
                                status_options,
                                index=status_index,
                            )

                        with edit_right:
                            corrected_owner = st.text_input(
                                "Owner",
                                value=clean_text(correction_row.get("owner", "")),
                            )
                            corrected_originator = st.text_input(
                                "Originator",
                                value=clean_text(correction_row.get("originator", "")),
                            )
                            corrected_created_date = st.date_input(
                                "Created Date",
                                value=optional_date_value(correction_row.get("created_date", "")),
                            )
                            corrected_due_date = st.date_input(
                                "Due Date (optional)",
                                value=optional_date_value(correction_row.get("due_date", "")),
                            )
                            corrected_file_name = st.text_input(
                                "File Name",
                                value=clean_text(correction_row.get("file_name", "")),
                            )

                        corrected_notes = st.text_area(
                            "Notes",
                            value=clean_text(correction_row.get("notes", "")),
                            height=100,
                        )
                        correction_reviewer = st.text_input(
                            "Correction completed by *",
                            placeholder="Reviewer or document controller name",
                        )
                        correction_comments = st.text_area(
                            "Correction comments *",
                            placeholder="Explain what was changed, what was checked and why the correction was required.",
                            height=110,
                        )
                        correction_confirmed = st.checkbox(
                            "I checked the register entry and related document before applying this correction."
                        )
                        correction_submitted = st.form_submit_button(
                            "Save corrected metadata",
                            type="primary",
                            use_container_width=True,
                            disabled=not correction_confirmed,
                        )

                        if correction_submitted:
                            if not clean_text(correction_reviewer):
                                st.error("Reviewer name is required.")
                            elif not clean_text(correction_comments):
                                st.error("Correction comments are required.")
                            elif not clean_text(corrected_document_number) or not clean_text(corrected_title):
                                st.error("Document Number and Document Title are required.")
                            else:
                                corrected_values = {
                                    "document_number": clean_text(corrected_document_number),
                                    "title": clean_text(corrected_title),
                                    "project": clean_text(corrected_project),
                                    "discipline": clean_text(corrected_discipline),
                                    "revision": clean_text(corrected_revision),
                                    "status": clean_text(corrected_status),
                                    "owner": clean_text(corrected_owner),
                                    "originator": clean_text(corrected_originator),
                                    "created_date": str(corrected_created_date) if corrected_created_date else "",
                                    "due_date": str(corrected_due_date) if corrected_due_date else "",
                                    "file_name": clean_text(corrected_file_name),
                                    "notes": clean_text(corrected_notes),
                                }
                                changed = update_document_details(
                                    correction_document_id,
                                    corrected_values,
                                    clean_text(correction_reviewer),
                                    clean_text(correction_comments),
                                    selected_case_id,
                                )
                                if changed:
                                    st.session_state["flash_message"] = (
                                        "success",
                                        "The corrected metadata was saved. The review case remains open until a final decision is approved.",
                                    )
                                else:
                                    st.session_state["flash_message"] = (
                                        "info",
                                        "No metadata values were changed.",
                                    )
                                st.rerun()

            decision_options = [
                "Start Review",
                "Approved – No Change Required",
                "Correction Required",
                "Not a Duplicate",
                "Escalated",
                "Resolved After Correction",
            ]
            if clean_text(case_row["issue_type"]) == "Exact duplicate":
                decision_options.insert(1, "Approved – Duplicate Archived")

            with st.form(f"manual_review_form_{selected_case_id}", border=True):
                reviewer = st.text_input(
                    "Reviewer name *",
                    placeholder="Enter the person completing the review",
                )
                decision = st.selectbox("Review decision *", decision_options)

                retained_id = None
                archive_ids = []
                move_pdfs = False

                if decision == "Approved – Duplicate Archived" and not case_documents.empty:
                    record_choices = build_record_choice_map(case_documents)
                    retained_label = st.selectbox(
                        "Record to retain *",
                        list(record_choices.keys()),
                    )
                    retained_id = record_choices[retained_label]
                    archive_choices = {
                        label: document_id
                        for label, document_id in record_choices.items()
                        if document_id != retained_id
                    }
                    selected_archive_labels = st.multiselect(
                        "Duplicate copies to archive *",
                        list(archive_choices.keys()),
                        default=list(archive_choices.keys()),
                    )
                    archive_ids = [archive_choices[label] for label in selected_archive_labels]
                    move_pdfs = st.checkbox(
                        "Move PDF links from the archived copies to the retained record",
                        value=False,
                        help="Use this only after comparing the PDFs. Archived metadata and the review audit remain available.",
                    )

                comments = st.text_area(
                    "Review comments *",
                    placeholder="Explain what was checked, what was approved and why.",
                    height=130,
                )
                submitted_review = st.form_submit_button(
                    "Save review decision",
                    type="primary",
                    use_container_width=True,
                )

                if submitted_review:
                    if not clean_text(reviewer):
                        st.error("Reviewer name is required.")
                    elif not clean_text(comments):
                        st.error("Review comments are required for every decision.")
                    elif decision == "Approved – Duplicate Archived" and (
                        retained_id is None or not archive_ids
                    ):
                        st.error("Select one retained record and at least one duplicate copy to archive.")
                    else:
                        details = {
                            "related_document_ids": related_ids,
                            "retained_document_id": retained_id,
                            "archived_document_ids": archive_ids,
                            "pdf_links_moved": move_pdfs,
                        }

                        if decision == "Approved – Duplicate Archived":
                            if move_pdfs:
                                for source_id in archive_ids:
                                    reassign_document_files(source_id, retained_id)
                            archive_documents(
                                archive_ids,
                                clean_text(reviewer),
                                clean_text(comments),
                                selected_case_id,
                            )
                            case_status = "Resolved"
                        elif decision == "Start Review":
                            case_status = "Under Review"
                        elif decision == "Correction Required":
                            case_status = "Correction Required"
                        elif decision == "Escalated":
                            case_status = "Escalated"
                        else:
                            case_status = "Resolved"

                        record_review_decision(
                            selected_case_id,
                            decision,
                            case_status,
                            clean_text(reviewer),
                            clean_text(comments),
                            details,
                        )
                        st.session_state["flash_message"] = (
                            "success",
                            "The manual review decision and comments were saved to the audit history.",
                        )
                        st.rerun()

            action_history = get_review_actions(selected_case_id)
            with st.expander("Review action history", expanded=False):
                if action_history.empty:
                    st.info("No decisions have been recorded for this case yet.")
                else:
                    display_table(
                        action_history,
                        columns=["action", "reviewer", "comments", "created_at"],
                        rename={"created_at": "Action Date"},
                        height=260,
                    )


# -----------------------------
# Revision history
# -----------------------------

elif page == "Revision history":
    render_section_header(
        "Revision history",
        "Keep every legitimate revision and its metadata. The newest revision is highlighted as current while all previous revisions and dates remain visible.",
    )

    if documents_df.empty:
        st.info("No documents are available.")
    else:
        families = {}
        family_groups = documents_df.groupby(documents_df.apply(revision_family_key, axis=1))
        for position, (_, group) in enumerate(family_groups, start=1):
            representative = group.iloc[0]
            label = (
                f"{clean_text(representative['project']) or 'Project not set'} · "
                f"{clean_text(representative['discipline']) or 'Discipline not set'} · "
                f"{clean_text(representative['document_number'])} · "
                f"{clean_text(representative['title'])}"
            )
            if label in families:
                label = f"{label} · Family {position}"
            families[label] = group.index.tolist()

        selected_family_label = st.selectbox(
            "Select a document by project, discipline, number and title",
            list(families.keys()),
        )
        history = documents_df.loc[families[selected_family_label]].copy()
        history = sort_revision_history(history)
        current = history.iloc[0]

        render_metric_cards(
            [
                ("Registered revisions", len(history), "Current and previous versions", ""),
                ("Current revision", clean_text(current["revision"]) or "Not set", "Highest registered revision", "health-good"),
                ("Current status", clean_text(current["status"]) or "Not set", "Current revision metadata", ""),
                ("Current created date", clean_text(current["created_date"]) or "Not set", "Revision-specific date", ""),
                ("Current registered date", clean_text(current["created_at"]) or "Not set", "Database registration date", ""),
            ]
        )

        display_table(
            history,
            columns=[
                "revision_role",
                "revision",
                "status",
                "created_date",
                "due_date",
                "created_at",
                "owner",
                "originator",
                "file_name",
                "pdf_count",
                "notes",
            ],
            rename={
                "revision_role": "Revision Role",
                "created_date": "Created Date",
                "due_date": "Due Date",
                "created_at": "Registered Date",
                "file_name": "File Name",
                "pdf_count": "PDF Count",
            },
            height=460,
        )

        st.info(
            "Previous revisions remain part of the controlled history. Only a manually approved duplicate copy can be archived."
        )

        st.subheader("Attached PDF files by revision")
        for entry_number, (_, document_row) in enumerate(history.iterrows(), start=1):
            label = (
                f"{clean_text(document_row['revision_role'])}: "
                f"{clean_text(document_row['revision']) or 'No revision'} · "
                f"{clean_text(document_row['created_date']) or 'Created date not set'}"
            )
            with st.expander(label, expanded=entry_number == 1):
                files = get_document_files(document_id=int(document_row["id"]))
                render_attached_files(
                    files,
                    key_prefix=f"revision_{entry_number}_{safe_folder_name(clean_text(document_row['document_number']))}",
                    allow_delete=False,
                )


# -----------------------------
# Administration
# -----------------------------

elif page == "Administration":
    render_section_header(
        "Register administration",
        "Update active records, archive records with a named reviewer and comments, restore archived records and view the audit history. Permanent deletion is not available in the interface.",
    )

    st.markdown(
        """
        <div class="notice notice-safe">
            Duplicate decisions are completed in <strong>Manual review</strong>. Records are archived only after a reviewer compares the metadata and PDFs and saves approval comments.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.subheader("Manage one active document")
    if documents_df.empty:
        st.info("No active documents are available to manage.")
    else:
        choices = build_record_choice_map(documents_df)
        selected_label = st.selectbox("Select an active record", list(choices.keys()))
        selected_id = choices[selected_label]
        selected_df = documents_df[documents_df["id"] == selected_id]

        display_table(selected_df, columns=DISPLAY_COLUMNS, height=180)

        st.markdown("#### Attached PDF files")
        selected_files = get_document_files(document_id=selected_id)
        render_attached_files(
            selected_files,
            key_prefix=f"admin_{selected_id}",
            allow_delete=False,
        )

        action_left, action_right = st.columns([1.45, 1])
        with action_left:
            selected_row = selected_df.iloc[0]
            administration_discipline_options, administration_discipline_index = (
                select_options_with_current(
                    DISCIPLINE_OPTIONS, selected_row.get("discipline", "")
                )
            )
            administration_status_options, administration_status_index = (
                select_options_with_current(
                    STATUS_OPTIONS, selected_row.get("status", "")
                )
            )

            with st.form(f"full_metadata_edit_{selected_id}", border=True):
                st.markdown("#### Edit document details")
                st.caption(
                    "All changes require a named reviewer and comments and are recorded in the audit history."
                )
                edit_col_one, edit_col_two = st.columns(2)
                with edit_col_one:
                    administration_document_number = st.text_input(
                        "Document Number *",
                        value=clean_text(selected_row.get("document_number", "")),
                    )
                    administration_title = st.text_input(
                        "Document Title *",
                        value=clean_text(selected_row.get("title", "")),
                    )
                    administration_project = st.text_input(
                        "Project",
                        value=clean_text(selected_row.get("project", "")),
                    )
                    administration_discipline = st.selectbox(
                        "Discipline",
                        administration_discipline_options,
                        index=administration_discipline_index,
                    )
                    administration_revision = st.text_input(
                        "Revision",
                        value=clean_text(selected_row.get("revision", "")),
                    )
                    administration_status = st.selectbox(
                        "Status",
                        administration_status_options,
                        index=administration_status_index,
                    )

                with edit_col_two:
                    administration_owner = st.text_input(
                        "Owner",
                        value=clean_text(selected_row.get("owner", "")),
                    )
                    administration_originator = st.text_input(
                        "Originator",
                        value=clean_text(selected_row.get("originator", "")),
                    )
                    administration_created_date = st.date_input(
                        "Created Date",
                        value=optional_date_value(selected_row.get("created_date", "")),
                    )
                    administration_due_date = st.date_input(
                        "Due Date (optional)",
                        value=optional_date_value(selected_row.get("due_date", "")),
                    )
                    administration_file_name = st.text_input(
                        "File Name",
                        value=clean_text(selected_row.get("file_name", "")),
                    )

                administration_notes = st.text_area(
                    "Notes",
                    value=clean_text(selected_row.get("notes", "")),
                    height=100,
                )
                administration_reviewer = st.text_input("Changed by *")
                administration_comments = st.text_area(
                    "Change reason and comments *",
                    placeholder="Explain what was changed, what was checked and why.",
                    height=100,
                )
                administration_confirmed = st.checkbox(
                    "I reviewed the selected register record before saving these changes."
                )
                administration_submitted = st.form_submit_button(
                    "Save document details",
                    type="primary",
                    use_container_width=True,
                    disabled=not administration_confirmed,
                )

                if administration_submitted:
                    if not clean_text(administration_reviewer):
                        st.error("Reviewer name is required.")
                    elif not clean_text(administration_comments):
                        st.error("Change comments are required.")
                    elif not clean_text(administration_document_number) or not clean_text(administration_title):
                        st.error("Document Number and Document Title are required.")
                    else:
                        administration_updates = {
                            "document_number": clean_text(administration_document_number),
                            "title": clean_text(administration_title),
                            "project": clean_text(administration_project),
                            "discipline": clean_text(administration_discipline),
                            "revision": clean_text(administration_revision),
                            "status": clean_text(administration_status),
                            "owner": clean_text(administration_owner),
                            "originator": clean_text(administration_originator),
                            "created_date": str(administration_created_date) if administration_created_date else "",
                            "due_date": str(administration_due_date) if administration_due_date else "",
                            "file_name": clean_text(administration_file_name),
                            "notes": clean_text(administration_notes),
                        }
                        changed = update_document_details(
                            selected_id,
                            administration_updates,
                            clean_text(administration_reviewer),
                            clean_text(administration_comments),
                        )
                        st.session_state["flash_message"] = (
                            "success" if changed else "info",
                            "Document details updated and written to the audit history."
                            if changed
                            else "No metadata values were changed.",
                        )
                        st.rerun()

        with action_right:
            with st.form("manual_archive_form"):
                st.markdown("#### Archive selected record")
                archive_reviewer = st.text_input("Reviewer name *")
                archive_comments = st.text_area(
                    "Archive reason and comments *",
                    placeholder="Explain why this active record should be archived.",
                )
                archive_confirmed = st.checkbox(
                    "I reviewed the record and understand it will leave the active register but remain recoverable."
                )
                archive_submitted = st.form_submit_button(
                    "Archive selected record",
                    disabled=not archive_confirmed,
                    use_container_width=True,
                )
                if archive_submitted:
                    if not clean_text(archive_reviewer) or not clean_text(archive_comments):
                        st.error("Reviewer name and archive comments are required.")
                    else:
                        archive_documents(
                            [selected_id],
                            clean_text(archive_reviewer),
                            clean_text(archive_comments),
                        )
                        st.session_state["flash_message"] = (
                            "success",
                            "The selected record was archived and remains available in the audit history.",
                        )
                        st.rerun()

    st.divider()
    st.subheader("Archived records")
    if archived_documents_df.empty:
        st.info("No records are currently archived.")
    else:
        display_table(
            archived_documents_df,
            columns=[
                "project",
                "discipline",
                "document_number",
                "title",
                "revision",
                "status",
                "created_date",
                "created_at",
                "archived_at",
                "archived_by",
                "archive_reason",
                "pdf_count",
            ],
            rename={
                "document_number": "Document Number",
                "created_date": "Created Date",
                "created_at": "Registered Date",
                "archived_at": "Archived Date",
                "archived_by": "Archived By",
                "archive_reason": "Archive Reason",
                "pdf_count": "PDF Count",
            },
            height=330,
        )

        archived_choices = build_record_choice_map(archived_documents_df)
        selected_archived_label = st.selectbox(
            "Select an archived record to restore",
            list(archived_choices.keys()),
        )
        selected_archived_id = archived_choices[selected_archived_label]
        with st.form("restore_archived_form"):
            restore_reviewer = st.text_input("Restored by *")
            restore_comments = st.text_area("Restoration comments *")
            restore_submitted = st.form_submit_button(
                "Restore selected record",
                type="primary",
                use_container_width=True,
            )
            if restore_submitted:
                if not clean_text(restore_reviewer) or not clean_text(restore_comments):
                    st.error("Reviewer name and restoration comments are required.")
                else:
                    restore_document(
                        selected_archived_id,
                        clean_text(restore_reviewer),
                        clean_text(restore_comments),
                    )
                    st.session_state["flash_message"] = (
                        "success",
                        "The archived record was restored to the active register.",
                    )
                    st.rerun()

    st.divider()
    st.subheader("Audit history")
    audit_df = get_audit_log()
    review_actions_df = get_review_actions()

    audit_tab, review_tab = st.tabs(["Archive and restore events", "Review decisions"])
    with audit_tab:
        if audit_df.empty:
            st.info("No archive or restoration events have been recorded.")
        else:
            display_table(
                audit_df,
                rename={
                    "event_type": "Event",
                    "document_number": "Document Number",
                    "created_at": "Event Date",
                },
                height=330,
            )

    with review_tab:
        if review_actions_df.empty:
            st.info("No manual review decisions have been recorded.")
        else:
            display_table(
                review_actions_df,
                columns=[
                    "issue_type",
                    "document_number",
                    "revision",
                    "action",
                    "reviewer",
                    "comments",
                    "created_at",
                ],
                rename={
                    "issue_type": "Issue Type",
                    "document_number": "Document Number",
                    "action": "Decision",
                    "created_at": "Decision Date",
                },
                height=360,
            )

