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
import pandas as pd
from dotenv import load_dotenv

# Import the template module
from commons_template import generate_wikitext, get_upload_filename, get_local_filepath, safe_str

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
    return pd.read_excel(EXCEL_FILE)


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

    Args:
        unique_id: The unique_id of the record
        commons_url: The Wikimedia Commons URL
        commons_mid_url: The Wikimedia Commons M-id URL
    """
    df = pd.read_excel(EXCEL_FILE)

    # Add columns if they don't exist
    if 'CommonsURL' not in df.columns:
        df['CommonsURL'] = ''
    if 'CommonsMidURL' not in df.columns:
        df['CommonsMidURL'] = ''

    # Update the URLs for this record
    mask = df['unique_id'] == unique_id
    df.loc[mask, 'CommonsURL'] = commons_url
    if commons_mid_url:
        df.loc[mask, 'CommonsMidURL'] = commons_mid_url

    # Save back to Excel
    df.to_excel(EXCEL_FILE, index=False)
    print(f"Saved CommonsURL and CommonsMidURL for {unique_id}")


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
    df = load_excel()
    row = get_record_by_id(df, unique_id)

    if row is None:
        print(f"ERROR: Record with unique_id '{unique_id}' not found.")
        return False

    # Load category exclusions
    exclusions = load_category_exclusions()
    if exclusions:
        print(f"Loaded category exclusions from {EXCLUSIONS_FILE}")

    filename, local_path, wikitext = preview_upload(row, exclusions)

    if not os.path.exists(local_path):
        print(f"\nERROR: Local file not found: {local_path}")
        return False

    if preview_only:
        print("\n[PREVIEW MODE - No upload performed]")
        return True

    # Connect and upload
    print("\nConnecting to Wikimedia Commons...")
    site = get_commons_site()

    # Check if file already exists
    if check_file_exists(site, filename):
        print(f"\nWARNING: File already exists on Commons: {filename}")
        response = input("Overwrite? (y/N): ")
        if response.lower() != 'y':
            print("Upload cancelled.")
            return False

    print(f"\nUploading: {filename}...")
    try:
        result = upload_file(site, local_path, filename, wikitext)
        print(f"Upload result: {result}")
        commons_url = f"https://commons.wikimedia.org/wiki/File:{filename.replace(' ', '_')}"
        commons_mid_url = get_commons_mid(site, filename)
        print(f"\nSuccess! View at: {commons_url}")
        print(f"M-id: {commons_mid_url}")

        # Save the Commons URL and M-id URL to Excel
        save_commons_url(unique_id, commons_url, commons_mid_url)

        return True
    except Exception as e:
        print(f"\nERROR during upload: {e}")
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
    df = load_excel()

    if end_idx > len(df):
        end_idx = len(df)

    print(f"Processing rows {start_idx} to {end_idx - 1} ({end_idx - start_idx} records)")

    # Load category exclusions
    exclusions = load_category_exclusions()
    if exclusions:
        print(f"Loaded category exclusions from {EXCLUSIONS_FILE}")

    if not preview_only:
        print("Connecting to Wikimedia Commons...")
        site = get_commons_site()
    else:
        site = None

    successful = 0
    failed = 0
    skipped = 0

    for idx in range(start_idx, end_idx):
        row = df.iloc[idx]
        unique_id = safe_str(row.get('unique_id', ''))
        filename = get_upload_filename(row)
        local_path = get_local_filepath(row)

        print(f"\n[{idx + 1}/{end_idx}] Processing: {unique_id}")

        if not os.path.exists(local_path):
            print(f"  SKIP: Local file not found")
            skipped += 1
            continue

        # Apply category exclusions
        if exclusions:
            original_cats = safe_str(row.get('commons_categories', ''))
            filtered_cats = filter_categories_for_record(unique_id, original_cats, exclusions)
            if original_cats != filtered_cats:
                row = row.copy()
                row['commons_categories'] = filtered_cats
                print(f"  Categories: {original_cats} -> {filtered_cats}")

        if preview_only:
            wikitext = generate_wikitext(row)
            print(f"  Filename: {filename}")
            print(f"  Categories: {safe_str(row.get('commons_categories', ''))}")
            successful += 1
            continue

        # Check if already exists
        if check_file_exists(site, filename):
            print(f"  SKIP: Already exists on Commons")
            skipped += 1
            continue

        # Upload
        try:
            wikitext = generate_wikitext(row)
            upload_file(site, local_path, filename, wikitext)
            commons_url = f"https://commons.wikimedia.org/wiki/File:{filename.replace(' ', '_')}"
            commons_mid_url = get_commons_mid(site, filename)
            print(f"  SUCCESS: Uploaded -> {commons_url}")

            # Save the Commons URL and M-id URL to Excel
            save_commons_url(unique_id, commons_url, commons_mid_url)

            successful += 1

            # Throttled delay between uploads to be nice to the server
            if idx < end_idx - 1:
                throttled_sleep(delay, add_jitter=True)

        except Exception as e:
            print(f"  FAILED: {e}")
            failed += 1

            # Add extra delay after failures to avoid hammering the server
            if idx < end_idx - 1:
                backoff_delay = exponential_backoff(0, delay)  # Use base backoff
                print(f"  Adding cooldown after failure...")
                throttled_sleep(backoff_delay, add_jitter=True)

    print(f"\n{'=' * 40}")
    print(f"Batch complete: {successful} successful, {failed} failed, {skipped} skipped")
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
