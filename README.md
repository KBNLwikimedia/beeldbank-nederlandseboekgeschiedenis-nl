[![GitHub](https://img.shields.io/badge/GitHub-KBNLwikimedia-blue?logo=github)](https://github.com/KBNLwikimedia/beeldbank-nederlandseboekgeschiedenis-nl)
[![Python](https://img.shields.io/badge/Python-3.8+-green?logo=python)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-Public%20Domain-brightgreen)](https://creativecommons.org/publicdomain/zero/1.0/)
[![Wikimedia Commons](https://img.shields.io/badge/Wikimedia-Commons-006699?logo=wikimedia-commons)](https://commons.wikimedia.org/wiki/Category:Beeldbank_Nederlandse_Boekgeschiedenis)

# Beeldbank Nederlandse Boekgeschiedenis - Wikimedia Commons Upload Project

Upload pipeline for the **Beeldbank (Image Bank) of Nederlandse Boekgeschiedenis (Dutch Book History)**, hosted by the KB (Koninklijke Bibliotheek / Royal Library of the Netherlands).

## Project Scope

This project harvests metadata and images from the **1,635 digitized historical book-related items** in the Beeldbank Nederlandse Boekgeschiedenis and uploads them to Wikimedia Commons with proper metadata, structured data, and categorization.

### Copyright Status

This project targets only images that are **in the public domain** - works that are out of copyright both in the Netherlands/EU and in the USA. The collection primarily contains historical book-related materials (manuscripts, prints, illustrations) from before the 20th century, ensuring they are no longer protected by copyright in any major jurisdiction.

### Goals
- Scrape all metadata and image URLs from the Beeldbank
- Download high-resolution images locally
- Upload images to Wikimedia Commons using the `{{Artwork}}` template
- Add structured data (Wikibase statements) to each file
- Properly categorize files based on classification

### Target Website
- **Search interface**: https://www.nederlandseboekgeschiedenis.nl/nl/beeldbank
- **Image resolver**: `http://resolver.kb.nl/resolve?urn=urn:BBB:{urn}`
- **Commons category**: [Category:Beeldbank Nederlandse Boekgeschiedenis](https://commons.wikimedia.org/wiki/Category:Beeldbank_Nederlandse_Boekgeschiedenis)

## Technical Approach

### Pipeline Overview

```
┌─────────────┐    ┌──────────────────┐    ┌─────────────┐    ┌─────────────────┐
│  scraper.py │ -> │ download_images.py│ -> │ uploader.py │ -> │structured_data.py│
│  (metadata) │    │    (images)       │    │  (upload)   │    │  (statements)   │
└─────────────┘    └──────────────────┘    └─────────────┘    └─────────────────┘
       ↓                   ↓                      ↓                    ↓
   Excel file         images/folder         Commons files      Structured data
```

### Step-by-Step Process

1. **Scrape metadata** (`scraper.py`) - Extract metadata from Beeldbank search results
2. **Download images** (`download_images.py`) - Download full-resolution images from KB resolver
3. **Prepare filenames** - Clean and standardize filenames for Commons (manual step in Excel)
4. **Map categories** - Map Dutch classifications to Commons categories
5. **Upload to Commons** (`uploader.py`) - Upload images with `{{Artwork}}` template
6. **Add structured data** (`structured_data.py`) - Add Wikibase statements to each file

## Scripts

### scraper.py
Scrapes metadata from the Beeldbank search interface using Playwright (browser automation required due to JavaScript/AJAX content).

```bash
python scraper.py
```

### download_images.py
Downloads high-resolution images from the KB resolver service.

```bash
python download_images.py
```

### commons_template.py
Defines the mapping between Excel columns and the `{{Artwork}}` template fields. Generates wikitext for file description pages.

**Key functions:**
- `generate_wikitext(row)` - Generate complete wikitext for a record
- `get_upload_filename(row)` - Get the Commons filename
- `format_bilingual_type(type_str)` - Format type as `{{nl|...}} {{en|...}}`

### uploader.py
Uploads images to Wikimedia Commons with proper metadata.

```bash
# Preview upload
python uploader.py --preview BBB-1

# Upload single file
python uploader.py BBB-1

# Batch upload (rows 0-10)
python uploader.py --batch 0 10
```

### structured_data.py
Adds structured data (Wikibase statements) to Commons files.

```bash
# Add Dutch description only
python structured_data.py BBB-1

# Add statements only
python structured_data.py --statements BBB-1

# Add both description and statements
python structured_data.py --all BBB-1

# Batch mode
python structured_data.py --batch 0 10 --all
```

### create_preview.py
Generates HTML preview pages for reviewing category mappings.

```bash
python create_preview.py  # Creates all 4 preview pages
```

## Excel Columns

The main data file (`nbg-beeldbank_all_24012026.xlsx`) contains the following columns:

| Column | Description | Used in Template |
|--------|-------------|------------------|
| `unique_id` | Record identifier (e.g., BBB-1) | Source field |
| `titel` | Title of the item | `title`, P1476 |
| `WikiCommonsFilename` | Target filename on Commons | Upload filename |
| `datum` | Date/year | `date` |
| `vervaardiger` | Creator/maker | `artist` |
| `periode` | Century/period | Not used |
| `type` | Type (Dutch, English) | `object type` (bilingual) |
| `afmetingen` | Dimensions | `dimensions` |
| `inhoud` | Description | `description` (wrapped in `{{nl|...}}`) |
| `classificatie` | Classification codes | Mapped to Commons categories |
| `gerelateerde_term` | Related terms | Not used |
| `origineel` | Original source | `notes` (prefixed) |
| `aanwezig_in` | Location/Institution | `accession number` |
| `image_url` | Full resolution image URL | Source field, P953 |
| `detail_url` | Link to detail page | Source field, P973 |
| `local_image_path` | Path to downloaded image | Upload source |
| `commons_categories` | Mapped Commons categories | Categories |
| `CommonsURL` | Wikimedia Commons file URL | After upload |
| `CommonsMidURL` | Commons M-id entity URL | After upload |

## Classification to Commons Categories Mapping

Only specific Dutch classifications are mapped to Commons categories (to avoid overly broad categorization):

| Code | Dutch Classification | Commons Category |
|------|---------------------|------------------|
| C | Paleografie, letterontwerp, lettertypen, lettergieten, schrift | [Dutch typography](https://commons.wikimedia.org/wiki/Category:Dutch_typography) |
| D | Geschiedenis van de boekdrukkunst | [Printing in the Netherlands](https://commons.wikimedia.org/wiki/Category:Printing_in_the_Netherlands) |
| F | Bindkunst | [Bookbinding in the Netherlands](https://commons.wikimedia.org/wiki/Category:Bookbinding_in_the_Netherlands) |
| J | Bibliotheken en instellingen | [Libraries in the Netherlands](https://commons.wikimedia.org/wiki/Category:Libraries_in_the_Netherlands) |

**Excluded classifications** (too broad):
- B, E, G, H, K, L (book-specific but no Dutch variant)
- M0-M9 (general subject classifications)

All files are automatically added to `[[Category:Beeldbank Nederlandse Boekgeschiedenis]]`.

## Structured Data Statements

Each uploaded file receives the following Wikibase statements:

| Property | Name | Value |
|----------|------|-------|
| P31 | Instance of | Q1250322 (digital image) |
| P195 | Collection | Q1526131 (Koninklijke Bibliotheek) |
| P6216 | Copyright status | Q19652 (public domain) |
| P1163 | MIME type | image/jpeg |
| P1476 | Title | (from `titel` column, Dutch) |
| P7482 | Source of file | Q74228490 (file available on the internet) |
| ↳ P137 | Operator | Q1526131 (Koninklijke Bibliotheek) |
| ↳ P953 | Full work available at URL | (from `image_url`) |
| ↳ P973 | Described at URL | (from `detail_url`) |

Additionally, a Dutch label (caption) is added from the `titel` column.

## Artwork Template Mapping

The `{{Artwork}}` template is populated as follows:

| Template Field | Source | Required |
|----------------|--------|----------|
| `title` | `titel` | Optional |
| `artist` | `vervaardiger` | Recommended |
| `description` | `inhoud` (wrapped in `{{nl|1=...}}`) | Optional |
| `date` | `datum` | Optional |
| `dimensions` | `afmetingen` | Optional |
| `object type` | `type` (formatted as `{{nl|...}} {{en|...}}`) | Optional |
| `institution` | Static: `{{Institution:Koninklijke Bibliotheek}}` | Optional |
| `source` | Composite from `image_url`, `detail_url`, `unique_id` | **Required** |
| `accession number` | `aanwezig_in` | Optional |
| `notes` | `origineel` (prefixed with "Orgineel:") | Optional |

**License**: `{{PD-US-expired|PD-old-70}}`

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Install Playwright browser
python -m playwright install chromium
```

## Configuration

Create a `.env` file with your Wikimedia Commons credentials:

```env
COMMONS_USERNAME=YourUsername@YourBotName
COMMONS_PASSWORD=your_bot_password_here
COMMONS_USER_AGENT=Your tool description (contact@email.com)
```

Bot passwords can be created at: https://commons.wikimedia.org/wiki/Special:BotPasswords

## Requirements

See `requirements.txt`:
- playwright (browser automation for scraping)
- pandas (data handling)
- openpyxl (Excel files)
- mwclient (Wikimedia API)
- python-dotenv (environment variables)
- requests (HTTP requests)

## License

This project uploads **public domain content** from the KB collection to Wikimedia Commons. All images in this collection are out of copyright in both the Netherlands/EU (life of author + 70 years) and the USA, making them free to use worldwide. Files are tagged with `{{PD-US-expired|PD-old-70}}` on Commons.

## Links

- **Beeldbank**: https://www.nederlandseboekgeschiedenis.nl/nl/beeldbank
- **Commons Category**: https://commons.wikimedia.org/wiki/Category:Beeldbank_Nederlandse_Boekgeschiedenis
- **KB (Koninklijke Bibliotheek)**: https://www.kb.nl/
