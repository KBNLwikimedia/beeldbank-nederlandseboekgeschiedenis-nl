"""
Generate HTML preview page for reviewing non-public-domain images.
Users can mark images that ARE actually in the public domain.

Usage:
    python tools/create_non_pd_review.py
"""
import os
import sys

# Ensure we're working from project root
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
os.chdir(project_root)
sys.path.insert(0, project_root)

import pandas as pd
import html
import json
import math

# Configuration
EXCEL_FILE = 'nbg-beeldbank_all_24012026.xlsx'
OUTPUT_FILE = 'tools/previews/non_pd_review.html'
ITEMS_PER_PAGE = 100

def generate_html():
    # Read the Excel file
    df = pd.read_excel(EXCEL_FILE, sheet_name='all')

    # Filter for non-public-domain files only
    non_pd = df[df['in_public_domain_files'] != True].copy()
    non_pd = non_pd.sort_values('unique_id', key=lambda x: x.str.extract(r'(\d+)')[0].astype(int))

    total_items = len(non_pd)
    total_pages = math.ceil(total_items / ITEMS_PER_PAGE)

    # Extract unique creators with counts for the sidebar
    creator_counts = non_pd['vervaardiger'].value_counts().to_dict()
    # Count empty/NaN creators
    empty_creator_count = non_pd['vervaardiger'].isna().sum()

    creators_with_counts = [(c, creator_counts.get(c, 0)) for c in creator_counts.keys()
                           if c and str(c).strip() and pd.notna(c)]
    # Add (onbekend) for empty creators if any exist
    if empty_creator_count > 0:
        creators_with_counts.append(('(onbekend)', empty_creator_count))
    creators_with_counts = sorted(creators_with_counts, key=lambda x: (-x[1], x[0]))  # Sort by count desc, then name
    creators_json = json.dumps([c[0] for c in creators_with_counts], ensure_ascii=False)

    print(f"Generating review page for {total_items} non-public-domain files ({total_pages} pages)")
    print(f"Found {len(creators_with_counts)} unique creators")

    # Generate HTML
    html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Non-Public Domain Review - Find Hidden Public Domain Files</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 0;
            background-color: #f5f5f5;
            display: flex;
        }}
        .sidebar {{
            width: 280px;
            min-width: 280px;
            height: 100vh;
            overflow-y: auto;
            background: #fff;
            border-right: 1px solid #ddd;
            position: fixed;
            left: 0;
            top: 0;
        }}
        .sidebar h3 {{
            margin: 0;
            padding: 15px;
            background: #343a40;
            color: white;
            font-size: 14px;
            position: sticky;
            top: 0;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .sidebar h3 button {{
            background: #6c757d;
            color: white;
            border: none;
            padding: 4px 8px;
            border-radius: 3px;
            font-size: 10px;
            cursor: pointer;
        }}
        .sidebar h3 button:hover {{
            background: #5a6268;
        }}
        .sidebar-search {{
            padding: 10px;
            border-bottom: 1px solid #ddd;
            position: sticky;
            top: 45px;
            background: #fff;
        }}
        .sidebar-search input {{
            width: 100%;
            padding: 8px;
            border: 1px solid #ccc;
            border-radius: 4px;
            box-sizing: border-box;
        }}
        .creator-list {{
            list-style: none;
            margin: 0;
            padding: 0;
        }}
        .creator-list li {{
            padding: 8px 15px;
            border-bottom: 1px solid #eee;
            cursor: pointer;
            font-size: 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .creator-list li:hover {{
            background: #f0f0f0;
        }}
        .creator-list li.active {{
            background: #007bff;
            color: white;
        }}
        .creator-list li .count {{
            background: #6c757d;
            color: white;
            padding: 2px 6px;
            border-radius: 10px;
            font-size: 10px;
        }}
        .creator-list li.active .count {{
            background: white;
            color: #007bff;
        }}
        .creator-list li.removed {{
            display: none !important;
        }}
        .creator-list li .remove-btn {{
            display: none;
            background: #dc3545;
            color: white;
            border: none;
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 10px;
            cursor: pointer;
            margin-left: 5px;
        }}
        .creator-list li:hover .remove-btn {{
            display: inline;
        }}
        .creator-list li.active .remove-btn {{
            display: inline;
        }}
        .main-content {{
            margin-left: 280px;
            padding: 20px;
            flex: 1;
        }}
        h1 {{ color: #333; }}
        .stats {{
            background: #fff3cd;
            border: 1px solid #ffc107;
            padding: 15px 20px;
            border-radius: 5px;
            margin-bottom: 20px;
        }}
        .controls {{
            background: #d4edda;
            border: 1px solid #c3e6cb;
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
        .controls button.primary {{ background: #28a745; color: white; }}
        .controls button.secondary {{ background: #6c757d; color: white; }}
        .controls button.info {{ background: #17a2b8; color: white; }}
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
        .bulk-actions {{
            margin-top: 10px;
            padding-top: 10px;
            border-top: 1px solid #c3e6cb;
        }}
        .bulk-actions button {{
            padding: 8px 16px;
            margin-right: 10px;
            cursor: pointer;
            border: none;
            border-radius: 4px;
        }}
        .bulk-actions button.success {{ background: #28a745; color: white; }}
        .bulk-actions button.warning {{ background: #ffc107; color: black; }}
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
        .marked-list {{
            background: #d4edda;
            border: 1px solid #c3e6cb;
            padding: 15px 20px;
            border-radius: 5px;
            margin-bottom: 20px;
            display: none;
        }}
        .marked-list.visible {{ display: block; }}
        .marked-list pre {{
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
        .card.marked {{
            border-color: #28a745;
            background: #f0fff0;
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
            margin-bottom: 5px;
        }}
        .card-id a {{
            color: #0066cc;
            text-decoration: none;
        }}
        .card-id a:hover {{
            text-decoration: underline;
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
        .card-toggle.not-pd {{
            background: #6c757d;
            color: white;
        }}
        .card-toggle.is-pd {{
            background: #28a745;
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
    <div class="sidebar">
        <h3>
            <span>Creators (<span id="visible-creators-count">{len(creators_with_counts)}</span>)</span>
            <button onclick="toggleRemovedCreators()" id="toggle-removed-btn" title="Show/hide removed creators">Show removed</button>
        </h3>
        <div class="sidebar-search">
            <input type="text" id="creator-search" placeholder="Search creators..." oninput="filterCreatorList()">
        </div>
        <ul class="creator-list" id="creator-list">
            <li onclick="clearCreatorFilter()" class="active" data-creator="">
                <span>All creators</span>
                <span class="count">{total_items}</span>
            </li>
'''

    # Add creator list items
    for creator, count in creators_with_counts:
        creator_escaped = html.escape(creator)
        creator_js = creator.replace("'", "\\'").replace('"', '&quot;')
        creator_display = creator[:35] + '...' if len(creator) > 35 else creator
        html_content += f'''            <li data-creator="{creator_escaped}">
                <span onclick="selectCreator(this.parentElement, '{creator_js}')" title="{creator_escaped}" style="flex:1;cursor:pointer">{html.escape(creator_display)}</span>
                <span class="count">{count}</span>
                <button class="remove-btn" onclick="event.stopPropagation(); removeCreator(this.parentElement, '{creator_js}')" title="Remove from list">&times;</button>
            </li>
'''

    html_content += f'''        </ul>
    </div>
    <div class="main-content">
    <h1>Non-Public Domain Review - Find Hidden Public Domain Files</h1>
    <div class="stats">
        <strong>Total non-public-domain files:</strong> {total_items} ({total_pages} pages of {ITEMS_PER_PAGE})<br>
        <strong>Purpose:</strong> Review images currently marked as NOT public domain to identify any that ARE actually in the public domain (pre-1886, anonymous works, etc.)
    </div>
    <div class="controls">
        <strong>Review status:</strong>
        <span id="not-pd-count">{total_items}</span> NOT public domain,
        <span id="marked-count">0</span> marked as IS public domain
        &nbsp;|&nbsp;
        <button class="secondary" onclick="toggleMarkedList()">Show/Hide Marked</button>
        <button class="primary" onclick="saveState()">Save Progress</button>
        <button class="secondary" onclick="loadState()">Load from File...</button>
        <button class="info" onclick="exportMarked()">Export PD IDs for Upload</button>
        <button class="info" onclick="showOnlyMarked()">Show Only Marked</button>
        <button class="secondary" onclick="showAll()">Show All Remaining</button>
        <div class="filter-controls">
            <input type="text" id="search-box" placeholder="Search by ID, title, date..." oninput="filterCards()">
            <button class="secondary" onclick="clearFilters()">Clear Filters</button>
        </div>
        <div class="bulk-actions">
            <strong>Bulk actions:</strong>
            <button class="success" onclick="markAllVisibleAsPD()">Mark ALL visible as IS PD</button>
            <button class="warning" onclick="unmarkAllVisibleAsPD()">Unmark ALL visible</button>
            <span id="visible-count" style="margin-left: 10px;">(showing all)</span>
        </div>
    </div>
    <div class="pagination" id="pagination">
        <button onclick="goToPage(1)" id="btn-first">&laquo; First</button>
        <button onclick="goToPage(currentPage - 1)" id="btn-prev">&lsaquo; Prev</button>
        <span class="page-info">Page <span id="current-page">1</span> of <span id="total-pages">{total_pages}</span></span>
        <button onclick="goToPage(currentPage + 1)" id="btn-next">Next &rsaquo;</button>
        <button onclick="goToPage(parseInt(document.getElementById('total-pages').textContent))" id="btn-last">Last &raquo;</button>
        <span style="margin-left: 20px;">Go to page:</span>
        <input type="number" id="page-input" min="1" max="{total_pages}" value="1" style="width: 60px; padding: 6px;">
        <button onclick="goToPage(parseInt(document.getElementById('page-input').value))">Go</button>
    </div>
    <div class="marked-list" id="marked-list">
        <strong>Marked as IS public domain (these will be uploaded to Commons):</strong>
        <pre id="marked-ids"></pre>
    </div>
    <div class="grid" id="image-grid">
'''

    # Generate cards for each image
    for idx, (_, row) in enumerate(non_pd.iterrows()):
        page_num = (idx // ITEMS_PER_PAGE) + 1
        unique_id = row['unique_id']
        titel = row['titel'] if pd.notna(row['titel']) else '(geen titel)'
        datum = row['datum'] if pd.notna(row['datum']) else '(onbekend)'
        vervaardiger = row['vervaardiger'] if pd.notna(row['vervaardiger']) else '(onbekend)'
        origineel = row['origineel'] if pd.notna(row['origineel']) else ''
        image_url = row['image_url'] if pd.notna(row['image_url']) else ''
        detail_url = row['detail_url'] if pd.notna(row['detail_url']) else ''

        # Escape HTML characters
        titel_escaped = html.escape(titel)
        titel_lower = titel.lower().replace('"', '&quot;')
        datum_escaped = html.escape(str(datum))
        datum_lower = str(datum).lower()
        vervaardiger_escaped = html.escape(str(vervaardiger))
        origineel_escaped = html.escape(str(origineel))
        detail_url_escaped = html.escape(detail_url)

        hidden_class = '' if page_num == 1 else ' hidden'
        creator_escaped = html.escape(str(vervaardiger))

        # Only show origineel line if it has content
        origineel_html = f'<br><strong>Origineel:</strong> {origineel_escaped}' if origineel else ''

        html_content += f'''        <div class="card{hidden_class}" data-id="{unique_id}" data-title="{titel_lower}" data-date="{datum_lower}" data-creator="{creator_escaped}" data-page="{page_num}">
            <button class="card-toggle not-pd" onclick="toggleMark(this, '{unique_id}')">NOT PD</button>
            <img src="{image_url}" alt="{titel_escaped}" loading="lazy" onclick="openLightbox(this.src)">
            <div class="card-content">
                <div class="card-id"><a href="{detail_url_escaped}" target="_blank" title="View on nederlandseboekgeschiedenis.nl">{unique_id} &#8599;</a></div>
                <div class="card-title">{titel_escaped}</div>
                <div class="card-meta">
                    <strong>Date:</strong> <span class="card-date">{datum_escaped}</span><br>
                    <strong>Creator:</strong> {vervaardiger_escaped}{origineel_html}
                </div>
            </div>
        </div>
'''

    # Close grid and add bottom pagination
    html_content += f'''    </div>
    <div class="pagination" style="margin-top: 20px;">
        <button onclick="goToPage(1)" id="btn-first-bottom">&laquo; First</button>
        <button onclick="goToPage(currentPage - 1)" id="btn-prev-bottom">&lsaquo; Prev</button>
        <span class="page-info">Page <span id="current-page-bottom">1</span> of <span id="total-pages-bottom">{total_pages}</span></span>
        <button onclick="goToPage(currentPage + 1)" id="btn-next-bottom">Next &rsaquo;</button>
        <button onclick="goToPage(parseInt(document.getElementById('total-pages').textContent))" id="btn-last-bottom">Last &raquo;</button>
    </div>
    <div class="lightbox" id="lightbox" onclick="closeLightbox()">
        <span class="lightbox-close">&times;</span>
        <img id="lightbox-img" src="" alt="Full size image">
    </div>
    <script>
        const ITEMS_PER_PAGE = {ITEMS_PER_PAGE};
        const CREATORS = {creators_json};
        const PROGRESS_FILE = 'non_pd_review_progress.json';
        let currentPage = 1;
        let markedItems = [];  // Array of {{id, creator, date}} objects
        let removedCreators = [];
        let filterMode = 'pagination';
        let showingRemoved = false;
        let fileHandle = null;  // File System Access API handle
        let filteredCards = [];  // Cards in current filter mode

        // Helper to get just the IDs for backward compatibility
        function getMarkedIds() {{
            return markedItems.map(item => typeof item === 'string' ? item : item.id);
        }}

        // Get cards based on current filter mode
        function getFilteredCards() {{
            const allCards = Array.from(document.querySelectorAll('.card'));
            const markedIds = getMarkedIds();

            if (filterMode === 'marked') {{
                // Show only marked items (including from removed creators)
                return allCards.filter(card => markedIds.includes(card.dataset.id));
            }} else {{
                // Show remaining (exclude removed creators and marked items)
                return allCards.filter(card => {{
                    const creator = card.dataset.creator;
                    const id = card.dataset.id;
                    return !removedCreators.includes(creator) && !markedIds.includes(id);
                }});
            }}
        }}

        function updatePagination() {{
            filteredCards = getFilteredCards();
            const totalPages = Math.max(1, Math.ceil(filteredCards.length / ITEMS_PER_PAGE));

            // Update total pages display
            document.getElementById('total-pages').textContent = totalPages;
            document.getElementById('total-pages-bottom').textContent = totalPages;

            // Ensure current page is valid
            if (currentPage > totalPages) {{
                currentPage = totalPages;
            }}

            // Update button states
            document.getElementById('btn-first').disabled = (currentPage === 1);
            document.getElementById('btn-prev').disabled = (currentPage === 1);
            document.getElementById('btn-next').disabled = (currentPage === totalPages);
            document.getElementById('btn-last').disabled = (currentPage === totalPages);
            document.getElementById('btn-first-bottom').disabled = (currentPage === 1);
            document.getElementById('btn-prev-bottom').disabled = (currentPage === 1);
            document.getElementById('btn-next-bottom').disabled = (currentPage === totalPages);
            document.getElementById('btn-last-bottom').disabled = (currentPage === totalPages);

            // Update page input max
            document.getElementById('page-input').max = totalPages;

            return totalPages;
        }}

        // Initialize - auto-load progress
        (async function init() {{
            await autoLoadProgress();
            filterMode = 'remaining';
            updateCounts();
            goToPage(1);
        }})();

        async function autoLoadProgress() {{
            try {{
                const response = await fetch(PROGRESS_FILE);
                if (response.ok) {{
                    const data = await response.json();
                    if (data.marked_as_public_domain && data.marked_as_public_domain.items) {{
                        // New format with creator info
                        markedItems = data.marked_as_public_domain.items;
                    }} else if (data.marked_as_public_domain && data.marked_as_public_domain.ids) {{
                        // Old format - convert to new format
                        markedItems = data.marked_as_public_domain.ids.map(id => ({{ id, creator: '', date: '' }}));
                    }}
                    if (data.removed_creators && data.removed_creators.creators) {{
                        removedCreators = data.removed_creators.creators;
                    }}
                    applyMarksToUI();
                    applyRemovedCreators();
                    if (markedItems.length > 0 || removedCreators.length > 0) {{
                        console.log(`Auto-loaded: ${{markedItems.length}} marked, ${{removedCreators.length}} removed creators`);
                    }}
                }}
            }} catch (err) {{
                console.log('No saved progress found or error loading:', err.message);
            }}
        }}

        function filterCreatorList() {{
            const query = document.getElementById('creator-search').value.toLowerCase();
            document.querySelectorAll('.creator-list li').forEach(li => {{
                const creator = li.dataset.creator.toLowerCase();
                if (creator === '' || creator.includes(query)) {{
                    li.style.display = '';
                }} else {{
                    li.style.display = 'none';
                }}
            }});
        }}

        function selectCreator(element, creator) {{
            // Update active state in sidebar
            document.querySelectorAll('.creator-list li').forEach(li => li.classList.remove('active'));
            element.classList.add('active');

            // Filter cards by creator
            filterByCreator(creator);
        }}

        function clearCreatorFilter() {{
            document.querySelectorAll('.creator-list li').forEach(li => li.classList.remove('active'));
            document.querySelector('.creator-list li[data-creator=""]').classList.add('active');
            document.getElementById('creator-search').value = '';
            filterCreatorList();
            showAll();
        }}

        function removeCreator(element, creator) {{
            if (!confirm(`Remove "${{creator.substring(0, 50)}}..." from the list?\\n\\nThis creator will be hidden (not in public domain).`)) {{
                return;
            }}
            if (!removedCreators.includes(creator)) {{
                removedCreators.push(creator);
            }}
            element.classList.add('removed');
            updateCreatorCount();
            // Go back to all view if we were viewing this creator
            if (element.classList.contains('active')) {{
                clearCreatorFilter();
            }}
        }}

        function toggleRemovedCreators() {{
            showingRemoved = !showingRemoved;
            const btn = document.getElementById('toggle-removed-btn');
            if (showingRemoved) {{
                btn.textContent = 'Hide removed';
                btn.style.background = '#dc3545';
                document.querySelectorAll('.creator-list li.removed').forEach(li => {{
                    li.style.display = '';
                    li.style.opacity = '0.5';
                    li.style.textDecoration = 'line-through';
                }});
            }} else {{
                btn.textContent = 'Show removed';
                btn.style.background = '#6c757d';
                document.querySelectorAll('.creator-list li.removed').forEach(li => {{
                    li.style.display = 'none';
                    li.style.opacity = '';
                    li.style.textDecoration = '';
                }});
            }}
        }}

        function restoreCreator(element, creator) {{
            removedCreators = removedCreators.filter(c => c !== creator);
            element.classList.remove('removed');
            element.style.opacity = '';
            element.style.textDecoration = '';
            updateCreatorCount();
        }}

        function applyRemovedCreators() {{
            document.querySelectorAll('.creator-list li[data-creator]').forEach(li => {{
                const creator = li.dataset.creator;
                if (creator && removedCreators.includes(creator)) {{
                    li.classList.add('removed');
                }}
            }});
            updateCreatorCount();
        }}

        function updateCreatorCount() {{
            const total = document.querySelectorAll('.creator-list li[data-creator]:not([data-creator=""])').length;
            const removed = removedCreators.length;
            document.getElementById('visible-creators-count').textContent = `${{total - removed}}/${{total}}`;
        }}

        async function saveState() {{
            // Sort items by ID number
            const sortedItems = [...markedItems].sort((a, b) => {{
                const numA = parseInt((a.id || a).toString().replace('BBB-', ''));
                const numB = parseInt((b.id || b).toString().replace('BBB-', ''));
                return numA - numB;
            }});

            const data = {{
                description: "Non-PD review progress - marked as public domain and removed creators",
                saved_at: new Date().toISOString(),
                marked_as_public_domain: {{
                    count: markedItems.length,
                    items: sortedItems
                }},
                removed_creators: {{
                    count: removedCreators.length,
                    creators: removedCreators.sort()
                }}
            }};
            const json = JSON.stringify(data, null, 2);

            try {{
                // Use File System Access API if available
                if ('showSaveFilePicker' in window) {{
                    // If we don't have a file handle yet, ask user to pick location
                    if (!fileHandle) {{
                        fileHandle = await window.showSaveFilePicker({{
                            suggestedName: PROGRESS_FILE,
                            types: [{{
                                description: 'JSON files',
                                accept: {{ 'application/json': ['.json'] }}
                            }}]
                        }});
                    }}
                    // Write to the file
                    const writable = await fileHandle.createWritable();
                    await writable.write(json);
                    await writable.close();
                    console.log(`Saved: ${{markedItems.length}} marked, ${{removedCreators.length}} removed`);
                    showSaveNotification();
                }} else {{
                    // Fallback: download file
                    const blob = new Blob([json], {{ type: 'application/json' }});
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = PROGRESS_FILE;
                    a.click();
                    URL.revokeObjectURL(url);
                    alert(`Saved progress:\\n- ${{markedItems.length}} images marked as public domain\\n- ${{removedCreators.length}} creators removed`);
                }}
            }} catch (err) {{
                if (err.name !== 'AbortError') {{
                    console.error('Save error:', err);
                    alert('Error saving: ' + err.message);
                }}
            }}
        }}

        function showSaveNotification() {{
            // Show a brief non-blocking notification
            const notification = document.createElement('div');
            notification.textContent = `Saved: ${{markedItems.length}} marked, ${{removedCreators.length}} removed`;
            notification.style.cssText = 'position:fixed;bottom:20px;right:20px;background:#28a745;color:white;padding:12px 20px;border-radius:5px;z-index:9999;font-weight:bold;box-shadow:0 2px 10px rgba(0,0,0,0.2);';
            document.body.appendChild(notification);
            setTimeout(() => notification.remove(), 2000);
        }}

        async function loadState() {{
            try {{
                let file;
                // Use File System Access API if available
                if ('showOpenFilePicker' in window) {{
                    const [handle] = await window.showOpenFilePicker({{
                        types: [{{
                            description: 'JSON files',
                            accept: {{ 'application/json': ['.json'] }}
                        }}]
                    }});
                    file = await handle.getFile();
                    // Store handle for future saves
                    fileHandle = handle;
                }} else {{
                    // Fallback: use file input
                    const input = document.createElement('input');
                    input.type = 'file';
                    input.accept = '.json';
                    await new Promise((resolve) => {{
                        input.onchange = () => resolve();
                        input.click();
                    }});
                    file = input.files[0];
                }}

                if (!file) return;

                const text = await file.text();
                const data = JSON.parse(text);

                // Load marked items (new format with creator) or IDs (old format)
                if (data.marked_as_public_domain && data.marked_as_public_domain.items) {{
                    markedItems = data.marked_as_public_domain.items;
                }} else if (data.marked_as_public_domain && data.marked_as_public_domain.ids) {{
                    markedItems = data.marked_as_public_domain.ids.map(id => ({{ id, creator: '', date: '' }}));
                }}

                // Load removed creators
                if (data.removed_creators && data.removed_creators.creators) {{
                    removedCreators = data.removed_creators.creators;
                }}

                // Apply to UI - Reset all cards first
                document.querySelectorAll('.card').forEach(card => {{
                    card.classList.remove('marked');
                    const btn = card.querySelector('.card-toggle');
                    btn.classList.remove('is-pd');
                    btn.classList.add('not-pd');
                    btn.textContent = 'NOT PD';
                }});
                // Reset all creators
                document.querySelectorAll('.creator-list li').forEach(li => {{
                    li.classList.remove('removed');
                    li.style.opacity = '';
                    li.style.textDecoration = '';
                }});

                applyMarksToUI();
                applyRemovedCreators();
                updateCounts();

                alert(`Loaded progress:\\n- ${{markedItems.length}} images marked as public domain\\n- ${{removedCreators.length}} creators removed`);
            }} catch (err) {{
                if (err.name !== 'AbortError') {{
                    alert('Error loading file: ' + err.message);
                }}
            }}
        }}

        function goToPage(page) {{
            const totalPages = updatePagination();
            if (page < 1) page = 1;
            if (page > totalPages) page = totalPages;
            currentPage = page;

            // Hide all cards first
            document.querySelectorAll('.card').forEach(card => {{
                card.classList.add('hidden');
            }});

            // Show cards for current page from filtered list
            const startIdx = (page - 1) * ITEMS_PER_PAGE;
            const endIdx = startIdx + ITEMS_PER_PAGE;
            const pageCards = filteredCards.slice(startIdx, endIdx);

            pageCards.forEach(card => {{
                card.classList.remove('hidden');
            }});

            // Update page displays
            document.getElementById('current-page').textContent = page;
            document.getElementById('current-page-bottom').textContent = page;
            document.getElementById('page-input').value = page;

            // Scroll to top
            window.scrollTo(0, 0);

            // Update visible count
            updateVisibleCount(pageCards.length);
        }}

        function toggleMark(btn, id) {{
            const card = btn.closest('.card');
            const isMarked = card.classList.contains('marked');

            if (isMarked) {{
                // Mark as NOT public domain (default)
                card.classList.remove('marked');
                btn.classList.remove('is-pd');
                btn.classList.add('not-pd');
                btn.textContent = 'NOT PD';
                markedItems = markedItems.filter(item => (item.id || item) !== id);
            }} else {{
                // Mark as IS public domain - store id, creator, and date
                card.classList.add('marked');
                btn.classList.remove('not-pd');
                btn.classList.add('is-pd');
                btn.textContent = '\\u2713 IS PD';
                const creator = card.dataset.creator || '';
                const date = card.dataset.date || '';
                if (!getMarkedIds().includes(id)) {{
                    markedItems.push({{ id, creator, date }});
                }}
            }}

            updateCounts();
        }}

        function updateCounts() {{
            const total = document.querySelectorAll('.card').length;
            const marked = markedItems.length;
            const markedIds = getMarkedIds();
            // Count remaining (excluding removed creators AND marked items)
            let remaining = 0;
            let removedByCreator = 0;
            document.querySelectorAll('.card').forEach(card => {{
                const creator = card.dataset.creator;
                const id = card.dataset.id;
                if (removedCreators.includes(creator)) {{
                    removedByCreator++;
                }} else if (!markedIds.includes(id)) {{
                    remaining++;
                }}
            }});
            document.getElementById('marked-count').textContent = marked;
            document.getElementById('not-pd-count').textContent = `${{remaining}} to review (${{removedByCreator}} removed, ${{marked}} marked)`;
            // Show items with creator info
            const markedText = markedItems.length > 0
                ? markedItems.map(item => `${{item.id}} | ${{item.date}} | ${{item.creator || '(unknown)'}}`).join('\\n')
                : '(none)';
            document.getElementById('marked-ids').textContent = markedText;
        }}

        function applyMarksToUI() {{
            const markedIds = getMarkedIds();
            document.querySelectorAll('.card').forEach(card => {{
                const id = card.dataset.id;
                const btn = card.querySelector('.card-toggle');
                if (markedIds.includes(id)) {{
                    card.classList.add('marked');
                    btn.classList.remove('not-pd');
                    btn.classList.add('is-pd');
                    btn.textContent = '\\u2713 IS PD';
                }}
            }});
        }}

        function toggleMarkedList() {{
            document.getElementById('marked-list').classList.toggle('visible');
        }}

        function exportMarked() {{
            if (markedItems.length === 0) {{
                alert('No files marked as public domain yet.');
                return;
            }}
            // Sort items by ID number
            const sortedItems = [...markedItems].sort((a, b) => {{
                const numA = parseInt((a.id || a).toString().replace('BBB-', ''));
                const numB = parseInt((b.id || b).toString().replace('BBB-', ''));
                return numA - numB;
            }});
            const data = {{
                description: "Newly discovered public domain files from non-PD review",
                exported_at: new Date().toISOString(),
                count: markedItems.length,
                items: sortedItems
            }};
            const json = JSON.stringify(data, null, 2);
            const blob = new Blob([json], {{ type: 'application/json' }});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'newly_discovered_public_domain.json';
            a.click();
            URL.revokeObjectURL(url);
        }}

        function showOnlyMarked() {{
            filterMode = 'marked';
            document.getElementById('search-box').value = '';
            // Reset sidebar selection
            document.querySelectorAll('.creator-list li').forEach(li => li.classList.remove('active'));
            document.querySelector('.creator-list li[data-creator=""]').classList.add('active');
            currentPage = 1;
            goToPage(1);
        }}

        function showAll() {{
            filterMode = 'remaining';
            document.getElementById('search-box').value = '';
            currentPage = 1;
            goToPage(1);
        }}

        function filterCards() {{
            const query = document.getElementById('search-box').value.toLowerCase();
            // Reset sidebar selection when searching
            document.querySelectorAll('.creator-list li').forEach(li => li.classList.remove('active'));
            document.querySelector('.creator-list li[data-creator=""]').classList.add('active');

            if (!query) {{
                goToPage(currentPage);
                return;
            }}
            filterMode = 'search';
            const markedIds = getMarkedIds();
            let visibleCount = 0;
            document.querySelectorAll('.card').forEach(card => {{
                const id = card.dataset.id;
                const idLower = id.toLowerCase();
                const title = card.dataset.title;
                const date = card.dataset.date;
                const creator = card.dataset.creator;
                const creatorLower = creator.toLowerCase();
                // Exclude removed creators and already marked items from search results
                if (removedCreators.includes(creator) || markedIds.includes(id)) {{
                    card.classList.add('hidden');
                }} else if (idLower.includes(query) || title.includes(query) || date.includes(query) || creatorLower.includes(query)) {{
                    card.classList.remove('hidden');
                    visibleCount++;
                }} else {{
                    card.classList.add('hidden');
                }}
            }});
            updateVisibleCount(visibleCount);
        }}

        function clearFilters() {{
            document.getElementById('search-box').value = '';
            clearCreatorFilter();
        }}

        function filterByCreator(creator) {{
            document.getElementById('search-box').value = '';

            if (!creator) {{
                showAll();
                return;
            }}

            filterMode = 'creator';
            const markedIds = getMarkedIds();
            let visibleCount = 0;
            document.querySelectorAll('.card').forEach(card => {{
                const id = card.dataset.id;
                // Show only cards matching creator, excluding already marked items
                if (card.dataset.creator === creator && !markedIds.includes(id)) {{
                    card.classList.remove('hidden');
                    visibleCount++;
                }} else {{
                    card.classList.add('hidden');
                }}
            }});
            updateVisibleCount(visibleCount);
        }}

        function markAllVisibleAsPD() {{
            const visibleCards = document.querySelectorAll('.card:not(.hidden)');
            if (visibleCards.length === 0) {{
                alert('No visible images to mark.');
                return;
            }}

            if (!confirm(`Mark ${{visibleCards.length}} visible images as IS public domain?`)) {{
                return;
            }}

            const markedIds = getMarkedIds();
            visibleCards.forEach(card => {{
                const id = card.dataset.id;
                const btn = card.querySelector('.card-toggle');

                if (!card.classList.contains('marked')) {{
                    card.classList.add('marked');
                    btn.classList.remove('not-pd');
                    btn.classList.add('is-pd');
                    btn.textContent = '\\u2713 IS PD';
                    if (!markedIds.includes(id)) {{
                        const creator = card.dataset.creator || '';
                        const date = card.dataset.date || '';
                        markedItems.push({{ id, creator, date }});
                    }}
                }}
            }});

            updateCounts();
        }}

        function unmarkAllVisibleAsPD() {{
            const visibleCards = document.querySelectorAll('.card:not(.hidden)');
            if (visibleCards.length === 0) {{
                alert('No visible images to unmark.');
                return;
            }}

            if (!confirm(`Unmark ${{visibleCards.length}} visible images (set to NOT public domain)?`)) {{
                return;
            }}

            visibleCards.forEach(card => {{
                const id = card.dataset.id;
                const btn = card.querySelector('.card-toggle');

                if (card.classList.contains('marked')) {{
                    card.classList.remove('marked');
                    btn.classList.remove('is-pd');
                    btn.classList.add('not-pd');
                    btn.textContent = 'NOT PD';
                    markedItems = markedItems.filter(item => (item.id || item) !== id);
                }}
            }});

            updateCounts();
        }}

        function updateVisibleCount(count) {{
            if (count !== undefined) {{
                document.getElementById('visible-count').textContent = `(showing ${{count}} images)`;
            }} else {{
                const visible = document.querySelectorAll('.card:not(.hidden)').length;
                document.getElementById('visible-count').textContent = `(showing ${{visible}} images)`;
            }}
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
            const totalPages = parseInt(document.getElementById('total-pages').textContent);
            if (e.key === 'ArrowLeft' && currentPage > 1) goToPage(currentPage - 1);
            if (e.key === 'ArrowRight' && currentPage < totalPages) goToPage(currentPage + 1);
        }});
    </script>
    </div>
</body>
</html>'''

    # Write the HTML file
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"Generated: {OUTPUT_FILE}")
    print(f"To use: python -m http.server 8000")
    print(f"Then open: http://localhost:8000/tools/previews/non_pd_review.html")

if __name__ == '__main__':
    generate_html()
