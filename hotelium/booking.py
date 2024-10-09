from seleniumwire import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from tqdm import tqdm
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import re
import os
import json
import time
import requests
import numpy as np
import pandas as pd
import multiprocessing as mp
import unicodedata
pd.options.mode.chained_assignment = None  # default='warn'

def norm_text(text):
    return unicodedata.normalize('NFD', text).encode('ascii', 'ignore').decode()

def fix_link(u, to="vi"):
    id = u.find(".html")
    if to == "vi":
        if u[int(id - 5):int(id)] != "en-gb" and u[int(id - 2):int(id)] != "vi":
            return u.replace(".html", ".vi.html")
        else:
            return u.replace("en-gb.html", "vi.html")
    elif to == "en":
        if u[int(id - 2):int(id)] == "vi":
            return u.replace("vi.html", "en-gb.html")

def try_element(driver,xpath):
    try:
        return driver.find_element(By.CSS_SELECTOR, xpath).text
    except:
        return np.nan

def extract_hotel_links(url, processed_links):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36"}
    resp = requests.get(url, headers=headers)
    soup = BeautifulSoup(resp.text, 'html.parser')
    property_cards = soup.find_all("div", {"data-testid": "property-card"})
    properties = []
    for property in property_cards:
        new_property = {}
        try:
            link = property.find('a', {'data-testid': 'title-link'}).get('href')
            new_property['link'] = fix_link(link)
        except:
            new_property['link'] = np.nan
        # Skip if duplicate
        if new_property['link'] in processed_links:
            continue
        try:
            new_property['hotel_name'] = property.find('div', {'data-testid': 'title'}).text
        except:
            new_property['hotel_name'] = np.nan
        try:
            review_score, review_count = property.find('div', {'data-testid': 'review-score'})
            new_property['review_score'] = review_score.text.strip()
            new_property['review_count'] = review_count.text.split(" ")[-3]
        except:
            new_property['review_score'] = np.nan
            new_property['review_count'] = np.nan
        try:
            new_property['price'] = property.find('span', {'data-testid': 'price-and-discounted-price'}).text
        except:
            new_property['price'] = np.nan
        try:
            new_property['address'] = property.find('span', {'data-testid': 'address'}).text
        except:
            new_property['address'] = np.nan
        try:
            new_property['image'] = property.find('img', {'data-testid': 'image'}).get('src')
        except:
            new_property['image'] = np.nan
        properties.append(new_property)
        processed_links.append(new_property['link'])
    return properties, processed_links

def get_properties(target_url,cookies=''):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36"}
    if str(cookies) != '':
        s = requests.Session()
        for cookie in cookies:
            s.cookies.set(cookie['name'], cookie['value'])
        resp = s.get(target_url, headers=headers)
    else:
        resp = requests.get(target_url, headers=headers)
    soup = BeautifulSoup(resp.text, 'html.parser')

    o = {}
    o['link'] = str(target_url)
    try:
        o["name"] = soup.find("h2", {"class": "pp-header__title"}).text
    except:
        o["name"] = np.nan
    try:
        o["address"] = soup.find("span", {"class": "hp_address_subtitle"}).text.strip("\n")
    except:
        o["address"] = np.nan
    try:
        o["content"] = soup.find("div", {"class": "hp_desc_main_content"}).text.strip()
    except:
        o["content"] = np.nan
    try:
        rs, rc = soup.find('div', {'data-testid': 'review-score-component'})
        o['review_score'] = rs.text.strip()
    except:
        o['review_score'] = np.nan
    try:
        o['review_count'] = rc.text.split("\xa0·\xa0")[-1]
    except:
        o['review_count'] = np.nan

    rate_dict = {}
    for p in soup.find_all("div", {"data-testid": "review-subscore"}):
        rate_dict[' '.join(p.text.split(" ")[:-1])] = p.text.split(" ")[-1]
    o['sub_rating'] = rate_dict

    try:
        try:
            o['rating_star'] = len(soup.find("span", {"data-testid": "rating-stars"}).find_all("span"))
            # print(len(sub_page_soup.find("span", {"data-testid": "rating-stars"}).find_all("span")))
        except:
            o['rating_star'] = len(soup.find("span", {"data-testid": "rating-squares"}).find_all("span"))
            # print(len(sub_page_soup.find("span", {"data-testid": "rating-squares"}).find_all("span")))
    except:
        o['rating_star'] = np.nan

    try:
        fac = soup.find("div", {"data-testid": "property-most-popular-facilities-wrapper"})
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
        for each in soup.find_all("div", {"class": "d4f5f4db7f"}):
            t = each.find('div', {'class': 'a432050e3a'}).text
            rs = []
            for a in each.find_all("span"):
                x = a.text.replace(t, '').strip()
                if x != '' and x not in rs:
                    rs.append(a.text.replace(t, '').strip())
            all_facilities.append({'key': t, 'value': rs})
        o['all_facilities'] = all_facilities
    except:
        o['all_facilities'] = np.nan

    try:
        tr = soup.find_all("tr")
    except:
        tr = None

    dataset = []
    temp = {}
    for y in range(0, len(tr)):
        try:
            datapoint = {}
            id = tr[y].get('data-block-id')
            maxp = tr[y].find("span", {"class": "bui-u-sr-only"}).text.strip()
            room_fac = tr[y].find_all("div", {"class": "hprt-facilities-facility"})
            try:
                room_price = tr[y].find("span", {"class": "prco-valign-middle-helper"}).text.strip()
            except:
                room_price = np.nan
            try:
                roomtype = tr[y].find("a", {"class": "hprt-roomtype-link"}).text.strip()
            except:
                roomtype = np.nan
                id_pre = tr[y - 1].get('data-block-id')
                if id.split("_")[0] == id_pre.split("_")[0]:
                    temp['room_price'] = room_price
                    temp['maxp'] = maxp
                    dataset[-1]['price/max_person'].append(str(temp['room_price']) + " / " + str(temp['maxp']))
                    continue
        except:
            id = None

        if (id is not None) and id != '':
            datapoint['roomtype'] = roomtype
            datapoint['room_facs'] = [rf.text for rf in room_fac]
            datapoint['price/max_person'] = [str(room_price) + " / " + str(maxp)]
            dataset.append(datapoint)
    o['rooms'] = dataset

    return o

def extract_properties(urls,url6):
    # Get Date Cookies
    options = Options()
    options.add_argument("start-maximized")
    driver = webdriver.Chrome(options=options)
    driver.get(fix_link(url6,to="en"))

    # print(driver.find_elements(By.CSS_SELECTOR, 'table[role="grid"]')[-1])
    try:
        tab2 = driver.find_elements(By.CSS_SELECTOR, 'table[role="grid"]')[-1]
    except:
        expand = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-testid="searchbox-dates-container"]')))
        expand.click()
        tab2 = driver.find_elements(By.CSS_SELECTOR, 'table[role="grid"]')[-1]

    tab3 = tab2.find_elements(By.CSS_SELECTOR, 'td[role="gridcell"]')[-2]
    element = WebDriverWait(tab3, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR,'*')))
    element.click()
    # print(tab3.text)
    # element = WebDriverWait(tab2, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'td[role="gridcell"]>:last-child')))
    # element.click()
    try:
        skip_ad = driver.find_element(By.XPATH,'//button[contains(@aria-label, "Dismiss sign in information.")]')
        driver.execute_script("arguments[0].click();", skip_ad)
    except:
        pass
    submit = WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'button[type="submit"]')))
    submit.click()
    cookies = driver.get_cookies()
    driver.quit()

    new_data = []
    for hotel_url in tqdm(urls):
        d = get_properties(hotel_url, cookies)
        new_data.append(d)
        # print(d["rooms"])
    data = pd.DataFrame(new_data)
    return data

