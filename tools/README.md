<img src="../media-assets/Logo_koninklijke_bibliotheek.svg" alt="KB Logo" width="250" align="right">

# Tools

This folder contains utility scripts for reviewing, previewing, and processing images before and after uploading to Wikimedia Commons.

## Scripts

| Script | Purpose |
|--------|---------|
| `create_preview.py` | Generate HTML pages for category selection preview |
| `create_non_pd_review.py` | Generate HTML page to find hidden public domain files |
| `create_pd_template_selector.py` | Generate HTML page to assign license templates |
| `verify_structured_data.py` | Check which files have structured data on Commons |
| `add_missing_structured_data.py` | Add missing labels/statements to Commons files |
| `upload_new_pd_files.py` | Upload newly discovered public domain files |

## Usage

All scripts should be run from the **project root folder**:

```bash
# Generate review/preview pages
python tools/create_non_pd_review.py
python tools/create_pd_template_selector.py
python tools/create_preview.py

# Verify and fix structured data
python tools/verify_structured_data.py
python tools/add_missing_structured_data.py

# Upload newly discovered files
python tools/upload_new_pd_files.py --dry-run      # Preview without uploading
python tools/upload_new_pd_files.py                # Upload all files
python tools/upload_new_pd_files.py --start 50     # Resume from 50th file
python tools/upload_new_pd_files.py --limit 10     # Upload only 10 files
python tools/upload_new_pd_files.py --delay 10     # 10s delay between uploads
```

## Preview Pages

The `previews/` subfolder contains generated HTML pages for reviewing images:

```bash
# Start web server from project root
python -m http.server 8000

# Then open in browser (Chrome/Edge recommended):
# http://localhost:8000/tools/previews/
```

See [`previews/README.md`](previews/README.md) for detailed documentation on each preview page.

### Main Pages

| Page | Purpose |
|------|---------|
| [pd_review_all.html](http://localhost:8000/tools/previews/pd_review_all.html) | Verify public domain status of 803 files |
| [non_pd_review.html](http://localhost:8000/tools/previews/non_pd_review.html) | Find hidden PD files among 829 non-PD items |
| [pd_template_selector.html](http://localhost:8000/tools/previews/pd_template_selector.html) | Assign license templates to newly discovered files |
| [pd_preview_all.html](http://localhost:8000/tools/previews/pd_preview_all.html) | Select Commons categories for files |

## Workflow

```
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────┐
│  1. Non-PD Review   │ --> │ 2. PD Template      │ --> │ 3. Upload       │
│  (find hidden PD)   │     │    Selector         │     │    to Commons   │
└─────────────────────┘     └─────────────────────┘     └─────────────────┘
         ↓                           ↓                          ↓
 newly_discovered_           pd_templates_              Files uploaded
 public_domain.json          for_upload.json            with templates
```

### upload_new_pd_files.py

Uploads newly discovered public domain files using the license templates from the template selector.

**Input files:**
- `tools/previews/pd_templates_for_upload.json` - Template assignments (id + template)

**Features:**
- Uses custom license templates (PD-old-70-expired, PD-anon-70-EU, PD-anon-expired, PD-Art)
- Adds structured data automatically after each upload
- Updates both Excel sheets ('all' and 'public-domain-files')
- Saves progress every 10 uploads to avoid data loss
- Supports resuming from any position with `--start`

## Browser Requirements

**Use Chrome or Edge** for preview pages. Firefox does not support the File System Access API required for saving selections directly to JSON files.
