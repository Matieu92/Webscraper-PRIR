import asyncio
import aiohttp
import multiprocessing
from bs4 import BeautifulSoup

async def fetch(url, session):
    try:
        async with session.get(url, timeout=10) as response:
            content = await response.text()
            soup = BeautifulSoup(content, 'html.parser')
            soup.encoding='utf-8'

            author_meta = soup.find('meta', attrs={'name': 'author'})
            if author_meta and author_meta.get('content'):
                author = author_meta['content'].strip()
            else:
                author = 'Brak autora'

            return {
                'url': url,
                'status': response.status,
                'author': author,
            }
        
    except Exception as e:
        return {
            'url': url,
            'error': {'Błąd podczas pobierania strony', +url}
        }

async def fetch_all(urls):
    async with aiohttp.ClientSession() as session:
        tasks = [fetch(url, session) for url in urls]
        return await asyncio.gather(*tasks)

def process_urls(urls):
    return asyncio.run(fetch_all(urls))

def run_scraper(all_urls, num_processes=None):
    if not num_processes:
        num_processes = multiprocessing.cpu_count()
    
    chunk_size = (len(all_urls) + num_processes - 1) // num_processes
    chunks = [all_urls[i:i + chunk_size] for i in range(0, len(all_urls), chunk_size)]

    with multiprocessing.Pool(processes=num_processes) as pool:
        results = pool.map(process_urls, chunks)

    merged_results = []
    for result in results:
        merged_results.extend(result)

    return merged_results

if __name__ == "__main__":
    urls = [
        'https://ans-elblag.pl'
    ]
    results = run_scraper(urls)
    for res in results:
        print(res)
