from seleniumwire import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from multiprocessing import Queue
from bs4 import BeautifulSoup
from tqdm import tqdm
import re
import os
import json
import time
import requests
import unicodedata
import numpy as np
import pandas as pd
import multiprocessing as mp

pd.options.mode.chained_assignment = None  # default='warn'

def norm_text(text):
    return unicodedata.normalize('NFD', text).encode('ascii', 'ignore').decode()

def merge_json_files(file_paths,save_name):
    merged_contents = []
    sum = 0
    for file_path in file_paths:
        with open(file_path, 'r', encoding='utf-8') as file_in:
            content_i = json.load(file_in)
            if str(content_i) != 'nan':
                merged_contents.extend(content_i)
                if str(content_i) != '[]':
                    sum = sum + 1
    print("Total hotels that have reviews: ",sum)
    print("Total reviews: ",len(merged_contents)," , Save as: ",save_name)
    with open(save_name , 'w', encoding='utf-8') as file_out:
        json.dump(merged_contents, file_out, ensure_ascii=False)

def get_reviews(url,cookies):
  s = requests.Session()
  for cookie in cookies:
      s.cookies.set(cookie['name'], cookie['value'])
  headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36"}
  resp = s.get(url, headers=headers)
  soup = BeautifulSoup(resp.text, 'html.parser')
  data = []
  container = soup.find_all("div",{"data-test-target":"HR_CC_CARD"})
  years = []
  for cont in container:
      try:
        date = cont.find("div",{"class":"cRVSd"}).text.split(" ")
        try:
            date_save = '/'.join(date[-2:])
        except:
            date_save = date
      except:
        date = np.nan
        date_save = date
      try:
        year = date[-1]
      except:
        year = np.nan

      try:
          if int(year) < 2015:
            years.append(year)
            if len(years) == len(container):
                return data, False
            continue
      except:
          pass

      try:
        title = cont.find("div",{"data-test-target":"review-title"}).text
      except:
        title = np.nan
      try:
        content = cont.find("span",{"class":"QewHA H4 _a"}).text
      except:
        content = np.nan
      try:
        user = cont.find("a",{"class":"ui_header_link uyyBf"}).text
      except:
        user = np.nan
      try:
        user_place = cont.find("span",{"class":"default LXUOn small"}).text
      except:
        user_place = np.nan
      try:
        rating = int(cont.find_all("div",{"data-test-target":"review-rating"})[0].find("span").get("class")[-1].split("_")[-1])/10
      except:
        rating = np.nan
      try:
        trip_type = cont.find("span",{"class":"TDKzw _R Me"}).text
      except:
        trip_type = np.nan
      try:
        properties_rating = cont.find("span",{"class":"mSSzu"}).find_all()[0].find_all("div")
        properties = [x.text for x in properties_rating]
        star = [int(x.find_all("span")[-2].get("class")[-1].split("_")[-1])/10 for x in properties_rating]
        properties_rating = [str(properties[i]) + " : " + str(star[i]) for i in range(len(properties))]
      except:
        properties_rating = np.nan
      data.append({"url":url,"date":date_save,"rating":rating,"title":title,"review":content,"user":user,"user_place":user_place,"trip_type":trip_type, "properties_rating":properties_rating})
  return data, True

