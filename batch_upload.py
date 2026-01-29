"""
Batch upload script for uploading multiple files by unique_id.

Reads IDs from batch_upload_ids.txt and uploads each one with structured data.

Usage:
    python batch_upload.py              # Upload all IDs in batch_upload_ids.txt
    python batch_upload.py --preview    # Preview only
    python batch_upload.py --delay 10   # Custom delay between uploads
"""

import os
import sys
import time
import argparse
from datetime import datetime
import pandas as pd

# Import the uploader module
from uploader import (
    load_excel, get_record_by_id, load_category_exclusions, filter_categories_for_record,
    get_commons_site, check_file_exists, upload_file, get_commons_mid, save_commons_url,
    add_structured_data_after_upload, throttled_sleep, exponential_backoff,
    log, print_progress_header, DEFAULT_DELAY, EXCLUSIONS_FILE
)
from commons_template import generate_wikitext, get_upload_filename, get_local_filepath, safe_str

EXCEL_FILE = 'nbg-beeldbank_all_24012026.xlsx'
IDS_FILE = 'batch_upload_ids.txt'


def load_ids_to_upload():
    """Load IDs from batch_upload_ids.txt"""
    if not os.path.exists(IDS_FILE):
        print(f"ERROR: {IDS_FILE} not found")
        return []

    with open(IDS_FILE, 'r') as f:
        ids = [line.strip() for line in f if line.strip()]
    return ids


def batch_upload_by_ids(ids, preview_only=False, delay=DEFAULT_DELAY):
    """
    Upload a list of records by unique_id.

    Args:
        ids: List of unique_ids to upload
        preview_only: If True, only preview without uploading
        delay: Delay between uploads in seconds
    """
    start_time = datetime.now()
    total_count = len(ids)

    print()
    print("=" * 80)
    print(f"  BATCH UPLOAD BY ID - {total_count} files")
    print(f"  Started at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    df = load_excel()

    # Load category exclusions
    exclusions = load_category_exclusions()
    if exclusions:
        log(f"Loaded category exclusions from {EXCLUSIONS_FILE}")

    if not preview_only:
        log("Connecting to Wikimedia Commons...", "PROGRESS")
        site = get_commons_site()
        log("Connected successfully", "SUCCESS")
    else:
        site = None
        log("PREVIEW MODE - No uploads will be performed", "WARN")

    successful = 0
    failed = 0
    skipped = 0
    structured_data_success = 0
    structured_data_failed = 0

    for i, unique_id in enumerate(ids):
        current_num = i + 1

        row = get_record_by_id(df, unique_id)
        if row is None:
            log(f"Record {unique_id} not found in Excel", "ERROR")
            failed += 1
            continue

        titel = safe_str(row.get('titel', ''))
        filename = get_upload_filename(row)
        local_path = get_local_filepath(row)

        print_progress_header(current_num, total_count, unique_id, titel)

        # Check local file
        if not os.path.exists(local_path):
            log(f"Local file not found: {local_path}", "WARN")
            log("SKIPPED - File not found", "WARN")
            skipped += 1
            continue

        log(f"Local file: {os.path.basename(local_path)}")

        # Apply category exclusions
        if exclusions:
            original_cats = safe_str(row.get('commons_categories', ''))
            filtered_cats = filter_categories_for_record(unique_id, original_cats, exclusions)
            if original_cats != filtered_cats:
                row = row.copy()
                row['commons_categories'] = filtered_cats
                log(f"Categories filtered: {original_cats} -> {filtered_cats}")

        if preview_only:
            wikitext = generate_wikitext(row)
            log(f"Filename: {filename}")
            log(f"Categories: {safe_str(row.get('commons_categories', ''))}")
            log("PREVIEW - Would upload this file", "INFO")
            successful += 1
            continue

        # Check if already exists on Commons
        log("Checking if file exists on Commons...")
        if check_file_exists(site, filename):
            log("File already exists on Commons", "WARN")
            log("SKIPPED - Already uploaded", "WARN")
            skipped += 1
            continue

        # Upload
        try:
            log(f"Uploading: {filename}...", "PROGRESS")
            wikitext = generate_wikitext(row)
            upload_file(site, local_path, filename, wikitext)

            commons_url = f"https://commons.wikimedia.org/wiki/File:{filename.replace(' ', '_')}"
            commons_mid_url = get_commons_mid(site, filename)
            log(f"Upload successful!", "SUCCESS")
            log(f"Commons URL: {commons_url}")

            # Save the Commons URL and M-id URL to Excel
            try:
                save_commons_url(unique_id, commons_url, commons_mid_url)
                log("Saved URLs to Excel", "SUCCESS")
            except Exception as e:
                log(f"Could not save to Excel: {e}", "WARN")

            successful += 1

            # Add structured data immediately after upload
            log("", "INFO")
            if add_structured_data_after_upload(unique_id):
                structured_data_success += 1
            else:
                structured_data_failed += 1

            # Throttled delay between files
            if i < len(ids) - 1:
                log("", "INFO")
                throttled_sleep(delay, add_jitter=True)

        except Exception as e:
            log(f"Upload failed: {e}", "ERROR")
            failed += 1

            # Add extra delay after failures
            if i < len(ids) - 1:
                backoff_delay = exponential_backoff(0, delay)
                log(f"Adding cooldown after failure...")
                throttled_sleep(backoff_delay, add_jitter=True)

    # Final summary
    end_time = datetime.now()
    duration = end_time - start_time

    print()
    print("=" * 80)
    print(f"  BATCH COMPLETE")
    print("=" * 80)
    print(f"  Duration: {duration}")
    print(f"  Uploads:  {successful} successful, {failed} failed, {skipped} skipped")
    print(f"  Structured data: {structured_data_success} successful, {structured_data_failed} failed")
    print("=" * 80)

    return successful, failed, skipped


def main():
    parser = argparse.ArgumentParser(description='Batch upload by ID list')
    parser.add_argument('--preview', '-p', action='store_true', help='Preview only')
    parser.add_argument('--delay', '-d', type=int, default=DEFAULT_DELAY,
                        help=f'Delay between uploads (default: {DEFAULT_DELAY})')

    args = parser.parse_args()

    ids = load_ids_to_upload()
    if not ids:
        print("No IDs to upload")
        return

    print(f"Loaded {len(ids)} IDs from {IDS_FILE}")
    batch_upload_by_ids(ids, preview_only=args.preview, delay=args.delay)


if __name__ == "__main__":
    main()
