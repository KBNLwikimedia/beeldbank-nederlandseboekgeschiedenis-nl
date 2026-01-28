"""
Wikimedia Commons Structured Data manager for Beeldbank Nederlandse Boekgeschiedenis.

This script adds structured data (Wikibase statements and labels) to Wikimedia Commons files.

Structured Data Added:
    Labels:
        - Dutch (nl): from 'titel' column

    Statements:
        - P31 (instance of): Q1250322 (digital image)
        - P195 (collection): Q1526131 (Koninklijke Bibliotheek)
        - P6216 (copyright status): Q19652 (public domain)
        - P1163 (MIME type): image/jpeg
        - P1476 (title): from 'titel' column (Dutch)
        - P7482 (source of file): Q74228490 (file available on the internet)
            - P137 (operator): Q1526131 (Koninklijke Bibliotheek)
            - P953 (full work URL): from 'image_url' column
            - P973 (described at URL): from 'detail_url' column

Usage:
    python structured_data.py BBB-1                    # Add Dutch description (label) only
    python structured_data.py --statements BBB-1      # Add all Wikibase statements
    python structured_data.py --all BBB-1             # Add both label and statements
    python structured_data.py --preview BBB-1         # Preview without making changes
    python structured_data.py --batch 0 10            # Add labels to rows 0-10
    python structured_data.py --batch 0 10 --all      # Add all structured data to rows 0-10

Requirements:
    - Files must be uploaded to Commons first (CommonsURL must exist in Excel)
    - Bot password with 'Edit existing pages' permission
"""

import json
import random
import os
import sys
import time
import argparse
import pandas as pd
from dotenv import load_dotenv

from commons_template import safe_str

# Load environment variables
load_dotenv()

# Configuration from .env
COMMONS_USERNAME = os.getenv('COMMONS_USERNAME')
COMMONS_PASSWORD = os.getenv('COMMONS_PASSWORD')
COMMONS_USER_AGENT = os.getenv('COMMONS_USER_AGENT')

# Excel file path
EXCEL_FILE = 'nbg-beeldbank_all_24012026.xlsx'

# Throttling and backoff configuration
DEFAULT_DELAY = 2           # Default delay between API calls (seconds)
MAX_DELAY = 60              # Maximum delay for backoff
MAX_RETRIES = 3             # Maximum retries for failed API calls
BACKOFF_FACTOR = 2          # Exponential backoff multiplier
JITTER_MAX = 1              # Maximum random jitter to add (seconds)


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
        error: The exception or API response

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
        'ratelimited',
    ]
    return any(pattern in error_str for pattern in retryable_patterns)


def api_call_with_retry(func, *args, max_retries=MAX_RETRIES, **kwargs):
    """
    Execute an API call with retry logic and exponential backoff.

    Args:
        func: Function to call
        *args: Arguments to pass to the function
        max_retries: Maximum number of retries
        **kwargs: Keyword arguments to pass to the function

    Returns:
        The result of the function call

    Raises:
        Exception: If all retries fail
    """
    last_error = None

    for attempt in range(max_retries):
        try:
            result = func(*args, **kwargs)

            # Check for API errors in the response
            if isinstance(result, dict) and 'error' in result:
                error_code = result.get('error', {}).get('code', '')
                if is_retryable_error(error_code):
                    raise Exception(f"API error: {result['error']}")

            return result

        except Exception as e:
            last_error = e

            if not is_retryable_error(e):
                raise

            if attempt < max_retries - 1:
                delay = exponential_backoff(attempt)
                print(f"    API call failed (attempt {attempt + 1}/{max_retries}): {e}")
                print(f"    Retrying in {delay:.1f} seconds...")
                time.sleep(delay)

    raise last_error

# Structured Data Constants
# Properties
P_INSTANCE_OF = 'P31'
P_COLLECTION = 'P195'
P_COPYRIGHT_STATUS = 'P6216'
P_SOURCE_OF_FILE = 'P7482'
P_MIME_TYPE = 'P1163'
P_TITLE = 'P1476'
P_OPERATOR = 'P137'
P_FULL_WORK_URL = 'P953'
P_DESCRIBED_AT_URL = 'P973'

