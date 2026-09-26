"""Authorize one dedicated local token for the shared Google Sheet.

This token is separate from every brand's Gmail token and is used only by the
Google Sheets client. It is saved only after a read-only access check succeeds.
"""

from __future__ import annotations

import argparse

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from app.config_loader import DEFAULT_SHEET_ID, SHEETS_SCOPES, load_runtime_config


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replace", action="store_true", help="Replace the existing dedicated Sheets token after a new authorization.")
    parser.add_argument("--no-browser", action="store_true", help="Print the authorization URL instead of opening a browser automatically.")
    args = parser.parse_args()

    runtime = load_runtime_config()
    token_path = runtime.google_sheets_token_file
    if not runtime.google_oauth_client_file.exists():
        raise FileNotFoundError(f"OAuth client file not found: {runtime.google_oauth_client_file}")
    if token_path.exists() and not args.replace:
        raise FileExistsError(
            f"A dedicated Google Sheets token already exists at {token_path}. "
            "Use --replace only when you intentionally need to authorize again."
        )

    print("Authorize the Google account that has access to the shared automation spreadsheet.")
    print("This grants Google Sheets access only. It does not authorize Gmail sending.")
    flow = InstalledAppFlow.from_client_secrets_file(str(runtime.google_oauth_client_file), SHEETS_SCOPES)
    credentials = flow.run_local_server(
        port=0,
        open_browser=not args.no_browser,
        access_type="offline",
        prompt="select_account consent",
    )

    service = build("sheets", "v4", credentials=credentials, cache_discovery=False)
    metadata = service.spreadsheets().get(spreadsheetId=DEFAULT_SHEET_ID, includeGridData=False).execute()
    title = str(metadata.get("properties", {}).get("title", "shared spreadsheet"))

    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(credentials.to_json(), encoding="utf-8")
    print(f"Google Sheets read access verified for: {title}")
    print(f"Dedicated Sheets token saved at: {token_path}")
    print("No email was sent and no Google Sheet cell was changed.")


if __name__ == "__main__":
    main()
