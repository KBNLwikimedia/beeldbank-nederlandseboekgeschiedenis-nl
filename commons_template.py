"""
Wikimedia Commons {{Artwork}} template mapping for Beeldbank Nederlandse Boekgeschiedenis.

This module defines the mapping between Excel columns and the Artwork template fields,
and provides functions to generate wikitext for file description pages.

Template Fields Mapping:
    - title: from 'titel' column
    - artist: from 'vervaardiger' column
    - description: from 'inhoud' column (wrapped in {{nl|1=...}})
    - date: from 'datum' column
    - dimensions: from 'afmetingen' column
    - object type: from 'type' column (formatted as {{nl|...}} {{en|...}})
    - institution: static (Koninklijke Bibliotheek)
    - source: composite (image_url, detail_url, unique_id)
    - accession number: from 'aanwezig_in' column
    - notes: from 'origineel' column (prefixed with "Orgineel:")

Categories:
    - Base: [[Category:Beeldbank Nederlandse Boekgeschiedenis]]
    - Additional: from 'commons_categories' column

License: {{PD-US-expired|PD-old-70}}

Usage:
    from commons_template import generate_wikitext, get_upload_filename

    wikitext = generate_wikitext(row)
    filename = get_upload_filename(row)
"""

# Mapping: Excel column -> Artwork template field
# Format: (excel_column, template_field, required, transform_function_name)
FIELD_MAPPING = [
    # Excel Column         Template Field      Required   Notes
    ('titel',              'title',            False,     'direct'),
    ('vervaardiger',       'artist',           False,     'direct'),      # Recommended
    ('inhoud',             'description',      False,     'wrap_nl'),     # Wrap in {{nl|1=...}}
    ('datum',              'date',             False,     'direct'),
    ('afmetingen',         'dimensions',       False,     'direct'),      # 70.3% filled
    ('type',               'object type',      False,     'direct'),      # 89.5% filled
    # institution is static
    # source is composite (required)
    ('aanwezig_in',        'accession number', False,     'direct'),      # 51.1% filled
    ('origineel',          'notes',            False,     'prefix_origineel'),  # 61.0% filled
]

# Static values
INSTITUTION = "{{Institution:Koninklijke Bibliotheek}}"
SOURCE_TEMPLATE = """{{{{Koninklijke Bibliotheek}}}}
* Image: {image_url}
* Metadata: {detail_url}
* Beeldbank Nederlandse Boekgeschiedenis Identifier: {unique_id}"""

LICENSE = "{{PD-US-expired|PD-old-70}}"
CATEGORY = "[[Category:Beeldbank Nederlandse Boekgeschiedenis]]"

# The complete wikitext template
ARTWORK_TEMPLATE = """=={{{{int:filedesc}}}}==
{{{{Artwork
| title = {title}
| artist = {artist}
| description = {description}
| date = {date}
| dimensions = {dimensions}
| object type = {object_type}
| institution = {institution}
| source = {source}
| accession number = {accession_number}
| notes = {notes}
| permission =
| other versions =
}}}}

=={{{{int:license-header}}}}==
{license}

{categories}"""


def wrap_nl(text):
    """Wrap text in Dutch language template."""
    if text:
        return f"{{{{nl|1={text}}}}}"
    return ""


def prefix_origineel(text):
    """Prefix text with 'Orgineel: ' if not empty."""
    if text:
        return f"Orgineel: {text}"
    return ""


def format_bilingual_type(type_str):
    """
    Format the type field as bilingual (Dutch + English) if both are present.

    The Excel has format: "Dutch term, English term"
    Output format: {{nl|1=Dutch term}} {{en|1=English term}}

    If empty or single value, no language templates are used.

    Args:
        type_str: The type string from Excel (e.g., "illustratie, illustration")

    Returns:
        str: Formatted string (bilingual with templates, or plain if single/empty)
    """
    if not type_str:
        return ""

    parts = type_str.split(', ')
    if len(parts) == 2:
        # Bilingual: use language templates
        dutch = parts[0].strip().capitalize()
        english = parts[1].strip().capitalize()
        return f"{{{{nl|1={dutch}}}}} {{{{en|1={english}}}}}"
    else:
        # Single value or unexpected format: return capitalized without templates
        return type_str.strip().capitalize()


def convert_unique_id(unique_id):
    """Convert unique_id from Excel format (BBB-1) to template format (BBB:1)."""
    if unique_id:
        return unique_id.replace('-', ':', 1)  # Replace only first hyphen
    return ""


def safe_str(value):
    """Convert value to string, handling None/NaN."""
    if value is None:
        return ""
    if isinstance(value, float):
        import math
        if math.isnan(value):
            return ""
    return str(value).strip()


