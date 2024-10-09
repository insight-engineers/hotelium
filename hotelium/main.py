from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
from tqdm import tqdm
import re
import os
import json
import time
import requests
import numpy as np
import pandas as pd
import multiprocessing as mp

pd.options.mode.chained_assignment = None  # default='warn'

def initialize_chromedriver(remote_webdriver:str="localhost")->webdriver.Chrome:
    prefs = {"profile.default_content_setting_values.geolocation": 2}
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--deny-permission-prompts")
    options.add_experimental_option("prefs", prefs)
    try:
        driver = webdriver.Remote(f'http://{remote_webdriver}:4444/wd/hub', options=options)
    except:
        raise Exception("Failed to install ChromeDriver")
    return driver

def try_element(driver,xpath):
    try:
        return driver.find_element(By.CSS_SELECTOR, xpath).text
    except:
        return np.nan


def extract_hotel_links(url,processed_links):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36"}
    resp = requests.get(url, headers=headers)
    soup = BeautifulSoup(resp.text, 'html.parser')
    property_cards = soup.find_all("div",{"data-testid":"property-card"})
    properties = []
    for property in property_cards:
          new_property = {}
          try:
              new_property['link'] = property.find('a',{'data-testid':'title-link'}).get('href').replace("en-gb.html","vi.html")
          except:
              new_property['link'] = np.nan
          # Skip if duplicate
          if new_property['link'] in processed_links:
              continue
          try:
              new_property['hotel_name'] = property.find('div',{'data-testid':'title'}).text
          except:
              new_property['hotel_name'] = np.nan
          try:
              review_score, review_count = property.find('div',{'data-testid':'review-score'})
              new_property['review_score'] = review_score.text.strip()
              new_property['review_count'] = review_count.text.split(" ")[-3]
          except:
              new_property['review_score'] = np.nan
              new_property['review_count'] = np.nan
          try:
              new_property['price'] = property.find('span',{'data-testid':'price-and-discounted-price'}).text
          except:
              new_property['price'] = np.nan
          try:
              new_property['address'] = property.find('span',{'data-testid':'address'}).text
          except:
              new_property['address'] = np.nan
          try:
              new_property['image'] = property.find('img',{'data-testid':'image'}).get('src')
          except:
              new_property['image'] = np.nan
          properties.append(new_property)
          processed_links.append(new_property['link'])
    return properties,processed_links

def extract_hotel_properties(target_url):
    headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36"}
    resp = requests.get(target_url, headers=headers)
    soup = BeautifulSoup(resp.text, 'html.parser')

    o={}
    o['link'] = str(target_url)
    try:
        o["name"]=soup.find("h2",{"class":"pp-header__title"}).text
    except:
        o["name"] =np.nan
    try:
        o["address"]=soup.find("span",{"class":"hp_address_subtitle"}).text.strip("\n")
    except:
        o["address"] = np.nan
    try:
        o["content"] = soup.find("div", {"class": "hp_desc_main_content"}).text.strip()
    except:
        o["content"] = np.nan
    try:
        rs, rc = soup.find('div',{'data-testid':'review-score-component'})
        o['review_score'] = rs.text.strip()
    except:
        o['review_score'] = np.nan
    try:
        o['review_count'] = rc.text.split("\xa0·\xa0")[-1]
    except:
        o['review_count'] = np.nan

    try:
        fac=soup.find("div",{"data-testid":"property-most-popular-facilities-wrapper"})
        fac_arr = []
        for i in range(len(fac.find_all("span"))):
            all_fac = fac.find_all("span")
            text = all_fac[i].text.strip()
            if text != "" and text not in fac_arr:
                fac_arr.append(text)
        o['most_facility'] = str(fac_arr)
    except:
        o['most_facility'] = np.nan

    try:
        all_facilities = []
        for each in soup.find_all("div",{"class":"d4f5f4db7f"}):
            t = each.find('div',{'class':'a432050e3a'}).text
            rs=[]
            for a in each.find_all("span"):
                x = a.text.replace(t,'').strip()
                if x !='' and x not in rs:
                    rs.append(a.text.replace(t,'').strip())
            all_facilities.append({'key':t,'value':rs})
        o['all_facilities'] = all_facilities
    except:
        o['all_facilities'] = np.nan

    try:
      tr = soup.find_all("tr")
    except:
      tr = None

    dataset = []
    temp = {}
    for y in range(0,len(tr)):
      try:
          datapoint = {}
          id = tr[y].get('data-block-id')
          maxp = tr[y].find("span",{"class":"bui-u-sr-only"}).text.strip()
          room_fac = tr[y].find_all("div",{"class":"hprt-facilities-facility"})
          try:
            room_price = tr[y].find("span",{"class":"prco-valign-middle-helper"}).text.strip()
          except:
            room_price = np.nan
          try:
            roomtype = tr[y].find("a",{"class":"hprt-roomtype-link"}).text.strip()
          except:
            roomtype = np.nan
            id_pre = tr[y-1].get('data-block-id')
            if id.split("_")[0] == id_pre.split("_")[0]:
              temp['room_price'] = room_price
              temp['maxp'] = maxp
              dataset[-1]['price/max_person'].append(str(temp['room_price'])+" / "+str(temp['maxp']))
              continue
      except:
          id = None

      if( id is not None) and id !='':
          datapoint['roomtype'] = roomtype
          datapoint['room_facs'] = [rf.text for rf in room_fac]
          datapoint['price/max_person'] = [str(room_price)+" / "+str(maxp)]
          dataset.append(datapoint)
    o['rooms'] = dataset

    return o

