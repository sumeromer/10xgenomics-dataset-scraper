# 10X Genomics File Extractor

This skill extracts file download information (URLs, sizes, MD5 checksums) from dataset detail pages and adds them to the enriched dataset information.

## Task

Read enriched dataset JSON and Excel files, visit each dataset URL, and extract comprehensive file metadata including download links, file types, sizes, and MD5 checksums.

### Input Sources

The file extractor reads from the metadata enricher's output directory:
- **JSON**: `output/{name}/enriched/Data-{name}-Enriched.json`
- **Excel**: `output/{name}/enriched/Data-{name}-Enriched.xlsx`

Note: The file extractor works with enriched data that includes metadata from previous pipeline stages.

## File Information to Extract

### From Input Files Section

1. **Microscope images** - BTF/TIF format microscopy images
2. **CytAssist images** - TIF format CytAssist images
3. **FASTQs** - TAR format sequencing data

### From Output and Supplemental Files Section

1. **Binned outputs** - GZ format binned data (all bin levels)
2. **Feature slice H5** - H5 format feature data
3. **Loupe files** - CLOUPE format visualization files
4. **Web summaries** - HTML format summary reports
5. **Other outputs** - CSV, TSV, and other supplemental files

### For Each File

Extract the following metadata:
- **file_title**: Human-readable file description (e.g., "Microscope image")
- **file_type**: File extension in uppercase (e.g., "BTF", "TIF", "GZ")
- **filename**: Complete filename from URL
- **size**: Human-readable size (e.g., "4.62 GB", "145.23 MB")
- **size_bytes**: Size in bytes for programmatic use
- **md5sum**: MD5 checksum for file integrity verification
- **url**: Direct download URL

## Output Format

The file extractor updates the existing enriched JSON and Excel files **in place** by adding file information to each dataset entry.

### Enhanced JSON Schema

```json
[
  {
    "dataset_name": "string",
    "dataset_url": "string",
    // ... all previous fields ...
    "files": [
      {
        "file_title": "Microscope image",
        "file_type": "BTF",
        "filename": "tissue_image.btf",
        "size": "8.02 GB",
        "size_bytes": 8020000000,
        "md5sum": "cb80c0cedaf581b2...",
        "url": "https://cf.10xgenomics.com/..."
      }
    ],
    "files_found_count": 14,
    "file_extraction_status": "success"
  }
]
```

### Enhanced Excel Output

The Excel output adds new columns:
- **files** - JSON-formatted list of file objects
- **files_found_count** - Integer count of files found
- **file_extraction_status** - "success", "failed", or "error"

## Directory Structure

```
skills/file_extractor/
├── SKILL.md                    # This file (agent instructions)
├── README.md                   # User documentation
├── file_extractor.py           # File extractor script
└── debug_page.py              # Debug utility for page inspection
```

## Usage

### Standalone Execution

```bash
python file_extractor.py --name "10xgenomics_visiumhd" --base-output-dir "../../output"
```

### Via Orchestrator

```bash
# Run full pipeline (all agents including file_extractor)
python orchestrator.py --url "..." --name "10xgenomics_visiumhd"

# Run only file_extractor (requires existing enriched data)
python orchestrator.py --skip-scraping --skip-validation --skip-enrichment --name "10xgenomics_visiumhd"
```

### Command Line Options

```bash
python file_extractor.py [OPTIONS]

Options:
  --name NAME              Run identifier (required, e.g., "10xgenomics_visiumhd")
  --base-output-dir PATH   Base output directory (default: ../../output)
  --max-retries N         Max retries for failed page loads (default: 3)
  --timeout N             Timeout for page loads in seconds (default: 30)
```

## Extraction Strategy

### Page Structure Analysis

The script uses Selenium to:
1. Navigate to each dataset detail page
2. Wait for page content to load completely
3. Extract `__NEXT_DATA__` JSON from page source (Next.js data)
4. Parse the `filesetMap` structure for file metadata
5. Handle both single-experiment and multi-experiment datasets

