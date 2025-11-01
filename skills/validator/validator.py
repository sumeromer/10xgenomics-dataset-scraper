#!/usr/bin/env python3
"""
10X Genomics Data Validator

Validates scraped dataset information through:
1. File consistency checks (JSON vs Excel)
2. URL content validation (scraped data vs actual website)
"""

import json
import sys
import os
import argparse
from datetime import datetime
from pathlib import Path
import pandas as pd
from deepdiff import DeepDiff
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm


class DataValidator:
    """Main validator class for 10X Genomics dataset validation."""

    def __init__(self, json_path, excel_path, output_dir, max_retries=3, timeout=30):
        """
        Initialize the validator.

        Args:
            json_path: Path to JSON file
            excel_path: Path to Excel file
            output_dir: Directory for validation reports
            max_retries: Maximum retries for failed URLs
            timeout: Timeout for page loads in seconds
        """
        self.json_path = Path(json_path)
        self.excel_path = Path(excel_path)
        self.output_dir = Path(output_dir)
        self.max_retries = max_retries
        self.timeout = timeout
        self.timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Results storage
        self.results = {
            "validation_timestamp": datetime.now().isoformat(),
            "total_datasets": 0,
            "file_consistency": {},
            "url_validation": {},
            "exit_code": 0
        }

    def load_data(self):
        """Load JSON and Excel data."""
        print("Loading data files...", file=sys.stderr, flush=True)

        try:
            # Load JSON
            with open(self.json_path, 'r', encoding='utf-8') as f:
                self.json_data = json.load(f)
            print(f"✓ Loaded JSON: {len(self.json_data)} entries", file=sys.stderr, flush=True)

            # Load Excel (keep_default_na=False to preserve "N/A" as literal string)
            self.excel_data = pd.read_excel(self.excel_path, keep_default_na=False)
            print(f"✓ Loaded Excel: {len(self.excel_data)} rows", file=sys.stderr, flush=True)

            self.results["total_datasets"] = len(self.json_data)

            return True

        except Exception as e:
            print(f"✗ Error loading data files: {e}", file=sys.stderr)
            self.results["exit_code"] = 2
            return False

    def validate_file_consistency(self):
        """Validate that JSON and Excel files contain identical data."""
        print("\n" + "="*60, file=sys.stderr, flush=True)
        print("FILE CONSISTENCY VALIDATION", file=sys.stderr, flush=True)
        print("="*60, file=sys.stderr, flush=True)

        consistency_result = {
            "passed": True,
            "json_count": len(self.json_data),
            "excel_count": len(self.excel_data),
            "mismatches": []
        }

        # Check entry counts
        if len(self.json_data) != len(self.excel_data):
            consistency_result["passed"] = False
            consistency_result["mismatches"].append({
                "type": "count_mismatch",
                "message": f"Entry count mismatch: JSON has {len(self.json_data)}, Excel has {len(self.excel_data)}"
            })
            print(f"✗ Entry count mismatch", file=sys.stderr)
            self.results["file_consistency"] = consistency_result
            self.results["exit_code"] = 1
            return False

        # Convert Excel to list of dicts for comparison
        excel_list = self.excel_data.to_dict('records')

        # Compare each entry
        mismatches_found = False
        for idx, (json_entry, excel_entry) in enumerate(zip(self.json_data, excel_list)):
            # Convert Excel NaN to empty string for comparison
            excel_entry = {k: (v if pd.notna(v) else '') for k, v in excel_entry.items()}
            json_entry = {k: (v if v is not None else '') for k, v in json_entry.items()}

            # Compare using deepdiff
            diff = DeepDiff(json_entry, excel_entry, ignore_order=False)

            if diff:
                mismatches_found = True
                consistency_result["passed"] = False
                consistency_result["mismatches"].append({
                    "row": idx + 1,
                    "dataset_url": json_entry.get("dataset_url", "Unknown"),
                    "differences": str(diff)
                })
                print(f"✗ Row {idx + 1}: Mismatch found", file=sys.stderr)

        if not mismatches_found:
            print("✓ All entries match between JSON and Excel", file=sys.stderr)
        else:
            self.results["exit_code"] = 1

        self.results["file_consistency"] = consistency_result
        return not mismatches_found

    def setup_driver(self):
        """Setup Chrome driver for URL validation."""
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')

        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            return driver
        except Exception as e:
            tqdm.write(f"✗ Failed to setup Chrome driver: {e}", file=sys.stderr)
            return None

    def validate_single_url(self, dataset, driver=None):
        """
        Validate a single dataset URL.

        Args:
            dataset: Dictionary containing dataset information
            driver: Optional Selenium WebDriver instance (if None, creates new one)

        Returns:
            Dictionary with validation results
        """
        url = dataset.get("dataset_url", "")
        result = {
            "dataset_url": url,
            "dataset_name": dataset.get("dataset_name", ""),
            "status": "unknown",
            "differences": []
        }

        driver_created = False
        try:
            # Use provided driver or create a new one
            if driver is None:
                driver = self.setup_driver()
                driver_created = True

            if not driver:
                result["status"] = "failed"
                result["differences"].append("Could not initialize browser")
                return result

            # Navigate to URL
            driver.set_page_load_timeout(self.timeout)
            driver.get(url)

            # Wait for page to load
            wait = WebDriverWait(driver, 10)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

            # Extract actual data from page
            actual_data = self.extract_page_data(driver)

            # Compare scraped vs actual
            differences = self.compare_data(dataset, actual_data)

            if not differences:
                result["status"] = "verified"
            elif any(d["severity"] == "error" for d in differences):
                result["status"] = "mismatched"
            else:
                result["status"] = "warning"

            result["differences"] = differences

        except Exception as e:
            result["status"] = "failed"
            result["differences"].append({
                "field": "page_load",
                "severity": "error",
                "message": str(e)
            })

        finally:
            # Only quit if we created the driver
            if driver_created and driver:
                driver.quit()

        return result

    def extract_page_data(self, driver):
        """
        Extract dataset information from the page.

        Args:
            driver: Selenium WebDriver instance

        Returns:
            Dictionary with extracted data
        """
        data = {
            "dataset_name": "",
            "product": "",
            "species": "",
            "sample_type": "",
            "preservation": "",
            "cells_or_nuclei": ""
        }

        try:
            # Try to extract title/name
            try:
                title = driver.find_element(By.TAG_NAME, "h1").text.strip()
                data["dataset_name"] = title
            except:
                pass

            # Try to find metadata table or key-value pairs
            try:
                # Look for common patterns in 10X Genomics pages
                page_text = driver.find_element(By.TAG_NAME, "body").text.lower()

                # Species detection
                if "human" in page_text:
                    data["species"] = "Human"
                elif "mouse" in page_text:
                    data["species"] = "Mouse"

                # Preservation detection
                if "ffpe" in page_text:
                    data["preservation"] = "FFPE"
                elif "fresh frozen" in page_text:
                    data["preservation"] = "Fresh Frozen"
                elif "fixed frozen" in page_text:
                    data["preservation"] = "Fixed Frozen"

                # Sample type detection (look for tissue types)
                tissues = ["pancreas", "breast", "lung", "kidney", "liver", "brain",
                          "colon", "lymph node", "prostate", "skin"]
                for tissue in tissues:
                    if tissue in page_text:
                        data["sample_type"] = tissue.title()
                        break

            except:
                pass

        except Exception as e:
            tqdm.write(f"Warning: Could not extract all fields: {e}", file=sys.stderr)

        return data

    def compare_data(self, scraped, actual):
        """
        Compare scraped data with actual page data.

        Args:
            scraped: Scraped dataset dictionary
            actual: Actual data from page

        Returns:
            List of difference dictionaries
        """
        differences = []

        # Define comparison rules for each field
        comparisons = [
            ("species", "exact"),
            ("preservation", "normalized"),
            ("sample_type", "substring"),
            ("dataset_name", "case_insensitive")
        ]

        for field, method in comparisons:
            scraped_value = scraped.get(field, "").strip()
            actual_value = actual.get(field, "").strip()

            # Skip if actual value is empty (field not found on page)
            if not actual_value:
                continue

            mismatch = False

            if method == "exact":
                mismatch = scraped_value != actual_value
            elif method == "case_insensitive":
                mismatch = scraped_value.lower() != actual_value.lower()
            elif method == "normalized":
                # Normalize and compare
                scraped_norm = scraped_value.lower().replace(" ", "").replace("-", "")
                actual_norm = actual_value.lower().replace(" ", "").replace("-", "")
                mismatch = scraped_norm != actual_norm
            elif method == "substring":
                # Check if one is substring of other
                mismatch = not (scraped_value.lower() in actual_value.lower() or
                               actual_value.lower() in scraped_value.lower())

            if mismatch:
                differences.append({
                    "field": field,
                    "severity": "error" if method == "exact" else "warning",
                    "scraped_value": scraped_value,
                    "actual_value": actual_value
                })

        return differences

    def validate_urls(self, max_workers=5):
        """
        Validate all URLs from scraped data.

        Args:
            max_workers: Maximum number of concurrent validations
        """
        print("\n" + "="*60, file=sys.stderr, flush=True)
        print("URL CONTENT VALIDATION", file=sys.stderr, flush=True)
        print("="*60, file=sys.stderr, flush=True)

        url_results = {
            "verified": 0,
            "mismatched": 0,
            "warnings": 0,
            "failed_urls": 0,
            "results": []
        }

        total = len(self.json_data)
        print(f"Validating {total} URLs...", file=sys.stderr, flush=True)

        # Create progress bar immediately so it's visible during driver setup
        with tqdm(total=total, desc="Setting up browser", unit="url", file=sys.stderr) as pbar:
            # Create a single driver instance to reuse
            driver = self.setup_driver()
            if not driver:
                pbar.write("✗ Failed to setup Chrome driver, cannot proceed with URL validation")
                self.results["url_validation"] = url_results
                self.results["exit_code"] = 2
                return

            try:
                # Update progress bar description to show we're now validating
                pbar.set_description("Validating URLs")

                for idx, dataset in enumerate(self.json_data, 1):
                    dataset_name = dataset.get('dataset_name', 'Unknown')[:50]
                    pbar.set_postfix_str(f"{dataset_name}...")

                    result = self.validate_single_url(dataset, driver)
                    url_results["results"].append(result)

                    # Update counts and progress bar description
                    status_symbol = ""
                    if result["status"] == "verified":
                        url_results["verified"] += 1
                        status_symbol = "✓"
                    elif result["status"] == "mismatched":
                        url_results["mismatched"] += 1
                        status_symbol = "✗"
                        self.results["exit_code"] = 1
                    elif result["status"] == "warning":
                        url_results["warnings"] += 1
                        status_symbol = "⚠"
                    elif result["status"] == "failed":
                        url_results["failed_urls"] += 1
                        status_symbol = "✗"
                        self.results["exit_code"] = 1

                    pbar.set_description(f"Validating URLs [{status_symbol}]")
                    pbar.update(1)

            finally:
                # Clean up the driver
                if driver:
                    driver.quit()

        self.results["url_validation"] = url_results

        print(f"\nURL Validation Summary:", file=sys.stderr)
        print(f"  ✓ Verified: {url_results['verified']}", file=sys.stderr)
        print(f"  ✗ Mismatched: {url_results['mismatched']}", file=sys.stderr)
        print(f"  ⚠ Warnings: {url_results['warnings']}", file=sys.stderr)
        print(f"  ✗ Failed: {url_results['failed_urls']}", file=sys.stderr)

    def generate_reports(self):
        """Generate validation reports in JSON and HTML formats."""
        print("\n" + "="*60, file=sys.stderr)
        print("GENERATING REPORTS", file=sys.stderr)
        print("="*60, file=sys.stderr)

        # JSON report
        json_report_path = self.output_dir / f"validation_report_{self.timestamp}.json"
        with open(json_report_path, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        print(f"✓ JSON report: {json_report_path}", file=sys.stderr)

        # HTML report
        html_report_path = self.output_dir / f"validation_report_{self.timestamp}.html"
        html_content = self.generate_html_report()
        with open(html_report_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"✓ HTML report: {html_report_path}", file=sys.stderr)

    def generate_html_report(self):
        """Generate HTML validation report."""
        # Simple HTML template
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Validation Report - {self.timestamp}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; border-bottom: 3px solid #007bff; padding-bottom: 10px; }}
        h2 {{ color: #555; margin-top: 30px; }}
        .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }}
        .stat-card {{ background: #f8f9fa; padding: 15px; border-radius: 5px; border-left: 4px solid #007bff; }}
        .stat-card.success {{ border-left-color: #28a745; }}
        .stat-card.warning {{ border-left-color: #ffc107; }}
        .stat-card.error {{ border-left-color: #dc3545; }}
        .stat-value {{ font-size: 2em; font-weight: bold; margin: 10px 0; }}
        .stat-label {{ color: #666; font-size: 0.9em; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background-color: #007bff; color: white; }}
        tr:hover {{ background-color: #f5f5f5; }}
        .status-verified {{ color: #28a745; font-weight: bold; }}
        .status-mismatched {{ color: #dc3545; font-weight: bold; }}
        .status-warning {{ color: #ffc107; font-weight: bold; }}
        .status-failed {{ color: #6c757d; font-weight: bold; }}
        .diff {{ background: #fff3cd; padding: 5px; border-radius: 3px; margin: 2px 0; font-size: 0.9em; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>10X Genomics Data Validation Report</h1>
        <p><strong>Generated:</strong> {self.results['validation_timestamp']}</p>
        <p><strong>Total Datasets:</strong> {self.results['total_datasets']}</p>

        <h2>File Consistency Check</h2>
        <div class="summary">
            <div class="stat-card {'success' if self.results['file_consistency'].get('passed') else 'error'}">
                <div class="stat-label">Status</div>
                <div class="stat-value">{'✓ PASSED' if self.results['file_consistency'].get('passed') else '✗ FAILED'}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">JSON Entries</div>
                <div class="stat-value">{self.results['file_consistency'].get('json_count', 0)}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Excel Entries</div>
                <div class="stat-value">{self.results['file_consistency'].get('excel_count', 0)}</div>
            </div>
            <div class="stat-card {'success' if len(self.results['file_consistency'].get('mismatches', [])) == 0 else 'error'}">
                <div class="stat-label">Mismatches</div>
                <div class="stat-value">{len(self.results['file_consistency'].get('mismatches', []))}</div>
            </div>
        </div>

        <h2>URL Validation Summary</h2>
        <div class="summary">
            <div class="stat-card success">
                <div class="stat-label">✓ Verified</div>
                <div class="stat-value">{self.results['url_validation'].get('verified', 0)}</div>
            </div>
            <div class="stat-card error">
                <div class="stat-label">✗ Mismatched</div>
                <div class="stat-value">{self.results['url_validation'].get('mismatched', 0)}</div>
            </div>
            <div class="stat-card warning">
                <div class="stat-label">⚠ Warnings</div>
                <div class="stat-value">{self.results['url_validation'].get('warnings', 0)}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">✗ Failed URLs</div>
                <div class="stat-value">{self.results['url_validation'].get('failed_urls', 0)}</div>
            </div>
        </div>

        <h2>Detailed URL Validation Results</h2>
        <table>
            <thead>
                <tr>
                    <th>#</th>
                    <th>Dataset Name</th>
                    <th>Status</th>
                    <th>Differences</th>
                </tr>
            </thead>
            <tbody>
"""

        # Add URL validation results
        for idx, result in enumerate(self.results['url_validation'].get('results', []), 1):
            status_class = f"status-{result['status']}"
            status_icon = {"verified": "✓", "mismatched": "✗", "warning": "⚠", "failed": "✗"}.get(result['status'], "?")
            status_text = f"{status_icon} {result['status'].upper()}"

            diffs_html = ""
            if result['differences']:
                for diff in result['differences']:
                    if isinstance(diff, dict):
                        field = diff.get('field', 'unknown')
                        scraped = diff.get('scraped_value', '')
                        actual = diff.get('actual_value', '')
                        diffs_html += f'<div class="diff"><strong>{field}:</strong> "{scraped}" → "{actual}"</div>'
                    else:
                        diffs_html += f'<div class="diff">{diff}</div>'

            html += f"""
                <tr>
                    <td>{idx}</td>
                    <td><a href="{result['dataset_url']}" target="_blank">{result['dataset_name'][:60]}</a></td>
                    <td class="{status_class}">{status_text}</td>
                    <td>{diffs_html if diffs_html else '-'}</td>
                </tr>
"""

        html += """
            </tbody>
        </table>

        <h2>Exit Code</h2>
        <p><strong>Exit Code:</strong> <span style="font-size: 1.5em; color: """ + ("#28a745" if self.results['exit_code'] == 0 else "#dc3545") + f""";">{self.results['exit_code']}</span></p>
        <p>
            <strong>0</strong>: All validations passed<br>
            <strong>1</strong>: Validation failures detected<br>
            <strong>2</strong>: Critical error
        </p>
    </div>
</body>
</html>
"""
        return html


def main():
    """Main function to run the validator."""
    parser = argparse.ArgumentParser(description='Validate 10X Genomics scraped data')
    parser.add_argument('--name', type=str, required=True,
                       help='Run identifier (e.g., "10XGenomics-VisiumHD-Human")')
    parser.add_argument('--base-output-dir', type=str, default='../../output',
                       help='Base output directory (default: ../../output)')
    parser.add_argument('--skip-file-check', action='store_true',
                       help='Skip file consistency validation')
    parser.add_argument('--skip-url-check', action='store_true',
                       help='Skip URL content validation')
    parser.add_argument('--max-retries', type=int, default=3,
                       help='Max retries for failed URLs')
    parser.add_argument('--timeout', type=int, default=30,
                       help='Timeout for page loads in seconds')

    args = parser.parse_args()

    # Build paths based on name and base output directory
    script_dir = Path(__file__).parent
    base_dir = script_dir.parent.parent / args.base_output_dir
    run_dir = base_dir / args.name
    
    json_path = run_dir / 'output' / f'Data-{args.name}.json'
    excel_path = run_dir / 'output' / f'Data-{args.name}.xlsx'
    output_dir = run_dir / 'reports'

    print("="*60, file=sys.stderr, flush=True)
    print("10X GENOMICS DATA VALIDATOR", file=sys.stderr, flush=True)
    print("="*60, file=sys.stderr, flush=True)

    # Initialize validator
    validator = DataValidator(json_path, excel_path, output_dir, args.max_retries, args.timeout)

    # Load data
    if not validator.load_data():
        sys.exit(2)

    # Run validations
    if not args.skip_file_check:
        validator.validate_file_consistency()

    if not args.skip_url_check:
        validator.validate_urls()

    # Generate reports
    validator.generate_reports()

    # Print summary
    print("\n" + "="*60, file=sys.stderr)
    print("VALIDATION COMPLETE", file=sys.stderr)
    print("="*60, file=sys.stderr)
    print(f"Exit Code: {validator.results['exit_code']}", file=sys.stderr)

    if validator.results['exit_code'] == 0:
        print("✓ All validations passed!", file=sys.stderr)
    elif validator.results['exit_code'] == 1:
        print("✗ Validation failures detected. Check reports for details.", file=sys.stderr)
    else:
        print("✗ Critical error occurred.", file=sys.stderr)

    sys.exit(validator.results['exit_code'])


if __name__ == "__main__":
    main()
