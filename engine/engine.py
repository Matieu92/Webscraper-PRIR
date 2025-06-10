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

# zebranie danych z jednej strony
async def fetch(url, session, visited=None, all_data=None, emails=None):
    if visited is None:
        visited = set()
    if all_data is None:
        all_data = []
    if emails is None:
        emails = {} 
    
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
                extrude = ('.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.zip', '.rar', '.7z', '.txt', '.csv', '.jpg', '.jpeg', '.png')
                path = parsed_url.path.lower()
                if not any(path.endswith(ext) for ext in extrude) and parsed_url.netloc == base_domain and parsed_url.scheme in ('http', 'https'):
                    if absolute_url not in visited:
                        sub_urls.append(absolute_url)
                        print(absolute_url)

            # przeszukiwanie podstron
            tasks = [fetch(sub_url, session, visited, all_data, emails) for sub_url in sub_urls]
            await asyncio.gather(*tasks)

    except Exception as e:
        all_data.append({'url': url, 'status': None, 'error': f'Błąd: {str(e)}'})

# async taski zbierajace dane, jedna sesja TCP
async def fetch_all(urls):
    all_data = []
    emails = {}
    async with aiohttp.ClientSession() as session:
        tasks = [fetch(url, session, all_data=all_data, emails=emails) 
                 for url in urls]
        await asyncio.gather(*tasks)
    return emails

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
    merged_data = []
    merged_emails = {}
    for emails in results:
        merged_emails.update(emails)

    return merged_emails

def save_to_mongo(emails):
    try:
        client = MongoClient("mongodb://mongo:27017")
        db = client["scraperPRIR"]
        collection = db["emaile"]

        count = 0
        for email, url in emails.items():
            collection.update_one(
                {"email": email},
                {"$setOnInsert": {"email": email, "url": url}},
                upsert=True
            )
            count += 1
        print(f"Zapisano {count} adresów do Mongo")
    except Exception as e:
        print(f"Błąd zapisu: {e}")
    finally:
        client.close()

def check_queue():
    queue_file = '/app/shared_queue_dir/queue.txt'
    processed_urls = set()

    while True:
        if os.path.exists(queue_file):
            with open(queue_file, 'r') as f:
                urls = [url.strip() for url in f.readlines() if url.strip() and url.strip() not in processed_urls]
            
            if urls:
                print(f"Processing URLs from queue: {urls}")  # Debug
                emails = run_scraper(urls)
                print(f"Emails after processing: {emails}")  # Debug
                if emails and any(emails.values()):  # Sprawdzenie, czy są jakiekolwiek emaili
                    save_to_mongo(emails)
                else:
                    print("No emails found for processed URLs")  # Debug
                processed_urls.update(urls)
                
                with open(queue_file, 'r') as f:
                    all_lines = f.readlines()
                with open(queue_file, 'w') as f:
                    f.writelines(line for line in all_lines if line.strip() not in processed_urls)
        
        time.sleep(5)  # Sprawdzanie co 5 sekund

if __name__ == "__main__":
    print("Engine started, monitoring queue...")
    check_queue()