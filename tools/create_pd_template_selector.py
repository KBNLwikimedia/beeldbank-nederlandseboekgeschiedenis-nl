"""
Generate HTML page for assigning Wikimedia Commons PD templates to newly discovered public domain files.

Usage:
    python tools/create_pd_template_selector.py
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
DISCOVERED_FILE = 'tools/previews/newly_discovered_public_domain.json'
OUTPUT_FILE = 'tools/previews/pd_template_selector.html'
PROGRESS_FILE = 'tools/previews/pd_template_assignments.json'
ITEMS_PER_PAGE = 50

# Available PD templates with descriptions and Commons documentation links
PD_TEMPLATES = [
    {
        "id": "pd-old-70",
        "template": "{{PD-old-70-expired}}",
        "name": "PD-old-70-expired (Default)",
        "description": "Author died 70+ years ago. Standard template for known authors.",
        "url": "https://commons.wikimedia.org/wiki/Template:PD-old-70-expired",
        "for_unknown": False
    },
    {
        "id": "pd-anon-70-eu",
        "template": "{{PD-anon-70-EU}}",
        "name": "PD-anon-70-EU",
        "description": "Anonymous work published 70+ years ago in EU. Use when creator is unknown.",
        "url": "https://commons.wikimedia.org/wiki/Template:PD-anon-70-EU",
        "for_unknown": True
    },
    {
        "id": "pd-old-100",
        "template": "{{PD-old-100}}",
        "name": "PD-old-100",
        "description": "Work is over 100 years old. Safe choice for very old works.",
        "url": "https://commons.wikimedia.org/wiki/Template:PD-old-100",
        "for_unknown": False
    },
    {
        "id": "pd-us-1929",
        "template": "{{PD-US-1929}}",
        "name": "PD-US-1929",
        "description": "Published before 1929, public domain in US.",
        "url": "https://commons.wikimedia.org/wiki/Template:PD-US-1929",
        "for_unknown": False
    },
    {
        "id": "pd-old-auto-expired",
        "template": "{{PD-old-auto-expired|deathyear=}}",
        "name": "PD-old-auto-expired",
        "description": "Author's death year known. Fill in deathyear parameter.",
        "url": "https://commons.wikimedia.org/wiki/Template:PD-old-auto-expired",
        "for_unknown": False
    },
    {
        "id": "pd-1996",
        "template": "{{PD-1996}}",
        "name": "PD-1996",
        "description": "Work was in public domain in source country before 1996.",
        "url": "https://commons.wikimedia.org/wiki/Template:PD-1996",
        "for_unknown": False
    }
]

def is_unknown_creator(creator):
    """Check if creator is unknown/anonymous."""
    if not creator:
        return True
    creator_lower = creator.lower().strip()
    return creator_lower in ['(onbekend)', 'onbekend', '', 'anoniem', 'anonymous', 'unknown']

def generate_html():
    # Read the discovered files
    with open(DISCOVERED_FILE, 'r', encoding='utf-8') as f:
        discovered = json.load(f)

    items = discovered.get('items', [])
    total_items = len(items)
    total_pages = math.ceil(total_items / ITEMS_PER_PAGE)

    # Read Excel for additional metadata (image_url, detail_url, origineel)
    df = pd.read_excel(EXCEL_FILE, sheet_name='all')
    df_dict = df.set_index('unique_id').to_dict('index')

    # Enrich items with Excel data
    for item in items:
        unique_id = item['id']
        if unique_id in df_dict:
            row = df_dict[unique_id]
            item['image_url'] = row.get('image_url', '')
            item['detail_url'] = row.get('detail_url', '')
            item['origineel'] = row.get('origineel', '')
            item['titel'] = row.get('titel', '')
        item['is_unknown'] = is_unknown_creator(item.get('creator', ''))

    # Count unknown vs known creators
    unknown_count = sum(1 for item in items if item['is_unknown'])
    known_count = total_items - unknown_count

    # Build creator counts for sidebar
    creator_counts = {}
    for item in items:
        creator = item.get('creator', '') or '(onbekend)'
        if creator not in creator_counts:
            creator_counts[creator] = 0
        creator_counts[creator] += 1

    # Sort by count descending, then name
    creators_with_counts = sorted(creator_counts.items(), key=lambda x: (-x[1], x[0]))
    creators_json = json.dumps([c[0] for c in creators_with_counts], ensure_ascii=False)

    templates_json = json.dumps(PD_TEMPLATES, ensure_ascii=False)
    items_json = json.dumps(items, ensure_ascii=False)

    print(f"Generating template selector for {total_items} files ({total_pages} pages)")
    print(f"  - Unique creators: {len(creators_with_counts)}")
    print(f"  - Unknown creators: {unknown_count}")
    print(f"  - Known creators: {known_count}")

    html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PD Template Selector - Assign Copyright Templates</title>
    <style>
        * {{ box-sizing: border-box; }}
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
        .creator-list li.unknown {{
            background: #fff8e7;
        }}
        .creator-list li.unknown.active {{
            background: #007bff;
        }}
        .main-content {{
            margin-left: 280px;
            padding: 20px;
            flex: 1;
        }}
        h1 {{ color: #333; margin-bottom: 10px; }}
        .template-reference {{
            background: #f8f9fa;
            border: 1px solid #dee2e6;
            padding: 12px 15px;
            border-radius: 5px;
            margin-bottom: 15px;
        }}
        .template-reference strong {{
            margin-right: 10px;
        }}
        .template-list {{
            display: inline-flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-top: 8px;
        }}
        .template-link {{
            display: inline-block;
            background: #e9ecef;
            color: #495057;
            padding: 4px 10px;
            border-radius: 4px;
            text-decoration: none;
            font-family: monospace;
            font-size: 12px;
            border: 1px solid #ced4da;
        }}
        .template-link:hover {{
            background: #007bff;
            color: white;
            border-color: #007bff;
        }}
        .stats {{
            background: #e7f3ff;
            border: 1px solid #b3d7ff;
            padding: 15px 20px;
            border-radius: 5px;
            margin-bottom: 20px;
        }}
        .stats strong {{ color: #0066cc; }}
        .controls {{
            background: #fff;
            border: 1px solid #ddd;
            padding: 15px 20px;
            border-radius: 5px;
            margin-bottom: 20px;
            position: sticky;
            top: 0;
            z-index: 100;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
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
        .controls button.warning {{ background: #ffc107; color: black; }}
        .filter-row {{
            margin-top: 10px;
            display: flex;
            gap: 10px;
            align-items: center;
            flex-wrap: wrap;
        }}
        .filter-row select, .filter-row input {{
            padding: 6px 10px;
            border: 1px solid #ccc;
            border-radius: 4px;
        }}
        .filter-row input {{ width: 200px; }}
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
        .pagination button:disabled {{ opacity: 0.5; cursor: not-allowed; }}
        .page-info {{ font-weight: bold; }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
            gap: 20px;
        }}
        .card {{
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            overflow: hidden;
            border: 3px solid transparent;
        }}
        .card.assigned {{
            border-color: #28a745;
        }}
        .card.unknown {{
            background: #fff8e7;
        }}
        .card.hidden {{
            display: none;
        }}
        .card-header {{
            display: flex;
            gap: 15px;
            padding: 15px;
        }}
        .card-image {{
            width: 160px;
            height: 160px;
            object-fit: contain;
            background: #eee;
            border-radius: 4px;
            cursor: pointer;
        }}
        .card-info {{
            flex: 1;
            min-width: 0;
        }}
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
        }}
        .card-meta strong {{ color: #333; }}
        .unknown-badge {{
            display: inline-block;
            background: #ffc107;
            color: #000;
            padding: 2px 8px;
            border-radius: 3px;
            font-size: 11px;
            font-weight: bold;
            margin-left: 5px;
        }}
        .card-template {{
            padding: 15px;
            border-top: 1px solid #eee;
            background: #f9f9f9;
        }}
        .template-select {{
            width: 100%;
            padding: 8px;
            border: 1px solid #ccc;
            border-radius: 4px;
            font-size: 13px;
            margin-bottom: 8px;
        }}
        .template-desc {{
            font-size: 11px;
            color: #666;
            margin-bottom: 8px;
        }}
        .template-desc a {{
            color: #0066cc;
            text-decoration: none;
            margin-left: 5px;
        }}
        .template-desc a:hover {{
            text-decoration: underline;
        }}
        .template-preview {{
            font-family: monospace;
            font-size: 12px;
            background: #fff;
            padding: 8px;
            border-radius: 4px;
            border: 1px solid #ddd;
            word-break: break-all;
        }}
        .template-preview.has-value {{
            background: #d4edda;
            border-color: #c3e6cb;
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
        .progress-bar {{
            height: 20px;
            background: #e9ecef;
            border-radius: 10px;
            overflow: hidden;
            margin-top: 10px;
        }}
        .progress-bar-fill {{
            height: 100%;
            background: #28a745;
            transition: width 0.3s;
        }}
    </style>
</head>
<body>
    <div class="sidebar">
        <h3>Creators ({len(creators_with_counts)})</h3>
        <div class="sidebar-search">
            <input type="text" id="creator-search" placeholder="Search creators..." oninput="filterCreatorList()">
        </div>
        <ul class="creator-list" id="creator-list">
            <li onclick="selectCreator('')" class="active" data-creator="">
                <span>All creators</span>
                <span class="count">{total_items}</span>
            </li>
'''

    # Add creator list items
    for creator, count in creators_with_counts:
        creator_escaped = html.escape(creator)
        creator_js = creator.replace("'", "\\'").replace('"', '&quot;')
        creator_display = creator[:30] + '...' if len(creator) > 30 else creator
        is_unknown = is_unknown_creator(creator)
        unknown_class = ' unknown' if is_unknown else ''
        html_content += f'''            <li class="{unknown_class.strip()}" data-creator="{creator_escaped}" onclick="selectCreator('{creator_js}')">
                <span title="{creator_escaped}">{html.escape(creator_display)}</span>
                <span class="count">{count}</span>
            </li>
'''

    html_content += f'''        </ul>
    </div>
    <div class="main-content">
    <h1>PD Template Selector</h1>
    <p>Assign Wikimedia Commons public domain copyright templates to newly discovered files.</p>

    <div class="template-reference">
        <strong>Available templates:</strong>
        <div class="template-list">
'''

    # Add template links
    for tmpl in PD_TEMPLATES:
        html_content += f'''            <a href="{tmpl['url']}" target="_blank" class="template-link" title="{tmpl['description']}">{tmpl['template']}</a>
'''

    html_content += f'''        </div>
    </div>

    <div class="stats">
        <strong>Total files:</strong> {total_items} |
        <strong>Unknown creators:</strong> <span style="color:#dc3545">{unknown_count}</span> |
        <strong>Known creators:</strong> {known_count} |
        <strong>Assigned:</strong> <span id="assigned-count">0</span> / {total_items}
        <div class="progress-bar">
            <div class="progress-bar-fill" id="progress-bar" style="width: 0%"></div>
        </div>
    </div>

    <div class="controls">
        <button class="primary" onclick="saveAssignments()">Save Assignments</button>
        <button class="secondary" onclick="loadAssignments()">Load from File...</button>
        <button class="info" onclick="exportForUpload()">Export for Upload</button>
        <button class="warning" onclick="autoAssignUnknown()">Auto-assign Unknown (PD-anon-70-EU)</button>
        <button class="warning" onclick="autoAssignDefault()">Auto-assign Remaining (PD-old-70)</button>

        <div class="filter-row">
            <label>Filter:</label>
            <select id="filter-status" onchange="applyFilters()">
                <option value="all">All items</option>
                <option value="unassigned">Unassigned only</option>
                <option value="assigned">Assigned only</option>
                <option value="unknown">Unknown creators</option>
                <option value="known">Known creators</option>
            </select>
            <input type="text" id="search-box" placeholder="Search ID, title, creator..." oninput="applyFilters()">
            <button class="secondary" onclick="clearFilters()">Clear</button>
        </div>
    </div>

    <div class="pagination" id="pagination">
        <button onclick="goToPage(1)" id="btn-first">&laquo; First</button>
        <button onclick="goToPage(currentPage - 1)" id="btn-prev">&lsaquo; Prev</button>
        <span class="page-info">Page <span id="current-page">1</span> of <span id="total-pages">{total_pages}</span></span>
        <button onclick="goToPage(currentPage + 1)" id="btn-next">Next &rsaquo;</button>
        <button onclick="goToPage(parseInt(document.getElementById('total-pages').textContent))" id="btn-last">Last &raquo;</button>
    </div>

    <div class="grid" id="card-grid">
'''

    # Generate cards
    for idx, item in enumerate(items):
        page_num = (idx // ITEMS_PER_PAGE) + 1
        unique_id = item['id']
        creator = item.get('creator', '') or '(onbekend)'
        date = item.get('date', '')
        titel_raw = item.get('titel', '') or ''
        if pd.isna(titel_raw): titel_raw = ''
        titel = str(titel_raw)[:80] + ('...' if len(str(titel_raw)) > 80 else '')
        image_url = item.get('image_url', '') or ''
        if pd.isna(image_url): image_url = ''
        detail_url = item.get('detail_url', '') or ''
        if pd.isna(detail_url): detail_url = ''
        origineel_raw = item.get('origineel', '') or ''
        if pd.isna(origineel_raw): origineel_raw = ''
        origineel = str(origineel_raw)[:100] + ('...' if len(str(origineel_raw)) > 100 else '')
        is_unknown = item.get('is_unknown', False)

        # Escape for HTML
        creator_escaped = html.escape(creator)
        titel_escaped = html.escape(titel)
        origineel_escaped = html.escape(origineel)
        detail_url_escaped = html.escape(detail_url) if detail_url else ''

        hidden_class = '' if page_num == 1 else ' hidden'
        unknown_class = ' unknown' if is_unknown else ''
        unknown_badge = '<span class="unknown-badge">UNKNOWN</span>' if is_unknown else ''

        # Build template options
        template_options = '<option value="">-- Select template --</option>'
        for tmpl in PD_TEMPLATES:
            selected = ''
            template_options += f'<option value="{tmpl["id"]}">{tmpl["name"]}</option>'

        html_content += f'''        <div class="card{hidden_class}{unknown_class}" data-id="{unique_id}" data-page="{page_num}" data-unknown="{str(is_unknown).lower()}" data-creator="{creator_escaped}" data-title="{html.escape(item.get('titel', '').lower())}">
            <div class="card-header">
                <img class="card-image" src="{image_url}" alt="{titel_escaped}" loading="lazy" onclick="openLightbox(this.src)">
                <div class="card-info">
                    <div class="card-id">
                        <a href="{detail_url_escaped}" target="_blank">{unique_id} &#8599;</a>
                        {unknown_badge}
                    </div>
                    <div class="card-title">{titel_escaped}</div>
                    <div class="card-meta">
                        <strong>Date:</strong> {html.escape(date)}<br>
                        <strong>Creator:</strong> {creator_escaped}
                    </div>
                </div>
            </div>
            <div class="card-template">
                <select class="template-select" onchange="updateTemplate(this, '{unique_id}')">
                    {template_options}
                </select>
                <div class="template-desc" id="desc-{unique_id}">Select a template above</div>
                <div class="template-preview" id="preview-{unique_id}">No template selected</div>
            </div>
        </div>
'''

    html_content += f'''    </div>

    <div class="lightbox" id="lightbox" onclick="closeLightbox()">
        <span class="lightbox-close">&times;</span>
        <img id="lightbox-img" src="" alt="Full size image">
    </div>

    <script>
        const ITEMS_PER_PAGE = {ITEMS_PER_PAGE};
        const TOTAL_ITEMS = {total_items};
        const TEMPLATES = {templates_json};
        const PROGRESS_FILE = 'pd_template_assignments.json';

        let currentPage = 1;
        let assignments = {{}};  // id -> {{templateId, template}}
        let fileHandle = null;
        let filteredCards = [];

        // Initialize
        (async function init() {{
            await autoLoadAssignments();
            updateProgress();
            applyFilters();
        }})();

        async function autoLoadAssignments() {{
            try {{
                const response = await fetch(PROGRESS_FILE);
                if (response.ok) {{
                    const data = await response.json();
                    if (data.assignments) {{
                        assignments = data.assignments;
                        applyAssignmentsToUI();
                        console.log(`Loaded ${{Object.keys(assignments).length}} assignments`);
                    }}
                }}
            }} catch (err) {{
                console.log('No saved assignments found');
            }}
        }}

        function applyAssignmentsToUI() {{
            for (const [id, assignment] of Object.entries(assignments)) {{
                const card = document.querySelector(`.card[data-id="${{id}}"]`);
                if (card) {{
                    const select = card.querySelector('.template-select');
                    select.value = assignment.templateId;
                    updateTemplateDisplay(card, assignment.templateId);
                    card.classList.add('assigned');
                }}
            }}
        }}

        function updateTemplate(select, id) {{
            const templateId = select.value;
            const card = select.closest('.card');

            if (templateId) {{
                const template = TEMPLATES.find(t => t.id === templateId);
                assignments[id] = {{
                    templateId: templateId,
                    template: template.template
                }};
                card.classList.add('assigned');
            }} else {{
                delete assignments[id];
                card.classList.remove('assigned');
            }}

            updateTemplateDisplay(card, templateId);
            updateProgress();
        }}

        function updateTemplateDisplay(card, templateId) {{
            const id = card.dataset.id;
            const descEl = document.getElementById(`desc-${{id}}`);
            const previewEl = document.getElementById(`preview-${{id}}`);

            if (templateId) {{
                const template = TEMPLATES.find(t => t.id === templateId);
                descEl.innerHTML = template.description + ` <a href="${{template.url}}" target="_blank" title="View template documentation">&#8599; docs</a>`;
                previewEl.textContent = template.template;
                previewEl.classList.add('has-value');
            }} else {{
                descEl.textContent = 'Select a template above';
                previewEl.textContent = 'No template selected';
                previewEl.classList.remove('has-value');
            }}
        }}

        function updateProgress() {{
            const count = Object.keys(assignments).length;
            document.getElementById('assigned-count').textContent = count;
            const pct = (count / TOTAL_ITEMS * 100).toFixed(1);
            document.getElementById('progress-bar').style.width = pct + '%';
        }}

        async function saveAssignments() {{
            const data = {{
                description: "PD template assignments for newly discovered public domain files",
                saved_at: new Date().toISOString(),
                total_items: TOTAL_ITEMS,
                assigned_count: Object.keys(assignments).length,
                assignments: assignments
            }};
            const json = JSON.stringify(data, null, 2);

            try {{
                if ('showSaveFilePicker' in window) {{
                    if (!fileHandle) {{
                        fileHandle = await window.showSaveFilePicker({{
                            suggestedName: PROGRESS_FILE,
                            types: [{{ description: 'JSON files', accept: {{ 'application/json': ['.json'] }} }}]
                        }});
                    }}
                    const writable = await fileHandle.createWritable();
                    await writable.write(json);
                    await writable.close();
                    showNotification(`Saved ${{Object.keys(assignments).length}} assignments`);
                }} else {{
                    const blob = new Blob([json], {{ type: 'application/json' }});
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = PROGRESS_FILE;
                    a.click();
                    URL.revokeObjectURL(url);
                }}
            }} catch (err) {{
                if (err.name !== 'AbortError') {{
                    alert('Error saving: ' + err.message);
                }}
            }}
        }}

        async function loadAssignments() {{
            try {{
                let file;
                if ('showOpenFilePicker' in window) {{
                    const [handle] = await window.showOpenFilePicker({{
                        types: [{{ description: 'JSON files', accept: {{ 'application/json': ['.json'] }} }}]
                    }});
                    file = await handle.getFile();
                    fileHandle = handle;
                }} else {{
                    const input = document.createElement('input');
                    input.type = 'file';
                    input.accept = '.json';
                    await new Promise(resolve => {{ input.onchange = resolve; input.click(); }});
                    file = input.files[0];
                }}
                if (!file) return;

                const text = await file.text();
                const data = JSON.parse(text);
                if (data.assignments) {{
                    assignments = data.assignments;
                    // Reset all cards
                    document.querySelectorAll('.card').forEach(card => {{
                        card.classList.remove('assigned');
                        const select = card.querySelector('.template-select');
                        select.value = '';
                        updateTemplateDisplay(card, '');
                    }});
                    applyAssignmentsToUI();
                    updateProgress();
                    alert(`Loaded ${{Object.keys(assignments).length}} assignments`);
                }}
            }} catch (err) {{
                if (err.name !== 'AbortError') {{
                    alert('Error loading: ' + err.message);
                }}
            }}
        }}

        function exportForUpload() {{
            const count = Object.keys(assignments).length;
            if (count === 0) {{
                alert('No assignments to export');
                return;
            }}

            const items = Object.entries(assignments).map(([id, a]) => ({{
                id: id,
                template: a.template
            }}));
            items.sort((a, b) => {{
                const numA = parseInt(a.id.replace('BBB-', ''));
                const numB = parseInt(b.id.replace('BBB-', ''));
                return numA - numB;
            }});

            const data = {{
                description: "PD templates for upload to Wikimedia Commons",
                exported_at: new Date().toISOString(),
                count: items.length,
                items: items
            }};

            const json = JSON.stringify(data, null, 2);
            const blob = new Blob([json], {{ type: 'application/json' }});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'pd_templates_for_upload.json';
            a.click();
            URL.revokeObjectURL(url);
        }}

        function autoAssignUnknown() {{
            const unknownCards = document.querySelectorAll('.card[data-unknown="true"]');
            let count = 0;
            unknownCards.forEach(card => {{
                const id = card.dataset.id;
                if (!assignments[id]) {{
                    const select = card.querySelector('.template-select');
                    select.value = 'pd-anon-70-eu';
                    updateTemplate(select, id);
                    count++;
                }}
            }});
            showNotification(`Auto-assigned ${{count}} unknown creators to PD-anon-70-EU`);
        }}

        function autoAssignDefault() {{
            const cards = document.querySelectorAll('.card');
            let count = 0;
            cards.forEach(card => {{
                const id = card.dataset.id;
                if (!assignments[id]) {{
                    const select = card.querySelector('.template-select');
                    select.value = 'pd-old-70';
                    updateTemplate(select, id);
                    count++;
                }}
            }});
            showNotification(`Auto-assigned ${{count}} items to PD-old-70`);
        }}

        function showNotification(message) {{
            const notification = document.createElement('div');
            notification.textContent = message;
            notification.style.cssText = 'position:fixed;bottom:20px;right:20px;background:#28a745;color:white;padding:12px 20px;border-radius:5px;z-index:9999;font-weight:bold;box-shadow:0 2px 10px rgba(0,0,0,0.2);';
            document.body.appendChild(notification);
            setTimeout(() => notification.remove(), 3000);
        }}

        function getFilteredCards() {{
            const allCards = Array.from(document.querySelectorAll('.card'));
            const filter = document.getElementById('filter-status').value;
            const search = document.getElementById('search-box').value.toLowerCase();

            return allCards.filter(card => {{
                const id = card.dataset.id;
                const isUnknown = card.dataset.unknown === 'true';
                const isAssigned = assignments[id] !== undefined;
                const creator = card.dataset.creator;
                const creatorLower = creator.toLowerCase();
                const title = card.dataset.title;

                // Creator sidebar filter
                if (selectedCreator && creator !== selectedCreator) return false;

                // Status filter
                if (filter === 'unassigned' && isAssigned) return false;
                if (filter === 'assigned' && !isAssigned) return false;
                if (filter === 'unknown' && !isUnknown) return false;
                if (filter === 'known' && isUnknown) return false;

                // Search filter
                if (search) {{
                    if (!id.toLowerCase().includes(search) &&
                        !creatorLower.includes(search) &&
                        !title.includes(search)) {{
                        return false;
                    }}
                }}

                return true;
            }});
        }}

        function applyFilters() {{
            filteredCards = getFilteredCards();
            const totalPages = Math.max(1, Math.ceil(filteredCards.length / ITEMS_PER_PAGE));
            document.getElementById('total-pages').textContent = totalPages;

            if (currentPage > totalPages) currentPage = totalPages;
            goToPage(currentPage);
        }}

        function goToPage(page) {{
            const totalPages = parseInt(document.getElementById('total-pages').textContent);
            if (page < 1) page = 1;
            if (page > totalPages) page = totalPages;
            currentPage = page;

            // Hide all
            document.querySelectorAll('.card').forEach(card => card.classList.add('hidden'));

            // Show filtered cards for this page
            const start = (page - 1) * ITEMS_PER_PAGE;
            const end = start + ITEMS_PER_PAGE;
            filteredCards.slice(start, end).forEach(card => card.classList.remove('hidden'));

            // Update UI
            document.getElementById('current-page').textContent = page;
            document.getElementById('btn-first').disabled = (page === 1);
            document.getElementById('btn-prev').disabled = (page === 1);
            document.getElementById('btn-next').disabled = (page === totalPages);
            document.getElementById('btn-last').disabled = (page === totalPages);

            window.scrollTo(0, 0);
        }}

        function clearFilters() {{
            document.getElementById('filter-status').value = 'all';
            document.getElementById('search-box').value = '';
            document.getElementById('creator-search').value = '';
            selectedCreator = '';
            // Reset sidebar selection
            document.querySelectorAll('.creator-list li').forEach(li => li.classList.remove('active'));
            document.querySelector('.creator-list li[data-creator=""]').classList.add('active');
            filterCreatorList();
            applyFilters();
        }}

        function openLightbox(src) {{
            document.getElementById('lightbox-img').src = src;
            document.getElementById('lightbox').classList.add('visible');
        }}

        function closeLightbox() {{
            document.getElementById('lightbox').classList.remove('visible');
        }}

        document.addEventListener('keydown', function(e) {{
            if (e.key === 'Escape') closeLightbox();
            const totalPages = parseInt(document.getElementById('total-pages').textContent);
            if (e.key === 'ArrowLeft' && currentPage > 1) goToPage(currentPage - 1);
            if (e.key === 'ArrowRight' && currentPage < totalPages) goToPage(currentPage + 1);
        }});

        // Creator sidebar functions
        let selectedCreator = '';

        function filterCreatorList() {{
            const query = document.getElementById('creator-search').value.toLowerCase();
            document.querySelectorAll('.creator-list li').forEach(li => {{
                const creator = (li.dataset.creator || '').toLowerCase();
                if (creator === '' || creator.includes(query)) {{
                    li.style.display = '';
                }} else {{
                    li.style.display = 'none';
                }}
            }});
        }}

        function selectCreator(creator) {{
            selectedCreator = creator;
            // Update active state in sidebar
            document.querySelectorAll('.creator-list li').forEach(li => {{
                li.classList.remove('active');
                if (li.dataset.creator === creator) {{
                    li.classList.add('active');
                }}
            }});
            // Reset to first page and apply filters
            currentPage = 1;
            applyFilters();
        }}
    </script>
    </div>
</body>
</html>'''

    # Write HTML file
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"Generated: {OUTPUT_FILE}")

    # Create initial progress file if it doesn't exist
    try:
        with open(PROGRESS_FILE, 'r') as f:
            pass
    except FileNotFoundError:
        initial_data = {
            "description": "PD template assignments for newly discovered public domain files",
            "saved_at": None,
            "total_items": total_items,
            "assigned_count": 0,
            "assignments": {}
        }
        with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
            json.dump(initial_data, f, indent=2)
        print(f"Created: {PROGRESS_FILE}")

if __name__ == '__main__':
    generate_html()