def extract_reviews(driver,url):
    id_url = url.split("?label")[0].split("/")[-1].split(".")[0]
    if "reviews_" + id_url + ".json" in os.listdir():
        return 0

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36"}
    driver.get(url)
    try:
        expand = driver.find_element(By.XPATH, './/button[contains(@data-testid, "fr-read-all-reviews")]')
        driver.execute_script("arguments[0].click();", expand)
        try:
            time.sleep(2)
            rvs_ = driver.find_element(By.XPATH, '//*[@id="review_list_page_container"]')
            page_nums = rvs_.find_elements(By.CSS_SELECTOR, 'a[class="bui-pagination__link"]')
            pages = int(page_nums[len(page_nums) - 1].find_element(By.CSS_SELECTOR, 'span[aria-hidden="true"]').text)
        except:
            pages = 1
    except:
        pages = 0

    reviews = []
    if pages > 1:
        reviews_link = str(page_nums[len(page_nums) - 1].get_attribute('href'))
        page_id = reviews_link[reviews_link.find('offset='):reviews_link.find('offset=') + 9]
        for i in range(pages):
            newset = "offset" + "=" + str(i * 10)
            new_url = reviews_link.replace(page_id, newset)
            resp = requests.get(new_url, headers=headers)
            soup = BeautifulSoup(resp.text, 'html.parser')
            rvs = soup.find_all('div', {'class': 'c-review-block'})
            for rv in rvs:
                try:
                    date = rv.find('span', {'class': 'c-review-block__date'}).text.replace('\n', '')
                    if int(date.split("/")[-1]) < 2015:
                        continue
                except:
                    date = np.nan
                try:
                    title = rv.find('h3').text.replace('\n', '')
                except:
                    title = np.nan
                try:
                    score = rv.find('div', {'class': 'bui-review-score c-score'}).text.replace('\n', '')
                except:
                    score = np.nan
                try:
                    content = rv.find('div', {'class': 'c-review'}).text.replace('\n', '')
                except:
                    content = np.nan
                try:
                    user = rv.find('span', {'class': 'bui-avatar-block__title'}).text.replace('\n', '')
                except:
                    user = np.nan
                try:
                    country = rv.find('span', {'class': 'bui-avatar-block__subtitle'}).text.replace('\n', '')
                except:
                    country = np.nan
                reviews.append({"date": date, "title": title, "content": content, "score": score, "user": user,
                                "country": country,"url":url })
    elif pages == 1:
        ## Get review when have only 1 review page
        rvs = rvs_.find_elements(By.XPATH, ".//div[@class='c-review-block']")
        for rv in rvs:
            date = try_element(rv,'span[class="c-review-block__date"]')
            title = try_element(rv, 'h3')
            score = try_element(rv, 'div[class="bui-review-score c-score"]')
            content = try_element(rv, 'div[class="c-review"]')
            user = try_element(rv, 'span[class="bui-avatar-block__title"]')
            country = try_element(rv, 'span[class="bui-avatar-block__subtitle"]')
            reviews.append({"date": date, "title": title, "content": content, "score": score, "user": user,
                            "country": country,"url":url})
    else:
        reviews = np.nan
    driver.quit()

    # Save reviews as url_id
    filename = "reviews_"+id_url+".json"
    with open(filename, "w", encoding='utf8') as file:
        json.dump(reviews, file, ensure_ascii=False)

def merge_json_files(file_paths,save_name):
    merged_contents = []
    sum = 0
    for file_path in file_paths:
        with open(file_path, 'r', encoding='utf-8') as file_in:
            content_i = json.load(file_in)
            if str(content_i) != 'nan':
                merged_contents.extend(content_i)
                sum = sum + 1
    print("Total hotels that have reviews: ",sum)
    print("Total reviews: ",len(merged_contents)," , Save as: ",save_name)
    with open(save_name , 'w', encoding='utf-8') as file_out:
        json.dump(merged_contents, file_out, ensure_ascii=False)