# Q-items (entities)
Q_DIGITAL_IMAGE = 'Q1250322'
Q_KB_NETHERLANDS = 'Q1526131'
Q_PUBLIC_DOMAIN = 'Q19652'
Q_FILE_ON_INTERNET = 'Q74228490'


def get_commons_session():
    """
    Create an authenticated session for Wikimedia Commons API.

    Returns:
        tuple: (session, csrf_token)
    """
    import requests

    session = requests.Session()
    session.headers.update({'User-Agent': COMMONS_USER_AGENT})

    api_url = 'https://commons.wikimedia.org/w/api.php'

    # Step 1: Get login token
    params = {
        'action': 'query',
        'meta': 'tokens',
        'type': 'login',
        'format': 'json'
    }
    response = session.get(api_url, params=params)
    login_token = response.json()['query']['tokens']['logintoken']

    # Step 2: Login
    data = {
        'action': 'login',
        'lgname': COMMONS_USERNAME,
        'lgpassword': COMMONS_PASSWORD,
        'lgtoken': login_token,
        'format': 'json'
    }
    response = session.post(api_url, data=data)
    login_result = response.json()

    if login_result.get('login', {}).get('result') != 'Success':
        raise Exception(f"Login failed: {login_result}")

    print(f"Logged in as: {COMMONS_USERNAME}")

    # Step 3: Get CSRF token
    params = {
        'action': 'query',
        'meta': 'tokens',
        'format': 'json'
    }
    response = session.get(api_url, params=params)
    csrf_token = response.json()['query']['tokens']['csrftoken']

    return session, csrf_token


def get_mid_from_filename(session, filename):
    """
    Get the M-id for a file on Wikimedia Commons.

    Args:
        session: requests Session object
        filename: The filename (without 'File:' prefix)

    Returns:
        str: The M-id (e.g., 'M12345') or None if not found
    """
    api_url = 'https://commons.wikimedia.org/w/api.php'
    params = {
        'action': 'query',
        'titles': f'File:{filename}',
        'format': 'json'
    }

    response = session.get(api_url, params=params)
    data = response.json()

    pages = data['query']['pages']
    for page_id, page_info in pages.items():
        if page_id != '-1':
            return f"M{page_id}"
    return None


def get_current_labels(session, mid):
    """
    Get current labels (captions) for a Commons file.

    Args:
        session: requests Session object
        mid: The M-id (e.g., 'M12345')

    Returns:
        dict: Current labels by language code
    """
    api_url = 'https://commons.wikimedia.org/w/api.php'
    params = {
        'action': 'wbgetentities',
        'ids': mid,
        'format': 'json'
    }

    response = session.get(api_url, params=params)
    data = response.json()

    if 'entities' in data and mid in data['entities']:
        return data['entities'][mid].get('labels', {})
    return {}


def get_current_statements(session, mid):
    """
    Get current statements for a Commons file.

    Args:
        session: requests Session object
        mid: The M-id (e.g., 'M12345')

    Returns:
        dict: Current statements by property ID
    """
    api_url = 'https://commons.wikimedia.org/w/api.php'
    params = {
        'action': 'wbgetentities',
        'ids': mid,
        'format': 'json'
    }

    response = session.get(api_url, params=params)
    data = response.json()

    if 'entities' in data and mid in data['entities']:
        return data['entities'][mid].get('statements', {})
    return {}


def has_statement(statements, property_id):
    """Check if a statement with given property already exists."""
    return property_id in statements and len(statements[property_id]) > 0


