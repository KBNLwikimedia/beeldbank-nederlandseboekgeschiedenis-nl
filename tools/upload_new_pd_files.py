"""
Upload newly discovered public domain files to Wikimedia Commons.

This script uploads files that were discovered during the non-PD review process,
using the custom PD templates assigned in the template selector.

Features:
    - Uses custom PD templates from pd_templates_for_upload.json
    - Adds structured data (Dutch label + Wikibase statements) after upload
    - Updates both Excel sheets ('all' and 'public-domain-files')
    - Supports dry-run mode for testing
    - Supports resuming from a specific position
    - Saves progress periodically to avoid data loss

Usage:
    python tools/upload_new_pd_files.py                      # Upload all
    python tools/upload_new_pd_files.py --dry-run            # Preview without uploading
    python tools/upload_new_pd_files.py --start 10           # Start from 10th item
    python tools/upload_new_pd_files.py --limit 5            # Process only 5 items
    python tools/upload_new_pd_files.py --start 10 --limit 5 # Process items 10-14
"""
import os
import sys

# Ensure we're working from project root
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
os.chdir(project_root)
sys.path.insert(0, project_root)

import json
import time
import argparse
from datetime import datetime
import pandas as pd

# Import the upload and structured data modules
from commons_template import generate_wikitext, get_upload_filename, get_local_filepath, safe_str
import structured_data

# Configuration
EXCEL_FILE = 'nbg-beeldbank_all_24012026.xlsx'
TEMPLATES_FILE = 'tools/previews/pd_templates_for_upload.json'
EXCLUSIONS_FILE = 'category_exclusions.json'

# Throttling configuration
DEFAULT_DELAY = 5           # Delay between uploads (seconds)
SAVE_INTERVAL = 10          # Save Excel every N uploads


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


def print_progress_header(current, total, unique_id, title):
    """Print a progress header for batch processing."""
    percent = (current / total) * 100
    bar_length = 30
    filled = int(bar_length * current / total)
    bar = "#" * filled + "-" * (bar_length - filled)

    print()
    print("=" * 80)
    print(f"  [{bar}] {current}/{total} ({percent:.1f}%)")
    print(f"  Processing: {unique_id}")
    if title:
        display_title = title[:60] + "..." if len(title) > 60 else title
        print(f"  Title: {display_title}")
    print("=" * 80)