def get_reviews(url,cookies=''):
    s = requests.Session()
    for cookie in cookies:
        s.cookies.set(cookie['name'], cookie['value'])
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36"}
    id_url = url.split("?label")[0].split("/")[-1].split(".")[0]
    resp = s.get(url, headers=headers)
    soup = BeautifulSoup(resp.text, 'html.parser')
    rvs = soup.find_all('div', {'class': 'c-review-block'})
    reviews = []
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
                        "country": country, "url": url, "id_url": id_url})
    return reviews

def extract_reviews(url):
    # Check if duplicate

    id_url = url.split("?label")[0].split("/")[-1].split(".")[0]
    if "reviews_" + id_url + ".json" in os.listdir():
        return 0

    # Change to Vietnamese
    url = fix_link(url)

    # Total Review
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36"}
    resp = requests.get(url, headers=headers)
    page_soup = BeautifulSoup(resp.text, 'html.parser')
    try:
        rvc = (page_soup.find("div", {"data-testid": "review-score-component"}).text.split("\xa0·\xa0")[-1])
        total_reviews = rvc.split(" ")[0].replace(".", "").replace(",", "")
    except:
        total_reviews = 0

    # Count total search pages
    total_pages = int(total_reviews) // 10
    _ = int(total_reviews) % 10
    if _ != 0:
        total_pages = total_pages + 1

    reviews = []
    new_urls = []
    # Get pages and Extract Reviews
    if total_pages >=1:
        options = Options()
        options.add_argument("start-maximized")
        driver = webdriver.Chrome(options=options)
        driver.get(url)
        if total_pages > 1:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.XPATH, './/button[contains(@data-testid, "fr-read-all-reviews")]')))
            expand = driver.find_element(By.XPATH, './/button[contains(@data-testid, "fr-read-all-reviews")]')
            # expand.click()
            driver.execute_script("arguments[0].click();", expand)
            rvs_ = driver.find_element(By.XPATH, '//*[@id="review_list_page_container"]')
            time.sleep(2)
            page_nums = rvs_.find_elements(By.CSS_SELECTOR, 'a[class="bui-pagination__link"]')
            reviews_link = str(page_nums[len(page_nums) - 1].get_attribute('href'))
            page_id = reviews_link[reviews_link.find('offset='):]
            for i in range(total_pages):
                newset = "offset" + "=" + str(i * 10)
                new_urls.append(reviews_link.replace(page_id, newset))
            # print(">1: ",total_pages, url)
        else:
            # print(url)
            new_urls = []
            # expand = driver.find_element(By.XPATH, './/button[contains(@data-testid, "fr-read-all-reviews")]')
            # driver.execute_script("arguments[0].click();", expand)
            expand = WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.XPATH, './/button[contains(@data-testid, "fr-read-all-reviews")]')))
            # expand = driver.find_element(By.XPATH, './/button[contains(@data-testid, "fr-read-all-reviews")]')
            # expand.click()
            driver.execute_script("arguments[0].click();", expand)
            try:
                WebDriverWait(driver, 20).until(EC.presence_of_element_located(
                    (By.XPATH, ".//div[@class='c-review-block']")))
            # rvs = driver.find_element(By.XPATH, '//*[@id="review_list_page_container"]')
                rvs_ = driver.find_elements(By.XPATH, ".//div[@class='c-review-block']")
                for rv in rvs_:
                    date = try_element(rv,'span[class="c-review-block__date"]')
                    title = try_element(rv, 'h3')
                    score = try_element(rv, 'div[class="bui-review-score c-score"]')
                    content = try_element(rv, 'div[class="c-review"]')
                    user = try_element(rv, 'span[class="bui-avatar-block__title"]')
                    country = try_element(rv, 'span[class="bui-avatar-block__subtitle"]')
                    reviews.append({"date": date, "title": title, "content": content, "score": score, "user": user,
                                    "country": country,"url":url,"id_url":id_url})
                # print("1 page: ",total_pages, url, reviews)
            except:
                reviews = []
                new_urls = []
                print("0 Reviews by Error: ", url)
        driver.quit()
    else:
        # print("0 Reviews",url)
        pass

    # Extract Reviews
    for new_url in new_urls:
        reviews = reviews + get_reviews(new_url)

    # Save reviews as url_id
    filename = "reviews_" + id_url + ".json"
    with open(filename, "w", encoding='utf8') as file:
        json.dump(reviews, file, ensure_ascii=False)

def merge_json_files(file_paths, save_name):
    merged_contents = []
    sum = 0
    for file_path in file_paths:
        with open(file_path, 'r', encoding='utf-8') as file_in:
            content_i = json.load(file_in)
            if str(content_i) != 'nan':
                merged_contents.extend(content_i)
                if str(content_i) !='[]':
                    sum = sum + 1
    print("Total hotels that have reviews: ", sum)
    print("Total reviews: ", len(merged_contents), " , Save as: ", save_name)
    with open(save_name, 'w', encoding='utf-8') as file_out:
        json.dump(merged_contents, file_out, ensure_ascii=False)

def crawling_from_booking(url,filter_name=''):
    data_path = os.path.join("D:/AISIA","data_booking")
    options = Options()
    options.add_argument("start-maximized")

    # Request bs4
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36"}
    # resp = requests.get(fix_link(url, to='en'), headers=headers)
    resp = requests.get(url, headers=headers)
    page_soup = BeautifulSoup(resp.text, 'html.parser')

    # Get Save Name
    location = norm_text(page_soup.find("input", {"name": "ss"}).get('value').replace(" ", "_").replace(".", "_").replace("__","_"))
    date = norm_text(page_soup.find("div", {"data-testid": "searchbox-dates-container"}).text)
    save_name = norm_text(filter_name + "_" + location + "_" + re.sub('[^A-Za-z0-9á]+', '_', date))
    save_path = os.path.join(data_path,filter_name + "_" + location)
    try:
        os.makedirs(save_path)
    except:
        pass
    print(save_name)

    # Total search pages
    try:
        total_pages = int(page_soup.find_all("div", {"data-testid": "pagination"})[0].find_all('li')[-1].text)
    except:
        total_pages = 1
    print(f"Total search pages: {total_pages}")

    # Extract Hotels Properties
    os.chdir(data_path)
    if str("hotels_" + save_name + ".csv") not in os.listdir():
        driver = webdriver.Chrome(options=options)
        driver.get(url)
        # print(driver.find_elements(By.CSS_SELECTOR, 'table[role="grid"]')[-1])
        # Extract Hotels URL from search pages
        properties = []
        processed_links = []
        for current_page in range(total_pages):
            del driver.requests  # processed_links to avoid duplicate Hotel on search pages
            new_properties, processed_links = extract_hotel_links(driver.current_url, processed_links)
            properties = properties + new_properties
            if total_pages > 1:
                try:
                    next_page_btn = driver.find_element(By.XPATH, '//button[contains(@aria-label, "Next page")]')
                except:
                    next_page_btn = driver.find_element(By.XPATH, '//button[contains(@aria-label, "Trang sau")]')
                driver.execute_script("arguments[0].click();", next_page_btn)
                time.sleep(1)
        # Get Date Cookies
        try:
            time.sleep(2)
            skip_ad = driver.find_element(By.XPATH,
                                          '//button[contains(@aria-label, "Dismiss sign in information.")]')
            driver.execute_script("arguments[0].click();", skip_ad)
            time.sleep(2)
        except:
            pass
        driver.quit()
        data_urls = pd.DataFrame(properties)

        # # Extract properties
        print("Extract Hotels Properties")
        data_search = extract_properties(data_urls['link'], url6)
        # data_search.insert(3, "rating_star", str(save_name.split("_")[0]))
        data_search.to_csv(os.path.join(data_path, "hotels_" + save_name + ".csv"))
    else:
        print("Already have hotels CSV file, Skip Extract Hotels Properties!")
        data_search = pd.read_csv(os.path.join(data_path, "hotels_" + save_name + ".csv"))
    print("Total hotels: ", len(data_search["link"]))

    # Extract Reviews
    os.chdir(save_path)
    with mp.Pool(4) as p:
        p.map(extract_reviews, data_search['link'])

    # Merge all reviews
    final_reviews_name = os.path.join(data_path, "reviews_" + save_name + ".json")
    merge_json_files(os.listdir(), final_reviews_name)

