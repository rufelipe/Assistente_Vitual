import hashlib
import json
import os
import threading
from datetime import datetime, timezone

from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

_lock = threading.Lock()
_last_snapshot = None


def _credentials():
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not raw:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON não configurada.")
    try:
        info = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON não contém JSON válido.") from exc
    return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)


def _config():
    spreadsheet_id = os.environ.get("GOOGLE_SHEET_ID", "").strip()
    range_name = os.environ.get("GOOGLE_SHEET_RANGE", "").strip()
    if not spreadsheet_id:
        raise RuntimeError("GOOGLE_SHEET_ID não configurado.")
    if not range_name:
        raise RuntimeError("GOOGLE_SHEET_RANGE não configurado.")
    return spreadsheet_id, range_name


def _read_values():
    spreadsheet_id, range_name = _config()
    service = build("sheets", "v4", credentials=_credentials(), cache_discovery=False)
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=range_name)
        .execute()
    )
    return result.get("values", [])


def _snapshot(values):
    normalized = json.dumps(values, ensure_ascii=False, sort_keys=False, separators=(",", ":"))
    return {
        "hash": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        "values": values,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def _diff(previous, current):
    if not previous:
        return []
    old = previous.get("values", [])
    new = current.get("values", [])
    changes = []
    max_rows = max(len(old), len(new))
    for r in range(max_rows):
        old_row = old[r] if r < len(old) else []
        new_row = new[r] if r < len(new) else []
        max_cols = max(len(old_row), len(new_row))
        for c in range(max_cols):
            before = old_row[c] if c < len(old_row) else ""
            after = new_row[c] if c < len(new_row) else ""
            if before != after:
                changes.append({
                    "row": r + 1,
                    "column": c + 1,
                    "before": before,
                    "after": after,
                })
    return changes


def check_for_changes():
    global _last_snapshot
    current = _snapshot(_read_values())
    with _lock:
        previous = _last_snapshot
        _last_snapshot = current
    return {
        "changed": bool(previous and previous["hash"] != current["hash"]),
        "changes": _diff(previous, current),
        "checked_at": current["checked_at"],
    }


def read_sheet():
    values = _read_values()
    return {"values": values, "checked_at": datetime.now(timezone.utc).isoformat()}
