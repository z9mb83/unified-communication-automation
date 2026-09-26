"""Small Google Sheets API wrapper with explicit dry-run protection."""

from __future__ import annotations

from typing import Any, Iterable

import google.auth
from google.auth.exceptions import DefaultCredentialsError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.config_loader import SHEETS_SCOPES, load_runtime_config


def load_sheets_credentials() -> Credentials:
    """Load the dedicated local Sheets token, falling back to ADC on a VM."""
    runtime = load_runtime_config()
    token_path = runtime.google_sheets_token_file
    if token_path.exists():
        try:
            credentials = Credentials.from_authorized_user_file(str(token_path), SHEETS_SCOPES)
        except Exception as error:
            raise DefaultCredentialsError(
                "The shared Google Sheets token could not be loaded. "
                "Run: python authorize_sheets.py --replace"
            ) from error
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            token_path.write_text(credentials.to_json(), encoding="utf-8")
        if credentials.valid:
            return credentials
        raise DefaultCredentialsError(
            "The shared Google Sheets token is invalid. "
            "Run: python authorize_sheets.py --replace"
        )

    try:
        credentials, _ = google.auth.default(scopes=SHEETS_SCOPES)
        return credentials
    except DefaultCredentialsError as error:
        raise DefaultCredentialsError(
            "No Google Sheets credentials are available. Run: python authorize_sheets.py"
        ) from error


class SheetClient:
    def __init__(self, spreadsheet_id: str, dry_run: bool = False) -> None:
        self.spreadsheet_id = spreadsheet_id
        self.dry_run = dry_run
        credentials = load_sheets_credentials()
        self.service = build("sheets", "v4", credentials=credentials, cache_discovery=False)

    def spreadsheet_metadata(self) -> dict[str, Any]:
        return self.service.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute()

    def sheet_ids(self) -> dict[str, int]:
        metadata = self.spreadsheet_metadata()
        return {
            item["properties"]["title"]: item["properties"]["sheetId"]
            for item in metadata.get("sheets", [])
        }

    def get(self, range_name: str) -> list[list[Any]]:
        result = (
            self.service.spreadsheets()
            .values()
            .get(spreadsheetId=self.spreadsheet_id, range=range_name)
            .execute()
        )
        return result.get("values", [])

    def update(self, range_name: str, values: list[list[Any]]) -> None:
        if self.dry_run:
            raise RuntimeError(f"dry-run blocked Sheets update to {range_name}")
        (
            self.service.spreadsheets()
            .values()
            .update(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                valueInputOption="USER_ENTERED",
                body={"values": values},
            )
            .execute()
        )

    def batch_values(self, updates: Iterable[tuple[str, list[list[Any]]]]) -> None:
        if self.dry_run:
            raise RuntimeError("dry-run blocked Sheets batch value update")
        data = [{"range": range_name, "values": values} for range_name, values in updates]
        if not data:
            return
        (
            self.service.spreadsheets()
            .values()
            .batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body={"valueInputOption": "USER_ENTERED", "data": data},
            )
            .execute()
        )

    def append(self, range_name: str, values: list[list[Any]]) -> None:
        if self.dry_run:
            raise RuntimeError(f"dry-run blocked Sheets append to {range_name}")
        (
            self.service.spreadsheets()
            .values()
            .append(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body={"values": values},
            )
            .execute()
        )

    def batch_update(self, requests: list[dict[str, Any]]) -> dict[str, Any]:
        if self.dry_run:
            raise RuntimeError("dry-run blocked Sheets batchUpdate")
        return (
            self.service.spreadsheets()
            .batchUpdate(spreadsheetId=self.spreadsheet_id, body={"requests": requests})
            .execute()
        )
