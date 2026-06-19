import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd


DB_PATH = Path("document_control.db")
FILES_ROOT = Path("document_files")


def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _column_names(connection, table_name):
    return {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }


def _add_column_if_missing(connection, table_name, column_name, definition):
    if column_name not in _column_names(connection, table_name):
        connection.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}"
        )


def init_db():
    FILES_ROOT.mkdir(parents=True, exist_ok=True)

    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_number TEXT NOT NULL,
                title TEXT,
                project TEXT,
                discipline TEXT,
                revision TEXT,
                status TEXT,
                owner TEXT,
                originator TEXT,
                created_date TEXT,
                due_date TEXT,
                file_name TEXT,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                is_archived INTEGER NOT NULL DEFAULT 0,
                archived_at TEXT,
                archived_by TEXT,
                archive_reason TEXT,
                archive_review_case_id INTEGER
            )
            """
        )

        # Safe migration for databases created by earlier app versions.
        _add_column_if_missing(connection, "documents", "is_archived", "INTEGER NOT NULL DEFAULT 0")
        _add_column_if_missing(connection, "documents", "archived_at", "TEXT")
        _add_column_if_missing(connection, "documents", "archived_by", "TEXT")
        _add_column_if_missing(connection, "documents", "archive_reason", "TEXT")
        _add_column_if_missing(connection, "documents", "archive_review_case_id", "INTEGER")

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS document_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                project TEXT NOT NULL,
                discipline TEXT NOT NULL,
                original_file_name TEXT NOT NULL,
                stored_file_name TEXT NOT NULL,
                stored_path TEXT NOT NULL,
                mime_type TEXT NOT NULL DEFAULT 'application/pdf',
                file_size INTEGER NOT NULL DEFAULT 0,
                sha256 TEXT NOT NULL,
                uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS review_cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                issue_key TEXT NOT NULL UNIQUE,
                issue_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                project TEXT,
                discipline TEXT,
                document_number TEXT,
                title TEXT,
                revision TEXT,
                primary_document_id INTEGER,
                related_document_ids TEXT NOT NULL DEFAULT '[]',
                issue_summary TEXT NOT NULL,
                recommended_action TEXT,
                status TEXT NOT NULL DEFAULT 'Pending Review',
                decision TEXT,
                reviewer TEXT,
                comments TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TEXT
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS review_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER,
                action TEXT NOT NULL,
                reviewer TEXT NOT NULL,
                comments TEXT NOT NULL,
                details TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(case_id) REFERENCES review_cases(id) ON DELETE SET NULL
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                document_id INTEGER,
                review_case_id INTEGER,
                actor TEXT,
                comments TEXT,
                details TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_document_files_sha256
            ON document_files(sha256)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_document_files_document_id
            ON document_files(document_id)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_document_files_project_discipline
            ON document_files(project, discipline)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_documents_archived
            ON documents(is_archived)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_review_cases_status
            ON review_cases(status)
            """
        )

        # Earlier versions incorrectly treated matching titles with different
        # document numbers as a conflict. Different document numbers may
        # represent completely separate controlled documents, so unresolved
        # cases created only by that retired rule are closed automatically.
        obsolete_cases = connection.execute(
            """
            SELECT id
            FROM review_cases
            WHERE issue_type = 'Document number conflict'
              AND status IN (
                  'Pending Review',
                  'Under Review',
                  'Correction Required',
                  'Escalated'
              )
            """
        ).fetchall()

        for obsolete_case in obsolete_cases:
            case_id = int(obsolete_case["id"])
            reason = (
                "Rule corrected: matching titles with different document numbers "
                "are permitted and are not duplicate or conflict records."
            )
            connection.execute(
                """
                UPDATE review_cases
                SET status = 'Closed – Rule Updated',
                    decision = 'Not a Duplicate',
                    reviewer = 'System rule update',
                    comments = ?,
                    reviewed_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (reason, case_id),
            )
            connection.execute(
                """
                INSERT INTO review_actions (
                    case_id, action, reviewer, comments, details
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    case_id,
                    'Case closed after validation-rule correction',
                    'System rule update',
                    reason,
                    json.dumps(
                        {
                            'retired_issue_type': 'Document number conflict',
                            'new_rule': (
                                'Same titles with different document numbers are allowed.'
                            ),
                        }
                    ),
                ),
            )

        connection.commit()


