<img src="../media-assets/Logo_koninklijke_bibliotheek.svg" alt="KB Logo" width="250" align="right">

# Preview and Review Pages

These HTML pages allow you to review images before uploading to Wikimedia Commons.

## Copyright Verification

Use the **public domain review page** to visually verify all 803 images are truly in the public domain:

- **[Public Domain Review](http://localhost:8000/previews/pd_review_all.html)** - Review ALL public domain files (9 pages of 100 images)

### Features

- **Pagination**: Browse 100 images per page (use arrow keys ← → to navigate)
- **Image details**: View ID, title, date, and creator for each image
- **Lightbox**: Click any image to view full-size
- **Flag images**: Click "✓ OK" to flag an image as NOT public domain (turns red "⚠ NOT PD")
- **Search/filter**: Search by ID, title, or date across all pages
- **Show Only Flagged**: View only flagged images for quick review
- **Export**: Download flagged IDs as text file for updating the Excel

### How to use

1. Start local server: `python -m http.server 8000`
2. Open: http://localhost:8000/previews/pd_review_all.html
3. Navigate pages using buttons or arrow keys (← →)
4. Click "✓ OK" on any image that is NOT in the public domain
5. Use "Export Flagged IDs" to download the list
6. Update the Excel file to remove flagged images from public domain sheet

Selections are saved in localStorage and persist between sessions.

## Category Selection

These pages allow you to select which images should receive specific Commons categories:

**Important: Use Chrome or Edge.** Firefox does not support the File System Access API required for saving selections directly to the JSON file.

## How to Use

### 1. Start a Local Web Server

The preview pages need to load `category_exclusions.json` from the project folder. Due to browser security restrictions, you need to serve the files via a local web server.

Open a terminal in the project root folder and run:

```bash
python -m http.server 8000
```

### 2. Open Preview Pages

With the server running, open the preview pages in your browser:

- **[All categories (combined)](http://localhost:8000/previews/pd_preview_all.html)** - Tabbed interface with all 4 categories
- [Dutch typography](http://localhost:8000/previews/pd_preview_dutch_typography.html)
- [Printing in the Netherlands](http://localhost:8000/previews/pd_preview_printing_netherlands.html)
- [Bookbinding in the Netherlands](http://localhost:8000/previews/pd_preview_bookbinding_netherlands.html)
- [Libraries in the Netherlands](http://localhost:8000/previews/pd_preview_libraries_netherlands.html)

### 3. Select Images

- **Green button (✓ Include)**: Image will receive this category
- **Red button (✗ Excluded)**: Image will NOT receive this category
- Click a button to toggle between include/exclude

### 4. Save Selection

Click the **"Save Selection"** button to save your choices to `category_exclusions.json`.

- **Chrome/Edge**: Uses File System Access API - first time you'll be asked to select the file location, then it saves directly
- **Other browsers**: Downloads the file - save it to the project root folder (overwrite the existing file)

### 5. Upload

Run `uploader.py` - it automatically reads `category_exclusions.json` and filters out excluded categories for each image.

```bash
python uploader.py --preview BBB-123  # Preview with filtered categories
python uploader.py BBB-123            # Upload with filtered categories
```

## Files

| File | Description |
|------|-------------|
| `pd_review_all.html` | **Copyright verification - review ALL 803 public domain files** |
| `pd_preview_all.html` | Combined preview with all 4 categories in tabs |
| `pd_preview_dutch_typography.html` | Preview for Dutch typography category |
| `pd_preview_printing_netherlands.html` | Preview for Printing in the Netherlands category |
| `pd_preview_bookbinding_netherlands.html` | Preview for Bookbinding in the Netherlands category |
| `pd_preview_libraries_netherlands.html` | Preview for Libraries in the Netherlands category |
| `../category_exclusions.json` | Stores excluded image IDs per category (in project root) |
| `non_pd_review.html` | **Find hidden public domain files** - review non-PD images |
| `non_pd_review_progress.json` | Stores marked items and removed creators |
| `newly_discovered_public_domain.json` | Exported list of newly discovered PD files |
| `pd_template_selector.html` | **Assign PD templates** to newly discovered files |
| `pd_template_assignments.json` | Stores template assignments |

---

## Non-Public Domain Review

Use this page to find images that may have been incorrectly classified as non-public-domain:

- **[Non-PD Review](http://localhost:8000/previews/non_pd_review.html)** - Review 829 non-public-domain files

### Purpose

Some images may be in the public domain even if they appear to be recent:
- **Anonymous/unknown creators**: No known death date means copyright cannot be calculated
- **Pre-1886 works**: Always public domain regardless of creator
- **Institutional works**: May have different copyright rules

### Features

| Feature | Description |
|---------|-------------|
| **Creator sidebar** | Filter by creator (including "(onbekend)"), remove entire creators from review |
| **Dynamic pagination** | Pagination updates based on current filter (remaining items, marked items, or creator filter) |
| **View modes** | "Show All Remaining" (excludes marked + removed), "Show Only Marked" |
| **Search** | Filter by ID, title, date, or creator |
| **Toggle cards** | Click "NOT PD" → "✓ IS PD" to mark as public domain |
| **Bulk actions** | Mark/unmark all visible images at once |
| **Auto-save/load** | Progress saved to `non_pd_review_progress.json` |
| **Source links** | Click ID to view original on nederlandseboekgeschiedenis.nl |
| **Card details** | Shows ID, title, date, creator, and origineel (source reference) |

### View Modes

| Mode | Shows | Excludes |
|------|-------|----------|
| **Show All Remaining** | Items still to review | Removed creators + already marked items |
| **Show Only Marked** | Items marked as PD | Everything else (including removed creators' items if marked) |
| **Creator filter** | Items by selected creator | Other creators + already marked items |

### Data Stored

When you mark an image as public domain, the following is saved:

```json
{
  "marked_as_public_domain": {
    "items": [
      { "id": "BBB-1268", "creator": "anoniem/anonymous", "date": "1920" }
    ]
  },
  "removed_creators": {
    "creators": ["Photographer Name (fotograaf/photographer)"]
  }
}
```

The **creator** and **date** fields are stored because:
- Unknown/anonymous creators may qualify for alternative PD license templates on Commons
- Works with unknown creators can still be public domain (no death date to calculate)
- The date helps determine which PD template to use

### How to Use

1. **Generate the page**: `python create_non_pd_review.py`
2. **Start local server**: `python -m http.server 8000`
3. **Open**: http://localhost:8000/previews/non_pd_review.html
4. **Review images**:
   - Use creator sidebar to focus on specific creators
   - Click "NOT PD" button to mark images that ARE public domain
   - Remove entire creators (click ✗) if all their work is clearly not PD
   - Use "Show All Remaining" to see only unprocessed items
5. **Save progress**: Click "Save Progress" (first time: select `non_pd_review_progress.json`)
6. **Export for upload**: Click "Export PD IDs for Upload" → downloads `newly_discovered_public_domain.json`
7. **Assign templates**: Use the PD Template Selector (see below)
8. **Upload**: `python upload_new_pd_files.py newly_discovered_public_domain.json`

### Browser Requirements

**Use Chrome or Edge** - Firefox does not support the File System Access API for direct file saving.

Progress auto-loads from `non_pd_review_progress.json` when you open the page.

---

## PD Template Selector

After discovering new public domain files, use this page to assign the correct Wikimedia Commons copyright template to each file:

- **[PD Template Selector](http://localhost:8000/previews/pd_template_selector.html)** - Assign templates to newly discovered files

### Purpose

Different public domain works require different license templates on Wikimedia Commons:
- **Known creators**: Use `{{PD-old-70}}` if author died 70+ years ago
- **Unknown/anonymous creators**: Use `{{PD-anon-70-EU}}` for anonymous EU works
- **Very old works**: Use `{{PD-old-100}}` for works over 100 years old

### Available Templates

| Template | Use for | Documentation |
|----------|---------|---------------|
| `{{PD-US-expired\|PD-old-70}}` | Default - known authors who died 70+ years ago | [docs](https://commons.wikimedia.org/wiki/Template:PD-old-70) |
| `{{PD-anon-70-EU}}` | **Unknown creators** - anonymous works 70+ years old | [docs](https://commons.wikimedia.org/wiki/Template:PD-anon-70-EU) |
| `{{PD-old-100}}` | Very old works (100+ years) | [docs](https://commons.wikimedia.org/wiki/Template:PD-old-100) |
| `{{PD-US-1929}}` | Published before 1929 | [docs](https://commons.wikimedia.org/wiki/Template:PD-US-1929) |
| `{{PD-old-auto-expired\|deathyear=}}` | When death year is known | [docs](https://commons.wikimedia.org/wiki/Template:PD-old-auto-expired) |
| `{{PD-1996}}` | PD in source country before 1996 | [docs](https://commons.wikimedia.org/wiki/Template:PD-1996) |

### Features

| Feature | Description |
|---------|-------------|
| **Progress bar** | Shows how many templates assigned |
| **Auto-assign buttons** | One-click assign all unknown → PD-anon-70-EU |
| **Filter/Search** | By status (assigned/unassigned), creator type, or text |
| **Template dropdown** | Select template for each image with description |
| **Documentation links** | Each template has a link to Commons documentation |
| **Auto-save/load** | Progress saved to `pd_template_assignments.json` |
| **Export** | Download assignments for upload script |

### How to Use

1. **Generate the page**: `python create_pd_template_selector.py`
2. **Start local server**: `python -m http.server 8000`
3. **Open**: http://localhost:8000/previews/pd_template_selector.html
4. **Quick assignment**:
   - Click **"Auto-assign Unknown (PD-anon-70-EU)"** for all unknown creators
   - Click **"Auto-assign Remaining (PD-old-70)"** for remaining items
5. **Review and adjust**: Check individual items and change templates as needed
6. **Save**: Click "Save Assignments" (first time: select `pd_template_assignments.json`)
7. **Export**: Click "Export for Upload" to download `pd_templates_for_upload.json`
