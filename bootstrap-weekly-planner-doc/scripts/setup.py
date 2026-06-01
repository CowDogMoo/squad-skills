#!/usr/bin/env python3
"""Create a Google Doc weekly planner with the structure the weekly-planner agent expects.

Usage:
    python3 setup.py --start-date 2026-06-07
    python3 setup.py --start-date 2026-06-07 --weeks 4 --title "My Family Planner"

Auth: expects credentials.json (Google Cloud Console > APIs & Services > OAuth 2.0
Client ID > "Desktop app") in the current directory. First run opens a browser for
OAuth consent and writes token.json. Subsequent runs reuse the token.

Required scopes: documents (to create + modify the doc), drive.file (so the script
only sees files it created — does NOT grant read access to the user's whole Drive).
"""
import argparse
import datetime
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive.file",
]

PLANNER_ROWS = [
    "Commitments",
    "Childcare",
    "Dinner (with recipe links)",
    "Notes",
]

GROCERIES_CATEGORIES = [
    "Produce",
    "Protein",
    "Dairy",
    "Pantry",
    "Frozen",
    "Refrigerated / Other",
]


def auth():
    token_path = Path("token.json")
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json())
    return creds


def fmt_long(d):
    return f"{d.strftime('%B')} {d.day}, {d.year}"


def fmt_short(d):
    return f"{d.strftime('%B')} {d.day}"


def week_heading(start):
    return f"WEEKLY FAMILY PLANNER · Week of {fmt_long(start)}"


def groceries_heading(start):
    return f"GROCERIES · Week of {fmt_short(start)}"


def column_header(date):
    return f"{date.strftime('%A').upper()} {fmt_short(date)}"


def append_week(docs, doc_id, start):
    """Append one week's section (heading + 7-col planner table + GROCERIES heading + 2-col groceries table)."""
    # Structural pass: append headings + empty tables to the doc body.
    structural = [
        {"insertText": {"endOfSegmentLocation": {}, "text": week_heading(start) + "\n"}},
        {"insertTable": {"rows": 1 + len(PLANNER_ROWS), "columns": 7, "endOfSegmentLocation": {}}},
        {"insertText": {"endOfSegmentLocation": {}, "text": "\n" + groceries_heading(start) + "\n"}},
        {"insertTable": {"rows": 2 + len(GROCERIES_CATEGORIES), "columns": 2, "endOfSegmentLocation": {}}},
        {"insertText": {"endOfSegmentLocation": {}, "text": "\n"}},
    ]
    docs.documents().batchUpdate(documentId=doc_id, body={"requests": structural}).execute()

    # Re-fetch the doc, find our two newly-appended tables (the last two in body order),
    # and compute (cell_start_index, text) tuples for content insertion.
    doc = docs.documents().get(documentId=doc_id).execute()
    body_tables = [el for el in doc["body"]["content"] if "table" in el]
    planner_table = body_tables[-2]
    groceries_table = body_tables[-1]

    writes = []  # list of (insert_index, text)

    # Planner header row: 7 date columns.
    dates = [start + datetime.timedelta(days=i) for i in range(7)]
    for col, d in enumerate(dates):
        writes.append((cell_insert_index(planner_table, 0, col), column_header(d)))

    # Planner row labels in col 0.
    for row, label in enumerate(PLANNER_ROWS, start=1):
        writes.append((cell_insert_index(planner_table, row, 0), label))

    # GROCERIES table: row 0 = heading, row 1 = "Covers:", rows 2..N = category labels.
    writes.append((cell_insert_index(groceries_table, 0, 0), groceries_heading(start)))
    writes.append((cell_insert_index(groceries_table, 1, 0), "Covers:"))
    for row, cat in enumerate(GROCERIES_CATEGORIES, start=2):
        writes.append((cell_insert_index(groceries_table, row, 0), cat))

    # Apply insertions highest-index first so earlier inserts don't shift later positions.
    writes.sort(key=lambda w: -w[0])
    content_requests = [
        {"insertText": {"location": {"index": idx}, "text": text}}
        for idx, text in writes
    ]
    docs.documents().batchUpdate(documentId=doc_id, body={"requests": content_requests}).execute()


def cell_insert_index(table, row, col):
    """Insertion index for the start of the first paragraph in a given table cell."""
    cell = table["table"]["tableRows"][row]["tableCells"][col]
    return cell["content"][0]["startIndex"]


def main():
    ap = argparse.ArgumentParser(description="Bootstrap a Google Doc weekly planner.")
    ap.add_argument("--title", default="Family Planner", help="Document title")
    ap.add_argument("--start-date", required=True,
                    help="First week's Sunday in YYYY-MM-DD format")
    ap.add_argument("--weeks", type=int, default=1,
                    help="Number of weeks to pre-seed (default 1)")
    args = ap.parse_args()

    start = datetime.datetime.strptime(args.start_date, "%Y-%m-%d").date()
    if start.weekday() != 6:
        sys.exit(f"--start-date must be a Sunday; got {start.strftime('%A')} {start}")

    creds = auth()
    docs = build("docs", "v1", credentials=creds)

    new = docs.documents().create(body={"title": args.title}).execute()
    doc_id = new["documentId"]
    print(f"Created '{args.title}' (file_id={doc_id})", file=sys.stderr)

    for i in range(args.weeks):
        week_start = start + datetime.timedelta(weeks=i)
        append_week(docs, doc_id, week_start)
        print(f"  seeded week of {week_start}", file=sys.stderr)

    print()
    print(f"Doc URL: https://docs.google.com/document/d/{doc_id}/edit")
    print(f"file_id: {doc_id}")
    print()
    print("Add the file_id to your squad config / agent vars so the weekly-planner")
    print("agent knows which doc to read from.")


if __name__ == "__main__":
    main()
