import logging
import time
import re
import numpy as np
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import json

logging.basicConfig(level=logging.INFO)

class Hotelium:
    def __init__(self):
        self.driver = None
        self.hotel_links = []

    def initialize_remote_chromedriver(self):
        logging.info("Initializing ChromeDriver")
        
        self.options = Options()
        self.options.add_argument('--ignore-ssl-errors=yes')
        self.options.add_argument('--ignore-certificate-errors')
        self.options.add_argument("user-agent='userMozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36'")
        self.options.add_argument('--disable-dev-shm-usage')
        self.options.add_argument('--blink-settings=imagesEnabled=false')
        self.options.add_argument('--no-sandbox')
        self.options.add_argument("--headless")
        self.options.add_argument("--disable-gpu")
        self.options.add_argument("--no-sandbox")
        self.options.add_argument("--disable-infobars")
        self.options.add_argument("window-size=1400,1500")
        self.options.add_argument("start-maximized")
        self.options.add_argument("enable-automation")

        try:
            self.driver = webdriver.Chrome(options=self.options)
            logging.info("ChromeDriver initialized successfully")
        except Exception as e:
            logging.error(f"Failed to initialize ChromeDriver: {e}")
            raise

    def fetch_hotel_links(self, search_url, top_n=10):
        logging.info(f"Fetching hotel links from search_url: {search_url}")
        try:
            self.driver.get(search_url)
            close_button = WebDriverWait(self.driver, 20).until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[aria-label="Dismiss sign-in info."]')))
            close_button.click()

            new_links = set()  # To store newly fetched links
            
            while len(new_links) < top_n:  # Stop once we reach top_n links
                scroll_height = self.driver.execute_script("return document.body.scrollHeight")
                scroll_to_position = scroll_height * 0.9
                self.driver.execute_script(f"window.scrollTo(0, {scroll_to_position});")
                time.sleep(2)  # Wait for content to load after scrolling

                try:
                    # Check if the "Load more results" button is present and clickable
                    load_more_button = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'a83ed08757')]//span[text()='Load more results']"))
                    )
                    # Click the "Load more results" button if it is found
                    load_more_button.click()
                    logging.info("Clicked 'Load more results' button")
                    time.sleep(1)  # Wait for new results to load
                except:
                    logging.info("No 'Load more results' button found or clickable.")
                
                # Scrape new hotel links from the page
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                for a in soup.find_all('a', href=True):
                    if re.search(r'/hotel/', a['href']):
                        new_links.add(a['href'])

                # Stop if we have reached top_n hotel links
                if len(new_links) >= top_n:
                    break

            # Convert new_links to a list and ensure no duplicates
            self.hotel_links = list(new_links)[:top_n]
            logging.info(f"Found {len(self.hotel_links)} hotel links")
        except Exception as e:
            logging.error(f"Failed to fetch hotel links: {e}")
            raise Exception

    def extract_all_hotels_data(self):
        logging.info("Extracting data for all hotels")
        all_hotels_data = []
        
        for link in self.hotel_links:
            try:
                start_time = time.time()
                self.driver.get(link)
                WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, 'hprt-table')))
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                hotel_data = self.extract_hotel_data(soup)
                hotel_data['crawl_time'] = time.time() - start_time
                all_hotels_data.append(hotel_data)
            except Exception as e:
                logging.error(f"Failed to extract data for hotel at {link}: {e}")
    
        self.driver.close()
        return all_hotels_data


    def extract_hotel_data(self, soup):
        logging.info("Extracting hotel data")
        return {
            'name': self.extract_hotel_name(soup),
            'address': self.extract_hotel_address(soup),
            'content': self.extract_hotel_content(soup),
            'review_score': self.extract_review_score(soup),
            'review_count': self.extract_review_count(soup),
            'most_facility': self.extract_most_facility(soup),
            'all_facilities': self.extract_all_facilities(soup),
            'rooms': self.extract_room_options(soup)  # Added room extraction
        }

    def extract_hotel_name(self, soup):
        try:
            name = soup.find("h2", {"class": "pp-header__title"}).text
            logging.info(f"Hotel name: {name}")
            return name
        except:
            logging.error("Failed to extract hotel name")
            return None

    def extract_hotel_address(self, soup):
        try:
            address = soup.find("span", {"class": "hp_address_subtitle"}).text.strip("\n")
            logging.info(f"Hotel address: {address}")
            return address
        except:
            logging.error("Failed to extract hotel address")
            return None

    def extract_hotel_content(self, soup):
        try:
            content = soup.find("div", {"class": "hp_desc_main_content"}).text.strip()
            logging.info(f"Hotel content: {content}")
            return content
        except:
            logging.error("Failed to extract hotel content")
            return None

    def extract_review_score(self, soup):
        try:
            rs = soup.find('div', {'data-testid': 'review-score-component'}).text.strip()
            logging.info(f"Review score: {rs}")
            return rs
        except:
            logging.error("Failed to extract review score")
            return None

    def extract_review_count(self, soup):
        try:
            rc = soup.find('div', {'data-testid': 'review-score-component'}).text.split("\xa0·\xa0")[-1]
            logging.info(f"Review count: {rc}")
            return rc
        except:
            logging.error("Failed to extract review count")
            return None

    def extract_most_facility(self, soup):
        try:
            fac = soup.find("div", {"data-testid": "property-most-popular-facilities-wrapper"})
            fac_arr = [text.strip() for text in fac.stripped_strings if text]
            logging.info(f"Most facilities: {fac_arr}")
            return str(fac_arr)
        except:
            logging.error("Failed to extract most facilities")
            return None

    def extract_all_facilities(self, soup):
        try:
            all_facilities = []
            for each in soup.find_all("div", {"class": "e50d7535fa"}):
                t = each.find('div', {'class': 'd1ca9115fe'}).text
                rs = [x.strip() for x in each.stripped_strings if x != t]
                all_facilities.append({'key': t, 'value': rs})
            logging.info(f"All facilities: {all_facilities}")
            return all_facilities
        except:
            logging.error("Failed to extract all facilities")
            return None

    def extract_room_options(self, soup):
        try:
            logging.info("Extracting room options")
            room_options = soup.find('table', {'class': 'hprt-table'})
            rooms = []

            if room_options:
                for row in room_options.find_all('tr', {'class': 'js-rt-block-row'}):
                    room = {}

                    room_name = row.find('a', {'class': 'hprt-roomtype-link'})
                    if room_name:
                        room['room_name'] = room_name.get_text(strip=True)

                    room_capacity = row.find('td', {'class': 'hprt-table-cell-occupancy'})
                    if room_capacity:
                        capacity_text = room_capacity.find('span', {'class': 'bui-u-sr-only'})
                        if capacity_text:
                            match = re.search(r'Max\. people: (\d+)', capacity_text.get_text())
                            if match:
                                room['room_capacity'] = match.group(1)

                    room_price_block = row.find('td', {'class': 'hprt-table-cell-price'})
                    if room_price_block:
                        original_price = room_price_block.find('div', class_='bui-price-display__original')
                        if original_price:
                            room['original_price'] = original_price.get_text(strip=True).replace('\xa0', ' ')

                        current_price = room_price_block.find('div', class_='bui-price-display__value')
                        if current_price:
                            room['current_price'] = current_price.get_text(strip=True).replace('\xa0', ' ')

                        discount = room_price_block.find('div', class_='bui-f-font-body', string=lambda x: 'Late Escape Deal' in x)
                        if discount:
                            discount_amount = discount.find_next('div')
                            if discount_amount:
                                room['discount_amount'] = discount_amount.get_text(strip=True).replace('\xa0', ' ')

                        total_price = room_price_block.find('div', class_='bui-f-font-strong prco-pop-breakdown-element prco-text-nowrap-helper bui-u-text-right')
                        if total_price:
                            room['total_price'] = total_price.get_text(strip=True).replace('\xa0', ' ')

                        deal_info = room_price_block.find('span', {'class': 'hprt-price-table__price-deal-text'})
                        if deal_info:
                            room['deal_info'] = deal_info.get_text(strip=True)

                    rooms.append(room)

            return rooms
        except Exception as e:
            logging.error(f"Error extracting room options: {e}")
            return []
        
    def cleanup(self):
        logging.info("Cleaning up")
        if self.driver:
            self.driver.quit()
            logging.info("ChromeDriver quit successfully")
            
    def benchmark(self, search_url, top_n=10):
        logging.info("Starting crawl process")

        start_time = time.time()
        
        self.fetch_hotel_links(search_url, top_n)
        all_hotels_data = self.extract_all_hotels_data()
        
        end_time = time.time()
        total_time = end_time - start_time
        avg_time_per_hotel = total_time / len(all_hotels_data) if all_hotels_data else float('inf')
        min_time_per_hotel = np.min([hotel['crawl_time'] for hotel in all_hotels_data]) if all_hotels_data else float('inf')
        max_time_per_hotel = np.max([hotel['crawl_time'] for hotel in all_hotels_data]) if all_hotels_data else float('inf')
        
        logging.info(f"Crawl process completed with total {len(all_hotels_data)} hotels")
        logging.info(f"Total time taken: {total_time:.2f} seconds")
        logging.info(f"Average time per hotel: {avg_time_per_hotel:.2f} seconds")
        logging.info(f"Minimum time per hotel: {min_time_per_hotel:.2f} seconds")
        logging.info(f"Maximum time per hotel: {max_time_per_hotel:.2f} seconds")
        
