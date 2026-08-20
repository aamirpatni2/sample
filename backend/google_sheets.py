import csv
import io
import re
from datetime import date, datetime

import httpx


def _normalize_to_csv_url(url: str) -> str:
    match = re.search(r'/spreadsheets/d/([a-zA-Z0-9_-]+)', url)
    if not match:
        raise ValueError("Not a valid Google Sheets URL — make sure you pasted a Google Sheets link")
    sheet_id = match.group(1)
    gid_match = re.search(r'[?&]gid=(\d+)', url)
    gid = gid_match.group(1) if gid_match else '0'
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"


def _find_col(row: dict, keyword: str) -> str | None:
    for k, v in row.items():
        if keyword.lower() in k.lower():
            return (v or '').strip()
    return None


def _date_matches_today(date_str: str) -> bool:
    if not date_str:
        return False
    today = date.today()
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%B %d %Y', '%b %d %Y', '%d %B %Y', '%d-%m-%Y'):
        try:
            parsed = datetime.strptime(date_str.strip(), fmt).date()
            if parsed == today:
                return True
        except ValueError:
            continue
    return False


def fetch_morning_plan(csv_url: str) -> list[dict]:
    export_url = _normalize_to_csv_url(csv_url)
    try:
        r = httpx.get(export_url, timeout=10, follow_redirects=True)
        r.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise ValueError(f"Google Sheets returned HTTP {e.response.status_code} — make sure the sheet is shared publicly")
    except Exception as e:
        raise ValueError(f"Could not fetch sheet: {e}")

    reader = csv.DictReader(io.StringIO(r.text))
    results = []
    for i, row in enumerate(reader):
        date_val = _find_col(row, 'date') or ''
        if not _date_matches_today(date_val):
            continue
        results.append({
            "topic": _find_col(row, 'topic') or _find_col(row, 'headline') or _find_col(row, 'content') or '',
            "platform_target": _find_col(row, 'platform') or '',
            "priority": str(i + 1),
            "notes": _find_col(row, 'notes') or _find_col(row, 'note') or '',
        })
    return results