def extract_reviews(url):
    name = "reviews_" + url.split("-Reviews-")[-1].replace(".html", "") + ".json"
    if name in os.listdir():
        # print("Skip dup: ", name)
        return 0

    # Driver get search page
    options = Options()
    options.add_argument("start-maximized")

    hotel_url = url.replace(".com.vn",".com")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36"}
    new_session = requests.session()
    resp = new_session.get(hotel_url, headers=headers)
    page_soup = BeautifulSoup(resp.text, 'html.parser')
    try:
        total_reviews = page_soup.find("span", {"class": "iypZC Mc _R b"}).text
        if total_reviews == 0:
            return 0
    except:
        return 0
    total_rv_pages = int(total_reviews)//10
    _ = int(total_reviews) % 10
    if _ != 0:
        total_rv_pages = total_rv_pages + 1

    # print(name," Total Reviews, Total Pages: ",total_reviews,total_rv_pages)

    driver = webdriver.Chrome(options=options)
    driver.get(hotel_url)
    # Choose all languages comment
    try:
        WebDriverWait(driver, 0.5).until(EC.presence_of_element_located((By.XPATH, ".//input[contains(@id, 'LanguageFilter_0')]")))
        lg = driver.find_element(By.XPATH, ".//input[contains(@id, 'LanguageFilter_0')]")
        driver.execute_script("arguments[0].click();", lg)
        time.sleep(0.5)
    except:
        pass
    # except:
    # print("without languages comment",hotel_url)

    # Expand the reviews
    try:
        WebDriverWait(driver, 0.5).until(
            EC.presence_of_element_located((By.XPATH, ".//span[contains(@class, 'Ignyf _S Z')]")))
        expand = driver.find_element(By.XPATH, ".//span[contains(@class, 'Ignyf _S Z')]")  # .click()
        driver.execute_script("arguments[0].click();", expand)
        time.sleep(0.5)
    except:
        pass
    # print("without expand comment",hotel_url)

    # Auto-translate off
    try:
        notranslate = driver.find_element(By.XPATH, ".//input[contains(@id, 'autoTranslateNo')]")  # .click()
        driver.execute_script("arguments[0].click();", notranslate)
        time.sleep(0.5)
    except:
        pass
        # print("without translate comment",hotel_url)
    cookies = driver.get_cookies()
    driver.quit()

    reviews_data = []
    for pnum in range(0,total_rv_pages,1):
        c_url = hotel_url.replace("-Reviews-" ,"-Reviews-or"+ str(pnum*10) + "-")
        # Get reviews
        # print(c_url)
        data, _ = get_reviews(c_url, cookies)
        reviews_data = reviews_data + data
        # print(len(reviews_data))

        # Skip reviews before 2015
        if not _:
            savename = hotel_url.split("-Reviews-")[-1].replace(".html", "")
            filename = "reviews_" + savename + ".json"
            with open(filename, "w", encoding='utf8') as file:
                json.dump(reviews_data, file, ensure_ascii=False)
            break

    # reviews_data = []
    # for i in range(total_rv_pages):
    #
    #     # Expand the reviews
    #     time.sleep(1)
    #     expand = driver.find_element(By.XPATH,".//span[contains(@class, 'Ignyf _S Z')]")#.click()
    #     driver.execute_script("arguments[0].click();", expand)
    #     try:
    #         notranslate = driver.find_element(By.XPATH, ".//input[contains(@id, 'autoTranslateNo')]")  # .click()
    #         driver.execute_script("arguments[0].click();", notranslate)
    #     except:
    #         pass
    #
    #     # Get reviews
    #     print(driver.current_url)
    #     data, _ = get_reviews(driver.current_url,cookies)
    #     reviews_data = reviews_data + data
    #     print(len(reviews_data))
    #     # Skip reviews before 2015
    #     if not _:
    #         # filename = "reviews_" + hotel_url + ".json"
    #         savename = hotel_url.split("-Reviews-")[-1].replace(".html", "")
    #         filename = "reviews_" + savename + ".json"
    #         with open(filename, "w", encoding='utf8') as file:
    #             json.dump(reviews_data, file, ensure_ascii=False)
    #         break
    #
    #     # If not enough review
    #     if int(len(reviews_data))<int(total_reviews):
    #         nx_page = driver.find_element(By.XPATH, './/a[@class="ui_button nav next primary "]')#.get_attribute("href")
    #         driver.execute_script("arguments[0].click();", nx_page)
    # driver.quit()

    # Save reviews as url_id
    savename = hotel_url.split("-Reviews-")[-1].replace(".html","")
    filename = "reviews_"+savename+".json"
    with open(filename, "w", encoding='utf8') as file:
        json.dump(reviews_data, file, ensure_ascii=False)