def load_templates():
    """Load the template assignments from JSON file."""
    if not os.path.exists(TEMPLATES_FILE):
        raise FileNotFoundError(f"Templates file not found: {TEMPLATES_FILE}")

    with open(TEMPLATES_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Convert to dict for easy lookup: id -> template
    templates = {item['id']: item['template'] for item in data['items']}
    return templates


def load_category_exclusions():
    """Load category exclusions from JSON file."""
    if not os.path.exists(EXCLUSIONS_FILE):
        return {}

    try:
        with open(EXCLUSIONS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('category_exclusions', {})
    except (json.JSONDecodeError, IOError) as e:
        log(f"Could not load exclusions file: {e}", "WARN")
        return {}


def filter_categories_for_record(unique_id, commons_categories, exclusions):
    """Filter out excluded categories for a specific record."""
    if not commons_categories or not exclusions:
        return commons_categories

    categories = [c.strip() for c in commons_categories.split(';') if c.strip()]
    filtered = []
    for cat in categories:
        excluded_ids = exclusions.get(cat, [])
        if unique_id not in excluded_ids:
            filtered.append(cat)

    return '; '.join(filtered)


def get_commons_site():
    """Connect to Wikimedia Commons and return the site object."""
    import mwclient
    from dotenv import load_dotenv

    load_dotenv()

    username = os.getenv('COMMONS_USERNAME')
    password = os.getenv('COMMONS_PASSWORD')
    user_agent = os.getenv('COMMONS_USER_AGENT')

    if not all([username, password, user_agent]):
        raise ValueError("Missing Commons credentials in .env file")

    site = mwclient.Site('commons.wikimedia.org', clients_useragent=user_agent)
    site.login(username, password)
    log(f"Logged in as: {username}", "SUCCESS")
    return site


def check_file_exists(site, filename):
    """Check if a file already exists on Wikimedia Commons."""
    page = site.pages[f'File:{filename}']
    return page.exists


def get_commons_mid(site, filename):
    """Get the M-id (page ID) for a file on Wikimedia Commons."""
    page = site.pages[f'File:{filename}']
    if page.exists:
        return f"M{page.pageid}"
    return None


def upload_file(site, local_path, filename, wikitext, max_retries=3):
    """Upload a file to Wikimedia Commons with retry logic."""
    comment = "Upload from Beeldbank Nederlandse Boekgeschiedenis - Dutch book history collection by KB, National Library of the Netherlands"

    for attempt in range(max_retries):
        try:
            with open(local_path, 'rb') as f:
                result = site.upload(
                    file=f,
                    filename=filename,
                    description=wikitext,
                    comment=comment,
                    ignore=True  # Ignore warnings like duplicate files
                )
            return result
        except Exception as e:
            if attempt < max_retries - 1:
                delay = 5 * (2 ** attempt)  # Exponential backoff
                log(f"Upload failed (attempt {attempt + 1}/{max_retries}): {e}", "WARN")
                log(f"Retrying in {delay}s...", "INFO")
                time.sleep(delay)
            else:
                raise


def add_structured_data(unique_id, preview_only=False):
    """Add structured data (Dutch label + statements) to a file after upload."""
    try:
        # Add Dutch description (label)
        structured_data.process_single(unique_id, preview_only=preview_only)

        # Add Wikibase statements
        success = structured_data.process_statements_single(unique_id, preview_only=preview_only)

        return success
    except Exception as e:
        log(f"Failed to add structured data: {e}", "ERROR")
        return False


def save_excel(df_all, df_pd):
    """Save both sheets to Excel file."""
    with pd.ExcelWriter(EXCEL_FILE, engine='openpyxl') as writer:
        df_all.to_excel(writer, sheet_name='all', index=False)
        df_pd.to_excel(writer, sheet_name='public-domain-files', index=False)


def upload_new_pd_files(dry_run=False, start=0, limit=None, delay=DEFAULT_DELAY):
    """
    Upload newly discovered public domain files to Wikimedia Commons.

    Args:
        dry_run: If True, preview without uploading
        start: Start from this index (0-based)
        limit: Process only this many files (None = all)
        delay: Delay between uploads in seconds
    """
    start_time = datetime.now()

    # Load template assignments
    log("Loading template assignments...", "PROGRESS")
    templates = load_templates()
    log(f"Loaded {len(templates)} template assignments", "SUCCESS")

    # Load category exclusions
    exclusions = load_category_exclusions()
    if exclusions:
        log(f"Loaded category exclusions for {len(exclusions)} categories", "INFO")

    # Load Excel file
    log("Loading Excel file...", "PROGRESS")
    df_all = pd.read_excel(EXCEL_FILE, sheet_name='all')
    df_pd = pd.read_excel(EXCEL_FILE, sheet_name='public-domain-files')
    log(f"Excel loaded: {len(df_all)} total records, {len(df_pd)} public domain", "SUCCESS")

    # Ensure required columns exist
    for col in ['CommonsURL', 'CommonsMidURL', 'in_public_domain_files', 'structured_data_added', 'pd_template']:
        if col not in df_all.columns:
            df_all[col] = None
        if col not in df_pd.columns:
            df_pd[col] = None

    # Get list of IDs to process
    ids_to_process = list(templates.keys())
    total_count = len(ids_to_process)

    # Apply start and limit
    if start > 0:
        ids_to_process = ids_to_process[start:]
    if limit:
        ids_to_process = ids_to_process[:limit]

    process_count = len(ids_to_process)

    print()
    print("=" * 80)
    print(f"  UPLOAD NEW PUBLIC DOMAIN FILES")
    print("=" * 80)
    print(f"  Total files to upload: {total_count}")
    print(f"  Processing: {process_count} files (start={start}, limit={limit})")
    print(f"  Mode: {'DRY RUN' if dry_run else 'LIVE UPLOAD'}")
    print(f"  Delay between uploads: {delay}s")
    print("=" * 80)

    if not dry_run:
        log("Connecting to Wikimedia Commons...", "PROGRESS")
        site = get_commons_site()
    else:
        site = None
        log("DRY RUN MODE - No uploads will be performed", "WARN")

    # Track results
    uploaded = []
    structured_data_added = []
    skipped_exists = []
    skipped_no_file = []
    failed = []

    for i, unique_id in enumerate(ids_to_process):
        current_num = start + i + 1
        template = templates[unique_id]

        # Find the row in Excel
        row_mask = df_all['unique_id'] == unique_id
        if not row_mask.any():
            log(f"ID {unique_id} not found in Excel", "ERROR")
            failed.append(unique_id)
            continue

        row = df_all[row_mask].iloc[0]
        idx = df_all[row_mask].index[0]
        titel = safe_str(row.get('titel', ''))

        print_progress_header(current_num, total_count, unique_id, titel)
        log(f"Template: {template}", "INFO")

        # Check if already uploaded
        existing_url = safe_str(row.get('CommonsURL', ''))
        if existing_url and existing_url.startswith('http'):
            log(f"Already uploaded: {existing_url}", "WARN")
            skipped_exists.append(unique_id)
            continue

        # Check local file exists
        local_path = get_local_filepath(row)
        if not os.path.exists(local_path):
            log(f"Local file not found: {local_path}", "ERROR")
            skipped_no_file.append(unique_id)
            continue

        filename = get_upload_filename(row)
        log(f"Filename: {filename}", "INFO")
        log(f"Local file: {os.path.basename(local_path)}", "INFO")

        # Apply category exclusions
        original_cats = safe_str(row.get('commons_categories', ''))
        filtered_cats = filter_categories_for_record(unique_id, original_cats, exclusions)
        if original_cats != filtered_cats:
            log(f"Categories filtered: {original_cats} -> {filtered_cats}", "INFO")
            row = row.copy()
            row['commons_categories'] = filtered_cats

        # Generate wikitext with custom template
        wikitext = generate_wikitext(row, license_template=template)

        if dry_run:
            log("DRY RUN - Would upload this file", "INFO")
            log(f"License template: {template}", "INFO")
            uploaded.append(unique_id)
            continue

        # Check if already exists on Commons
        if check_file_exists(site, filename):
            log("File already exists on Commons", "WARN")
            # Get existing URL and M-id
            commons_url = f"https://commons.wikimedia.org/wiki/File:{filename.replace(' ', '_')}"
            mid = get_commons_mid(site, filename)

            # Update Excel
            df_all.at[idx, 'CommonsURL'] = commons_url
            if mid:
                df_all.at[idx, 'CommonsMidURL'] = f"https://commons.wikimedia.org/entity/{mid}"
            df_all.at[idx, 'in_public_domain_files'] = True
            df_all.at[idx, 'pd_template'] = template

            skipped_exists.append(unique_id)
            continue

        # Upload the file
        try:
            log(f"Uploading...", "PROGRESS")
            result = upload_file(site, local_path, filename, wikitext)

            if result and result.get('result') == 'Success':
                commons_url = f"https://commons.wikimedia.org/wiki/File:{filename.replace(' ', '_')}"
                log(f"Upload successful!", "SUCCESS")
                log(f"Commons URL: {commons_url}", "INFO")

                # Get M-id
                time.sleep(1)  # Brief wait for Commons to process
                mid = get_commons_mid(site, filename)
                mid_url = f"https://commons.wikimedia.org/entity/{mid}" if mid else ""

                # Update 'all' sheet
                df_all.at[idx, 'CommonsURL'] = commons_url
                df_all.at[idx, 'CommonsMidURL'] = mid_url
                df_all.at[idx, 'in_public_domain_files'] = True
                df_all.at[idx, 'pd_template'] = template

                uploaded.append(unique_id)

                # Add structured data
                log("Adding structured data...", "PROGRESS")
                time.sleep(2)  # Wait before adding structured data
                if add_structured_data(unique_id, preview_only=False):
                    df_all.at[idx, 'structured_data_added'] = True
                    structured_data_added.append(unique_id)
                    log("Structured data added", "SUCCESS")

                # Add to public-domain-files sheet if not already there
                if not (df_pd['unique_id'] == unique_id).any():
                    new_row = df_all.loc[idx].copy()
                    df_pd = pd.concat([df_pd, new_row.to_frame().T], ignore_index=True)
                else:
                    # Update existing row in pd sheet
                    pd_idx = df_pd[df_pd['unique_id'] == unique_id].index[0]
                    df_pd.at[pd_idx, 'CommonsURL'] = commons_url
                    df_pd.at[pd_idx, 'CommonsMidURL'] = mid_url
                    df_pd.at[pd_idx, 'structured_data_added'] = True
                    df_pd.at[pd_idx, 'pd_template'] = template

                # Save periodically
                if len(uploaded) % SAVE_INTERVAL == 0:
                    log(f"Saving progress ({len(uploaded)} uploaded)...", "INFO")
                    save_excel(df_all, df_pd)

                # Delay before next upload
                if i < len(ids_to_process) - 1:
                    log(f"Waiting {delay}s...", "INFO")
                    time.sleep(delay)
            else:
                log(f"Upload returned unexpected result: {result}", "ERROR")
                failed.append(unique_id)

        except Exception as e:
            log(f"Upload failed: {e}", "ERROR")
            failed.append(unique_id)
            # Extra delay after failure
            time.sleep(delay * 2)

    # Final save
    if not dry_run and uploaded:
        log("Saving final results to Excel...", "PROGRESS")

        # Sort pd sheet by unique_id
        df_pd['sort_key'] = df_pd['unique_id'].str.extract(r'(\d+)')[0].astype(int)
        df_pd = df_pd.sort_values('sort_key').drop(columns=['sort_key'])

        save_excel(df_all, df_pd)
        log("Excel saved", "SUCCESS")

    # Summary
    end_time = datetime.now()
    duration = end_time - start_time

    print()
    print("=" * 80)
    print("  SUMMARY")
    print("=" * 80)
    print(f"  Duration: {duration}")
    print(f"  Uploaded: {len(uploaded)}")
    print(f"  Structured data added: {len(structured_data_added)}")
    print(f"  Skipped (already uploaded): {len(skipped_exists)}")
    print(f"  Skipped (no local file): {len(skipped_no_file)}")
    print(f"  Failed: {len(failed)}")
    if failed:
        print(f"  Failed IDs: {', '.join(failed[:10])}")
        if len(failed) > 10:
            print(f"             ... and {len(failed) - 10} more")
    print()
    print(f"  Public domain files in Excel: {len(df_pd)}")
    print("=" * 80)

    return {
        'uploaded': uploaded,
        'structured_data_added': structured_data_added,
        'skipped_exists': skipped_exists,
        'skipped_no_file': skipped_no_file,
        'failed': failed
    }


def main():
    parser = argparse.ArgumentParser(
        description='Upload newly discovered public domain files to Wikimedia Commons',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
    python tools/upload_new_pd_files.py                    # Upload all files
    python tools/upload_new_pd_files.py --dry-run          # Preview without uploading
    python tools/upload_new_pd_files.py --start 10         # Resume from 10th file
    python tools/upload_new_pd_files.py --limit 5          # Upload only 5 files
    python tools/upload_new_pd_files.py --delay 10         # 10s delay between uploads
        '''
    )
    parser.add_argument('--dry-run', '-n', action='store_true',
                        help='Preview without uploading')
    parser.add_argument('--start', '-s', type=int, default=0,
                        help='Start from this index (0-based)')
    parser.add_argument('--limit', '-l', type=int, default=None,
                        help='Process only this many files')
    parser.add_argument('--delay', '-d', type=int, default=DEFAULT_DELAY,
                        help=f'Delay between uploads in seconds (default: {DEFAULT_DELAY})')

    args = parser.parse_args()

    try:
        upload_new_pd_files(
            dry_run=args.dry_run,
            start=args.start,
            limit=args.limit,
            delay=args.delay
        )
    except KeyboardInterrupt:
        print("\n\nUpload interrupted by user. Progress has been saved.")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
