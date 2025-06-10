from flask import Blueprint, flash, g, redirect, render_template, request, url_for
from .auth import login_required
from pymongo import MongoClient
import sys
sys.path.append('/app')  # Dodanie ścieżki do korzenia projektu
from engine.engine import run_scraper  # Bezwzględny import

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
        url = request.form['url']
        error = None

        if not url:
            error = 'URL is required.'

        if error is None:
            flash(error)
        else:
            try:
                emails = run_scraper([url])
                if emails:
                    for email in emails:
                        emaile_collection.update_one(
                            {"email": email, "url": url},
                            {"$setOnInsert": {"email": email, "url": url}},
                            upsert=True
                        )
                    flash(f'Scraping completed successfully. Found {len(emails)} emails.')
                else:
                    flash('No emails found.')
                return redirect(url_for('scraper.scraper_index'))  # Zaktualizowano na nowy endpoint
            except Exception as e:
                flash(f'Error during scraping: {str(e)}')
                print(f"Scraping error: {str(e)}")  # Debug

    return render_template('scraper/scrape.html')

@bp.route('/results/<url>', endpoint='scraper_results')
def results(url):
    print(f"Accessing results for {url}")  # Debug
    emails = list(emaile_collection.find({'url': url}))
    if not emails:
        flash('No emails found for this URL.')
        return redirect(url_for('scraper.scraper_index'))  # Zaktualizowano na nowy endpoint
    return render_template('scraper/results.html', data={'url': url, 'emails': emails})