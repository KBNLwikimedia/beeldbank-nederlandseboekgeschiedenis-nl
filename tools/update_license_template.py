"""
Update license template on existing Wikimedia Commons files.

This script replaces one license template with another on specified files.

Usage:
    python tools/update_license_template.py --preview   # Preview changes without editing
    python tools/update_license_template.py             # Apply changes
"""

import os
import sys
import re
import time
import argparse
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration from .env
COMMONS_USERNAME = os.getenv('COMMONS_USERNAME')
COMMONS_PASSWORD = os.getenv('COMMONS_PASSWORD')
COMMONS_USER_AGENT = os.getenv('COMMONS_USER_AGENT')

# Excel file path
EXCEL_FILE = 'nbg-beeldbank_all_24012026.xlsx'

# Files to update (unique_ids)
FILES_TO_UPDATE = ['BBB-645', 'BBB-646', 'BBB-654', 'BBB-659', 'BBB-661', 'BBB-669', 'BBB-671']

# Template replacement
OLD_TEMPLATE = '{{PD-anon-70-EU}}'
NEW_TEMPLATE = '{{PD-old-70-expired}}'

# Delay between edits (seconds)
EDIT_DELAY = 5


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
    """Connect to Wikimedia Commons and return the site object."""
    import mwclient

    site = mwclient.Site('commons.wikimedia.org', clients_useragent=COMMONS_USER_AGENT)
    site.login(COMMONS_USERNAME, COMMONS_PASSWORD)
    log(f"Logged in as: {COMMONS_USERNAME}", "SUCCESS")
    return site


def load_filenames():
    """Load filenames for the files to update from Excel."""
    df = pd.read_excel(EXCEL_FILE, sheet_name='all')

    filenames = {}
    for unique_id in FILES_TO_UPDATE:
        row = df[df['unique_id'] == unique_id]
        if len(row) > 0:
            filename = row.iloc[0]['WikiCommonsFilename']
            filenames[unique_id] = filename
        else:
            log(f"Could not find {unique_id} in Excel", "WARN")

    return filenames


def update_template_in_text(text, old_template, new_template):
    """
    Replace the license template in the wikitext.

    Args:
        text: The current page wikitext
        old_template: Template to find (e.g., '{{PD-anon-70-EU}}')
        new_template: Template to replace with (e.g., '{{PD-old-70-expired}}')

    Returns:
        tuple: (new_text, was_changed)
    """
    # Case-insensitive search for the template
    # Handle variations like {{PD-anon-70-EU}} or {{ PD-anon-70-EU }}
    pattern = re.escape(old_template).replace(r'\{\{', r'\{\{\s*').replace(r'\}\}', r'\s*\}\}')

    if re.search(pattern, text, re.IGNORECASE):
        new_text = re.sub(pattern, new_template, text, flags=re.IGNORECASE)
        return new_text, True

    return text, False


def update_file(site, filename, old_template, new_template, preview_only=False):
    """
    Update the license template on a single file.

    Args:
        site: mwclient Site object
        filename: The filename (without 'File:' prefix)
        old_template: Template to find
        new_template: Template to replace with
        preview_only: If True, don't actually edit

    Returns:
        bool: True if successful (or would be successful in preview mode)
    """
    page = site.pages[f'File:{filename}']

    if not page.exists:
        log(f"File does not exist: {filename}", "ERROR")
        return False

    # Get current text
    current_text = page.text()

    # Check if old template exists
    if old_template.lower() not in current_text.lower():
        # Try without the curly braces wrapper
        template_name = old_template.strip('{}')
        if template_name.lower() not in current_text.lower():
            log(f"Template '{old_template}' not found in page", "WARN")
            return False

    # Replace template
    new_text, was_changed = update_template_in_text(current_text, old_template, new_template)

    if not was_changed:
        log(f"No changes needed for {filename}", "INFO")
        return True

    if preview_only:
        log(f"Would replace: {old_template} -> {new_template}", "INFO")
        return True

    # Save the edit
    try:
        edit_summary = f"Changing license template from {old_template} to {new_template}"
        page.save(new_text, summary=edit_summary)
        log(f"Successfully updated: {filename}", "SUCCESS")
        return True
    except Exception as e:
        log(f"Failed to save: {e}", "ERROR")
        return False


def main():
    parser = argparse.ArgumentParser(description='Update license template on Commons files')
    parser.add_argument('--preview', '-p', action='store_true', help='Preview only, do not edit')
    args = parser.parse_args()

    print("=" * 80)
    print("  LICENSE TEMPLATE UPDATER")
    print("=" * 80)
    print(f"  Old template: {OLD_TEMPLATE}")
    print(f"  New template: {NEW_TEMPLATE}")
    print(f"  Files to update: {len(FILES_TO_UPDATE)}")
    if args.preview:
        print("  MODE: PREVIEW (no edits will be made)")
    print("=" * 80)
    print()

    # Load filenames from Excel
    log("Loading filenames from Excel...", "PROGRESS")
    filenames = load_filenames()
    log(f"Found {len(filenames)} files", "SUCCESS")

    # Connect to Commons
    log("Connecting to Wikimedia Commons...", "PROGRESS")
    site = get_commons_site()

    # Update each file
    successful = 0
    failed = 0

    for unique_id, filename in filenames.items():
        print()
        log(f"Processing {unique_id}: {filename[:60]}...", "PROGRESS")

        if update_file(site, filename, OLD_TEMPLATE, NEW_TEMPLATE, preview_only=args.preview):
            successful += 1
        else:
            failed += 1

        # Delay between edits (except for last file)
        if not args.preview and unique_id != list(filenames.keys())[-1]:
            log(f"Waiting {EDIT_DELAY} seconds...", "INFO")
            time.sleep(EDIT_DELAY)

    # Summary
    print()
    print("=" * 80)
    print(f"  COMPLETE: {successful} successful, {failed} failed")
    print("=" * 80)


if __name__ == "__main__":
    main()
