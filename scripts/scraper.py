"""
Scraper for Beeldbank Nederlandse Boekgeschiedenis
Extracts metadata and image URLs from the KB image bank search results.
"""

import time
import pandas as pd
from playwright.sync_api import sync_playwright


def save_to_excel(records: list, output_file: str):
    """Save records to Excel file."""
    if not records:
        return

    df = pd.DataFrame(records)

    # Columns to exclude
    exclude_cols = {"thumbnail_url"}

    # Reorder columns
    preferred_order = [
        "nr", "titel", "vervaardiger", "datum", "type", "afmetingen",
        "inhoud", "omschrijving", "periode", "classificatie",
        "gerelateerde_term", "origineel", "aanwezig_in",
        "image_url", "detail_url"
    ]
    columns = [col for col in preferred_order if col in df.columns and col not in exclude_cols]
    columns += [col for col in df.columns if col not in columns and col not in exclude_cols]
    df = df[columns]

    df.to_excel(output_file, index=False, engine="openpyxl")


def scrape_detail_metadata(page, detail_url: str) -> dict:
    """Scrape metadata from a detail page."""
    metadata = {}

    try:
        page.goto(detail_url, wait_until="domcontentloaded")
        time.sleep(2)

        # Wait for the record content to load
        try:
            page.wait_for_selector("#jsru-search-record", timeout=10000)
            time.sleep(1)
        except:
            pass

        # Extract all metadata fields from the detail page
        metadata = page.evaluate("""
            () => {
                const data = {};

                // Known field labels to look for
                const fieldLabels = [
                    'Titel', 'Vervaardiger', 'Datum', 'Jaar', 'Type',
                    'Afmetingen', 'Inhoud', 'Omschrijving', 'Periode',
                    'Classificatie', 'Gerelateerde term', 'Gerelateerde termen',
                    'Origineel', 'Aanwezig in'
                ];

                // Method 1: Look for bold/strong elements followed by text
                const strongElements = document.querySelectorAll('#jsru-search-record strong, #jsru-search-record b');
                strongElements.forEach(el => {
                    const labelText = el.innerText.trim().replace(':', '');
                    if (fieldLabels.some(f => f.toLowerCase() === labelText.toLowerCase())) {
                        // Get the next sibling text or element
                        let value = '';
                        let nextNode = el.nextSibling;
                        while (nextNode && nextNode.nodeName !== 'STRONG' && nextNode.nodeName !== 'B' && nextNode.nodeName !== 'BR') {
                            if (nextNode.nodeType === Node.TEXT_NODE) {
                                value += nextNode.textContent;
                            } else if (nextNode.nodeType === Node.ELEMENT_NODE) {
                                value += nextNode.innerText;
                            }
                            nextNode = nextNode.nextSibling;
                        }
                        value = value.trim();
                        if (value) {
                            data[labelText.toLowerCase()] = value;
                        }
                    }
                });

                // Method 2: Look for spans with class containing 'label' or 'field'
                const labelSpans = document.querySelectorAll('#jsru-search-record span[class*="label"], #jsru-search-record .field-label');
                labelSpans.forEach(label => {
                    const key = label.innerText.trim().replace(':', '').toLowerCase();
                    const valueEl = label.nextElementSibling;
                    if (valueEl) {
                        const val = valueEl.innerText.trim();
                        if (key && val) {
                            data[key] = val;
                        }
                    }
                });

                // Method 3: Parse the text content looking for field patterns
                const recordDiv = document.querySelector('#jsru-search-record');
                if (recordDiv && Object.keys(data).length === 0) {
                    const html = recordDiv.innerHTML;
                    fieldLabels.forEach(label => {
                        // Look for pattern: <strong>Label</strong> or <b>Label</b> followed by value
                        const patterns = [
                            new RegExp('<strong[^>]*>' + label + ':?</strong>\\s*([^<]+)', 'i'),
                            new RegExp('<b[^>]*>' + label + ':?</b>\\s*([^<]+)', 'i'),
                            new RegExp(label + ':?\\s*</strong>\\s*([^<]+)', 'i'),
                            new RegExp(label + ':?\\s*</b>\\s*([^<]+)', 'i')
                        ];
                        for (const pattern of patterns) {
                            const match = html.match(pattern);
                            if (match && match[1]) {
                                data[label.toLowerCase()] = match[1].trim();
                                break;
                            }
                        }
                    });
                }

                return data;
            }
        """)

        # Debug: show what was extracted
        if metadata:
            keys = list(metadata.keys())[:5]
            print(f"    Found fields: {keys}{'...' if len(metadata) > 5 else ''}")
        else:
            print(f"    No metadata found")

    except Exception as e:
        print(f"  Error scraping {detail_url}: {e}")

    return metadata


def enrich_records_with_metadata(page, records: list, output_file: str) -> list:
    """Visit each detail page and add metadata to records."""
    total = len(records)

    for i, record in enumerate(records):
        detail_url = record.get('detail_url')
        if not detail_url:
            continue

        print(f"  [{i+1}/{total}] Fetching metadata for record #{record.get('nr', '?')}...", flush=True)

        metadata = scrape_detail_metadata(page, detail_url)

        # Map Dutch field names to column names
        field_mapping = {
            'titel': 'titel',
            'vervaardiger': 'vervaardiger',
            'datum': 'datum',
            'jaar': 'datum',
            'type': 'type',
            'afmetingen': 'afmetingen',
            'inhoud': 'inhoud',
            'omschrijving': 'omschrijving',
            'periode': 'periode',
            'classificatie': 'classificatie',
            'gerelateerde term': 'gerelateerde_term',
            'gerelateerde termen': 'gerelateerde_term',
            'origineel': 'origineel',
            'aanwezig in': 'aanwezig_in',
        }

        for dutch_key, col_name in field_mapping.items():
            if dutch_key in metadata and metadata[dutch_key]:
                # Only update if we don't have this field or it's empty
                if col_name not in record or not record[col_name]:
                    record[col_name] = metadata[dutch_key]

        # Also store any unmapped fields
        for key, value in metadata.items():
            normalized_key = key.replace(' ', '_')
            if normalized_key not in record:
                record[normalized_key] = value

        # Save to Excel every 10 records
        if (i + 1) % 10 == 0:
            print(f"  Saving progress to {output_file}...", flush=True)
            save_to_excel(records, output_file)

    return records


