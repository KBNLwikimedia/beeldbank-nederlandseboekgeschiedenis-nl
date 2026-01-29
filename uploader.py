"""
Wikimedia Commons uploader for Beeldbank Nederlandse Boekgeschiedenis.

This script uploads images from the local collection to Wikimedia Commons
using the {{Artwork}} template for metadata.

Usage:
    python uploader.py BBB-2           # Upload a single record by unique_id
    python uploader.py --preview BBB-2 # Preview wikitext without uploading
    python uploader.py --batch 1 10    # Upload records 1-10 (by row index)

Category Exclusions:
    The uploader reads 'category_exclusions.json' to determine which categories
    should NOT be applied to specific files. This file is exported from the
    preview HTML pages (previews/pd_preview_*.html) using the "Export JSON" button.

    JSON structure:
    {
        "category_exclusions": {
            "Dutch typography": ["BBB-123", "BBB-456"],
            "Printing in the Netherlands": ["BBB-789"]
        }
    }
"""

import os
import sys
import time
import json
import random
import argparse
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv

# Import the template module
from commons_template import generate_wikitext, get_upload_filename, get_local_filepath, safe_str

# Import structured data module for adding statements after upload
import structured_data

# Category exclusions file (exported from preview HTML pages)
EXCLUSIONS_FILE = 'category_exclusions.json'

# Load environment variables
load_dotenv()

# Configuration from .env
COMMONS_USERNAME = os.getenv('COMMONS_USERNAME')
COMMONS_PASSWORD = os.getenv('COMMONS_PASSWORD')
COMMONS_USER_AGENT = os.getenv('COMMONS_USER_AGENT')

# Excel file path
EXCEL_FILE = 'nbg-beeldbank_all_24012026.xlsx'

# Throttling and backoff configuration
DEFAULT_DELAY = 5           # Default delay between uploads (seconds)
MIN_DELAY = 3               # Minimum delay between requests
MAX_DELAY = 60              # Maximum delay for backoff
MAX_RETRIES = 3             # Maximum retries for failed uploads
BACKOFF_FACTOR = 2          # Exponential backoff multiplier
JITTER_MAX = 2              # Maximum random jitter to add (seconds)


def log(message, level="INFO"):
    """
    Print a timestamped log message.

    Args:
        message: The message to print
        level: Log level (INFO, SUCCESS, ERROR, WARN, PROGRESS)
    """
    timestamp = datetime.now().strftime("%H:%M:%S")
    # Use ASCII-safe characters for Windows compatibility
    prefix = {
        "INFO": "   ",
        "SUCCESS": "[+]",
        "ERROR": "[X]",
        "WARN": "[!]",
        "PROGRESS": ">>>"
    }.get(level, "   ")
    print(f"[{timestamp}]{prefix} {message}")


def print_progress_header(current, total, unique_id, title):
    """
    Print a progress header for batch processing.

    Args:
        current: Current item number (1-based)
        total: Total number of items
        unique_id: The unique ID being processed
        title: The title of the item
    """
    percent = (current / total) * 100
    bar_length = 30
    filled = int(bar_length * current / total)
    # Use ASCII-safe characters for Windows compatibility
    bar = "#" * filled + "-" * (bar_length - filled)

    print()
    print("=" * 80)
    print(f"  [{bar}] {current}/{total} ({percent:.1f}%)")
    print(f"  Processing: {unique_id}")
    if title:
        display_title = title[:60] + "..." if len(title) > 60 else title
        print(f"  Title: {display_title}")
    print("=" * 80)


def add_structured_data_after_upload(unique_id):
    """
    Add structured data (Dutch description + statements) to a file after upload.

    Args:
        unique_id: The unique_id of the uploaded record

    Returns:
        bool: True if successful, False otherwise
    """
    log(f"Adding structured data for {unique_id}...", "PROGRESS")

    try:
        # Add Dutch description
        log("Adding Dutch description (label)...")
        structured_data.process_single(unique_id, preview_only=False)

        # Add statements
        log("Adding Wikibase statements...")
        success = structured_data.process_statements_single(unique_id, preview_only=False)

        if success:
            log(f"Structured data added successfully for {unique_id}", "SUCCESS")
        return success

    except Exception as e:
        log(f"Failed to add structured data: {e}", "ERROR")
        return False


def throttled_sleep(delay, add_jitter=True):
    """
    Sleep for the specified delay, optionally adding random jitter.

    Args:
        delay: Base delay in seconds
        add_jitter: If True, add random jitter to prevent thundering herd
    """
    if add_jitter:
        jitter = random.uniform(0, JITTER_MAX)
        delay = delay + jitter
    print(f"  Waiting {delay:.1f} seconds...")
    time.sleep(delay)


