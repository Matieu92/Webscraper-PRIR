import os
import asyncio
import aiohttp
import multiprocessing
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
import warnings
from urllib.parse import urljoin, urlparse
import re
from pymongo import MongoClient
import time

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

SOCIAL_DOMAINS = [
    "facebook.com", "instagram.com", "twitter.com", "x.com",
    "linkedin.com", "youtube.com", "tiktok.com"
]

# zebranie danych z jednej strony
async def fetch(url, session, visited=None, all_data=None, emails=None, postal_codes=None, social_links=None):
    if visited is None:
        visited = set()
    if all_data is None:
        all_data = []
    if emails is None:
        emails = {} 
    if postal_codes is None: 
        postal_codes = {}
    if social_links is None: 
        social_links = {}  

    visited.add(url)

    base_domain = urlparse(url).netloc

    try:
        async with session.get(url, timeout=30) as response:
            if response.status != 200:
                all_data.append({'url': url, 'status': response.status})
                return
            
            # komenda GET
            content = await response.text()
            soup = BeautifulSoup(content, 'html.parser')
            soup.encoding = 'utf-8'

            # email href
            email_elements = soup.select('a[href*="mailto"]')
            for element in email_elements:
                href = element.get('href', '')
                if href and 'mailto' in href.lower():
                    email = href.replace('mailto:', '').strip()
                    email = email.split('?')[0].strip()
                    if email and '@' in email:
                        emails[email] = base_domain
                                
            # e-mail regex
            page_text = soup.get_text(separator=' ', strip=True)
            email_pattern = r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b'
            found_emails = re.findall(email_pattern, page_text)
            for email in found_emails:
                if email and '@' in email:
                    emails[email] = base_domain

            # kody pocztowe i miasta regex
            code_loc_pattern = r'(\b\d{2}-\d{3}\b)\s+([A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+(?:[\s-][A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+){0,2})'
            codes_matched_with_locality = set() # To track codes already found with a locality
            for code, locality_raw in re.findall(code_loc_pattern, page_text):
                locality = re.sub(r'[,\.]?$', '', locality_raw.strip()) # Clean trailing punctuation from locality
                postal_codes[(code, locality)] = base_domain
                codes_matched_with_locality.add(code)

            # same kody regex
            standalone_code_pattern = r'\b\d{2}-\d{3}\b'
            all_codes_on_page = re.findall(standalone_code_pattern, page_text)
            for code in all_codes_on_page:
                if code not in codes_matched_with_locality:
                    postal_codes[(code, None)] = base_domain


            #linki social media
            for link_tag in soup.find_all('a', href=True):
                href = link_tag['href']
                if not href: continue

                try:
                    parsed_href_netloc = urlparse(href).netloc.lower()
                    if any(domain in parsed_href_netloc for domain in SOCIAL_DOMAINS):
                        full_social_url = urljoin(url, href)

                        if urlparse(full_social_url).scheme in ('http', 'https'):
                            social_links[full_social_url] = base_domain
                except ValueError: pass    

            # zebrane dane
            all_data.append({
                'url': url,
                'status': response.status
            })

            # poszukiwanie podstron
            sub_urls = []
            for link in soup.find_all('a', href=True):
                href = link['href']
                absolute_url = urljoin(url, href)
                parsed_url = urlparse(absolute_url)
                extrude = ('.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.zip', '.rar', '.7z', '.txt', '.csv', 
                    '.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp', '.mp3', '.mp4', '.avi', '.mov')
                
                path = parsed_url.path.lower()
                if not any(path.endswith(ext) for ext in extrude) and parsed_url.netloc == base_domain and parsed_url.scheme in ('http', 'https'):
                    if absolute_url not in visited:
                        sub_urls.append(absolute_url)
                        print(absolute_url)

            # przeszukiwanie podstron
            tasks = [fetch(sub_url, session, visited, all_data, emails, postal_codes, social_links) for sub_url in sub_urls]
            await asyncio.gather(*tasks)

    except Exception as e:
        all_data.append({'url': url, 'status': None, 'error': f'Błąd: {str(e)}'})

# async taski zbierajace dane, jedna sesja TCP
async def fetch_all(urls):
    all_data = []
    emails = {}
    postal_codes = {}
    social_media_links = {}
    async with aiohttp.ClientSession() as session:
        tasks = [fetch(url, session, all_data=all_data, emails=emails, 
                       postal_codes=postal_codes, # Pass new dicts
                       social_links=social_media_links) 
                 for url in urls]
        await asyncio.gather(*tasks)
    return {
        'emails': emails, 
        'postal_codes': postal_codes, 
        'social_media_links': social_media_links
    }

# petla zbierajaca dane
def process_urls(urls):
    return asyncio.run(fetch_all(urls))

