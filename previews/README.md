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
