"""
Generate HTML preview pages for Commons category mapping review.

This script creates visual HTML galleries to review which images are mapped
to which Wikimedia Commons categories. Useful for quality control before
uploading.

Usage:
    python create_preview.py                    # Create all preview pages
    python create_preview.py "Dutch typography" # Create specific category preview

Output files:
    - preview_dutch_typography.html
    - preview_printing_netherlands.html
    - preview_bookbinding_netherlands.html
    - preview_libraries_netherlands.html
"""

import pandas as pd
import os
import sys

# Excel file path
EXCEL_FILE = 'nbg-beeldbank_all_24012026.xlsx'


def create_preview_html(df, category_name, output_file):
    """
    Create an HTML preview page for a specific category.

    Generates a responsive grid of image cards showing thumbnails, titles,
    descriptions, and classification info for all images mapped to the
    specified Commons category.

    Args:
        df: pandas DataFrame with the Excel data
        category_name: Commons category name (e.g., 'Dutch typography')
        output_file: Output HTML filename

    Returns:
        int: Number of images in the category
    """

    # Filter for the category
    filtered = df[df['commons_categories'].str.contains(category_name, na=False)]

    print(f'Creating HTML preview for {category_name}: {len(filtered)} images')

    # Map category to classificatie code
    category_mapping = {
        'Dutch typography': 'C: Paleografie, letterontwerp, lettertypen, lettergieten, schrift',
        'Printing in the Netherlands': 'D: Geschiedenis van de boekdrukkunst',
        'Bookbinding in the Netherlands': 'F: Bindkunst',
        'Libraries in the Netherlands': 'J: Bibliotheken en instellingen',
    }

    mapped_from = category_mapping.get(category_name, 'Unknown')
    commons_url = f"https://commons.wikimedia.org/wiki/Category:{category_name.replace(' ', '_')}"

    html_parts = []
    html_parts.append(f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{category_name} - Category Preview</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        h1 {{ color: #333; }}
        .stats {{
            background: #e0e0e0;
            padding: 10px 20px;
            border-radius: 5px;
            margin-bottom: 20px;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 20px;
        }}
        .card {{
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .card img {{
            width: 100%;
            height: 250px;
            object-fit: contain;
            background: #eee;
        }}
        .card-content {{ padding: 15px; }}
        .card-title {{
            font-weight: bold;
            font-size: 14px;
            margin-bottom: 10px;
            color: #1a1a1a;
        }}
        .card-desc {{
            font-size: 12px;
            color: #666;
            max-height: 100px;
            overflow-y: auto;
            margin-bottom: 10px;
        }}
        .card-meta {{
            font-size: 11px;
            color: #999;
            border-top: 1px solid #eee;
            padding-top: 10px;
        }}
        .card-id {{ font-weight: bold; color: #0066cc; }}
    </style>
</head>
<body>
    <h1>Category Preview: {category_name}</h1>
    <div class="stats">
        <strong>Total images:</strong> {len(filtered)}<br>
        <strong>Commons category:</strong> <a href="{commons_url}" target="_blank">Category:{category_name}</a><br>
        <strong>Mapped from:</strong> {mapped_from}
    </div>
    <div class="grid">
''')

    for idx, row in filtered.iterrows():
        unique_id = str(row.get('unique_id', ''))
        title = str(row.get('titel', '')).replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')
        desc = str(row.get('inhoud', ''))
        if pd.isna(row.get('inhoud')) or desc == 'nan':
            desc = '(geen beschrijving)'
        desc = desc.replace('<', '&lt;').replace('>', '&gt;')

        classificatie = str(row.get('classificatie', ''))

        # Use local image path - convert backslashes to forward slashes
        local_path = str(row.get('local_image_path', ''))
        img_src = 'file:///' + local_path.replace('\\', '/')

        truncated_desc = desc[:500] + "..." if len(desc) > 500 else desc

        html_parts.append(f'''
        <div class="card">
            <img src="{img_src}" alt="{title}" loading="lazy">
            <div class="card-content">
                <div class="card-title">{title}</div>
                <div class="card-desc">{truncated_desc}</div>
                <div class="card-meta">
                    <span class="card-id">{unique_id}</span><br>
                    Classificatie: {classificatie}
                </div>
            </div>
        </div>
''')

    html_parts.append('''
    </div>
</body>
</html>
''')

    # Write the HTML file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(''.join(html_parts))

    print(f'Created: {output_file}')
    return len(filtered)


if __name__ == "__main__":
    # Read the Excel file
    df = pd.read_excel(EXCEL_FILE)

    # Categories to create previews for
    categories = [
        ('Dutch typography', 'preview_dutch_typography.html'),
        ('Printing in the Netherlands', 'preview_printing_netherlands.html'),
        ('Bookbinding in the Netherlands', 'preview_bookbinding_netherlands.html'),
        ('Libraries in the Netherlands', 'preview_libraries_netherlands.html'),
    ]

    # If command line argument provided, only create that one
    if len(sys.argv) > 1:
        cat_name = sys.argv[1]
        for name, filename in categories:
            if cat_name.lower() in name.lower():
                create_preview_html(df, name, filename)
                break
    else:
        # Create all previews
        for name, filename in categories:
            create_preview_html(df, name, filename)