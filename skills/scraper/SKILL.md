# 10X Genomics Visium HD Dataset Scraper

This skill scrapes the 10X Genomics datasets page to extract information about Visium HD Spatial Gene Expression datasets for human samples.

## Task

Scrape the filtered 10X Genomics datasets page and extract structured information about each dataset entry.

### Source URL

```
https://www.10xgenomics.com/datasets?configure%5BhitsPerPage%5D=50&configure%5BmaxValuesPerFacet%5D=1000&query=Visium%20HD&refinementList%5Bplatform%5D%5B0%5D=Visium%20Spatial&refinementList%5Bproduct.name%5D%5B0%5D=HD%20Spatial%20Gene%20Expression&refinementList%5Bspecies%5D%5B0%5D=Human
```

This URL filters for:
- Platform: Visium Spatial
- Product: HD Spatial Gene Expression
- Species: Human

## Data to Extract

For each dataset entry in the table/list, extract the following information:

1. **Dataset Name** - The name/title of the dataset (from the first column)
2. **Dataset URL** - The link URL when the dataset name is clicked
3. **Product** - Product type (e.g., "HD Spatial Gene Expression")
4. **Species** - Species information (e.g., "Human")
5. **Sample Type** - Type of sample used
6. **Cells or Nuclei** - Whether cells or nuclei were used
7. **Preservation** - Preservation method used

## Output Format

The scraper outputs the extracted data in two formats:

1. **JSON** - Structured JSON array
2. **Excel** - Formatted spreadsheet (.xlsx)

### JSON Output

Output the extracted data as a structured JSON array with the following schema:

```json
[
  {
    "dataset_name": "string",
    "dataset_url": "string",
    "product": "string",
    "species": "string",
    "sample_type": "string",
    "cells_or_nuclei": "string",
    "preservation": "string"
  }
]
```

### Example Output

```json
[
  {
    "dataset_name": "Visium HD Spatial Gene Expression Library, Human Pancreas (FFPE)",
    "dataset_url": "https://www.10xgenomics.com/datasets/visium-hd-cytassist-gene-expression-libraries-human-pancreas-4",
    "product": "HD Spatial Gene Expression v1.0",
    "species": "Human",
    "sample_type": "Pancreas",
    "cells_or_nuclei": "N/A",
    "preservation": "FFPE"
  },
  {
    "dataset_name": "Visium HD Spatial Gene Expression Library, Human Breast Cancer (Fresh Frozen), Ultima Sequencing",
    "dataset_url": "https://www.10xgenomics.com/datasets/visium-hd-cytassist-gene-expression-libraries-human-breast-cancer-ff-ultima-4",
    "product": "HD Spatial Gene Expression v1.0",
    "species": "Human",
    "sample_type": "Breast",
    "cells_or_nuclei": "N/A",
    "preservation": "Fresh Frozen"
  }
]
```

### Excel Output

The Excel output contains the same data as the JSON format, but presented as a spreadsheet with the following features:

- **Sheet Name**: "Datasets"
- **Columns**: All fields are included as separate columns in the same order as the JSON schema
- **Auto-sized columns**: Column widths are automatically adjusted to fit content
- **Header row**: First row contains column headers
- **No index column**: Data starts from column A

The Excel file is ideal for:
- Quick visual inspection of the data
- Sorting and filtering datasets
- Manual data analysis
- Sharing with non-technical stakeholders
- Importing into other tools

## Directory Structure

The scraper uses a modular directory structure with parameterized output paths:

```
10XGenomics_scraper/
├── output/                     # Base output directory
│   └── {name}/                 # Run-specific directory (e.g., "10XGenomics-VisiumHD-Human")
│       ├── input/              # Input directory for this run
│       │   ├── URL-{name}.txt          # Source URL saved here
│       │   └── RawData-{name}.html     # Raw HTML page source
│       └── output/             # Output directory for this run
│           ├── Data-{name}.json        # Scraped data (JSON format)
│           └── Data-{name}.xlsx        # Scraped data (Excel format)
└── scraper.py                  # Main scraper script
```