def add_document(document):
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO documents (
                document_number, title, project, discipline, revision, status,
                owner, originator, created_date, due_date, file_name, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document.get("document_number", ""),
                document.get("title", ""),
                document.get("project", ""),
                document.get("discipline", ""),
                document.get("revision", ""),
                document.get("status", ""),
                document.get("owner", ""),
                document.get("originator", ""),
                document.get("created_date", ""),
                document.get("due_date", ""),
                document.get("file_name", ""),
                document.get("notes", ""),
            ),
        )
        connection.commit()
        return cursor.lastrowid


def get_documents(include_archived=False):
    archive_filter = "" if include_archived else "WHERE d.is_archived = 0"

    with get_connection() as connection:
        return pd.read_sql_query(
            f"""
            SELECT
                d.*,
                COUNT(f.id) AS pdf_count
            FROM documents AS d
            LEFT JOIN document_files AS f
                ON f.document_id = d.id
            {archive_filter}
            GROUP BY d.id
            ORDER BY d.id DESC
            """,
            connection,
        )


def get_archived_documents():
    with get_connection() as connection:
        return pd.read_sql_query(
            """
            SELECT
                d.*,
                COUNT(f.id) AS pdf_count
            FROM documents AS d
            LEFT JOIN document_files AS f
                ON f.document_id = d.id
            WHERE d.is_archived = 1
            GROUP BY d.id
            ORDER BY d.archived_at DESC, d.id DESC
            """,
            connection,
        )


def get_document(document_id):
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM documents WHERE id = ?",
            (int(document_id),),
        ).fetchone()
        return dict(row) if row else None


def add_document_file(file_record):
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO document_files (
                document_id, project, discipline, original_file_name,
                stored_file_name, stored_path, mime_type, file_size, sha256
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(file_record["document_id"]),
                file_record.get("project", ""),
                file_record.get("discipline", ""),
                file_record.get("original_file_name", ""),
                file_record.get("stored_file_name", ""),
                file_record.get("stored_path", ""),
                file_record.get("mime_type", "application/pdf"),
                int(file_record.get("file_size", 0)),
                file_record.get("sha256", ""),
            ),
        )
        connection.commit()
        return cursor.lastrowid


def get_document_files(document_id=None, project=None, discipline=None):
    where_clauses = []
    parameters = []

    if document_id is not None:
        where_clauses.append("f.document_id = ?")
        parameters.append(int(document_id))

    if project is not None:
        where_clauses.append("LOWER(TRIM(f.project)) = LOWER(TRIM(?))")
        parameters.append(str(project))

    if discipline is not None:
        where_clauses.append("LOWER(TRIM(f.discipline)) = LOWER(TRIM(?))")
        parameters.append(str(discipline))

    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses)

    with get_connection() as connection:
        return pd.read_sql_query(
            f"""
            SELECT
                f.id AS file_id,
                f.document_id,
                d.document_number,
                d.title,
                d.revision,
                d.status,
                d.is_archived,
                f.project,
                f.discipline,
                f.original_file_name,
                f.stored_file_name,
                f.stored_path,
                f.mime_type,
                f.file_size,
                f.sha256,
                f.uploaded_at
            FROM document_files AS f
            JOIN documents AS d
                ON d.id = f.document_id
            {where_sql}
            ORDER BY f.project, f.discipline, d.document_number, d.revision, f.uploaded_at DESC
            """,
            connection,
            params=parameters,
        )


def get_document_file(file_id):
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT f.*, d.document_number, d.title, d.revision, d.status
            FROM document_files AS f
            JOIN documents AS d ON d.id = f.document_id
            WHERE f.id = ?
            """,
            (int(file_id),),
        ).fetchone()
        return dict(row) if row else None


def find_document_file_by_hash(sha256):
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT f.*, d.document_number, d.revision, d.title
            FROM document_files AS f
            JOIN documents AS d ON d.id = f.document_id
            WHERE f.sha256 = ?
            """,
            (str(sha256),),
        ).fetchone()
        return dict(row) if row else None


def _safe_folder_name(value):
    cleaned = "".join(
        character if character.isalnum() or character in "._-" else "_"
        for character in str(value or "").strip()
    )
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("._-") or "Unassigned"