def add_entity_statement(session, csrf_token, mid, property_id, qid, summary="Adding statement"):
    """
    Add a statement with an entity (Q-item) value.

    Args:
        session: requests Session object
        csrf_token: CSRF token
        mid: The M-id (e.g., 'M12345')
        property_id: Property ID (e.g., 'P31')
        qid: Q-item ID (e.g., 'Q1250322')
        summary: Edit summary

    Returns:
        dict: API response
    """
    api_url = 'https://commons.wikimedia.org/w/api.php'

    # Use wbcreateclaim for new claims
    value = json.dumps({
        "entity-type": "item",
        "numeric-id": int(qid[1:]),
        "id": qid
    })

    data = {
        'action': 'wbcreateclaim',
        'entity': mid,
        'snaktype': 'value',
        'property': property_id,
        'value': value,
        'token': csrf_token,
        'format': 'json',
        'summary': summary
    }

    response = session.post(api_url, data=data)
    return response.json()


def add_string_statement(session, csrf_token, mid, property_id, value, summary="Adding statement"):
    """
    Add a statement with a string value.

    Args:
        session: requests Session object
        csrf_token: CSRF token
        mid: The M-id (e.g., 'M12345')
        property_id: Property ID (e.g., 'P1163')
        value: String value
        summary: Edit summary

    Returns:
        dict: API response
    """
    api_url = 'https://commons.wikimedia.org/w/api.php'

    data = {
        'action': 'wbcreateclaim',
        'entity': mid,
        'snaktype': 'value',
        'property': property_id,
        'value': json.dumps(value),
        'token': csrf_token,
        'format': 'json',
        'summary': summary
    }

    response = session.post(api_url, data=data)
    return response.json()


def add_monolingual_statement(session, csrf_token, mid, property_id, text, language='nl', summary="Adding statement"):
    """
    Add a statement with a monolingual text value.

    Args:
        session: requests Session object
        csrf_token: CSRF token
        mid: The M-id (e.g., 'M12345')
        property_id: Property ID (e.g., 'P1476')
        text: The text value
        language: Language code (default: 'nl')
        summary: Edit summary

    Returns:
        dict: API response
    """
    api_url = 'https://commons.wikimedia.org/w/api.php'

    value = json.dumps({
        "text": text,
        "language": language
    })

    data = {
        'action': 'wbcreateclaim',
        'entity': mid,
        'snaktype': 'value',
        'property': property_id,
        'value': value,
        'token': csrf_token,
        'format': 'json',
        'summary': summary
    }

    response = session.post(api_url, data=data)
    return response.json()


def add_qualifier(session, csrf_token, claim_id, property_id, value, value_type='string', summary="Adding qualifier"):
    """
    Add a qualifier to an existing claim.

    Args:
        session: requests Session object
        csrf_token: CSRF token
        claim_id: The claim GUID
        property_id: Property ID for the qualifier
        value: The value (dict for entity, string for string)
        value_type: 'string' or 'entity'
        summary: Edit summary

    Returns:
        dict: API response
    """
    api_url = 'https://commons.wikimedia.org/w/api.php'

    if value_type == 'entity':
        value_json = json.dumps({
            "entity-type": "item",
            "numeric-id": int(value[1:]),
            "id": value
        })
    else:
        value_json = json.dumps(value)

    data = {
        'action': 'wbsetqualifier',
        'claim': claim_id,
        'snaktype': 'value',
        'property': property_id,
        'value': value_json,
        'token': csrf_token,
        'format': 'json',
        'summary': summary
    }

    response = session.post(api_url, data=data)
    return response.json()


def add_source_statement(session, csrf_token, mid, image_url, detail_url, summary="Adding source statement"):
    """
    Add the P7482 (source of file) statement with qualifiers.

    Args:
        session: requests Session object
        csrf_token: CSRF token
        mid: The M-id (e.g., 'M12345')
        image_url: URL to the full image (P953 qualifier)
        detail_url: URL to the metadata page (P973 qualifier)
        summary: Edit summary

    Returns:
        dict: API response
    """
    api_url = 'https://commons.wikimedia.org/w/api.php'

    # Step 1: Create the base claim (P7482 = Q74228490)
    value = json.dumps({
        "entity-type": "item",
        "numeric-id": int(Q_FILE_ON_INTERNET[1:]),
        "id": Q_FILE_ON_INTERNET
    })

    data = {
        'action': 'wbcreateclaim',
        'entity': mid,
        'snaktype': 'value',
        'property': P_SOURCE_OF_FILE,
        'value': value,
        'token': csrf_token,
        'format': 'json',
        'summary': summary
    }

    response = session.post(api_url, data=data)
    result = response.json()

    if 'error' in result:
        return result

    # Get the claim ID from the response
    claim_id = result['claim']['id']

    # Step 2: Add qualifiers
    # P137 - Operator (KB)
    add_qualifier(session, csrf_token, claim_id, P_OPERATOR, Q_KB_NETHERLANDS, 'entity', summary)

    # P953 - Full work URL
    add_qualifier(session, csrf_token, claim_id, P_FULL_WORK_URL, image_url, 'string', summary)

    # P973 - Described at URL
    add_qualifier(session, csrf_token, claim_id, P_DESCRIBED_AT_URL, detail_url, 'string', summary)

    return result


