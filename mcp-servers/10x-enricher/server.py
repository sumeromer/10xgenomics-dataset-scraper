#!/usr/bin/env python3
"""
10X Genomics Metadata Enricher MCP Server

Exposes the metadata enricher as MCP tools for Claude Code.
"""

import json
import sys
import subprocess
from pathlib import Path
from typing import Optional
from mcp.server.fastmcp import FastMCP

# Initialize MCP server
mcp = FastMCP("10x-genomics-enricher")

# Base paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
ENRICHER_SCRIPT = PROJECT_ROOT / "skills" / "metadata_enricher" / "metadata_enricher.py"


@mcp.tool()
def enrich_metadata(
    name: str,
    base_output_dir: Optional[str] = None
) -> dict:
    """
    Enrich dataset metadata by extracting additional information from detail pages.

    This tool runs the metadata enricher agent which:
    1. Reads validated scraper output
    2. Visits each dataset detail page
    3. Extracts imaging metadata (microscope, camera, magnification, etc.)
    4. Extracts sample information (anatomy, disease state, preservation, etc.)
    5. Saves enriched data with all additional fields

    Args:
        name: Run identifier for the scraping run to enrich
        base_output_dir: Base output directory (default: PROJECT_ROOT/output)

    Returns:
        dict with keys:
            - status: "success", "partial", or "failed"
            - exit_code: Process exit code
            - enrichment_summary: Summary of enrichment results
            - output_files: Paths to enriched data files
            - message: Status message
            - stderr: Error output (if any)

    Example:
        result = enrich_metadata(name="10XGenomics-VisiumHD-Human")
    """
    if base_output_dir is None:
        base_output_dir = str(PROJECT_ROOT / "output")

    # Prepare command
    cmd = [
        sys.executable,
        str(ENRICHER_SCRIPT),
        "--name", name,
        "--base-output-dir", base_output_dir
    ]

    # Execute enricher
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(ENRICHER_SCRIPT.parent)
    )

    # Parse results
    enriched_dir = Path(base_output_dir) / name / "enriched"

    response = {
        "status": "success" if result.returncode == 0 else "partial" if result.returncode == 1 else "failed",
        "exit_code": result.returncode,
        "enrichment_summary": {},
        "output_files": {},
        "message": "",
        "stderr": result.stderr
    }

    # Find enriched output files
    if enriched_dir.exists():
        json_files = list(enriched_dir.glob("*-Enriched.json"))
        excel_files = list(enriched_dir.glob("*-Enriched.xlsx"))

        if json_files:
            json_file = json_files[0]
            response["output_files"]["json"] = str(json_file)

            try:
                data = json.loads(json_file.read_text())

                # Calculate field completion statistics
                if data:
                    field_stats = {}
                    for field in data[0].keys():
                        non_empty = sum(1 for d in data if d.get(field))
                        field_stats[field] = {
                            "filled": non_empty,
                            "total": len(data),
                            "completion_rate": round(non_empty / len(data) * 100, 1)
                        }

                    response["enrichment_summary"] = {
                        "total_datasets": len(data),
                        "field_completion": field_stats
                    }

                    response["message"] = f"Successfully enriched {len(data)} datasets"
                else:
                    response["message"] = "No datasets to enrich"

            except Exception as e:
                response["message"] = f"Failed to read enriched output: {str(e)}"

        if excel_files:
            response["output_files"]["excel"] = str(excel_files[0])
    else:
        response["message"] = f"No enriched output found for run '{name}'"

    return response


@mcp.tool()
def get_enriched_data(
    name: str,
    base_output_dir: Optional[str] = None,
    format: str = "json"
) -> dict:
    """
    Read enriched metadata from a previous enrichment run.

    Args:
        name: Run identifier
        base_output_dir: Base output directory (default: PROJECT_ROOT/output)
        format: Output format - "json", "summary", or "fields_only" (default: "json")

    Returns:
        dict with keys:
            - status: "success" or "not_found"
            - data: Enriched datasets or summary
            - output_files: Paths to output files

    Example:
        result = get_enriched_data(name="10XGenomics-VisiumHD-Human", format="summary")
    """
    if base_output_dir is None:
        base_output_dir = str(PROJECT_ROOT / "output")

    enriched_dir = Path(base_output_dir) / name / "enriched"

    if not enriched_dir.exists():
        return {
            "status": "not_found",
            "message": f"No enriched data found for run '{name}'",
            "expected_path": str(enriched_dir)
        }

    json_files = list(enriched_dir.glob("*-Enriched.json"))
    excel_files = list(enriched_dir.glob("*-Enriched.xlsx"))

    if not json_files:
        return {
            "status": "not_found",
            "message": f"No enriched JSON files found in {enriched_dir}"
        }

    json_file = json_files[0]

    try:
        data = json.loads(json_file.read_text())

        response = {
            "status": "success",
            "output_files": {
                "json": str(json_file),
                "excel": str(excel_files[0]) if excel_files else None
            }
        }

        if format == "json":
            response["data"] = data
        elif format == "summary":
            # Calculate field completion statistics
            if data:
                field_stats = {}
                for field in data[0].keys():
                    non_empty = sum(1 for d in data if d.get(field))
                    field_stats[field] = {
                        "filled": non_empty,
                        "total": len(data),
                        "completion_rate": round(non_empty / len(data) * 100, 1)
                    }

                response["data"] = {
                    "total_datasets": len(data),
                    "available_fields": list(data[0].keys()),
                    "field_completion": field_stats
                }
            else:
                response["data"] = {"total_datasets": 0}
        elif format == "fields_only":
            # Return just the list of available fields
            if data:
                response["data"] = {
                    "available_fields": list(data[0].keys()),
                    "original_fields": [
                        "dataset_name", "dataset_url", "product",
                        "species", "sample_type", "cells_or_nuclei", "preservation"
                    ],
                    "enriched_fields": [
                        k for k in data[0].keys()
                        if k not in ["dataset_name", "dataset_url", "product",
                                     "species", "sample_type", "cells_or_nuclei", "preservation"]
                    ]
                }
            else:
                response["data"] = {"available_fields": []}

        return response

    except Exception as e:
        return {
            "status": "failed",
            "message": f"Failed to read enriched data: {str(e)}"
        }