def update_document_details(
    document_id,
    updates,
    reviewer,
    comments,
    review_case_id=None,
):
    """Update controlled metadata and write a complete audit trail.

    Internal IDs remain hidden from users. Project, discipline and document-number
    changes also relocate linked PDF files into the correct controlled folders.
    """
    allowed_fields = [
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

    current = get_document(document_id)
    if not current:
        raise ValueError("The selected document record could not be found.")

    cleaned_updates = {
        field: str(updates.get(field, "") or "").strip()
        for field in allowed_fields
    }

    if not cleaned_updates["document_number"]:
        raise ValueError("Document Number is required.")
    if not cleaned_updates["title"]:
        raise ValueError("Document Title is required.")

    before = {field: str(current.get(field, "") or "") for field in allowed_fields}
    changed_fields = {
        field: {"before": before[field], "after": cleaned_updates[field]}
        for field in allowed_fields
        if before[field] != cleaned_updates[field]
    }

    if not changed_fields:
        return 0

    moved_files = []
    with get_connection() as connection:
        file_rows = connection.execute(
            "SELECT id, stored_file_name, stored_path FROM document_files WHERE document_id = ?",
            (int(document_id),),
        ).fetchall()

    target_directory = (
        FILES_ROOT
        / _safe_folder_name(cleaned_updates["project"])
        / _safe_folder_name(cleaned_updates["discipline"])
        / _safe_folder_name(cleaned_updates["document_number"])
    )
    target_directory.mkdir(parents=True, exist_ok=True)

    for file_row in file_rows:
        old_path = Path(file_row["stored_path"])
        new_path = target_directory / file_row["stored_file_name"]

        if old_path != new_path and old_path.exists():
            if new_path.exists():
                stem = new_path.stem
                suffix = new_path.suffix
                new_path = target_directory / f"{stem}_{file_row['id']}{suffix}"
            shutil.move(str(old_path), str(new_path))

        moved_files.append(
            {
                "file_id": int(file_row["id"]),
                "old_path": str(old_path),
                "new_path": str(new_path),
            }
        )

    assignments = ", ".join(f"{field} = ?" for field in allowed_fields)
    values = [cleaned_updates[field] for field in allowed_fields]
    now = datetime.now().isoformat(timespec="seconds")
    details = {
        "changed_fields": changed_fields,
        "before": before,
        "after": cleaned_updates,
        "moved_files": moved_files,
    }

    with get_connection() as connection:
        cursor = connection.execute(
            f"UPDATE documents SET {assignments} WHERE id = ?",
            [*values, int(document_id)],
        )

        for moved_file in moved_files:
            connection.execute(
                """
                UPDATE document_files
                SET project = ?, discipline = ?, stored_path = ?
                WHERE id = ?
                """,
                (
                    cleaned_updates["project"],
                    cleaned_updates["discipline"],
                    moved_file["new_path"],
                    moved_file["file_id"],
                ),
            )

        connection.execute(
            """
            INSERT INTO audit_log (
                event_type, document_id, review_case_id, actor, comments, details
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "Document metadata updated",
                int(document_id),
                int(review_case_id) if review_case_id is not None else None,
                reviewer,
                comments,
                json.dumps(details, ensure_ascii=False),
            ),
        )

        if review_case_id is not None:
            connection.execute(
                """
                INSERT INTO review_actions (
                    case_id, action, reviewer, comments, details
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    int(review_case_id),
                    "Metadata corrected",
                    reviewer,
                    comments,
                    json.dumps(details, ensure_ascii=False),
                ),
            )
            connection.execute(
                """
                UPDATE review_cases
                SET status = 'Under Review', updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (int(review_case_id),),
            )

        connection.commit()
        return cursor.rowcount


def update_document_status(document_id, new_status):
    with get_connection() as connection:
        cursor = connection.execute(
            "UPDATE documents SET status = ? WHERE id = ?",
            (new_status, int(document_id)),
        )
        connection.commit()
        return cursor.rowcount


def reassign_document_files(source_document_id, target_document_id):
    target = get_document(target_document_id)
    if not target:
        return 0

    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE document_files
            SET document_id = ?, project = ?, discipline = ?
            WHERE document_id = ?
            """,
            (
                int(target_document_id),
                target.get("project", ""),
                target.get("discipline", ""),
                int(source_document_id),
            ),
        )
        connection.commit()
        return cursor.rowcount


def _unlink_paths(paths):
    for path_value in paths:
        try:
            path = Path(path_value)
            if path.exists() and path.is_file():
                path.unlink()
        except OSError:
            pass


def delete_document_file(file_id):
    with get_connection() as connection:
        row = connection.execute(
            "SELECT stored_path FROM document_files WHERE id = ?",
            (int(file_id),),
        ).fetchone()
        cursor = connection.execute(
            "DELETE FROM document_files WHERE id = ?",
            (int(file_id),),
        )
        connection.commit()

    if row:
        _unlink_paths([row["stored_path"]])
    return cursor.rowcount


def delete_document(document_id):
    with get_connection() as connection:
        paths = [
            row["stored_path"]
            for row in connection.execute(
                "SELECT stored_path FROM document_files WHERE document_id = ?",
                (int(document_id),),
            ).fetchall()
        ]
        connection.execute(
            "DELETE FROM document_files WHERE document_id = ?",
            (int(document_id),),
        )
        cursor = connection.execute(
            "DELETE FROM documents WHERE id = ?",
            (int(document_id),),
        )
        connection.commit()

    _unlink_paths(paths)
    return cursor.rowcount


def delete_documents(document_ids: Iterable[int]):
    ids = sorted({int(document_id) for document_id in document_ids})
    if not ids:
        return 0

    placeholders = ",".join("?" for _ in ids)
    with get_connection() as connection:
        paths = [
            row["stored_path"]
            for row in connection.execute(
                f"SELECT stored_path FROM document_files WHERE document_id IN ({placeholders})",
                ids,
            ).fetchall()
        ]
        connection.execute(
            f"DELETE FROM document_files WHERE document_id IN ({placeholders})",
            ids,
        )
        cursor = connection.execute(
            f"DELETE FROM documents WHERE id IN ({placeholders})",
            ids,
        )
        connection.commit()

    _unlink_paths(paths)
    return cursor.rowcount


def sync_review_cases(findings):
    """Insert new findings without overwriting a human decision on an existing case."""
    if findings is None:
        return 0

    if isinstance(findings, pd.DataFrame):
        records = findings.to_dict("records")
    else:
        records = list(findings)

    inserted = 0
    with get_connection() as connection:
        for finding in records:
            issue_key = str(finding.get("issue_key", "")).strip()
            if not issue_key:
                continue

            related_ids = finding.get("related_document_ids", [])
            if isinstance(related_ids, str):
                try:
                    related_ids = json.loads(related_ids)
                except json.JSONDecodeError:
                    related_ids = []

            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO review_cases (
                    issue_key, issue_type, severity, project, discipline,
                    document_number, title, revision, primary_document_id,
                    related_document_ids, issue_summary, recommended_action
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    issue_key,
                    finding.get("issue_type", "General review"),
                    finding.get("severity", "Review"),
                    finding.get("project", ""),
                    finding.get("discipline", ""),
                    finding.get("document_number", ""),
                    finding.get("title", ""),
                    finding.get("revision", ""),
                    finding.get("record_id"),
                    json.dumps(sorted({int(value) for value in related_ids})),
                    finding.get("issue", ""),
                    finding.get("recommended_action", ""),
                ),
            )
            inserted += cursor.rowcount

            # Keep machine-detected description current, but never overwrite review fields.
            connection.execute(
                """
                UPDATE review_cases
                SET severity = ?, project = ?, discipline = ?, document_number = ?,
                    title = ?, revision = ?, primary_document_id = ?,
                    related_document_ids = ?, issue_summary = ?, recommended_action = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE issue_key = ?
                """,
                (
                    finding.get("severity", "Review"),
                    finding.get("project", ""),
                    finding.get("discipline", ""),
                    finding.get("document_number", ""),
                    finding.get("title", ""),
                    finding.get("revision", ""),
                    finding.get("record_id"),
                    json.dumps(sorted({int(value) for value in related_ids})),
                    finding.get("issue", ""),
                    finding.get("recommended_action", ""),
                    issue_key,
                ),
            )

        connection.commit()
    return inserted


