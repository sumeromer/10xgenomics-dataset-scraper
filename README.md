# 10xgenomics-dataset-scraper

A multi-agent orchestrator and Model Context Protocol (MCP) system to automate the scraping, validation, and metadata retrieval of spatial transcriptomics and microscopy image datasets from 10xgenomics.com.

This repository implements an automated data engineering pipeline for collecting 10X Genomics datasets' metadata, built as a practical learning project for Claude Skills and MCP.

## Overview

This project implements an automated, multi-agent architecture for:

- [x] **Scraping** dataset information from 10X Genomics website (main search page)
- [x] **Validating** scraped data for accuracy and consistency (cross-referencing search page with individual dataset pages)
- [x] **Enriching** datasets with additional metadata from detail pages (species, tissue type, disease state, technologies, etc.)
- [x] **Exporting** final metadata in structured formats (JSON, Excel)
- [ ] **Downloading** generating curl/wget scripts for bulk dataset retrieval (microscopy images, CytAssist files, binned or spatial outputs, etc.)

## Architecture

```
10XGenomics_scraper/
├── orchestrator.py              # Master pipeline controller
├── config.yml                   # Pipeline configuration
├── environment.yml              # Conda environment
├── README.md                    # This file
├── mcp-servers/                 # MCP (Model Context Protocol) servers
│   ├── 10x-scraper/            # Scraper MCP server
│   ├── 10x-validator/          # Validator MCP server
│   ├── 10x-enricher/           # Enricher MCP server
│   ├── mcp-config.json         # MCP configuration template
│   ├── requirements.txt        # MCP dependencies
│   └── README.md               # MCP integration guide
├── skills/
│   ├── scraper/
│   │   ├── SKILL.md            # Scraper agent documentation
│   │   ├── scraper.py          # Web scraping script
│   │   ├── input/              # Source URLs and raw HTML
│   │   └── output/             # Scraped data (JSON + Excel)
│   ├── validator/
│   │   ├── SKILL.md            # Validator agent documentation
│   │   ├── validator.py        # Validation script
│   │   └── reports/            # Validation reports
│   └── metadata_enricher/
│       ├── SKILL.md            # Enricher agent documentation
│       ├── metadata_enricher.py # Metadata enrichment script
│       └── enriched/           # Enriched data outputs
└── logs/                        # Pipeline execution logs
```

**See [mcp-servers/README.md](mcp-servers/README.md) for full MCP integration guide.**

## Installation

```bash
# Create and activate environment
micromamba env create -f environment.yml
micromamba activate 10XGenomics_scraper
```

The skills use Selenium with ChromeDriver. Make sure you have Google Chrome or Chromium installed.  
Tested in MacOS using Chrome (Version 141.0.7390.123).
```bash
# Check if Chrome is installed
ls -la "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# Or try to get version (may not work from terminal, but app should exist)
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --version
```



## Usage

### Command Line Interface

**Run Full Pipeline**

```bash
# Run scraper, validator, and enricher
python orchestrator.py \
    --url "<Datasets_URL>" \
    --name "<Search_Name>"
```

**Example:**
```bash
python orchestrator.py \
    --url "https://www.10xgenomics.com/datasets?query=Visium%20HD&refinementList[species][0]=Human" \
    --name "10XGenomics-VisiumHD-Human"
```

This will:
1. Scrape datasets from 10X Genomics website
2. Save outputs to `output/<Search_Name>/output/`
3. Validate file consistency (JSON vs Excel)
4. Validate URL content (scraped vs actual)
5. Generate validation reports in `output/<Search_Name>/reports/`
6. Enrich metadata from dataset detail pages
7. Save enriched data to `output/<Search_Name>/enriched/`
8. Save execution logs to `logs/`

**Notes:**
- You can use skip flags like `--skip-scraper`, `--skip-validator`, `--skip-enricher` to skip specific agents.
- Alternatively, you can use `config.yml` to configure the orchestrator parameters.

### MCP Integration

Use natural language with Claude Code to control the pipeline:

```bash
# After setting up MCP servers (see mcp-servers/README.md)
# Start Claude Code and interact naturally:

User: "Scrape Visium HD datasets for human samples from 10X Genomics"
Claude: [Automatically uses the scraper tool]

User: "Now validate the data"
Claude: [Runs validation and shows results]

User: "Enrich the metadata"
Claude: [Enriches datasets with additional metadata]
```

**Setup:** See [mcp-servers/README.md](mcp-servers/README.md) for complete installation and usage guide.

## Development Notes

🤖 The initial SKILL.md files were manually written, while all data scraping scripts were generated using Claude Code (2.0.31). Scripts have been reviewed and tested against various 10X Genomics dataset pages to verify they meet the objectives.

> **TODO:** For now, I'm learning and demonstrating Claude Skills and MCP capabilities through real-world data/metadata scraping of 10X Genomics spatial transcriptomics data. Future plans include integrating ST and pathology data processing and analysis pipelines into the Skills/MCP framework.