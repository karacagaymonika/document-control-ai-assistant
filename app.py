import hashlib
import io
import re
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from database import (
    FILES_ROOT,
    add_document,
    add_document_file,
    delete_document,
    delete_document_file,
    delete_documents,
    find_document_file_by_hash,
    get_document_files,
    get_documents,
    init_db,
    reassign_document_files,
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
    "id",
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


def normalized_key(value):
    return clean_text(value).casefold()


def make_document_key(document_number, revision):
    return (
        normalized_key(document_number),
        normalized_key(revision),
    )


def existing_document_keys(df):
    if df.empty:
        return set()

    return {
        make_document_key(row["document_number"], row["revision"])
        for _, row in df.iterrows()
    }


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
    if df.empty:
        return pd.DataFrame()

    working = df.copy()
    working["_doc_key"] = working["document_number"].map(normalized_key)
    working["_rev_key"] = working["revision"].map(normalized_key)

    duplicates = working[
        working.duplicated(["_doc_key", "_rev_key"], keep=False)
    ].copy()

    if duplicates.empty:
        return pd.DataFrame()

    duplicates["duplicate_group"] = (
        duplicates["_doc_key"] + " | " + duplicates["_rev_key"]
    )

    return duplicates.drop(columns=["_doc_key", "_rev_key"]).sort_values(
        ["document_number", "revision", "id"]
    )


def find_revision_groups(df):
    if df.empty:
        return pd.DataFrame()

    working = df.copy()
    working["_doc_key"] = working["document_number"].map(normalized_key)
    working["_rev_key"] = working["revision"].map(normalized_key)

    rows = []

    for _, group in working.groupby("_doc_key"):
        distinct_revisions = sorted(
            {
                clean_text(value)
                for value in group["revision"]
                if clean_text(value) != ""
            }
        )

        if len(distinct_revisions) > 1:
            latest = group.sort_values("id", ascending=False).iloc[0]
            rows.append(
                {
                    "document_number": clean_text(latest["document_number"]),
                    "title": clean_text(latest["title"]),
                    "revision_count": len(distinct_revisions),
                    "revisions": ", ".join(distinct_revisions),
                    "latest_registered_revision": clean_text(latest["revision"]),
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

    missing = find_missing_metadata(df)
    for _, row in missing.iterrows():
        queue.append(
            {
                "severity": "Warning",
                "record_id": int(row["id"]),
                "document_number": row["document_number"],
                "revision": row["revision"],
                "issue": "Missing required metadata: " + row["missing_fields"],
                "recommended_action": "Complete the missing register fields",
            }
        )

    duplicates = find_exact_duplicates(df)
    if not duplicates.empty:
        for _, group in duplicates.groupby("duplicate_group"):
            ranked = group.sort_values("id", ascending=True)
            kept_id = int(ranked.iloc[0]["id"])

            # One finding for each extra copy. The retained record is not itself an error.
            for _, row in ranked.iloc[1:].iterrows():
                queue.append(
                    {
                        "severity": "Critical",
                        "record_id": int(row["id"]),
                        "document_number": clean_text(row["document_number"]),
                        "revision": clean_text(row["revision"]),
                        "issue": f"Extra exact duplicate; record {kept_id} can be retained",
                        "recommended_action": "Review the cleanup plan and remove this extra copy",
                    }
                )

    overdue = find_overdue_documents(df)
    if not overdue.empty:
        for _, row in overdue.iterrows():
            queue.append(
                {
                    "severity": "Warning",
                    "record_id": int(row["id"]),
                    "document_number": clean_text(row["document_number"]),
                    "revision": clean_text(row["revision"]),
                    "issue": f"Open record is {int(row['days_overdue'])} day(s) overdue",
                    "recommended_action": "Confirm the status or revise the due date",
                }
            )

    date_issues = find_date_sequence_issues(df)
    if not date_issues.empty:
        for _, row in date_issues.iterrows():
            queue.append(
                {
                    "severity": "Warning",
                    "record_id": int(row["id"]),
                    "document_number": clean_text(row["document_number"]),
                    "revision": clean_text(row["revision"]),
                    "issue": "Created date is later than due date",
                    "recommended_action": "Correct the document dates",
                }
            )

    filename_issues = find_filename_issues(df)
    if not filename_issues.empty:
        for _, row in filename_issues.iterrows():
            queue.append(
                {
                    "severity": "Review",
                    "record_id": int(row["id"]),
                    "document_number": row["document_number"],
                    "revision": row["revision"],
                    "issue": row["issue"],
                    "recommended_action": "Check the file-naming convention",
                }
            )

    missing_pdfs = find_missing_pdf_records(df)
    if not missing_pdfs.empty:
        for _, row in missing_pdfs.iterrows():
            queue.append(
                {
                    "severity": "Review",
                    "record_id": int(row["id"]),
                    "document_number": clean_text(row["document_number"]),
                    "revision": clean_text(row["revision"]),
                    "issue": "No PDF file is attached to this register record",
                    "recommended_action": "Upload the controlled PDF in PDF library",
                }
            )

    invalid_statuses = find_invalid_statuses(df)
    if not invalid_statuses.empty:
        for _, row in invalid_statuses.iterrows():
            queue.append(
                {
                    "severity": "Warning",
                    "record_id": int(row["id"]),
                    "document_number": clean_text(row["document_number"]),
                    "revision": clean_text(row["revision"]),
                    "issue": f"Unrecognised status: {clean_text(row['status'])}",
                    "recommended_action": "Replace it with an approved status value",
                }
            )

    queue_df = pd.DataFrame(queue)

    if queue_df.empty:
        return pd.DataFrame(
            columns=[
                "severity",
                "record_id",
                "document_number",
                "revision",
                "issue",
                "recommended_action",
            ]
        )

    order = {"Critical": 0, "Warning": 1, "Review": 2}
    queue_df["_order"] = queue_df["severity"].map(order).fillna(9)
    return queue_df.sort_values(["_order", "record_id"]).drop(columns="_order")


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
all_pdf_files_df = get_document_files()
missing_pdf_df = find_missing_pdf_records(documents_df)
review_queue_df = build_review_queue(documents_df)
exact_duplicates_df = find_exact_duplicates(documents_df)
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
    st.write(f"**{len(review_queue_df)}** review items")
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
            <span class="hero-badge">Quality review queue</span>
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
            ("Review queue", len(review_queue_df), "Open quality findings", ""),
            ("Register health", f"{health_score}/100", health_note, health_class),
        ]
    )

    if documents_df.empty:
        st.info("The register is empty. Add a document manually or import a CSV register.")
    else:
        left, right = st.columns([1.25, 1])

        with left:
            st.subheader("Priority actions")
            if review_queue_df.empty:
                st.success("No rule-based quality findings are currently open.")
            else:
                display_table(
                    review_queue_df.head(10),
                    rename={
                        "severity": "Severity",
                        "record_id": "ID",
                        "document_number": "Document Number",
                        "revision": "Revision",
                        "issue": "Issue",
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
                "id",
                "document_number",
                "title",
                "revision",
                "status",
                "owner",
                "due_date",
            ],
            rename={
                "id": "ID",
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
            elif make_document_key(document_number, revision) in existing_document_keys(documents_df):
                st.error(
                    "This document number and revision already exist. Add a new revision or review the existing record."
                )
            else:
                add_document(new_document)
                st.session_state["flash_message"] = (
                    "success",
                    "Document saved successfully. The form has been cleared.",
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
                prepared_df["_key"] = prepared_df.apply(
                    lambda row: make_document_key(
                        row["document_number"], row["revision"]
                    ),
                    axis=1,
                )

                invalid_rows = prepared_df[
                    (prepared_df["document_number"] == "")
                    | (prepared_df["title"] == "")
                ].copy()

                valid_rows = prepared_df.drop(index=invalid_rows.index).copy()

                duplicate_inside_mask = valid_rows.duplicated(
                    subset=["_key"], keep="first"
                )
                duplicate_inside_csv = valid_rows[duplicate_inside_mask].copy()
                valid_rows = valid_rows[~duplicate_inside_mask].copy()

                database_keys = existing_document_keys(documents_df)
                already_exists_mask = valid_rows["_key"].isin(database_keys)
                already_in_database = valid_rows[already_exists_mask].copy()
                new_rows = valid_rows[~already_exists_mask].copy()

                render_metric_cards(
                    [
                        ("CSV rows", len(prepared_df), "Rows read from file", ""),
                        ("New records", len(new_rows), "Ready to import", "health-good" if len(new_rows) else ""),
                        ("Already stored", len(already_in_database), "Skipped safely", ""),
                        ("Repeated in CSV", len(duplicate_inside_csv), "Extra copies skipped", "health-watch" if len(duplicate_inside_csv) else ""),
                        ("Invalid rows", len(invalid_rows), "Missing number or title", "health-risk" if len(invalid_rows) else ""),
                    ]
                )

                st.subheader("Import preview")
                display_table(
                    prepared_df.drop(columns="_key"),
                    height=350,
                )

                with st.expander("Rows already stored", expanded=False):
                    if already_in_database.empty:
                        st.success("No existing exact duplicates were found.")
                    else:
                        display_table(already_in_database.drop(columns="_key"), height=260)

                with st.expander("Repeated rows inside the CSV", expanded=False):
                    if duplicate_inside_csv.empty:
                        st.success("No repeated document number and revision combinations were found inside the CSV.")
                    else:
                        display_table(duplicate_inside_csv.drop(columns="_key"), height=260)

                with st.expander("Invalid rows", expanded=False):
                    if invalid_rows.empty:
                        st.success("Every row has a document number and title.")
                    else:
                        display_table(invalid_rows.drop(columns="_key"), height=260)

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
                            f"{len(new_rows)} new document record(s) imported. Existing and repeated rows were skipped.",
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
                record_choices = {
                    (
                        f"ID {int(row['id'])} · {clean_text(row['document_number'])} · "
                        f"{clean_text(row['revision']) or 'No revision'} · {clean_text(row['title'])}"
                    ): int(row["id"])
                    for _, row in discipline_records.sort_values(
                        ["document_number", "revision", "id"]
                    ).iterrows()
                }

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
                        "id",
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
                        "id": "ID",
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
                f"Export includes {len(filtered)} filtered record(s). The internal database ID is not included."
            )


# -----------------------------
# Quality review
# -----------------------------

elif page == "Quality review":
    render_section_header(
        "Assistant quality review",
        "The checks now separate true data-control problems from normal revision history. Use the review queue to decide what needs human attention.",
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
            ("Review queue", len(review_queue_df), "All findings", "health-watch" if len(review_queue_df) else "health-good"),
            ("Exact duplicate groups", duplicate_group_count, "Same number + revision", "health-risk" if duplicate_group_count else "health-good"),
            ("Missing metadata", len(missing_df), "Records affected", "health-watch" if len(missing_df) else "health-good"),
            ("Overdue records", len(overdue_df), "Open and past due", "health-risk" if len(overdue_df) else "health-good"),
            ("Missing PDF files", len(missing_pdf_df), "Register rows without attachment", "health-watch" if len(missing_pdf_df) else "health-good"),
        ]
    )

    st.subheader("Review queue")
    if review_queue_df.empty:
        st.success("No rule-based quality findings are currently open.")
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
                "record_id": "ID",
                "document_number": "Document Number",
                "revision": "Revision",
                "issue": "Issue",
                "recommended_action": "Recommended Action",
            },
            height=430,
        )

    st.divider()

    st.subheader("1. Exact duplicates — action required")
    st.caption("Only records with the same document number and the same revision appear here.")
    if exact_duplicates_df.empty:
        st.success("No exact duplicate document number and revision combinations were found.")
    else:
        display_table(
            exact_duplicates_df,
            columns=DISPLAY_COLUMNS,
            height=320,
        )
        st.info("Use Administration → Duplicate cleanup to remove the extra copies safely.")

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
                "latest_registered_revision": "Latest Registered",
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
                    "id",
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
                    "id",
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
                    "id",
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
# Revision history
# -----------------------------