def exponential_backoff(attempt, base_delay=DEFAULT_DELAY):
    """
    Calculate exponential backoff delay for retries.

    Args:
        attempt: Current attempt number (0-based)
        base_delay: Base delay in seconds

    Returns:
        float: Delay in seconds (capped at MAX_DELAY)
    """
    delay = base_delay * (BACKOFF_FACTOR ** attempt)
    return min(delay, MAX_DELAY)


def is_retryable_error(error):
    """
    Check if an error is retryable (transient server errors, rate limits, etc.).

    Args:
        error: The exception that was raised

    Returns:
        bool: True if the error is retryable
    """
    error_str = str(error).lower()
    retryable_patterns = [
        'rate limit',
        'too many requests',
        '429',
        '503',
        '502',
        'timeout',
        'connection',
        'temporary',
        'try again',
        'server error',
        'maxlag',
    ]
    return any(pattern in error_str for pattern in retryable_patterns)


def load_category_exclusions():
    """
    Load category exclusions from JSON file.

    The JSON file is exported from the preview HTML pages and contains
    a mapping of category names to lists of excluded unique_ids.

    Returns:
        dict: Category exclusions, e.g., {'Dutch typography': ['BBB-123', 'BBB-456']}
    """
    if not os.path.exists(EXCLUSIONS_FILE):
        return {}

    try:
        with open(EXCLUSIONS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('category_exclusions', {})
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not load exclusions file: {e}")
        return {}


def filter_categories_for_record(unique_id, commons_categories, exclusions):
    """
    Filter out excluded categories for a specific record.

    Args:
        unique_id: The unique_id of the record (e.g., 'BBB-123')
        commons_categories: Original categories string from Excel (semicolon-separated)
        exclusions: Dict of category exclusions from load_category_exclusions()

    Returns:
        str: Filtered categories string (semicolon-separated)
    """
    if not commons_categories or not exclusions:
        return commons_categories

    # Split categories
    categories = [c.strip() for c in commons_categories.split(';') if c.strip()]

    # Filter out excluded categories for this record
    filtered = []
    for cat in categories:
        excluded_ids = exclusions.get(cat, [])
        if unique_id not in excluded_ids:
            filtered.append(cat)

    return '; '.join(filtered)


def get_commons_site():
    """
    Connect to Wikimedia Commons and return the site object.

    Returns:
        mwclient.Site: Connected site object
    """
    import mwclient

    site = mwclient.Site('commons.wikimedia.org', clients_useragent=COMMONS_USER_AGENT)
    site.login(COMMONS_USERNAME, COMMONS_PASSWORD)
    print(f"Logged in as: {COMMONS_USERNAME}")
    return site


def load_excel():
    """Load the Excel file and return the DataFrame."""
    # Try 'all' sheet first, fall back to 'Sheet1'
    try:
        return pd.read_excel(EXCEL_FILE, sheet_name='all')
    except ValueError:
        return pd.read_excel(EXCEL_FILE, sheet_name='Sheet1')


def get_commons_mid(site, filename):
    """
    Get the M-id (page ID) for a file on Wikimedia Commons.

    Args:
        site: mwclient Site object
        filename: The filename (without 'File:' prefix)

    Returns:
        str: The M-id URL (e.g., 'https://commons.wikimedia.org/entity/M12345')
    """
    page = site.pages[f'File:{filename}']
    if page.exists:
        return f"https://commons.wikimedia.org/entity/M{page.pageid}"
    return ""


def save_commons_url(unique_id, commons_url, commons_mid_url=""):
    """
    Save the Commons URL and M-id URL to the Excel file for a given record.
    Preserves the two-sheet structure (all, public-domain-files).

    Args:
        unique_id: The unique_id of the record
        commons_url: The Wikimedia Commons URL
        commons_mid_url: The Wikimedia Commons M-id URL
    """
    try:
        # Read both sheets to preserve the two-sheet structure
        df_all = pd.read_excel(EXCEL_FILE, sheet_name='all')
        df_pd = pd.read_excel(EXCEL_FILE, sheet_name='public-domain-files')
    except ValueError:
        # Fallback if sheets don't exist - read default sheet
        df_all = pd.read_excel(EXCEL_FILE)
        df_pd = None

    # Add columns if they don't exist
    for df in [df_all, df_pd] if df_pd is not None else [df_all]:
        if df is None:
            continue
        if 'CommonsURL' not in df.columns:
            df['CommonsURL'] = ''
        if 'CommonsMidURL' not in df.columns:
            df['CommonsMidURL'] = ''

    # Update the URLs in 'all' sheet
    mask_all = df_all['unique_id'] == unique_id
    df_all.loc[mask_all, 'CommonsURL'] = commons_url
    if commons_mid_url:
        df_all.loc[mask_all, 'CommonsMidURL'] = commons_mid_url

    # Update in 'public-domain-files' sheet if it exists
    if df_pd is not None:
        mask_pd = df_pd['unique_id'] == unique_id
        df_pd.loc[mask_pd, 'CommonsURL'] = commons_url
        if commons_mid_url:
            df_pd.loc[mask_pd, 'CommonsMidURL'] = commons_mid_url

    # Save back to Excel, preserving both sheets
    if df_pd is not None:
        with pd.ExcelWriter(EXCEL_FILE, engine='openpyxl') as writer:
            df_all.to_excel(writer, sheet_name='all', index=False)
            df_pd.to_excel(writer, sheet_name='public-domain-files', index=False)
    else:
        df_all.to_excel(EXCEL_FILE, index=False)

    log(f"Saved URLs for {unique_id}")


def get_record_by_id(df, unique_id):
    """
    Get a record from the DataFrame by unique_id.

    Args:
        df: pandas DataFrame
        unique_id: The unique_id to search for (e.g., 'BBB-2')

    Returns:
        pandas Series or None if not found
    """
    matches = df[df['unique_id'] == unique_id]
    if len(matches) == 0:
        return None
    return matches.iloc[0]


def check_file_exists(site, filename):
    """
    Check if a file already exists on Wikimedia Commons.

    Args:
        site: mwclient Site object
        filename: The filename to check (without 'File:' prefix)

    Returns:
        bool: True if file exists, False otherwise
    """
    page = site.pages[f'File:{filename}']
    return page.exists


def upload_file(site, local_path, filename, wikitext, comment="Upload from Beeldbank Nederlandse Boekgeschiedenis - Dutch book history collection by KB, National Library of the Netherlands"):
    """
    Upload a file to Wikimedia Commons with retry logic and exponential backoff.

    Args:
        site: mwclient Site object
        local_path: Path to the local file
        filename: Target filename on Commons
        wikitext: The wikitext for the file description page
        comment: Upload comment

    Returns:
        dict: Upload result

    Raises:
        Exception: If upload fails after all retries
    """
    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            with open(local_path, 'rb') as f:
                result = site.upload(
                    file=f,
                    filename=filename,
                    description=wikitext,
                    comment=comment,
                    ignore=False  # Don't ignore warnings (like duplicate files)
                )
            return result

        except Exception as e:
            last_error = e

            if not is_retryable_error(e):
                # Non-retryable error, raise immediately
                raise

            if attempt < MAX_RETRIES - 1:
                delay = exponential_backoff(attempt)
                print(f"  Upload failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
                print(f"  Retrying in {delay:.1f} seconds...")
                time.sleep(delay)
            else:
                print(f"  Upload failed after {MAX_RETRIES} attempts")

    # If we get here, all retries failed
    raise last_error


def preview_upload(row, exclusions=None):
    """
    Preview what would be uploaded without actually uploading.

    Args:
        row: pandas Series with the record data
        exclusions: Optional dict of category exclusions
    """
    unique_id = safe_str(row.get('unique_id', ''))
    filename = get_upload_filename(row)
    local_path = get_local_filepath(row)

    # Apply category exclusions if provided
    if exclusions:
        original_cats = safe_str(row.get('commons_categories', ''))
        filtered_cats = filter_categories_for_record(unique_id, original_cats, exclusions)
        row = row.copy()
        row['commons_categories'] = filtered_cats
        if original_cats != filtered_cats:
            print(f"Categories filtered: {original_cats} -> {filtered_cats}")

    wikitext = generate_wikitext(row)

    print("=" * 80)
    print(f"PREVIEW: {unique_id}")
    print("=" * 80)
    print(f"\nFilename: {filename}")
    print(f"Local path: {local_path}")
    print(f"File exists: {os.path.exists(local_path)}")
    print(f"\nWikitext:\n{'-' * 40}")
    print(wikitext)
    print("-" * 40)

    return filename, local_path, wikitext


def upload_single(unique_id, preview_only=False):
    """
    Upload a single record by unique_id.

    Args:
        unique_id: The unique_id of the record to upload (e.g., 'BBB-2')
        preview_only: If True, only preview without uploading

    Returns:
        bool: True if successful, False otherwise
    """
    start_time = datetime.now()
    log(f"Starting upload for {unique_id}", "PROGRESS")

    df = load_excel()
    row = get_record_by_id(df, unique_id)

    if row is None:
        log(f"Record with unique_id '{unique_id}' not found.", "ERROR")
        return False

    # Load category exclusions
    exclusions = load_category_exclusions()
    if exclusions:
        log(f"Loaded category exclusions from {EXCLUSIONS_FILE}")

    filename, local_path, wikitext = preview_upload(row, exclusions)

    if not os.path.exists(local_path):
        log(f"Local file not found: {local_path}", "ERROR")
        return False

    if preview_only:
        log("PREVIEW MODE - No upload performed", "WARN")
        return True

    # Connect and upload
    log("Connecting to Wikimedia Commons...", "PROGRESS")
    site = get_commons_site()
    log("Connected successfully", "SUCCESS")

    # Check if file already exists
    log("Checking if file exists on Commons...")
    if check_file_exists(site, filename):
        log(f"File already exists on Commons: {filename}", "WARN")
        response = input("Overwrite? (y/N): ")
        if response.lower() != 'y':
            log("Upload cancelled by user.", "WARN")
            return False

    log(f"Uploading: {filename}...", "PROGRESS")
    try:
        result = upload_file(site, local_path, filename, wikitext)
        log(f"Upload result: {result.get('result', 'Unknown')}", "SUCCESS")

        commons_url = f"https://commons.wikimedia.org/wiki/File:{filename.replace(' ', '_')}"
        commons_mid_url = get_commons_mid(site, filename)
        log(f"Commons URL: {commons_url}", "SUCCESS")
        log(f"M-id: {commons_mid_url}")

        # Save the Commons URL and M-id URL to Excel
        try:
            save_commons_url(unique_id, commons_url, commons_mid_url)
            log("Saved URLs to Excel", "SUCCESS")
        except Exception as e:
            log(f"Could not save to Excel: {e}", "WARN")

        # Add structured data immediately after upload
        print()
        add_structured_data_after_upload(unique_id)

        # Summary
        duration = datetime.now() - start_time
        print()
        log(f"Complete! Total time: {duration}", "SUCCESS")

        return True
    except Exception as e:
        log(f"Upload failed: {e}", "ERROR")
        return False


def upload_batch(start_idx, end_idx, preview_only=False, delay=5):
    """
    Upload a batch of records by row index.

    Args:
        start_idx: Starting row index (0-based)
        end_idx: Ending row index (exclusive)
        preview_only: If True, only preview without uploading
        delay: Delay between uploads in seconds

    Returns:
        tuple: (successful_count, failed_count)
    """
    start_time = datetime.now()
    df = load_excel()

    if end_idx > len(df):
        end_idx = len(df)

    total_count = end_idx - start_idx

    print()
    print("=" * 80)
    print(f"  BATCH UPLOAD - {total_count} files")
    print(f"  Started at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Rows: {start_idx} to {end_idx - 1}")
    print("=" * 80)

    # Load category exclusions
    exclusions = load_category_exclusions()
    if exclusions:
        log(f"Loaded category exclusions from {EXCLUSIONS_FILE}")

    if not preview_only:
        log("Connecting to Wikimedia Commons...")
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

    for idx in range(start_idx, end_idx):
        row = df.iloc[idx]
        unique_id = safe_str(row.get('unique_id', ''))
        titel = safe_str(row.get('titel', ''))
        filename = get_upload_filename(row)
        local_path = get_local_filepath(row)

        current_num = idx - start_idx + 1
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
            log("", "INFO")  # Empty line for readability
            if add_structured_data_after_upload(unique_id):
                structured_data_success += 1
            else:
                structured_data_failed += 1

            # Throttled delay between files
            if idx < end_idx - 1:
                log("", "INFO")  # Empty line for readability
                throttled_sleep(delay, add_jitter=True)

        except Exception as e:
            log(f"Upload failed: {e}", "ERROR")
            failed += 1

            # Add extra delay after failures to avoid hammering the server
            if idx < end_idx - 1:
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

    return successful, failed


def main():
    parser = argparse.ArgumentParser(
        description='Upload images to Wikimedia Commons',
        epilog=f'''
Throttling defaults:
  - Delay between uploads: {DEFAULT_DELAY} seconds (configurable with --delay)
  - Max retries on failure: {MAX_RETRIES} (with exponential backoff)
  - Backoff factor: {BACKOFF_FACTOR}x per retry
  - Max backoff delay: {MAX_DELAY} seconds
        '''
    )
    parser.add_argument('unique_id', nargs='?', help='Unique ID of record to upload (e.g., BBB-2)')
    parser.add_argument('--preview', '-p', action='store_true', help='Preview only, do not upload')
    parser.add_argument('--batch', '-b', nargs=2, type=int, metavar=('START', 'END'),
                        help='Upload batch of records by row index')
    parser.add_argument('--delay', '-d', type=int, default=DEFAULT_DELAY,
                        help=f'Delay between batch uploads in seconds (default: {DEFAULT_DELAY})')

    args = parser.parse_args()

    if args.batch:
        upload_batch(args.batch[0], args.batch[1], preview_only=args.preview, delay=args.delay)
    elif args.unique_id:
        upload_single(args.unique_id, preview_only=args.preview)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
