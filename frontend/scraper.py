from flask import Blueprint, flash, g, redirect, render_template, request, url_for
from .auth import login_required
from pymongo import MongoClient
import os
import sys
sys.path.append('/app')  # Dodanie ścieżki do korzenia projektu

print("Loading scraper.py")  # Debug

bp = Blueprint('scraper', __name__)

# Połączenie z MongoDB w kontenerze Docker
client = MongoClient('mongodb://mongo:27017/')
db = client['scraperPRIR']
emaile_collection = db['emaile']
print(f"Connected to MongoDB at mongodb://mongo:27017/")  # Debug

@bp.route('/', endpoint='scraper_index')
def index():
    print("Accessing scraper index")  # Debug
    scraped_urls = emaile_collection.distinct('url')
    return render_template('scraper/index.html', urls=scraped_urls)

@bp.route('/scrape', methods=('GET', 'POST'), endpoint='scraper_scrape')
@login_required
def scrape():
    print("Accessing scrape view")  # Debug
    if request.method == 'POST':
        url = request.form.get('url')  # Użycie .get() dla bezpieczeństwa
        print(f"Received URL: {url}")  # Debug
        error = None

        if not url:
            error = 'URL is required.'
        else:
            queue_file = '/app/shared_queue_dir/queue.txt'
            try:
                with open(queue_file, 'a') as f:
                    f.write(f"{url}\n")
                print(f"Added URL {url} to queue file")  # Debug
                flash('Scraping started. Check results later.')
                return redirect(url_for('scraper.scraper_index'))
            except Exception as e:
                error = f'Error adding to queue: {str(e)}'
                print(f"Queue error: {str(e)}")  # Debug

        if error:
            flash(error)

    return render_template('scraper/scrape.html')

@bp.route('/results/<url>', endpoint='scraper_results')
def results(url):
    print(f"Accessing results for {url}")  # Debug
    emails = list(emaile_collection.find({'url': url}))
    if not emails:
        flash('No emails found for this URL.')
        return redirect(url_for('scraper.scraper_index'))
    return render_template('scraper/results.html', data={'url': url, 'emails': emails})