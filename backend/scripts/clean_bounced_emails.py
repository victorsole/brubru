"""
Clean Bounced Emails

Connects to Gmail via IMAP, finds bounce/delivery failure messages,
extracts the bounced email addresses, and removes them from the CSV files.

Usage:
    # Preview bounced emails (no changes)
    python scripts/clean_bounced_emails.py

    # Remove bounced emails from CSVs
    python scripts/clean_bounced_emails.py --apply
"""

import csv
import email
import imaplib
import logging
import os
import re
import sys
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EMAIL_DIR = os.path.join(PROJECT_ROOT, "data", "emails")

CSV_FILES = [
    os.path.join(EMAIL_DIR, "mep_emails.csv"),
    os.path.join(EMAIL_DIR, "com_emails.csv"),
    os.path.join(EMAIL_DIR, "consil_emails.csv"),
    os.path.join(EMAIL_DIR, "eeas_emails.csv"),
    os.path.join(EMAIL_DIR, "agencies_emails.csv"),
    os.path.join(EMAIL_DIR, "eib_emails.csv"),
    os.path.join(EMAIL_DIR, "ecb_emails.csv"),
    os.path.join(EMAIL_DIR, "curia_emails.csv"),
    os.path.join(EMAIL_DIR, "eca_emails.csv"),
    os.path.join(EMAIL_DIR, "eesc_emails.csv"),
    os.path.join(EMAIL_DIR, "omb_emails.csv"),
    os.path.join(EMAIL_DIR, "edps_emails.csv"),
    os.path.join(EMAIL_DIR, "cor_emails.csv"),
    os.path.join(EMAIL_DIR, "lobby_orgs_emails.csv"),
]

# Patterns that indicate a bounce message
BOUNCE_SENDERS = [
    "mailer-daemon@",
    "postmaster@",
    "mail-noreply@google.com",
]

BOUNCE_SUBJECTS = [
    "delivery status notification",
    "undeliverable",
    "undelivered mail",
    "mail delivery failed",
    "failure notice",
    "returned mail",
    "delivery failure",
    "message not delivered",
    "address rejected",
]

# Regex to find bounced email addresses in bounce message body
# Match any email address in bounce messages (not just EU institutions)
EMAIL_PATTERN = re.compile(
    r"[\w.\-+]+@[\w.\-]+\.\w{2,}",
    re.IGNORECASE,
)


def connect_imap() -> imaplib.IMAP4_SSL:
    """Connect to Gmail IMAP using configured credentials."""
    from core.config import settings

    imap_host = "imap.gmail.com"
    imap_port = 993

    user = settings.SMTP_USER
    password = settings.SMTP_PASSWORD

    if not user or not password:
        raise ValueError("SMTP_USER / SMTP_PASSWORD not configured")

    logger.info(f"[INFO] Connecting to IMAP as {user}...")
    conn = imaplib.IMAP4_SSL(imap_host, imap_port)
    conn.login(user, password)
    logger.info("[OK] IMAP connected")
    return conn


