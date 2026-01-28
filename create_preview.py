"""
Generate HTML preview pages for Commons category mapping review.

This script creates visual HTML galleries to review which public domain images
are mapped to which Wikimedia Commons categories. Useful for quality control
before uploading.

Usage:
    python create_preview.py                    # Create all preview pages
    python create_preview.py "Dutch typography" # Create specific category preview

Output files (in previews/ folder):
    - pd_preview_dutch_typography.html
    - pd_preview_printing_netherlands.html
    - pd_preview_bookbinding_netherlands.html
    - pd_preview_libraries_netherlands.html
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

    # Create a safe key for localStorage based on category name
    storage_key = category_name.lower().replace(' ', '_').replace('the_', '')

    html_parts = []
    html_parts.append(f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{category_name} - Public Domain Files Preview</title>
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
        .controls {{
            background: #fff3cd;
            border: 1px solid #ffc107;
            padding: 15px 20px;
            border-radius: 5px;
            margin-bottom: 20px;
            position: sticky;
            top: 0;
            z-index: 100;
        }}
        .controls button {{
            padding: 8px 16px;
            margin-right: 10px;
            cursor: pointer;
            border: none;
            border-radius: 4px;
        }}
        .controls button.primary {{
            background: #007bff;
            color: white;
        }}
        .controls button.secondary {{
            background: #6c757d;
            color: white;
        }}
        .excluded-list {{
            background: #f8d7da;
            border: 1px solid #f5c6cb;
            padding: 15px 20px;
            border-radius: 5px;
            margin-bottom: 20px;
            display: none;
        }}
        .excluded-list.visible {{
            display: block;
        }}
        .excluded-list pre {{
            background: white;
            padding: 10px;
            border-radius: 4px;
            max-height: 200px;
            overflow-y: auto;
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
            position: relative;
            border: 3px solid transparent;
        }}
        .card.excluded {{
            border-color: #dc3545;
            opacity: 0.6;
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
        .card-toggle {{
            position: absolute;
            top: 10px;
            right: 10px;
            padding: 8px 12px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-weight: bold;
            font-size: 12px;
        }}
        .card-toggle.include {{
            background: #28a745;
            color: white;
        }}
        .card-toggle.exclude {{
            background: #dc3545;
            color: white;
        }}
    </style>
</head>
<body>
    <h1>Public Domain Files - Category Preview: {category_name}</h1>
    <div class="stats">
        <strong>Total images:</strong> {len(filtered)}<br>
        <strong>Commons category:</strong> <a href="{commons_url}" target="_blank">Category:{category_name}</a><br>
        <strong>Mapped from:</strong> {mapped_from}
    </div>
    <div class="controls">
        <strong>Selection:</strong>
        <span id="include-count">{len(filtered)}</span> included,
        <span id="exclude-count">0</span> excluded
        &nbsp;|&nbsp;
        <button class="secondary" onclick="toggleExcludedList()">Show/Hide Excluded List</button>
        <button class="secondary" onclick="openJSONFile()">Open JSON File</button>
        <button class="primary" onclick="saveSelection()">Save Selection</button>
        <button class="secondary" onclick="resetAll()">Reset All</button>
        <span id="save-status" style="margin-left: 10px; color: #666;"></span>
    </div>
    <div class="excluded-list" id="excluded-list">
        <strong>Excluded files (will NOT get this category):</strong>
        <pre id="excluded-ids"></pre>
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

        # Use KB resolver URL (works when served via web server)
        img_src = str(row.get('image_url', ''))
        if not img_src or img_src == 'nan':
            img_src = ''

        truncated_desc = desc[:500] + "..." if len(desc) > 500 else desc

        html_parts.append(f'''
        <div class="card" data-id="{unique_id}">
            <button class="card-toggle include" onclick="toggleCard(this, '{unique_id}')">✓ Include</button>
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

    html_parts.append(f'''
    </div>
    <script>
        const STORAGE_KEY = 'excluded_{storage_key}';
        let excludedIds = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');

        // Initialize on page load - try JSON first, fallback to localStorage
        document.addEventListener('DOMContentLoaded', function() {{
            // First apply any localStorage exclusions (will be overwritten by JSON if available)
            applyExclusionsToUI();
            updateCounts();
        }});

        function toggleCard(btn, id) {{
            const card = btn.closest('.card');
            const isExcluded = card.classList.contains('excluded');

            if (isExcluded) {{
                // Include it
                card.classList.remove('excluded');
                btn.classList.remove('exclude');
                btn.classList.add('include');
                btn.textContent = '✓ Include';
                excludedIds = excludedIds.filter(x => x !== id);
            }} else {{
                // Exclude it
                card.classList.add('excluded');
                btn.classList.remove('include');
                btn.classList.add('exclude');
                btn.textContent = '✗ Excluded';
                if (!excludedIds.includes(id)) {{
                    excludedIds.push(id);
                }}
            }}

            localStorage.setItem(STORAGE_KEY, JSON.stringify(excludedIds));
            updateCounts();
        }}

        function updateCounts() {{
            const total = document.querySelectorAll('.card').length;
            const excluded = excludedIds.length;
            document.getElementById('exclude-count').textContent = excluded;
            document.getElementById('include-count').textContent = total - excluded;
            document.getElementById('excluded-ids').textContent = excludedIds.join('\\n') || '(none)';
        }}

        function toggleExcludedList() {{
            document.getElementById('excluded-list').classList.toggle('visible');
        }}

        const CATEGORY_NAME = '{category_name}';
        const JSON_FILENAME = '../category_exclusions.json';
        let fileHandle = null;

        // Open the JSON file to get a file handle for saving
        async function openJSONFile() {{
            if (!('showOpenFilePicker' in window)) {{
                alert('File System Access API not supported. Use Chrome or Edge.');
                return;
            }}
            try {{
                const [handle] = await window.showOpenFilePicker({{
                    types: [{{ description: 'JSON', accept: {{ 'application/json': ['.json'] }} }}],
                    multiple: false
                }});
                fileHandle = handle;

                // Load the file contents
                const file = await handle.getFile();
                const text = await file.text();
                const data = JSON.parse(text);
                const exclusions = data.category_exclusions || {{}};

                // Update localStorage with all categories
                const categoryKeys = {{
                    'Dutch typography': 'dutch_typography',
                    'Printing in the Netherlands': 'printing_in_netherlands',
                    'Bookbinding in the Netherlands': 'bookbinding_in_netherlands',
                    'Libraries in the Netherlands': 'libraries_in_netherlands'
                }};

                Object.entries(categoryKeys).forEach(([name, key]) => {{
                    const ids = exclusions[name] || [];
                    localStorage.setItem('excluded_' + key, JSON.stringify(ids));
                }});

                // Update current category
                excludedIds = exclusions[CATEGORY_NAME] || [];
                applyExclusionsToUI();
                updateCounts();

                setStatus('Opened ' + handle.name + ' - ready to save');
            }} catch (err) {{
                if (err.name !== 'AbortError') {{
                    console.error('Error opening file:', err);
                    setStatus('Error: ' + err.message);
                }}
            }}
        }}

        // Load exclusions from JSON file on page load
        async function loadFromJSON() {{
            try {{
                const response = await fetch(JSON_FILENAME);
                if (response.ok) {{
                    const data = await response.json();
                    const exclusions = data.category_exclusions || {{}};

                    // Load this category's exclusions
                    excludedIds = exclusions[CATEGORY_NAME] || [];
                    localStorage.setItem(STORAGE_KEY, JSON.stringify(excludedIds));

                    // Update UI
                    applyExclusionsToUI();
                    updateCounts();
                    setStatus('Loaded from ' + JSON_FILENAME);
                }}
            }} catch (err) {{
                console.log('Could not load JSON file:', err);
                setStatus('Using localStorage (JSON file not found)');
            }}
        }}

        function applyExclusionsToUI() {{
            document.querySelectorAll('.card').forEach(card => {{
                const id = card.dataset.id;
                const btn = card.querySelector('.card-toggle');
                if (excludedIds.includes(id)) {{
                    card.classList.add('excluded');
                    btn.classList.remove('include');
                    btn.classList.add('exclude');
                    btn.textContent = '✗ Excluded';
                }} else {{
                    card.classList.remove('excluded');
                    btn.classList.remove('exclude');
                    btn.classList.add('include');
                    btn.textContent = '✓ Include';
                }}
            }});
        }}

        function setStatus(msg) {{
            document.getElementById('save-status').textContent = msg;
        }}

        async function saveSelection() {{
            // Build the complete exclusions object from all localStorage
            const allExclusions = {{}};
            const categoryKeys = {{
                'dutch_typography': 'Dutch typography',
                'printing_in_netherlands': 'Printing in the Netherlands',
                'bookbinding_in_netherlands': 'Bookbinding in the Netherlands',
                'libraries_in_netherlands': 'Libraries in the Netherlands'
            }};

            Object.entries(categoryKeys).forEach(([key, name]) => {{
                const excluded = JSON.parse(localStorage.getItem('excluded_' + key) || '[]');
                if (excluded.length > 0) {{
                    allExclusions[name] = excluded;
                }}
            }});

            const json = JSON.stringify({{ category_exclusions: allExclusions }}, null, 2);

            // If we have a file handle, save directly
            if (fileHandle) {{
                try {{
                    const writable = await fileHandle.createWritable();
                    await writable.write(json);
                    await writable.close();
                    setStatus('Saved ✓');
                    return;
                }} catch (err) {{
                    console.error('Save error:', err);
                    setStatus('Error saving: ' + err.message);
                    return;
                }}
            }}

            // No file handle - prompt user to open file first
            if ('showOpenFilePicker' in window) {{
                setStatus('Click "Open JSON File" first to select category_exclusions.json');
                return;
            }}

            // Fallback for browsers without File System Access API: download the file
            const blob = new Blob([json], {{ type: 'application/json' }});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'category_exclusions.json';
            a.click();
            URL.revokeObjectURL(url);
            setStatus('Downloaded category_exclusions.json (save to project root folder)');
        }}

        // Load from JSON file when page loads
        loadFromJSON();

        function resetAll() {{
            if (confirm('Reset all selections? This will include all images again.')) {{
                excludedIds = [];
                localStorage.setItem(STORAGE_KEY, JSON.stringify(excludedIds));
                document.querySelectorAll('.card.excluded').forEach(card => {{
                    card.classList.remove('excluded');
                    const btn = card.querySelector('.card-toggle');
                    btn.classList.remove('exclude');
                    btn.classList.add('include');
                    btn.textContent = '✓ Include';
                }});
                updateCounts();
            }}
        }}
    </script>
</body>
</html>
''')

    # Write the HTML file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(''.join(html_parts))

    print(f'Created: {output_file}')
    return len(filtered)


def create_combined_preview_html(df, output_file):
    """
    Create a single HTML file with tabs for all 4 categories.

    Args:
        df: pandas DataFrame with the Excel data
        output_file: Output HTML filename
    """
    categories = [
        ('Dutch typography', 'dutch_typography', 'C: Paleografie, letterontwerp, lettertypen, lettergieten, schrift'),
        ('Printing in the Netherlands', 'printing_in_netherlands', 'D: Geschiedenis van de boekdrukkunst'),
        ('Bookbinding in the Netherlands', 'bookbinding_in_netherlands', 'F: Bindkunst'),
        ('Libraries in the Netherlands', 'libraries_in_netherlands', 'J: Bibliotheken en instellingen'),
    ]

    html_parts = []
    html_parts.append('''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Category Preview - Public Domain Files</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        h1 { color: #333; margin-bottom: 20px; }

        /* Tabs */
        .tabs {
            display: flex;
            border-bottom: 2px solid #dee2e6;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        .tab {
            padding: 12px 24px;
            cursor: pointer;
            border: 1px solid transparent;
            border-bottom: none;
            margin-bottom: -2px;
            background: #e9ecef;
            border-radius: 8px 8px 0 0;
            margin-right: 4px;
        }
        .tab:hover { background: #dee2e6; }
        .tab.active {
            background: white;
            border-color: #dee2e6;
            font-weight: bold;
        }
        .tab-count {
            font-size: 12px;
            color: #666;
            margin-left: 5px;
        }
        .tab-content {
            display: none;
            background: white;
            padding: 20px;
            border-radius: 0 8px 8px 8px;
        }
        .tab-content.active { display: block; }

        /* Controls */
        .controls {
            background: #fff3cd;
            border: 1px solid #ffc107;
            padding: 15px 20px;
            border-radius: 5px;
            margin-bottom: 20px;
            position: sticky;
            top: 0;
            z-index: 100;
        }
        .controls button {
            padding: 8px 16px;
            margin-right: 10px;
            cursor: pointer;
            border: none;
            border-radius: 4px;
        }
        .controls button.primary { background: #007bff; color: white; }
        .controls button.secondary { background: #6c757d; color: white; }

        /* Stats */
        .stats {
            background: #e0e0e0;
            padding: 10px 20px;
            border-radius: 5px;
            margin-bottom: 20px;
        }

        /* Excluded list */
        .excluded-list {
            background: #f8d7da;
            border: 1px solid #f5c6cb;
            padding: 15px 20px;
            border-radius: 5px;
            margin-bottom: 20px;
            display: none;
        }
        .excluded-list.visible { display: block; }
        .excluded-list pre {
            background: white;
            padding: 10px;
            border-radius: 4px;
            max-height: 200px;
            overflow-y: auto;
        }

        /* Grid */
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 20px;
        }
        .card {
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            overflow: hidden;
            position: relative;
            border: 3px solid transparent;
        }
        .card.excluded {
            border-color: #dc3545;
            opacity: 0.6;
        }
        .card img {
            width: 100%;
            height: 250px;
            object-fit: contain;
            background: #eee;
        }
        .card-content { padding: 15px; }
        .card-title {
            font-weight: bold;
            font-size: 14px;
            margin-bottom: 10px;
            color: #1a1a1a;
        }
        .card-desc {
            font-size: 12px;
            color: #666;
            max-height: 100px;
            overflow-y: auto;
            margin-bottom: 10px;
        }
        .card-meta {
            font-size: 11px;
            color: #999;
            border-top: 1px solid #eee;
            padding-top: 10px;
        }
        .card-id { font-weight: bold; color: #0066cc; }
        .card-toggle {
            position: absolute;
            top: 10px;
            right: 10px;
            padding: 8px 12px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-weight: bold;
            font-size: 12px;
        }
        .card-toggle.include { background: #28a745; color: white; }
        .card-toggle.exclude { background: #dc3545; color: white; }
    </style>
</head>
<body>
    <h1>Public Domain Files - Category Preview</h1>

    <div class="controls">
        <button class="secondary" onclick="openJSONFile()">Open JSON File</button>
        <button class="primary" onclick="saveSelection()">Save Selection</button>
        <button class="secondary" onclick="toggleExcludedList()">Show/Hide Excluded</button>
        <button class="secondary" onclick="resetCurrentTab()">Reset Current Tab</button>
        <span id="save-status" style="margin-left: 10px; color: #666;"></span>
    </div>

    <div class="excluded-list" id="excluded-list">
        <strong>Excluded files for current category:</strong>
        <pre id="excluded-ids"></pre>
    </div>

    <div class="tabs">
''')

    # Add tab buttons
    for i, (cat_name, cat_key, _) in enumerate(categories):
        filtered = df[df['commons_categories'].str.contains(cat_name, na=False)]
        count = len(filtered)
        active = 'active' if i == 0 else ''
        html_parts.append(f'''        <div class="tab {active}" onclick="switchTab('{cat_key}')" data-tab="{cat_key}">
            {cat_name}<span class="tab-count">({count})</span>
        </div>
''')

    html_parts.append('    </div>\n')

    # Add tab contents
    for i, (cat_name, cat_key, mapped_from) in enumerate(categories):
        filtered = df[df['commons_categories'].str.contains(cat_name, na=False)]
        commons_url = f"https://commons.wikimedia.org/wiki/Category:{cat_name.replace(' ', '_')}"
        active = 'active' if i == 0 else ''

        html_parts.append(f'''
    <div class="tab-content {active}" id="tab-{cat_key}" data-category="{cat_name}">
        <div class="stats">
            <strong>Total images:</strong> <span class="total-count">{len(filtered)}</span> |
            <strong>Included:</strong> <span class="include-count">{len(filtered)}</span> |
            <strong>Excluded:</strong> <span class="exclude-count">0</span><br>
            <strong>Commons:</strong> <a href="{commons_url}" target="_blank">Category:{cat_name}</a> |
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
            img_src = str(row.get('image_url', ''))
            if not img_src or img_src == 'nan':
                img_src = ''
            truncated_desc = desc[:500] + "..." if len(desc) > 500 else desc

            html_parts.append(f'''            <div class="card" data-id="{unique_id}">
                <button class="card-toggle include" onclick="toggleCard(this, '{unique_id}', '{cat_key}')">✓ Include</button>
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

        html_parts.append('        </div>\n    </div>\n')

    # Add JavaScript
    html_parts.append('''
    <script>
        const JSON_FILENAME = 'category_exclusions.json';
        let fileHandle = null;
        let currentTab = 'dutch_typography';

        const categoryKeys = {
            'dutch_typography': 'Dutch typography',
            'printing_in_netherlands': 'Printing in the Netherlands',
            'bookbinding_in_netherlands': 'Bookbinding in the Netherlands',
            'libraries_in_netherlands': 'Libraries in the Netherlands'
        };

        // Store exclusions per category
        const exclusions = {
            'dutch_typography': [],
            'printing_in_netherlands': [],
            'bookbinding_in_netherlands': [],
            'libraries_in_netherlands': []
        };

        // Load from localStorage on init
        Object.keys(exclusions).forEach(key => {
            exclusions[key] = JSON.parse(localStorage.getItem('excluded_' + key) || '[]');
        });

        function switchTab(tabKey) {
            currentTab = tabKey;

            // Update tab buttons
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelector(`.tab[data-tab="${tabKey}"]`).classList.add('active');

            // Update tab contents
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            document.getElementById('tab-' + tabKey).classList.add('active');

            updateCounts();
            updateExcludedList();
        }

        function toggleCard(btn, id, catKey) {
            const card = btn.closest('.card');
            const isExcluded = card.classList.contains('excluded');

            if (isExcluded) {
                card.classList.remove('excluded');
                btn.classList.remove('exclude');
                btn.classList.add('include');
                btn.textContent = '✓ Include';
                exclusions[catKey] = exclusions[catKey].filter(x => x !== id);
            } else {
                card.classList.add('excluded');
                btn.classList.remove('include');
                btn.classList.add('exclude');
                btn.textContent = '✗ Excluded';
                if (!exclusions[catKey].includes(id)) {
                    exclusions[catKey].push(id);
                }
            }

            localStorage.setItem('excluded_' + catKey, JSON.stringify(exclusions[catKey]));
            updateCounts();
            updateExcludedList();
        }

        function updateCounts() {
            const tabContent = document.getElementById('tab-' + currentTab);
            const total = tabContent.querySelectorAll('.card').length;
            const excluded = exclusions[currentTab].length;
            tabContent.querySelector('.include-count').textContent = total - excluded;
            tabContent.querySelector('.exclude-count').textContent = excluded;
        }

        function updateExcludedList() {
            document.getElementById('excluded-ids').textContent =
                exclusions[currentTab].join('\\n') || '(none)';
        }

        function toggleExcludedList() {
            document.getElementById('excluded-list').classList.toggle('visible');
        }

        function setStatus(msg) {
            document.getElementById('save-status').textContent = msg;
        }

        async function openJSONFile() {
            if (!('showOpenFilePicker' in window)) {
                alert('File System Access API not supported. Use Chrome or Edge.');
                return;
            }
            try {
                const [handle] = await window.showOpenFilePicker({
                    types: [{ description: 'JSON', accept: { 'application/json': ['.json'] } }],
                    multiple: false
                });
                fileHandle = handle;

                const file = await handle.getFile();
                const text = await file.text();
                const data = JSON.parse(text);
                const loadedExclusions = data.category_exclusions || {};

                // Update exclusions from file
                Object.entries(categoryKeys).forEach(([key, name]) => {
                    exclusions[key] = loadedExclusions[name] || [];
                    localStorage.setItem('excluded_' + key, JSON.stringify(exclusions[key]));
                });

                // Apply to UI
                applyAllExclusions();
                setStatus('Opened ' + handle.name + ' - ready to save');
            } catch (err) {
                if (err.name !== 'AbortError') {
                    console.error('Error opening file:', err);
                    setStatus('Error: ' + err.message);
                }
            }
        }

        async function loadFromJSON() {
            try {
                const response = await fetch(JSON_FILENAME);
                if (response.ok) {
                    const data = await response.json();
                    const loadedExclusions = data.category_exclusions || {};

                    Object.entries(categoryKeys).forEach(([key, name]) => {
                        exclusions[key] = loadedExclusions[name] || [];
                        localStorage.setItem('excluded_' + key, JSON.stringify(exclusions[key]));
                    });

                    applyAllExclusions();
                    setStatus('Loaded from ' + JSON_FILENAME);
                }
            } catch (err) {
                console.log('Could not load JSON file:', err);
                setStatus('Using localStorage');
            }
        }

        function applyAllExclusions() {
            Object.keys(exclusions).forEach(catKey => {
                const tabContent = document.getElementById('tab-' + catKey);
                tabContent.querySelectorAll('.card').forEach(card => {
                    const id = card.dataset.id;
                    const btn = card.querySelector('.card-toggle');
                    if (exclusions[catKey].includes(id)) {
                        card.classList.add('excluded');
                        btn.classList.remove('include');
                        btn.classList.add('exclude');
                        btn.textContent = '✗ Excluded';
                    } else {
                        card.classList.remove('excluded');
                        btn.classList.remove('exclude');
                        btn.classList.add('include');
                        btn.textContent = '✓ Include';
                    }
                });
            });
            updateCounts();
            updateExcludedList();
        }

        async function saveSelection() {
            const allExclusions = {};
            Object.entries(categoryKeys).forEach(([key, name]) => {
                if (exclusions[key].length > 0) {
                    allExclusions[name] = exclusions[key];
                }
            });

            const json = JSON.stringify({ category_exclusions: allExclusions }, null, 2);

            if (fileHandle) {
                try {
                    const writable = await fileHandle.createWritable();
                    await writable.write(json);
                    await writable.close();
                    setStatus('Saved ✓');
                    return;
                } catch (err) {
                    console.error('Save error:', err);
                    setStatus('Error saving: ' + err.message);
                    return;
                }
            }

            if ('showOpenFilePicker' in window) {
                setStatus('Click "Open JSON File" first');
                return;
            }

            // Fallback: download
            const blob = new Blob([json], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'category_exclusions.json';
            a.click();
            URL.revokeObjectURL(url);
            setStatus('Downloaded (save to project folder)');
        }

        function resetCurrentTab() {
            if (confirm('Reset all selections for this category?')) {
                exclusions[currentTab] = [];
                localStorage.setItem('excluded_' + currentTab, '[]');

                const tabContent = document.getElementById('tab-' + currentTab);
                tabContent.querySelectorAll('.card.excluded').forEach(card => {
                    card.classList.remove('excluded');
                    const btn = card.querySelector('.card-toggle');
                    btn.classList.remove('exclude');
                    btn.classList.add('include');
                    btn.textContent = '✓ Include';
                });
                updateCounts();
                updateExcludedList();
            }
        }

        // Initialize
        document.addEventListener('DOMContentLoaded', function() {
            applyAllExclusions();
            loadFromJSON();
        });
    </script>
</body>
</html>
''')

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(''.join(html_parts))

    print(f'Created combined preview: {output_file}')


def create_public_domain_review_html(df, output_file, per_page=100):
    """
    Create an HTML page to review ALL public domain files for copyright verification.

    Shows all images with ID, title, date, and creator so user can verify
    each is truly in the public domain. Includes pagination.

    Args:
        df: pandas DataFrame with public domain files
        output_file: Output HTML filename
        per_page: Number of images per page (default 100)
    """
    # Sort by date (newest first), then by BBB id
    # Extract numeric part of unique_id for proper sorting (BBB-1, BBB-2, ..., BBB-1000)
    df = df.copy()
    df['_sort_id'] = df['unique_id'].str.extract(r'BBB-(\d+)').astype(int)
    df = df.sort_values(by=['datum', '_sort_id'], ascending=[False, True])
    df = df.drop(columns=['_sort_id'])

    total_images = len(df)
    total_pages = (total_images + per_page - 1) // per_page  # Ceiling division
    print(f'Creating public domain review page: {total_images} images ({total_pages} pages, sorted by date desc, then BBB id)')

    html_parts = []
    html_parts.append(f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Public Domain Files Review - Copyright Verification</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        h1 {{ color: #333; }}
        .stats {{
            background: #d4edda;
            border: 1px solid #c3e6cb;
            padding: 15px 20px;
            border-radius: 5px;
            margin-bottom: 20px;
        }}
        .controls {{
            background: #fff3cd;
            border: 1px solid #ffc107;
            padding: 15px 20px;
            border-radius: 5px;
            margin-bottom: 20px;
            position: sticky;
            top: 0;
            z-index: 100;
        }}
        .controls button {{
            padding: 8px 16px;
            margin-right: 10px;
            cursor: pointer;
            border: none;
            border-radius: 4px;
        }}
        .controls button.primary {{ background: #007bff; color: white; }}
        .controls button.secondary {{ background: #6c757d; color: white; }}
        .controls button.danger {{ background: #dc3545; color: white; }}
        .filter-controls {{
            margin-top: 10px;
        }}
        .filter-controls input {{
            padding: 6px 10px;
            margin-right: 10px;
            border: 1px solid #ccc;
            border-radius: 4px;
            width: 200px;
        }}
        .pagination {{
            background: #e9ecef;
            padding: 15px 20px;
            border-radius: 5px;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
            flex-wrap: wrap;
        }}
        .pagination button {{
            padding: 8px 14px;
            border: 1px solid #ccc;
            background: white;
            border-radius: 4px;
            cursor: pointer;
        }}
        .pagination button:hover {{ background: #f0f0f0; }}
        .pagination button.active {{
            background: #007bff;
            color: white;
            border-color: #007bff;
        }}
        .pagination button:disabled {{
            opacity: 0.5;
            cursor: not-allowed;
        }}
        .page-info {{
            font-weight: bold;
            margin: 0 10px;
        }}
        .flagged-list {{
            background: #f8d7da;
            border: 1px solid #f5c6cb;
            padding: 15px 20px;
            border-radius: 5px;
            margin-bottom: 20px;
            display: none;
        }}
        .flagged-list.visible {{ display: block; }}
        .flagged-list pre {{
            background: white;
            padding: 10px;
            border-radius: 4px;
            max-height: 200px;
            overflow-y: auto;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: 20px;
        }}
        .card {{
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            overflow: hidden;
            position: relative;
            border: 3px solid transparent;
        }}
        .card.flagged {{
            border-color: #dc3545;
            background: #fff5f5;
        }}
        .card.hidden {{
            display: none;
        }}
        .card img {{
            width: 100%;
            height: 220px;
            object-fit: contain;
            background: #eee;
            cursor: pointer;
        }}
        .card-content {{ padding: 12px; }}
        .card-id {{
            font-weight: bold;
            font-size: 16px;
            color: #0066cc;
            margin-bottom: 5px;
        }}
        .card-title {{
            font-size: 13px;
            color: #333;
            margin-bottom: 8px;
            line-height: 1.3;
        }}
        .card-meta {{
            font-size: 12px;
            color: #666;
            border-top: 1px solid #eee;
            padding-top: 8px;
        }}
        .card-meta strong {{ color: #333; }}
        .card-date {{
            background: #e9ecef;
            padding: 2px 8px;
            border-radius: 3px;
            font-weight: bold;
        }}
        .card-toggle {{
            position: absolute;
            top: 10px;
            right: 10px;
            padding: 6px 10px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-weight: bold;
            font-size: 11px;
        }}
        .card-toggle.ok {{
            background: #28a745;
            color: white;
        }}
        .card-toggle.flagged {{
            background: #dc3545;
            color: white;
        }}
        .lightbox {{
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.9);
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }}
        .lightbox.visible {{
            display: flex;
        }}
        .lightbox img {{
            max-width: 90%;
            max-height: 90%;
            object-fit: contain;
        }}
        .lightbox-close {{
            position: absolute;
            top: 20px;
            right: 30px;
            font-size: 40px;
            color: white;
            cursor: pointer;
        }}
    </style>
</head>
<body>
    <h1>Public Domain Files Review - Copyright Verification</h1>
    <div class="stats">
        <strong>Total public domain files:</strong> {total_images} ({total_pages} pages of {per_page})<br>
        <strong>Purpose:</strong> Review all images to verify they are indeed in the public domain (pre-1886 or otherwise copyright-free)
    </div>
    <div class="controls">
        <strong>Review status:</strong>
        <span id="ok-count">{total_images}</span> OK,
        <span id="flagged-count">0</span> flagged as NOT public domain
        &nbsp;|&nbsp;
        <button class="secondary" onclick="toggleFlaggedList()">Show/Hide Flagged</button>
        <button class="primary" onclick="exportFlagged()">Export Flagged IDs</button>
        <button class="secondary" onclick="showOnlyFlagged()">Show Only Flagged</button>
        <button class="secondary" onclick="showAll()">Show All</button>
        <div class="filter-controls">
            <input type="text" id="search-box" placeholder="Search by ID, title, date..." oninput="filterCards()">
            <button class="secondary" onclick="clearSearch()">Clear</button>
        </div>
    </div>
    <div class="pagination" id="pagination">
        <button onclick="goToPage(1)" id="btn-first">« First</button>
        <button onclick="goToPage(currentPage - 1)" id="btn-prev">‹ Prev</button>
        <span class="page-info">Page <span id="current-page">1</span> of <span id="total-pages">{total_pages}</span></span>
        <button onclick="goToPage(currentPage + 1)" id="btn-next">Next ›</button>
        <button onclick="goToPage({total_pages})" id="btn-last">Last »</button>
        <span style="margin-left: 20px;">Go to page:</span>
        <input type="number" id="page-input" min="1" max="{total_pages}" value="1" style="width: 60px; padding: 6px;">
        <button onclick="goToPage(parseInt(document.getElementById('page-input').value))">Go</button>
    </div>
    <div class="flagged-list" id="flagged-list">
        <strong>Flagged as NOT public domain (copy these IDs to update Excel):</strong>
        <pre id="flagged-ids"></pre>
    </div>
    <div class="grid" id="image-grid">
''')

    for i, (idx, row) in enumerate(df.iterrows()):
        page_num = (i // per_page) + 1  # Calculate which page this image belongs to
        unique_id = str(row.get('unique_id', ''))
        title = str(row.get('titel', '')).replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')
        datum = str(row.get('datum', ''))
        if pd.isna(row.get('datum')) or datum == 'nan':
            datum = '(geen datum)'
        vervaardiger = str(row.get('vervaardiger', ''))
        if pd.isna(row.get('vervaardiger')) or vervaardiger == 'nan':
            vervaardiger = '(onbekend)'
        vervaardiger = vervaardiger.replace('<', '&lt;').replace('>', '&gt;')

        img_src = str(row.get('image_url', ''))
        if not img_src or img_src == 'nan':
            img_src = ''

        # Truncate long titles
        display_title = title[:120] + "..." if len(title) > 120 else title

        html_parts.append(f'''        <div class="card" data-id="{unique_id}" data-title="{title.lower()}" data-date="{datum.lower()}" data-page="{page_num}">
            <button class="card-toggle ok" onclick="toggleFlag(this, '{unique_id}')">✓ OK</button>
            <img src="{img_src}" alt="{title}" loading="lazy" onclick="openLightbox(this.src)">
            <div class="card-content">
                <div class="card-id">{unique_id}</div>
                <div class="card-title">{display_title}</div>
                <div class="card-meta">
                    <strong>Date:</strong> <span class="card-date">{datum}</span><br>
                    <strong>Creator:</strong> {vervaardiger}
                </div>
            </div>
        </div>
''')

    html_parts.append(f'''    </div>

    <div class="pagination" id="pagination-bottom" style="margin-top: 20px;">
        <button onclick="goToPage(1)" id="btn-first-bottom">« First</button>
        <button onclick="goToPage(currentPage - 1)" id="btn-prev-bottom">‹ Prev</button>
        <span class="page-info">Page <span id="current-page-bottom">1</span> of <span id="total-pages-bottom">{total_pages}</span></span>
        <button onclick="goToPage(currentPage + 1)" id="btn-next-bottom">Next ›</button>
        <button onclick="goToPage({total_pages})" id="btn-last-bottom">Last »</button>
    </div>

    <div class="lightbox" id="lightbox" onclick="closeLightbox()">
        <span class="lightbox-close">&times;</span>
        <img id="lightbox-img" src="">
    </div>

    <script>
        const STORAGE_KEY = 'flagged_not_public_domain';
        const TOTAL_PAGES = {total_pages};
        const PER_PAGE = {per_page};
        let flaggedIds = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
        let currentPage = 1;
        let filterMode = 'pagination'; // 'pagination', 'flagged', or 'search'

        // Initialize on page load
        document.addEventListener('DOMContentLoaded', function() {{
            applyFlagsToUI();
            updateCounts();
            goToPage(1);
        }});

        function goToPage(page) {{
            if (page < 1 || page > TOTAL_PAGES) return;
            currentPage = page;
            filterMode = 'pagination';

            // Hide all cards first
            document.querySelectorAll('.card').forEach(card => {{
                card.classList.add('hidden');
            }});

            // Show only cards for current page
            document.querySelectorAll(`.card[data-page="${{page}}"]`).forEach(card => {{
                card.classList.remove('hidden');
            }});

            // Update page displays
            document.getElementById('current-page').textContent = page;
            document.getElementById('current-page-bottom').textContent = page;
            document.getElementById('page-input').value = page;

            // Update button states
            document.getElementById('btn-first').disabled = (page === 1);
            document.getElementById('btn-prev').disabled = (page === 1);
            document.getElementById('btn-next').disabled = (page === TOTAL_PAGES);
            document.getElementById('btn-last').disabled = (page === TOTAL_PAGES);
            document.getElementById('btn-first-bottom').disabled = (page === 1);
            document.getElementById('btn-prev-bottom').disabled = (page === 1);
            document.getElementById('btn-next-bottom').disabled = (page === TOTAL_PAGES);
            document.getElementById('btn-last-bottom').disabled = (page === TOTAL_PAGES);

            // Scroll to top
            window.scrollTo(0, 0);
        }}

        function toggleFlag(btn, id) {{
            const card = btn.closest('.card');
            const isFlagged = card.classList.contains('flagged');

            if (isFlagged) {{
                // Mark as OK
                card.classList.remove('flagged');
                btn.classList.remove('flagged');
                btn.classList.add('ok');
                btn.textContent = '✓ OK';
                flaggedIds = flaggedIds.filter(x => x !== id);
            }} else {{
                // Flag as NOT public domain
                card.classList.add('flagged');
                btn.classList.remove('ok');
                btn.classList.add('flagged');
                btn.textContent = '⚠ NOT PD';
                if (!flaggedIds.includes(id)) {{
                    flaggedIds.push(id);
                }}
            }}

            localStorage.setItem(STORAGE_KEY, JSON.stringify(flaggedIds));
            updateCounts();
        }}

        function updateCounts() {{
            const total = document.querySelectorAll('.card').length;
            const flagged = flaggedIds.length;
            document.getElementById('flagged-count').textContent = flagged;
            document.getElementById('ok-count').textContent = total - flagged;
            document.getElementById('flagged-ids').textContent = flaggedIds.join('\\n') || '(none)';
        }}

        function applyFlagsToUI() {{
            document.querySelectorAll('.card').forEach(card => {{
                const id = card.dataset.id;
                const btn = card.querySelector('.card-toggle');
                if (flaggedIds.includes(id)) {{
                    card.classList.add('flagged');
                    btn.classList.remove('ok');
                    btn.classList.add('flagged');
                    btn.textContent = '⚠ NOT PD';
                }}
            }});
        }}

        function toggleFlaggedList() {{
            document.getElementById('flagged-list').classList.toggle('visible');
        }}

        function exportFlagged() {{
            if (flaggedIds.length === 0) {{
                alert('No files flagged as NOT public domain.');
                return;
            }}
            const text = flaggedIds.join('\\n');
            const blob = new Blob([text], {{ type: 'text/plain' }});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'flagged_not_public_domain.txt';
            a.click();
            URL.revokeObjectURL(url);
        }}

        function showOnlyFlagged() {{
            filterMode = 'flagged';
            document.querySelectorAll('.card').forEach(card => {{
                if (flaggedIds.includes(card.dataset.id)) {{
                    card.classList.remove('hidden');
                }} else {{
                    card.classList.add('hidden');
                }}
            }});
        }}

        function showAll() {{
            filterMode = 'pagination';
            document.getElementById('search-box').value = '';
            goToPage(currentPage);
        }}

        function filterCards() {{
            const query = document.getElementById('search-box').value.toLowerCase();
            if (!query) {{
                goToPage(currentPage);
                return;
            }}
            filterMode = 'search';
            document.querySelectorAll('.card').forEach(card => {{
                const id = card.dataset.id.toLowerCase();
                const title = card.dataset.title;
                const date = card.dataset.date;
                if (id.includes(query) || title.includes(query) || date.includes(query)) {{
                    card.classList.remove('hidden');
                }} else {{
                    card.classList.add('hidden');
                }}
            }});
        }}

        function clearSearch() {{
            document.getElementById('search-box').value = '';
            showAll();
        }}

        function openLightbox(src) {{
            document.getElementById('lightbox-img').src = src;
            document.getElementById('lightbox').classList.add('visible');
        }}

        function closeLightbox() {{
            document.getElementById('lightbox').classList.remove('visible');
        }}

        // Keyboard navigation
        document.addEventListener('keydown', function(e) {{
            if (e.key === 'Escape') closeLightbox();
            if (filterMode === 'pagination') {{
                if (e.key === 'ArrowLeft' && currentPage > 1) goToPage(currentPage - 1);
                if (e.key === 'ArrowRight' && currentPage < TOTAL_PAGES) goToPage(currentPage + 1);
            }}
        }});
    </script>
</body>
</html>
''')

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(''.join(html_parts))

    print(f'Created: {output_file}')
    return len(df)


if __name__ == "__main__":
    # Read the public-domain-files sheet from the Excel file
    df = pd.read_excel(EXCEL_FILE, sheet_name='public-domain-files')

    # Categories to create previews for (output to previews/ folder)
    categories = [
        ('Dutch typography', 'previews/pd_preview_dutch_typography.html'),
        ('Printing in the Netherlands', 'previews/pd_preview_printing_netherlands.html'),
        ('Bookbinding in the Netherlands', 'previews/pd_preview_bookbinding_netherlands.html'),
        ('Libraries in the Netherlands', 'previews/pd_preview_libraries_netherlands.html'),
    ]

    # If command line argument provided, only create that one
    if len(sys.argv) > 1:
        cat_name = sys.argv[1]
        for name, filename in categories:
            if cat_name.lower() in name.lower():
                create_preview_html(df, name, filename)
                break
    else:
        # Create all previews (individual files)
        for name, filename in categories:
            create_preview_html(df, name, filename)

        # Also create combined preview with tabs
        create_combined_preview_html(df, 'previews/pd_preview_all.html')

        # Create public domain review page for copyright verification
        create_public_domain_review_html(df, 'previews/pd_review_all.html')