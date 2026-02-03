"""
Add a category to existing Wikimedia Commons files.

This script adds a specified category to files if not already present.

Usage:
    python tools/add_category_to_files.py --preview   # Preview changes without editing
    python tools/add_category_to_files.py             # Apply changes
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

# Category to add
CATEGORY_TO_ADD = 'Bookbindings from Koninklijke Bibliotheek'

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


def get_boekband_kb_files():
    """Get list of boekband files with KB Den Haag accession numbers."""
    df = pd.read_excel(EXCEL_FILE, sheet_name='all')

    # Find rows where type contains 'boekband' and has KB Den Haag accession
    boekband_rows = df[df['type'].str.contains('boekband', case=False, na=False)]
    kb_rows = boekband_rows[boekband_rows['aanwezig_in'].str.contains('Koninklijke Bibliotheek, Den Haag', case=False, na=False)]
    kb_rows = kb_rows[~kb_rows['aanwezig_in'].str.contains('onbekend', case=False, na=False)]

    # Get unique_ids and filenames
    files = {}
    for idx, row in kb_rows.iterrows():
        unique_id = row['unique_id']
        filename = row['WikiCommonsFilename'] if pd.notna(row['WikiCommonsFilename']) else ''
        if filename:
            files[unique_id] = filename

    return files


def has_category(text, category_name):
    """Check if the wikitext already contains the specified category."""
    # Match [[Category:Name]] with optional whitespace variations
    pattern = r'\[\[\s*Category\s*:\s*' + re.escape(category_name) + r'\s*\]\]'
    return bool(re.search(pattern, text, re.IGNORECASE))


def add_category(text, category_name):
    """
    Add a category to the wikitext.

    Adds the category at the end of the existing categories section.
    """
    category_tag = f'[[Category:{category_name}]]'

    # Find the last category in the text
    last_cat_match = None
    for match in re.finditer(r'\[\[Category:[^\]]+\]\]', text, re.IGNORECASE):
        last_cat_match = match

    if last_cat_match:
        # Insert after the last category
        insert_pos = last_cat_match.end()
        new_text = text[:insert_pos] + '\n' + category_tag + text[insert_pos:]
    else:
        # No categories found, add at the end
        new_text = text.rstrip() + '\n\n' + category_tag + '\n'

    return new_text


def process_file(site, filename, category_name, preview_only=False):
    """
    Add category to a single file if not already present.

    Args:
        site: mwclient Site object
        filename: The filename (without 'File:' prefix)
        category_name: Category name to add (without 'Category:' prefix)
        preview_only: If True, don't actually edit

    Returns:
        str: 'added', 'exists', 'not_found', or 'error'
    """
    page = site.pages[f'File:{filename}']

    if not page.exists:
        log(f"File does not exist on Commons", "ERROR")
        return 'not_found'

    # Get current text
    current_text = page.text()

    # Check if category already exists
    if has_category(current_text, category_name):
        log(f"Category already present", "INFO")
        return 'exists'

    # Add category
    new_text = add_category(current_text, category_name)

    if preview_only:
        log(f"Would add: [[Category:{category_name}]]", "INFO")
        return 'added'

    # Save the edit
    try:
        edit_summary = f"Adding [[Category:{category_name}]]"
        page.save(new_text, summary=edit_summary)
        log(f"Category added successfully", "SUCCESS")
        return 'added'
    except Exception as e:
        log(f"Failed to save: {e}", "ERROR")
        return 'error'


def main():
    parser = argparse.ArgumentParser(description='Add category to Commons files')
    parser.add_argument('--preview', '-p', action='store_true', help='Preview only, do not edit')
    args = parser.parse_args()

    print("=" * 80)
    print("  ADD CATEGORY TO FILES")
    print("=" * 80)
    print(f"  Category: [[Category:{CATEGORY_TO_ADD}]]")
    if args.preview:
        print("  MODE: PREVIEW (no edits will be made)")
    print("=" * 80)
    print()

    # Get files to process
    log("Loading files from Excel...", "PROGRESS")
    files = get_boekband_kb_files()
    log(f"Found {len(files)} files to process", "SUCCESS")

    # Connect to Commons
    log("Connecting to Wikimedia Commons...", "PROGRESS")
    site = get_commons_site()

    # Process each file
    added = 0
    exists = 0
    not_found = 0
    errors = 0

    file_list = list(files.items())
    total = len(file_list)

    for i, (unique_id, filename) in enumerate(file_list, 1):
        print()
        log(f"[{i}/{total}] Processing {unique_id}: {filename[:50]}...", "PROGRESS")

        result = process_file(site, filename, CATEGORY_TO_ADD, preview_only=args.preview)

        if result == 'added':
            added += 1
        elif result == 'exists':
            exists += 1
        elif result == 'not_found':
            not_found += 1
        else:
            errors += 1

        # Delay between edits (except for last file and when category already exists)
        if not args.preview and result == 'added' and i < total:
            log(f"Waiting {EDIT_DELAY} seconds...", "INFO")
            time.sleep(EDIT_DELAY)

    # Summary
    print()
    print("=" * 80)
    print(f"  COMPLETE")
    print("=" * 80)
    print(f"  Added:     {added}")
    print(f"  Existed:   {exists}")
    print(f"  Not found: {not_found}")
    print(f"  Errors:    {errors}")
    print("=" * 80)


if __name__ == "__main__":
    main()