if __name__ == '__main__':
    url1 = "https://www.booking.com/searchresults.en-gb.html?ss=Dong+Nai%2C+Vietnam&ssne=Nha+Trang&ssne_untouched=Nha+Trang&label=gen173nr-1BCAEoggI46AdIM1gEaPQBiAEBmAEJuAEXyAEM2AEB6AEBiAIBqAIDuAKTyIenBsACAdICJDFlMWMzMTZkLWYyNmItNGI3Zi04NjA1LTg0OTg0MTQwNGRjY9gCBeACAQ&sid=061d914f8e154e41e540f0a383ec0301&aid=304142&lang=en-gb&sb=1&src_elem=sb&src=searchresults&dest_id=6884&dest_type=region&ac_position=0&ac_click_type=b&ac_langcode=en&ac_suggestion_list_length=5&search_selected=true&search_pageview_id=ed3d4665dcdd0144&ac_meta=GhBlZDNkNDY2NWRjZGQwMTQ0IAAoATICZW46CGRvbmcgbmFpQABKAFAA&checkin=2023-09-01&checkout=2023-09-02&group_adults=2&no_rooms=1&group_children=0"
    url2 = "https://www.booking.com/searchresults.en-gb.html?ss=B%E1%BA%BFn+Tre&ssne=%C4%90%C3%A0+N%E1%BA%B5ng&ssne_untouched=%C4%90%C3%A0+N%E1%BA%B5ng&label=gen173nr-1BCAEoggI46AdIM1gEaPQBiAEBmAEquAEXyAEM2AEB6AEBiAIBqAIDuALdr4mnBsACAdICJDVkMjIwNTE5LTIwMDYtNDI0OS1hNWQ2LTc5ZDhlNGJiYjRkY9gCBeACAQ&sid=061d914f8e154e41e540f0a383ec0301&aid=304142&lang=vi&sb=1&src_elem=sb&src=index&dest_id=6888&dest_type=region&ac_position=0&ac_click_type=b&ac_langcode=vi&ac_suggestion_list_length=5&search_selected=true&search_pageview_id=aed3802f9ba001f1&ac_meta=GhBhZWQzODAyZjliYTAwMWYxIAAoATICdmk6CULhur9uIFRyZUAASgBQAA%3D%3D&checkin=2023-09-11&checkout=2023-09-12&group_adults=2&no_rooms=1&group_children=0&sb_travel_purpose=leisure"
    url3 = "https://www.booking.com/searchresults.html?ss=Dong+Thap%2C+Vietnam&ssne=Nha+Trang&ssne_untouched=Nha+Trang&label=gen173nr-1FCAEoggI46AdIM1gEaPQBiAEBmAExuAEXyAEM2AEB6AEB-AECiAIBqAIDuAKc2IunBsACAdICJDYyMmU4MGQ1LWUzYWQtNGRhZC1iNmEzLWJhOTI5OWVjZTQ1YtgCBeACAQ&aid=304142&lang=en-us&sb=1&src_elem=sb&src=searchresults&dest_id=6890&dest_type=region&ac_position=0&ac_click_type=b&ac_langcode=en&ac_suggestion_list_length=5&search_selected=true&search_pageview_id=10e22195bd450125&ac_meta=GhAxMGUyMjE5NWJkNDUwMTI1IAAoATICZW46DcSQ4buTbmcgVGjDoXBAAEoAUAA%3D&checkin=2023-09-13&checkout=2023-09-14&group_adults=2&no_rooms=1&group_children=0"
    url4 = "https://www.booking.com/searchresults.html?ss=Ho+Chi+Minh+City%2C+Ho+Chi+Minh+Municipality%2C+Vietnam&ssne=Hue&ssne_untouched=Hue&label=gen173nr-1FCAEoggI46AdIM1gEaPQBiAEBmAExuAEXyAEM2AEB6AEB-AECiAIBqAIDuAKc2IunBsACAdICJDYyMmU4MGQ1LWUzYWQtNGRhZC1iNmEzLWJhOTI5OWVjZTQ1YtgCBeACAQ&aid=304142&lang=en-us&sb=1&src_elem=sb&src=searchresults&dest_id=-3730078&dest_type=city&ac_position=0&ac_click_type=b&ac_langcode=en&ac_suggestion_list_length=5&search_selected=true&search_pageview_id=a98d21b625600091&ac_meta=GhBhOThkMjFiNjI1NjAwMDkxIAAoATICZW46C0hvIENoaSBNaW5oQABKAFAA&checkin=2023-09-13&checkout=2023-09-14&group_adults=2&no_rooms=1&group_children=0"
    url5 = "https://www.booking.com/searchresults.vi.html?ss=V%C4%A9nh+Long&ssne=V%C4%A9nh+Long&ssne_untouched=V%C4%A9nh+Long&efdco=1&label=gen173nr-1FCAso9AFCCGhhdmVuaHV0SCpYBGj0AYgBAZgBKrgBF8gBDNgBAegBAfgBAogCAagCA7gC5sCwpwbAAgHSAiQ2Yjg5Mzk4NS05YWQwLTQzYzgtYTg3Ni1jMWJkZTU3MWQxN2LYAgXgAgE&sid=65dea12cdbba7b5902d66089ad78c0ac&aid=304142&lang=vi&sb=1&src_elem=sb&src=searchresults&dest_id=6889&dest_type=region&checkin=2023-09-16&checkout=2023-09-17&group_adults=2&no_rooms=1&group_children=0"
    url6 = "https://www.booking.com/searchresults.vi.html?label=gen173nr-1BCAEoggI46AdIM1gEaPQBiAEBmAEquAEXyAEM2AEB6AEBiAIBqAIDuALA2LWnBsACAdICJGExMTdhNzk3LWM0YTItNDY3MC1iZTQ4LTdjOWI5NGE4YWRjZNgCBeACAQ&sid=2ed53e5107abaf0a3256f3a26126c6d2&aid=304142&ss=TP.+H%C3%B4%CC%80+Chi%CC%81+Minh%2C+Vi%C3%AA%CC%A3t+Nam&efdco=1&lang=vi&src=index&dest_id=-3730078&dest_type=city&group_adults=2&no_rooms=1&group_children=0&sb_travel_purpose=leisure&nflt=class%3D5"
    url7 = "https://www.booking.com/searchresults.vi.html?label=gen173nr-1BCAEoggI46AdIM1gEaPQBiAEBmAEquAEXyAEM2AEB6AEBiAIBqAIDuALA2LWnBsACAdICJGExMTdhNzk3LWM0YTItNDY3MC1iZTQ4LTdjOWI5NGE4YWRjZNgCBeACAQ&sid=2ed53e5107abaf0a3256f3a26126c6d2&aid=304142&ss=TP.+H%C3%B4%CC%80+Chi%CC%81+Minh%2C+Vi%C3%AA%CC%A3t+Nam&efdco=1&lang=vi&src=index&dest_id=-3730078&dest_type=city&group_adults=2&no_rooms=1&group_children=0&sb_travel_purpose=leisure&nflt=class%3D4"
    url8 = "https://www.booking.com/searchresults.vi.html?label=gen173nr-1BCAEoggI46AdIM1gEaPQBiAEBmAEquAEXyAEM2AEB6AEBiAIBqAIDuALA2LWnBsACAdICJGExMTdhNzk3LWM0YTItNDY3MC1iZTQ4LTdjOWI5NGE4YWRjZNgCBeACAQ&sid=2ed53e5107abaf0a3256f3a26126c6d2&aid=304142&ss=TP.+H%C3%B4%CC%80+Chi%CC%81+Minh%2C+Vi%C3%AA%CC%A3t+Nam&efdco=1&lang=vi&src=index&dest_id=-3730078&dest_type=city&group_adults=2&no_rooms=1&group_children=0&sb_travel_purpose=leisure&nflt=class%3D3"
    url9 = "https://www.booking.com/searchresults.vi.html?label=gen173nr-1BCAEoggI46AdIM1gEaPQBiAEBmAEquAEXyAEM2AEB6AEBiAIBqAIDuALA2LWnBsACAdICJGExMTdhNzk3LWM0YTItNDY3MC1iZTQ4LTdjOWI5NGE4YWRjZNgCBeACAQ&sid=2ed53e5107abaf0a3256f3a26126c6d2&aid=304142&ss=TP.+H%C3%B4%CC%80+Chi%CC%81+Minh%2C+Vi%C3%AA%CC%A3t+Nam&efdco=1&lang=vi&src=index&dest_id=-3730078&dest_type=city&group_adults=2&no_rooms=1&group_children=0&sb_travel_purpose=leisure&nflt=class%3D2"
    url10 = "https://www.booking.com/searchresults.vi.html?label=gen173nr-1FCAEoggI46AdIM1gEaPQBiAEBmAExuAEHyAEM2AEB6AEB-AECiAIBqAIDuALvifamBsACAdICJDJkZGI2YmM2LTMxMzQtNGM1Yi04MWNjLWI2NTVkMDM0NWQ0OdgCBeACAQ&aid=304142&ss=Ho+Chi+Minh+City%2C+Vietnam&ssne=Ha+Giang&ssne_untouched=Ha+Giang&efdco=1&lang=en-us&src=searchresults&dest_id=-3730078&dest_type=city&group_adults=2&no_rooms=1&group_children=0&nflt=class%3D1"
    url0 = "https://www.booking.com/searchresults.vi.html?label=gen173nr-1BCAEoggI46AdIM1gEaPQBiAEBmAEquAEXyAEM2AEB6AEBiAIBqAIDuAK7oNCnBsACAdICJDIwNjU2ZjIyLThiYWUtNDU4ZC1iMGZkLTUxNzZiYTNjZDc4YtgCBeACAQ&sid=01d5c73c9795e9c283e07821a0e13d64&aid=304142&ss=TP.+H%C3%B4%CC%80+Chi%CC%81+Minh&ssne=TP.+H%C3%B4%CC%80+Chi%CC%81+Minh&ssne_untouched=TP.+H%C3%B4%CC%80+Chi%CC%81+Minh&efdco=1&lang=vi&dest_id=-3730078&dest_type=city&group_adults=2&no_rooms=1&group_children=0&nflt=class%3D0&order=class_asc"
    url00 = "https://www.booking.com/searchresults.vi.html?label=gen173nr-1BCAEoggI46AdIM1gEaPQBiAEBmAEquAEXyAEM2AEB6AEBiAIBqAIDuAK7oNCnBsACAdICJDIwNjU2ZjIyLThiYWUtNDU4ZC1iMGZkLTUxNzZiYTNjZDc4YtgCBeACAQ&sid=01d5c73c9795e9c283e07821a0e13d64&aid=304142&ss=TP.+H%C3%B4%CC%80+Chi%CC%81+Minh&ssne=TP.+H%C3%B4%CC%80+Chi%CC%81+Minh&ssne_untouched=TP.+H%C3%B4%CC%80+Chi%CC%81+Minh&efdco=1&lang=vi&dest_id=-3730078&dest_type=city&group_adults=2&no_rooms=1&group_children=0&nflt=class%3D0&order=class"
    #HN
    url21 = "https://www.booking.com/searchresults.vi.html?label=gen173nr-1BCAEoggI46AdIM1gEaPQBiAEBmAEquAEXyAEM2AEB6AEBiAIBqAIDuAKD7d6nBsACAdICJDlkYTY3MTYxLThlMjItNDExNS1iZmU1LWFlNWVkZGFhM2M4OdgCBeACAQ&sid=fa6c9cd6fe0f66705a76b6e1c13ff9aa&aid=304142&ss=Ha%CC%80+N%C3%B4%CC%A3i%2C+Vi%C3%AA%CC%A3t+Nam&efdco=1&lang=vi&src=index&dest_id=-3714993&dest_type=city&group_adults=2&no_rooms=1&group_children=0&sb_travel_purpose=leisure&nflt=class%3D5"
    url22 = "https://www.booking.com/searchresults.vi.html?label=gen173nr-1BCAEoggI46AdIM1gEaPQBiAEBmAEquAEXyAEM2AEB6AEBiAIBqAIDuAKD7d6nBsACAdICJDlkYTY3MTYxLThlMjItNDExNS1iZmU1LWFlNWVkZGFhM2M4OdgCBeACAQ&sid=fa6c9cd6fe0f66705a76b6e1c13ff9aa&aid=304142&ss=Ha%CC%80+N%C3%B4%CC%A3i%2C+Vi%C3%AA%CC%A3t+Nam&efdco=1&lang=vi&src=index&dest_id=-3714993&dest_type=city&group_adults=2&no_rooms=1&group_children=0&sb_travel_purpose=leisure&nflt=class%3D4"
    url23 = "https://www.booking.com/searchresults.vi.html?label=gen173nr-1BCAEoggI46AdIM1gEaPQBiAEBmAEquAEXyAEM2AEB6AEBiAIBqAIDuAKD7d6nBsACAdICJDlkYTY3MTYxLThlMjItNDExNS1iZmU1LWFlNWVkZGFhM2M4OdgCBeACAQ&sid=fa6c9cd6fe0f66705a76b6e1c13ff9aa&aid=304142&ss=Ha%CC%80+N%C3%B4%CC%A3i%2C+Vi%C3%AA%CC%A3t+Nam&efdco=1&lang=vi&src=index&dest_id=-3714993&dest_type=city&group_adults=2&no_rooms=1&group_children=0&sb_travel_purpose=leisure&nflt=class%3D3"
    url24 = "https://www.booking.com/searchresults.vi.html?label=gen173nr-1BCAEoggI46AdIM1gEaPQBiAEBmAEquAEXyAEM2AEB6AEBiAIBqAIDuAKD7d6nBsACAdICJDlkYTY3MTYxLThlMjItNDExNS1iZmU1LWFlNWVkZGFhM2M4OdgCBeACAQ&sid=fa6c9cd6fe0f66705a76b6e1c13ff9aa&aid=304142&ss=Ha%CC%80+N%C3%B4%CC%A3i%2C+Vi%C3%AA%CC%A3t+Nam&efdco=1&lang=vi&src=index&dest_id=-3714993&dest_type=city&group_adults=2&no_rooms=1&group_children=0&sb_travel_purpose=leisure&nflt=class%3D2"
    url25 = "https://www.booking.com/searchresults.vi.html?label=gen173nr-1BCAEoggI46AdIM1gEaPQBiAEBmAEquAEXyAEM2AEB6AEBiAIBqAIDuAKD7d6nBsACAdICJDlkYTY3MTYxLThlMjItNDExNS1iZmU1LWFlNWVkZGFhM2M4OdgCBeACAQ&sid=fa6c9cd6fe0f66705a76b6e1c13ff9aa&aid=304142&ss=Ha%CC%80+N%C3%B4%CC%A3i%2C+Vi%C3%AA%CC%A3t+Nam&efdco=1&lang=vi&src=index&dest_id=-3714993&dest_type=city&group_adults=2&no_rooms=1&group_children=0&sb_travel_purpose=leisure&nflt=class%3D1"
    url02 = "https://www.booking.com/searchresults.vi.html?label=gen173nr-1BCAEoggI46AdIM1gEaPQBiAEBmAEquAEXyAEM2AEB6AEBiAIBqAIDuAKTmPCnBsACAdICJDBjMTdmYTg2LTU0YTItNGE3OS05OTMzLWU0M2MxZThlOTgyNNgCBeACAQ&sid=fe0e90048ca34c54ee39cf4b4ebe7504&aid=304142&ss=Ha%CC%80+N%C3%B4%CC%A3i%2C+Vi%C3%AA%CC%A3t+Nam&efdco=1&lang=vi&dest_id=-3714993&dest_type=city&group_adults=2&no_rooms=1&group_children=0&sb_travel_purpose=leisure&nflt=class%3D0&order=class"
    url021 = "https://www.booking.com/searchresults.vi.html?label=gen173nr-1BCAEoggI46AdIM1gEaPQBiAEBmAEquAEXyAEM2AEB6AEBiAIBqAIDuAKTmPCnBsACAdICJDBjMTdmYTg2LTU0YTItNGE3OS05OTMzLWU0M2MxZThlOTgyNNgCBeACAQ&sid=fe0e90048ca34c54ee39cf4b4ebe7504&aid=304142&ss=Ha%CC%80+N%C3%B4%CC%A3i%2C+Vi%C3%AA%CC%A3t+Nam&efdco=1&lang=vi&dest_id=-3714993&dest_type=city&group_adults=2&no_rooms=1&group_children=0&sb_travel_purpose=leisure&nflt=class%3D0&order=class_asc"

    #VungTau
    url3 = "https://www.booking.com/searchresults.html?label=gen173nr-1FCAEoggI46AdIM1gEaPQBiAEBmAExuAEHyAEM2AEB6AEB-AECiAIBqAIDuALvifamBsACAdICJDJkZGI2YmM2LTMxMzQtNGM1Yi04MWNjLWI2NTVkMDM0NWQ0OdgCBeACAQ&aid=304142&ss=Ba+Ria+-+Vung+Tau%2C+Vietnam&ssne=Ha+Giang&ssne_untouched=Ha+Giang&efdco=1&lang=en-us&src=searchresults&dest_id=6233&dest_type=region&ac_position=1&ac_click_type=b&ac_langcode=en&ac_suggestion_list_length=5&search_selected=true&search_pageview_id=d34909da1d9c00cc&ac_meta=GhBkMzQ5MDlkYTFkOWMwMGNjIAEoATICZW46BmJhIHJpYUAASgBQAA%3D%3D&group_adults=2&no_rooms=1&group_children=0&nflt=class%3D1%3Bclass%3D2%3Bclass%3D3%3Bclass%3D4%3Bclass%3D5"
    url03 = "https://www.booking.com/searchresults.html?label=gen173nr-1FCAEoggI46AdIM1gEaPQBiAEBmAExuAEHyAEM2AEB6AEB-AECiAIBqAIDuALvifamBsACAdICJDJkZGI2YmM2LTMxMzQtNGM1Yi04MWNjLWI2NTVkMDM0NWQ0OdgCBeACAQ&aid=304142&ss=Ba+Ria+-+Vung+Tau%2C+Vietnam&ssne=Ha+Giang&ssne_untouched=Ha+Giang&efdco=1&lang=en-us&dest_id=6233&dest_type=region&ac_position=1&ac_click_type=b&ac_langcode=en&ac_suggestion_list_length=5&search_selected=true&search_pageview_id=d34909da1d9c00cc&ac_meta=GhBkMzQ5MDlkYTFkOWMwMGNjIAEoATICZW46BmJhIHJpYUAASgBQAA%3D%3D&group_adults=2&no_rooms=1&group_children=0&nflt=class%3D0&order=class_asc"
    url30 = "https://www.booking.com/searchresults.html?label=gen173nr-1FCAEoggI46AdIM1gEaPQBiAEBmAExuAEHyAEM2AEB6AEB-AECiAIBqAIDuALvifamBsACAdICJDJkZGI2YmM2LTMxMzQtNGM1Yi04MWNjLWI2NTVkMDM0NWQ0OdgCBeACAQ&aid=304142&ss=Ba+Ria+-+Vung+Tau%2C+Vietnam&ssne=Ha+Giang&ssne_untouched=Ha+Giang&efdco=1&lang=en-us&dest_id=6233&dest_type=region&ac_position=1&ac_click_type=b&ac_langcode=en&ac_suggestion_list_length=5&search_selected=true&search_pageview_id=d34909da1d9c00cc&ac_meta=GhBkMzQ5MDlkYTFkOWMwMGNjIAEoATICZW46BmJhIHJpYUAASgBQAA%3D%3D&group_adults=2&no_rooms=1&group_children=0&nflt=class%3D0&order=class"
    # url03 = "https://www.booking.com/searchresults.vi.html?label=gen173nr-1BCAEoggI46AdIM1gEaPQBiAEBmAEquAEXyAEM2AEB6AEBiAIBqAIDuALfuvKnBsACAdICJDc3MzA1OWE2LTk4OTEtNDRmNC04MTZmLTBhYjFkODhmNWFlOdgCBeACAQ&sid=755e46e9acf30e3457b1313be0548f47&aid=304142&ss=Vu%CC%83ng+Ta%CC%80u%2C+Vi%C3%AA%CC%A3t+Nam&ssne=Ha%CC%80+N%C3%B4%CC%A3i&ssne_untouched=Ha%CC%80+N%C3%B4%CC%A3i&efdco=1&lang=vi&dest_id=-3733750&dest_type=city&group_adults=2&no_rooms=1&group_children=0&sb_travel_purpose=leisure&nflt=class%3D0&order=class"
    # url30 = "https://www.booking.com/searchresults.vi.html?label=gen173nr-1BCAEoggI46AdIM1gEaPQBiAEBmAEquAEXyAEM2AEB6AEBiAIBqAIDuALfuvKnBsACAdICJDc3MzA1OWE2LTk4OTEtNDRmNC04MTZmLTBhYjFkODhmNWFlOdgCBeACAQ&sid=755e46e9acf30e3457b1313be0548f47&aid=304142&ss=Vu%CC%83ng+Ta%CC%80u%2C+Vi%C3%AA%CC%A3t+Nam&ssne=Ha%CC%80+N%C3%B4%CC%A3i&ssne_untouched=Ha%CC%80+N%C3%B4%CC%A3i&efdco=1&lang=vi&dest_id=-3733750&dest_type=city&group_adults=2&no_rooms=1&group_children=0&sb_travel_purpose=leisure&nflt=class%3D0&order=class_asc"
    # url3 = "https://www.booking.com/searchresults.vi.html?label=gen173nr-1BCAEoggI46AdIM1gEaPQBiAEBmAEquAEXyAEM2AEB6AEBiAIBqAIDuALfuvKnBsACAdICJDc3MzA1OWE2LTk4OTEtNDRmNC04MTZmLTBhYjFkODhmNWFlOdgCBeACAQ&sid=755e46e9acf30e3457b1313be0548f47&aid=304142&ss=B%C3%A0+R%E1%BB%8Ba+-+V%C5%A9ng+T%C3%A0u%2C+Vi%E1%BB%87t+Nam&ssne=L%C3%A2m+%C4%90%E1%BB%93ng&ssne_untouched=L%C3%A2m+%C4%90%E1%BB%93ng&efdco=1&lang=vi&src=searchresults&dest_id=6233&dest_type=region&ac_position=0&ac_click_type=b&ac_langcode=vi&ac_suggestion_list_length=5&search_selected=true&search_pageview_id=126758a4527e02fc&ac_meta=GhAxMjY3NThhNDUyN2UwMmZjIAAoATICdmk6B2JhIHJpYSBAAEoAUAA%3D&group_adults=2&no_rooms=1&group_children=0&nflt=class%3D5%3Bclass%3D4%3Bclass%3D2%3Bclass%3D3%3Bclass%3D1"
    # url03 = "https://www.booking.com/searchresults.vi.html?label=gen173nr-1BCAEoggI46AdIM1gEaPQBiAEBmAEquAEXyAEM2AEB6AEBiAIBqAIDuALfuvKnBsACAdICJDc3MzA1OWE2LTk4OTEtNDRmNC04MTZmLTBhYjFkODhmNWFlOdgCBeACAQ&sid=755e46e9acf30e3457b1313be0548f47&aid=304142&ss=B%C3%A0+R%E1%BB%8Ba+-+V%C5%A9ng+T%C3%A0u%2C+Vi%E1%BB%87t+Nam&ssne=L%C3%A2m+%C4%90%E1%BB%93ng&ssne_untouched=L%C3%A2m+%C4%90%E1%BB%93ng&efdco=1&lang=vi&dest_id=6233&dest_type=region&ac_position=0&ac_click_type=b&ac_langcode=vi&ac_suggestion_list_length=5&search_selected=true&search_pageview_id=126758a4527e02fc&ac_meta=GhAxMjY3NThhNDUyN2UwMmZjIAAoATICdmk6B2JhIHJpYSBAAEoAUAA%3D&group_adults=2&no_rooms=1&group_children=0&nflt=class%3D0&order=class"
    # url03 = "https://www.booking.com/searchresults.vi.html?label=gen173nr-1BCAEoggI46AdIM1gEaPQBiAEBmAEquAEXyAEM2AEB6AEBiAIBqAIDuALfuvKnBsACAdICJDc3MzA1OWE2LTk4OTEtNDRmNC04MTZmLTBhYjFkODhmNWFlOdgCBeACAQ&sid=755e46e9acf30e3457b1313be0548f47&aid=304142&ss=B%C3%A0+R%E1%BB%8Ba+-+V%C5%A9ng+T%C3%A0u%2C+Vi%E1%BB%87t+Nam&ssne=L%C3%A2m+%C4%90%E1%BB%93ng&ssne_untouched=L%C3%A2m+%C4%90%E1%BB%93ng&efdco=1&lang=vi&dest_id=6233&dest_type=region&ac_position=0&ac_click_type=b&ac_langcode=vi&ac_suggestion_list_length=5&search_selected=true&search_pageview_id=126758a4527e02fc&ac_meta=GhAxMjY3NThhNDUyN2UwMmZjIAAoATICdmk6B2JhIHJpYSBAAEoAUAA%3D&group_adults=2&no_rooms=1&group_children=0&nflt=class%3D0&order=class_asc"
    #
    # #Lam Dong
    # url45 = "https://www.booking.com/searchresults.html?label=gen173nr-1FCAEoggI46AdIM1gEaPQBiAEBmAExuAEHyAEM2AEB6AEB-AECiAIBqAIDuAKwspinBsACAdICJDNiMjVjYzFmLTc1NTUtNGM2OC1iMWFhLTQzNDY2MzgxZTIwYdgCBeACAQ&aid=304142&ss=Quang+Ninh%2C+Vietnam&efdco=1&lang=en-us&src=index&dest_id=5390&dest_type=region&ac_position=1&ac_click_type=b&ac_langcode=en&ac_suggestion_list_length=5&search_selected=true&search_pageview_id=54bb669865630081&ac_meta=GhA1NGJiNjY5ODY1NjMwMDgxIAEoATICZW46CnF1YW5nIE5pbmhAAEoAUAA%3D&checkin=2023-08-26&checkout=2023-08-27&group_adults=2&no_rooms=1&group_children=0&sb_travel_purpose=leisure&nflt=class%3D2%3Bclass%3D4%3Bclass%3D3%3Bclass%3D1%3Bclass%3D5"

    # url44 = "https://www.booking.com/searchresults.html?label=gen173nr-1FCAEoggI46AdIM1gEaPQBiAEBmAExuAEHyAEM2AEB6AEB-AECiAIBqAIDuAKwspinBsACAdICJDNiMjVjYzFmLTc1NTUtNGM2OC1iMWFhLTQzNDY2MzgxZTIwYdgCBeACAQ&aid=304142&ss=Da+Nang+Municipality%2C+Vietnam&ssne=Quang+Tri&ssne_untouched=Quang+Tri&lang=en-us&src=searchresults&dest_id=6232&dest_type=region&ac_position=1&ac_click_type=b&ac_langcode=en&ac_suggestion_list_length=5&search_selected=true&search_pageview_id=526868a5af3a010c&ac_meta=GhA1MjY4NjhhNWFmM2EwMTBjIAEoATICZW46B0RhIE5hbmdAAEoAUAA%3D&checkin=2023-08-26&checkout=2023-08-27&group_adults=2&no_rooms=1&nflt=class%3D0"
    url_qn_a = "https://www.booking.com/searchresults.html?label=gen173nr-1FCAEoggI46AdIM1gEaPQBiAEBmAExuAEHyAEM2AEB6AEB-AECiAIBqAIDuAKwspinBsACAdICJDNiMjVjYzFmLTc1NTUtNGM2OC1iMWFhLTQzNDY2MzgxZTIwYdgCBeACAQ&aid=304142&ss=Quang+Ninh%2C+Vietnam&efdco=1&lang=en-us&src=index&dest_id=5390&dest_type=region&ac_position=1&ac_click_type=b&ac_langcode=en&ac_suggestion_list_length=5&search_selected=true&search_pageview_id=54bb669865630081&ac_meta=GhA1NGJiNjY5ODY1NjMwMDgxIAEoATICZW46CnF1YW5nIE5pbmhAAEoAUAA%3D&checkin=2023-08-26&checkout=2023-08-27&group_adults=2&no_rooms=1&group_children=0&sb_travel_purpose=leisure&nflt=class%3D1%3Bclass%3D2%3Bclass%3D3%3Bclass%3D4%3Bclass%3D5"
    url_qn_0 = "https://www.booking.com/searchresults.html?label=gen173nr-1FCAEoggI46AdIM1gEaPQBiAEBmAExuAEHyAEM2AEB6AEB-AECiAIBqAIDuAKwspinBsACAdICJDNiMjVjYzFmLTc1NTUtNGM2OC1iMWFhLTQzNDY2MzgxZTIwYdgCBeACAQ&aid=304142&ss=Quang+Ninh%2C+Vietnam&efdco=1&lang=en-us&src=index&dest_id=5390&dest_type=region&ac_position=1&ac_click_type=b&ac_langcode=en&ac_suggestion_list_length=5&search_selected=true&search_pageview_id=54bb669865630081&ac_meta=GhA1NGJiNjY5ODY1NjMwMDgxIAEoATICZW46CnF1YW5nIE5pbmhAAEoAUAA%3D&checkin=2023-08-26&checkout=2023-08-27&group_adults=2&no_rooms=1&group_children=0&sb_travel_purpose=leisure&nflt=class%3D0"

    url_qnam_a = "https://www.booking.com/searchresults.html?label=gen173nr-1FCAEoggI46AdIM1gEaPQBiAEBmAExuAEHyAEM2AEB6AEB-AECiAIBqAIDuAKwspinBsACAdICJDNiMjVjYzFmLTc1NTUtNGM2OC1iMWFhLTQzNDY2MzgxZTIwYdgCBeACAQ&aid=304142&ss=Quang+Nam%2C+Vietnam&efdco=1&lang=en-us&src=index&dest_id=6925&dest_type=region&ac_position=0&ac_click_type=b&ac_langcode=en&ac_suggestion_list_length=5&search_selected=true&search_pageview_id=54bb669865630081&ac_meta=GhA1NGJiNjY5ODY1NjMwMDgxIAAoATICZW46CXF1YW5nIE5hbUAASgBQAA%3D%3D&checkin=2023-08-26&checkout=2023-08-27&group_adults=2&no_rooms=1&group_children=0&sb_travel_purpose=leisure&nflt=class%3D2%3Bclass%3D1%3Bclass%3D4%3Bclass%3D3%3Bclass%3D5"
    url_qnam_0 = "https://www.booking.com/searchresults.html?label=gen173nr-1FCAEoggI46AdIM1gEaPQBiAEBmAExuAEHyAEM2AEB6AEB-AECiAIBqAIDuAKwspinBsACAdICJDNiMjVjYzFmLTc1NTUtNGM2OC1iMWFhLTQzNDY2MzgxZTIwYdgCBeACAQ&aid=304142&ss=Quang+Nam%2C+Vietnam&efdco=1&lang=en-us&src=index&dest_id=6925&dest_type=region&ac_position=0&ac_click_type=b&ac_langcode=en&ac_suggestion_list_length=5&search_selected=true&search_pageview_id=54bb669865630081&ac_meta=GhA1NGJiNjY5ODY1NjMwMDgxIAAoATICZW46CXF1YW5nIE5hbUAASgBQAA%3D%3D&checkin=2023-08-26&checkout=2023-08-27&group_adults=2&no_rooms=1&group_children=0&sb_travel_purpose=leisure&nflt=class%3D0"

    url_kg_a = "https://www.booking.com/searchresults.html?label=gen173nr-1FCAEoggI46AdIM1gEaPQBiAEBmAExuAEHyAEM2AEB6AEB-AECiAIBqAIDuAKwspinBsACAdICJDNiMjVjYzFmLTc1NTUtNGM2OC1iMWFhLTQzNDY2MzgxZTIwYdgCBeACAQ&aid=304142&ss=Kien+Giang+%2C+Vietnam&efdco=1&lang=en-us&src=index&dest_id=5405&dest_type=region&ac_position=0&ac_click_type=b&ac_langcode=en&ac_suggestion_list_length=5&search_selected=true&search_pageview_id=54bb669865630081&ac_meta=GhA1NGJiNjY5ODY1NjMwMDgxIAAoATICZW46CmtpZW4gZ2lhbmdAAEoAUAA%3D&checkin=2023-08-26&checkout=2023-08-27&group_adults=2&no_rooms=1&group_children=0&sb_travel_purpose=leisure&nflt=class%3D2%3Bclass%3D3%3Bclass%3D4%3Bclass%3D5%3Bclass%3D1"
    url_kg_0 = "https://www.booking.com/searchresults.html?label=gen173nr-1FCAEoggI46AdIM1gEaPQBiAEBmAExuAEHyAEM2AEB6AEB-AECiAIBqAIDuAKwspinBsACAdICJDNiMjVjYzFmLTc1NTUtNGM2OC1iMWFhLTQzNDY2MzgxZTIwYdgCBeACAQ&aid=304142&ss=Kien+Giang+%2C+Vietnam&efdco=1&lang=en-us&src=index&dest_id=5405&dest_type=region&ac_position=0&ac_click_type=b&ac_langcode=en&ac_suggestion_list_length=5&search_selected=true&search_pageview_id=54bb669865630081&ac_meta=GhA1NGJiNjY5ODY1NjMwMDgxIAAoATICZW46CmtpZW4gZ2lhbmdAAEoAUAA%3D&checkin=2023-08-26&checkout=2023-08-27&group_adults=2&no_rooms=1&group_children=0&sb_travel_purpose=leisure&nflt=class%3D0"

    url_kh_a = "https://www.booking.com/searchresults.html?label=gen173nr-1FCAEoggI46AdIM1gEaPQBiAEBmAExuAEHyAEM2AEB6AEB-AECiAIBqAIDuAKZ6KenBsACAdICJGI3YTNiNjFhLTM0OTQtNGEzYS04NDljLTY2NzQ2MzRlNzZmMNgCBeACAQ&aid=304142&ss=Khanh+Hoa%2C+Vietnam&efdco=1&lang=en-us&src=index&dest_id=5425&dest_type=region&ac_position=0&ac_click_type=b&ac_langcode=en&ac_suggestion_list_length=5&search_selected=true&search_pageview_id=005d59cc933302e4&ac_meta=GhAwMDVkNTljYzkzMzMwMmU0IAAoATICZW46BmtoYW5oIEAASgBQAA%3D%3D&group_adults=2&no_rooms=1&group_children=0&sb_travel_purpose=leisure&nflt=class%3D2%3Bclass%3D3%3Bclass%3D4%3Bclass%3D5%3Bclass%3D1"
    url_kh_0 = "https://www.booking.com/searchresults.html?label=gen173nr-1FCAEoggI46AdIM1gEaPQBiAEBmAExuAEHyAEM2AEB6AEB-AECiAIBqAIDuAKZ6KenBsACAdICJGI3YTNiNjFhLTM0OTQtNGEzYS04NDljLTY2NzQ2MzRlNzZmMNgCBeACAQ&aid=304142&ss=Khanh+Hoa%2C+Vietnam&efdco=1&lang=en-us&src=index&dest_id=5425&dest_type=region&ac_position=0&ac_click_type=b&ac_langcode=en&ac_suggestion_list_length=5&search_selected=true&search_pageview_id=005d59cc933302e4&ac_meta=GhAwMDVkNTljYzkzMzMwMmU0IAAoATICZW46BmtoYW5oIEAASgBQAA%3D%3D&group_adults=2&no_rooms=1&group_children=0&sb_travel_purpose=leisure&nflt=class%3D0"

    # url42 = "https://www.booking.com/searchresults.html?label=gen173nr-1FCAEoggI46AdIM1gEaPQBiAEBmAExuAEHyAEM2AEB6AEB-AECiAIBqAIDuAKwspinBsACAdICJDNiMjVjYzFmLTc1NTUtNGM2OC1iMWFhLTQzNDY2MzgxZTIwYdgCBeACAQ&aid=304142&ss=Quang+Nam%2C+Vietnam&efdco=1&lang=en-us&src=index&dest_id=6925&dest_type=region&ac_position=0&ac_click_type=b&ac_langcode=en&ac_suggestion_list_length=5&search_selected=true&search_pageview_id=54bb669865630081&ac_meta=GhA1NGJiNjY5ODY1NjMwMDgxIAAoATICZW46CXF1YW5nIE5hbUAASgBQAA%3D%3D&checkin=2023-08-26&checkout=2023-08-27&group_adults=2&no_rooms=1&group_children=0&sb_travel_purpose=leisure&nflt=class%3D5%3Bclass%3D4%3Bclass%3D3%3Bclass%3D1%3Bclass%3D2"
    # url41 = "https://www.booking.com/searchresults.html?label=gen173nr-1FCAEoggI46AdIM1gEaPQBiAEBmAExuAEHyAEM2AEB6AEB-AECiAIBqAIDuAKZ6KenBsACAdICJGI3YTNiNjFhLTM0OTQtNGEzYS04NDljLTY2NzQ2MzRlNzZmMNgCBeACAQ&aid=304142&ss=Khanh+Hoa%2C+Vietnam&efdco=1&lang=en-us&src=index&dest_id=5425&dest_type=region&ac_position=0&ac_click_type=b&ac_langcode=en&ac_suggestion_list_length=5&search_selected=true&search_pageview_id=005d59cc933302e4&ac_meta=GhAwMDVkNTljYzkzMzMwMmU0IAAoATICZW46BmtoYW5oIEAASgBQAA%3D%3D&group_adults=2&no_rooms=1&group_children=0&sb_travel_purpose=leisure&nflt=class%3D2%3Bclass%3D4%3Bclass%3D3%3Bclass%3D1%3Bclass%3D5"
    # url40 = "https://www.booking.com/searchresults.vi.html?label=gen173nr-1BCAEoggI46AdIM1gEaPQBiAEBmAEquAEXyAEM2AEB6AEBiAIBqAIDuALfuvKnBsACAdICJDc3MzA1OWE2LTk4OTEtNDRmNC04MTZmLTBhYjFkODhmNWFlOdgCBeACAQ&sid=755e46e9acf30e3457b1313be0548f47&aid=304142&ss=L%C3%A2m+%C4%90%E1%BB%93ng%2C+Vi%E1%BB%87t+Nam&ssne=%C4%90%C3%A0+L%E1%BA%A1t&ssne_untouched=%C4%90%C3%A0+L%E1%BA%A1t&efdco=1&lang=vi&dest_id=6269&dest_type=region&ac_position=0&ac_click_type=b&ac_langcode=vi&ac_suggestion_list_length=5&search_selected=true&search_pageview_id=60f9589fff560486&ac_meta=GhA2MGY5NTg5ZmZmNTYwNDg2IAAoATICdmk6CGxhbSBkb25nQABKAFAA&group_adults=2&no_rooms=1&group_children=0&nflt=class%3D0&order=class"
    # url04 = "https://www.booking.com/searchresults.vi.html?label=gen173nr-1BCAEoggI46AdIM1gEaPQBiAEBmAEquAEXyAEM2AEB6AEBiAIBqAIDuALfuvKnBsACAdICJDc3MzA1OWE2LTk4OTEtNDRmNC04MTZmLTBhYjFkODhmNWFlOdgCBeACAQ&sid=755e46e9acf30e3457b1313be0548f47&aid=304142&ss=L%C3%A2m+%C4%90%E1%BB%93ng%2C+Vi%E1%BB%87t+Nam&ssne=%C4%90%C3%A0+L%E1%BA%A1t&ssne_untouched=%C4%90%C3%A0+L%E1%BA%A1t&efdco=1&lang=vi&dest_id=6269&dest_type=region&ac_position=0&ac_click_type=b&ac_langcode=vi&ac_suggestion_list_length=5&search_selected=true&search_pageview_id=60f9589fff560486&ac_meta=GhA2MGY5NTg5ZmZmNTYwNDg2IAAoATICdmk6CGxhbSBkb25nQABKAFAA&group_adults=2&no_rooms=1&group_children=0&nflt=class%3D0&order=class"
    # #DaNang
    # url5 = "https://www.booking.com/searchresults.vi.html?label=gen173nr-1BCAEoggI46AdIM1gEaPQBiAEBmAEquAEXyAEM2AEB6AEBiAIBqAIDuALfuvKnBsACAdICJDc3MzA1OWE2LTk4OTEtNDRmNC04MTZmLTBhYjFkODhmNWFlOdgCBeACAQ&sid=755e46e9acf30e3457b1313be0548f47&aid=304142&ss=%C4%90%C3%A0+N%E1%BA%B5ng%2C+Vi%C3%AA%CC%A3t+Nam&ssne=L%C3%A2m+%C4%90%E1%BB%93ng&ssne_untouched=L%C3%A2m+%C4%90%E1%BB%93ng&efdco=1&lang=vi&src=searchresults&dest_id=-3712125&dest_type=city&group_adults=2&no_rooms=1&group_children=0&nflt=class%3D4%3Bclass%3D2%3Bclass%3D3%3Bclass%3D1%3Bclass%3D5"
    # url50 = "https://www.booking.com/searchresults.vi.html?label=gen173nr-1BCAEoggI46AdIM1gEaPQBiAEBmAEquAEXyAEM2AEB6AEBiAIBqAIDuALfuvKnBsACAdICJDc3MzA1OWE2LTk4OTEtNDRmNC04MTZmLTBhYjFkODhmNWFlOdgCBeACAQ&sid=755e46e9acf30e3457b1313be0548f47&aid=304142&ss=%C4%90%C3%A0+N%E1%BA%B5ng%2C+Vi%C3%AA%CC%A3t+Nam&ssne=L%C3%A2m+%C4%90%E1%BB%93ng&ssne_untouched=L%C3%A2m+%C4%90%E1%BB%93ng&efdco=1&lang=vi&src=searchresults&dest_id=-3712125&dest_type=city&group_adults=2&no_rooms=1&group_children=0&nflt=class%3D0"

    # htlist = pd.read_excel("C:/Users/aisia\PycharmProjects\Crawl_booking\place_booking.xlsx")
    # for i in range(len(htlist)):
    #     if str(htlist['link'][i]) != 'nan':
    #         print(str(htlist['link'][i]))
    #         print(norm_text(htlist['Tỉnh'][i]))
    #         start_time = time.time()
    #         crawling_from_booking(str(htlist['link'][i]), filter_name=norm_text(htlist['Tỉnh'][i]).replace(" ","_"))
    #         print("Time process: ", time.time() - start_time)

    # start_time = time.time()
    # crawling_from_booking(url45, filter_name="5_star")
    # print("Time process: ", time.time() - start_time)
    # start_time = time.time()
    # crawling_from_booking(url44, filter_name="4_star")
    # print("Time process: ", time.time() - start_time)
    # start_time = time.time()
    # crawling_from_booking(url43, filter_name="3_star")
    # print("Time process: ", time.time() - start_time)
    # start_time = time.time()
    # crawling_from_booking(url42, filter_name="2_star")
    # print("Time process: ", time.time() - start_time)
    # start_time = time.time()
    # crawling_from_booking(url10, filter_name="1_star")
    # print("Time process: ", time.time() - start_time)

    # start_time = time.time()
    # crawling_from_booking(url43, filter_name="nan_star")
    # print("Time process: ", time.time() - start_time)
    # start_time = time.time()
    # crawling_from_booking(url03, filter_name="nan2_star")
    # print("Time process: ", time.time() - start_time)

    # start_time = time.time()
    # crawling_from_booking(url40, filter_name="0_star")
    # print("Time process: ", time.time() - start_time)

    # Recrawl Error data
    e = pd.read_excel("booking_error.xlsx")
    u = extract_properties(e['urls'],url6)
    u.to_excel("fix_error_booking.xlsx")

    # Recrawl Missing Hotels
    e = pd.read_excel("missing_hotel.xlsx")
    urls = ['https://www.booking.com/hotel/vn/' + str(url) +'.html' for url in e['id_url']]
    data = extract_properties(urls, url6)
    data.to_excel("fix_missing_booking.xlsx")