def extract_add_sel(u):



    # Driver get search page
    # options = Options()
    # options.add_argument("start-maximized")

    # driver = webdriver.Chrome(options=options)
    try:
        u.insert(1,'address',np.nan)
    except:
        pass
    data_fs = pd.DataFrame()

    for i in tqdm(range(len(u))):
        total_i = u['address'][i]
        # print(str(u['address'][i]))
        if u['address'][i] != 'done':
        # if str(u['address'][i]) =='nan':
            url = u['urls'][i]
            # name = "reviews_" + url.split("-Reviews-")[-1].replace(".html", "") + ".json"
            hotel_url = url.replace(".com.vn", ".com")
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36"}
            new_session = requests.session()

            # resp = new_session.get(hotel_url, headers=headers)

            x = extract_properties(hotel_url)
            print(x)
            data_fs=pd.concat([data_fs,pd.DataFrame(x)])
            u['address'][i] = 'done'
            u.to_excel("fixed_address_missing.xlsx")
            data_fs.to_excel("fixed_data_missing.xlsx")
            # driver.get(hotel_url)
            #
            # # print(hotel_url)
            # time.sleep(0.5)
            # try:
            #     try:
            #     # WebDriverWait(driver, 0.5).until(
            #     #     EC.presence_of_element_located((By.XPATH, ".//span[contains(@class, 'biGQs _P pZUbB KxBGd')]")))
            #         address = driver.find_element(By.XPATH, ".//div[contains(@class,'gZwVG H3 f u ERCyA')]").text
            #
            #     except:
            #         address = driver.find_element(By.XPATH, ".//span[contains(@class, 'oAPmj _S ')]").text
            # except:
            #     x= driver.find_element(By.XPATH, ".//span[contains(@class, 'biGQs _P pZUbB KxBGd')]")
            #     # print(x)
            #     address = x.text
            # # print(address)
            # # u['address'][i]
            # u['address'][i] = address
            # u.to_excel("fixed_address_missing.xlsx")

    # driver.quit()
    return u


