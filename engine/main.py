import asyncio
import aiohttp
import multiprocessing
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
import warnings
from urllib.parse import urljoin, urlparse
import re

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# zebranie danych z jednej strony
async def fetch(url, session, visited=None, all_data=None, emails=None):
    if visited is None:
        visited = set()
    if all_data is None:
        all_data = []
    if emails is None:
        emails = set()
    
    visited.add(url)

    try:
        async with session.get(url, timeout=10) as response:
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
                        emails.add(email)
            
            # e-mail regex
            page_text = soup.get_text(separator=' ', strip=True)
            email_pattern = r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b'
            found_emails = re.findall(email_pattern, page_text)
            for email in found_emails:
                emails.add(email)

            # zebrane dane
            all_data.append({
                'url': url,
                'status': response.status
            })

            # poszukiwanie podstron
            base_domain = urlparse(url).netloc
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
    emails = set()
    async with aiohttp.ClientSession() as session:
        tasks = [fetch(url, session, all_data=all_data, emails=emails) 
                 for url in urls]
        await asyncio.gather(*tasks)
    return list(emails)

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
    merged_emails = set()
    for emails in results:
        merged_emails.update(emails)

    return list(merged_emails)

if __name__ == "__main__":
    urls = [
    ]
    emails = run_scraper(urls)
    print("E-maile:", emails)