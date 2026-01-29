"""
Add missing structured data to uploaded files on Commons.
Only adds labels/statements if they don't already exist.
"""

import pandas as pd
import mwclient
import os
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

EXCEL_FILE = 'nbg-beeldbank_all_24012026.xlsx'
COMMONS_USERNAME = os.getenv('COMMONS_USERNAME')
COMMONS_PASSWORD = os.getenv('COMMONS_PASSWORD')
COMMONS_USER_AGENT = os.getenv('COMMONS_USER_AGENT', 'BeeldbankNBGUploader/1.0')

# Import structured data functions
import structured_data


def log(message, level="INFO"):
    """Print a timestamped log message."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    prefix = {
        "INFO": "   ",
        "SUCCESS": "[+]",
        "ERROR": "[X]",
        "WARN": "[!]",
        "PROGRESS": ">>>"
    }.get(level, "   ")
    print(f"[{timestamp}]{prefix} {message}")


def get_commons_site():
    """Connect to Wikimedia Commons."""
    site = mwclient.Site('commons.wikimedia.org', clients_useragent=COMMONS_USER_AGENT)
    site.login(COMMONS_USERNAME, COMMONS_PASSWORD)
    return site


def check_existing_structured_data(site, mid):
    """
    Check what structured data already exists for a file.

    Returns:
        tuple: (has_labels, has_statements, label_count, statement_count)
    """
    try:
        # Note: mediainfo entities use 'statements' not 'claims'
        result = site.api('wbgetentities', ids=mid)

        if 'entities' in result and mid in result['entities']:
            entity = result['entities'][mid]
            # MediaInfo uses 'statements' instead of 'claims'
            statements = entity.get('statements', {})
            labels = entity.get('labels', {})

            label_count = len(labels)
            statement_count = sum(len(v) for v in statements.values())

            return label_count > 0, statement_count > 0, label_count, statement_count

        return False, False, 0, 0
    except Exception as e:
        log(f"Error checking structured data: {e}", "ERROR")
        return False, False, 0, 0


def get_mid_from_url(mid_url):
    """Extract M-id from URL."""
    if mid_url and pd.notna(mid_url):
        return mid_url.split('/')[-1]
    return None


def main():
    start_time = datetime.now()

    print()
    print("=" * 80)
    print("  ADD MISSING STRUCTURED DATA")
    print(f"  Started at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    # Read Excel
    log("Reading Excel file...")
    df_all = pd.read_excel(EXCEL_FILE, sheet_name='all')
    df_pd = pd.read_excel(EXCEL_FILE, sheet_name='public-domain-files')

    # Ensure structured_data_added column exists
    if 'structured_data_added' not in df_all.columns:
        df_all['structured_data_added'] = False
    if 'structured_data_added' not in df_pd.columns:
        df_pd['structured_data_added'] = False

    # Get uploaded files
    has_url = df_all['CommonsURL'].notna() & (df_all['CommonsURL'].astype(str).str.len() > 0)
    uploaded = df_all[has_url][['unique_id', 'CommonsMidURL']].to_dict('records')

    log(f"Found {len(uploaded)} uploaded files to process")
    print()

    # Connect to Commons
    log("Connecting to Wikimedia Commons...", "PROGRESS")
    site = get_commons_site()
    log(f"Logged in as: {COMMONS_USERNAME}", "SUCCESS")
    print()

    # Statistics
    stats = {
        'already_complete': 0,
        'labels_added': 0,
        'statements_added': 0,
        'labels_failed': 0,
        'statements_failed': 0,
        'skipped': 0
    }

    for i, record in enumerate(uploaded):
        unique_id = record['unique_id']
        mid_url = record['CommonsMidURL']
        mid = get_mid_from_url(mid_url)

        print(f"[{i+1}/{len(uploaded)}] {unique_id}")

        if not mid:
            log("No M-id found, skipping", "WARN")
            stats['skipped'] += 1
            continue

        # Check existing structured data
        has_labels, has_statements, label_count, statement_count = check_existing_structured_data(site, mid)

        log(f"Current state: {label_count} labels, {statement_count} statements")

        needs_labels = not has_labels
        needs_statements = not has_statements

        if not needs_labels and not needs_statements:
            log("Already has labels and statements, skipping", "SUCCESS")
            stats['already_complete'] += 1
            # Update Excel
            df_all.loc[df_all['unique_id'] == unique_id, 'structured_data_added'] = True
            df_pd.loc[df_pd['unique_id'] == unique_id, 'structured_data_added'] = True
            continue

        # Add missing labels (Dutch description)
        if needs_labels:
            log("Adding Dutch label...", "PROGRESS")
            try:
                success = structured_data.process_single(unique_id, preview_only=False)
                if success:
                    log("Label added", "SUCCESS")
                    stats['labels_added'] += 1
                else:
                    log("Failed to add label", "ERROR")
                    stats['labels_failed'] += 1
            except Exception as e:
                log(f"Error adding label: {e}", "ERROR")
                stats['labels_failed'] += 1

            time.sleep(1)  # Throttle
        else:
            log("Labels already exist, skipping")

        # Add missing statements
        if needs_statements:
            log("Adding Wikibase statements...", "PROGRESS")
            try:
                success = structured_data.process_statements_single(unique_id, preview_only=False)
                if success:
                    log("Statements added", "SUCCESS")
                    stats['statements_added'] += 1
                else:
                    log("Failed to add statements", "ERROR")
                    stats['statements_failed'] += 1
            except Exception as e:
                log(f"Error adding statements: {e}", "ERROR")
                stats['statements_failed'] += 1

            time.sleep(1)  # Throttle
        else:
            log("Statements already exist, skipping")

        # Update Excel if we added anything
        if (needs_labels and stats['labels_added'] > 0) or (needs_statements and stats['statements_added'] > 0):
            df_all.loc[df_all['unique_id'] == unique_id, 'structured_data_added'] = True
            df_pd.loc[df_pd['unique_id'] == unique_id, 'structured_data_added'] = True

        print()

        # Save Excel periodically (every 10 files)
        if (i + 1) % 10 == 0:
            log("Saving progress to Excel...", "PROGRESS")
            with pd.ExcelWriter(EXCEL_FILE, engine='openpyxl') as writer:
                df_all.to_excel(writer, sheet_name='all', index=False)
                df_pd.to_excel(writer, sheet_name='public-domain-files', index=False)

    # Final save
    log("Saving final results to Excel...", "PROGRESS")
    with pd.ExcelWriter(EXCEL_FILE, engine='openpyxl') as writer:
        df_all.to_excel(writer, sheet_name='all', index=False)
        df_pd.to_excel(writer, sheet_name='public-domain-files', index=False)

    # Summary
    end_time = datetime.now()
    duration = end_time - start_time

    print()
    print("=" * 80)
    print("  COMPLETE")
    print("=" * 80)
    print(f"  Duration: {duration}")
    print(f"  Already complete: {stats['already_complete']}")
    print(f"  Labels added: {stats['labels_added']}")
    print(f"  Labels failed: {stats['labels_failed']}")
    print(f"  Statements added: {stats['statements_added']}")
    print(f"  Statements failed: {stats['statements_failed']}")
    print(f"  Skipped: {stats['skipped']}")
    print("=" * 80)


if __name__ == "__main__":
    main()