elif page == "Revision history":
    render_section_header(
        "Revision history",
        "Review every registered version of a document number without treating valid revisions as duplicate errors.",
    )

    if documents_df.empty:
        st.info("No documents are available.")
    else:
        document_numbers = sorted(
            value
            for value in documents_df["document_number"].dropna().astype(str).unique()
            if clean_text(value)
        )

        selected_document = st.selectbox(
            "Select a document number",
            document_numbers,
        )

        history = documents_df[
            documents_df["document_number"].map(normalized_key)
            == normalized_key(selected_document)
        ].sort_values("id", ascending=False)

        current = history.iloc[0]

        render_metric_cards(
            [
                ("Registered versions", len(history), "Rows for this document", ""),
                ("Latest registered", clean_text(current["revision"]) or "Not set", "Based on latest database entry", ""),
                ("Current status", clean_text(current["status"]) or "Not set", "Latest registered row", ""),
                ("Owner", clean_text(current["owner"]) or "Not set", "Latest registered row", ""),
                ("Project", clean_text(current["project"]) or "Not set", "Latest registered row", ""),
            ]
        )

        display_table(
            history,
            columns=DISPLAY_COLUMNS,
            height=460,
        )

        st.subheader("Attached PDF files")
        history_files = all_pdf_files_df[
            all_pdf_files_df["document_id"].isin(history["id"].tolist())
        ].copy() if not all_pdf_files_df.empty else pd.DataFrame()
        render_attached_files(
            history_files,
            key_prefix=f"revision_{safe_folder_name(selected_document)}",
            allow_delete=False,
        )


