#!/usr/bin/env python3
"""
10X Genomics Scraper MCP Server

Exposes the 10X Genomics dataset scraper as MCP tools for Claude Code.
"""

import json
import sys
import subprocess
from pathlib import Path
from typing import Optional
from mcp.server.fastmcp import FastMCP

# Initialize MCP server
mcp = FastMCP("10x-genomics-scraper")

# Base paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
SCRAPER_SCRIPT = PROJECT_ROOT / "skills" / "scraper" / "scraper.py"


@mcp.tool()
def scrape_datasets(
    url: str,
    name: str,
    base_output_dir: Optional[str] = None
) -> dict:
    """
    Scrape 10X Genomics datasets from a given URL.

    This tool launches the scraper agent to extract dataset information from
    the 10X Genomics website. It uses browser automation to handle dynamic
    JavaScript content.

    Args:
        url: Source URL to scrape (e.g., filtered datasets page from 10xgenomics.com)
        name: Human-readable identifier for this scraping run (e.g., "10XGenomics-VisiumHD-Human")
        base_output_dir: Base output directory (default: PROJECT_ROOT/output)

    Returns:
        dict with keys:
            - status: "success" or "failed"
            - exit_code: Process exit code
            - datasets_count: Number of datasets scraped
            - output_files: Paths to generated files
            - message: Status message
            - stderr: Error output (if any)

    Example:
        result = scrape_datasets(
            url="https://www.10xgenomics.com/datasets?query=Visium%20HD",
            name="10XGenomics-VisiumHD-Human"
        )
    """
    if base_output_dir is None:
        base_output_dir = str(PROJECT_ROOT / "output")

    # Prepare command
    cmd = [
        sys.executable,
        str(SCRAPER_SCRIPT),
        "--url", url,
        "--name", name,
        "--base-output-dir", base_output_dir
    ]

    # Execute scraper
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(SCRAPER_SCRIPT.parent)
    )

    # Parse results
    output_dir = Path(base_output_dir) / name / "output"
    json_file = output_dir / f"Data-{name}.json"
    excel_file = output_dir / f"Data-{name}.xlsx"

    response = {
        "status": "success" if result.returncode == 0 else "failed",
        "exit_code": result.returncode,
        "datasets_count": 0,
        "output_files": {},
        "message": "",
        "stderr": result.stderr
    }

    # Load scraped data if successful
    if result.returncode == 0 and json_file.exists():
        try:
            data = json.loads(json_file.read_text())
            response["datasets_count"] = len(data)
            response["output_files"] = {
                "json": str(json_file),
                "excel": str(excel_file) if excel_file.exists() else None
            }
            response["message"] = f"Successfully scraped {len(data)} datasets"
        except Exception as e:
            response["status"] = "failed"
            response["message"] = f"Failed to read output: {str(e)}"
    else:
        response["message"] = f"Scraping failed with exit code {result.returncode}"

    return response


@mcp.tool()
def get_scraper_output(
    name: str,
    base_output_dir: Optional[str] = None,
    format: str = "json"
) -> dict:
    """
    Read the output from a previous scraping run.

    Args:
        name: Run identifier used during scraping
        base_output_dir: Base output directory (default: PROJECT_ROOT/output)
        format: Output format to read - "json" or "summary" (default: "json")

    Returns:
        dict with keys:
            - status: "success" or "not_found"
            - data: Scraped datasets (if format="json") or summary (if format="summary")
            - output_files: Paths to output files

    Example:
        result = get_scraper_output(name="10XGenomics-VisiumHD-Human")
    """
    if base_output_dir is None:
        base_output_dir = str(PROJECT_ROOT / "output")

    output_dir = Path(base_output_dir) / name / "output"
    json_file = output_dir / f"Data-{name}.json"
    excel_file = output_dir / f"Data-{name}.xlsx"

    if not json_file.exists():
        return {
            "status": "not_found",
            "message": f"No scraper output found for run '{name}'",
            "expected_path": str(json_file)
        }

    try:
        data = json.loads(json_file.read_text())

        response = {
            "status": "success",
            "output_files": {
                "json": str(json_file),
                "excel": str(excel_file) if excel_file.exists() else None
            }
        }

        if format == "json":
            response["data"] = data
        elif format == "summary":
            # Create summary statistics
            species = set(d.get("species", "Unknown") for d in data)
            products = set(d.get("product", "Unknown") for d in data)
            sample_types = set(d.get("sample_type", "Unknown") for d in data)

            response["data"] = {
                "total_datasets": len(data),
                "species": list(species),
                "products": list(products),
                "sample_types": list(sample_types)
            }

        return response

    except Exception as e:
        return {
            "status": "failed",
            "message": f"Failed to read output: {str(e)}"
        }


@mcp.tool()
def check_scraper_status(
    name: str,
    base_output_dir: Optional[str] = None
) -> dict:
    """
    Check if scraping has been completed for a given run.

    Args:
        name: Run identifier to check
        base_output_dir: Base output directory (default: PROJECT_ROOT/output)

    Returns:
        dict with keys:
            - completed: Boolean indicating if scraping is complete
            - output_files: Dict of output file paths and their existence status
            - datasets_count: Number of datasets (if completed)

    Example:
        status = check_scraper_status(name="10XGenomics-VisiumHD-Human")
    """
    if base_output_dir is None:
        base_output_dir = str(PROJECT_ROOT / "output")

    output_dir = Path(base_output_dir) / name / "output"
    input_dir = Path(base_output_dir) / name / "input"

    json_file = output_dir / f"Data-{name}.json"
    excel_file = output_dir / f"Data-{name}.xlsx"
    url_file = input_dir / f"URL-{name}.txt"
    html_file = input_dir / f"RawData-{name}.html"

    output_files = {
        "json": {"path": str(json_file), "exists": json_file.exists()},
        "excel": {"path": str(excel_file), "exists": excel_file.exists()},
        "url": {"path": str(url_file), "exists": url_file.exists()},
        "html": {"path": str(html_file), "exists": html_file.exists()}
    }

    completed = json_file.exists() and excel_file.exists()

    response = {
        "completed": completed,
        "output_files": output_files
    }

    if completed:
        try:
            data = json.loads(json_file.read_text())
            response["datasets_count"] = len(data)
        except Exception:
            response["datasets_count"] = None

    return response


if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