# podzielenie stron i podstron dzieki multiprocesowosci
def run_scraper(all_urls, num_processes=None):
    if not num_processes:
        num_processes = multiprocessing.cpu_count()
    
    chunk_size = (len(all_urls) + num_processes - 1) // num_processes
    chunks = [all_urls[i:i + chunk_size] for i in range(0, len(all_urls), chunk_size)]

    with multiprocessing.Pool(processes=num_processes) as pool:
        results = pool.map(process_urls, chunks)

    # scalanie wynikow z watkow
    merged_emails = {}
    merged_postal_codes = {} # New
    merged_social_media_links = {} # New

    for res_dict in results:
        if isinstance(res_dict, dict):
            merged_emails.update(res_dict.get('emails', {}))
            merged_postal_codes.update(res_dict.get('postal_codes', {}))
            merged_social_media_links.update(res_dict.get('social_media_links', {}))
   
    return {
        'emails': merged_emails,
        'postal_codes': merged_postal_codes,
        'social_media_links': merged_social_media_links
    }

def save_to_mongo(scraped_results):
    client = None # Initialize client to None for the finally block
    try:
        client = MongoClient("mongodb://mongo:27017")
        db = client["scraperPRIR"]
        
        emails_data = scraped_results.get('emails', {})
        postal_codes_data = scraped_results.get('postal_codes', {})
        social_media_data = scraped_results.get('social_media_links', {})

        email_collection = db["emaile"]
        email_count = 0
        for email, url_domain in emails_data.items():
            email_collection.update_one(
                {"email": email, "url": url_domain}, # Query by email and originating domain
                {"$setOnInsert": {"email": email, "url": url_domain}},
                upsert=True
            )
            email_count += 1
        if email_count > 0: print(f"Zapisano/zaktualizowano {email_count} adresów email do Mongo")

        kody_collection = db["kody_pocztowe_miejscowosci"] 
        kody_count = 0
        for (code, locality), url_domain in postal_codes_data.items():
            kody_collection.update_one(
                {"code": code, "locality": locality, "url": url_domain},
                {"$setOnInsert": {"code": code, "locality": locality, "url": url_domain}},
                upsert=True
            )
            kody_count += 1
        if kody_count > 0: print(f"Zapisano/zaktualizowano {kody_count} kodów pocztowych/miejscowości do Mongo")

        social_collection = db["social_media_links"]
        social_count = 0
        for link, url_domain in social_media_data.items():
            social_collection.update_one(
                {"link": link, "url": url_domain},
                {"$setOnInsert": {"link": link, "url": url_domain}},
                upsert=True
            )
            social_count += 1
        if social_count > 0: print(f"Zapisano/zaktualizowano {social_count} linków social media do Mongo")

    except Exception as e:
        print(f"Błąd zapisu do MongoDB: {e}")
    finally:
        if client:
            client.close()


def check_queue():
    queue_file = '/app/shared_queue_dir/queue.txt'
    processed_urls = set()

    while True:
        if os.path.exists(queue_file):
            try:
                with open(queue_file, 'r') as f:
                    urls_to_process_this_round = [
                        url.strip() for url in f.readlines() 
                        if url.strip() and url.strip() not in processed_urls
                    ]
            except IOError as e:
                print(f"Błąd odczytu pliku kolejki {queue_file}: {e}")
                time.sleep(5)
                continue

            if urls_to_process_this_round:
                print(f"Przetwarzanie adresów URL z kolejki: {urls_to_process_this_round}")

                scraped_results = run_scraper(urls_to_process_this_round)
                
                print(f"Dane po przetworzeniu: "
                      f"Emaile: {len(scraped_results.get('emails', {}))}, "
                      f"Kody pocztowe: {len(scraped_results.get('postal_codes', {}))}, "
                      f"Linki social media: {len(scraped_results.get('social_media_links', {}))}")

                data_found_to_save = False
                if scraped_results:
                    if scraped_results.get('emails'):
                        data_found_to_save = True
                    elif scraped_results.get('postal_codes'):
                        data_found_to_save = True
                    elif scraped_results.get('social_media_links'):
                        data_found_to_save = True
                
                if data_found_to_save:
                    save_to_mongo(scraped_results)
                else:
                    print("Nie znaleziono nowych danych (e-maile, kody pocztowe, linki social media) dla przetworzonych adresów URL.")
                
                processed_urls.update(urls_to_process_this_round)

                try:
                    all_lines_in_queue = []
                    if os.path.exists(queue_file):
                         with open(queue_file, 'r') as f:
                            all_lines_in_queue = f.readlines()
                    
                    with open(queue_file, 'w') as f:
                        lines_kept = 0
                        for line in all_lines_in_queue:
                            if line.strip() not in processed_urls:
                                f.write(line)
                                lines_kept +=1
                except IOError as e:
                    print(f"Błąd zapisu do pliku kolejki {queue_file} po przetworzeniu: {e}")

        time.sleep(5)

if __name__ == "__main__":
    print("Engine started, monitoring queue...")
    check_queue()