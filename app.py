import hashlib
import io
import json
import re
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

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
    init_db,
    reassign_document_files,
    record_review_decision,
    restore_document,
    sync_review_cases,
    update_document_details,
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

STATUS_OPTIONS = [
    "Draft",
    "For Review",
    "For Information",
    "Approved",
    "Approved with Comments",
    "Rejected",
    "Superseded",
    "Missing Information",
    "Closed",
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
    "due_date",
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
    "due_date",
    "file_name",
    "pdf_count",
    "notes",
]


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
    """Find ambiguous records that must never be cleaned automatically."""
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
            normalized_key(value) for value in group["title"] if clean_text(value)
        }
        if len(group) > 1 and len(distinct_titles) > 1:
            conflicts.append(
                {
                    "conflict_type": "Title conflict",
                    "project": clean_text(group.iloc[0]["project"]),
                    "discipline": clean_text(group.iloc[0]["discipline"]),
                    "document_number": clean_text(group.iloc[0]["document_number"]),
                    "revision": clean_text(group.iloc[0]["revision"]),
                    "titles": " | ".join(sorted({clean_text(value) for value in group["title"]})),
                    "related_document_ids": [int(value) for value in group["id"].tolist()],
                }
            )

    title_revision_keys = [
        "_project_key",
        "_discipline_key",
        "_title_key",
        "_revision_key",
    ]
    for _, group in working.groupby(title_revision_keys, dropna=False):
        distinct_numbers = {
            normalized_key(value)
            for value in group["document_number"]
            if clean_text(value)
        }
        if len(group) > 1 and len(distinct_numbers) > 1:
            conflicts.append(
                {
                    "conflict_type": "Document number conflict",
                    "project": clean_text(group.iloc[0]["project"]),
                    "discipline": clean_text(group.iloc[0]["discipline"]),
                    "document_number": " | ".join(sorted({clean_text(value) for value in group["document_number"]})),
                    "revision": clean_text(group.iloc[0]["revision"]),
                    "titles": clean_text(group.iloc[0]["title"]),
                    "related_document_ids": [int(value) for value in group["id"].tolist()],
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

    overdue = find_overdue_documents(df)
    if not overdue.empty:
        for _, row in overdue.iterrows():
            add_finding(
                "Overdue open record",
                "Warning",
                row["id"],
                [row["id"]],
                row["document_number"],
                row["revision"],
                f"Open record is {int(row['days_overdue'])} day(s) overdue",
                "Review the document status and due date, then record the decision",
            )

    date_issues = find_date_sequence_issues(df)
    if not date_issues.empty:
        for _, row in date_issues.iterrows():
            add_finding(
                "Date sequence issue",
                "Warning",
                row["id"],
                [row["id"]],
                row["document_number"],
                row["revision"],
                "Created date is later than due date",
                "Inspect the dates and approve a correction or escalation",
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
overdue_df = find_overdue_documents(documents_df)
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

with st.sidebar:
    st.markdown("## 📑 Document Control")
    st.caption("Register governance workspace")

    page = st.radio(
        "Navigation",
        [
            "Dashboard",
            "Add document",
            "Import CSV",
            "PDF library",
            "Document register",
            "Quality review",
            "Manual review",
            "Revision history",
            "Administration",
        ],
        label_visibility="collapsed",
    )

    st.divider()
    st.markdown("#### Workspace status")
    st.write(f"**{len(documents_df)}** stored records")
    st.write(f"**{len(all_pdf_files_df)}** PDF files")
    st.write(f"**{len(missing_pdf_df)}** records without PDF")
    st.write(f"**{len(open_review_cases_df)}** open review cases")
    st.write(f"**{health_score}/100** health score")
    st.caption("Local SQLite database and file library · Demo data only")


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
            <span class="hero-badge">CSV import</span>
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
        st.info("The register is empty. Add a document manually or import a CSV register.")
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
            due_date = st.date_input("Due Date", value=None)
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
                st.error("Created Date cannot be later than Due Date.")
            else:
                possible_duplicate = make_document_key(
                    document_number,
                    title,
                    revision,
                    project,
                    discipline,
                ) in existing_document_keys(documents_df)
                exact_same_metadata = make_record_signature(
                    new_document
                ) in existing_record_signatures(documents_df)

                if exact_same_metadata:
                    st.error(
                        "An identical register row is already stored. No additional copy was created."
                    )
                elif possible_duplicate and not allow_possible_duplicate:
                    st.error(
                        "A record with the same project, discipline, document number, title and revision already exists. Tick the manual-review option only when the records genuinely need comparison."
                    )
                else:
                    add_document(new_document)
                    message = (
                        "Possible duplicate saved and added to Manual review."
                        if possible_duplicate
                        else "Document saved successfully. The form has been cleared."
                    )
                    st.session_state["flash_message"] = (
                        "success",
                        message,
                    )
                    st.rerun()


# -----------------------------
# Import CSV
# -----------------------------

elif page == "Import CSV":
    render_section_header(
        "Import a CSV register",
        "Preview and validate the file before importing. Exact duplicates are separated and will not be added again.",
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
                "due_date": "2026-06-26",
                "file_name": "RWE-ENG-DRG-0001_P01.pdf",
                "notes": "Initial submission",
            }
        ]
    )

    st.download_button(
        "Download CSV template",
        data=template_df.to_csv(index=False).encode("utf-8-sig"),
        file_name="document_register_template.csv",
        mime="text/csv",
        use_container_width=False,
    )

    uploaded_file = st.file_uploader(
        "Choose a CSV document register",
        type=["csv"],
    )

    if uploaded_file is not None:
        try:
            raw_df = read_uploaded_csv(uploaded_file)
            missing_columns = [
                column
                for column in ["document_number", "title"]
                if column not in raw_df.columns
            ]

            if missing_columns:
                st.error(
                    "The CSV is missing essential columns: "
                    + ", ".join(missing_columns)
                )
            else:
                prepared_df = prepare_uploaded_register(raw_df)
                prepared_df["_identity_key"] = prepared_df.apply(
                    lambda row: make_document_key(
                        row["document_number"],
                        row["title"],
                        row["revision"],
                        row["project"],
                        row["discipline"],
                    ),
                    axis=1,
                )
                prepared_df["_signature"] = prepared_df.apply(
                    make_record_signature,
                    axis=1,
                )

                invalid_rows = prepared_df[
                    (prepared_df["document_number"] == "")
                    | (prepared_df["title"] == "")
                ].copy()

                valid_rows = prepared_df.drop(index=invalid_rows.index).copy()

                duplicate_inside_mask = valid_rows.duplicated(
                    subset=["_signature"], keep="first"
                )
                duplicate_inside_csv = valid_rows[duplicate_inside_mask].copy()
                valid_rows = valid_rows[~duplicate_inside_mask].copy()

                database_signatures = existing_record_signatures(documents_df)
                already_exists_mask = valid_rows["_signature"].isin(database_signatures)
                already_in_database = valid_rows[already_exists_mask].copy()
                new_rows = valid_rows[~already_exists_mask].copy()

                database_identity_keys = existing_document_keys(documents_df)
                possible_duplicates = new_rows[
                    new_rows["_identity_key"].isin(database_identity_keys)
                ].copy()

                render_metric_cards(
                    [
                        ("CSV rows", len(prepared_df), "Rows read from file", ""),
                        ("New records", len(new_rows), "Ready to import", "health-good" if len(new_rows) else ""),
                        ("Already stored", len(already_in_database), "Identical rows skipped", ""),
                        ("Possible duplicates", len(possible_duplicates), "Imported for manual review", "health-watch" if len(possible_duplicates) else ""),
                        ("Repeated in CSV", len(duplicate_inside_csv), "Identical extra rows skipped", "health-watch" if len(duplicate_inside_csv) else ""),
                        ("Invalid rows", len(invalid_rows), "Missing number or title", "health-risk" if len(invalid_rows) else ""),
                    ]
                )

                st.subheader("Import preview")
                display_table(
                    prepared_df.drop(columns=["_identity_key", "_signature"]),
                    height=350,
                )

                with st.expander("Rows already stored", expanded=False):
                    if already_in_database.empty:
                        st.success("No identical stored rows were found.")
                    else:
                        display_table(already_in_database.drop(columns=["_identity_key", "_signature"]), height=260)

                with st.expander("Repeated rows inside the CSV", expanded=False):
                    if duplicate_inside_csv.empty:
                        st.success("No completely identical repeated rows were found inside the CSV.")
                    else:
                        display_table(duplicate_inside_csv.drop(columns=["_identity_key", "_signature"]), height=260)

                with st.expander("Possible duplicates requiring manual review", expanded=False):
                    if possible_duplicates.empty:
                        st.success("No incoming rows share an existing document identity with different metadata.")
                    else:
                        st.warning(
                            "These rows have the same project, discipline, document number, title and revision as an existing record, but other metadata differs. They will be imported and sent to Manual review."
                        )
                        display_table(
                            possible_duplicates.drop(columns=["_identity_key", "_signature"]),
                            height=280,
                        )

                with st.expander("Invalid rows", expanded=False):
                    if invalid_rows.empty:
                        st.success("Every row has a document number and title.")
                    else:
                        display_table(invalid_rows.drop(columns=["_identity_key", "_signature"]), height=260)

                if new_rows.empty:
                    st.info("There are no new valid records to import.")
                else:
                    confirmed = st.checkbox(
                        f"I reviewed the preview and want to import {len(new_rows)} new record(s)."
                    )

                    if st.button(
                        "Import new records",
                        type="primary",
                        disabled=not confirmed,
                        use_container_width=True,
                    ):
                        for _, row in new_rows.iterrows():
                            add_document(
                                {
                                    column: clean_text(row[column])
                                    for column in CSV_COLUMNS
                                }
                            )

                        st.session_state["flash_message"] = (
                            "success",
                            f"{len(new_rows)} new document record(s) imported. Identical stored and repeated rows were skipped; possible duplicate identities were imported for manual review.",
                        )
                        st.rerun()

        except pd.errors.EmptyDataError:
            st.error("The uploaded CSV file is empty.")
        except Exception as error:
            st.error("The CSV could not be processed.")
            st.code(str(error))


# -----------------------------
# PDF library
# -----------------------------

elif page == "PDF library":
    render_section_header(
        "Controlled PDF library",
        "Attach a PDF to an existing register record. Files are validated against the selected document number and revision, then stored under Project → Discipline → Document Number.",
    )

    if documents_df.empty:
        st.info("Add or import document register records before uploading PDF files.")
    else:
        project_values = sorted(
            value
            for value in documents_df["project"].dropna().astype(str).unique()
            if clean_text(value)
        )

        if not project_values:
            st.warning("No projects are available. Complete the Project field in the register first.")
        else:
            selected_project = st.selectbox("Project", project_values)

            project_records = documents_df[
                documents_df["project"].map(normalized_key)
                == normalized_key(selected_project)
            ].copy()

            discipline_values = sorted(
                value
                for value in project_records["discipline"].dropna().astype(str).unique()
                if clean_text(value)
            )

            selected_discipline = st.selectbox(
                "Discipline",
                discipline_values if discipline_values else ["Unassigned"],
            )

            if selected_discipline == "Unassigned":
                discipline_records = project_records[
                    project_records["discipline"].map(clean_text) == ""
                ].copy()
            else:
                discipline_records = project_records[
                    project_records["discipline"].map(normalized_key)
                    == normalized_key(selected_discipline)
                ].copy()

            attached_count = int(
                pd.to_numeric(discipline_records.get("pdf_count", 0), errors="coerce")
                .fillna(0)
                .sum()
            ) if not discipline_records.empty else 0
            missing_count = int(
                (pd.to_numeric(discipline_records.get("pdf_count", 0), errors="coerce").fillna(0) == 0).sum()
            ) if not discipline_records.empty else 0

            render_metric_cards(
                [
                    ("Project records", len(project_records), selected_project, ""),
                    ("Discipline records", len(discipline_records), selected_discipline, ""),
                    ("Attached PDFs", attached_count, "Files in this discipline", ""),
                    ("Missing PDFs", missing_count, "Register rows without a file", "health-watch" if missing_count else "health-good"),
                ]
            )

            st.subheader("Upload and match a PDF")

            if discipline_records.empty:
                st.info("No register records match this Project and Discipline selection.")
            else:
                record_choices = build_record_choice_map(discipline_records)

                selected_record_label = st.selectbox(
                    "Register record",
                    list(record_choices.keys()),
                )
                selected_record_id = record_choices[selected_record_label]
                selected_record = discipline_records[
                    discipline_records["id"] == selected_record_id
                ].iloc[0]

                record_summary = pd.DataFrame(
                    [
                        {
                            "Document Number": clean_text(selected_record["document_number"]),
                            "Title": clean_text(selected_record["title"]),
                            "Project": clean_text(selected_record["project"]),
                            "Discipline": clean_text(selected_record["discipline"]),
                            "Revision": clean_text(selected_record["revision"]),
                            "Status": clean_text(selected_record["status"]),
                            "Attached PDFs": int(selected_record.get("pdf_count", 0) or 0),
                        }
                    ]
                )
                st.dataframe(record_summary, use_container_width=True, hide_index=True)

                uploaded_pdf = st.file_uploader(
                    "Choose the controlled PDF",
                    type=["pdf"],
                    accept_multiple_files=False,
                    key=f"pdf_upload_{selected_record_id}",
                )

                if uploaded_pdf is not None:
                    inspection = inspect_pdf_upload(uploaded_pdf, selected_record)

                    check_rows = pd.DataFrame(
                        [
                            {
                                "Check": "Valid PDF file",
                                "Result": "Pass" if inspection["valid_header"] else "Fail",
                                "Expected": "File begins with a valid PDF signature",
                            },
                            {
                                "Check": "Document number in filename",
                                "Result": "Pass" if inspection["document_number_match"] else "Review",
                                "Expected": clean_text(selected_record["document_number"]),
                            },
                            {
                                "Check": "Revision in filename",
                                "Result": "Pass" if inspection["revision_match"] else "Review",
                                "Expected": clean_text(selected_record["revision"]) or "No revision required",
                            },
                            {
                                "Check": "Identical file already stored",
                                "Result": "Fail" if inspection["duplicate_file"] else "Pass",
                                "Expected": "Unique PDF content",
                            },
                        ]
                    )
                    st.dataframe(check_rows, use_container_width=True, hide_index=True)
                    st.caption(
                        f"Selected file: {inspection['file_name']} · {human_file_size(inspection['file_size'])}"
                    )

                    if inspection["duplicate_file"]:
                        duplicate = inspection["duplicate_file"]
                        st.error(
                            "This exact PDF is already stored against "
                            f"{duplicate['document_number']} revision {duplicate['revision'] or 'not set'}."
                        )
                    elif not inspection["valid_header"]:
                        st.error("The uploaded file does not contain a valid PDF signature.")
                    else:
                        naming_matches = (
                            inspection["document_number_match"]
                            and inspection["revision_match"]
                        )

                        allow_mismatch = False
                        if not naming_matches:
                            st.warning(
                                "The PDF filename does not fully match the selected register record. Review the document number and revision before saving."
                            )
                            allow_mismatch = st.checkbox(
                                "I reviewed the mismatch and confirm that this PDF belongs to the selected record.",
                                key=f"allow_pdf_mismatch_{selected_record_id}_{inspection['file_hash'][:8]}",
                            )

                        can_store = naming_matches or allow_mismatch

                        if st.button(
                            "Save PDF to controlled library",
                            type="primary",
                            disabled=not can_store,
                            use_container_width=True,
                        ):
                            target_path = build_pdf_storage_path(
                                selected_record,
                                inspection["file_name"],
                                inspection["file_hash"],
                            )
                            target_path.write_bytes(inspection["file_bytes"])

                            try:
                                add_document_file(
                                    {
                                        "document_id": selected_record_id,
                                        "project": clean_text(selected_record["project"]),
                                        "discipline": clean_text(selected_record["discipline"]),
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
                                "PDF uploaded, validated and linked to the selected register record.",
                            )
                            st.rerun()

            st.divider()
            st.subheader("Project and discipline file audit")
            st.caption(
                "This view checks the selected register group against the PDF files stored in the system."
            )

            if discipline_records.empty:
                st.info("No records are available for this group.")
            else:
                audit_df = discipline_records[
                    [
                        "document_number",
                        "title",
                        "revision",
                        "status",
                        "owner",
                        "pdf_count",
                    ]
                ].copy()
                audit_df["file_record_check"] = audit_df["pdf_count"].apply(
                    lambda count: "PDF attached" if int(count or 0) > 0 else "Missing PDF"
                )
                audit_df = audit_df.rename(
                    columns={
                        "document_number": "Document Number",
                        "title": "Title",
                        "revision": "Revision",
                        "status": "Status",
                        "owner": "Owner",
                        "pdf_count": "PDF Count",
                        "file_record_check": "File Record Check",
                    }
                )
                st.dataframe(audit_df, use_container_width=True, hide_index=True, height=360)

                group_files = get_document_files(
                    project=selected_project,
                    discipline="" if selected_discipline == "Unassigned" else selected_discipline,
                )
                st.subheader("Stored PDFs in this group")
                render_attached_files(
                    group_files,
                    key_prefix=f"group_{safe_folder_name(selected_project)}_{safe_folder_name(selected_discipline)}",
                    allow_delete=False,
                )


# -----------------------------
# Register
# -----------------------------

elif page == "Document register":
    render_section_header(
        "Document register",
        "Search by document number or title, then filter and export the controlled register. Different revisions remain visible as separate records.",
    )

    if documents_df.empty:
        st.info("No documents have been added yet.")
    else:
        def clear_register_filters():
            st.session_state["register_search"] = ""
            st.session_state["register_projects"] = []
            st.session_state["register_disciplines"] = []
            st.session_state["register_statuses"] = []

        project_values = sorted(
            value
            for value in documents_df["project"].dropna().astype(str).unique()
            if clean_text(value)
        )
        discipline_values = sorted(
            value
            for value in documents_df["discipline"].dropna().astype(str).unique()
            if clean_text(value)
        )
        status_values = sorted(
            value
            for value in documents_df["status"].dropna().astype(str).unique()
            if clean_text(value)
        )

        with st.container(border=True):
            filter_header_left, filter_header_right = st.columns([5, 1])
            with filter_header_left:
                st.markdown("### 🔎 Filter the register")
                st.caption(
                    "Use the search box first, then narrow the results by project, discipline or status."
                )
            with filter_header_right:
                st.button(
                    "Clear filters",
                    on_click=clear_register_filters,
                    use_container_width=True,
                )

            search_text = st.text_input(
                "🔎 Search by document number or title",
                placeholder="Enter a document number or document title",
                key="register_search",
            )

            project_col, discipline_col, status_col = st.columns(3, gap="large")

            with project_col:
                selected_projects = st.multiselect(
                    "📁 Project",
                    project_values,
                    placeholder="Choose one or more projects",
                    key="register_projects",
                )

            with discipline_col:
                selected_disciplines = st.multiselect(
                    "🧭 Discipline",
                    discipline_values,
                    placeholder="Choose one or more disciplines",
                    key="register_disciplines",
                )

            with status_col:
                selected_statuses = st.multiselect(
                    "🏷️ Status",
                    status_values,
                    placeholder="Choose one or more statuses",
                    key="register_statuses",
                )

        filtered = documents_df.copy()

        if search_text:
            search_key = normalized_key(search_text)
            searchable = (
                filtered["document_number"].fillna("").astype(str)
                + " "
                + filtered["title"].fillna("").astype(str)
            ).str.casefold()
            filtered = filtered[searchable.str.contains(re.escape(search_key), na=False)]

        if selected_projects:
            filtered = filtered[filtered["project"].isin(selected_projects)]

        if selected_statuses:
            filtered = filtered[filtered["status"].isin(selected_statuses)]

        if selected_disciplines:
            filtered = filtered[filtered["discipline"].isin(selected_disciplines)]

        render_metric_cards(
            [
                ("Matching records", len(filtered), "Current filtered view", ""),
                ("Total records", len(documents_df), "Complete register", ""),
                ("Unique documents", filtered["document_number"].map(normalized_key).nunique(), "In current view", ""),
                ("PDF files", int(pd.to_numeric(filtered.get("pdf_count", 0), errors="coerce").fillna(0).sum()), "In current view", ""),
                ("Missing PDFs", int((pd.to_numeric(filtered.get("pdf_count", 0), errors="coerce").fillna(0) == 0).sum()), "In current view", "health-watch"),
            ]
        )

        filtered = filtered.sort_values(
            ["project", "discipline", "document_number", "revision", "id"]
        )

        register_rename = {
            "document_number": "Document Number",
            "title": "Title",
            "project": "Project",
            "discipline": "Discipline",
            "revision": "Revision",
            "status": "Status",
            "owner": "Owner",
            "originator": "Originator",
            "created_date": "Created Date",
            "due_date": "Due Date",
            "file_name": "Expected File Name",
            "pdf_count": "PDF Files",
            "notes": "Notes",
        }

        available_columns = [
            column
            for column in DISPLAY_COLUMNS
            if column in filtered.columns and column != "id"
        ]
        label_to_column = {
            register_rename.get(column, column): column
            for column in available_columns
        }

        if "register_visible_columns" in st.session_state:
            allowed_labels = set(label_to_column.keys())
            st.session_state["register_visible_columns"] = [
                label
                for label in st.session_state["register_visible_columns"]
                if label in allowed_labels
            ]

        with st.expander("⚙️ Table view settings", expanded=True):
            settings_col_1, settings_col_2, settings_col_3 = st.columns([2.2, 1, 1])

            with settings_col_1:
                selected_column_labels = st.multiselect(
                    "Visible columns",
                    options=list(label_to_column.keys()),
                    default=list(label_to_column.keys()),
                    help="Remove columns you do not need. Add them back at any time.",
                    key="register_visible_columns",
                )

            with settings_col_2:
                table_height = st.slider(
                    "Table height",
                    min_value=350,
                    max_value=950,
                    value=650,
                    step=50,
                    key="register_table_height",
                )

            with settings_col_3:
                row_height = st.slider(
                    "Row height",
                    min_value=26,
                    max_value=58,
                    value=34,
                    step=2,
                    key="register_row_height",
                )

            st.caption(
                "Drag a column border to resize it. Use the fullscreen icon in the table toolbar to inspect every column on a larger canvas."
            )

        selected_columns = [
            label_to_column[label]
            for label in selected_column_labels
            if label in label_to_column
        ]

        if not selected_columns:
            st.warning("Select at least one visible column in Table view settings.")
        else:
            column_config = {
                "Document Number": st.column_config.TextColumn(width="medium"),
                "Title": st.column_config.TextColumn(width="large"),
                "Project": st.column_config.TextColumn(width="medium"),
                "Discipline": st.column_config.TextColumn(width="medium"),
                "Revision": st.column_config.TextColumn(width="small"),
                "Status": st.column_config.TextColumn(width="medium"),
                "Owner": st.column_config.TextColumn(width="medium"),
                "Originator": st.column_config.TextColumn(width="medium"),
                "Created Date": st.column_config.TextColumn(width="small"),
                "Due Date": st.column_config.TextColumn(width="small"),
                "Expected File Name": st.column_config.TextColumn(width="large"),
                "PDF Files": st.column_config.NumberColumn(width="small"),
                "Notes": st.column_config.TextColumn(width="large"),
            }

            display_table(
                filtered,
                columns=selected_columns,
                rename=register_rename,
                height=table_height,
                row_height=row_height,
                column_config=column_config,
                key="document_register_table",
            )

        export_col_1, export_col_2 = st.columns([1, 4])
        with export_col_1:
            st.download_button(
                "Export current view as CSV",
                data=filtered.drop(columns=["id"], errors="ignore").to_csv(index=False).encode("utf-8-sig"),
                file_name="document_register_export.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with export_col_2:
            st.caption(
                f"Export includes {len(filtered)} filtered record(s) and the selected register fields."
            )


# -----------------------------
# Quality review
# -----------------------------

elif page == "Quality review":
    render_section_header(
        "Assistant quality review",
        "Automated checks identify possible issues, but every decision is completed by a person with a reviewer name, approval decision and comments.",
    )

    duplicate_group_count = (
        exact_duplicates_df["duplicate_group"].nunique()
        if not exact_duplicates_df.empty
        else 0
    )

    missing_df = find_missing_metadata(documents_df)
    date_issues_df = find_date_sequence_issues(documents_df)
    filename_issues_df = find_filename_issues(documents_df)

    render_metric_cards(
        [
            ("Health score", f"{health_score}/100", "Rule-based register indicator", health_class),
            ("Detected findings", len(review_queue_df), "Synced to manual review", "health-watch" if len(review_queue_df) else "health-good"),
            ("Exact duplicate groups", duplicate_group_count, "Same project + discipline + number + title + revision", "health-risk" if duplicate_group_count else "health-good"),
            ("Missing metadata", len(missing_df), "Records affected", "health-watch" if len(missing_df) else "health-good"),
            ("Overdue records", len(overdue_df), "Open and past due", "health-risk" if len(overdue_df) else "health-good"),
            ("Missing PDF files", len(missing_pdf_df), "Register rows without attachment", "health-watch" if len(missing_pdf_df) else "health-good"),
        ]
    )

    st.subheader("Detected findings")
    if review_queue_df.empty:
        st.success("No automated quality findings are currently open.")
    else:
        severity_filter = st.multiselect(
            "Filter by severity",
            ["Critical", "Warning", "Review"],
            default=["Critical", "Warning", "Review"],
        )
        filtered_queue = review_queue_df[
            review_queue_df["severity"].isin(severity_filter)
        ]
        display_table(
            filtered_queue,
            rename={
                "severity": "Severity",
                "document_number": "Document Number",
                "revision": "Revision",
                "issue": "Issue",
                "recommended_action": "Recommended Action",
            },
            height=430,
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

    with st.expander("Overdue open records", expanded=False):
        if overdue_df.empty:
            st.success("No open records are overdue.")
        else:
            display_table(
                overdue_df,
                columns=[
                    "document_number",
                    "revision",
                    "title",
                    "status",
                    "owner",
                    "due_date",
                    "days_overdue",
                ],
                height=300,
            )

    with st.expander("Date sequence issues", expanded=False):
        if date_issues_df.empty:
            st.success("No records have a created date later than their due date.")
        else:
            display_table(
                date_issues_df,
                columns=[
                    "document_number",
                    "revision",
                    "created_date",
                    "due_date",
                ],
                height=260,
            )

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
        "Manual document review",
        "Inspect the affected records and PDFs, record a reviewer, add mandatory comments and approve the decision. The system never archives uncertain records automatically.",
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
                                "Due Date",
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
                        "Due Date",
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
