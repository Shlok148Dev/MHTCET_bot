# scraper.py

import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
import logging
import time
from tqdm import tqdm

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
BASE_URL = "https://www.shiksha.com/engineering/mht-cet-college-predictor"
OUTPUT_FILE = "mht_cet_data.json"

def get_soup(url):
    """Fetches and parses a URL, returning a BeautifulSoup object."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        return BeautifulSoup(response.text, 'html.parser')
    except requests.RequestException as e:
        logging.error(f"Failed to fetch {url}: {e}")
        return None

def scrape_shiksha():
    """Scrapes MHT-CET college cutoff ranks from Shiksha.com."""
    all_colleges = []
    current_url = BASE_URL
    page_num = 1

    while current_url:
        logging.info(f"Scraping page {page_num}: {current_url}")
        soup = get_soup(current_url)
        if not soup:
            break

        # Shiksha lists colleges in specific 'card' like divs.
        # This selector is based on observation and may need updating if the site changes.
        college_cards = soup.find_all('div', {'data-csm-parent-name': 'predictor-Result-card'})

        if not college_cards:
            logging.warning(f"No college cards found on page {page_num}. Ending scrape.")
            break

        for card in tqdm(college_cards, desc=f"Processing Page {page_num}"):
            try:
                college_name_tag = card.find('p', {'class': 'font-bold'})
                college_name = college_name_tag.text.strip() if college_name_tag else 'N/A'

                # Cutoff ranks are often in a specific div. We look for text like "Closing All India rank"
                # and then find the corresponding rank value.
                rank_label = card.find(lambda tag: 'Closing All India rank' in tag.text and tag.name == 'p')
                if rank_label:
                    rank_value_tag = rank_label.find_next_sibling('p')
                    rank_str = rank_value_tag.text.strip().replace(',', '') if rank_value_tag else '0'
                    closing_rank = int(rank_str)
                else:
                    closing_rank = 0

                # Assume branch is Computer Science for this specific predictor page
                branch_name = "Computer Science and Engineering"

                if college_name != 'N/A' and closing_rank > 0:
                    all_colleges.append({
                        'college': college_name,
                        'branch': branch_name,
                        'closing_rank': closing_rank
                    })
            except (AttributeError, ValueError) as e:
                logging.warning(f"Could not parse a card: {e}")
                continue

        # Find the 'Next' button to go to the next page
        next_page_tag = soup.find('a', {'class': 'next-page-btn'})
        if next_page_tag and 'href' in next_page_tag.attrs:
            current_url = "https://www.shiksha.com" + next_page_tag['href']
            page_num += 1
            time.sleep(2)  # Be respectful to the server
        else:
            current_url = None
            logging.info("No 'Next' page button found. Scrape complete.")

    if not all_colleges:
        logging.error("No data was scraped. The website structure may have changed significantly.")
        return

    # Convert to DataFrame for cleaning and saving
    df = pd.DataFrame(all_colleges)
    df.drop_duplicates(subset=['college', 'branch'], inplace=True)
    df.sort_values(by='closing_rank', ascending=True, inplace=True)

    logging.info(f"Successfully scraped {len(df)} unique college records.")
    df.to_json(OUTPUT_FILE, orient='records', indent=4)
    logging.info(f"Data saved to {OUTPUT_FILE}")

if __name__ == '__main__':
    scrape_shiksha()
