#!/usr/bin/env python3
"""
10X Genomics Validator MCP Server

Exposes the data validator as MCP tools for Claude Code.
"""

import json
import sys
import subprocess
from pathlib import Path
from typing import Optional
from mcp.server.fastmcp import FastMCP

# Initialize MCP server
mcp = FastMCP("10x-genomics-validator")

# Base paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
VALIDATOR_SCRIPT = PROJECT_ROOT / "skills" / "validator" / "validator.py"


@mcp.tool()
def validate_datasets(
    name: str,
    base_output_dir: Optional[str] = None
) -> dict:
    """
    Validate scraped dataset data for accuracy and consistency.

    This tool runs the validator agent which:
    1. Checks consistency between JSON and Excel outputs
    2. Validates dataset URLs by visiting each page
    3. Compares scraped data against live page content
    4. Generates detailed validation reports

    Args:
        name: Run identifier for the scraping run to validate
        base_output_dir: Base output directory (default: PROJECT_ROOT/output)

    Returns:
        dict with keys:
            - status: "success", "warnings", or "failed"
            - exit_code: Process exit code
            - validation_summary: Summary of validation results
            - report_files: Paths to validation reports
            - message: Status message
            - stderr: Error output (if any)

    Example:
        result = validate_datasets(name="10XGenomics-VisiumHD-Human")
    """
    if base_output_dir is None:
        base_output_dir = str(PROJECT_ROOT / "output")

    # Prepare command
    cmd = [
        sys.executable,
        str(VALIDATOR_SCRIPT),
        "--name", name,
        "--base-output-dir", base_output_dir
    ]

    # Execute validator
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(VALIDATOR_SCRIPT.parent)
    )

    # Parse results
    reports_dir = Path(base_output_dir) / name / "reports"

    response = {
        "status": "success" if result.returncode == 0 else "warnings" if result.returncode == 1 else "failed",
        "exit_code": result.returncode,
        "validation_summary": {},
        "report_files": {},
        "message": "",
        "stderr": result.stderr
    }

    # Find the latest validation report
    if reports_dir.exists():
        json_reports = sorted(reports_dir.glob("validation_report_*.json"), reverse=True)
        html_reports = sorted(reports_dir.glob("validation_report_*.html"), reverse=True)

        if json_reports:
            report_file = json_reports[0]
            response["report_files"]["json"] = str(report_file)

            try:
                report_data = json.loads(report_file.read_text())
                response["validation_summary"] = {
                    "total_datasets": report_data.get("total_datasets", 0),
                    "file_consistency": report_data.get("file_consistency", {}),
                    "url_validation": {
                        "verified": report_data.get("url_validation", {}).get("verified", 0),
                        "mismatched": report_data.get("url_validation", {}).get("mismatched", 0),
                        "warnings": report_data.get("url_validation", {}).get("warnings", 0),
                        "failed_urls": report_data.get("url_validation", {}).get("failed_urls", 0)
                    }
                }

                # Set appropriate message
                if result.returncode == 0:
                    response["message"] = f"All {report_data.get('total_datasets', 0)} datasets validated successfully"
                elif result.returncode == 1:
                    warnings = report_data.get("url_validation", {}).get("warnings", 0)
                    mismatched = report_data.get("url_validation", {}).get("mismatched", 0)
                    response["message"] = f"Validation completed with {warnings} warnings and {mismatched} mismatches"
                else:
                    response["message"] = "Validation failed"

            except Exception as e:
                response["message"] = f"Failed to read validation report: {str(e)}"

        if html_reports:
            response["report_files"]["html"] = str(html_reports[0])
    else:
        response["message"] = f"No validation reports found for run '{name}'"

    return response


@mcp.tool()
def get_validation_report(
    name: str,
    base_output_dir: Optional[str] = None,
    format: str = "summary"
) -> dict:
    """
    Read the validation report from a previous validation run.

    Args:
        name: Run identifier
        base_output_dir: Base output directory (default: PROJECT_ROOT/output)
        format: Report format - "summary", "full", or "issues_only" (default: "summary")

    Returns:
        dict with keys:
            - status: "success" or "not_found"
            - report: Validation report data
            - report_files: Paths to report files

    Example:
        result = get_validation_report(name="10XGenomics-VisiumHD-Human", format="issues_only")
    """
    if base_output_dir is None:
        base_output_dir = str(PROJECT_ROOT / "output")

    reports_dir = Path(base_output_dir) / name / "reports"

    if not reports_dir.exists():
        return {
            "status": "not_found",
            "message": f"No validation reports found for run '{name}'",
            "expected_path": str(reports_dir)
        }

    # Find latest report
    json_reports = sorted(reports_dir.glob("validation_report_*.json"), reverse=True)
    html_reports = sorted(reports_dir.glob("validation_report_*.html"), reverse=True)

    if not json_reports:
        return {
            "status": "not_found",
            "message": f"No JSON validation reports found in {reports_dir}"
        }

    report_file = json_reports[0]

    try:
        report_data = json.loads(report_file.read_text())

        response = {
            "status": "success",
            "report_files": {
                "json": str(report_file),
                "html": str(html_reports[0]) if html_reports else None
            }
        }

        if format == "summary":
            response["report"] = {
                "validation_timestamp": report_data.get("validation_timestamp"),
                "total_datasets": report_data.get("total_datasets", 0),
                "file_consistency": report_data.get("file_consistency", {}),
                "url_validation_summary": {
                    "verified": report_data.get("url_validation", {}).get("verified", 0),
                    "mismatched": report_data.get("url_validation", {}).get("mismatched", 0),
                    "warnings": report_data.get("url_validation", {}).get("warnings", 0),
                    "failed_urls": report_data.get("url_validation", {}).get("failed_urls", 0)
                }
            }
        elif format == "full":
            response["report"] = report_data
        elif format == "issues_only":
            # Extract only problematic entries
            issues = []
            for result in report_data.get("url_validation", {}).get("results", []):
                if result.get("status") in ["mismatched", "warning", "failed"]:
                    issues.append(result)

            response["report"] = {
                "total_issues": len(issues),
                "file_consistency_passed": report_data.get("file_consistency", {}).get("passed", True),
                "issues": issues
            }

        return response

    except Exception as e:
        return {
            "status": "failed",
            "message": f"Failed to read validation report: {str(e)}"
        }


@mcp.tool()
def check_validation_status(
    name: str,
    base_output_dir: Optional[str] = None
) -> dict:
    """
    Check if validation has been completed for a given run.

    Args:
        name: Run identifier to check
        base_output_dir: Base output directory (default: PROJECT_ROOT/output)

    Returns:
        dict with keys:
            - completed: Boolean indicating if validation is complete
            - report_files: List of report files found
            - latest_report: Path to latest report (if any)

    Example:
        status = check_validation_status(name="10XGenomics-VisiumHD-Human")
    """
    if base_output_dir is None:
        base_output_dir = str(PROJECT_ROOT / "output")

    reports_dir = Path(base_output_dir) / name / "reports"

    if not reports_dir.exists():
        return {
            "completed": False,
            "report_files": [],
            "message": "Validation not started"
        }

    json_reports = sorted(reports_dir.glob("validation_report_*.json"), reverse=True)
    html_reports = sorted(reports_dir.glob("validation_report_*.html"), reverse=True)

    return {
        "completed": len(json_reports) > 0,
        "report_files": {
            "json": [str(f) for f in json_reports],
            "html": [str(f) for f in html_reports]
        },
        "latest_report": str(json_reports[0]) if json_reports else None
    }


if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
