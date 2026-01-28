# Category Preview Pages

These HTML pages allow you to review and select which images should receive specific Commons categories before uploading.

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
| `pd_preview_all.html` | **Combined preview with all 4 categories in tabs** |
| `pd_preview_dutch_typography.html` | Preview for Dutch typography category |
| `pd_preview_printing_netherlands.html` | Preview for Printing in the Netherlands category |
| `pd_preview_bookbinding_netherlands.html` | Preview for Bookbinding in the Netherlands category |
| `pd_preview_libraries_netherlands.html` | Preview for Libraries in the Netherlands category |
| `../category_exclusions.json` | Stores excluded image IDs per category (in project root) |
