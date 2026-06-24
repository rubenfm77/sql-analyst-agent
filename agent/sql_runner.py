"""
Safe SQL execution layer: only SELECT statements, row cap, timeout guard.
"""

from __future__ import annotations
import re
import sqlite3
import threading
from pathlib import Path

import pandas as pd

DB_PATH   = Path(__file__).parent.parent / "bank.db"
ROW_LIMIT = 500
TIMEOUT_S = 15

# Tokens that can never appear in a safe read-only query
_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|REPLACE|TRUNCATE|PRAGMA|ATTACH|DETACH)\b",
    re.IGNORECASE,
)


class SQLError(Exception):
    pass


class UnsafeQueryError(SQLError):
    pass


def _clean(sql: str) -> str:
    """Strip markdown fences and leading/trailing whitespace."""
    sql = sql.strip()
    sql = re.sub(r"^```[a-z]*\n?", "", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\n?```$", "", sql)
    return sql.strip().rstrip(";")


def validate(sql: str) -> str:
    """Raise UnsafeQueryError if the query is not a safe SELECT."""
    sql = _clean(sql)
    first_token = sql.split()[0].upper() if sql.split() else ""
    if first_token != "SELECT":
        raise UnsafeQueryError(
            f"Only SELECT statements are allowed (got: '{first_token}')."
        )
    if _FORBIDDEN.search(sql):
        m = _FORBIDDEN.search(sql)
        raise UnsafeQueryError(f"Forbidden keyword detected: '{m.group()}'.")
    return sql


def run(sql: str, db_path: Path = DB_PATH, row_limit: int = ROW_LIMIT) -> pd.DataFrame:
    """
    Execute a validated SELECT and return results as a DataFrame.
    Raises SQLError on any DB or safety problem.
    """
    sql = validate(sql)

    # Inject LIMIT if absent
    if not re.search(r"\bLIMIT\b", sql, re.IGNORECASE):
        sql = f"{sql} LIMIT {row_limit}"

    result: list   = []
    error:  list   = []
    cols:   list   = []

    def _execute():
        try:
            con = sqlite3.connect(db_path, timeout=TIMEOUT_S)
            con.row_factory = sqlite3.Row
            cur = con.execute(sql)
            cols.extend([d[0] for d in cur.description])
            result.extend(cur.fetchall())
            con.close()
        except Exception as exc:       # noqa: BLE001
            error.append(exc)

    t = threading.Thread(target=_execute, daemon=True)
    t.start()
    t.join(timeout=TIMEOUT_S + 2)

    if t.is_alive():
        raise SQLError("Query timed out after 15 seconds.")
    if error:
        raise SQLError(str(error[0]))

    rows = [dict(r) for r in result]
    return pd.DataFrame(rows, columns=cols) if rows else pd.DataFrame(columns=cols)
