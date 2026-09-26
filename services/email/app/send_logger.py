"""Send-log helpers."""

from __future__ import annotations

import logging
import os
from datetime import datetime

from app.limit_manager import Mailbox
from app.sheet_client import SheetClient
from app.utilities import now_text


def logger_for(name: str, log_file) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        if os.getenv("RUNTIME_ENV") == "cloud_run":
            # Cloud Run captures stdout/stderr into Cloud Logging automatically;
            # there is no writable, persistent local disk to keep a log file on.
            handler = logging.StreamHandler()
        else:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            handler = logging.FileHandler(log_file, encoding="utf-8")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


def append_sheet_log(
    sheets: SheetClient,
    send_log_tab: str,
    now: datetime,
    mailbox: Mailbox,
    recipient: str,
    subject: str,
    message_id: str,
    result: str,
    error: str,
) -> None:
    sheets.append(
        f"'{send_log_tab}'!A:I",
        [[
            now_text(now),
            mailbox.email,
            recipient,
            subject,
            message_id,
            result,
            error,
            mailbox.daily_limit,
            mailbox.stage,
        ]],
    )

