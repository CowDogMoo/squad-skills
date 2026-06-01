#!/usr/bin/env python3
"""Create a Google Doc weekly planner by copying a publicly-shared template.

Usage:
    python3 setup.py --start-date 2026-06-07
    python3 setup.py --start-date 2026-06-07 --title "My Family Planner"

The template (`TEMPLATE_ID` below) is a fully-styled planner doc shared
"Anyone with the link → Viewer". This script:

  1. Copies it into the running user's Drive via Drive API `files.copy`.
  2. Substitutes the week's dates into the placeholders the template carries.

Auth: expects `credentials.json` (Google Cloud Console > APIs & Services >
OAuth 2.0 Client ID > "Desktop app") in the current directory. First run
opens a browser for OAuth consent and writes `token.json`. Subsequent runs
reuse the token. Required scopes: `documents` (substitute placeholders) +
`drive.file` (copy the template into the user's Drive).
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

# Publicly-shared template doc (planner with styling intact, content cells
# blank, and dates substituted with placeholders).
TEMPLATE_ID = "1EROlprviDJKVN6AwWf-AV1prtXsbcSfHd2CmCFhOI-k"

WEEKDAY_KEYS = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]


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


def main():
    ap = argparse.ArgumentParser(description="Bootstrap a Google Doc weekly planner from the public template.")
    ap.add_argument("--title", default="Weekly Planner", help="Document title")
    ap.add_argument("--start-date", required=True, help="The Sunday that anchors the planner's first week (YYYY-MM-DD)")
    args = ap.parse_args()

    start = datetime.datetime.strptime(args.start_date, "%Y-%m-%d").date()
    if start.weekday() != 6:
        sys.exit(f"--start-date must be a Sunday; got {start.strftime('%A')} {start}")

    creds = auth()
    drive = build("drive", "v3", credentials=creds)
    docs = build("docs", "v1", credentials=creds)

    new = drive.files().copy(fileId=TEMPLATE_ID, body={"name": args.title}).execute()
    doc_id = new["id"]
    print(f"copied template → {args.title!r}  file_id={doc_id}", file=sys.stderr)

    dates = [start + datetime.timedelta(days=i) for i in range(7)]
    replacements = {
        "{{WEEK_DATE}}": fmt_long(start),
        "{{GROCERIES_DATE}}": fmt_short(start),
    }
    for key, date in zip(WEEKDAY_KEYS, dates):
        replacements[f"{{{{{key}_DATE}}}}"] = fmt_short(date)

    requests = [
        {"replaceAllText": {
            "containsText": {"text": placeholder, "matchCase": True},
            "replaceText": value,
        }}
        for placeholder, value in replacements.items()
    ]
    docs.documents().batchUpdate(documentId=doc_id, body={"requests": requests}).execute()
    print(f"substituted {len(replacements)} placeholders", file=sys.stderr)

    print()
    print(f"Doc URL: https://docs.google.com/document/d/{doc_id}/edit")
    print(f"file_id: {doc_id}")
    print()
    print("Add the file_id to your squad config / agent vars so the weekly-planner")
    print("agent knows which doc to read from.")


if __name__ == "__main__":
    main()