def find_bounced_emails(conn: imaplib.IMAP4_SSL, days_back: int = 7) -> set[str]:
    """Search Inbox, Trash, and Spam for bounce messages and extract bounced addresses."""
    bounced = set()

    since_date = (datetime.now() - timedelta(days=days_back)).strftime("%d-%b-%Y")

    # Search for messages from mailer-daemon or with bounce-like subjects
    search_queries = [
        f'(FROM "mailer-daemon" SINCE {since_date})',
        f'(FROM "postmaster" SINCE {since_date})',
        f'(FROM "mail-noreply@google.com" SINCE {since_date})',
        f'(SUBJECT "Delivery Status Notification" SINCE {since_date})',
        f'(SUBJECT "Undeliverable" SINCE {since_date})',
        f'(SUBJECT "delivery failure" SINCE {since_date})',
        f'(SUBJECT "Mail delivery failed" SINCE {since_date})',
        f'(SUBJECT "Message not delivered" SINCE {since_date})',
        f'(SUBJECT "Address not found" SINCE {since_date})',
    ]

    # Check all three folders: Inbox, Trash, and Spam
    folders = ["INBOX", "[Gmail]/Trash", "[Gmail]/Spam"]
    all_msg_ids_by_folder = {}

    for folder in folders:
        try:
            status, _ = conn.select(folder)
            if status != "OK":
                logger.warning(f"[WARN] Could not select {folder}")
                continue
        except Exception as e:
            logger.warning(f"[WARN] Error selecting {folder}: {e}")
            continue

        folder_msg_ids = set()
        for query in search_queries:
            try:
                status, data = conn.search(None, query)
                if status == "OK" and data[0]:
                    msg_ids = data[0].split()
                    folder_msg_ids.update(msg_ids)
            except Exception as e:
                logger.warning(f"[WARN] Search failed for {query} in {folder}: {e}")

        if folder_msg_ids:
            all_msg_ids_by_folder[folder] = folder_msg_ids
        logger.info(f"[{folder}] {len(folder_msg_ids)} bounce messages")

    total_msgs = sum(len(ids) for ids in all_msg_ids_by_folder.values())
    logger.info(f"[INFO] Found {total_msgs} bounce messages total")

    # Fetch messages in batches with reconnection on failure
    BATCH_SIZE = 20
    SKIP_SENDERS = {"beresol", "google.com", "mailer-daemon", "postmaster"}

    for folder, folder_msg_ids in all_msg_ids_by_folder.items():
        # Select the folder before fetching
        try:
            conn.select(folder)
        except Exception:
            conn = connect_imap()
            conn.select(folder)

        msg_id_list = sorted(folder_msg_ids)
        for batch_start in range(0, len(msg_id_list), BATCH_SIZE):
            batch = msg_id_list[batch_start : batch_start + BATCH_SIZE]
            batch_num = batch_start // BATCH_SIZE + 1
            total_batches = (len(msg_id_list) + BATCH_SIZE - 1) // BATCH_SIZE
            logger.info(f"[INFO] {folder} batch {batch_num}/{total_batches} ({len(batch)} messages)...")

            for msg_id in batch:
                try:
                    status, msg_data = conn.fetch(msg_id, "(RFC822)")
                    if status != "OK":
                        continue

                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)

                    # Extract body text
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            content_type = part.get_content_type()
                            if content_type in ("text/plain", "text/html", "message/delivery-status"):
                                try:
                                    payload = part.get_payload(decode=True)
                                    if payload:
                                        body += payload.decode("utf-8", errors="replace")
                                except Exception:
                                    pass
                    else:
                        try:
                            payload = msg.get_payload(decode=True)
                            if payload:
                                body = payload.decode("utf-8", errors="replace")
                        except Exception:
                            pass

                    # Find bounced email addresses in the bounce body
                    found = EMAIL_PATTERN.findall(body)
                    for addr in found:
                        addr_lower = addr.lower()
                        if any(skip in addr_lower for skip in SKIP_SENDERS):
                            continue
                        bounced.add(addr_lower)

                except (imaplib.IMAP4.abort, imaplib.IMAP4.error, OSError) as e:
                    logger.warning(f"[WARN] Connection lost at message {msg_id}, reconnecting...")
                    try:
                        conn = connect_imap()
                        conn.select(folder)
                    except Exception as reconn_err:
                        logger.warning(f"[WARN] Reconnect failed: {reconn_err}")
                        break
                except Exception as e:
                    logger.warning(f"[WARN] Failed to parse message {msg_id}: {e}")

            # Small delay between batches to avoid Gmail throttling
            if batch_start + BATCH_SIZE < len(msg_id_list):
                time.sleep(1)

    return bounced


def remove_from_csv(csv_path: str, bounced: set[str]) -> tuple[int, int]:
    """Remove bounced emails from a CSV file. Returns (original_count, removed_count)."""
    if not os.path.exists(csv_path):
        return 0, 0

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    original_count = len(rows)
    # Support both "email" and "contact_email" column names
    email_col = "contact_email" if "contact_email" in (fieldnames or []) else "email"
    filtered = [r for r in rows if r.get(email_col, "").lower() not in bounced]
    removed = original_count - len(filtered)

    if removed > 0:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(filtered)

    return original_count, removed


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Clean bounced emails from CSV files")
    parser.add_argument("--apply", action="store_true", help="Actually remove bounced emails from CSVs")
    parser.add_argument("--days", type=int, default=7, help="How many days back to search (default: 7)")
    args = parser.parse_args()

    # Connect to Gmail IMAP
    conn = connect_imap()

    try:
        # Find bounced emails
        bounced = find_bounced_emails(conn, days_back=args.days)
    finally:
        try:
            conn.logout()
        except Exception:
            pass  # Connection may already be closed

    if not bounced:
        logger.info("[OK] No bounced emails found - all CSVs are clean")
        return

    logger.info(f"\n[INFO] Found {len(bounced)} bounced email addresses:")
    for addr in sorted(bounced):
        logger.info(f"  - {addr}")

    if not args.apply:
        logger.info("\n[DRY-RUN] Run with --apply to remove these from CSVs")
        return

    # Remove from each CSV
    logger.info("\n[INFO] Removing bounced emails from CSVs...")
    total_removed = 0
    for csv_path in CSV_FILES:
        if not os.path.exists(csv_path):
            continue
        original, removed = remove_from_csv(csv_path, bounced)
        fname = os.path.basename(csv_path)
        if removed > 0:
            logger.info(f"  {fname}: {original} -> {original - removed} (removed {removed})")
            total_removed += removed
        else:
            logger.info(f"  {fname}: {original} (no changes)")

    logger.info(f"\n[OK] Removed {total_removed} bounced emails total")


if __name__ == "__main__":
    main()
