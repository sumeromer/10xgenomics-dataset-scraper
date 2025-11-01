# 10X Genomics Metadata Enricher

This skill enriches the validated dataset information by extracting additional metadata from each dataset's detail page.

## Task

Read validated dataset JSON and Excel files, visit each dataset URL, and extract comprehensive metadata from the dataset detail pages to enrich the existing data.

### Input Sources

The enricher reads from the validator's output directory:
- **JSON**: `../scraper/output/Data-10XGenomics-VisiumHD-Human.json`
- **Excel**: `../scraper/output/Data-10XGenomics-VisiumHD-Human.xlsx`

Note: The enricher should work with already-validated data to ensure data quality.

## Metadata to Extract

### From Dataset Overview → Imaging Section

Extract the following fields:

1. **Biomaterials** - Type of biomaterial used
2. **Sample preparation** - Sample preparation method details
3. **Image type** - Type of imaging (e.g., H&E, IF, etc.)
4. **Microscope** - Microscope model/manufacturer used
5. **Objective magnification** - Magnification level (e.g., 20X, 40X)
6. **Numerical Aperture** - Objective numerical aperture value
7. **ScopeLED light source** - Light source specifications
8. **Camera** - Camera model/specifications
9. **Exposure** - Exposure settings/time

### From Right Panel (Sample Information)

Extract the following fields:

1. **Species** - Species information (if not already captured)
2. **Anatomical Entity** - Anatomical location/tissue
3. **Preservation Method** - Preservation method (FFPE, Fresh Frozen, etc.)
4. **Disease State** - Disease state or condition (e.g., Healthy, Cancer)
5. **Biomaterial Type** - Type of biomaterial (e.g., Tissue section)
6. **Donor Count** - Number of donors
7. **Date Published** - Publication date of the dataset

## Output Format

The enricher generates enhanced versions of both JSON and Excel files with all original fields plus the new metadata fields.

### Enhanced JSON Schema

```json
[
  {
    "dataset_name": "string",
    "dataset_url": "string",
    "product": "string",
    "species": "string",
    "sample_type": "string",
    "cells_or_nuclei": "string",
    "preservation": "string",
    "biomaterials": "string",
    "sample_preparation": "string",
    "image_type": "string",
    "microscope": "string",
    "objective_magnification": "string",
    "numerical_aperture": "string",
    "scopeled_light_source": "string",
    "camera": "string",
    "exposure": "string",
    "anatomical_entity": "string",
    "preservation_method": "string",
    "disease_state": "string",
    "biomaterial_type": "string",
    "donor_count": "string",
    "date_published": "string"
  }
]
```

### Enhanced Excel Output

The Excel output contains all fields as separate columns:

- **Original columns**: dataset_name, dataset_url, product, species, sample_type, cells_or_nuclei, preservation
- **New Imaging columns**: biomaterials, sample_preparation, image_type, microscope, objective_magnification, numerical_aperture, scopeled_light_source, camera, exposure
- **New Sample Info columns**: anatomical_entity, preservation_method, disease_state, biomaterial_type, donor_count, date_published

## Directory Structure

```
skills/metadata_enricher/
├── SKILL.md                    # This file (agent instructions)
├── metadata_enricher.py        # Enricher script
└── output/                     # Enriched output files
    ├── Data-10XGenomics-VisiumHD-Human-Enriched.json
    └── Data-10XGenomics-VisiumHD-Human-Enriched.xlsx
```

## Usage

### Standalone Execution

```bash
python metadata_enricher.py
```

### Via Orchestrator

```bash
# Run full pipeline (scraper + validator + enricher)
python ../../orchestrator.py

# Run only enricher (requires existing validated data)
python ../../orchestrator.py --skip-scraping --skip-validation
```

### Command Line Options

