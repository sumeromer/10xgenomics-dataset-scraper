#!/usr/bin/env python3
"""
10X Genomics Metadata Enricher

Enriches validated dataset information by extracting additional metadata
from each dataset's detail page, including imaging parameters and sample information.
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
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm


class MetadataEnricher:
    """Enriches dataset information with additional metadata from detail pages."""

    def __init__(self, json_path, excel_path, output_dir, max_retries=3, timeout=30, max_workers=3):
        """
        Initialize the enricher.

        Args:
            json_path: Path to input JSON file
            excel_path: Path to input Excel file
            output_dir: Directory for enriched output files
            max_retries: Maximum retries for failed page loads
            timeout: Timeout for page loads in seconds
            max_workers: Number of parallel browser instances
        """
        self.json_path = Path(json_path)
        self.excel_path = Path(excel_path)
        self.output_dir = Path(output_dir)
        self.max_retries = max_retries
        self.timeout = timeout
        self.max_workers = max_workers

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Statistics
        self.stats = {
            "total_datasets": 0,
            "successful": 0,
            "failed": 0,
            "field_completion": {}
        }

    def load_input_data(self):
        """Load validated JSON and Excel data."""
        print("Loading validated data files...", file=sys.stderr, flush=True)

        try:
            # Load JSON
            with open(self.json_path, 'r', encoding='utf-8') as f:
                self.json_data = json.load(f)
            print(f"✓ Loaded JSON: {len(self.json_data)} entries", file=sys.stderr, flush=True)

            # Load Excel (keep_default_na=False to preserve "N/A" as literal string)
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

        10X Genomics uses Next.js which embeds data in a JSON script tag.

        Args:
            driver: Selenium WebDriver instance

        Returns:
            Dictionary with parsed JSON data, or None if not found
        """
        try:
            # Get page source
            page_source = driver.page_source

            # Find the __NEXT_DATA__ script tag
            import re
            pattern = r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>'
            match = re.search(pattern, page_source, re.DOTALL)

            if match:
                json_str = match.group(1)
                data = json.loads(json_str)
                return data
            else:
                # Silently return None - not all pages will have this data
                return None

        except Exception as e:
            # Silently return None - extraction errors are expected for some pages
            return None

    def extract_imaging_metadata(self, driver):
        """
        Extract imaging section metadata from __NEXT_DATA__ JSON.

        Args:
            driver: Selenium WebDriver instance

        Returns:
            Dictionary with imaging metadata
        """
        imaging_data = {
            "biomaterials": "",
            "sample_preparation": "",
            "image_type": "",
            "microscope": "",
            "objective_magnification": "",
            "numerical_aperture": "",
            "scopeled_light_source": "",
            "camera": "",
            "exposure": ""
        }

        try:
            # Wait for page content to load
            wait = WebDriverWait(driver, 10)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            time.sleep(2)  # Additional time for dynamic content

            # Extract the __NEXT_DATA__ JSON
            next_data = self.extract_next_data_json(driver)

            if next_data:
                # Navigate to the dataset information
                dataset = next_data.get('props', {}).get('pageProps', {}).get('dataset', {})

                # Get the body text which contains imaging information
                body_text = dataset.get('body', '')

                if body_text:
                    # Parse the body text for imaging parameters
                    lines = body_text.split('\n')
                    current_section = None

                    for line in lines:
                        line = line.strip()

                        # Track which section we're in
                        if line.startswith('**Biomaterials**'):
                            current_section = 'biomaterials'
                            continue
                        elif line.startswith('**Sample preparation**'):
                            current_section = 'sample_preparation'
                            continue
                        elif line.startswith('**Imaging**'):
                            current_section = 'imaging'
                            continue
                        elif line.startswith('**'):
                            current_section = None
                            continue

                        # Extract content based on section
                        if current_section == 'biomaterials' and line:
                            if not imaging_data["biomaterials"]:
                                imaging_data["biomaterials"] = line

                        elif current_section == 'sample_preparation' and line:
                            if not imaging_data["sample_preparation"]:
                                imaging_data["sample_preparation"] = line

                        elif current_section == 'imaging' and ':' in line:
                            # Parse key-value pairs in imaging section
                            if line.startswith('- '):
                                line = line[2:]  # Remove bullet point
                            parts = line.split(':', 1)
                            if len(parts) == 2:
                                key = parts[0].strip().lower()
                                value = parts[1].strip()
                                self._map_imaging_field(key, value, imaging_data)

        except Exception as e:
            # Silently return partial data - extraction errors are expected
            pass

        return imaging_data

    def _map_imaging_field(self, key, value, imaging_data):
        """
        Map extracted key-value pair to imaging_data field.

        Args:
            key: Field name (lowercase)
            value: Field value
            imaging_data: Dictionary to update
        """
        if not value or value == 'N/A':
            return

        # Map variations of field names to standard fields
        field_mappings = {
            "biomaterials": ["biomaterial", "biomaterials", "bio materials"],
            "sample_preparation": ["sample preparation", "sample prep", "preparation"],
            "image_type": ["image type", "imaging type", "staining", "stain"],
            "microscope": ["microscope", "imaging system"],
            "objective_magnification": ["magnification", "objective magnification", "objective mag"],
            "numerical_aperture": ["numerical aperture", "na", "n.a."],
            "scopeled_light_source": ["light source", "scopeled", "led source", "illumination"],
            "camera": ["camera", "detector"],
            "exposure": ["exposure", "exposure time", "exposure settings"]
        }

        for field, variations in field_mappings.items():
            if any(variation in key for variation in variations):
                if not imaging_data[field]:  # Only update if empty
                    imaging_data[field] = value
                break

    def _extract_from_page_text(self, page_text, imaging_data):
        """
        Extract fields from page text using keyword search.

        Args:
            page_text: Full page text content
            imaging_data: Dictionary to update
        """
        lines = page_text.split('\n')

        # Look for H&E, IF, IHC, etc.
        if not imaging_data["image_type"]:
            for line in lines:
                line_lower = line.lower()
                if 'h&e' in line_lower or 'hematoxylin' in line_lower:
                    imaging_data["image_type"] = "H&E"
                    break
                elif 'if' in line_lower or 'immunofluorescence' in line_lower:
                    imaging_data["image_type"] = "IF"
                    break
                elif 'ihc' in line_lower or 'immunohistochemistry' in line_lower:
                    imaging_data["image_type"] = "IHC"
                    break

    def extract_sample_info(self, driver):
        """
        Extract sample information from __NEXT_DATA__ JSON.

        Args:
            driver: Selenium WebDriver instance

        Returns:
            Dictionary with sample information
        """
        sample_info = {
            "anatomical_entity": "",
            "preservation_method": "",
            "disease_state": "",
            "biomaterial_type": "",
            "donor_count": "",
            "date_published": ""
        }

        try:
            # Extract the __NEXT_DATA__ JSON
            next_data = self.extract_next_data_json(driver)

            if next_data:
                # Navigate to the dataset information
                dataset = next_data.get('props', {}).get('pageProps', {}).get('dataset', {})

                # Extract structured fields
                # Anatomical Entity
                anatomical_entities = dataset.get('anatomicalEntities', [])
                if anatomical_entities:
                    sample_info["anatomical_entity"] = ", ".join(anatomical_entities)

                # Preservation Method
                preservation_methods = dataset.get('preservationMethods', [])
                if preservation_methods:
                    sample_info["preservation_method"] = ", ".join(preservation_methods)

                # Disease State
                disease_states = dataset.get('diseaseStates', [])
                if disease_states:
                    sample_info["disease_state"] = ", ".join(disease_states)

                # Biomaterial Type
                biomaterial_types = dataset.get('biomaterialTypes', [])
                if biomaterial_types:
                    sample_info["biomaterial_type"] = ", ".join(biomaterial_types)

                # Donor Count
                donor_count = dataset.get('donorCount', '')
                if donor_count:
                    sample_info["donor_count"] = str(donor_count)

                # Date Published
                published_at = dataset.get('publishedAt', '')
                if published_at:
                    # Convert ISO date to readable format
                    from datetime import datetime
                    try:
                        dt = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                        sample_info["date_published"] = dt.strftime("%Y-%m-%d")
                    except:
                        sample_info["date_published"] = published_at

        except Exception as e:
            # Silently return partial data - extraction errors are expected
            pass

        return sample_info

    def _map_sample_field(self, key, value, sample_info):
        """
        Map extracted key-value pair to sample_info field.

        Args:
            key: Field name (lowercase)
            value: Field value
            sample_info: Dictionary to update
        """
        if not value or value == 'N/A':
            return

        field_mappings = {
            "anatomical_entity": ["anatomical entity", "anatomical location", "tissue", "organ"],
            "preservation_method": ["preservation", "preservation method", "fixation"],
            "disease_state": ["disease", "disease state", "condition", "pathology"],
            "biomaterial_type": ["biomaterial type", "material type", "sample type"],
            "donor_count": ["donor", "donor count", "donors", "number of donors"],
            "date_published": ["date published", "published", "publication date", "release date"]
        }

        for field, variations in field_mappings.items():
            if any(variation in key for variation in variations):
                if not sample_info[field]:  # Only update if empty
                    sample_info[field] = value
                break

    def _extract_sample_from_page_text(self, page_text, sample_info):
        """
        Extract sample fields from page text.

        Args:
            page_text: Full page text
            sample_info: Dictionary to update
        """
        lines = page_text.split('\n')

        # Disease state detection
        if not sample_info["disease_state"]:
            for line in lines:
                line_lower = line.lower()
                if 'healthy' in line_lower or 'normal' in line_lower:
                    sample_info["disease_state"] = "Healthy"
                    break
                elif 'cancer' in line_lower or 'tumor' in line_lower or 'carcinoma' in line_lower:
                    sample_info["disease_state"] = "Cancer"
                    break

        # Preservation method
        if not sample_info["preservation_method"]:
            for line in lines:
                line_lower = line.lower()
                if 'ffpe' in line_lower or 'formalin' in line_lower:
                    sample_info["preservation_method"] = "FFPE"
                    break
                elif 'fresh frozen' in line_lower or 'frozen' in line_lower:
                    sample_info["preservation_method"] = "Fresh Frozen"
                    break

    def enrich_single_dataset(self, dataset, driver=None):
        """
        Enrich a single dataset with additional metadata.

        Args:
            dataset: Dictionary containing dataset information
            driver: Optional Selenium WebDriver instance (if None, creates new one)

        Returns:
            Enriched dataset dictionary
        """
        url = dataset.get("dataset_url", "")
        enriched = dataset.copy()

        # Initialize new fields
        new_fields = {
            "biomaterials": "",
            "sample_preparation": "",
            "image_type": "",
            "microscope": "",
            "objective_magnification": "",
            "numerical_aperture": "",
            "scopeled_light_source": "",
            "camera": "",
            "exposure": "",
            "anatomical_entity": "",
            "preservation_method": "",
            "disease_state": "",
            "biomaterial_type": "",
            "donor_count": "",
            "date_published": ""
        }

        enriched.update(new_fields)

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

                # Extract imaging metadata
                imaging_data = self.extract_imaging_metadata(driver)
                enriched.update(imaging_data)

                # Extract sample information
                sample_info = self.extract_sample_info(driver)
                enriched.update(sample_info)

                # Success
                self.stats["successful"] += 1
                break

            except Exception as e:
                retry_count += 1
                if retry_count >= self.max_retries:
                    tqdm.write(f"  ✗ Failed to enrich {url}: {str(e)[:100]}", file=sys.stderr)
                    self.stats["failed"] += 1
                else:
                    time.sleep(2 ** retry_count)  # Exponential backoff

            finally:
                # Only quit if we created the driver
                if driver_created and driver:
                    driver.quit()

        return enriched

    def enrich_all_datasets(self):
        """Enrich all datasets with additional metadata."""
        print("\n" + "="*60, file=sys.stderr, flush=True)
        print("ENRICHING DATASETS WITH ADDITIONAL METADATA", file=sys.stderr, flush=True)
        print("="*60, file=sys.stderr, flush=True)

        enriched_datasets = []
        total = len(self.json_data)

        # Create progress bar immediately so it's visible during driver setup
        with tqdm(total=total, desc="Setting up browser", unit="dataset", file=sys.stderr) as pbar:
            # Create a single driver instance to reuse
            driver = self.setup_driver()
            if not driver:
                pbar.write("✗ Failed to setup Chrome driver, cannot proceed with enrichment")
                return []

            try:
                # Update progress bar description to show we're now enriching
                pbar.set_description("Enriching datasets")

                for idx, dataset in enumerate(self.json_data, 1):
                    dataset_name = dataset.get('dataset_name', 'Unknown')[:50]
                    pbar.set_postfix_str(f"{dataset_name}...")

                    enriched = self.enrich_single_dataset(dataset, driver)
                    enriched_datasets.append(enriched)

                    # Update field completion statistics
                    for field in ["biomaterials", "sample_preparation", "image_type", "microscope",
                                 "objective_magnification", "numerical_aperture", "scopeled_light_source",
                                 "camera", "exposure", "anatomical_entity", "preservation_method",
                                 "disease_state", "biomaterial_type", "donor_count", "date_published"]:
                        if field not in self.stats["field_completion"]:
                            self.stats["field_completion"][field] = 0
                        if enriched.get(field, ""):
                            self.stats["field_completion"][field] += 1

                    # Update progress bar with success/fail status
                    status = "✓" if idx <= self.stats["successful"] else "✗"
                    pbar.set_description(f"Enriching datasets [{status}]")
                    pbar.update(1)

            finally:
                # Clean up the driver
                if driver:
                    driver.quit()

        return enriched_datasets

    def save_enriched_data(self, enriched_datasets):
        """
        Save enriched data to JSON and Excel files.

        Args:
            enriched_datasets: List of enriched dataset dictionaries
        """
        print("\n" + "="*60, file=sys.stderr)
        print("SAVING ENRICHED DATA", file=sys.stderr)
        print("="*60, file=sys.stderr)

        # Save JSON
        json_output_path = self.output_dir / "Data-10XGenomics-VisiumHD-Human-Enriched.json"
        with open(json_output_path, 'w', encoding='utf-8') as f:
            json.dump(enriched_datasets, f, indent=2, ensure_ascii=False)
        print(f"✓ JSON saved to: {json_output_path}", file=sys.stderr)

        # Save Excel
        excel_output_path = self.output_dir / "Data-10XGenomics-VisiumHD-Human-Enriched.xlsx"
        df = pd.DataFrame(enriched_datasets)

        # Reorder columns for better readability
        original_columns = [
            'dataset_name', 'dataset_url', 'product', 'species', 'sample_type',
            'cells_or_nuclei', 'preservation'
        ]
        imaging_columns = [
            'biomaterials', 'sample_preparation', 'image_type', 'microscope',
            'objective_magnification', 'numerical_aperture', 'scopeled_light_source',
            'camera', 'exposure'
        ]
        sample_columns = [
            'anatomical_entity', 'preservation_method', 'disease_state',
            'biomaterial_type', 'donor_count', 'date_published'
        ]

        column_order = original_columns + imaging_columns + sample_columns
        available_columns = [col for col in column_order if col in df.columns]
        df = df[available_columns]

        # Save to Excel with formatting
        with pd.ExcelWriter(excel_output_path, engine='openpyxl') as writer:
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

        print(f"✓ Excel saved to: {excel_output_path}", file=sys.stderr)

    def print_summary(self):
        """Print enrichment summary statistics."""
        print("\n" + "="*60, file=sys.stderr)
        print("ENRICHMENT SUMMARY", file=sys.stderr)
        print("="*60, file=sys.stderr)

        print(f"Total datasets: {self.stats['total_datasets']}", file=sys.stderr)
        print(f"Successfully enriched: {self.stats['successful']}", file=sys.stderr)
        print(f"Failed: {self.stats['failed']}", file=sys.stderr)

        print("\nField Completion Rates:", file=sys.stderr)
        for field, count in sorted(self.stats['field_completion'].items()):
            percentage = (count / self.stats['total_datasets']) * 100 if self.stats['total_datasets'] > 0 else 0
            print(f"  {field}: {count}/{self.stats['total_datasets']} ({percentage:.1f}%)", file=sys.stderr)

        print("="*60, file=sys.stderr)