def scrape_all_pages(page) -> list:
    """Scrape all records from all pages of search results."""
    all_records = []
    url = "https://www.nederlandseboekgeschiedenis.nl/nl/beeldbank"

    print(f"Loading beeldbank: {url}")
    page.goto(url, wait_until="domcontentloaded")
    time.sleep(2)

    # Enter * in the search field
    print("Entering * in search field...")
    search_input = page.query_selector("#edit-searchform-fields-any-search-key")
    if search_input:
        search_input.fill("*")

    # Set results per page to 250
    print("Setting results per page to 250...")
    results_select = page.query_selector("#edit-searchform-results-limit")
    if results_select:
        results_select.select_option(value="3")  # value="3" = 250 results

    # Submit search
    print("Submitting search...")
    submit_button = page.query_selector("#edit-searchform-submit")
    if submit_button:
        submit_button.click()
        # Wait for table to appear, not for all images to load
        page.wait_for_selector("#jsru-search-results", timeout=30000)
        time.sleep(2)

    page_num = 1
    while True:
        print(f"\n--- Scraping page {page_num} ---", flush=True)

        # Wait for table to be present
        page.wait_for_selector("#jsru-search-results tr", timeout=30000)

        # Extract data from current page using JavaScript
        results = page.evaluate("""
            () => {
                const records = [];
                const rows = document.querySelectorAll('#jsru-search-results tr');

                rows.forEach((row, index) => {
                    if (index === 0) return;  // Skip header

                    const cells = row.querySelectorAll('td');
                    if (cells.length >= 4) {
                        const record = {};

                        // Nr (record number)
                        const nrLink = cells[0].querySelector('a');
                        if (nrLink) {
                            record.nr = nrLink.innerText.trim();
                            record.detail_url = nrLink.href;
                        }

                        // Thumbnail URL
                        const img = cells[1].querySelector('img');
                        if (img && img.src) {
                            record.thumbnail_url = img.src;
                            // Create full image URL by removing role parameter
                            record.image_url = img.src.replace('&role=thumbnail', '').replace('?role=thumbnail', '');
                        }

                        // Titel
                        const titleLink = cells[2].querySelector('a');
                        if (titleLink) {
                            record.titel = titleLink.innerText.trim();
                        }

                        // Vervaardiger
                        const creatorLinks = cells[3].querySelectorAll('a');
                        if (creatorLinks.length > 0) {
                            record.vervaardiger = Array.from(creatorLinks).map(a => a.innerText.trim()).join(', ');
                        } else {
                            record.vervaardiger = cells[3].innerText.trim();
                        }

                        // Datum
                        if (cells.length >= 5) {
                            const dateLink = cells[4].querySelector('a');
                            if (dateLink) {
                                record.datum = dateLink.innerText.trim();
                            } else {
                                record.datum = cells[4].innerText.trim();
                            }
                        }

                        if (record.nr) {
                            records.push(record);
                        }
                    }
                });

                return records;
            }
        """)

        print(f"Found {len(results)} records on page {page_num} (total: {len(all_records) + len(results)})", flush=True)

        # Stop if no results on this page
        if len(results) == 0:
            print("No results on this page - stopping.", flush=True)
            break

        all_records.extend(results)

        # Check for "Volgende pagina" button
        next_button = page.query_selector("#edit-searchform-next")

        if next_button and next_button.is_visible():
            print(f"Clicking 'Volgende pagina'...", flush=True)
            next_button.click()
            # Wait for new results, not for all images
            time.sleep(1)
            try:
                page.wait_for_selector("#jsru-search-results", timeout=30000)
                time.sleep(1)
            except:
                print("Timeout waiting for next page")
                break
            page_num += 1
        else:
            print("No more pages - done!", flush=True)
            break

    return all_records


def scrape_beeldbank(output_file: str = "beeldbank_all.xlsx"):
    """Scrape all beeldbank records and save to Excel."""

    records = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # Scrape all pages
        records = scrape_all_pages(page)
        print(f"\nTotal records scraped: {len(records)}")

        # Enrich with detail page metadata
        if records:
            print(f"\n--- Fetching metadata from detail pages ---")
            records = enrich_records_with_metadata(page, records, output_file)
            print(f"\nMetadata enrichment complete.")

        browser.close()

    # Save final results to Excel
    if records:
        save_to_excel(records, output_file)
        print(f"\nSaved {len(records)} records to {output_file}")
    else:
        print("No records were scraped.")

    return records


if __name__ == "__main__":
    print("="*60)
    print("BEELDBANK SCRAPER - Full Dataset")
    print("="*60, flush=True)

    records = scrape_beeldbank(output_file="beeldbank_all.xlsx")

    print("\n" + "="*60)
    print(f"SCRAPING COMPLETE - {len(records)} records")
    print("="*60)

    # Show sample
    if records:
        print("\nFirst 3 records:")
        for r in records[:3]:
            print(f"  #{r.get('nr')}: {r.get('titel', 'N/A')[:50]}...")

        print("\nLast 3 records:")
        for r in records[-3:]:
            print(f"  #{r.get('nr')}: {r.get('titel', 'N/A')[:50]}...")
