#!/usr/bin/env python3
"""
10X Genomics Visium HD Dataset Scraper

Scrapes the 10X Genomics datasets page to extract information about
Visium HD Spatial Gene Expression datasets for human samples.
"""
import pathlib
import json
import time
import sys
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


def setup_driver():
    """Setup Chrome driver with appropriate options."""
    chrome_options = Options()
    chrome_options.add_argument('--headless')  # Run in background
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--remote-debugging-port=9222')

    # Add binary location options to try
    chrome_binary_locations = [
        # macOS paths
        '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome',
        '/Applications/Chromium.app/Contents/MacOS/Chromium',
        # Linux paths
        '/usr/bin/google-chrome',
        '/usr/bin/chromium',
        '/usr/bin/chromium-browser',
        '/snap/bin/chromium',
        None  # Let Selenium find it automatically
    ]

    driver = None
    last_error = None

    for binary_location in chrome_binary_locations:
        try:
            if binary_location:
                chrome_options.binary_location = binary_location
                print(f"Trying Chrome binary at: {binary_location}", file=sys.stderr)
            else:
                print("Trying default Chrome binary location", file=sys.stderr)

            # Use webdriver-manager to automatically handle driver installation
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)

            print(f"Successfully initialized Chrome driver", file=sys.stderr)
            return driver

        except Exception as e:
            last_error = e
            if binary_location:
                print(f"Failed with {binary_location}: {e}", file=sys.stderr)
            continue

    # If we get here, no Chrome installation worked
    print("\n" + "="*60, file=sys.stderr)
    print("ERROR: Could not find Chrome/Chromium browser!", file=sys.stderr)
    print("="*60, file=sys.stderr)
    print("\nPlease install Chrome or Chromium:", file=sys.stderr)
    print("  macOS: Download from https://www.google.com/chrome/", file=sys.stderr)
    print("         Install to /Applications/Google Chrome.app", file=sys.stderr)
    print("  Ubuntu/Debian: sudo apt install chromium-browser", file=sys.stderr)
    print("  Or: sudo snap install chromium", file=sys.stderr)
    print("\nLast error:", last_error, file=sys.stderr)
    print("="*60 + "\n", file=sys.stderr)

    raise Exception("No Chrome/Chromium browser found. Please install Chrome or Chromium.")