if __name__ == '__main__':
    search_url = "https://www.booking.com/searchresults.html?ss=Ho+Chi+Minh+City%2C+Ho+Chi+Minh+Municipality%2C+Vietnam&ssne=Hue&ssne_untouched=Hue&label=gen173nr-1FCAEoggI46AdIM1gEaPQBiAEBmAExuAEXyAEM2AEB6AEB-AECiAIBqAIDuAKc2IunBsACAdICJDYyMmU4MGQ1LWUzYWQtNGRhZC1iNmEzLWJhOTI5OWVjZTQ1YtgCBeACAQ&aid=304142&lang=en-us&sb=1&src_elem=sb&src=searchresults&dest_id=-3730078&dest_type=city&ac_position=0&ac_click_type=b&ac_langcode=en&ac_suggestion_list_length=5&search_selected=true&search_pageview_id=a98d21b625600091&ac_meta=GhBhOThkMjFiNjI1NjAwMDkxIAAoATICZW46C0hvIENoaSBNaW5oQABKAFAA&checkin=2024-11-21&checkout=2024-11-22&group_adults=2&no_rooms=1&group_children=0"
    
    hotelium = Hotelium()
    hotelium.initialize_remote_chromedriver()
    hotelium.fetch_hotel_links(search_url, top_n=100)
    all_hotels_data = hotelium.extract_all_hotels_data()
    
    with open('hotels_data_2024-11-21.json', 'w') as f:
        json.dump(all_hotels_data, f, indent=2)
        
    hotelium.cleanup()