### Dataset Structure Handling

The extractor handles two different page structures:

#### Single-Experiment Datasets
```json
{
  "filesetMap": {
    "Files": {
      "inputs": [...],
      "outputs": [...]
    }
  }
}
```

#### Multi-Experiment Datasets
```json
{
  "filesetMap": {
    "Experiment 1, HD only (control)": {
      "inputs": [...],
      "outputs": [...]
    },
    "Experiment 2, post-Xenium": {
      "inputs": [...],
      "outputs": [...]
    }
  }
}
```

The extractor automatically detects the structure and processes all experiments.

### Size Conversion

Sizes are converted using **decimal** (1000-based) units to match the website display:
- `1000 bytes = 1 KB`
- `1000 KB = 1 MB`
- `1000 MB = 1 GB`

This matches the 10X Genomics website's size reporting.

### Error Handling

- **Missing files**: Record status as "failed", files_found_count = 0
- **Page load failures**: Retry up to max_retries times
- **Parsing errors**: Log error and mark dataset as failed
- **Network issues**: Implement retry logic with timeout

## Exit Codes

- **0**: All datasets processed successfully
- **1**: Some datasets failed to extract files (partial success)
- **2**: Critical error (unable to read input files, no browser available, etc.)

## Performance Considerations

- **Browser Automation**: Uses headless Chrome for efficiency
- **Progress Tracking**: Shows real-time progress with tqdm progress bars
- **Estimated Time**: ~2-3 seconds per dataset
- **Batch Processing**: Processes all datasets in sequence
- **Memory Efficient**: Processes datasets one at a time

## Technical Details

- **Browser Automation**: Uses Selenium with headless Chrome
- **Data Source**: Extracts from `__NEXT_DATA__` JSON embedded in page
- **Data Processing**: Uses pandas for DataFrame manipulation
- **Excel Export**: Preserves existing formatting while adding new columns
- **Logging**: Comprehensive logging to stderr with progress indicators
- **Timestamp Tracking**: Updates `timestamp.txt` with completion time

## Modular Functions

The file extractor is organized into modular functions:

- **`setup_driver()`** - Configures and initializes Chrome WebDriver
- **`extract_next_data_json(driver)`** - Extracts `__NEXT_DATA__` from page source
- **`extract_file_info(driver)`** - Extracts file metadata from JSON structure
- **`process_dataset(dataset, max_retries, timeout)`** - Processes one dataset
- **`load_enriched_data(json_path, excel_path)`** - Loads enriched input files
- **`save_updated_data(datasets, json_path, excel_path)`** - Saves updated files
- **`update_timestamp(timestamp_file)`** - Updates timestamp tracking file
- **`main()`** - Orchestrates the file extraction workflow

## Agent Independence

This file extractor agent:
- ✅ Runs independently after metadata enrichment
- ✅ Reads enriched input from file system
- ✅ Can be executed standalone or via orchestrator
- ✅ Updates existing files in place (no separate output directory)
- ✅ Uses standard exit codes for pipeline integration
- ✅ Maintains backward compatibility with existing data structure

## Data Quality

The file extractor ensures data quality by:
- **Validation**: Only processes datasets with valid URLs
- **Consistency**: Maintains all original fields unchanged
- **Completeness**: Attempts to extract all available files
- **Accuracy**: Uses exact file metadata from website JSON data
- **Traceability**: Logs extraction status for each dataset
- **Verification**: Provides summary statistics on success/failure rates

## Notes

- The extractor updates existing enriched files **in place**
- Original fields remain unchanged; only adds `files`, `files_found_count`, `file_extraction_status`
- Missing or unavailable files result in empty `files` array with status "failed"
- Handles both single-experiment and multi-experiment dataset pages
- Size conversions use decimal (1000-based) to match website display
- Can be re-run safely to update file information
- Progress is reported to stderr, final status to stdout
- Updates `timestamp.txt` with execution time for tracking
