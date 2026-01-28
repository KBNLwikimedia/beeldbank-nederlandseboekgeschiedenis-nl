"""
Download images from Beeldbank Nederlandse Boekgeschiedenis.
Reads image URLs from Excel and downloads highest resolution images.
"""

import os
import re
import time
import requests
import pandas as pd
from pathlib import Path


def extract_filename_from_url(image_url: str) -> str:
    """Extract filename from image URL.

    Example:
    http://resolver.kb.nl/resolve?urn=urn:BBB:74G2_1494-GE_FOL91V-FOL92R
    --> BBB_74G2_1494-GE_FOL91V-FOL92R.jpg
    """
    # Extract the URN part after 'urn:'
    match = re.search(r'urn[=:]urn:([^&\s]+)', image_url)
    if match:
        urn = match.group(1)
        # Replace colons with underscores
        filename = urn.replace(':', '_') + '.jpg'
        return filename
    return None


def download_image(url: str, filepath: Path, timeout: int = 30) -> bool:
    """Download an image from URL to filepath."""
    try:
        response = requests.get(url, timeout=timeout, stream=True)
        response.raise_for_status()

        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception as e:
        print(f"    Error downloading: {e}")
        return False


def download_all_images(
    excel_file: str = "beeldbank_all.xlsx",
    output_folder: str = "images",
    save_every: int = 10
):
    """Download all images from Excel and update with local paths."""

    # Read Excel file
    print(f"Reading {excel_file}...")
    df = pd.read_excel(excel_file, engine="openpyxl")
    print(f"Found {len(df)} records")

    # Create output folder
    output_path = Path(output_folder).resolve()
    output_path.mkdir(exist_ok=True)
    print(f"Saving images to: {output_path}")

    # Add column for local path if not exists
    if 'local_image_path' not in df.columns:
        df['local_image_path'] = None

    # Download each image
    total = len(df)
    downloaded = 0
    skipped = 0
    failed = 0

    for idx, row in df.iterrows():
        image_url = row.get('image_url')
        nr = row.get('nr', idx + 1)

        if pd.isna(image_url) or not image_url:
            print(f"  [{idx+1}/{total}] Record #{nr}: No image URL - skipping")
            skipped += 1
            continue

        # Generate filename
        filename = extract_filename_from_url(image_url)
        if not filename:
            print(f"  [{idx+1}/{total}] Record #{nr}: Could not parse URL - skipping")
            skipped += 1
            continue

        filepath = output_path / filename

        # Check if already downloaded
        if filepath.exists():
            print(f"  [{idx+1}/{total}] Record #{nr}: Already exists - {filename}")
            df.at[idx, 'local_image_path'] = str(filepath)
            skipped += 1
        else:
            print(f"  [{idx+1}/{total}] Record #{nr}: Downloading {filename}...", flush=True)

            if download_image(image_url, filepath):
                df.at[idx, 'local_image_path'] = str(filepath)
                downloaded += 1
            else:
                failed += 1

            # Small delay to be polite to the server
            time.sleep(0.5)

        # Save progress every N records
        if (idx + 1) % save_every == 0:
            print(f"  Saving progress to {excel_file}...", flush=True)
            df.to_excel(excel_file, index=False, engine="openpyxl")

    # Final save
    df.to_excel(excel_file, index=False, engine="openpyxl")

    print(f"\n{'='*60}")
    print(f"DOWNLOAD COMPLETE")
    print(f"{'='*60}")
    print(f"  Downloaded: {downloaded}")
    print(f"  Skipped:    {skipped}")
    print(f"  Failed:     {failed}")
    print(f"  Total:      {total}")
    print(f"\nImages saved to: {output_path}")
    print(f"Excel updated:   {excel_file}")

    return df


if __name__ == "__main__":
    print("="*60)
    print("BEELDBANK IMAGE DOWNLOADER")
    print("="*60, flush=True)

    download_all_images(
        excel_file="beeldbank_all.xlsx",
        output_folder="images",
        save_every=10
    )