def scrape_datasets(url):
    """
    Scrape dataset information from the 10X Genomics datasets page.
    Automatically handles pagination to get all datasets.

    Args:
        url: The filtered datasets page URL

    Returns:
        Tuple of (datasets list, raw HTML content of last page)
    """
    driver = setup_driver()
    all_datasets = []
    raw_html = ""
    page_num = 0
    seen_urls_global = set()  # Track URLs across all pages to avoid duplicates
    consecutive_empty_pages = 0  # Track consecutive pages with no new data
    max_consecutive_empty = 3  # Stop after 3 consecutive pages with no new data

    # Parse the URL to handle pagination
    from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

    try:
        while True:
            # Construct URL for current page
            if page_num == 0:
                # First page - use URL as-is without adding page parameter
                current_url = url
                print(f"\nLoading page {page_num} (first page): {current_url}", file=sys.stderr)
            else:
                # Subsequent pages - add page parameter
                parsed_url = urlparse(url)
                query_params = parse_qs(parsed_url.query)
                query_params['page'] = [str(page_num)]
                new_query = urlencode(query_params, doseq=True)
                current_url = urlunparse((
                    parsed_url.scheme,
                    parsed_url.netloc,
                    parsed_url.path,
                    parsed_url.params,
                    new_query,
                    parsed_url.fragment
                ))
                print(f"\nLoading page {page_num}: {current_url}", file=sys.stderr)

            driver.get(current_url)

            # Wait for the page to load - adjust selector based on actual page structure
            print("Waiting for content to load...", file=sys.stderr)
            wait = WebDriverWait(driver, 20)

            # Try multiple possible selectors for the dataset table/list
            selectors_to_try = [
                "//div[contains(@class, 'dataset')]",
                "//table//tr",
                "//div[contains(@class, 'hit')]",
                "//div[contains(@class, 'result')]",
                "//article",
                "//a[contains(@href, '/datasets/')]",
            ]

            dataset_elements = None
            for selector in selectors_to_try:
                try:
                    wait.until(EC.presence_of_element_located((By.XPATH, selector)))
                    dataset_elements = driver.find_elements(By.XPATH, selector)
                    if dataset_elements:
                        print(f"Found {len(dataset_elements)} elements using selector: {selector}", file=sys.stderr)
                        break
                except:
                    continue

            if not dataset_elements:
                print(f"No dataset elements found on page {page_num}. Stopping pagination.", file=sys.stderr)
                break

            # Give extra time for dynamic content
            time.sleep(3)

            # Capture the raw HTML after page loads (keep the last page's HTML)
            raw_html = driver.page_source

            # Try to find dataset rows/cards
            # Look specifically for the dataset result items in the Algolia search results
            # Exclude links from header, navigation, and featured sections

            # Try to find table rows in the results
            tbody = driver.find_elements(By.XPATH, "//table//tbody")

            datasets = []  # Datasets for this page
            if tbody:
                print("Found table body, extracting from table rows", file=sys.stderr)
                table_rows = tbody[0].find_elements(By.XPATH, ".//tr")
                print(f"Found {len(table_rows)} table rows", file=sys.stderr)

                for row in table_rows:
                    try:
                        # Get all cells in the row
                        cells = row.find_elements(By.XPATH, ".//td")

                        if len(cells) < 2:
                            continue

                        # First cell usually contains the dataset name link
                        first_cell = cells[0]
                        link = first_cell.find_element(By.XPATH, ".//a[contains(@href, '/datasets/') and not(contains(@href, '/datasets?'))]")

                        dataset_url = link.get_attribute('href')
                        dataset_name = link.text.strip()
                        dataset_name = ' '.join(dataset_name.split())

                        if not dataset_name or dataset_url in seen_urls_global:
                            continue

                        seen_urls_global.add(dataset_url)

                        # Initialize dataset info
                        dataset_info = {
                            'dataset_name': dataset_name,
                            'dataset_url': dataset_url,
                            'product': '',
                            'species': '',
                            'sample_type': '',
                            'cells_or_nuclei': '',
                            'preservation': ''
                        }

                        # Extract metadata from cells based on position
                        # Table structure: [Name, Empty, Product, Species, Sample Type, Cells/Nuclei, Preservation]
                        # Indices:          0      1      2        3        4            5              6

                        if len(cells) >= 7:
                            # Extract by position
                            dataset_info['product'] = cells[2].text.strip()
                            dataset_info['species'] = cells[3].text.strip()
                            dataset_info['sample_type'] = cells[4].text.strip()
                            dataset_info['cells_or_nuclei'] = cells[5].text.strip()
                            dataset_info['preservation'] = cells[6].text.strip()
                        elif len(cells) >= 5:
                            # Fallback for tables with fewer columns - try pattern matching
                            for i, cell in enumerate(cells[1:], 1):
                                cell_text = cell.text.strip()
                                cell_text_lower = cell_text.lower()

                                if 'spatial' in cell_text_lower or 'expression' in cell_text_lower:
                                    dataset_info['product'] = cell_text
                                elif cell_text_lower in ['human', 'mouse', 'rat']:
                                    dataset_info['species'] = cell_text
                                elif 'ffpe' in cell_text_lower or 'fresh frozen' in cell_text_lower or 'fixed frozen' in cell_text_lower:
                                    dataset_info['preservation'] = cell_text
                                elif cell_text_lower in ['cells', 'nuclei', 'n/a']:
                                    dataset_info['cells_or_nuclei'] = cell_text
                                elif cell_text and not dataset_info['sample_type']:
                                    dataset_info['sample_type'] = cell_text

                        datasets.append(dataset_info)
                        print(f"Extracted: {dataset_name}", file=sys.stderr)

                    except Exception as e:
                        # Row doesn't have the expected structure, skip it
                        continue
            else:
                print("No table found, using fallback method", file=sys.stderr)
                # Fallback to old method if no table found
                dataset_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/datasets/') and not(contains(@href, '/datasets?'))]")

                for link in dataset_links:
                    try:
                        dataset_url = link.get_attribute('href')
                        if not dataset_url or dataset_url in seen_urls_global:
                            continue

                        dataset_name = link.text.strip()
                        dataset_name = ' '.join(dataset_name.split())

                        if not dataset_name:
                            continue

                        seen_urls_global.add(dataset_url)

                        datasets.append({
                            'dataset_name': dataset_name,
                            'dataset_url': dataset_url,
                            'product': '',
                            'species': '',
                            'sample_type': '',
                            'cells_or_nuclei': '',
                            'preservation': ''
                        })
                        print(f"Extracted: {dataset_name}", file=sys.stderr)

                    except Exception as e:
                        continue

            # Add datasets from this page to the overall collection
            print(f"\nPage {page_num}: Extracted {len(datasets)} new unique datasets", file=sys.stderr)

            if len(datasets) == 0:
                # No new datasets found on this page (all duplicates or empty)
                consecutive_empty_pages += 1
                print(f"No new datasets on page {page_num}. Consecutive empty pages: {consecutive_empty_pages}/{max_consecutive_empty}", file=sys.stderr)

                if consecutive_empty_pages >= max_consecutive_empty:
                    print(f"Reached {max_consecutive_empty} consecutive pages with no new data. Stopping pagination.", file=sys.stderr)
                    break
            else:
                # Found new data, reset the counter
                consecutive_empty_pages = 0

            all_datasets.extend(datasets)
            print(f"Total unique datasets so far: {len(all_datasets)}", file=sys.stderr)

            # Move to next page
            page_num += 1

    except Exception as e:
        print(f"Error during scraping: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()

    finally:
        driver.quit()

    print(f"\n{'='*60}", file=sys.stderr)
    print(f"Pagination complete. Total datasets scraped: {len(all_datasets)}", file=sys.stderr)
    print(f"{'='*60}\n", file=sys.stderr)

    return all_datasets, raw_html


def ensure_directories(base_output_dir, name):
    """Create input and output directories if they don't exist.

    Args:
        base_output_dir: Base output directory path
        name: Run identifier for organizing outputs

    Returns:
        Tuple of (input_dir, output_dir) paths
    """
    import os
    # Create run-specific directory structure
    run_dir = os.path.join(base_output_dir, name)
    input_dir = os.path.join(run_dir, 'input')
    output_dir = os.path.join(run_dir, 'output')

    os.makedirs(input_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    return input_dir, output_dir


def save_url_to_file(url, filepath):
    """
    Save the URL to a file in the input directory.

    Args:
        url: The URL to save
        filepath: The file path where to save the URL
    """
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(url)
    print(f"URL saved to: {filepath}", file=sys.stderr)


def save_raw_html(html_content, filepath):
    """
    Save the raw HTML page source to a file.

    Args:
        html_content: The HTML content to save
        filepath: The file path where to save the HTML
    """
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"Raw HTML saved to: {filepath}", file=sys.stderr)


def save_json_output(data, filepath):
    """
    Save the scraped data as JSON to the output directory.

    Args:
        data: The data to save (list of dictionaries)
        filepath: The file path where to save the JSON
    """
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"JSON output saved to: {filepath}", file=sys.stderr)