def add_all_statements(session, csrf_token, mid, image_url, detail_url, title, summary="Adding structured data"):
    """
    Add all standard statements to a Commons file.

    Statements added:
    - P31 (instance of) = Q1250322 (digital image)
    - P195 (collection) = Q1526131 (Koninklijke Bibliotheek)
    - P6216 (copyright status) = Q19652 (public domain)
    - P1163 (MIME type) = image/jpeg
    - P1476 (title) = title in Dutch
    - P7482 (source of file) = Q74228490 (file available on the internet)
      - P137 (operator) = Q1526131 (KB)
      - P953 (full work URL) = image_url
      - P973 (described at URL) = detail_url

    Args:
        session: requests Session object
        csrf_token: CSRF token
        mid: The M-id
        image_url: URL to the full image
        detail_url: URL to the metadata page
        title: Title in Dutch (from 'titel' column)
        summary: Edit summary

    Returns:
        dict: Results for each statement
    """
    results = {}
    current = get_current_statements(session, mid)

    # P31 - Instance of (digital image)
    if not has_statement(current, P_INSTANCE_OF):
        print(f"    Adding P31 (instance of: digital image)...")
        results['P31'] = add_entity_statement(
            session, csrf_token, mid, P_INSTANCE_OF, Q_DIGITAL_IMAGE, summary
        )
    else:
        print(f"    P31 already exists, skipping")
        results['P31'] = {'skipped': True}

    # P195 - Collection (KB)
    if not has_statement(current, P_COLLECTION):
        print(f"    Adding P195 (collection: KB)...")
        results['P195'] = add_entity_statement(
            session, csrf_token, mid, P_COLLECTION, Q_KB_NETHERLANDS, summary
        )
    else:
        print(f"    P195 already exists, skipping")
        results['P195'] = {'skipped': True}

    # P6216 - Copyright status (public domain)
    if not has_statement(current, P_COPYRIGHT_STATUS):
        print(f"    Adding P6216 (copyright: public domain)...")
        results['P6216'] = add_entity_statement(
            session, csrf_token, mid, P_COPYRIGHT_STATUS, Q_PUBLIC_DOMAIN, summary
        )
    else:
        print(f"    P6216 already exists, skipping")
        results['P6216'] = {'skipped': True}

    # P1163 - MIME type
    if not has_statement(current, P_MIME_TYPE):
        print(f"    Adding P1163 (MIME type: image/jpeg)...")
        results['P1163'] = add_string_statement(
            session, csrf_token, mid, P_MIME_TYPE, 'image/jpeg', summary
        )
    else:
        print(f"    P1163 already exists, skipping")
        results['P1163'] = {'skipped': True}

    # P1476 - Title (in Dutch)
    if not has_statement(current, P_TITLE):
        print(f"    Adding P1476 (title in Dutch)...")
        results['P1476'] = add_monolingual_statement(
            session, csrf_token, mid, P_TITLE, title, 'nl', summary
        )
    else:
        print(f"    P1476 already exists, skipping")
        results['P1476'] = {'skipped': True}

    # P7482 - Source of file (with qualifiers)
    if not has_statement(current, P_SOURCE_OF_FILE):
        print(f"    Adding P7482 (source of file with qualifiers)...")
        results['P7482'] = add_source_statement(
            session, csrf_token, mid, image_url, detail_url, summary
        )
    else:
        print(f"    P7482 already exists, skipping")
        results['P7482'] = {'skipped': True}

    return results


