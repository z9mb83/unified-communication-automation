"""Authorize Gmail accounts for exactly one selected brand."""

from __future__ import annotations

import argparse

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.errors import HttpError
from googleapiclient.discovery import build

from app.config_loader import BRAND_ORDER, GMAIL_SCOPES, ensure_runtime_directories, load_brand_config, load_runtime_config


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--brand", required=True, choices=BRAND_ORDER)
    parser.add_argument("--account", help="Authorize only this configured Gmail account for the selected brand.")
    args = parser.parse_args()

    runtime = load_runtime_config()
    brand = load_brand_config(args.brand)
    ensure_runtime_directories([brand])

    if not runtime.google_oauth_client_file.exists():
        raise FileNotFoundError(f"OAuth client file not found: {runtime.google_oauth_client_file}")

    accounts = brand.gmail_accounts
    if args.account:
        requested_account = args.account.strip().lower()
        if requested_account not in brand.gmail_accounts:
            raise ValueError(f"{requested_account} is not configured for brand {brand.brand_id}")
        accounts = [requested_account]

    for mailbox in accounts:
        token_path = brand.token_path_for(mailbox)
        print("\n" + "=" * 72)
        print(f"Brand: {brand.brand_name}")
        print(f"Authorize this exact account: {mailbox}")
        print(f"Token will be saved only here: {token_path}")
        print("If Google shows a different Gmail account, choose 'Use another account' and select the account above.")
        flow = InstalledAppFlow.from_client_secrets_file(str(runtime.google_oauth_client_file), GMAIL_SCOPES)
        credentials = flow.run_local_server(
            port=0,
            open_browser=True,
            access_type="offline",
            prompt="select_account consent",
            login_hint=mailbox,
        )
        service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
        try:
            profile = service.users().getProfile(userId="me").execute()
            signed_in = str(profile.get("emailAddress", "")).strip().lower()
            if signed_in != mailbox.lower():
                raise RuntimeError(
                    f"Wrong account authorized. Expected {mailbox}, but Google returned {signed_in}. "
                    "No token was saved."
                )
        except HttpError as error:
            raise RuntimeError(
                f"Could not verify signed-in Gmail account for {mailbox}. No token was saved."
            ) from error
        token_path.write_text(credentials.to_json(), encoding="utf-8")
        print(f"Saved token for {mailbox}.")
    print(f"\nAuthorization completed for brand: {brand.brand_id}")


if __name__ == "__main__":
    main()
