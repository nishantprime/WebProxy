from flask import Flask, request, Response
import requests
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from bs4 import BeautifulSoup
import time # Optional: for adding waits
import random

REALISTIC_USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/109.0'
]

def scrape(url, cookies=None):
    try:
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument("--window-size=1920,1080") # Set a common window size
        chrome_options.add_argument("--lang=en-US,en;q=0.9") # Set language
        user_agent = random.choice(REALISTIC_USER_AGENTS)
        chrome_options.add_argument(f'user-agent={user_agent}')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled') # Try to hide navigator.webdriver
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        driver = webdriver.Chrome(options=chrome_options)

        print(f"Fetching URL: {url}")

        # Add cookies if provided
        if cookies:
            for cookie in cookies:
                cookie_domain = cookie.get('domain')
                base_url = f"https://{cookie_domain.lstrip('.')}/"
                driver.get(base_url)
                time.sleep(1)
                driver.add_cookie(cookie)

        driver.get(url)

        time.sleep(3)

        dom_content = driver.page_source
        return dom_content

    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None


    finally:
        if driver:
            driver.quit()




server_url = os.getenv('url')

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
}

js_code = f"""
<script>
    document.addEventListener('DOMContentLoaded', () => {{
        document.body.addEventListener('click', e => {{
            const targetUrl = e.target.getAttribute('href');
            const isExternalLink = targetUrl && targetUrl.startsWith('http') && !targetUrl.startsWith('https://{server_url}');
            
            if (isExternalLink && !window.confirm('You are leaving the proxy site and going to ' + targetUrl + '. Continue?')) {{
                e.preventDefault();
            }}
        }});
    }});
</script>
"""

def modify_links(base_url, html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    for tag in soup.find_all(['a'], href=True):
        old_url = tag['href']

        if '//' not in old_url:
            new_url = f'{base_url}/{old_url.lstrip("/")}'
            tag['href'] = new_url

    return str(soup)


app = Flask(__name__)

user_site = 'https://www.wiki.com'

# Create a session and set headers
session = requests.Session()
session.headers.update(headers)

@app.route('/clone', methods=['GET', 'POST'])
def clone_site():
    global user_site
    if request.method == 'POST':
        site = request.form.get('site', '')
        if site.startswith('www'):
            site = 'https://' + site
        user_site = site.rstrip('/')
        
        return f"User site set to: {user_site}<br><br><a href='/'>Return"

    return f"""
Currently cloning: {user_site}

<form method='post'>
    <label for='site'>Enter Website URL:</label>
    <input type='text' id='site' name='site' value='https://'>
    <input type='submit' value='Clone'>
</form>
"""

def fetch_and_modify_content(url):
    full_url = user_site.rstrip('/') + '/' + url.lstrip('/')
    user_sitename = urlparse(user_site).netloc # More robust way to get domain
    dom_content = scrape(full_url) # Pass cookies if you have them managed elsewhere

    if dom_content is None:
        return Response(f"Failed to fetch content using Selenium from {full_url}", status=502, content_type='text/plain')
    content_type = 'text/html'
    html_bytes = dom_content.encode('utf-8') # Modifications often need bytes

    try:
        modified_content = html_bytes.replace(user_sitename.encode('utf-8'), server_url.encode('utf-8'))
        modified_content = modified_content.replace(b'</head>', js_code.encode('utf-8') + b'</head>', 1)
        return Response(modified_content, content_type=content_type)

    except Exception as e:
        return Response(f"Error processing content from {full_url}: {e}", status=500, content_type='text/plain')



@app.route('/<path:url>')
def proxy(url):
    if 'http' not in url:
        modified_content, content_type = fetch_and_modify_content(url)
        return Response(modified_content, content_type=content_type)
    else:
        response = session.get(url)
        content_type = response.headers['Content-Type']
        modified_content = modify_links(url, response.content)
        return Response(modified_content, content_type=content_type)
            

@app.route('/')
def site():
    modified_content, content_type = fetch_and_modify_content('')
    return Response(modified_content, content_type=content_type)

if __name__ == '__main__':
    app.run(debug=True)
