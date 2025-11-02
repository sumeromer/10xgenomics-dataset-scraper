#!/usr/bin/env python3
"""
10X Genomics File Extractor

Extracts file download information (URLs, sizes, MD5 checksums) from dataset pages
and adds them to enriched dataset records.
"""

import json
import sys
import os
import argparse
import re
from datetime import datetime
from pathlib import Path
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
from tqdm import tqdm


class FileExtractor:
    """Extracts file download information from dataset detail pages."""

    def __init__(self, json_path, excel_path, max_retries=3, timeout=30):
        """
        Initialize the file extractor.

        Args:
            json_path: Path to enriched JSON file
            excel_path: Path to enriched Excel file
            max_retries: Maximum retries for failed page loads
            timeout: Timeout for page loads in seconds
        """
        self.json_path = Path(json_path)
        self.excel_path = Path(excel_path)
        self.max_retries = max_retries
        self.timeout = timeout

        # Statistics
        self.stats = {
            "total_datasets": 0,
            "successful": 0,
            "partial": 0,
            "failed": 0,
            "total_files_extracted": 0,
            "microscope_images_found": 0,
            "binned_outputs_found": 0
        }

    def load_input_data(self):
        """Load enriched JSON and Excel data."""
        print("Loading enriched data files...", file=sys.stderr, flush=True)

        try:
            # Load JSON
            with open(self.json_path, 'r', encoding='utf-8') as f:
                self.json_data = json.load(f)
            print(f"✓ Loaded JSON: {len(self.json_data)} entries", file=sys.stderr, flush=True)

            # Load Excel
            self.excel_data = pd.read_excel(self.excel_path, keep_default_na=False)
            print(f"✓ Loaded Excel: {len(self.excel_data)} rows", file=sys.stderr, flush=True)

            self.stats["total_datasets"] = len(self.json_data)

            return True

        except Exception as e:
            print(f"✗ Error loading data files: {e}", file=sys.stderr)
            return False

    def setup_driver(self):
        """Setup Chrome driver for web scraping."""
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')

        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            return driver
        except Exception as e:
            tqdm.write(f"✗ Failed to setup Chrome driver: {e}", file=sys.stderr)
            return None

    def extract_next_data_json(self, driver):
        """
        Extract __NEXT_DATA__ JSON from the page source.

        Args:
            driver: Selenium WebDriver instance

        Returns:
            Dictionary with parsed JSON data, or None if not found
        """
        try:
            page_source = driver.page_source
            pattern = r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>'
            match = re.search(pattern, page_source, re.DOTALL)

            if match:
                json_str = match.group(1)
                data = json.loads(json_str)
                return data
            else:
                return None

        except Exception as e:
            return None

    def parse_file_size(self, size_str):
        """
        Parse file size string to bytes.

        Args:
            size_str: Size string like "2.3 GB" or "1500 MB"

        Returns:
            Tuple of (human_readable_size, size_in_bytes)
        """
        if not size_str:
            return ("", 0)

        try:
            # Handle various formats: "2.3 GB", "1,500 MB", "2.3GB"
            size_str = size_str.strip().replace(',', '')
            match = re.match(r'([\d.]+)\s*([KMGT]?B)', size_str, re.IGNORECASE)

            if match:
                value = float(match.group(1))
                unit = match.group(2).upper()

                multipliers = {
                    'B': 1,
                    'KB': 1024,
                    'MB': 1024**2,
                    'GB': 1024**3,
                    'TB': 1024**4
                }

                size_bytes = int(value * multipliers.get(unit, 1))

                # Format human-readable size
                if size_bytes >= 1024**3:
                    human_size = f"{size_bytes / 1024**3:.1f} GB"
                elif size_bytes >= 1024**2:
                    human_size = f"{size_bytes / 1024**2:.1f} MB"
                elif size_bytes >= 1024:
                    human_size = f"{size_bytes / 1024:.1f} KB"
                else:
                    human_size = f"{size_bytes} B"

                return (human_size, size_bytes)

        except Exception as e:
            pass

        return (size_str, 0)

    def extract_file_info(self, driver):
        """
        Extract file information from __NEXT_DATA__ JSON in page source.

        Args:
            driver: Selenium WebDriver instance

        Returns:
            List of file dictionaries
        """
        files = []

        try:
            # Wait for page content to load
            wait = WebDriverWait(driver, 10)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            time.sleep(2)

            # Extract __NEXT_DATA__ JSON
            next_data = self.extract_next_data_json(driver)

            if not next_data:
                return files

            # Navigate to file information in the JSON structure
            fileset_map = next_data.get('props', {}).get('pageProps', {}).get('filesetMap', {})

            # Determine dataset structure
            sections_to_process = []
            if 'Files' in fileset_map:
                # Single-experiment dataset
                sections_to_process = [('Files', fileset_map['Files'])]
            else:
                # Multi-experiment dataset - process all experiment sections
                sections_to_process = [(name, section) for name, section in fileset_map.items()]

            # Process each section (either single 'Files' or multiple experiments)
            for section_name, files_section in sections_to_process:
                # Extract input files
                input_files = files_section.get('inputs', [])
                for file_data in input_files:
                    file_title = file_data.get('title', '')
                    file_url = file_data.get('url', '')
                    file_bytes = file_data.get('bytes', 0)
                    file_md5 = file_data.get('md5sum', '')

                    if not file_url:
                        continue

                    # Get filename from URL
                    file_name = file_url.split('/')[-1].split('?')[0]

                    # Extract file type from filename extension
                    file_ext = file_name.split('.')[-1].upper()

                    # Convert bytes to human-readable size (using decimal, matching website)
                    if file_bytes >= 1000**3:
                        human_size = f"{file_bytes / 1000**3:.2f} GB"
                    elif file_bytes >= 1000**2:
                        human_size = f"{file_bytes / 1000**2:.2f} MB"
                    elif file_bytes >= 1000:
                        human_size = f"{file_bytes / 1000:.2f} KB"
                    else:
                        human_size = f"{file_bytes} B"

                    # Create file entry matching website table structure
                    file_info = {
                        "file_title": file_title,          # e.g., "Microscope image"
                        "file_type": file_ext,              # e.g., "TIF", "BTF", "GZ"
                        "filename": file_name,
                        "size": human_size,
                        "size_bytes": file_bytes,
                        "md5sum": file_md5,
                        "url": file_url
                    }

                    files.append(file_info)

                    # Update statistics
                    if "microscope" in file_title.lower():
                        self.stats["microscope_images_found"] += 1

                # Extract output files
                output_files = files_section.get('outputs', [])
                for file_data in output_files:
                    file_title = file_data.get('title', '')
                    file_url = file_data.get('url', '')
                    file_bytes = file_data.get('bytes', 0)
                    file_md5 = file_data.get('md5sum', '')

                    if not file_url:
                        continue

                    # Get filename from URL
                    file_name = file_url.split('/')[-1].split('?')[0]

                    # Extract file type from filename extension
                    file_ext = file_name.split('.')[-1].upper()

                    # Convert bytes to human-readable size (using decimal, matching website)
                    if file_bytes >= 1000**3:
                        human_size = f"{file_bytes / 1000**3:.2f} GB"
                    elif file_bytes >= 1000**2:
                        human_size = f"{file_bytes / 1000**2:.2f} MB"
                    elif file_bytes >= 1000:
                        human_size = f"{file_bytes / 1000:.2f} KB"
                    else:
                        human_size = f"{file_bytes} B"

                    # Create file entry matching website table structure
                    file_info = {
                        "file_title": file_title,          # e.g., "Binned outputs (all bin levels)"
                        "file_type": file_ext,              # e.g., "GZ", "H5", "CSV"
                        "filename": file_name,
                        "size": human_size,
                        "size_bytes": file_bytes,
                        "md5sum": file_md5,
                        "url": file_url
                    }

                    files.append(file_info)

                    # Update statistics
                    if "binned" in file_title.lower():
                        self.stats["binned_outputs_found"] += 1

        except Exception as e:
            tqdm.write(f"  ✗ Error extracting files: {str(e)[:100]}", file=sys.stderr)

        return files

    def _classify_file_from_title(self, title, filename):
        """
        Use the title from metadata as-is.

        Args:
            title: File title from metadata
            filename: Actual filename

        Returns:
            File type string (uses title from metadata)
        """
        # Always use the title from the metadata as it's the most accurate
        # The website already provides correct titles for each file
        return title if title else self._classify_file_type(filename)

    def _classify_file_type(self, filename):
        """
        Classify file based on filename.

        Args:
            filename: File name

        Returns:
            Descriptive file type string
        """
        filename_lower = filename.lower()

        # Microscope image (BTF)
        if filename_lower.endswith('.btf'):
            return "Microscope Image (BTF)"

        # Binned outputs
        if 'square' in filename_lower and filename_lower.endswith('.tar.gz'):
            # Extract bin level (e.g., "002um" -> "2μm")
            match = re.search(r'(\d+)um', filename_lower)
            if match:
                bin_size = int(match.group(1))
                return f"Binned Output ({bin_size}μm)"
            return "Binned Output (GZ)"

        # Generic classifications
        if filename_lower.endswith('.tar.gz') or filename_lower.endswith('.gz'):
            return "Compressed Archive (GZ)"
        elif filename_lower.endswith('.h5'):
            return "Feature Matrix (H5)"
        elif filename_lower.endswith('.cloupe'):
            return "Loupe File"
        else:
            return "Other"

    def extract_single_dataset(self, dataset, driver=None):
        """
        Extract file information for a single dataset.

        Args:
            dataset: Dictionary containing dataset information
            driver: Optional Selenium WebDriver instance

        Returns:
            Updated dataset dictionary with files information
        """
        url = dataset.get("dataset_url", "")
        enriched = dataset.copy()

        # Initialize file fields
        enriched["files"] = []
        enriched["files_found_count"] = 0
        enriched["file_extraction_status"] = "failed"

        driver_created = False
        retry_count = 0

        while retry_count < self.max_retries:
            try:
                # Use provided driver or create a new one
                if driver is None:
                    driver = self.setup_driver()
                    driver_created = True

                if not driver:
                    raise Exception("Could not initialize browser")

                # Navigate to URL
                driver.set_page_load_timeout(self.timeout)
                driver.get(url)

                # Extract file information
                files = self.extract_file_info(driver)

                enriched["files"] = files
                enriched["files_found_count"] = len(files)

                # Determine status
                if len(files) >= 2:  # At least microscope image + one binned output
                    enriched["file_extraction_status"] = "success"
                    self.stats["successful"] += 1
                elif len(files) > 0:
                    enriched["file_extraction_status"] = "partial"
                    self.stats["partial"] += 1
                else:
                    enriched["file_extraction_status"] = "failed"
                    self.stats["failed"] += 1

                self.stats["total_files_extracted"] += len(files)

                # Success
                break

            except Exception as e:
                retry_count += 1
                if retry_count >= self.max_retries:
                    tqdm.write(f"  ✗ Failed to extract files from {url}: {str(e)[:100]}", file=sys.stderr)
                    self.stats["failed"] += 1
                else:
                    time.sleep(2 ** retry_count)  # Exponential backoff

            finally:
                # Only quit if we created the driver
                if driver_created and driver:
                    driver.quit()

        return enriched

    def extract_all_datasets(self):
        """Extract file information for all datasets."""
        print("\n" + "="*60, file=sys.stderr, flush=True)
        print("EXTRACTING FILE INFORMATION", file=sys.stderr, flush=True)
        print("="*60, file=sys.stderr, flush=True)

        enriched_datasets = []
        total = len(self.json_data)

        with tqdm(total=total, desc="Setting up browser", unit="dataset", file=sys.stderr) as pbar:
            driver = self.setup_driver()
            if not driver:
                pbar.write("✗ Failed to setup Chrome driver, cannot proceed with file extraction")
                return []

            try:
                pbar.set_description("Extracting files")

                for idx, dataset in enumerate(self.json_data, 1):
                    dataset_name = dataset.get('dataset_name', 'Unknown')[:50]
                    pbar.set_postfix_str(f"{dataset_name}...")

                    enriched = self.extract_single_dataset(dataset, driver)
                    enriched_datasets.append(enriched)

                    # Update progress bar
                    status = "✓" if enriched.get("file_extraction_status") == "success" else "⚠" if enriched.get("file_extraction_status") == "partial" else "✗"
                    pbar.set_description(f"Extracting files [{status}]")
                    pbar.update(1)

            finally:
                if driver:
                    driver.quit()

        return enriched_datasets

    def save_enriched_data(self, enriched_datasets):
        """
        Save enriched data with file information back to JSON and Excel.

        Args:
            enriched_datasets: List of enriched dataset dictionaries
        """
        print("\n" + "="*60, file=sys.stderr)
        print("SAVING ENRICHED DATA WITH FILE INFORMATION", file=sys.stderr)
        print("="*60, file=sys.stderr)

        # Save JSON (with files array)
        with open(self.json_path, 'w', encoding='utf-8') as f:
            json.dump(enriched_datasets, f, indent=2, ensure_ascii=False)
        print(f"✓ JSON updated: {self.json_path}", file=sys.stderr)

        # Convert to DataFrame for Excel
        # Flatten the files array into columns
        flattened_data = []
        for dataset in enriched_datasets:
            row = {k: v for k, v in dataset.items() if k != 'files'}

            # Add file columns
            files = dataset.get('files', [])
            for idx, file_info in enumerate(files, 1):
                row[f'file_{idx}_type'] = file_info.get('file_type', '')
                row[f'file_{idx}_filename'] = file_info.get('filename', '')
                row[f'file_{idx}_size'] = file_info.get('size', '')
                row[f'file_{idx}_md5sum'] = file_info.get('md5sum', '')
                row[f'file_{idx}_url'] = file_info.get('url', '')

            flattened_data.append(row)

        df = pd.DataFrame(flattened_data)

        # Save to Excel
        with pd.ExcelWriter(self.excel_path, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Enriched Datasets')

            # Get the worksheet
            worksheet = writer.sheets['Enriched Datasets']

            # Auto-adjust column widths
            for idx, col in enumerate(df.columns, 1):
                max_length = max(
                    df[col].astype(str).apply(len).max(),
                    len(col)
                )
                adjusted_width = min(max_length + 2, 100)
                worksheet.column_dimensions[worksheet.cell(row=1, column=idx).column_letter].width = adjusted_width

        print(f"✓ Excel updated: {self.excel_path}", file=sys.stderr)

    def print_summary(self):
        """Print file extraction summary statistics."""
        print("\n" + "="*60, file=sys.stderr)
        print("FILE EXTRACTION SUMMARY", file=sys.stderr)
        print("="*60, file=sys.stderr)

        print(f"Total datasets: {self.stats['total_datasets']}", file=sys.stderr)
        print(f"Successful extractions: {self.stats['successful']}", file=sys.stderr)
        print(f"Partial extractions: {self.stats['partial']}", file=sys.stderr)
        print(f"Failed extractions: {self.stats['failed']}", file=sys.stderr)
        print(f"\nTotal files extracted: {self.stats['total_files_extracted']}", file=sys.stderr)
        print(f"Microscope images found: {self.stats['microscope_images_found']}", file=sys.stderr)
        print(f"Binned outputs found: {self.stats['binned_outputs_found']}", file=sys.stderr)

        print("="*60, file=sys.stderr)


def main():
    """Main function to run the file extractor."""
    parser = argparse.ArgumentParser(description='Extract file download information from 10X Genomics datasets')
    parser.add_argument('--json-path', type=str,
                       help='Direct path to enriched JSON file')
    parser.add_argument('--excel-path', type=str,
                       help='Direct path to enriched Excel file')
    parser.add_argument('--name', type=str,
                       help='Run identifier (e.g., "10XGenomics-VisiumHD-Human")')
    parser.add_argument('--base-output-dir', type=str, default='../../output',
                       help='Base output directory (default: ../../output)')
    parser.add_argument('--max-retries', type=int, default=3,
                       help='Max retries for failed page loads')
    parser.add_argument('--timeout', type=int, default=30,
                       help='Timeout for page loads in seconds')

    args = parser.parse_args()

    # Build paths - either from direct paths or from name + base_output_dir
    if args.json_path and args.excel_path:
        json_path = Path(args.json_path)
        excel_path = Path(args.excel_path)
    elif args.name:
        script_dir = Path(__file__).parent
        base_dir = (script_dir / args.base_output_dir).resolve()
        enriched_dir = base_dir / args.name / 'enriched'
        json_path = enriched_dir / f'Data-{args.name}-Enriched.json'
        excel_path = enriched_dir / f'Data-{args.name}-Enriched.xlsx'
    else:
        print("✗ Error: Must provide either --json-path and --excel-path, or --name", file=sys.stderr)
        sys.exit(2)

    print("="*60, file=sys.stderr, flush=True)
    print("10X GENOMICS FILE EXTRACTOR", file=sys.stderr, flush=True)
    print("="*60, file=sys.stderr, flush=True)

    # Check if input files exist
    if not json_path.exists() or not excel_path.exists():
        print(f"✗ Error: Enriched files not found in {enriched_dir}", file=sys.stderr)
        print(f"  Expected: {json_path.name} and {excel_path.name}", file=sys.stderr)
        sys.exit(2)

    # Initialize extractor
    extractor = FileExtractor(json_path, excel_path, args.max_retries, args.timeout)

    # Load input data
    if not extractor.load_input_data():
        sys.exit(2)

    # Extract file information for all datasets
    enriched_datasets = extractor.extract_all_datasets()

    if not enriched_datasets:
        print("✗ No datasets were processed", file=sys.stderr)
        sys.exit(2)

    # Save enriched data
    extractor.save_enriched_data(enriched_datasets)

    # Print summary
    extractor.print_summary()

    # Exit code
    if extractor.stats["failed"] > 0 or extractor.stats["partial"] > 0:
        print(f"\n⚠ Partial success: {extractor.stats['failed']} failed, {extractor.stats['partial']} partial", file=sys.stderr)
        sys.exit(1)
    else:
        print(f"\n✓ All datasets processed successfully!", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
