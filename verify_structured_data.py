"""
Verify which uploaded files have structured data on Commons.
Updates the structured_data_added column in both Excel sheets.
"""

import pandas as pd
import mwclient
import os
import time
from dotenv import load_dotenv

load_dotenv()

EXCEL_FILE = 'nbg-beeldbank_all_24012026.xlsx'
COMMONS_USERNAME = os.getenv('COMMONS_USERNAME')
COMMONS_PASSWORD = os.getenv('COMMONS_PASSWORD')
COMMONS_USER_AGENT = os.getenv('COMMONS_USER_AGENT', 'BeeldbankNBGUploader/1.0')


def get_commons_site():
    """Connect to Wikimedia Commons."""
    site = mwclient.Site('commons.wikimedia.org', clients_useragent=COMMONS_USER_AGENT)
    site.login(COMMONS_USERNAME, COMMONS_PASSWORD)
    print(f"Logged in as: {COMMONS_USERNAME}")
    return site


def check_structured_data(site, filename):
    """
    Check if a file on Commons has structured data (labels and/or statements).

    Returns:
        tuple: (has_structured_data, label_count, statement_count)
    """
    try:
        # Get the page
        page = site.pages[f'File:{filename}']
        if not page.exists:
            return False, 0, 0

        # Get the M-id (page ID)
        mid = f"M{page.pageid}"

        # Use the Wikibase API to get entity data
        # Note: mediainfo entities use 'statements' not 'claims'
        result = site.api('wbgetentities', ids=mid)

        if 'entities' in result and mid in result['entities']:
            entity = result['entities'][mid]
            # MediaInfo uses 'statements' instead of 'claims'
            statements = entity.get('statements', {})
            labels = entity.get('labels', {})

            label_count = len(labels)
            statement_count = sum(len(v) for v in statements.values())

            # Has structured data if either labels or statements exist
            has_data = label_count > 0 or statement_count > 0
            return has_data, label_count, statement_count

        return False, 0, 0

    except Exception as e:
        print(f"  Error checking {filename}: {e}")
        return False, 0, 0


def get_filename_from_url(commons_url):
    """Extract filename from Commons URL."""
    if not commons_url or pd.isna(commons_url):
        return None
    # URL format: https://commons.wikimedia.org/wiki/File:Filename.jpg
    if 'File:' in commons_url:
        filename = commons_url.split('File:')[-1]
        # URL decode - underscores become spaces in MediaWiki titles
        from urllib.parse import unquote
        filename = unquote(filename)
        filename = filename.replace('_', ' ')
        return filename
    return None


def main():
    # Read both sheets
    print("Reading Excel file...")
    df_all = pd.read_excel(EXCEL_FILE, sheet_name='all')
    df_pd = pd.read_excel(EXCEL_FILE, sheet_name='public-domain-files')

    # Ensure structured_data_added column exists
    if 'structured_data_added' not in df_all.columns:
        df_all['structured_data_added'] = False
    if 'structured_data_added' not in df_pd.columns:
        df_pd['structured_data_added'] = False

    # Find uploaded files (those with CommonsURL)
    has_url = df_all['CommonsURL'].notna() & (df_all['CommonsURL'].astype(str) != '')
    uploaded_records = df_all[has_url][['unique_id', 'CommonsURL']].to_dict('records')

    print(f"Found {len(uploaded_records)} uploaded files to check")
    print()

    # Connect to Commons
    site = get_commons_site()
    print()

    # Check each file
    results = {}
    has_data_count = 0
    no_data_count = 0
    labels_only_count = 0

    for i, record in enumerate(uploaded_records):
        unique_id = record['unique_id']
        commons_url = record['CommonsURL']
        filename = get_filename_from_url(commons_url)

        if not filename:
            print(f"{unique_id}: Could not extract filename from URL")
            results[unique_id] = False
            no_data_count += 1
            continue

        has_data, label_count, statement_count = check_structured_data(site, filename)
        results[unique_id] = has_data

        if has_data:
            has_data_count += 1
            if statement_count == 0:
                labels_only_count += 1
                print(f"{unique_id}: LABELS ONLY ({label_count} labels, 0 statements)")
            else:
                print(f"{unique_id}: YES ({label_count} labels, {statement_count} statements)")
        else:
            no_data_count += 1
            print(f"{unique_id}: NO (0 labels, 0 statements)")

        # Small delay every 10 requests
        if (i + 1) % 10 == 0:
            time.sleep(0.5)

    print()
    print(f"Summary:")
    print(f"  - Total with any structured data: {has_data_count}")
    print(f"  - With labels only (no statements): {labels_only_count}")
    print(f"  - With statements: {has_data_count - labels_only_count}")
    print(f"  - No structured data at all: {no_data_count}")
    print()

    # Update the DataFrames
    for unique_id, has_data in results.items():
        df_all.loc[df_all['unique_id'] == unique_id, 'structured_data_added'] = has_data
        df_pd.loc[df_pd['unique_id'] == unique_id, 'structured_data_added'] = has_data

    # Save
    print("Saving to Excel...")
    with pd.ExcelWriter(EXCEL_FILE, engine='openpyxl') as writer:
        df_all.to_excel(writer, sheet_name='all', index=False)
        df_pd.to_excel(writer, sheet_name='public-domain-files', index=False)

    print("Excel updated successfully!")

    # Final count
    sd_all = df_all['structured_data_added'].sum()
    sd_pd = df_pd['structured_data_added'].sum()
    print(f"structured_data_added=True in 'all' sheet: {sd_all}")
    print(f"structured_data_added=True in 'public-domain-files' sheet: {sd_pd}")


if __name__ == "__main__":
    main()
