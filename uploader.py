"""
Wikimedia Commons uploader for Beeldbank Nederlandse Boekgeschiedenis.

This script uploads images from the local collection to Wikimedia Commons
using the {{Artwork}} template for metadata.

Usage:
    python uploader.py BBB-2           # Upload a single record by unique_id
    python uploader.py --preview BBB-2 # Preview wikitext without uploading
    python uploader.py --batch 1 10    # Upload records 1-10 (by row index)
"""

import os
import sys
import time
import argparse
import pandas as pd
from dotenv import load_dotenv

# Import the template module
from commons_template import generate_wikitext, get_upload_filename, get_local_filepath, safe_str

# Load environment variables
load_dotenv()

# Configuration from .env
COMMONS_USERNAME = os.getenv('COMMONS_USERNAME')
COMMONS_PASSWORD = os.getenv('COMMONS_PASSWORD')
COMMONS_USER_AGENT = os.getenv('COMMONS_USER_AGENT')

# Excel file path
EXCEL_FILE = 'nbg-beeldbank_all_24012026.xlsx'


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
    Upload a file to Wikimedia Commons.

    Args:
        site: mwclient Site object
        local_path: Path to the local file
        filename: Target filename on Commons
        wikitext: The wikitext for the file description page
        comment: Upload comment

    Returns:
        dict: Upload result
    """
    with open(local_path, 'rb') as f:
        result = site.upload(
            file=f,
            filename=filename,
            description=wikitext,
            comment=comment,
            ignore=False  # Don't ignore warnings (like duplicate files)
        )
    return result


def preview_upload(row):
    """
    Preview what would be uploaded without actually uploading.

    Args:
        row: pandas Series with the record data
    """
    unique_id = safe_str(row.get('unique_id', ''))
    filename = get_upload_filename(row)
    local_path = get_local_filepath(row)
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

    filename, local_path, wikitext = preview_upload(row)

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

            # Delay between uploads to be nice to the server
            if idx < end_idx - 1:
                print(f"  Waiting {delay} seconds...")
                time.sleep(delay)

        except Exception as e:
            print(f"  FAILED: {e}")
            failed += 1

    print(f"\n{'=' * 40}")
    print(f"Batch complete: {successful} successful, {failed} failed, {skipped} skipped")
    return successful, failed


def main():
    parser = argparse.ArgumentParser(description='Upload images to Wikimedia Commons')
    parser.add_argument('unique_id', nargs='?', help='Unique ID of record to upload (e.g., BBB-2)')
    parser.add_argument('--preview', '-p', action='store_true', help='Preview only, do not upload')
    parser.add_argument('--batch', '-b', nargs=2, type=int, metavar=('START', 'END'),
                        help='Upload batch of records by row index')
    parser.add_argument('--delay', '-d', type=int, default=5,
                        help='Delay between batch uploads in seconds (default: 5)')

    args = parser.parse_args()

    if args.batch:
        upload_batch(args.batch[0], args.batch[1], preview_only=args.preview, delay=args.delay)
    elif args.unique_id:
        upload_single(args.unique_id, preview_only=args.preview)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