def add_dutch_description(session, csrf_token, mid, description, summary="Adding Dutch description"):
    """
    Add a Dutch description (label/caption) to a Commons file.

    Args:
        session: requests Session object
        csrf_token: CSRF token for authentication
        mid: The M-id (e.g., 'M12345')
        description: The Dutch description text
        summary: Edit summary

    Returns:
        dict: API response
    """
    api_url = 'https://commons.wikimedia.org/w/api.php'

    data = {
        'action': 'wbsetlabel',
        'id': mid,
        'language': 'nl',
        'value': description,
        'token': csrf_token,
        'format': 'json',
        'summary': summary
    }

    response = session.post(api_url, data=data)
    return response.json()


def load_excel():
    """Load the Excel file and return the DataFrame."""
    return pd.read_excel(EXCEL_FILE, sheet_name='all')


def update_structured_data_status(unique_id):
    """
    Update the structured_data_added column to True for a record in both sheets.

    Args:
        unique_id: The unique_id of the record (e.g., 'BBB-1')
    """
    try:
        # Read both sheets
        df_all = pd.read_excel(EXCEL_FILE, sheet_name='all')
        df_pd = pd.read_excel(EXCEL_FILE, sheet_name='public-domain-files')

        # Ensure column exists
        if 'structured_data_added' not in df_all.columns:
            df_all['structured_data_added'] = False
        if 'structured_data_added' not in df_pd.columns:
            df_pd['structured_data_added'] = False

        # Update in both sheets
        df_all.loc[df_all['unique_id'] == unique_id, 'structured_data_added'] = True
        df_pd.loc[df_pd['unique_id'] == unique_id, 'structured_data_added'] = True

        # Save
        with pd.ExcelWriter(EXCEL_FILE, engine='openpyxl') as writer:
            df_all.to_excel(writer, sheet_name='all', index=False)
            df_pd.to_excel(writer, sheet_name='public-domain-files', index=False)

        print(f"Updated structured_data_added=True for {unique_id}")
    except Exception as e:
        print(f"Warning: Could not update Excel: {e}")


def get_record_by_id(df, unique_id):
    """Get a record from the DataFrame by unique_id."""
    matches = df[df['unique_id'] == unique_id]
    if len(matches) == 0:
        return None
    return matches.iloc[0]


def process_statements_single(unique_id, preview_only=False):
    """
    Add structured data statements to a single file by unique_id.

    Args:
        unique_id: The unique_id of the record (e.g., 'BBB-1')
        preview_only: If True, only preview without making changes

    Returns:
        bool: True if successful, False otherwise
    """
    df = load_excel()
    row = get_record_by_id(df, unique_id)

    if row is None:
        print(f"ERROR: Record with unique_id '{unique_id}' not found.")
        return False

    # Get the data
    titel = safe_str(row.get('titel', ''))
    image_url = safe_str(row.get('image_url', ''))
    detail_url = safe_str(row.get('detail_url', ''))
    commons_url = safe_str(row.get('CommonsURL', ''))
    filename = safe_str(row.get('WikiCommonsFilename', ''))

    if not commons_url and not filename:
        print(f"ERROR: No CommonsURL or WikiCommonsFilename for {unique_id}")
        return False

    print("=" * 80)
    print(f"Adding statements for: {unique_id}")
    print("=" * 80)
    print(f"Title: {titel}")
    print(f"Image URL: {image_url}")
    print(f"Detail URL: {detail_url}")

    if preview_only:
        print("\nStatements to add:")
        print(f"  P31 (instance of) = Q1250322 (digital image)")
        print(f"  P195 (collection) = Q1526131 (KB)")
        print(f"  P6216 (copyright) = Q19652 (public domain)")
        print(f"  P1163 (MIME type) = image/jpeg")
        print(f"  P1476 (title) = nl: {titel}")
        print(f"  P7482 (source) = Q74228490 (file on internet)")
        print(f"    + P137 (operator) = Q1526131 (KB)")
        print(f"    + P953 (full work URL) = {image_url}")
        print(f"    + P973 (described at URL) = {detail_url}")
        print("\n[PREVIEW MODE - No changes made]")
        return True

    # Connect to Commons
    print("\nConnecting to Wikimedia Commons...")
    session, csrf_token = get_commons_session()

    # Get M-id
    mid = get_mid_from_filename(session, filename)
    if not mid:
        print(f"ERROR: Could not find M-id for {filename}")
        return False

    print(f"M-id: {mid}")
    print("\nAdding statements...")

    results = add_all_statements(
        session, csrf_token, mid, image_url, detail_url, titel,
        summary="Adding structured data from Beeldbank Nederlandse Boekgeschiedenis"
    )

    # Check results
    success = all('error' not in r for r in results.values() if not r.get('skipped'))
    if success:
        print("\nSuccess! All statements added.")
        # Update Excel to mark structured data as added
        update_structured_data_status(unique_id)
    else:
        print(f"\nSome statements failed: {results}")

    return success


