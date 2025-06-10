from flask import Blueprint, flash, g, redirect, render_template, request, url_for
from pymongo import MongoClient
import os
import sys
sys.path.append('/app')  # Dodanie ścieżki do korzenia projektu

print("Loading scraper.py")

bp = Blueprint('scraper', __name__)

# Połączenie z MongoDB w kontenerze Docker
try:
    client = MongoClient('mongodb://mongo:27017/', serverSelectionTimeoutMS=5000)
    client.admin.command('ismaster') 
    db = client['scraperPRIR']
    emaile_collection = db['emaile']
    postal_codes_collection = db['kody_pocztowe_miejscowosci']
    social_media_collection = db['social_media_links']
    print(f"Successfully connected to MongoDB at mongodb://mongo:27017/")
except Exception as e:
    print(f"Failed to connect to MongoDB: {e}")
    db = None 
    emaile_collection = None
    postal_codes_collection = None
    social_media_collection = None


def check_db_connection():
    # Sprawdzenie, czy 'db' nie jest None jest wystarczające,
    # ponieważ jeśli 'db' jest None, to kolekcje też będą None.
    if db is None:
        flash('Database connection error. Please try again later.', 'error')
        return False
    return True

@bp.route('/', endpoint='scraper_index')
def index():
    print("Accessing scraper index")
    if not check_db_connection():
        return render_template('scraper/index.html', urls=[])
        
    distinct_source_urls = set()
    # POPRAWKA: Sprawdzaj 'is not None' zamiast 'if kolekcja:'
    if emaile_collection is not None:
        distinct_source_urls.update(emaile_collection.distinct('url'))
    if postal_codes_collection is not None:
        distinct_source_urls.update(postal_codes_collection.distinct('url'))
    if social_media_collection is not None:
        distinct_source_urls.update(social_media_collection.distinct('url'))
    
    sorted_urls = sorted(list(distinct_source_urls))
    return render_template('scraper/index.html', urls=sorted_urls)

@bp.route('/scrape', methods=('GET', 'POST'), endpoint='scraper_scrape')
def scrape():
    print("Accessing scrape view")
    if request.method == 'POST':
        url_to_scrape = request.form.get('url', '').strip()
        print(f"Received URL for scraping: {url_to_scrape}")
        error = None

        if not url_to_scrape:
            error = 'URL is required.'
        elif not (url_to_scrape.startswith('http://') or url_to_scrape.startswith('https://')):
             error = 'URL must start with http:// or https://'
        else:
            shared_queue_dir = '/app/shared_queue_dir'
            if not os.path.exists(shared_queue_dir):
                try:
                    os.makedirs(shared_queue_dir, exist_ok=True)
                except OSError as e:
                    error = f'Could not create shared directory for queue: {e}'
            
            if not error:
                queue_file = os.path.join(shared_queue_dir, 'queue.txt')
                try:
                    with open(queue_file, 'a') as f:
                        f.write(f"{url_to_scrape}\n")
                    print(f"Added URL {url_to_scrape} to queue file: {queue_file}")
                    flash(f'Scraping for {url_to_scrape} has been queued. Results will appear later.', 'info')
                    return redirect(url_for('scraper.scraper_index'))
                except Exception as e:
                    error = f'Error adding URL to queue: {str(e)}'
                    print(f"Queue writing error: {str(e)}")

        if error:
            flash(error, 'error')

    return render_template('scraper/scrape.html')

@bp.route('/results/<path:scraped_domain_url>', endpoint='scraper_results')
def results(scraped_domain_url):
    print(f"Accessing results overview for domain: {scraped_domain_url}")
    if not check_db_connection():
        return redirect(url_for('scraper.scraper_index'))

    has_any_data = False
    # POPRAWKA: Sprawdzaj 'is not None'
    if emaile_collection is not None and emaile_collection.count_documents({'url': scraped_domain_url}) > 0:
        has_any_data = True
    elif postal_codes_collection is not None and postal_codes_collection.count_documents({'url': scraped_domain_url}) > 0:
        has_any_data = True
    elif social_media_collection is not None and social_media_collection.count_documents({'url': scraped_domain_url}) > 0:
        has_any_data = True
    
    if not has_any_data:
        flash(f'No data found for the domain: {scraped_domain_url}. It might still be processing, or no relevant data was extractable.', 'warning')
        return redirect(url_for('scraper.scraper_index'))
        
    return render_template('scraper/results.html', current_scraped_domain=scraped_domain_url)

@bp.route('/results/<path:scraped_domain_url>/emails', endpoint='scraper_results_emails')
def results_emails(scraped_domain_url):
    print(f"Accessing email results for domain: {scraped_domain_url}")
    if not check_db_connection():
        return redirect(url_for('scraper.scraper_results', scraped_domain_url=scraped_domain_url))
        
    email_data = []
    if emaile_collection is not None:
        email_data = list(emaile_collection.find({'url': scraped_domain_url}, {'_id': 0, 'email': 1}))
    
    return render_template('scraper/results_emails.html', current_scraped_domain=scraped_domain_url, emails=email_data)

@bp.route('/results/<path:scraped_domain_url>/postal_codes', endpoint='scraper_results_postal_codes')
def results_postal_codes(scraped_domain_url):
    print(f"Accessing postal code results for domain: {scraped_domain_url}")
    if not check_db_connection():
        return redirect(url_for('scraper.scraper_results', scraped_domain_url=scraped_domain_url))

    pc_data = []
    if postal_codes_collection is not None:
        pc_data = list(postal_codes_collection.find({'url': scraped_domain_url}, {'_id': 0, 'code': 1, 'locality': 1}))
    
    return render_template('scraper/results_postal_codes.html', current_scraped_domain=scraped_domain_url, postal_codes=pc_data)

@bp.route('/results/<path:scraped_domain_url>/social_media', endpoint='scraper_results_social_media')
def results_social_media(scraped_domain_url):
    print(f"Accessing social media results for domain: {scraped_domain_url}")
    if not check_db_connection():
        return redirect(url_for('scraper.scraper_results', scraped_domain_url=scraped_domain_url))
        
    sm_data = []
    if social_media_collection is not None:
        sm_data = list(social_media_collection.find({'url': scraped_domain_url}, {'_id': 0, 'link': 1}))

    return render_template('scraper/results_social_media.html', current_scraped_domain=scraped_domain_url, social_links=sm_data)