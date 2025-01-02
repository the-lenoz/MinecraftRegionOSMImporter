import subprocess
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from zipfile import ZipFile
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import time

# Define custom headers with a Firefox User-Agent
HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
    )
}

MAX_RETRIES = 3  # Maximum number of retries for failed requests
RETRY_DELAY = 5  # Delay (in seconds) between retries


def download_and_extract_file(file_url, output_folder):
    """
    Downloads and extracts a single .zip file from a given URL to the specified folder.

    Args:
        file_url (str): URL of the .zip file to download.
        output_folder (Path): Directory where the file will be extracted.

    Returns:
        str: The name of the extracted file or an error message.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            # Download the zip file
            response = requests.get(file_url, headers=HEADERS)
            response.raise_for_status()

            # Extract the zip file
            with ZipFile(BytesIO(response.content)) as zip_file:
                zip_file.extractall(output_folder)
            return f'Extracted {file_url} successfully.'
        except Exception as e:
            if attempt < MAX_RETRIES:
                print(f'Retry {attempt}/{MAX_RETRIES} for {file_url} due to error: {e}')
                time.sleep(RETRY_DELAY)
            else:
                return f'Failed to process {file_url} after {MAX_RETRIES} retries: {e}'


def crawl_and_download(url, output_folder, max_threads=10):
    """
    Recursively downloads and extracts all .zip files from a URL and its sub_folders.

    Args:
        url (str): The base URL to crawl.
        output_folder (Path): The folder where files will be downloaded and extracted.
        max_threads (int): Maximum number of threads to use.

    Returns:
        None
    """
    # Ensure the output folder exists
    output_folder = Path(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)

    try:
        # Fetch all links (files and sub_folders) from the base URL
        print(f'Fetching links from {url}...')
        all_links = fetch_links(url)

        # Separate links into files and sub_folders
        zip_files = [link for link in all_links if link.endswith('.zip')]
        sub_folders = [link for link in all_links if not link.endswith('.zip') and not link.endswith('/')]

        print(f'Found {len(zip_files)} .zip files and {len(sub_folders)} sub_folders to process.')

        # Download and extract .zip files concurrently
        with ThreadPoolExecutor(max_threads) as executor:
            with tqdm(total=len(zip_files), desc='Downloading and Extracting', unit='file') as progress_bar:
                future_to_url = {
                    executor.submit(download_and_extract_file, file_url, output_folder): file_url for file_url in
                    zip_files
                }

                for future in as_completed(future_to_url):
                    url = future_to_url[future]
                    try:
                        result = future.result()
                        print(result)  # Optional: Print success or error messages for individual files
                    except Exception as e:
                        print(f'An error occurred while processing {url}: {e}')
                    finally:
                        progress_bar.update(1)

        # Recursively process sub_folders
        for sub_folder in sub_folders:
            sub_folder_name = Path(sub_folder).name
            sub_folder_output = output_folder / sub_folder_name
            crawl_and_download(sub_folder, sub_folder_output, max_threads)

        print('All files downloaded and extracted successfully.')

    except Exception as e:
        print(f'An error occurred: {e}')


def fetch_links(url):
    """
    Fetches all links (files and directories) from the specified URL.

    Args:
        url (str): The URL to scrape.

    Returns:
        list: List of links (absolute URLs).
    """
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        links = [f'{url}/{a["href"]}' for a in soup.find_all('a', href=True) if not a['href'].startswith('?')]
        return links
    except Exception as e:
        print(f'Failed to fetch links from {url}: {e}')
        return []


def setup_osm2world():
    download_and_extract_file('https://osm2world.org/download/files/latest/OSM2World-latest-bin.zip',
                              Path('osm2world'))


def obtain_SRTM_data():
    crawl_and_download('https://srtm.kurviger.de/SRTM3', Path('osm2world/SRTM'), max_threads=10)


def setup_splitter():
    subprocess.run('ObjFileSplitter/gradlew', cwd='ObjFileSplitter', check=True)


def main():
    print('Setting up OSM2world')
    setup_osm2world()
    print('Setting up splitter')
    setup_splitter()

    print('Obtaining SRTM data. It may take long')
    obtain_SRTM_data()


if __name__ == '__main__':
    main()