def build_categories(row):
    """
    Build the categories wikitext from the base category and commons_categories.

    Args:
        row: A pandas Series or dict-like object with the Excel columns

    Returns:
        str: The categories wikitext (e.g., [[Category:X]]\n[[Category:Y]])
    """
    categories = [CATEGORY]  # Always include the base category

    # Add categories from commons_categories column
    commons_cats = safe_str(row.get('commons_categories', ''))
    if commons_cats:
        for cat in commons_cats.split('; '):
            cat = cat.strip()
            if cat:
                categories.append(f'[[Category:{cat}]]')

    return '\n'.join(categories)


def generate_wikitext(row):
    """
    Generate wikitext for a single record from the Excel data.

    Args:
        row: A pandas Series or dict-like object with the Excel columns

    Returns:
        str: The complete wikitext for the Wikimedia Commons file page
    """
    # Build the source field (required)
    # Convert unique_id from Excel format (BBB-1) to template format (BBB:1)
    unique_id = convert_unique_id(safe_str(row.get('unique_id', '')))
    source = SOURCE_TEMPLATE.format(
        image_url=safe_str(row.get('image_url', '')),
        detail_url=safe_str(row.get('detail_url', '')),
        unique_id=unique_id
    )

    # Process each mapped field
    title = safe_str(row.get('titel', ''))
    artist = safe_str(row.get('vervaardiger', ''))
    description = wrap_nl(safe_str(row.get('inhoud', '')))
    date = safe_str(row.get('datum', ''))
    dimensions = safe_str(row.get('afmetingen', ''))
    object_type = format_bilingual_type(safe_str(row.get('type', '')))
    accession_number = safe_str(row.get('aanwezig_in', ''))
    notes = prefix_origineel(safe_str(row.get('origineel', '')))

    # Build categories (base + commons_categories)
    categories = build_categories(row)

    # Generate the complete wikitext
    wikitext = ARTWORK_TEMPLATE.format(
        title=title,
        artist=artist,
        description=description,
        date=date,
        dimensions=dimensions,
        object_type=object_type,
        institution=INSTITUTION,
        source=source,
        accession_number=accession_number,
        notes=notes,
        license=LICENSE,
        categories=categories
    )

    return wikitext


def get_upload_filename(row):
    """
    Get the filename for uploading to Wikimedia Commons.

    Args:
        row: A pandas Series or dict-like object with the Excel columns

    Returns:
        str: The filename for the upload
    """
    return safe_str(row.get('WikiCommonsFilename', ''))


def get_local_filepath(row):
    """
    Get the local file path of the image to upload.

    Args:
        row: A pandas Series or dict-like object with the Excel columns

    Returns:
        str: The local file path
    """
    return safe_str(row.get('local_image_path', ''))


# For testing: generate wikitext for a sample record
if __name__ == "__main__":
    # Sample record matching the example upload
    sample_record = {
        'unique_id': 'BBB-1',  # Excel format, will be converted to BBB:1
        'titel': 'De wolf en de ezel uit de "Dyalogus creaturarum" gedrukt door Gheraert Leeu, Gouda, 1481',
        'WikiCommonsFilename': 'De wolf en de ezel uit de Dyalogus creaturarum gedrukt door Gheraert Leeu Gouda, 1481 - BBB-1.jpg',
        'datum': '4 apr. 1481',
        'vervaardiger': 'anoniem/anonymous (auteur/author), Leeu, Gheraert (drukker/printer), Pergamenus, Nicolaus (auteur/author), De Mayneriis, Mayno (auteur/author)',
        'type': 'illustratie, illustration',
        'afmetingen': '11,1 x 7,9 cm.',
        'inhoud': 'Illustratie van een anoniem kunstenaar uit een verzameling fabels en exempels, weergegeven in 122 dialogen tussen dieren en mensen met 120 in de 17e eeuw ingekleurde houtsneden. De houtsnede werd in dit soort incunabelen als de meest gangbare illustratietechniek toegepast.',
        'origineel': '[Nicolaus Pergamenus of Mayno de Mayneriis]. - Dyalogus creaturarum dat is twijspraec der creaturen. - Gouda: Gerard Leeu, 1481, dl. 2, fol. o4r',
        'aanwezig_in': 'Koninklijke Bibliotheek, Den Haag 170 E 26',
        'image_url': 'http://resolver.kb.nl/resolve?urn=urn:BBB:170E26_1481-DL2-WO_FOLO4R',
        'detail_url': 'https://www.nederlandseboekgeschiedenis.nl/nl/beeldbank?id=BBB%3A1#jsru-search-record',
        'local_image_path': r'D:\KB-OPEN\github-repos\beeldbank-nederlandseboekgeschiedenis-nl\images\BBB_170E26_1481-DL2-WO_FOLO4R.jpg',
    }

    print("Generated wikitext:")
    print("=" * 80)
    print(generate_wikitext(sample_record))
    print("=" * 80)
    print(f"\nUpload filename: {get_upload_filename(sample_record)}")
    print(f"Local file: {get_local_filepath(sample_record)}")
