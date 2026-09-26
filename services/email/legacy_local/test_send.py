"""Preview or explicitly send one controlled test email."""

from __future__ import annotations

import argparse
from datetime import datetime

from app.config_loader import BRAND_ORDER, ensure_runtime_directories, load_brand_config, load_runtime_config
from app.gmail_client import send_email
from app.utilities import is_valid_email, timezone_for


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--brand", required=True, choices=BRAND_ORDER)
    parser.add_argument("--from-mailbox", required=True)
    parser.add_argument("--to", required=True)
    parser.add_argument("--cc", default=None)
    parser.add_argument("--confirm-send", action="store_true")
    args = parser.parse_args()

    runtime = load_runtime_config()
    brand = load_brand_config(args.brand)
    ensure_runtime_directories([brand])
    sender = args.from_mailbox.strip().lower()
    recipient = args.to.strip().lower()
    cc_email = brand.mandatory_cc if args.cc is None else args.cc.strip()

    if sender not in brand.gmail_accounts:
        raise ValueError(f"{sender} is not configured for {brand.brand_id}")
    if not is_valid_email(recipient):
        raise ValueError("Test recipient is not a valid email address")

    print(f"Brand: {brand.brand_name}")
    print(f"Sender: {sender}")
    print(f"Recipient: {recipient}")
    print(f"Cc: {cc_email or '(none)'}")
    print(f"Mode: {'SEND' if args.confirm_send else 'PREVIEW ONLY'}")
    if not args.confirm_send:
        print("Preview only. Add --confirm-send to send this controlled test message.")
        return

    subject = f"{brand.brand_name} automation test"
    body = (
        f"Hello,\n\nThis is a controlled test of the {brand.brand_name} Gmail API automation.\n\n"
        f"Warm regards,\n{brand.brand_name}"
    )
    message_id = send_email(brand, sender, recipient, cc_email, subject, body)
    log_path = brand.log_directory / "test_sends.log"
    now = datetime.now(timezone_for(runtime.timezone)).isoformat()
    log_path.write_text(
        (log_path.read_text(encoding="utf-8") if log_path.exists() else "")
        + f"{now} brand={brand.brand_id} sender={sender} recipient={recipient} message_id={message_id}\n",
        encoding="utf-8",
    )
    print(f"Test sent successfully. Gmail Message ID: {message_id}")


if __name__ == "__main__":
    main()