def extract_properties(h_url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36"}
    new_session = requests.Session()
    resp = new_session.get(h_url, headers=headers)
    # time.sleep(0.5)
    soup = BeautifulSoup(resp.text, 'html.parser')
    # print(soup)

    # print(soup)

    d = {}
    d["url"] = h_url

    try:
        resp_en = new_session.get(h_url.replace(".com.vn",".com"), headers=headers)
        d["price"] = BeautifulSoup(resp_en.text, 'html.parser').find("div",{"class":"gbXAQ"}).text
    except:
        d["price"] = np.nan
    try:
        d["hotel_name"] = soup.find("h1", {"id": "HEADING"}).text
    except:
        d["hotel_name"] = np.nan
    try:
        d["address"] = soup.find("span", {"class": "oAPmj _S"}).text
        # .find("span", {"class": "APmj _S"})
        # d["address"] = soup.find("span", {"class": "oAPmj _S YUQUy PTrfg"}).text
        # d["address"] = soup.find("div", {"class": "biGQs _P pZUbB KxBGd"}).text
    except:
        # try:
        #     d["address"] = soup.find("div", {"class": "DWwCf"}).text
        # except:
        #     try:
        #         d["address"] = soup.find("span", {"class": "biGQs _P pZUbB KxBGd"}).text
        #     except:
        try:
            d["address"] = soup.find("span", {"class": "CdhWK _S "}).text
        except:
            d["address"] = np.nan
    try:
        d["total_reviews"] = soup.find("span", {"class": "hkxYU q Wi z Wc"}).text
    except:
        d["total_reviews"] = np.nan
    try:
        d["rating"] = soup.find("span", {"class": "uwJeR P"}).text
    except:
        d["rating"] = np.nan
    try:
        d["content"] = soup.find("div", {"class": "fIrGe _T"}).text
    except:
        d["content"] = np.nan
    try:
        # star = soup.find("div", {"class": "euDRl _R MC S4 _a H"}).find_all("svg")[0].get("aria-label").split(" ")[0]
        star = soup.find("div", {"class": "CMiVw _R MC S4 _a H"}).find_all("svg")[0].get("aria-label").split(" ")[0]
        d['rating_star'] = star
    except:
        d['rating_star'] = np.nan
    # More Informations
    try:
        in4 = soup.find("div", {"class": "GFCJJ"}).find_all()[1:]
        for t in range(0, len(in4), 2):
            if in4[t].text == "KHOẢNG GIÁ":
                d["range_price"] = in4[t + 1].text
            if in4[t].text == "SỐ LƯỢNG PHÒNG":
                d["number_of_rooms"] = in4[t + 1].text
        if "number_of_rooms" not in list(d):
            d["number_of_rooms"] = np.nan
        if "range_price" not in list(d):
            d["range_price"] = np.nan
    except:
        d["range_price"] = np.nan
        d["number_of_rooms"] = np.nan

    # Properties Rating
    try:
        p_rating = soup.find_all("div", {"class": "HXCfp"})
        p_ratings = {}
        for p in p_rating:
            p_ratings[p.find_all()[1].text] = int(p.find_all()[0].get("class")[1].split("_")[1]) / 10
        d["p_ratings"] = p_ratings
    except:
        d["p_ratings"] = np.nan

    # Properties
    try:
        keys = soup.find_all("div", {"class": "aeQAp S5 b Pf ME"})
        values = soup.find_all("div", {"class": "OsCbb K"})
        all_p = []
        for v in range(len(values)):
            temp = values[v].find_all("div")
            all_v = []
            for h in temp:
                if str(h.find("div")) == "None":
                    all_v.append(h.text)
            all_p.append({"key":keys[v].text,"value":all_v})
        d["properties"] = all_p
    except:
        if "properties" not in list(d):
            d["properties"] = np.nan
    return d

def crawling_from_tripadvisor(url):

    # Request bs4
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36"}
    s = requests.session()
    resp = s.get(url.replace(".com.vn",".com"), headers=headers)
    page_soup = BeautifulSoup(resp.text, 'html.parser')

    # Get Save Name
    save_name = page_soup.find("h1", {"data-automation": "header_geo_title"}).text.replace(" ","_")
    print(save_name)

    data_path = os.path.join("D:/AISIA", "data_tripadvisor")
    save_path = os.path.join("D:/AISIA", "data_tripadvisor", save_name)
    try:
        os.makedirs(save_path)
    except:
        pass
    os.chdir(data_path)

    filename = os.path.join(data_path, "hotels_" + save_name + '.csv')
    if str("hotels_" + save_name + ".csv") not in os.listdir():
        # Total Hotels (display)
        options = Options()
        options.add_argument("start-maximized")
        driver = webdriver.Chrome(options=options)
        driver.get(url)
        time.sleep(3)
        railmain = driver.find_element(By.CSS_SELECTOR, 'div[data-automation="LeftRailMain"]')
        total_hotels = int(
            railmain.find_element(By.CSS_SELECTOR, 'span[class="b"]').text.split(" ")[0].replace(",", ""))
        print(total_hotels)
        driver.quit()

        # Count total search pages
        total_pages = int(total_hotels) // 30
        _ = int(total_hotels) % 30
        if _ != 0:
            total_pages = total_pages + 1
        print("total search page:", total_pages)

        # Get search pages url
        lis = url.split("-")
        lis.insert(2, 'oaxx')
        t_url = "-".join(lis)
        nums = [i * 30 for i in range(int(total_pages))]
        urls = [t_url.replace("-oaxx-", "-oa" + str(n) + "-") for n in nums]
        # print(urls)

        # Get Hotels url
        h_urls = []
        for u in tqdm(urls):
            new_s = requests.session()
            resp = new_s.get(u, headers=headers)
            sub_page_soup = BeautifulSoup(resp.text, 'html.parser')
            links = sub_page_soup.find_all('div',{'data-automation':'hotel-card-title'})
            h_urls = h_urls + [links[i].find('a').get('href') for i in range(len(links))]
        # print(["https://www.tripadvisor.com.vn" + hotel_url for hotel_url in [*set(h_urls)]][int(total_hotels):])
        hotel_urls = ["https://www.tripadvisor.com.vn" + hotel_url for hotel_url in [*set(h_urls)]][:int(total_hotels)]

        # print(len(hotel_urls),int(total_hotels),len(h_urls))
        # print(hotel_urls)
        # # Extract hotels properties
        print("Extract Hotels properties")
        # datafs = pd.DataFrame()
        dataf = []
        # with mp.Pool(8) as p:
        #     data = p.map(extract_properties, hotel_urls)
        try:
            a = pd.read_csv(filename)
        except:
            a = pd.DataFrame()
        datafs=a
        for h in tqdm(range(len(hotel_urls))):
            try:
                if str(hotel_urls[h]) in a['url'].values:#str(a['url'][h]):
                    print("skip url")
            except:
                0
            data = extract_properties(hotel_urls[h])
            dataf.append(data)
            # dataf = pd.DataFrame(data)
            # datafs = pd.concat([datafs,dataf])
        # datafs.insert(3, "rating_star", str(save_name.split("-")[0]))
        #     datafs = pd.concat([a,pd.DataFrame(dataf)])
            datafs = pd.concat([datafs,pd.DataFrame([data])])
        # datafs = pd.DataFrame(dataf)
            datafs.to_csv(filename)
        print("Save Hotels properties: ", filename)
    else:
        print("Already have hotels CSV file, Skip Extract Hotels Properties!")
        hotel_urls = pd.read_csv(filename)["url"]

    print("Total Hotels", len(hotel_urls))

    # # Extract Review
    # print("Extract Reviews")
    # os.chdir(save_path)
    # # reviews_data = []
    # with mp.Pool(4) as p:
    #     # reviews_data.append(p.map(extract_reviews, hotel_urls))
    #     p.map(extract_reviews, hotel_urls)

    # final_reviews_name = os.path.join(data_path, "reviews_" + save_name + ".json")
    # merge_json_files(os.listdir(), final_reviews_name)

if __name__ == '__main__':
    # url1 = "https://www.tripadvisor.com.vn/Hotels-g303942-Can_Tho_Mekong_Delta-Hotels.html"
    # url1 = "https://www.tripadvisor.com.vn/Hotels-g469420-Soc_Trang_Soc_Trang_Province_Mekong_Delta-Hotels.html"
    # url2 = "https://www.tripadvisor.com.vn/Hotels-g2146206-Dong_Thap_Province_Mekong_Delta-Hotels.html"

    # url1 = "https://www.tripadvisor.com/Hotels-g293925-zfc1-a_ufe.true-Ho_Chi_Minh_City-Hotels.html"
    # url2 = "https://www.tripadvisor.com/Hotels-g293925-zfc2-a_ufe.true-Ho_Chi_Minh_City-Hotels.html"
    # url3 = "https://www.tripadvisor.com/Hotels-g293925-zfc3-a_ufe.true-Ho_Chi_Minh_City-Hotels.html"
    # url4 = "https://www.tripadvisor.com/Hotels-g293925-zfc4-a_ufe.true-Ho_Chi_Minh_City-Hotels.html"
    # url5 = "https://www.tripadvisor.com/Hotels-g293925-zfc5-a_ufe.true-Ho_Chi_Minh_City-Hotels.html"

    # url2 = "https://www.tripadvisor.com/Hotels-g293925-zfc9571,9574-a_ufe.true-Ho_Chi_Minh_City-Hotels.html"
    # url2 = "https://www.tripadvisor.com/Hotels-g293925-a_ufe.true-Ho_Chi_Minh_City-Hotels.html"
    #HN
    # url0 = "https://www.tripadvisor.com/Hotels-g293924-Hanoi-Hotels.html"
    # url1 = "https://www.tripadvisor.com/Hotels-g293924-zfc9571,9574-a_ufe.true-Hanoi-Hotels.html"
    # url2 = "https://www.tripadvisor.com/Hotels-g293924-zfc2-a_ufe.true-Hanoi-Hotels.html"
    # url3 = "https://www.tripadvisor.com/Hotels-g293924-zfc3-a_ufe.true-Hanoi-Hotels.html"
    # url4 = "https://www.tripadvisor.com/Hotels-g293924-zfc4-a_ufe.true-Hanoi-Hotels.html"
    # url5 = "https://www.tripadvisor.com/Hotels-g293924-zfc5-a_ufe.true-Hanoi-Hotels.html"
    #
    # start_time = time.time()
    # crawling_from_tripadvisor(url0)
    # print("Time process: ", time.time() - start_time)
    # start_time = time.time()
    # crawling_from_tripadvisor(url2)
    # print("Time process: ", time.time() - start_time)
    # start_time = time.time()
    # crawling_from_tripadvisor(url3)
    # print("Time process: ", time.time() - start_time)
    # start_time = time.time()
    # crawling_from_tripadvisor(url4)
    # print("Time process: ", time.time() - start_time)
    # start_time = time.time()
    # crawling_from_tripadvisor(url5)
    # print("Time process: ", time.time() - start_time)


    # htlist = pd.read_excel("C:/Users/aisia\PycharmProjects\Crawl_booking\place_tripadvisor.xlsx")
    # for i in range(len(htlist)):
    #     if str(htlist['url'][i]) != 'nan':
    #         print(str(htlist['url'][i]))
    #         print(norm_text(htlist['tinh'][i]))
    #         start_time = time.time()
    #         crawling_from_tripadvisor( str(htlist['url'][i]) )
    #         print("Time process: ", time.time() - start_time)


    # if "comments_dataset.csv" in os.listdir():
    #     cm_dataset = pd.read_csv("D:\Workspace\Projects\AISIA Lab\Crawler_CIRTECH/comments_dataset.csv")
    #     cmds = [cmd.split(".html")[0] for cmd in cm_dataset['id']]
    #     news_ids = [*set(cmds)]
    #     # print(news_ids)
    # else:
    #     cm_dataset = pd.DataFrame()
    #     news_ids = []
    #
    # # Get comments (Selenium)
    # # cm_dataset = pd.DataFrame()
    # comments_dataset = []
    # for url in tqdm(us):
    #     print(url.split("/")[-1].split(".html")[0])
    #     if url.split("/")[-1].split(".html")[0] in news_ids:
    #         print("skip")
    #         continue
    #     comments = get_comments(url)
    #     cm_dataset = pd.concat([cm_dataset,pd.DataFrame(comments)])
    #     cm_dataset.to_csv("comments_dataset.csv")
    #     # comments_dataset = comments_dataset + comments

    # Recrawl Error data

    # e = pd.read_csv("fixed_hotels_tripadvisor_normalized_Dec_21.csv", lineterminator='\n')

            # options = Options()
            # # options.add_argument("start-maximized")
            # options.add_argument("--headless")
            # driver = webdriver.Chrome(options=options)

    # datas = []
    # extract_add_sel(e)
    # new_s = requests.session()
    # for u in tqdm(range(len(e['link']))):
        # if str(e['rating_star'][u]) == 'nan':
            # data = extract_properties(e['url'][u])
            data = pd.read_excel(
                "C:/Users/aisia\PycharmProjects\Crawl_booking/FIXSTAR2_tripadvisor_hotel_Ranking_for_website.xlsx")
            p0_merge = data[data['rating_star'] == '0-star'].reset_index().copy()
            stars = []
            links = []
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36"}
            new_session = requests.Session()
    # Lọc ra danh sách có nhãn trước (Loại bỏ các dòng ko có nhãn trước maybe nhanh)
    # Sau đó chạy lấy lại các dòng có sao
            j=0
            for i in tqdm(range(len(p0_merge))):
                if p0_merge['rating_star'][i] == '0-star':
                    url = p0_merge['link'][i].strip()
                    # url1= 'https://www.tripadvisor.com.vn/Hotel_Review-g293925-d16811734-Reviews-Mai_House_Saigon_Hotel-Ho_Chi_Minh_City.html'
                    resp = new_session.get(url, headers=headers)
                    # time.sleep()
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    # print(len(soup))
                    try:
                        star = soup.find("svg", {"class": "JXZuC d H0"}).get("aria-label")
                        j=j+1
                        print(j)
                    except:
                        star = np.nan
                        continue

                    p0_merge['rating_star'][i] = star
                    # links.append(url)
                    # stars.append(star)
                # fix_data = pd.DataFrame(np.column_stack([links, stars]),
                #                    columns=['links', 'stars'])
                # fix_data['stars'] = stars
            p0_merge[['link','rating_star']].to_excel("FIXSTAR3_tripadvisor_hotel_Ranking_for_website.xlsx")
                # break

                # driver.get(url)
                # print(driver.find_elements(By.XPATH,".//div[contains(@class, 'euDRl _R MC S4 _a H')]"))
                # tol = driver.find_elements(By.TAG_NAME, "svg")

                # print(len(tol))
                # for j in range(len(tol)):
                #     try:
                #         cl = tol[j].get_attribute("class")
                #     except:
                #         cl = ''
                #     if cl == 'JXZuC d H0':
                #         print(p0_merge['rating_star'][i], url, tol[j].get_attribute("aria-label"))

                    # links.append(url)
                    # stars.append(tol[j].get_attribute("aria-label"))
                    # fix_data = pd.DataFrame([links], columns=['links'])
                    # fix_data['stars'] = stars
                    # fix_data.to_excel("FIXSTAR_tripadvisor_hotel_Ranking_for_website.xlsx")


            # fix_data = pd.DataFrame([links],columns=['links'])
            # fix_data['stars'] = stars
            # fix_data.to_excel("FIXSTAR_tripadvisor_hotel_Ranking_for_website.xlsx")

            # new_s = requests.session()
            # resp = new_s.get(e['link'][u], headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36"})
            # soup = BeautifulSoup(resp.text,'html.parser')
            # try:
            #     print(e['link'][u],)
            #     star = soup.find("div", {"class": "CMiVw _R MC S4 _a H"}).find_all("svg")[0].get("aria-label").split(" ")[0]
            #     print( star)
            # except:
            #     print(soup.find("div", {"class": "CMiVw _R MC S4 _a H"}))
            #     star = np.nan
            # e['rating_star'][u] = star

            # print(data)
            # address = extract_add_sel(u)
            #     datas.append(data)
            # for k in data.keys():
            #     e[k][u] = data[k]
            # e['address'][u] = data['address']
            # print(e.iloc[u])
            # e.to_csv("fixed_hotels_tripadvisor_normalized_Dec_21_2.csv")



    # e = pd.read_excel("fixed_data_missingi.xlsx")
    # datas= []
    # # extract_add_sel(e)
    #
    # for u in tqdm(range(len(e['url']))):
    #     if str(e['address'][u]) == 'nan':
    #         data = extract_properties(e['url'][u])
    #         print(data['address'],data['url'])
    #
    #         # print(data)
    #     # address = extract_add_sel(u)
    #     #     datas.append(data)
    #         for k in data.keys():
    #             e[k][u] = data[k]
    #         e['address'][u] = data['address']
    #         # print(e.iloc[u])
    #         e.to_excel("fixed_data_missingi.xlsx")





    # e['address'] = datas
    #         break

    # addresses = pd.DataFrame(datas)
    # addresses.to_excel("fixed_data_missing_3.xlsx")

    # e.to_excel("fixed_address_missing.xlsx")
    # for i in range(len(dataset)):
        # for col in dataset.columns:
        #     print(dataset['hotel_name'][i], dataset['address'][i])


    # url = "https://www.tripadvisor.com.vn/Hotel_Review-g298085-d6405717-Reviews-Bin_Star_Hotel-Da_Nang.html"
    # url1 = "https://www.tripadvisor.com.vn/Hotel_Review-g1544599-d15319392-Reviews-Homestay_Nam_Tran-Ha_Giang_Ha_Giang_Province.html"
    #
    # a=extract_properties(url)
    # b=extract_properties(url1)
    # print(a)
    # print(b)