```bash
python metadata_enricher.py [OPTIONS]

Options:
  --json-path PATH        Path to input JSON file (default: ../scraper/output/Data-10XGenomics-VisiumHD-Human.json)
  --excel-path PATH       Path to input Excel file (default: ../scraper/output/Data-10XGenomics-VisiumHD-Human.xlsx)
  --output-dir PATH       Output directory for enriched files (default: ./output)
  --max-retries N         Max retries for failed page loads (default: 3)
  --timeout N             Timeout for page loads in seconds (default: 30)
  --parallel N            Number of parallel browser instances (default: 3)
```

## Extraction Strategy

### Page Structure Analysis

The script uses Selenium to:
1. Navigate to each dataset detail page
2. Wait for dynamic content to load
3. Locate the "Dataset Overview" section
4. Find the "Imaging" subsection within Dataset Overview
5. Extract key-value pairs from the Imaging section
6. Locate the right panel with sample information
7. Extract metadata from the sample info panel

### Field Mapping

The script uses intelligent field mapping to handle variations in field names:
- **Case-insensitive matching**: "Biomaterials" vs "biomaterials"
- **Label variations**: "Objective Magnification" vs "Magnification"
- **Flexible selectors**: Multiple XPath/CSS selectors to accommodate page changes

### Error Handling

- **Missing fields**: Record as empty string or "N/A"
- **Page load failures**: Retry up to max_retries times
- **Parsing errors**: Log error and continue with next field
- **Network issues**: Implement exponential backoff

## Exit Codes

- **0**: All datasets enriched successfully
- **1**: Some datasets failed to enrich (partial success)
- **2**: Critical error (unable to read input files, no browser available, etc.)

## Performance Considerations

- **Parallel Processing**: Process multiple URLs concurrently (default: 3 browsers)
- **Browser Reuse**: Reuse browser instances where possible
- **Progress Tracking**: Show real-time progress with ETA
- **Caching**: Cache extracted data to allow resume on failure
- **Estimated Time**: ~3-5 seconds per dataset (total ~1-3 minutes for 19 datasets)

## Technical Details

- **Browser Automation**: Uses Selenium with headless Chrome
- **Data Processing**: Uses pandas for DataFrame manipulation
- **Excel Export**: Uses openpyxl for formatted Excel output with auto-sized columns
- **Logging**: Comprehensive logging to stderr with progress indicators
- **Resume Support**: Can resume from partial completion using checkpoint file

## Modular Functions

The enricher is organized into modular functions:

- **`ensure_directories()`** - Creates output directory if needed
- **`load_input_data(json_path, excel_path)`** - Loads validated input files
- **`setup_driver()`** - Configures and initializes Chrome WebDriver
- **`extract_imaging_metadata(driver)`** - Extracts imaging section metadata
- **`extract_sample_info(driver)`** - Extracts right panel sample information
- **`enrich_single_dataset(dataset, max_retries, timeout)`** - Enriches one dataset
- **`enrich_all_datasets(datasets, max_workers, max_retries, timeout)`** - Enriches all datasets with parallel processing
- **`save_enriched_data(data, output_dir)`** - Saves enriched JSON and Excel files
- **`main()`** - Orchestrates the enrichment workflow

## Agent Independence

This enricher agent:
- ✅ Runs independently after validation
- ✅ Reads validated input from file system
- ✅ Can be executed standalone or via orchestrator
- ✅ Produces structured output for downstream processing
- ✅ Uses standard exit codes for pipeline integration
- ✅ Does not modify original scraper/validator outputs (creates new files)

## Data Quality

The enricher ensures data quality by:
- **Validation**: Only processes validated input data
- **Consistency**: Maintains all original fields unchanged
- **Completeness**: Attempts to extract all specified fields
- **Traceability**: Logs which fields were successfully extracted vs. missing
- **Verification**: Provides summary statistics on field completion rates

## Notes

- The enricher adds NEW fields without modifying existing ones
- Original files remain unchanged; enriched data is saved separately
- Missing or unavailable fields are marked as empty strings
- The script handles dynamic page content using explicit waits
- Progress is reported to stderr, final status to stdout
- Can be re-run safely (idempotent operation)