@mcp.tool()
def check_enrichment_status(
    name: str,
    base_output_dir: Optional[str] = None
) -> dict:
    """
    Check if metadata enrichment has been completed for a given run.

    Args:
        name: Run identifier to check
        base_output_dir: Base output directory (default: PROJECT_ROOT/output)

    Returns:
        dict with keys:
            - completed: Boolean indicating if enrichment is complete
            - output_files: Dict of output file paths and their existence status
            - datasets_count: Number of enriched datasets (if completed)

    Example:
        status = check_enrichment_status(name="10XGenomics-VisiumHD-Human")
    """
    if base_output_dir is None:
        base_output_dir = str(PROJECT_ROOT / "output")

    enriched_dir = Path(base_output_dir) / name / "enriched"

    if not enriched_dir.exists():
        return {
            "completed": False,
            "output_files": {},
            "message": "Enrichment not started"
        }

    json_files = list(enriched_dir.glob("*-Enriched.json"))
    excel_files = list(enriched_dir.glob("*-Enriched.xlsx"))

    output_files = {
        "json": [str(f) for f in json_files],
        "excel": [str(f) for f in excel_files]
    }

    completed = len(json_files) > 0

    response = {
        "completed": completed,
        "output_files": output_files
    }

    if completed and json_files:
        try:
            data = json.loads(json_files[0].read_text())
            response["datasets_count"] = len(data)
        except Exception:
            response["datasets_count"] = None

    return response


@mcp.tool()
def get_field_statistics(
    name: str,
    base_output_dir: Optional[str] = None,
    field_name: Optional[str] = None
) -> dict:
    """
    Get detailed statistics about enriched fields.

    Args:
        name: Run identifier
        base_output_dir: Base output directory (default: PROJECT_ROOT/output)
        field_name: Specific field to analyze (optional, returns stats for all fields if not specified)

    Returns:
        dict with field statistics including:
            - completion_rate: Percentage of datasets with this field filled
            - unique_values: List of unique values (for categorical fields)
            - value_distribution: Count of each unique value

    Example:
        stats = get_field_statistics(name="10XGenomics-VisiumHD-Human", field_name="microscope")
    """
    if base_output_dir is None:
        base_output_dir = str(PROJECT_ROOT / "output")

    enriched_dir = Path(base_output_dir) / name / "enriched"
    json_files = list(enriched_dir.glob("*-Enriched.json"))

    if not json_files:
        return {
            "status": "not_found",
            "message": f"No enriched data found for run '{name}'"
        }

    try:
        data = json.loads(json_files[0].read_text())

        if not data:
            return {
                "status": "success",
                "message": "No datasets to analyze"
            }

        def analyze_field(field):
            values = [d.get(field, "") for d in data]
            non_empty = [v for v in values if v]

            stats = {
                "total": len(data),
                "filled": len(non_empty),
                "completion_rate": round(len(non_empty) / len(data) * 100, 1)
            }

            # Add value distribution for categorical fields
            if non_empty:
                from collections import Counter
                value_counts = Counter(non_empty)
                stats["unique_values_count"] = len(value_counts)
                stats["value_distribution"] = dict(value_counts)

            return stats

        if field_name:
            if field_name not in data[0]:
                return {
                    "status": "not_found",
                    "message": f"Field '{field_name}' not found in enriched data",
                    "available_fields": list(data[0].keys())
                }

            return {
                "status": "success",
                "field": field_name,
                "statistics": analyze_field(field_name)
            }
        else:
            # Analyze all fields
            field_stats = {
                field: analyze_field(field)
                for field in data[0].keys()
            }

            return {
                "status": "success",
                "total_datasets": len(data),
                "field_statistics": field_stats
            }

    except Exception as e:
        return {
            "status": "failed",
            "message": f"Failed to analyze field statistics: {str(e)}"
        }


if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
