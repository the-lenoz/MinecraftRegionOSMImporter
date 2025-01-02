import time
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import requests
from bs4 import BeautifulSoup

# Define custom headers with a Firefox User-Agent
HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
    )
}

MAX_RETRIES = 3  # Maximum number of retries for failed requests
RETRY_DELAY = 5  # Delay (in seconds) between retries


def download_map_data(config: dict, bbox: tuple, output_file_path: Path):
    url = config['url'].format(lat0=bbox[0][0], lon0=bbox[0][1], lat1=bbox[1][0], lon1=bbox[1][1])
    response = requests.get(url)
    with open(output_file_path, 'w') as osm_file:
        osm_file.write(response.text)


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
        links = [f'{url.replace("/index.html", "")}/{a["href"]}' for a in soup.find_all('a', href=True) if
                 not a['href'].startswith('?')
                 and not a['href'].startswith('..')]
        return links
    except Exception as e:
        print(f'Failed to fetch links from {url}: {e}')
        return []


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
                for file_info in zip_file.infolist():
                    zip_file.extract(file_info, path=output_folder)
            return f'Extracted {file_url} successfully.'
        except Exception as e:
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
            else:
                return f'Failed to process {file_url} after {MAX_RETRIES} retries: {e}'


def find_SRTM_link(root_url: str, filename: str) -> str | None:
    links = fetch_links(root_url)

    file_url = None
    for link in links:
        if filename in link:
            file_url = link
        if not file_url and link.endswith('index.html'):
            file_url = find_SRTM_link(link, filename)
        if file_url:
            return file_url


def download_SRTM_data(root_url: str, destination_folder: Path, lat: int, lon: int):
    lat_prefix = 'N' if lat >= 0 else 'S'
    lon_prefix = 'E' if lon >= 0 else 'W'

    lat, lon = abs(lat), abs(lon)

    SRTM_file_name = f'{lat_prefix}{str(lat).zfill(2)}{lon_prefix}{str(lon).zfill(3)}'
    SRTM_file_link = find_SRTM_link(root_url, SRTM_file_name)
    result = download_and_extract_file(SRTM_file_link, destination_folder)
    return result