def get_review_cases(statuses=None):
    where_sql = ""
    parameters = []

    if statuses:
        placeholders = ",".join("?" for _ in statuses)
        where_sql = f"WHERE status IN ({placeholders})"
        parameters.extend(statuses)

    with get_connection() as connection:
        return pd.read_sql_query(
            f"""
            SELECT *
            FROM review_cases
            {where_sql}
            ORDER BY
                CASE status
                    WHEN 'Pending Review' THEN 0
                    WHEN 'Under Review' THEN 1
                    WHEN 'Correction Required' THEN 2
                    WHEN 'Escalated' THEN 3
                    ELSE 4
                END,
                CASE severity
                    WHEN 'Critical' THEN 0
                    WHEN 'Warning' THEN 1
                    ELSE 2
                END,
                created_at DESC
            """,
            connection,
            params=parameters,
        )


def get_review_case(case_id):
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM review_cases WHERE id = ?",
            (int(case_id),),
        ).fetchone()
        return dict(row) if row else None


def get_review_actions(case_id=None):
    where_sql = ""
    parameters = []
    if case_id is not None:
        where_sql = "WHERE a.case_id = ?"
        parameters.append(int(case_id))

    with get_connection() as connection:
        return pd.read_sql_query(
            f"""
            SELECT a.*, c.issue_type, c.document_number, c.revision
            FROM review_actions AS a
            LEFT JOIN review_cases AS c ON c.id = a.case_id
            {where_sql}
            ORDER BY a.created_at DESC, a.id DESC
            """,
            connection,
            params=parameters,
        )