# -----------------------------
# Administration
# -----------------------------

elif page == "Administration":
    render_section_header(
        "Register administration",
        "Manage individual records and clean existing exact duplicates. Different revisions are never removed by duplicate cleanup.",
    )

    st.subheader("Duplicate cleanup")
    st.markdown(
        """
        <div class="notice notice-safe">
            The cleanup checks only exact matches of <strong>Document Number + Revision</strong>.
            It will not delete P01, P02 or other legitimate revision history.
        </div>
        """,
        unsafe_allow_html=True,
    )

    cleanup_strategy = st.selectbox(
        "Which copy should be retained?",
        [
            "Keep most complete record (recommended)",
            "Keep oldest record",
            "Keep newest record",
        ],
    )

    cleanup_plan = build_duplicate_cleanup_plan(documents_df, cleanup_strategy)

    if cleanup_plan.empty:
        st.success("No existing exact duplicates need cleaning.")
    else:
        st.warning(
            f"The plan will keep one record per exact key and remove {len(cleanup_plan)} extra duplicate copy/copies."
        )
        display_table(
            cleanup_plan,
            rename={
                "document_number": "Document Number",
                "revision": "Revision",
                "keep_id": "Keep ID",
                "remove_id": "Remove ID",
                "kept_title": "Kept Title",
                "removed_title": "Removed Title",
                "reason": "Decision Rule",
            },
            height=330,
        )

        st.download_button(
            "Download cleanup plan",
            data=cleanup_plan.to_csv(index=False).encode("utf-8-sig"),
            file_name="duplicate_cleanup_plan.csv",
            mime="text/csv",
        )

        confirm_cleanup = st.checkbox(
            "I reviewed the cleanup plan and understand that the listed Remove IDs will be deleted."
        )

        if st.button(
            f"Remove {len(cleanup_plan)} duplicate copy/copies",
            type="primary",
            disabled=not confirm_cleanup,
            use_container_width=True,
        ):
            for _, cleanup_row in cleanup_plan.iterrows():
                reassign_document_files(
                    int(cleanup_row["remove_id"]),
                    int(cleanup_row["keep_id"]),
                )
            removed_count = delete_documents(cleanup_plan["remove_id"].tolist())
            st.session_state["flash_message"] = (
                "success",
                f"Duplicate cleanup completed. {removed_count} extra record(s) were removed and legitimate revisions were preserved.",
            )
            st.rerun()

    st.divider()
    st.subheader("Manage one document")

    if documents_df.empty:
        st.info("No documents are available to manage.")
    else:
        choices = {
            f"ID {int(row['id'])} · {clean_text(row['document_number'])} · {clean_text(row['revision']) or 'No revision'} · {clean_text(row['title'])}": int(row["id"])
            for _, row in documents_df.iterrows()
        }

        selected_label = st.selectbox("Select a record", list(choices.keys()))
        selected_id = choices[selected_label]
        selected_df = documents_df[documents_df["id"] == selected_id]

        display_table(selected_df, columns=DISPLAY_COLUMNS, height=180)

        st.markdown("#### Attached PDF files")
        selected_files = get_document_files(document_id=selected_id)
        render_attached_files(
            selected_files,
            key_prefix=f"admin_{selected_id}",
            allow_delete=True,
        )

        action_left, action_right = st.columns(2)

        with action_left:
            with st.form("status_update_form"):
                current_status = clean_text(selected_df.iloc[0]["status"])
                default_status_index = (
                    STATUS_OPTIONS.index(current_status)
                    if current_status in STATUS_OPTIONS
                    else 0
                )
                new_status = st.selectbox(
                    "Update status",
                    STATUS_OPTIONS,
                    index=default_status_index,
                )
                update_submitted = st.form_submit_button(
                    "Save status",
                    type="primary",
                    use_container_width=True,
                )

                if update_submitted:
                    update_document_status(selected_id, new_status)
                    st.session_state["flash_message"] = (
                        "success",
                        f"Status updated for record ID {selected_id}.",
                    )
                    st.rerun()

        with action_right:
            st.markdown("#### Delete selected record")
            confirm_delete = st.checkbox(
                "I understand this removes the selected row from the register.",
                key="confirm_single_delete",
            )

            if st.button(
                "Delete selected record",
                disabled=not confirm_delete,
                use_container_width=True,
            ):
                delete_document(selected_id)
                st.session_state["flash_message"] = (
                    "success",
                    f"Record ID {selected_id} was deleted.",
                )
                st.rerun()
