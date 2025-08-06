# scraper.py

import requests
from bs4 import BeautifulSoup
import json
import pandas as pd
import time
import re
import logging
from tqdm import tqdm

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MHTCETScraper:
    """
    A robust scraper for MHT-CET cutoff data.
    
    Strategy:
    1.  Attempt to scrape data from multiple reliable third-party sources that
        present data in clean HTML tables. This is more practical than parsing
        the complex PDFs on official government sites.
    2.  Combine and standardize the data from all sources.
    3.  If all live scraping attempts fail, generate a comprehensive set of mock data
        to ensure the chatbot application remains functional.
    4.  Clean, de-duplicate, and save the final dataset to a JSON file.
    """
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        # These are our primary scraping targets, known to have HTML tables.
        self.live_sources = [
            {'name': 'CollegeSearch', 'url': 'https://www.collegesearch.in/articles/mht-cet-cutoff-for-computer-engineering', 'parser': self._parse_collegesearch},
            {'name': 'CollegeDunia', 'url': 'https://collegedunia.com/exams/mht-cet/cutoff', 'parser': self._parse_collegedunia}
        ]
        self.college_data = []

    def _get_page_content(self, url, timeout=30):
        """Safely fetch page content with error handling."""
        try:
            response = self.session.get(url, timeout=timeout)
            response.raise_for_status()
            return BeautifulSoup(response.content, 'html.parser')
        except requests.RequestException as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    def _standardize_branch_name(self, branch):
        """Standardize common branch name variations."""
        branch = branch.lower()
        if 'computer' in branch:
            return 'Computer Engineering'
        if 'information technology' in branch or 'it' in branch:
            return 'Information Technology'
        if 'electronics' in branch and 'telecommunication' in branch:
            return 'Electronics and Telecommunication Engineering'
        if 'mechanical' in branch:
            return 'Mechanical Engineering'
        if 'civil' in branch:
            return 'Civil Engineering'
        if 'electrical' in branch:
            return 'Electrical Engineering'
        # Add more rules as needed
        return branch.title()

    def _parse_collegesearch(self, soup, url):
        """Parser for CollegeSearch website structure."""
        data = []
        tables = soup.find_all('table')
        if not tables:
            return data
            
        for table in tables:
            headers = [th.get_text(strip=True).lower() for th in table.find_all('th')]
            if 'college name' in headers and 'mht cet cutoff percentile' in headers:
                for row in table.find('tbody').find_all('tr'):
                    cols = row.find_all('td')
                    if len(cols) >= 2:
                        college_name = cols[0].get_text(strip=True)
                        percentile_str = cols[1].get_text(strip=True)
                        percentile_match = re.search(r'(\d+\.\d+)', percentile_str)
                        if percentile_match:
                            data.append({
                                'college': self.clean_text(college_name),
                                'branch': 'Computer Engineering', # This page is specific
                                'cutoff_percentile': float(percentile_match.group(1)),
                                'category': 'General', # Assume General unless specified
                                'source': url
                            })
        return data

    def _parse_collegedunia(self, soup, url):
        """Parser for CollegeDunia website structure."""
        data = []
        # CollegeDunia often puts data in tables with specific classes or IDs
        cutoff_div = soup.find('div', id='cutoff')
        if not cutoff_div:
            return data
        
        tables = cutoff_div.find_all('table')
        for table in tables:
            # Heuristic: find tables with college name and cutoff score
            rows = table.find('tbody').find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 2:
                    college_link = cols[0].find('a')
                    if not college_link: continue
                    
                    college_name = college_link.get_text(strip=True)
                    # This page structure often has branch in the name, e.g., "VJTI, B.Tech Computer Engineering"
                    # We will simplify this
                    branch_match = re.search(r'B\.Tech\s*(.*)', college_name)
                    branch_name = branch_match.group(1) if branch_match else "Unknown"
                    college_name = re.sub(r',?\s*B\.Tech.*', '', college_name) # Clean college name

                    percentile_str = cols[1].get_text(strip=True)
                    percentile_match = re.search(r'(\d+(\.\d+)?)', percentile_str)

                    if percentile_match:
                         data.append({
                                'college': self.clean_text(college_name),
                                'branch': self._standardize_branch_name(branch_name),
                                'cutoff_percentile': float(percentile_match.group(1)),
                                'category': 'General',
                                'source': url
                            })
        return data

    def scrape_live_data(self):
        """Scrape data from all configured live sources."""
        all_data = []
        logger.info("Starting to scrape live data from configured sources...")
        
        for source in tqdm(self.live_sources, desc="Scraping Sources"):
            logger.info(f"Attempting to scrape: {source['name']} ({source['url']})")
            soup = self._get_page_content(source['url'])
            if soup:
                try:
                    scraped_data = source['parser'](soup, source['url'])
                    if scraped_data:
                        logger.info(f"Successfully extracted {len(scraped_data)} records from {source['name']}.")
                        all_data.extend(scraped_data)
                    else:
                        logger.warning(f"No records extracted from {source['name']}. The site structure might have changed.")
                except Exception as e:
                    logger.error(f"Failed to parse {source['name']}: {e}", exc_info=True)
            time.sleep(2)  # Be respectful to the servers
            
        return all_data

    def generate_mock_data(self):
        """Generate mock data if live scraping fails."""
        logger.warning("Live scraping failed or yielded no data. Generating mock data as a fallback.")
        
        colleges = ["Veermata Jijabai Technological Institute (VJTI), Mumbai", "College of Engineering, Pune (CoEP)", "Sardar Patel Institute of Technology, Mumbai", "Walchand College of Engineering, Sangli", "MIT Academy of Engineering, Pune", "Vishwakarma Institute of Technology, Pune", "Thadomal Shahani Engineering College, Mumbai", "Government College of Engineering, Aurangabad"]
        branches = ["Computer Engineering", "Information Technology", "Electronics and Telecommunication Engineering", "Mechanical Engineering", "Civil Engineering"]
        
        mock_data = []
        for college in tqdm(colleges, desc="Generating Mock Data"):
            for branch in branches:
                base_percentile = self._get_base_percentile(college, branch)
                mock_data.append({
                    'college': college,
                    'branch': branch,
                    'cutoff_percentile': round(max(85.0, min(99.9, base_percentile)), 4),
                    'category': 'General',
                    'source': 'mock_data'
                })
        return mock_data

    def _get_base_percentile(self, college, branch):
        """Helper for mock data generation."""
        base = 85.0
        if any(t in college for t in ["VJTI", "CoEP", "Sardar Patel"]): base = 96.0
        elif any(t in college for t in ["Walchand", "MIT", "Vishwakarma"]): base = 92.0
        
        if "Computer" in branch: base += 3.5
        elif "Information Technology" in branch: base += 3.0
        elif "Electronics" in branch: base += 1.5
        
        # Add a little noise
        import random
        return base - random.uniform(0, 1.5)

    def clean_text(self, text):
        """Clean and normalize text data."""
        return re.sub(r'\s+', ' ', text).strip()

    def save_data(self, data, filename='mht_cet_data.json'):
        """Save final data to a JSON file after cleaning and de-duplication."""
        if not data:
            logger.error("No data to save!")
            return False

        logger.info("Cleaning and finalizing data...")
        df = pd.DataFrame(data)
        
        # Drop records with missing essential info
        df.dropna(subset=['college', 'branch', 'cutoff_percentile'], inplace=True)
        
        # Standardize branch names for better grouping
        df['branch'] = df['branch'].apply(self._standardize_branch_name)

        # De-duplicate, keeping the highest cutoff for a given college/branch/category combo
        df = df.sort_values('cutoff_percentile', ascending=False)
        df = df.drop_duplicates(subset=['college', 'branch', 'category'], keep='first')
        
        # Sort for final presentation
        df = df.sort_values(['cutoff_percentile', 'college', 'branch'], ascending=[False, True, True])

        # Convert to final JSON format
        final_data = df.to_dict('records')

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(final_data, f, indent=4)
            
        logger.info(f"Successfully saved {len(final_data)} unique records to {filename}")
        return True

    def run(self):
        """Main execution method."""
        logger.info("--- Starting MHT-CET Data Scraper ---")
        
        data = self.scrape_live_data()
        
        if not data:
            data = self.generate_mock_data()
            
        if not data:
            logger.critical("Scraping and mock data generation both failed. Exiting.")
            return False
            
        success = self.save_data(data)
        
        if success:
            logger.info("--- Scraping process completed successfully! ---")
        else:
            logger.error("--- Scraping process failed during file save. ---")

def main():
    """Main function to run the scraper."""
    scraper = MHTCETScraper()
    scraper.run()
    print("\nProcess finished. Check the log and 'mht_cet_data.json' file.")

if __name__ == "__main__":
    main()
