# 10X Genomics MCP Servers

This directory contains MCP (Model Context Protocol) servers that expose the 10X Genomics scraper skills as tools for Claude Code and other MCP-compatible clients.

## Overview

The MCP integration allows you to interact with the scraper, validator, and enricher skills through natural language via Claude Code, rather than running command-line scripts directly.

### Available MCP Servers

1. **10x-genomics-scraper** - Scrapes 10X Genomics dataset metadata
2. **10x-genomics-validator** - Validates scraped data accuracy
3. **10x-genomics-enricher** - Enriches datasets with additional metadata

## Installation

### Prerequisites

- Python 3.12+ (already installed if using the project micromamba/conda environment)
- Claude Code CLI or another MCP-compatible client
- All project dependencies installed (`micromamba activate 10XGenomics_scraper`)

### Step 1: Install MCP Dependencies

```bash
# Activate your micromamba environment
micromamba activate 10XGenomics_scraper

# Install FastMCP
pip install -r mcp-servers/requirements.txt
```

### Step 2: Configure Claude Code

Add the MCP servers to your Claude Code configuration file:

**Location:** `~/.config/claude-code/mcp_settings.json`

**Method 1: Copy from template**
```bash
# Edit the mcp-config.json to use absolute paths for your system
# Then merge with your existing MCP settings
cat mcp-servers/mcp-config.json
```

**Method 2: Manual configuration**

Add the following to your `~/.config/claude-code/mcp_settings.json`:

```json
{
  "mcpServers": {
    "10x-genomics-scraper": {
      "command": "python",
      "args": [
        "/ABSOLUTE/PATH/TO/10XGenomics_scraper/mcp-servers/10x-scraper/server.py"
      ],
      "description": "10X Genomics dataset scraper"
    },
    "10x-genomics-validator": {
      "command": "python",
      "args": [
        "/ABSOLUTE/PATH/TO/10XGenomics_scraper/mcp-servers/10x-validator/server.py"
      ],
      "description": "10X Genomics data validator"
    },
    "10x-genomics-enricher": {
      "command": "python",
      "args": [
        "/ABSOLUTE/PATH/TO/10XGenomics_scraper/mcp-servers/10x-enricher/server.py"
      ],
      "description": "10X Genomics metadata enricher"
    }
  }
}
```

**Important:** Replace `/ABSOLUTE/PATH/TO/` with the actual path to your project directory.

### Step 3: Restart Claude Code

```bash
# If Claude Code is running, restart it to load the new MCP servers
# The MCP servers will appear as available tools
```

## Available Tools

### Scraper Server Tools

#### `scrape_datasets`
Scrapes 10X Genomics datasets from a URL.

**Parameters:**
- `url` (string, required): Source URL to scrape
- `name` (string, required): Run identifier (e.g., "10XGenomics-VisiumHD-Human")
- `base_output_dir` (string, optional): Output directory (default: ./output)

**Returns:**
- `status`: "success" or "failed"
- `exit_code`: Process exit code
- `datasets_count`: Number of datasets scraped
- `output_files`: Paths to JSON and Excel files

#### `get_scraper_output`
Reads output from a previous scraping run.

**Parameters:**
- `name` (string, required): Run identifier
- `base_output_dir` (string, optional): Output directory
- `format` (string, optional): "json" or "summary" (default: "json")

#### `check_scraper_status`
Checks if scraping has completed.

**Parameters:**
- `name` (string, required): Run identifier
- `base_output_dir` (string, optional): Output directory

---

### Validator Server Tools

#### `validate_datasets`
Validates scraped data for accuracy.

**Parameters:**
- `name` (string, required): Run identifier to validate
- `base_output_dir` (string, optional): Output directory

**Returns:**
- `status`: "success", "warnings", or "failed"
- `exit_code`: Process exit code
- `validation_summary`: Summary of validation results
- `report_files`: Paths to validation reports

#### `get_validation_report`
Reads validation report.

**Parameters:**
- `name` (string, required): Run identifier
- `base_output_dir` (string, optional): Output directory
- `format` (string, optional): "summary", "full", or "issues_only" (default: "summary")

#### `check_validation_status`
Checks if validation has completed.