def crawling_from_booking(driver, url, skip_extract_reviews = False):
    data_path = os.path.join(os.getcwd(),"data", "booking")
    os.makedirs(data_path, exist_ok=True)

    # Request bs4
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36"}
    resp = requests.get(url, headers=headers)
    page_soup = BeautifulSoup(resp.text, 'html.parser')

    # Get Save Name
    location = page_soup.find("input", {"name": "ss"}).get('value').replace(" ", "_")
    date = page_soup.find("div", {"data-testid": "searchbox-dates-container"}).text
    save_name = location + "_" + re.sub('[^A-Za-z0-9á]+', '_', date)
    save_path = os.path.join(os.getcwd(),"data","booking",save_name)
    os.makedirs(save_path, exist_ok=True)
    print(f"Save name: {save_name}")

    # Total search pages
    try:
        total_pages = int(page_soup.find_all("div",{"data-testid":"pagination"})[0].find_all('li')[-1].text)
    except:
        total_pages = 1
    print(f"Total search pages: {total_pages}")

    # Extract Hotels Properties
    os.chdir(data_path)
    if str("hotels_"+save_name + ".csv") not in os.listdir():
        driver.get(url)
        # Extract Hotels URL from search pages
        properties = []
        processed_links  = []
        for current_page in range(total_pages):
            print(f"Processing page {current_page + 1} of {total_pages}")
            new_properties,processed_links = extract_hotel_links(driver.current_url,processed_links)
            properties = properties + new_properties
            if total_pages > 1:
                if int(current_page) == 0:
                    try:
                        time.sleep(1)
                        skip_ad = driver.find_element(By.XPATH, '//button[contains(@aria-label, "Dismiss sign in information.")]')
                        driver.execute_script("arguments[0].click();", skip_ad)
                        time.sleep(1)
                    except:
                        pass
                next_page_btn = driver.find_element(By.XPATH, '//button[contains(@aria-label, "Next page")]')
                driver.execute_script("arguments[0].click();", next_page_btn)
                time.sleep(1)
        driver.quit()

        print(f"Total hotels: {len(properties)}")
        data_search = pd.DataFrame(properties)

        # Extract properties
        data_hotels = []
        for idx, link in enumerate(tqdm(data_search['link']), start=1):
            print(f"Extracting properties for hotel {idx} of {len(data_search['link'])}")
            o = extract_hotel_properties(link)
            o['id_url'] = link.split("?label")[0].split("/")[-1].split(".")[0]
            data_hotels.append(o)
        # Save Hotels Data
        data_search = pd.DataFrame(data_hotels)
        data_search.to_csv(os.path.join(data_path,"hotels_"+save_name+".csv"),encoding='utf-16')
    else:
        data_search = pd.read_csv(os.path.join(data_path,"hotels_"+save_name+".csv"))

    # Extract Reviews
    if not skip_extract_reviews:
        os.chdir(save_path)
        with mp.Pool(8) as p:
            p.map(extract_reviews, data_search['link'])

    # Merge all reviews
    final_reviews_name = os.path.join(data_path, "reviews_" +save_name + ".json")
    merge_json_files(os.listdir(),final_reviews_name)

    print(f"Completed crawling for {save_name}")

def crawl_until_done(url):
    try:
        start_time = time.time()
        crawling_from_booking(url)
        print("Time process: ", time.time() - start_time)
    except:
        print("Time process: ", time.time() - start_time)
        print("Recrawl")
        crawl_until_done(url)