def main():
    """Main function to run the enricher."""
    parser = argparse.ArgumentParser(description='Enrich 10X Genomics dataset metadata')
    parser.add_argument('--name', type=str, required=True,
                       help='Run identifier (e.g., "10XGenomics-VisiumHD-Human")')
    parser.add_argument('--base-output-dir', type=str, default='../../output',
                       help='Base output directory (default: ../../output)')
    parser.add_argument('--max-retries', type=int, default=3,
                       help='Max retries for failed page loads')
    parser.add_argument('--timeout', type=int, default=30,
                       help='Timeout for page loads in seconds')
    parser.add_argument('--parallel', type=int, default=3,
                       help='Number of parallel browser instances')

    args = parser.parse_args()

    # Build paths based on name and base output directory
    script_dir = Path(__file__).parent
    base_dir = script_dir.parent.parent / args.base_output_dir
    run_dir = base_dir / args.name

    json_path = run_dir / 'output' / f'Data-{args.name}.json'
    excel_path = run_dir / 'output' / f'Data-{args.name}.xlsx'
    output_dir = run_dir / 'enriched'

    print("="*60, file=sys.stderr, flush=True)
    print("10X GENOMICS METADATA ENRICHER", file=sys.stderr, flush=True)
    print("="*60, file=sys.stderr, flush=True)

    # Initialize enricher
    enricher = MetadataEnricher(json_path, excel_path, output_dir, args.max_retries, args.timeout, args.parallel)

    # Load input data
    if not enricher.load_input_data():
        sys.exit(2)

    # Enrich all datasets
    enriched_datasets = enricher.enrich_all_datasets()

    # Save enriched data
    enricher.save_enriched_data(enriched_datasets)

    # Print summary
    enricher.print_summary()

    # Exit code
    if enricher.stats["failed"] > 0:
        print(f"\n⚠ Partial success: {enricher.stats['failed']} dataset(s) failed to enrich", file=sys.stderr)
        sys.exit(1)
    else:
        print(f"\n✓ All datasets enriched successfully!", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