**Parameters:**
- `name` (string, required): Run identifier
- `base_output_dir` (string, optional): Output directory

---

### Enricher Server Tools

#### `enrich_metadata`
Enriches datasets with additional metadata.

**Parameters:**
- `name` (string, required): Run identifier to enrich
- `base_output_dir` (string, optional): Output directory

**Returns:**
- `status`: "success", "partial", or "failed"
- `exit_code`: Process exit code
- `enrichment_summary`: Field completion statistics
- `output_files`: Paths to enriched data files

#### `get_enriched_data`
Reads enriched metadata.

**Parameters:**
- `name` (string, required): Run identifier
- `base_output_dir` (string, optional): Output directory
- `format` (string, optional): "json", "summary", or "fields_only" (default: "json")

#### `check_enrichment_status`
Checks if enrichment has completed.

**Parameters:**
- `name` (string, required): Run identifier
- `base_output_dir` (string, optional): Output directory

#### `get_field_statistics`
Gets statistics about enriched fields.

**Parameters:**
- `name` (string, required): Run identifier
- `base_output_dir` (string, optional): Output directory
- `field_name` (string, optional): Specific field to analyze (returns all if not specified)

## Usage Examples

### Example 1: Complete Pipeline via Natural Language

```
User: "Scrape Visium HD datasets for human samples from 10X Genomics"

Claude: I'll scrape the datasets for you using the 10X Genomics scraper tool.

[Calls: scrape_datasets(
    url="https://www.10xgenomics.com/datasets?query=Visium%20HD&refinementList[species][0]=Human",
    name="10XGenomics-VisiumHD-Human"
)]

Result: Successfully scraped 19 datasets

User: "Now validate the data"

Claude: I'll validate the scraped datasets.

[Calls: validate_datasets(name="10XGenomics-VisiumHD-Human")]

Result: All 19 datasets validated successfully

User: "Enrich the metadata"

Claude: I'll enrich the datasets with additional metadata.

[Calls: enrich_metadata(name="10XGenomics-VisiumHD-Human")]

Result: Successfully enriched 19 datasets with imaging and sample metadata
```

### Example 2: Check Status and Read Results

```
User: "Check if the enrichment for 10XGenomics-VisiumHD-Human is complete"

Claude: [Calls: check_enrichment_status(name="10XGenomics-VisiumHD-Human")]

Result: Enrichment is complete. Found 19 enriched datasets.

User: "Show me field completion statistics"

Claude: [Calls: get_field_statistics(name="10XGenomics-VisiumHD-Human")]

Result:
- microscope: 85% complete (16/19 datasets)
- camera: 90% complete (17/19 datasets)
- anatomical_entity: 100% complete (19/19 datasets)
- disease_state: 95% complete (18/19 datasets)
[... more fields ...]
```

### Example 3: Targeted Analysis

```
User: "What microscopes were used in the 10XGenomics-VisiumHD-Human datasets?"

Claude: Let me check the microscope field statistics.

[Calls: get_field_statistics(
    name="10XGenomics-VisiumHD-Human",
    field_name="microscope"
)]

Result: Microscope distribution:
- Zeiss Axio Scan.Z1: 8 datasets
- Leica Aperio GT 450: 6 datasets
- Olympus VS200: 2 datasets
- Empty: 3 datasets
```

### Example 4: Review Validation Issues

```
User: "Were there any validation issues with the scraped data?"

Claude: Let me check the validation report.

[Calls: get_validation_report(
    name="10XGenomics-VisiumHD-Human",
    format="issues_only"
)]

Result: Found 1 warning - dataset "Pancreas FFPE" has minor field mismatches
in preservation method (scraped: "FFPE", actual page: "ffpe"). All other
datasets validated successfully.
```

## Advantages of MCP Integration

### 1. **Natural Language Interface**
- No need to remember CLI syntax
- Describe what you want in plain English
- Claude understands context and can chain operations

### 2. **Interactive Debugging**
- Claude can analyze validation failures
- Ask follow-up questions about results
- Get explanations of the data

### 3. **Intelligent Orchestration**
- Claude decides when to run each tool
- Handles error cases gracefully
- Can retry with different parameters