def record_review_decision(case_id, decision, status, reviewer, comments, details=None):
    now = datetime.now().isoformat(timespec="seconds")
    details_text = json.dumps(details or {}, ensure_ascii=False)

    with get_connection() as connection:
        connection.execute(
            """
            UPDATE review_cases
            SET status = ?, decision = ?, reviewer = ?, comments = ?,
                reviewed_at = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                status,
                decision,
                reviewer,
                comments,
                now,
                int(case_id),
            ),
        )
        connection.execute(
            """
            INSERT INTO review_actions (
                case_id, action, reviewer, comments, details
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                int(case_id),
                decision,
                reviewer,
                comments,
                details_text,
            ),
        )
        connection.commit()


def archive_documents(document_ids, reviewer, reason, review_case_id=None):
    ids = sorted({int(document_id) for document_id in document_ids})
    if not ids:
        return 0

    placeholders = ",".join("?" for _ in ids)
    now = datetime.now().isoformat(timespec="seconds")

    with get_connection() as connection:
        cursor = connection.execute(
            f"""
            UPDATE documents
            SET is_archived = 1,
                archived_at = ?,
                archived_by = ?,
                archive_reason = ?,
                archive_review_case_id = ?
            WHERE id IN ({placeholders}) AND is_archived = 0
            """,
            [now, reviewer, reason, review_case_id, *ids],
        )

        for document_id in ids:
            connection.execute(
                """
                INSERT INTO audit_log (
                    event_type, document_id, review_case_id, actor, comments, details
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "Document archived",
                    document_id,
                    review_case_id,
                    reviewer,
                    reason,
                    json.dumps({"document_id": document_id}),
                ),
            )

        connection.commit()
        return cursor.rowcount


def restore_document(document_id, reviewer, comments):
    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE documents
            SET is_archived = 0,
                archived_at = NULL,
                archived_by = NULL,
                archive_reason = NULL,
                archive_review_case_id = NULL
            WHERE id = ? AND is_archived = 1
            """,
            (int(document_id),),
        )
        connection.execute(
            """
            INSERT INTO audit_log (
                event_type, document_id, actor, comments, details
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                "Document restored",
                int(document_id),
                reviewer,
                comments,
                json.dumps({"document_id": int(document_id)}),
            ),
        )
        connection.commit()
        return cursor.rowcount


def get_audit_log(limit=500):
    with get_connection() as connection:
        return pd.read_sql_query(
            """
            SELECT
                a.event_type,
                d.document_number,
                d.title,
                d.revision,
                a.actor,
                a.comments,
                a.created_at
            FROM audit_log AS a
            LEFT JOIN documents AS d ON d.id = a.document_id
            ORDER BY a.created_at DESC, a.id DESC
            LIMIT ?
            """,
            connection,
            params=(int(limit),),
        )