def process_single(unique_id, preview_only=False):
    """
    Add Dutch description to a single file by unique_id.

    Args:
        unique_id: The unique_id of the record (e.g., 'BBB-1')
        preview_only: If True, only preview without making changes

    Returns:
        bool: True if successful, False otherwise
    """
    df = load_excel()
    row = get_record_by_id(df, unique_id)

    if row is None:
        print(f"ERROR: Record with unique_id '{unique_id}' not found.")
        return False

    # Get the data
    titel = safe_str(row.get('titel', ''))
    commons_url = safe_str(row.get('CommonsURL', ''))
    filename = safe_str(row.get('WikiCommonsFilename', ''))

    if not commons_url and not filename:
        print(f"ERROR: No CommonsURL or WikiCommonsFilename for {unique_id}")
        return False

    print("=" * 80)
    print(f"Processing: {unique_id}")
    print("=" * 80)
    print(f"Title (nl): {titel}")
    print(f"Commons URL: {commons_url}")
    print(f"Filename: {filename}")

    if preview_only:
        print("\n[PREVIEW MODE - No changes made]")
        return True

    # Connect to Commons
    print("\nConnecting to Wikimedia Commons...")
    session, csrf_token = get_commons_session()

    # Get M-id
    mid = get_mid_from_filename(session, filename)
    if not mid:
        print(f"ERROR: Could not find M-id for {filename}")
        return False

    print(f"M-id: {mid}")

    # Check current labels
    current_labels = get_current_labels(session, mid)
    if 'nl' in current_labels:
        current_nl = current_labels['nl']['value']
        print(f"Current Dutch label: {current_nl}")
        if current_nl == titel:
            print("Dutch label already set correctly. Skipping.")
            return True

    # Add the Dutch description
    print(f"\nAdding Dutch description...")
    result = add_dutch_description(
        session, csrf_token, mid, titel,
        summary="Adding Dutch description from Beeldbank Nederlandse Boekgeschiedenis"
    )

    if 'success' in result:
        print(f"Success! Dutch description added.")
        return True
    else:
        print(f"ERROR: {result}")
        return False


