# 10X Genomics Data Validator

This skill validates the accuracy and consistency of scraped 10X Genomics dataset information by performing two types of validation checks.

## Task

Validate the scraped dataset information to ensure data integrity and accuracy through automated checks.

### Input Sources

The validator reads from the scraper's output directory:
- **JSON**: `../scraper/output/Data-10XGenomics-VisiumHD-Human.json`
- **Excel**: `../scraper/output/Data-10XGenomics-VisiumHD-Human.xlsx`

## Validation Types

### 1. File Consistency Validation

**Purpose**: Ensure JSON and Excel outputs contain identical data

**Checks**:
- Entry count matches between JSON and Excel
- All dataset URLs are present in both files
- All fields match for each dataset:
  - `dataset_name`
  - `dataset_url`
  - `product`
  - `species`
  - `sample_type`
  - `cells_or_nuclei`
  - `preservation`
- Field values are identical (no data corruption)

**Output**: Detailed report of any mismatches with row/column references

### 2. URL Content Validation

**Purpose**: Verify that scraped data matches actual content on dataset detail pages

**Process**:
1. For each dataset URL in the scraped data:
   - Launch headless browser
   - Navigate to the dataset detail page
   - Extract actual metadata from the page
   - Compare with scraped values
   - Record matches, mismatches, and missing fields

**Checks**:
- Dataset name matches page title
- Product information is correct
- Species is correctly identified
- Sample type matches
- Preservation method is accurate
- Cells/Nuclei information is correct

**Output**: Validation report showing:
- ✅ Verified entries (data matches website)
- ❌ Mismatched entries (differences found)
- ⚠️ Warning entries (fields missing or unclear)
- 🔗 Failed URLs (page not accessible)

## Output Format

The validator generates comprehensive reports in multiple formats:

### JSON Report

```json
{
  "validation_timestamp": "2025-10-30T09:30:00Z",
  "total_datasets": 19,
  "file_consistency": {
    "passed": true,
    "json_count": 19,
    "excel_count": 19,
    "mismatches": []
  },
  "url_validation": {
    "verified": 18,
    "mismatched": 1,
    "warnings": 0,
    "failed_urls": 0,
    "results": [
      {
        "dataset_url": "https://...",
        "status": "verified|mismatched|warning|failed",
        "differences": []
      }
    ]
  },
  "exit_code": 0
}
```

### HTML Report

An interactive HTML report with:
- Summary dashboard (pass/fail counts, percentages)
- Detailed results table with filtering
- Diff viewer for mismatched entries
- Color-coded status indicators
- Timestamp and execution metadata

### Report Location

- **JSON**: `./reports/validation_report_YYYY-MM-DD_HH-MM-SS.json`
- **HTML**: `./reports/validation_report_YYYY-MM-DD_HH-MM-SS.html`

## Exit Codes

The validator uses standard exit codes for pipeline integration:

- **0**: All validations passed
- **1**: Validation failures detected (file inconsistencies or URL mismatches)
- **2**: Critical error (unable to read input files, network issues, etc.)

## Usage

### Standalone Execution

```bash
python validator.py
```

### Via Orchestrator

```bash
# Run full pipeline (scraper + validator)
python ../../orchestrator.py

# Run only validator (skip scraping)
python ../../orchestrator.py --skip-scraping
```

### Command Line Options

```bash
python validator.py [OPTIONS]

Options:
  --json-path PATH        Path to JSON file (default: ../scraper/output/Data-10XGenomics-VisiumHD-Human.json)
  --excel-path PATH       Path to Excel file (default: ../scraper/output/Data-10XGenomics-VisiumHD-Human.xlsx)
  --skip-file-check       Skip file consistency validation
  --skip-url-check        Skip URL content validation
  --output-dir PATH       Output directory for reports (default: ./reports)
  --max-retries N         Max retries for failed URLs (default: 3)
  --timeout N             Timeout for page loads in seconds (default: 30)
```

## Directory Structure

```
skills/validator/
├── SKILL.md                    # This file (agent instructions)
├── validator.py                # Validator script
└── reports/                    # Validation reports
    ├── validation_report_YYYY-MM-DD_HH-MM-SS.json
    └── validation_report_YYYY-MM-DD_HH-MM-SS.html
```

## Technical Details

- **Browser Automation**: Uses Selenium with headless Chrome for URL validation
- **Data Comparison**: Uses pandas for file comparison and deepdiff for detailed diff analysis
- **Report Generation**: Uses jinja2 for HTML report templating
- **Error Handling**: Implements retry logic for transient network errors
- **Logging**: Comprehensive logging to stderr with progress indicators

## Validation Logic Details

### Field Extraction from Dataset Pages

The validator extracts fields from dataset detail pages using these selectors/patterns:

- **Dataset Name**: Page title or main heading
- **Product**: Product/technology section
- **Species**: Organism field
- **Sample Type**: Tissue/sample type field
- **Preservation**: Sample preparation method
- **Cells or Nuclei**: Cell type information (may be N/A)

### Comparison Rules

- **Exact match**: dataset_url, species, product version
- **Case-insensitive**: dataset_name (allows for minor formatting differences)
- **Substring match**: sample_type (allows "Pancreas" vs "Human Pancreas")
- **Normalized match**: preservation (handles "FFPE" vs "ffpe" vs "Formalin-Fixed Paraffin-Embedded")

### Tolerance Levels

- **Strict**: URL, species, product must match exactly
- **Moderate**: Sample type and preservation allow normalized variations
- **Lenient**: Dataset name allows case and whitespace differences

## Error Scenarios

### Handled Gracefully

- Dataset page temporarily unavailable → Retry with backoff
- Field missing on page → Mark as warning, not failure
- Minor formatting differences → Apply normalization rules

### Reported as Failures

- Data type mismatch (e.g., "Human" vs "Mouse")
- Missing required fields that were scraped
- File consistency issues between JSON and Excel

## Agent Independence

This validator agent:
- ✅ Runs independently of the scraper agent
- ✅ Reads input from file system (no direct agent communication)
- ✅ Can be executed standalone or via orchestrator
- ✅ Produces structured output for downstream processing
- ✅ Uses standard exit codes for pipeline integration

## Performance Considerations

- **Parallel URL Checks**: Validates multiple URLs concurrently (default: 5 concurrent connections)
- **Caching**: Caches browser instances to reduce overhead
- **Progress Indicators**: Shows progress for long-running validations
- **Estimated Time**: ~2-5 seconds per URL (total ~1-2 minutes for 19 datasets)