if __name__ == '__main__':
    url1 = "https://www.booking.com/searchresults.en-gb.html?ss=Dong+Nai%2C+Vietnam&ssne=Nha+Trang&ssne_untouched=Nha+Trang&label=gen173nr-1BCAEoggI46AdIM1gEaPQBiAEBmAEJuAEXyAEM2AEB6AEBiAIBqAIDuAKTyIenBsACAdICJDFlMWMzMTZkLWYyNmItNGI3Zi04NjA1LTg0OTg0MTQwNGRjY9gCBeACAQ&sid=061d914f8e154e41e540f0a383ec0301&aid=304142&lang=en-gb&sb=1&src_elem=sb&src=searchresults&dest_id=6884&dest_type=region&ac_position=0&ac_click_type=b&ac_langcode=en&ac_suggestion_list_length=5&search_selected=true&search_pageview_id=ed3d4665dcdd0144&ac_meta=GhBlZDNkNDY2NWRjZGQwMTQ0IAAoATICZW46CGRvbmcgbmFpQABKAFAA&checkin=2023-09-01&checkout=2023-09-02&group_adults=2&no_rooms=1&group_children=0"
    url2 = "https://www.booking.com/searchresults.en-gb.html?ss=B%E1%BA%BFn+Tre&ssne=%C4%90%C3%A0+N%E1%BA%B5ng&ssne_untouched=%C4%90%C3%A0+N%E1%BA%B5ng&label=gen173nr-1BCAEoggI46AdIM1gEaPQBiAEBmAEquAEXyAEM2AEB6AEBiAIBqAIDuALdr4mnBsACAdICJDVkMjIwNTE5LTIwMDYtNDI0OS1hNWQ2LTc5ZDhlNGJiYjRkY9gCBeACAQ&sid=061d914f8e154e41e540f0a383ec0301&aid=304142&lang=vi&sb=1&src_elem=sb&src=index&dest_id=6888&dest_type=region&ac_position=0&ac_click_type=b&ac_langcode=vi&ac_suggestion_list_length=5&search_selected=true&search_pageview_id=aed3802f9ba001f1&ac_meta=GhBhZWQzODAyZjliYTAwMWYxIAAoATICdmk6CULhur9uIFRyZUAASgBQAA%3D%3D&checkin=2023-09-11&checkout=2023-09-12&group_adults=2&no_rooms=1&group_children=0&sb_travel_purpose=leisure"
    url3 = "https://www.booking.com/searchresults.html?ss=Dong+Thap%2C+Vietnam&ssne=Nha+Trang&ssne_untouched=Nha+Trang&label=gen173nr-1FCAEoggI46AdIM1gEaPQBiAEBmAExuAEXyAEM2AEB6AEB-AECiAIBqAIDuAKc2IunBsACAdICJDYyMmU4MGQ1LWUzYWQtNGRhZC1iNmEzLWJhOTI5OWVjZTQ1YtgCBeACAQ&aid=304142&lang=en-us&sb=1&src_elem=sb&src=searchresults&dest_id=6890&dest_type=region&ac_position=0&ac_click_type=b&ac_langcode=en&ac_suggestion_list_length=5&search_selected=true&search_pageview_id=10e22195bd450125&ac_meta=GhAxMGUyMjE5NWJkNDUwMTI1IAAoATICZW46DcSQ4buTbmcgVGjDoXBAAEoAUAA%3D&checkin=2023-09-13&checkout=2023-09-14&group_adults=2&no_rooms=1&group_children=0"
    url4 = "https://www.booking.com/searchresults.html?ss=Ho+Chi+Minh+City%2C+Ho+Chi+Minh+Municipality%2C+Vietnam&ssne=Hue&ssne_untouched=Hue&label=gen173nr-1FCAEoggI46AdIM1gEaPQBiAEBmAExuAEXyAEM2AEB6AEB-AECiAIBqAIDuAKc2IunBsACAdICJDYyMmU4MGQ1LWUzYWQtNGRhZC1iNmEzLWJhOTI5OWVjZTQ1YtgCBeACAQ&aid=304142&lang=en-us&sb=1&src_elem=sb&src=searchresults&dest_id=-3730078&dest_type=city&ac_position=0&ac_click_type=b&ac_langcode=en&ac_suggestion_list_length=5&search_selected=true&search_pageview_id=a98d21b625600091&ac_meta=GhBhOThkMjFiNjI1NjAwMDkxIAAoATICZW46C0hvIENoaSBNaW5oQABKAFAA&checkin=2024-11-21&checkout=2024-11-22&group_adults=2&no_rooms=1&group_children=0"
    url_test ="https://www.booking.com/searchresults.html?ss=Ha+Giang%2C+Vietnam&label=gen173nr-1FCAEoggI46AdIM1gEaPQBiAEBmAExuAEHyAEM2AEB6AEB-AECiAIBqAIDuALvifamBsACAdICJDJkZGI2YmM2LTMxMzQtNGM1Yi04MWNjLWI2NTVkMDM0NWQ0OdgCBeACAQ&aid=304142&lang=en-us&sb=1&src_elem=sb&src=index&dest_id=6906&dest_type=region&ac_position=1&ac_click_type=b&ac_langcode=en&ac_suggestion_list_length=5&search_selected=true&search_pageview_id=b48710f70163005c&ac_meta=GhBiNDg3MTBmNzAxNjMwMDVjIAEoATICZW46CEhBIGdpYW5nQABKAFAA&checkin=2023-08-26&checkout=2023-08-27&group_adults=2&no_rooms=1&group_children=0&sb_travel_purpose=leisure"

    start_time = time.time()
    driver = initialize_chromedriver()
    crawling_from_booking(driver=driver,url=url4)
    print("Time process: ", time.time() - start_time)