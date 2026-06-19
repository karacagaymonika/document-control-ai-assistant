import sqlite3
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
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

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
        connection.commit()


def add_document(document):
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO documents (
                document_number,
                title,
                project,
                discipline,
                revision,
                status,
                owner,
                originator,
                created_date,
                due_date,
                file_name,
                notes
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


def get_documents():
    with get_connection() as connection:
        return pd.read_sql_query(
            """
            SELECT
                d.*,
                COUNT(f.id) AS pdf_count
            FROM documents AS d
            LEFT JOIN document_files AS f
                ON f.document_id = d.id
            GROUP BY d.id
            ORDER BY d.id DESC
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
                document_id,
                project,
                discipline,
                original_file_name,
                stored_file_name,
                stored_path,
                mime_type,
                file_size,
                sha256
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
            SELECT
                f.*,
                d.document_number,
                d.title,
                d.revision,
                d.status
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
            SELECT
                f.*,
                d.document_number,
                d.revision,
                d.title
            FROM document_files AS f
            JOIN documents AS d ON d.id = f.document_id
            WHERE f.sha256 = ?
            """,
            (str(sha256),),
        ).fetchone()
        return dict(row) if row else None


def update_document_status(document_id, new_status):
    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE documents
            SET status = ?
            WHERE id = ?
            """,
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