def save_excel_output(data, filepath):
    """
    Save the scraped data as an Excel spreadsheet to the output directory.

    Args:
        data: The data to save (list of dictionaries)
        filepath: The file path where to save the Excel file
    """
    if not data:
        print("No data to save to Excel", file=sys.stderr)
        return

    # Convert list of dictionaries to pandas DataFrame
    df = pd.DataFrame(data)

    # Reorder columns for better readability
    column_order = [
        'dataset_name',
        'dataset_url',
        'product',
        'species',
        'sample_type',
        'cells_or_nuclei',
        'preservation'
    ]

    # Only include columns that exist in the data
    available_columns = [col for col in column_order if col in df.columns]
    df = df[available_columns]

    # Save to Excel with some formatting
    with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Datasets')

        # Get the worksheet to apply formatting
        worksheet = writer.sheets['Datasets']

        # Auto-adjust column widths based on content
        for idx, col in enumerate(df.columns, 1):
            max_length = max(
                df[col].astype(str).apply(len).max(),
                len(col)
            )
            # Add some padding and cap at a reasonable width
            adjusted_width = min(max_length + 2, 100)
            worksheet.column_dimensions[worksheet.cell(row=1, column=idx).column_letter].width = adjusted_width

    print(f"Excel output saved to: {filepath}", file=sys.stderr)


def main():
    """Main function to run the scraper."""
    import os
    import argparse

    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='10X Genomics Dataset Scraper')
    parser.add_argument('--url', type=str, required=True,
                       help='Source URL to scrape')
    parser.add_argument('--name', type=str, required=True,
                       help='Human-readable run identifier (e.g., "10XGenomics-VisiumHD-Human")')
    parser.add_argument('--base-output-dir', type=str, default='../../output',
                       help='Base output directory (default: ../../output)')

    args = parser.parse_args()

    url = args.url
    name = args.name
    base_output_dir = "/Users/omersumer/Desktop/skills/10XGenomics_scraper/output" # args.base_output_dir

    # Ensure directories exist
    input_dir, output_dir = ensure_directories(base_output_dir, name)

    # Define file paths with parameterized names
    url_filepath = os.path.join(input_dir, f'URL-{name}.txt')
    raw_html_filepath = os.path.join(input_dir, f'RawData-{name}.html')
    output_filepath = os.path.join(output_dir, f'Data-{name}.json')
    excel_filepath = os.path.join(output_dir, f'Data-{name}.xlsx')

    print('===> ', "input_dir:", input_dir)
    print('===> ', "output_dir:", output_dir)
    print('===> ', "url_filepath:", url_filepath)
    print('===> ', "raw_html_filepath:", raw_html_filepath)
    print('===> ', "output_filepath:", output_filepath)
    print('===> ', "excel_filepath:", excel_filepath)


    print(f"Starting 10X Genomics Dataset Scraper: {name}", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(f"URL: {url}", file=sys.stderr)
    print(f"Output directory: {os.path.join(base_output_dir, name)}", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    # Save URL to input file
    save_url_to_file(url, url_filepath)

    # Scrape datasets and get raw HTML
    datasets, raw_html = scrape_datasets(url)

    # Save raw HTML to input file
    save_raw_html(raw_html, raw_html_filepath)

    # Save JSON output to file
    save_json_output(datasets, output_filepath)

    # Save Excel output to file
    save_excel_output(datasets, excel_filepath)

    # Also output to stdout for backward compatibility
    print(json.dumps(datasets, indent=2))

    print("=" * 60, file=sys.stderr)
    print(f"Scraping completed. Found {len(datasets)} datasets.", file=sys.stderr)
    print(f"JSON output saved to: {output_filepath}", file=sys.stderr)
    print(f"Excel output saved to: {excel_filepath}", file=sys.stderr)


if __name__ == "__main__":
    main()