### 4. **Context Awareness**
- Claude remembers previous results in the conversation
- Can compare multiple runs
- Provides insights and recommendations

### 5. **Extensibility**
- Easy to add new tools by adding functions to server.py
- No changes needed to client code
- Works with any MCP-compatible client

## Comparison: CLI vs MCP

### Traditional CLI Approach
```bash
# Manual command execution
python orchestrator.py \
  --url "https://www.10xgenomics.com/datasets?query=Visium%20HD" \
  --name "10XGenomics-VisiumHD-Human"

# Wait for completion...

# Check results manually
cat output/10XGenomics-VisiumHD-Human/output/Data-10XGenomics-VisiumHD-Human.json

# If there's an issue, manually investigate
python skills/validator/validator.py --name "10XGenomics-VisiumHD-Human"
```

### MCP Approach
```
User: "Scrape and validate Visium HD human datasets from 10X Genomics"

Claude: I'll handle that for you. Let me scrape the data first, then validate it.
[Automatically runs scraper, checks results, runs validator, interprets findings]

Result: Scraped 19 datasets, all validated successfully. Would you like me to
enrich the metadata as well?
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│ Claude Code CLI (User Interface)                        │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│ MCP Client (Built into Claude Code)                     │
│ - Discovers available MCP servers                       │
│ - Routes tool calls to appropriate servers              │
└─────────────────────────────────────────────────────────┘
                          ↓
        ┌─────────────────┼─────────────────┐
        ↓                 ↓                 ↓
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ 10x-scraper  │  │ 10x-validator│  │ 10x-enricher │
│ MCP Server   │  │ MCP Server   │  │ MCP Server   │
│              │  │              │  │              │
│ Tools:       │  │ Tools:       │  │ Tools:       │
│ - scrape     │  │ - validate   │  │ - enrich     │
│ - get_output │  │ - get_report │  │ - get_data   │
│ - check      │  │ - check      │  │ - check      │
└──────────────┘  └──────────────┘  └──────────────┘
        ↓                 ↓                 ↓
┌─────────────────────────────────────────────────────────┐
│ Skills (subprocess execution)                           │
│ - skills/scraper/scraper.py                            │
│ - skills/validator/validator.py                        │
│ - skills/metadata_enricher/metadata_enricher.py        │
└─────────────────────────────────────────────────────────┘
```

## Troubleshooting

### MCP Servers Not Appearing in Claude Code

1. Check that MCP configuration file exists: `~/.config/claude-code/mcp_settings.json`
2. Verify absolute paths in the configuration are correct
3. Restart Claude Code CLI
4. Check Claude Code logs: `~/.config/claude-code/logs/`

### Tool Execution Fails

1. Verify conda environment is activated: `conda activate 10XGenomics_scraper`
2. Check that all project dependencies are installed
3. Verify file paths in error messages
4. Check that the skill scripts are executable

### FastMCP Import Error

```bash
# Ensure FastMCP is installed in your micromamba environment
micromamba activate 10XGenomics_scraper
pip install fastmcp
```

## Development

### Adding New Tools

To add a new tool to an existing MCP server:

1. Open the appropriate server file (e.g., `10x-scraper/server.py`)
2. Add a new function decorated with `@mcp.tool()`
3. Restart Claude Code to pick up the changes

Example:
```python
@mcp.tool()
def my_new_tool(param1: str, param2: int) -> dict:
    """
    Description of what this tool does.

    Args:
        param1: Description of param1
        param2: Description of param2

    Returns:
        dict with results
    """
    # Implementation here
    return {"status": "success", "result": ...}
```

### Creating a New MCP Server

1. Create a new directory in `mcp-servers/`
2. Create `server.py` with FastMCP initialization
3. Add tools using `@mcp.tool()` decorator
4. Update `mcp_settings.json` to include the new server
5. Restart Claude Code

## Additional Resources

- [MCP Documentation](https://modelcontextprotocol.io/)
- [FastMCP Documentation](https://github.com/jlowin/fastmcp)
- [Claude Code Documentation](https://docs.claude.com/claude-code)

## License

Same as the main project (see root LICENSE file).