### Parameterization

The scraper supports dynamic configuration via command-line parameters:

- **`--url`**: The source URL to scrape (e.g., filtered datasets page)
- **`--name`**: Human-readable identifier for this scraping run (e.g., "10XGenomics-VisiumHD-Human", "10XGenomics-Xenium-Mouse")
- **`--base-output-dir`**: Base directory for all outputs (default: `../../output`)

This structure allows multiple scraping runs to coexist without conflicts.

## Instructions

### Automated Scraping (Recommended)

Run the Python scraper script with URL and name parameters:

```bash
python scraper.py --url "https://www.10xgenomics.com/datasets?query=Visium%20HD" --name "10XGenomics-VisiumHD-Human"
```

The script will:
1. Create `../../output/{name}/input/` and `../../output/{name}/output/` directories if they don't exist
2. Save the source URL to `../../output/{name}/input/URL-{name}.txt`
3. Launch a headless Chrome browser
4. Navigate to the provided URL
5. Wait for JavaScript content to load dynamically
6. Extract all dataset entries with their metadata from the table
7. Save the raw HTML page source to `../../output/{name}/input/RawData-{name}.html`
8. Save results as JSON to `../../output/{name}/output/Data-{name}.json`
9. Save results as Excel to `../../output/{name}/output/Data-{name}.xlsx`
10. Also output JSON to stdout for backward compatibility

**Command-line Options:**
```bash
python scraper.py --url URL --name NAME [--base-output-dir DIR]

Required:
  --url URL              Source URL to scrape
  --name NAME            Human-readable run identifier

Optional:
  --base-output-dir DIR  Base output directory (default: ../../output)
```

### Manual Steps (if needed)

1. Ensure dependencies are installed: `conda env create -f environment.yml` and `conda activate 10XGenomics_scraper`
2. Run the scraper script: `python scraper.py`
3. Find the outputs in:
   - JSON: `./output/Data-10XGenomics-VisiumHD-Human.json`
   - Excel: `./output/Data-10XGenomics-VisiumHD-Human.xlsx`

## Modular Functions

The scraper is organized into modular functions for better maintainability:

- **`ensure_directories()`** - Creates input/output directories if they don't exist
- **`save_url_to_file(url, filepath)`** - Saves the source URL to the input directory
- **`save_raw_html(html_content, filepath)`** - Saves the raw HTML page source to the input directory
- **`save_json_output(data, filepath)`** - Saves the scraped data as JSON to the output directory
- **`save_excel_output(data, filepath)`** - Saves the scraped data as Excel to the output directory with auto-sized columns
- **`setup_driver()`** - Configures and initializes the Chrome WebDriver
- **`scrape_datasets(url)`** - Performs the web scraping and data extraction
- **`main()`** - Orchestrates the entire scraping workflow

## Technical Details

- **Browser**: Uses Chrome/Chromium in headless mode
- **Driver Management**: Automatically downloads and manages ChromeDriver via webdriver-manager
- **Wait Strategy**: Implements explicit waits for dynamic content loading
- **Table Parsing**: Extracts data from table rows with position-based column mapping
- **Error Handling**: Gracefully handles missing fields and extraction errors
- **File Organization**: Automatically manages input/output file structure
- **Excel Export**: Uses pandas and openpyxl to generate formatted Excel spreadsheets with auto-sized columns
- **Data Processing**: Converts JSON data to pandas DataFrame for flexible export formats

## Notes

- The page uses JavaScript to load data dynamically, requiring browser automation
- WebFetch tool is insufficient as it only retrieves static HTML
- The scraper extracts data from the table body (`<tbody>`), filtering out header/navigation elements
- Position-based extraction ensures all metadata fields are captured accurately
- Progress and debug information is output to stderr, JSON results to stdout and file