def process_batch(start_idx, end_idx, preview_only=False, delay=2):
    """
    Add Dutch descriptions to a batch of files.

    Args:
        start_idx: Starting row index (0-based)
        end_idx: Ending row index (exclusive)
        preview_only: If True, only preview without making changes
        delay: Delay between API calls in seconds

    Returns:
        tuple: (successful_count, failed_count, skipped_count)
    """
    df = load_excel()

    if end_idx > len(df):
        end_idx = len(df)

    print(f"Processing rows {start_idx} to {end_idx - 1} ({end_idx - start_idx} records)")

    session = None
    csrf_token = None

    if not preview_only:
        print("Connecting to Wikimedia Commons...")
        session, csrf_token = get_commons_session()

    successful = 0
    failed = 0
    skipped = 0

    for idx in range(start_idx, end_idx):
        row = df.iloc[idx]
        unique_id = safe_str(row.get('unique_id', ''))
        titel = safe_str(row.get('titel', ''))
        filename = safe_str(row.get('WikiCommonsFilename', ''))
        commons_url = safe_str(row.get('CommonsURL', ''))

        print(f"\n[{idx + 1}/{end_idx}] Processing: {unique_id}")

        # Skip if not uploaded yet
        if not commons_url:
            print(f"  SKIP: Not uploaded to Commons yet")
            skipped += 1
            continue

        if preview_only:
            print(f"  Title: {titel[:60]}...")
            successful += 1
            continue

        # Get M-id
        mid = get_mid_from_filename(session, filename)
        if not mid:
            print(f"  SKIP: Could not find M-id")
            skipped += 1
            continue

        # Check if already has Dutch label
        current_labels = get_current_labels(session, mid)
        if 'nl' in current_labels and current_labels['nl']['value'] == titel:
            print(f"  SKIP: Dutch label already set")
            skipped += 1
            continue

        # Add the Dutch description
        try:
            result = add_dutch_description(
                session, csrf_token, mid, titel,
                summary="Adding Dutch description from Beeldbank Nederlandse Boekgeschiedenis"
            )

            if 'success' in result:
                print(f"  SUCCESS: Dutch description added")
                successful += 1
            else:
                print(f"  FAILED: {result}")
                failed += 1

            # Delay between API calls
            if idx < end_idx - 1:
                time.sleep(delay)

        except Exception as e:
            print(f"  FAILED: {e}")
            failed += 1

    print(f"\n{'=' * 40}")
    print(f"Batch complete: {successful} successful, {failed} failed, {skipped} skipped")
    return successful, failed, skipped


def main():
    parser = argparse.ArgumentParser(description='Add structured data to Wikimedia Commons files')
    parser.add_argument('unique_id', nargs='?', help='Unique ID of record (e.g., BBB-1)')
    parser.add_argument('--preview', '-p', action='store_true', help='Preview only, do not make changes')
    parser.add_argument('--statements', '-s', action='store_true',
                        help='Add structured data statements (P31, P195, P6216, P1163, P1476, P7482)')
    parser.add_argument('--all', '-a', action='store_true',
                        help='Add both Dutch description and statements')
    parser.add_argument('--batch', '-b', nargs=2, type=int, metavar=('START', 'END'),
                        help='Process batch of records by row index')
    parser.add_argument('--delay', '-d', type=int, default=2,
                        help='Delay between API calls in seconds (default: 2)')

    args = parser.parse_args()

    if args.batch:
        # Batch mode
        if args.all:
            # Add both descriptions and statements
            print("Adding Dutch descriptions...")
            process_batch(args.batch[0], args.batch[1], preview_only=args.preview, delay=args.delay)
            print("\nAdding statements...")
            for idx in range(args.batch[0], args.batch[1]):
                df = load_excel()
                if idx < len(df):
                    row = df.iloc[idx]
                    unique_id = safe_str(row.get('unique_id', ''))
                    commons_url = safe_str(row.get('CommonsURL', ''))
                    if commons_url:
                        process_statements_single(unique_id, preview_only=args.preview)
        elif args.statements:
            # Statements only for batch
            for idx in range(args.batch[0], args.batch[1]):
                df = load_excel()
                if idx < len(df):
                    row = df.iloc[idx]
                    unique_id = safe_str(row.get('unique_id', ''))
                    commons_url = safe_str(row.get('CommonsURL', ''))
                    if commons_url:
                        process_statements_single(unique_id, preview_only=args.preview)
        else:
            # Default: Dutch descriptions only
            process_batch(args.batch[0], args.batch[1], preview_only=args.preview, delay=args.delay)
    elif args.unique_id:
        # Single file mode
        if args.all:
            # Add both
            process_single(args.unique_id, preview_only=args.preview)
            process_statements_single(args.unique_id, preview_only=args.preview)
        elif args.statements:
            # Statements only
            process_statements_single(args.unique_id, preview_only=args.preview)
        else:
            # Default: Dutch description only
            process_single(args.unique_id, preview_only=args.preview)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
